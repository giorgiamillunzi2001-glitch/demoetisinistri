from __future__ import annotations

from typing import Any

import pandas as pd

from .config import load_config


def calcola_score_pratica(sinistro: dict[str, Any] | pd.Series, config: dict | None = None) -> float:
    """Calcola il punteggio AS-IS per un singolo sinistro."""
    cfg = config or load_config()
    weights = cfg.get("asis", {}).get("weights", {})
    score = 0.0
    amount = float(sinistro.get("importo_richiesto", 0) or 0)
    if amount > 5000:
        score += float(weights.get("importo_richiesto", 30))
    if int(sinistro.get("giorni_da_inizio_polizza", 0) or 0) < 30:
        score += float(weights.get("giorni_da_inizio_polizza", 25))
    if bool(sinistro.get("orario_notturno", False)):
        score += float(weights.get("orario_notturno", 20))
    if not bool(sinistro.get("verbale_autorita", False)):
        score += float(weights.get("verbale_autorita", 15))
    if bool(sinistro.get("testimone", False)):
        score += float(weights.get("testimone", 10))
    return min(100.0, score)


def aggiungi_score_pratica(sinistri: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """Applica il punteggio AS-IS a un DataFrame di sinistri."""
    out = sinistri.copy()
    cfg = config or load_config()
    out["score_pratica"] = out.apply(lambda row: calcola_score_pratica(row.to_dict(), cfg), axis=1)
    out["alert_asis"] = out["score_pratica"] >= float(cfg.get("asis", {}).get("threshold", 50))
    return out
