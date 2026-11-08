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
    """Anello organizzato: un gruppo di persone ricorrenti su molti sinistri.

    Ogni sinistro coinvolge 2-4 membri, come un sinistro normale. I segnali sono volutamente non
    netti: solo una parte dei membri cambia ruolo, l'anello usa più IBAN e telefoni (alcuni propri)
    e i sinistri possono essere distribuiti su finestre lunghe.
    """
    ring_claims: list[dict] = []
    involvements: list[dict] = []
    people_count = int(rng.integers(6, 10))
    claim_count = int(rng.integers(5, 15))
    shared_phones = [_safe_phone(rng) for _ in range(int(rng.integers(1, 4)))]
    shared_ibans = [_safe_iban(rng) for _ in range(int(rng.integers(1, 5)))]
    same_shop = _officina(rng)
    same_lawyer = _avvocato(rng)
    same_perito = _perito(rng)
    ring_people: list[str] = []
    while len(ring_people) < people_count:
        candidate = _persona(rng)
        if candidate not in ring_people:
            ring_people.append(candidate)
    # una parte dei membri usa un telefono condiviso, gli altri il proprio
    quota_tel_condiviso = float(rng.uniform(0.2, 0.6))
    phones = {
        person: shared_phones[int(rng.integers(0, len(shared_phones)))] if rng.random() < quota_tel_condiviso else _safe_phone(rng)
        for person in ring_people
    }
    cars = {person: _targa(rng) for person in ring_people}
    # non tutti cambiano ruolo: ogni membro ha un ruolo abituale che mantiene con una certa probabilità
    ruoli = ["assicurato", "controparte", "conducente", "testimone"]
    ruolo_abituale = {person: str(rng.choice(ruoli)) for person in ring_people}
    fedelta_ruolo = float(rng.uniform(0.4, 0.85))
    # anelli più o meno "prudenti": finestra temporale e concentrazione su officina/avvocato variabili
    finestra = int(rng.integers(120, 600))
    p_officina = float(rng.uniform(0.4, 0.9))
    p_iban_personale = float(rng.uniform(0.0, 0.35))
    start_offset = int(rng.integers(0, 750 - finestra))
    for i in range(claim_count):
        claim_id = f"S{start_idx + i:05d}"
        claim_date = base_date + timedelta(days=start_offset + int(rng.integers(0, finestra)))
        denuncia = claim_date + timedelta(days=int(rng.integers(1, 25)))
        importo = float(rng.uniform(1500, 3500))
        iban = _safe_iban(rng) if rng.random() < p_iban_personale else shared_ibans[i % len(shared_ibans)]
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
            "id_officina": same_shop if rng.random() < p_officina else _officina(rng),
            "id_perito": same_perito if rng.random() < 0.7 else _perito(rng),
            "id_avvocato": same_lawyer if rng.random() < p_officina else _avvocato(rng),
            "iban_liquidazione": iban,
            "label_frode": 1,
        }
        ring_claims.append(row)

        coinvolti = [str(x) for x in rng.choice(ring_people, size=int(rng.integers(2, 5)), replace=False)]
        usati: set[str] = set()
        for person_key in coinvolti:
            ruolo = ruolo_abituale[person_key] if rng.random() < fedelta_ruolo else str(rng.choice(ruoli))
            if ruolo in usati and ruolo in {"assicurato", "controparte"}:
                ruolo = "conducente"
            usati.add(ruolo)
            involvements.append(
                {
                    "id_sinistro": claim_id,
                    "id_persona": person_key,
                    "ruolo": ruolo,
                    "telefono": phones[person_key],
                    "email": _email(person_key),
                    "targa": cars[person_key] if ruolo != "testimone" else None,
                    "iban": iban if ruolo != "testimone" else None,
                }
            )
    return ring_claims, involvements


TIPI_LEGITTIMI = ("famiglia", "colleghi", "flotta")


def _generate_legit_group(kind: str, rng: np.random.Generator, base_date: datetime, start_idx: int):
    """Gruppo collegato ma legittimo, con casi volutamente ambigui.

    - famiglia: 2-4 persone con telefono di casa e IBAN comuni; i familiari compaiono in più
      sinistri con ruoli diversi (assicurato, conducente, a volte testimone);
    - colleghi: persone dello stesso ufficio, ognuna con il proprio IBAN, che si fanno da
      testimone a vicenda (testimoni ricorrenti occasionali);
    - flotta: azienda con un IBAN condiviso da tutti i sinistri, un responsabile e più autisti,
      officina convenzionata frequente, a volte sinistri ravvicinati.
    """
    rows: list[dict] = []
    involvements: list[dict] = []
    group_iban = _safe_iban(rng)
    if kind == "famiglia":
        membri = [_persona(rng) for _ in range(int(rng.integers(2, 5)))]
        telefono_casa = _safe_phone(rng)
        phones = {m: telefono_casa if rng.random() < 0.7 else _safe_phone(rng) for m in membri}
        claim_count = int(rng.integers(3, 7))
        finestra = int(rng.integers(300, 750))
    elif kind == "colleghi":
        membri = [_persona(rng) for _ in range(int(rng.integers(3, 6)))]
        phones = {m: _safe_phone(rng) for m in membri}
        iban_personali = {m: _safe_iban(rng) for m in membri}
        claim_count = int(rng.integers(3, 7))
        finestra = int(rng.integers(250, 750))
    else:
        responsabile = _persona(rng)
        autisti = [_persona(rng) for _ in range(int(rng.integers(3, 7)))]
        membri = [responsabile, *autisti]
        phones = {m: _safe_phone(rng) for m in membri}
        claim_count = int(rng.integers(5, 13))
        finestra = int(rng.integers(150, 750))
    cars = {m: _targa(rng) for m in membri}
    hub_prob = float(rng.uniform(0.5, 0.85)) if kind == "flotta" else 0.15
    inizio = int(rng.integers(0, 750 - finestra + 1))

    for i in range(claim_count):
        claim_id = f"S{start_idx + i:05d}"
        claim_date = base_date + timedelta(days=inizio + int(rng.integers(0, finestra)))
        denuncia = claim_date + timedelta(days=int(rng.integers(1, 45)))
        importo = float(np.exp(rng.normal(loc=8.0, scale=0.8)))

        if kind == "famiglia":
            assicurato = str(rng.choice(membri))
            interni = [(assicurato, "assicurato")]
            altri = [m for m in membri if m != assicurato]
            if altri and rng.random() < 0.5:
                interni.append((str(rng.choice(altri)), "conducente"))
            elif altri and rng.random() < 0.3:
                interni.append((str(rng.choice(altri)), "testimone"))
            iban = group_iban
        elif kind == "colleghi":
            assicurato = str(rng.choice(membri))
            interni = [(assicurato, "assicurato")]
            altri = [m for m in membri if m != assicurato]
            if rng.random() < 0.6:
                interni.append((str(rng.choice(altri)), "testimone"))
            iban = iban_personali[assicurato]
        else:
            interni = [(responsabile, "assicurato"), (str(rng.choice(autisti)), "conducente")]
            if rng.random() < 0.2:
                interni.append((str(rng.choice(autisti)), "testimone"))
            iban = group_iban

        rows.append(
            {
                "id_sinistro": claim_id,
                "data_sinistro": claim_date.date().isoformat(),
                "data_denuncia": denuncia.date().isoformat(),
                "provincia": f"P{rng.integers(1, 21):02d}",
                "importo_richiesto": round(min(max(importo, 400.0), 12000.0), 2),
                "orario_notturno": bool(rng.random() < 0.12),
                "verbale_autorita": bool(rng.random() < 0.45),
                "cai_firmato_entrambi": bool(rng.random() < 0.7),
                "giorni_da_inizio_polizza": int(rng.integers(10, 500)),
                "id_officina": OFFICINA_HUB if rng.random() < hub_prob else _officina(rng),
                "id_perito": _perito(rng),
                "id_avvocato": _avvocato(rng),
                "iban_liquidazione": iban,
                "label_frode": 0,
            }
        )
        visti: set[str] = set()
        for persona, ruolo in interni:
            if persona in visti:
                continue
            visti.add(persona)
            involvements.append(
                {"id_sinistro": claim_id, "id_persona": persona, "ruolo": ruolo, "telefono": phones[persona],
                 "email": _email(persona), "targa": cars[persona] if ruolo != "testimone" else None,
                 "iban": iban if ruolo != "testimone" else None}
            )
        controparte = _persona(rng)
        involvements.append(
            {"id_sinistro": claim_id, "id_persona": controparte, "ruolo": "controparte", "telefono": _safe_phone(rng),
             "email": _email(controparte), "targa": _targa(rng), "iban": iban}
        )
    return rows, involvements


def genera_dataset(
    n_sinistri: int = 2000, n_anelli: int = 4, seed: int = 42, n_gruppi_legittimi: int | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Genera sinistri e coinvolgimenti sintetici.

    Contiene anelli di frode, gruppi collegati legittimi (famiglie, colleghi e flotte; di default
    tanti quanti gli anelli) e sinistri regolari isolati fino a raggiungere `n_sinistri`.
    """
    rng = np.random.default_rng(seed)
    base_date = datetime(2022, 1, 1)

    sinistri: list[dict] = []
    coinvolgimenti: list[dict] = []

    for ring_index in range(n_anelli):
        claims, rels = _generate_fraud_ring(ring_index, rng, base_date, len(sinistri) + 1)
        sinistri.extend(claims)
        coinvolgimenti.extend(rels)

    n_legittimi = n_anelli if n_gruppi_legittimi is None else n_gruppi_legittimi
    for idx in range(n_legittimi):
        kind = TIPI_LEGITTIMI[idx % len(TIPI_LEGITTIMI)]
        claims, rels = _generate_legit_group(kind, rng, base_date, len(sinistri) + 1)
        sinistri.extend(claims)
        coinvolgimenti.extend(rels)

    if len(sinistri) < n_sinistri:
        regular_rows, regular_rels = _generate_regular_claims(n_sinistri - len(sinistri), rng, base_date, len(sinistri) + 1)
        sinistri.extend(regular_rows)
        coinvolgimenti.extend(regular_rels)

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
