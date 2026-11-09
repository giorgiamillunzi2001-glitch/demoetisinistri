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


# --- Calibrazione su statistiche pubbliche (IVASS 2023-2024) -----------------------------------
# I valori effettivi si leggono da config.yaml > calibrazione; questi sono i default.
CALIBRAZIONE_DEFAULT = {
    "costo_medio_sinistro": 4962,  # IVASS, Relazione annuale 2024, autovetture
    "quota_rischio_frode": 0.24,   # IVASS antifrode 2024
    "rischio_nord": 0.215,         # IVASS antifrode 2023
    "rischio_sud": 0.399,          # IVASS antifrode 2023
    "rischio_campania": 0.51,      # IVASS antifrode 2023
}
QUOTA_LESIONI = 0.15      # quota di sinistri con lesioni alla persona (ipotesi del prototipo)
RAPPORTO_LESIONI = 4.0    # importo medio con lesioni / importo medio senza lesioni (ipotesi)
# Province (sigla -> area, peso sul numero di sinistri): più sinistri al Sud e in Campania.
PROVINCE = {
    "MI": ("nord", 8), "TO": ("nord", 5), "BS": ("nord", 3), "BG": ("nord", 3), "VR": ("nord", 3),
    "PD": ("nord", 3), "BO": ("nord", 3), "GE": ("nord", 3),
    "RM": ("centro", 9), "FI": ("centro", 3), "PG": ("centro", 2), "AN": ("centro", 2),
    "NA": ("campania", 11), "CE": ("campania", 5), "SA": ("campania", 5),
    "BA": ("sud", 5), "LE": ("sud", 3), "PA": ("sud", 5), "CT": ("sud", 5), "RC": ("sud", 3),
}
_SIGLE = list(PROVINCE)
_PESI = np.array([PROVINCE[s][1] for s in _SIGLE], dtype=float)
_PESI /= _PESI.sum()
# Gli anelli si concentrano dove gli indicatori di rischio sono più alti
_PESI_ANELLI = np.array([PROVINCE[s][1] * (2.5 if PROVINCE[s][0] in {"sud", "campania"} else 1.0)
                         for s in _SIGLE], dtype=float)
_PESI_ANELLI /= _PESI_ANELLI.sum()


def calibrazione() -> dict[str, float]:
    """Parametri di calibrazione: config.yaml > calibrazione, con i default IVASS."""
    from .config import load_config

    cal = dict(CALIBRAZIONE_DEFAULT)
    cal.update({k: float(v) for k, v in (load_config().get("calibrazione") or {}).items()})
    return cal


def _rischio_area(area: str, cal: dict[str, float]) -> float:
    if area == "centro":  # valore non usato tra i parametri: media tra Nord e Sud
        return (cal["rischio_nord"] + cal["rischio_sud"]) / 2
    return cal[f"rischio_{area}"]


def _provincia(rng: np.random.Generator, anello: bool = False) -> str:
    return str(rng.choice(_SIGLE, p=_PESI_ANELLI if anello else _PESI))


def _importo(rng: np.random.Generator, lesioni: bool, cal: dict[str, float]) -> float:
    """Importo lognormale: la media complessiva (con il 15% di lesioni) è il costo medio IVASS."""
    media_base = cal["costo_medio_sinistro"] / (1 + QUOTA_LESIONI * (RAPPORTO_LESIONI - 1))
    media, sigma = (media_base * RAPPORTO_LESIONI, 0.6) if lesioni else (media_base, 0.8)
    return round(max(200.0, float(rng.lognormal(np.log(media) - sigma**2 / 2, sigma))), 2)


def _pratica(rng: np.random.Generator, provincia: str, cal: dict[str, float], p_lesioni: float = QUOTA_LESIONI) -> dict:
    """Attributi della pratica usati dalle regole attuali. Gli indicatori di anomalia (notte, assenza
    di verbale, polizza recente) sono più frequenti dove il rischio frode IVASS è più alto."""
    a = _rischio_area(PROVINCE[provincia][0], cal) / cal["quota_rischio_frode"]
    lesioni = bool(rng.random() < p_lesioni)
    return {
        "provincia": provincia,
        "importo_richiesto": _importo(rng, lesioni, cal),
        "lesioni": lesioni,
        "orario_notturno": bool(rng.random() < min(0.5, 0.08 * a)),
        "verbale_autorita": bool(rng.random() >= min(0.9, 0.40 * a)),
        "cai_firmato_entrambi": bool(rng.random() < 0.7),
        "giorni_da_inizio_polizza": int(rng.integers(5, 30)) if rng.random() < min(0.5, 0.06 * a)
        else int(rng.integers(30, 600)),
    }


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
    l = lambda: str(rng.choice(LETTERE))
    return f"{l()}{l()}{int(rng.integers(100, 999))}{l()}{l()}"


def _generate_regular_claims(n_claims: int, rng: np.random.Generator, base_date: datetime, start_idx: int,
                             cal: dict[str, float]):
    rows: list[dict] = []
    involvements: list[dict] = []
    hub_officina = OFFICINA_HUB
    for i in range(n_claims):
        claim_id = f"S{start_idx + i:05d}"
        claim_date = base_date + timedelta(days=int(rng.integers(0, 750)))
        denuncia = claim_date + timedelta(days=int(rng.integers(1, 45)))
        pratica = _pratica(rng, _provincia(rng), cal)
        witness = bool(rng.random() < 0.25)
        num_people = int(rng.integers(1, 4))
        office = hub_officina if rng.random() < 0.15 else _officina(rng)
        perito = _perito(rng)
        avvocato = _avvocato(rng)
        row = {
            "id_sinistro": claim_id,
            "data_sinistro": claim_date.date().isoformat(),
            "data_denuncia": denuncia.date().isoformat(),
            **pratica,
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


# Profili degli anelli. Gli anelli "prudenti" hanno meno sinistri, finestre più lunghe, ruoli più
# stabili (pochi cambi di ruolo, quasi nessun testimone abituale) e IBAN/telefoni condivisi solo in
# parte: alcuni restano sotto la soglia di segnalazione, come accade nella realtà.
PROFILI_ANELLO = {
    "organizzato": {"sinistri": (5, 15), "finestra": (60, 300), "fedelta_ruolo": (0.4, 0.85),
                    "quota_tel_condiviso": (0.2, 0.6), "p_iban_personale": (0.0, 0.35), "testimone_abituale": True},
    "prudente": {"sinistri": (6, 10), "finestra": (250, 600), "fedelta_ruolo": (0.9, 0.98),
                 "quota_tel_condiviso": (0.0, 0.15), "p_iban_personale": (0.5, 0.8), "testimone_abituale": False},
}
OGNI_QUANTI_PRUDENTE = 3  # un anello ogni 3 è prudente (scelta deterministica: risultati riproducibili)


def profilo_anello(ring_index: int) -> str:
    return "prudente" if ring_index % OGNI_QUANTI_PRUDENTE == OGNI_QUANTI_PRUDENTE - 1 else "organizzato"


def _generate_fraud_ring(ring_index: int, rng: np.random.Generator, base_date: datetime, start_idx: int,
                        cal: dict[str, float]):
    """Anello organizzato: un gruppo di persone ricorrenti su molti sinistri.

    Ogni sinistro coinvolge 2-4 membri, come un sinistro normale. I segnali sono volutamente non
    netti: solo una parte dei membri cambia ruolo, l'anello usa più IBAN e telefoni (alcuni propri)
    e i sinistri sono concentrati nel tempo (60-300 giorni), ma non abbastanza da distinguerli
    dalle flotte e dalle famiglie con sinistri ravvicinati. Un anello ogni tre è "prudente"
    (vedi PROFILI_ANELLO).
    """
    prof = PROFILI_ANELLO[profilo_anello(ring_index)]
    ring_claims: list[dict] = []
    involvements: list[dict] = []
    people_count = int(rng.integers(6, 10))
    claim_count = int(rng.integers(*prof["sinistri"]))
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
    quota_tel_condiviso = float(rng.uniform(*prof["quota_tel_condiviso"]))
    phones = {
        person: shared_phones[int(rng.integers(0, len(shared_phones)))] if rng.random() < quota_tel_condiviso else _safe_phone(rng)
        for person in ring_people
    }
    cars = {person: _targa(rng) for person in ring_people}
    # non tutti cambiano ruolo: ogni membro ha un ruolo abituale che mantiene con una certa probabilità
    ruoli = ["assicurato", "controparte", "conducente", "testimone"]
    ruoli_abituali = ruoli if prof["testimone_abituale"] else ruoli[:3]
    ruolo_abituale = {person: str(rng.choice(ruoli_abituali)) for person in ring_people}
    fedelta_ruolo = float(rng.uniform(*prof["fedelta_ruolo"]))
    # finestra temporale e concentrazione su officina/avvocato variabili
    finestra = int(rng.integers(*prof["finestra"]))
    p_officina = float(rng.uniform(0.4, 0.9))
    p_iban_personale = float(rng.uniform(*prof["p_iban_personale"]))
    start_offset = int(rng.integers(0, 750 - finestra))
    provincia_anello = _provincia(rng, anello=True)  # l'anello opera soprattutto in una provincia
    for i in range(claim_count):
        claim_id = f"S{start_idx + i:05d}"
        claim_date = base_date + timedelta(days=start_offset + int(rng.integers(0, finestra)))
        denuncia = claim_date + timedelta(days=int(rng.integers(1, 25)))
        provincia = provincia_anello if rng.random() < 0.8 else _provincia(rng, anello=True)
        pratica = _pratica(rng, provincia, cal, p_lesioni=0.2)
        iban = _safe_iban(rng) if rng.random() < p_iban_personale else shared_ibans[i % len(shared_ibans)]
        row = {
            "id_sinistro": claim_id,
            "data_sinistro": claim_date.date().isoformat(),
            "data_denuncia": denuncia.date().isoformat(),
            **pratica,
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
QUOTA_CENTRALINO_FLOTTA = (0.5, 0.9)


def _generate_legit_group(kind: str, rng: np.random.Generator, base_date: datetime, start_idx: int,
                          cal: dict[str, float]):
    """Gruppo collegato ma legittimo, con casi volutamente ambigui.

    - famiglia: 2-4 persone con telefono di casa e IBAN comuni; i familiari compaiono in più
      sinistri con ruoli diversi (assicurato, conducente, a volte testimone);
    - colleghi: persone dello stesso ufficio, ognuna con il proprio IBAN, che si fanno da
      testimone a vicenda (testimoni ricorrenti occasionali);
    - flotta: azienda con un IBAN condiviso da tutti i sinistri, un responsabile e più autisti,
      officina convenzionata frequente, telefono aziendale condiviso da una parte degli autisti,
      a volte sinistri ravvicinati.
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
        # centralino aziendale: una parte degli autisti lascia il telefono della ditta
        centralino = _safe_phone(rng)
        quota_centralino = float(rng.uniform(*QUOTA_CENTRALINO_FLOTTA))
        phones = {m: centralino if (m == responsabile or rng.random() < quota_centralino) else _safe_phone(rng)
                  for m in membri}
        claim_count = int(rng.integers(5, 13))
        finestra = int(rng.integers(150, 750))
    cars = {m: _targa(rng) for m in membri}
    hub_prob = float(rng.uniform(0.5, 0.85)) if kind == "flotta" else 0.15
    inizio = int(rng.integers(0, 750 - finestra + 1))
    provincia_gruppo = _provincia(rng)

    for i in range(claim_count):
        claim_id = f"S{start_idx + i:05d}"
        claim_date = base_date + timedelta(days=inizio + int(rng.integers(0, finestra)))
        denuncia = claim_date + timedelta(days=int(rng.integers(1, 45)))
        pratica = _pratica(rng, provincia_gruppo if rng.random() < 0.85 else _provincia(rng), cal)

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
                **pratica,
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

    Calibrazione su statistiche pubbliche IVASS 2023-2024 (config.yaml > calibrazione):
    - importi lognormali con media pari al costo medio di un sinistro auto (circa 4.962 €);
      circa il 15% dei sinistri ha lesioni, con importi più alti;
    - province con più sinistri e più indicatori di anomalia al Sud e in Campania (rischio frode
      IVASS per area). La provincia è solo descrittiva: è una feature vietata nel modello;
    - indicatori di anomalia tarati perché le regole attuali segnalino circa il 24% dei sinistri,
      come la quota di sinistri a rischio frode del mercato.

    La quota di frodi nel dataset è volutamente molto più alta di quella reale (circa 1,5% di frodi
    accertate secondo IVASS): gli anelli sono sovracampionati per renderli visibili nel prototipo.
    """
    cal = calibrazione()
    rng = np.random.default_rng(seed)
    base_date = datetime(2022, 1, 1)

    sinistri: list[dict] = []
    coinvolgimenti: list[dict] = []

    for ring_index in range(n_anelli):
        claims, rels = _generate_fraud_ring(
            # generatore proprio per ogni anello, derivato dal seed: il profilo di un anello non sposta il resto dei dati
            ring_index, np.random.default_rng(int(rng.integers(2**63))), base_date, len(sinistri) + 1, cal
        )
        sinistri.extend(claims)
        coinvolgimenti.extend(rels)

    n_legittimi = n_anelli if n_gruppi_legittimi is None else n_gruppi_legittimi
    for idx in range(n_legittimi):
        kind = TIPI_LEGITTIMI[idx % len(TIPI_LEGITTIMI)]
        claims, rels = _generate_legit_group(kind, np.random.default_rng(int(rng.integers(2**63))), base_date, len(sinistri) + 1, cal)
        sinistri.extend(claims)
        coinvolgimenti.extend(rels)

    if len(sinistri) < n_sinistri:
        regular_rows, regular_rels = _generate_regular_claims(n_sinistri - len(sinistri), rng, base_date, len(sinistri) + 1, cal)
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
    con_testimone = set(coinvolgimenti_df.loc[coinvolgimenti_df["ruolo"] == "testimone", "id_sinistro"])
    sinistri_df["testimone"] = sinistri_df["id_sinistro"].isin(con_testimone)
    sinistri_df = sinistri_df[[
        "id_sinistro",
        "data_sinistro",
        "data_denuncia",
        "provincia",
        "importo_richiesto",
        "lesioni",
        "orario_notturno",
        "verbale_autorita",
        "cai_firmato_entrambi",
        "giorni_da_inizio_polizza",
        "testimone",
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
