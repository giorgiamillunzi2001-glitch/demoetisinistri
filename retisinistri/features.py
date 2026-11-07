from __future__ import annotations

from collections import Counter

import networkx as nx
import pandas as pd


def _group_ids_to_claims(gruppo_ids: list[str], sinistri: pd.DataFrame) -> pd.DataFrame:
    return sinistri[sinistri["id_sinistro"].isin(gruppo_ids)].copy()


def calcola_feature_gruppo(gruppo_ids: list[str], sinistri: pd.DataFrame, coinvolgimenti: pd.DataFrame, G: nx.Graph) -> dict:
    """Genera le feature di rete a livello di gruppo."""
    if not gruppo_ids:
        return {"n_sinistri": 0}
    gruppo_sinistri = _group_ids_to_claims(gruppo_ids, sinistri)
    gruppo_coinvolgimenti = coinvolgimenti[coinvolgimenti["id_sinistro"].isin(gruppo_ids)].copy()

    persone = gruppo_coinvolgimenti["id_persona"].dropna().unique()
    roles_by_person = {}
    for _, row in gruppo_coinvolgimenti.iterrows():
        person = row.get("id_persona")
        if pd.isna(person):
            continue
        roles_by_person.setdefault(person, set()).add(row.get("ruolo"))
    persone_multi_ruolo = sum(1 for roles in roles_by_person.values() if len(roles) >= 2)

    iban_distinti = gruppo_coinvolgimenti["iban"].dropna().nunique()
    telefoni_distinti = gruppo_coinvolgimenti["telefono"].dropna().nunique()

    office_counts = gruppo_sinistri["id_officina"].value_counts()
    avvocato_counts = gruppo_sinistri["id_avvocato"].fillna("NA").value_counts()

    role_counts = gruppo_coinvolgimenti["ruolo"].value_counts()
    max_witness = int(role_counts.get("testimone", 0))

    subgraph = G.subgraph([f"sinistro:{sinistro_id}" for sinistro_id in gruppo_ids])
    densita = nx.density(subgraph) if subgraph.number_of_nodes() > 1 else 0.0

    data_sinistri = pd.to_datetime(gruppo_sinistri["data_sinistro"], errors="coerce")
    finestra = 0.0
    if data_sinistri.notna().any():
        valid_dates = data_sinistri.dropna()
        if len(valid_dates) > 1:
            finestra = float((valid_dates.max() - valid_dates.min()).days)

    return {
        "n_sinistri": len(gruppo_sinistri),
        "n_persone": len(persone),
        "persone_multi_ruolo": persone_multi_ruolo,
        "quota_multi_ruolo": (persone_multi_ruolo / len(persone)) if len(persone) else 0.0,
        "sinistri_per_iban": (len(gruppo_sinistri) / iban_distinti) if iban_distinti else 0.0,
        "sinistri_per_telefono": (len(gruppo_sinistri) / telefoni_distinti) if telefoni_distinti else 0.0,
        "quota_officina_top": float((office_counts.max() / len(gruppo_sinistri))) if not office_counts.empty else 0.0,
        "quota_avvocato_top": float((avvocato_counts.max() / len(gruppo_sinistri))) if not avvocato_counts.empty else 0.0,
        "finestra_giorni": finestra,
        "densita": densita,
        "testimone_ricorrente_max": max_witness,
        "importo_totale": float(gruppo_sinistri["importo_richiesto"].sum()),
        "score_pratica_medio": float(gruppo_sinistri["score_pratica"].mean()) if "score_pratica" in gruppo_sinistri.columns else 0.0,
    }


def calcola_feature_sinistro(sinistro_id: str, sinistri: pd.DataFrame, coinvolgimenti: pd.DataFrame, G: nx.Graph) -> dict:
    """Feature per sinistri isolati."""
    if sinistro_id not in sinistri["id_sinistro"].values:
        return {"grado_entita_forti": 0}
    sinistro_node = f"sinistro:{sinistro_id}"
    strong_neighbors = [
        n for n in G.neighbors(sinistro_node)
        if G.nodes.get(n, {}).get("tipo") in {"persona", "iban", "telefono"}
    ]
    shared = 0
    for other in sinistri["id_sinistro"].dropna():
        if other == sinistro_id:
            continue
        other_node = f"sinistro:{other}"
        if other_node in G and len(set(G.neighbors(sinistro_node)) & set(G.neighbors(other_node))) > 0:
            shared += 1
    return {"grado_entita_forti": len(strong_neighbors) + shared}
