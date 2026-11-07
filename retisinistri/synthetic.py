from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def _safe_phone(rng: np.random.Generator) -> str:
    return f"333{rng.integers(1000000, 9999999, dtype=int)}"


def _safe_iban(rng: np.random.Generator) -> str:
    return f"IT{rng.integers(10_000_000, 99_999_999, dtype=int)}{rng.integers(1000, 9999, dtype=int)}"


def _normalize_name(prefix: str, index: int) -> str:
    return f"{prefix}{index}"


# Codici neutri condivisi da sinistri regolari e anelli: nessun indizio nei dati.
N_OFFICINE, N_PERITI, N_AVVOCATI = 40, 80, 70
OFFICINA_HUB = "OFF_021"  # officina convenzionata molto frequentata (legittima)
LETTERE = list("ABCDEFGHJKLMNPRSTVWXYZ")


def _officina(rng: np.random.Generator) -> str:
    return f"OFF_{int(rng.integers(1, N_OFFICINE + 1)):03d}"


def _perito(rng: np.random.Generator) -> str:
    return f"PER_{int(rng.integers(1, N_PERITI + 1)):03d}"


def _avvocato(rng: np.random.Generator) -> str:
    return f"AVV_{int(rng.integers(1, N_AVVOCATI + 1)):03d}"


def _persona(rng: np.random.Generator) -> str:
    return f"P{int(rng.integers(100000, 999999)):06d}"


def _email(person_id: str) -> str:
    return f"{person_id.lower()}@mail.it"


def _targa(rng: np.random.Generator) -> str:
    l = lambda: str(rng.choice(LETTERE))  # noqa: E731
    return f"{l()}{l()}{int(rng.integers(100, 999))}{l()}{l()}"


def _generate_regular_claims(n_claims: int, rng: np.random.Generator, base_date: datetime, start_idx: int):
    rows: list[dict] = []
    involvements: list[dict] = []
    hub_officina = OFFICINA_HUB
    for i in range(n_claims):
        claim_id = f"S{start_idx + i:05d}"
        claim_date = base_date + timedelta(days=int(rng.integers(0, 750)))
        denuncia = claim_date + timedelta(days=int(rng.integers(1, 45)))
        importo = float(np.exp(rng.normal(loc=8.0, scale=0.8)))
        is_night = bool(rng.random() < 0.12)
        has_report = bool(rng.random() < 0.45)
        witness = bool(rng.random() < 0.25)
        num_people = int(rng.integers(1, 4))
        office = hub_officina if rng.random() < 0.15 else _officina(rng)
        perito = _perito(rng)
        avvocato = _avvocato(rng)
        row = {
            "id_sinistro": claim_id,
            "data_sinistro": claim_date.date().isoformat(),
            "data_denuncia": denuncia.date().isoformat(),
            "provincia": f"P{rng.integers(1, 21):02d}",
            "importo_richiesto": round(min(max(importo, 400.0), 12000.0), 2),
            "orario_notturno": is_night,
            "verbale_autorita": has_report,
            "cai_firmato_entrambi": bool(rng.random() < 0.7),
            "giorni_da_inizio_polizza": int(rng.integers(10, 500)),
            "id_officina": office,
            "id_perito": perito,
            "id_avvocato": avvocato,
            "iban_liquidazione": _safe_iban(rng),
            "label_frode": 0,
        }
        rows.append(row)

        used_names: set[str] = set()
        for person_idx in range(num_people):
            person_id = _persona(rng)
            while person_id in used_names:
                person_id = _persona(rng)
            used_names.add(person_id)
            ruolo = "assicurato" if person_idx == 0 else ("controparte" if person_idx == 1 else "testimone" if witness and person_idx == 2 else "conducente")
            phone = _safe_phone(rng)
            email = _email(person_id)
            involvement = {
                "id_sinistro": claim_id,
                "id_persona": person_id,
                "ruolo": ruolo,
                "telefono": phone,
                "email": email,
                "targa": _targa(rng),
                "iban": row["iban_liquidazione"],
            }
            involvements.append(involvement)

        if witness:
            witness_id = _persona(rng)
            involvements.append(
                {
                    "id_sinistro": claim_id,
                    "id_persona": witness_id,
                    "ruolo": "testimone",
                    "telefono": _safe_phone(rng),
                    "email": _email(witness_id),
                    "targa": None,
                    "iban": None,
                }
            )
    return rows, involvements


def _generate_fraud_ring(ring_index: int, rng: np.random.Generator, base_date: datetime, start_idx: int):
    ring_claims: list[dict] = []
    involvements: list[dict] = []
    people_count = int(rng.integers(6, 10))
    claim_count = int(rng.integers(8, 15))
    shared_phones = [_safe_phone(rng) for _ in range(int(rng.integers(1, 3)))]
    shared_ibans = [_safe_iban(rng) for _ in range(int(rng.integers(1, 3)))]
    same_shop = _officina(rng)
    same_lawyer = _avvocato(rng)
    same_perito = _perito(rng)
    ring_people = []
    while len(ring_people) < people_count:
        candidate = _persona(rng)
        if candidate not in ring_people:
            ring_people.append(candidate)
    ring_cars = {person: _targa(rng) for person in ring_people}
    for i in range(claim_count):
        claim_id = f"S{start_idx + i:05d}"
        days_offset = int(rng.integers(0, 180))
        claim_date = base_date + timedelta(days=days_offset)
        denuncia = claim_date + timedelta(days=int(rng.integers(1, 25)))
        importo = float(rng.uniform(1500, 3500))
        row = {
            "id_sinistro": claim_id,
            "data_sinistro": claim_date.date().isoformat(),
            "data_denuncia": denuncia.date().isoformat(),
            "provincia": f"P{rng.integers(1, 21):02d}",
            "importo_richiesto": round(importo, 2),
            "orario_notturno": bool(rng.random() < 0.15),
            "verbale_autorita": bool(rng.random() < 0.40),
            "cai_firmato_entrambi": bool(rng.random() < 0.6),
            "giorni_da_inizio_polizza": int(rng.integers(5, 220)),
            "id_officina": same_shop,
            "id_perito": same_perito,
            "id_avvocato": same_lawyer,
            "iban_liquidazione": shared_ibans[i % len(shared_ibans)],
            "label_frode": 1,
        }
        ring_claims.append(row)

        for person_idx, person_key in enumerate(ring_people):
            ruolo = ["assicurato", "controparte", "conducente", "testimone", "assicurato", "controparte"][person_idx % 6]
            phone = shared_phones[(person_idx + i) % len(shared_phones)]
            email = _email(person_key)
            involvements.append(
                {
                    "id_sinistro": claim_id,
                    "id_persona": person_key,
                    "ruolo": ruolo,
                    "telefono": phone,
                    "email": email,
                    "targa": ring_cars[person_key],
                    "iban": row["iban_liquidazione"],
                }
            )
    return ring_claims, involvements


def genera_dataset(n_sinistri: int = 2000, n_anelli: int = 4, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Genera sinteticamente sinistri e coinvolgimenti, con anelli di frode e regolari."""
    rng = np.random.default_rng(seed)
    base_date = datetime(2022, 1, 1)

    sinistri: list[dict] = []
    coinvolgimenti: list[dict] = []

    ring_claim_total = 0
    for ring_index in range(n_anelli):
        claim_count = max(8, min(15, n_sinistri // max(1, n_anelli)))
        ring_claim_total += claim_count
        claims, rels = _generate_fraud_ring(ring_index, rng, base_date, len(sinistri) + 1)
        sinistri.extend(claims)
        coinvolgimenti.extend(rels)

    regular_n = max(0, n_sinistri - ring_claim_total)
    regular_rows, regular_rels = _generate_regular_claims(regular_n, rng, base_date, len(sinistri) + 1)
    sinistri.extend(regular_rows)
    coinvolgimenti.extend(regular_rels)

    if len(sinistri) < n_sinistri:
        extra_rows, extra_rels = _generate_regular_claims(n_sinistri - len(sinistri), rng, base_date, len(sinistri) + 1)
        sinistri.extend(extra_rows)
        coinvolgimenti.extend(extra_rels)

    sinistri_df = pd.DataFrame(sinistri)
    coinvolgimenti_df = pd.DataFrame(coinvolgimenti)

    # Mescola le righe e riassegna gli id: i sinistri fraudolenti non sono più in blocco all'inizio
    sinistri_df = sinistri_df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    nuovi_id = {old: f"S{idx + 1:05d}" for idx, old in enumerate(sinistri_df["id_sinistro"])}
    sinistri_df["id_sinistro"] = sinistri_df["id_sinistro"].map(nuovi_id)
    coinvolgimenti_df["id_sinistro"] = coinvolgimenti_df["id_sinistro"].map(nuovi_id)
    coinvolgimenti_df = coinvolgimenti_df.sort_values("id_sinistro", kind="stable").reset_index(drop=True)
    sinistri_df = sinistri_df[[
        "id_sinistro",
        "data_sinistro",
        "data_denuncia",
        "provincia",
        "importo_richiesto",
        "orario_notturno",
        "verbale_autorita",
        "cai_firmato_entrambi",
        "giorni_da_inizio_polizza",
        "id_officina",
        "id_perito",
        "id_avvocato",
        "iban_liquidazione",
        "label_frode",
    ]]
    coinvolgimenti_df = coinvolgimenti_df[["id_sinistro", "id_persona", "ruolo", "telefono", "email", "targa", "iban"]]

    raw_dir = RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    sinistri_df.to_csv(raw_dir / "sinistri.csv", index=False)
    coinvolgimenti_df.to_csv(raw_dir / "coinvolgimenti.csv", index=False)
    try:
        sinistri_df.to_parquet(raw_dir / "sinistri.parquet", index=False)
        coinvolgimenti_df.to_parquet(raw_dir / "coinvolgimenti.parquet", index=False)
    except Exception:
        pass

    return sinistri_df, coinvolgimenti_df
