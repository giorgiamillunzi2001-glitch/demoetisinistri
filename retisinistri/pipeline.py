from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .anomaly import calcola_anomaly_score
from .communities import trova_gruppi
from .config import load_config
from .features import calcola_feature_gruppo
from .graph_builder import costruisci_grafo, proietta_sinistri
from .metrics import business_case, stress_test
from .models import fit_challenger, fit_champion, salva_coefficienti
from .score_pratica import aggiungi_score_pratica
from .scoring import assegna_fascia, reason_codes
from .synthetic import genera_dataset

ROOT = Path(__file__).resolve().parents[1]


def _root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def esegui_pipeline(config: dict | None = None) -> dict:
    """Pipeline end-to-end di analisi antifrode."""
    cfg = config or load_config()
    processed_dir = _root_path(cfg.get("paths", {}).get("processed_dir", "data/processed"))
    processed_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = _root_path(cfg.get("paths", {}).get("raw_dir", "data/raw"))
    raw_path = raw_dir / "sinistri.csv"
    raw_links = raw_dir / "coinvolgimenti.csv"
    if raw_path.exists() and raw_links.exists():
        sinistri = pd.read_csv(raw_path)
        coinvolgimenti = pd.read_csv(raw_links)
    else:
        sinistri, coinvolgimenti = genera_dataset(n_sinistri=200, n_anelli=4, seed=42)

    sinistri = aggiungi_score_pratica(sinistri, cfg)

    G = costruisci_grafo(sinistri, coinvolgimenti)
    G_proj = proietta_sinistri(G, solo_forti=True)
    community_map = trova_gruppi(G_proj)

    groups = {}
    for group_id in sorted(set(community_map.values())):
        if group_id == -1:
            continue
        ids = [claim_id for claim_id, mapped in community_map.items() if mapped == group_id]
        feat = calcola_feature_gruppo(ids, sinistri, coinvolgimenti, G_proj)
        feat["id_gruppo"] = group_id
        feat["label_frode"] = int((sinistri[sinistri["id_sinistro"].isin(ids)]["label_frode"].mean() > 0.5))
        groups[group_id] = feat

    feature_rows = list(groups.values())
    if not feature_rows:
        feature_rows = [{"id_gruppo": -1, "n_sinistri": 1, "n_persone": 1, "persone_multi_ruolo": 0, "quota_multi_ruolo": 0.0, "sinistri_per_iban": 1.0, "sinistri_per_telefono": 1.0, "quota_officina_top": 0.0, "quota_avvocato_top": 0.0, "finestra_giorni": 0.0, "densita": 0.0, "testimone_ricorrente_max": 0, "importo_totale": 0.0, "score_pratica_medio": 0.0, "label_frode": 0}]

    features_df = pd.DataFrame(feature_rows)
    features_df["anomaly_score"] = calcola_anomaly_score(features_df).values

    model_cols = [
        "n_sinistri",
        "n_persone",
        "persone_multi_ruolo",
        "quota_multi_ruolo",
        "sinistri_per_iban",
        "sinistri_per_telefono",
        "quota_officina_top",
        "quota_avvocato_top",
        "finestra_giorni",
        "densita",
        "testimone_ricorrente_max",
        "importo_totale",
        "score_pratica_medio",
        "anomaly_score",
    ]
    X = features_df[model_cols].fillna(0)
    y = features_df["label_frode"].astype(int)
    X_train, y_train = X, y
    if y.nunique() < 2:
        # Serve almeno un esempio per classe: si aggiunge un profilo "sinistro isolato" (regolare)
        # e, se mancano gruppi regolari, il gruppo stesso fa da riferimento positivo.
        baseline = pd.DataFrame([{col: 0.0 for col in model_cols}])
        baseline["n_sinistri"] = 1.0
        baseline["n_persone"] = 2.0
        X_train = pd.concat([X, baseline], ignore_index=True)
        y_train = pd.concat([y, pd.Series([0 if y.iloc[0] == 1 else 1])], ignore_index=True)
    champion, coefs = fit_champion(X_train, y_train)
    challenger = fit_challenger(X_train, y_train)
    probs = champion.predict_proba(X)[:, 1]
    features_df["score_rete"] = [round(100 * p) for p in probs]
    features_df["fascia"] = features_df["score_rete"].apply(lambda score: assegna_fascia(score, cfg.get("scoring", {}).get("soglia_media", 40), cfg.get("scoring", {}).get("soglia_alta", 70)))

    # Score di rete a livello di singolo sinistro (eredita quello del gruppo)
    score_by_group = {str(g): int(sc) for g, sc in zip(features_df["id_gruppo"], features_df["score_rete"])}
    sinistri["id_gruppo"] = sinistri["id_sinistro"].map(lambda sid: str(community_map.get(sid, -1)))
    sinistri["score_rete"] = sinistri["id_gruppo"].map(lambda g: score_by_group.get(g, 0))
    sinistri["fascia"] = sinistri["score_rete"].apply(lambda score: assegna_fascia(score, cfg.get("scoring", {}).get("soglia_media", 40), cfg.get("scoring", {}).get("soglia_alta", 70)))

    alerts = []
    for _, row in features_df.iterrows():
        if row["fascia"] in {"media", "alta"}:
            feature_values = {col: float(row[col]) for col in model_cols if col in row}
            reasons = reason_codes(feature_values, coefs, top_n=3)
            alert = {
                "id_gruppo": str(row.get("id_gruppo", "-1")),
                "score_rete": int(row["score_rete"]),
                "score_pratica_medio": float(row.get("score_pratica_medio", 0.0)),
                "fascia": row["fascia"],
                "reason_codes": reasons,
                "feature_gruppo": feature_values,
                "anomaly_score": float(row.get("anomaly_score", 0.0)),
                "label_frode": int(row.get("label_frode", 0)),
                "persone": [],
            }
            alerts.append(alert)

    (processed_dir / "alert.json").write_text(json.dumps(alerts, ensure_ascii=False, indent=2), encoding="utf-8")
    salva_coefficienti(coefs, processed_dir / "coefficienti.csv")
    metrics = business_case(cfg)
    kpis = stress_test(cfg)
    return {
        "config": cfg,
        "grafo": G,
        "grafo_proiettato": G_proj,
        "coefficienti": coefs,
        "model_cols": model_cols,
        "sinistri": sinistri,
        "coinvolgimenti": coinvolgimenti,
        "communities": community_map,
        "feature_df": features_df,
        "model": champion,
        "challenger": challenger,
        "alerts": alerts,
        "kpi": metrics,
        "stress_test": kpis,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline RetiSinistri")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    esegui_pipeline(cfg)


if __name__ == "__main__":
    main()
