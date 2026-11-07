from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FORBIDDEN_FEATURES = {"provincia", "cap", "nazionalita", "eta", "sesso"}


def valida_feature_vietate(df: pd.DataFrame) -> None:
    """Il modello non accetta feature sensibili."""
    forbidden = [feature for feature in FORBIDDEN_FEATURES if feature in df.columns]
    if forbidden:
        raise ValueError(f"Feature vietate rilevate: {sorted(forbidden)}")


def fit_champion(X: pd.DataFrame, y: pd.Series) -> tuple[Pipeline, dict[str, float]]:
    """Addestra il champion (regressione logistica)."""
    valida_feature_vietate(X)
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("logreg", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
    ])
    model.fit(X, y)
    coefs = {feature: float(coef) for feature, coef in zip(X.columns, model.named_steps["logreg"].coef_[0])}
    return model, coefs


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
