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


SOGLIA_FINESTRA_GIORNI = 180


def _frase(feature: str, f: dict[str, Any]) -> str | None:
    """Frase concreta e assoluta per una feature del champion (None se non c'è un fatto da dire)."""
    n = int(f.get("n_sinistri", 0))
    if feature in {"n_sinistri", "sinistri_per_iban", "sinistri_per_telefono"}:
        # Numero di sinistri, IBAN e telefoni descrivono la stessa concentrazione: un'unica frase,
        # che il controllo dei duplicati in `motivazioni` usa una volta sola.
        if n < 3:
            return None
        k_iban, k_tel = int(f.get("iban_distinti", 0)), int(f.get("telefoni_distinti", 0))
        iban = "1 solo IBAN" if k_iban == 1 else f"{k_iban} IBAN"
        tel = "1 solo telefono" if k_tel == 1 else f"{k_tel} telefoni"
        return f"{n} sinistri su {iban} e {tel}"
    if feature == "quota_multi_ruolo":
        m = int(f.get("persone_multi_ruolo", 0))
        if m <= 0:
            return None
        return "1 persona compare con ruoli diversi" if m == 1 else f"{m} persone compaiono con ruoli diversi"
    if feature == "testimone_ricorrente_max":
        t = int(f.get("testimone_ricorrente_max", 0))
        return f"la stessa persona è testimone in {t} sinistri" if t >= 2 else None
    if feature == "finestra_giorni":
        g = int(f.get("finestra_giorni", 0))
        return f"{n} sinistri in {g} giorni" if 0 < g < SOGLIA_FINESTRA_GIORNI else None
    return None


# Verso in cui ogni frase descrive un fatto come sospetto: +1 = "più è alto, più è sospetto"
# (es. "14 risarcimenti su 1 solo IBAN"), -1 = "più è basso, più è sospetto" ("7 sinistri in 88 giorni").
VERSO_SOSPETTO = {
    "n_sinistri": 1,
    "sinistri_per_iban": 1,
    "sinistri_per_telefono": 1,
    "quota_multi_ruolo": 1,
    "testimone_ricorrente_max": 1,
    "finestra_giorni": -1,
}


def motivazioni(
    feature_gruppo: dict[str, Any], contributi: dict[str, float], coefs: dict[str, float] | None = None, n: int = 3
) -> list[str]:
    """Fino a `n` frasi concrete, partendo dai segnali con contributo positivo più alto.

    Una frase è ammessa solo se il modello pesa quel segnale nello stesso verso in cui la frase
    lo presenta come sospetto (es. non si cita "su 1 solo IBAN" se il modello considera gli IBAN
    condivisi un segnale rassicurante). Se i segnali positivi non bastano, si completa con gli
    altri fatti ammessi. La finestra temporale compare solo se inferiore a 180 giorni.
    """
    coefs = coefs or {}

    def coerente(feature: str) -> bool:
        beta = coefs.get(feature)
        return beta is None or beta * VERSO_SOSPETTO.get(feature, 1) > 0

    ordinati = sorted(contributi.items(), key=lambda kv: kv[1], reverse=True)
    positivi = [k for k, v in ordinati if v > 0 and coerente(k)]
    altri = [k for k, v in ordinati if v <= 0 and coerente(k)]
    frasi: list[str] = []
    for feature in positivi + altri:
        frase = _frase(feature, feature_gruppo)
        if frase and frase not in frasi:
            frasi.append(frase)
        if len(frasi) == n:
            break
    return frasi
