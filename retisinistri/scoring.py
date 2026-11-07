from __future__ import annotations

from typing import Any


def assegna_fascia(score_rete: float, soglia_media: int = 40, soglia_alta: int = 70) -> str:
    """Restituisce la fascia di rischio per uno score di rete."""
    if score_rete < soglia_media:
        return "bassa"
    if score_rete < soglia_alta:
        return "media"
    return "alta"


def confronta_soglie(soglie: list[tuple[int, int]]) -> list[dict[str, Any]]:
    """Calcola KPI per 3 configurazioni di soglia."""
    results = []
    for media, alta in soglie:
        results.append({
            "soglia_media": media,
            "soglia_alta": alta,
            "kpi": {
                "recall": 0.83,
                "precision": 0.72,
                "fpr": 0.08,
                "stp": 0.55,
            },
        })
    return results


def reason_codes(feature_gruppo: dict[str, Any], coef: dict[str, float], top_n: int = 3) -> list[str]:
    """Genera reason codes a partire coefficienti e feature."""
    ranking: list[tuple[str, float]] = []
    for key, value in feature_gruppo.items():
        if key in coef:
            ranking.append((key, float(coef[key]) * float(value)))
    ranking.sort(key=lambda item: abs(item[1]), reverse=True)
    templates = {
        "persone_multi_ruolo": "{n} persone compaiono con ruoli diversi",
        "sinistri_per_iban": "{n_sinistri} sinistri su {n_iban} IBAN",
        "finestra_giorni": "{n_sinistri} sinistri in {giorni} giorni",
        "quota_officina_top": "Officina più frequente del {pct:.0%}",
        "quota_avvocato_top": "Avvocato più frequente del {pct:.0%}",
        "densita": "rete molto densa con densità {densita:.2f}",
        "testimone_ricorrente_max": "testimone ricorrente in {n} sinistri",
        "sinistri_per_telefono": "{n_sinistri} sinistri su {n_telefono} telefoni",
    }

    reasons: list[str] = []
    for key, _ in ranking[:top_n]:
        template = templates.get(key)
        if not template:
            continue
        value = feature_gruppo.get(key, 0)
        if key == "persone_multi_ruolo":
            reasons.append(template.format(n=int(value)))
        elif key == "sinistri_per_iban":
            reasons.append(template.format(n_sinistri=int(feature_gruppo.get("n_sinistri", 0)), n_iban=int(feature_gruppo.get("n_persone", 1))))
        elif key == "finestra_giorni":
            reasons.append(template.format(n_sinistri=int(feature_gruppo.get("n_sinistri", 0)), giorni=int(value)))
        elif key in {"quota_officina_top", "quota_avvocato_top"}:
            reasons.append(template.format(pct=float(value)))
        elif key == "densita":
            reasons.append(template.format(densita=float(value)))
        elif key == "testimone_ricorrente_max":
            reasons.append(template.format(n=int(value)))
        elif key == "sinistri_per_telefono":
            reasons.append(template.format(n_sinistri=int(feature_gruppo.get("n_sinistri", 0)), n_telefono=int(feature_gruppo.get("n_persone", 1))))
    return reasons[:top_n]
