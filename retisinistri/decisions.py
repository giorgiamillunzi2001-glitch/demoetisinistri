from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "decisions.sqlite"


def init_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Inizializza il database SQLite per le decisioni e la governance."""
    target = Path(db_path) if db_path is not None else DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decisioni (
            id_alert TEXT,
            id_gruppo TEXT,
            timestamp TEXT,
            id_liquidatore TEXT,
            decisione TEXT,
            esito_finale TEXT,
            note TEXT
        )
        """
    )
    return conn


def salva_decisione(id_alert: str, id_gruppo: str, id_liquidatore: str, decisione: str, esito_finale: str, note: str = "") -> dict[str, Any]:
    """Registra la decisione del liquidatore."""
    conn = init_db()
    conn.execute(
        "INSERT INTO decisioni (id_alert, id_gruppo, timestamp, id_liquidatore, decisione, esito_finale, note) VALUES (?, ?, datetime('now'), ?, ?, ?, ?)",
        (id_alert, id_gruppo, id_liquidatore, decisione, esito_finale, note),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "id_alert": id_alert, "id_gruppo": id_gruppo}


def dataset_riaddestramento() -> list[dict[str, Any]]:
    """Ritorna i gruppi con esito noto in vista di un riaddestramento."""
    conn = init_db()
    rows = conn.execute(
        "SELECT id_gruppo, decisione, esito_finale, note FROM decisioni WHERE esito_finale IN ('frode_confermata', 'regolare')"
    ).fetchall()
    conn.close()
    return [{"id_gruppo": row[0], "decisione": row[1], "esito_finale": row[2], "note": row[3]} for row in rows]


DECISIONI_OVERRIDE = {"liquidazione", "archiviazione"}


def override_rate(gruppi_segnalati: set[str] | list[str]) -> float | None:
    """Quota di gruppi segnalati in cui l'ultima decisione del liquidatore va contro il modello
    (archiviazione o liquidazione). None se nessun gruppo segnalato ha ancora una decisione."""
    segnalati = {str(g) for g in gruppi_segnalati}
    ultime: dict[str, str] = {}
    for d in lista_decisioni():  # ordinate dalla più recente
        ultime.setdefault(str(d["id_gruppo"]), d["decisione"])
    decise = [dec for g, dec in ultime.items() if g in segnalati]
    if not decise:
        return None
    return sum(dec in DECISIONI_OVERRIDE for dec in decise) / len(decise)


def psi(atteso: Any, osservato: Any, eps: float = 1e-4) -> float | None:
    """Population Stability Index tra due distribuzioni di categorie (es. fasce di score)."""
    a, o = pd.Series(atteso), pd.Series(osservato)
    if a.empty or o.empty:
        return None
    categorie = sorted(set(a) | set(o))
    pa = a.value_counts(normalize=True).reindex(categorie, fill_value=0).clip(lower=eps)
    po = o.value_counts(normalize=True).reindex(categorie, fill_value=0).clip(lower=eps)
    return float(((po - pa) * np.log(po / pa)).sum())


def monitoraggio(sinistri: Any = None, gruppi_segnalati: Any = (), soglia_media: int = 40, soglia_alta: int = 70,
                 min_regolari_provincia: int = 10) -> dict[str, Any]:
    """Metriche di governance calcolate dai dati; un valore non calcolabile è None ("n.d." a video).

    - psi: stabilità della distribuzione dello score di rete dei sinistri (fasce: non collegato,
      basso, medio, alto), confrontando la prima e la seconda metà del dataset per data del sinistro;
    - override_rate: dallo storico decisioni (vedi `override_rate`);
    - fpr_provincia: falsi allarmi (sinistri regolari con score >= soglia media) per provincia,
      solo per le province con almeno `min_regolari_provincia` sinistri regolari. È un controllo di
      equità: la provincia non è usata dal modello.
    """
    out: dict[str, Any] = {"psi": None, "override_rate": override_rate(gruppi_segnalati),
                           "fpr_provincia": None, "provincia_max": None, "fpr_per_provincia": None}
    if sinistri is None or len(sinistri) == 0:
        return out
    df = sinistri.copy()
    if {"data_sinistro", "score_rete"} <= set(df.columns):
        df["_data"] = pd.to_datetime(df["data_sinistro"], errors="coerce")
        df = df.dropna(subset=["_data"]).sort_values("_data")
        if len(df) >= 2:
            fascia = pd.cut(df["score_rete"], [-1, 0, soglia_media - 1, soglia_alta - 1, 100],
                            labels=["non collegato", "basso", "medio", "alto"]).astype(str)
            meta = len(df) // 2
            out["psi"] = psi(fascia.iloc[:meta], fascia.iloc[meta:])
    if {"provincia", "label_frode", "score_rete"} <= set(sinistri.columns):
        reg = sinistri[sinistri["label_frode"] == 0]
        tab = reg.groupby("provincia").agg(regolari=("score_rete", "size"),
                                           falsi_allarmi=("score_rete", lambda s: int((s >= soglia_media).sum())))
        tab = tab[tab["regolari"] >= min_regolari_provincia]
        if not tab.empty:
            tab["fpr"] = tab["falsi_allarmi"] / tab["regolari"]
            tab = tab.sort_values("fpr", ascending=False)
            out["fpr_provincia"] = float(tab["fpr"].iloc[0])
            out["provincia_max"] = str(tab.index[0])
            out["fpr_per_provincia"] = tab.reset_index()
    return out


def azzera_decisioni() -> int:
    """Cancella tutto lo storico decisioni (uso demo). Restituisce il numero di righe eliminate."""
    conn = init_db()
    n = conn.execute("DELETE FROM decisioni").rowcount
    conn.commit()
    conn.close()
    return int(n)


def lista_decisioni(id_gruppo: str | None = None) -> list[dict[str, Any]]:
    """Storico delle decisioni registrate (opzionalmente filtrato per gruppo)."""
    conn = init_db()
    query = "SELECT rowid, id_alert, id_gruppo, timestamp, id_liquidatore, decisione, esito_finale, note FROM decisioni"
    params: tuple = ()
    if id_gruppo is not None:
        query += " WHERE id_gruppo = ?"
        params = (str(id_gruppo),)
    rows = conn.execute(query + " ORDER BY timestamp DESC, rowid DESC", params).fetchall()
    conn.close()
    cols = ["id_decisione", "id_alert", "id_gruppo", "timestamp", "id_liquidatore", "decisione", "esito_finale", "note"]
    return [dict(zip(cols, row)) for row in rows]


ESITI_DEFINITIVI = {"frode_confermata", "regolare"}


def registra_esito(id_decisione: int, esito_finale: str, id_liquidatore: str, note: str = "") -> dict[str, Any]:
    """Chiude una decisione "in corso" registrando l'esito finale (frode confermata o regolare).

    L'esito aggiorna la riga della decisione, così alimenta le metriche e il dataset di
    riaddestramento; nelle note resta traccia di chi l'ha registrato e quando (ora locale).
    """
    if esito_finale not in ESITI_DEFINITIVI:
        raise ValueError(f"Esito non valido: {esito_finale!r} (ammessi: {sorted(ESITI_DEFINITIVI)})")
    conn = init_db()
    riga = conn.execute("SELECT esito_finale, note FROM decisioni WHERE rowid = ?", (int(id_decisione),)).fetchone()
    if riga is None:
        conn.close()
        raise ValueError(f"Decisione {id_decisione} non trovata")
    if riga[0] != "in_corso":
        conn.close()
        raise ValueError(f"La decisione {id_decisione} ha già un esito: {riga[0]}")
    etichetta = {"frode_confermata": "frode confermata", "regolare": "regolare"}[esito_finale]
    quando = datetime.now().strftime("%d/%m/%Y %H:%M")
    aggiunta = f"Esito {etichetta} registrato da {id_liquidatore} il {quando}" + (f": {note}" if note else "")
    nuove_note = f"{riga[1]} · {aggiunta}" if riga[1] else aggiunta
    conn.execute("UPDATE decisioni SET esito_finale = ?, note = ? WHERE rowid = ?", (esito_finale, nuove_note, int(id_decisione)))
    conn.commit()
    conn.close()
    return {"ok": True, "id_decisione": int(id_decisione), "esito_finale": esito_finale}
