from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def calcola_anomaly_score(feature_df: pd.DataFrame) -> pd.Series:
    """Calcola un anomaly score normalizzato tra 0 e 1."""
    feature_cols = [
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
    ]
    X = feature_df[feature_cols].fillna(0)
    model = IsolationForest(n_estimators=200, contamination="auto", random_state=42)
    model.fit(X)
    raw_scores = -model.score_samples(X)
    min_score = raw_scores.min()
    max_score = raw_scores.max()
    if np.isclose(max_score - min_score, 0):
        return pd.Series(np.zeros(len(X)), index=feature_df.index)
    normalized = (raw_scores - min_score) / (max_score - min_score)
    return pd.Series(np.clip(normalized, 0.0, 1.0), index=feature_df.index)
