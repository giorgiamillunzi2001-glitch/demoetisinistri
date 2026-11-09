from __future__ import annotations

from typing import Any

import numpy as np


def matrice_confusione(y_true: list[int] | np.ndarray, y_pred: list[int] | np.ndarray) -> dict[str, int]:
    """Restituisce la matrice di confusione in termini di TP, FP, FN, TN."""
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn}


def metriche_kpi(y_true: list[int] | np.ndarray, y_pred: list[int] | np.ndarray, y_score: list[float] | np.ndarray | None = None) -> dict[str, float]:
    """Calcola recall, precision, FPR e AUC."""
    matrix = matrice_confusione(y_true, y_pred)
    tp = matrix["TP"]
    fp = matrix["FP"]
    fn = matrix["FN"]
    tn = matrix["TN"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    auc = 0.0
    if y_score is not None:
        from sklearn.metrics import roc_auc_score

        auc = float(roc_auc_score(y_true, y_score))
    return {"precision": precision, "recall": recall, "FPR": fpr, "AUC": auc}


COSTO_MEDIO_SINISTRO = 4962  # IVASS, Relazione annuale 2024, autovetture

# Parametri reali di calibrazione (config.yaml > calibrazione): etichetta, formato, anno, fonte.
FONTI_CALIBRAZIONE = {
    "costo_medio_sinistro": ("Costo medio di un sinistro (autovetture)", "euro", "2024",
                             "IVASS, Relazione annuale 2024"),
    "quota_rischio_frode": ("Sinistri a rischio frode", "pct", "2024",
                            "IVASS, Relazione antifrode 2024 (613 mila su 2,509 mln)"),
    "quota_approfondimenti": ("Sinistri approfonditi", "pct", "2024", "IVASS, Relazione antifrode 2024 (292 mila)"),
    "quota_frodi_accertate": ("Frodi accertate", "pct", "2024", "IVASS, Relazione antifrode 2024 (38 mila)"),
    "risparmio_medio_frode": ("Risparmio medio per frode accertata", "euro", "2024",
                              "IVASS, Relazione antifrode 2024 (202,5 mln € / 38 mila)"),
    "rischio_nord": ("Sinistri a rischio frode, Nord", "pct", "2023", "IVASS, Relazione antifrode 2023"),
    "rischio_sud": ("Sinistri a rischio frode, Sud", "pct", "2023", "IVASS, Relazione antifrode 2023"),
    "rischio_campania": ("Sinistri a rischio frode, Campania", "pct", "2023", "IVASS, Relazione antifrode 2023"),
}


def parametri_reali(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Parametri reali usati nella calibrazione, con anno e fonte (per la tabella del business case)."""
    cal = config.get("calibrazione", {}) or {}
    return [{"chiave": k, "parametro": nome, "valore": cal[k], "formato": fmt, "anno": anno, "fonte": fonte}
            for k, (nome, fmt, anno, fonte) in FONTI_CALIBRAZIONE.items() if k in cal]


def business_case(config: dict[str, Any], f_rotture: int = 0, n_alert: int = 0) -> dict[str, float]:
    """Valore netto annuo e primo anno, sulla base delle ipotesi dichiarate.

    Costo dei sinistri = premi × loss ratio; sinistri stimati all'anno = costo dei sinistri / costo
    medio di un sinistro (IVASS); valore = costo dei sinistri × quota di frodi extra evitate.
    """
    b = config.get("business", {})
    premi = float(b.get("premi_rc_auto", 239_300_000))
    loss_ratio = float(b.get("loss_ratio", 0.75))
    quota = float(b.get("quota_frodi_extra_evitate", 0.005))
    costi_annui = float(b.get("costi_annui", 300_000))
    costo_una_tantum = float(b.get("costo_una_tantum", 500_000))
    costo_medio = float((config.get("calibrazione", {}) or {}).get("costo_medio_sinistro", COSTO_MEDIO_SINISTRO))
    costo_sinistri = premi * loss_ratio
    sinistri_annui = costo_sinistri / costo_medio if costo_medio else 0.0
    valore_avviato = costo_sinistri * quota
    netto_annuo = valore_avviato - costi_annui
    primo_anno = netto_annuo - costo_una_tantum
    return {"valore_annuo": netto_annuo, "primo_anno": primo_anno, "valore_avviato": valore_avviato,
            "costo_sinistri": costo_sinistri, "sinistri_annui": sinistri_annui, "costo_medio_sinistro": costo_medio}


def stress_test(config: dict[str, Any]) -> list[dict[str, float]]:
    """Ricalcola il business case per diverse quote di frodi extra evitate."""
    quotas = [0.003, 0.005, 0.01, 0.02]
    results = []
    for quota in quotas:
        cfg = dict(config)
        cfg["business"] = dict(config.get("business", {}), quota_frodi_extra_evitate=quota)
        results.append({"quota": quota, **business_case(cfg)})
    return results
