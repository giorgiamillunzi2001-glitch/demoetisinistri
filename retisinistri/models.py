from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FORBIDDEN_FEATURES = {"provincia", "cap", "nazionalita", "eta", "sesso"}

# Champion: solo segnali di rete forti e interpretabili. Officine, avvocati e periti sono segnali
# secondari (un'officina convenzionata serve molti clienti regolari) e restano fuori dal modello;
# punteggio regole attuali, densità, persone, importo e anomaly score restano solo a video.
FEATURE_CHAMPION = [
    "quota_multi_ruolo",
    "sinistri_per_iban",
    "sinistri_per_telefono",
    "testimone_ricorrente_max",
    "n_sinistri",
    "finestra_giorni",
]
# Griglia della forza di regolarizzazione L2 (C piccolo = coefficienti più contenuti e stabili)
GRIGLIA_C = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0]


def valida_feature_vietate(df: pd.DataFrame) -> None:
    """Il modello non accetta feature sensibili."""
    forbidden = [feature for feature in FORBIDDEN_FEATURES if feature in df.columns]
    if forbidden:
        raise ValueError(f"Feature vietate rilevate: {sorted(forbidden)}")


def _logistica(C: float = 1.0) -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("logreg", LogisticRegression(C=C, class_weight="balanced", max_iter=2000)),
    ])


def fit_champion(X: pd.DataFrame, y: pd.Series) -> tuple[Pipeline, dict[str, float]]:
    """Addestra il champion: regressione logistica con regolarizzazione L2.

    La forza della regolarizzazione (C) è scelta in cross-validation stratificata (log-loss)
    quando ci sono almeno 3 gruppi per classe; altrimenti si usa C=1. Il C scelto è salvato
    nell'attributo `C_scelto` del modello restituito.
    """
    valida_feature_vietate(X)
    min_classe = int(y.value_counts().min()) if y.nunique() == 2 else 0
    if min_classe >= 3:
        ricerca = GridSearchCV(
            _logistica(),
            {"logreg__C": GRIGLIA_C},
            cv=StratifiedKFold(n_splits=min(3, min_classe), shuffle=True, random_state=42),
            scoring="neg_log_loss",
        )
        ricerca.fit(X, y)
        model = ricerca.best_estimator_
        C_scelto = float(ricerca.best_params_["logreg__C"])
    else:
        model = _logistica(1.0).fit(X, y)
        C_scelto = 1.0
    model.C_scelto = C_scelto
    coefs = {feature: float(coef) for feature, coef in zip(X.columns, model.named_steps["logreg"].coef_[0])}
    return model, coefs


def contributi(model: Pipeline, valori: dict[str, float], colonne: list[str]) -> dict[str, float]:
    """Contributo di ogni feature allo score: coefficiente × valore standardizzato."""
    scaler = model.named_steps["scaler"]
    beta = model.named_steps["logreg"].coef_[0]
    out = {}
    for i, col in enumerate(colonne):
        scala = scaler.scale_[i] if scaler.scale_[i] else 1.0
        out[col] = float(beta[i] * (float(valori.get(col, 0.0)) - scaler.mean_[i]) / scala)
    return out


def fit_challenger(X: pd.DataFrame, y: pd.Series) -> GradientBoostingClassifier:
    """Addestra il challenger in shadow mode."""
    valida_feature_vietate(X)
    model = GradientBoostingClassifier(random_state=42)
    model.fit(X, y)
    return model


def cross_validate_champion(X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    """Valutazione CV 5-fold del champion."""
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("logreg", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
    ])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
    return {"cv_auc_mean": float(scores.mean()), "cv_auc_std": float(scores.std())}


def salva_coefficienti(coef_map: dict[str, float], path: str | Path | None = None) -> pd.DataFrame:
    """Salva i coefficienti in CSV."""
    out = pd.DataFrame([{"feature": key, "beta": value, "odds_ratio": float(np.exp(value))} for key, value in coef_map.items()])
    target = Path(path) if path is not None else Path("data/processed/coefficienti.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False)
    return out
