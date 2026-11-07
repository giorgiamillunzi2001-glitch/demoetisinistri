from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

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


def monitoraggio() -> dict[str, float]:
    """Metriche di governance generiche."""
    return {"psi": 0.12, "override_rate": 0.08, "fpr_provincia": 0.04}


def lista_decisioni(id_gruppo: str | None = None) -> list[dict[str, Any]]:
    """Storico delle decisioni registrate (opzionalmente filtrato per gruppo)."""
    conn = init_db()
    query = "SELECT id_alert, id_gruppo, timestamp, id_liquidatore, decisione, esito_finale, note FROM decisioni"
    params: tuple = ()
    if id_gruppo is not None:
        query += " WHERE id_gruppo = ?"
        params = (str(id_gruppo),)
    rows = conn.execute(query + " ORDER BY timestamp DESC, rowid DESC", params).fetchall()
    conn.close()
    cols = ["id_alert", "id_gruppo", "timestamp", "id_liquidatore", "decisione", "esito_finale", "note"]
    return [dict(zip(cols, row)) for row in rows]
