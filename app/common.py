"""Funzioni condivise tra le pagine dell'app RetiSinistri."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retisinistri.config import DEFAULT_CONFIG_PATH, load_config  # noqa: E402
from retisinistri.pipeline import esegui_pipeline  # noqa: E402

# Palette dell'app per i grafici della pagina Analisi
PRINCIPALE = "#14213D"  # serie principale
RISCHIO = "#C0392B"     # rischio o valori negativi
NEUTRO = "#A6A6A6"      # tutto il resto

LIVELLO = {"alta": "Alto", "media": "Medio", "bassa": "Basso"}

GRIGIO_NODO = "#A6A6A6"
TIPI_NODO = {
    # tipo: (etichetta, colore, simbolo)
    "sinistro": ("Sinistro", "#14213D", "circle"),
    "persona": ("Persona", "#C0392B", "diamond"),
    "iban": ("IBAN", "#6B4E9B", "square"),
    "telefono": ("Telefono", "#2E86C1", "triangle-up"),
    "officina": ("Officina", GRIGIO_NODO, "cross"),
    "avvocato": ("Avvocato", GRIGIO_NODO, "x"),
    "perito": ("Perito", GRIGIO_NODO, "star"),
}

ESITI = {
    "in_corso": "In corso",
    "frode_confermata": "Frode confermata",
    "regolare": "Regolare",
}
DECISIONI = {
    "approfondimento": "Approfondimento",
    "liquidazione": "Liquidazione regolare",
    "sospensione": "Sospensione pagamento",
    "archiviazione": "Archiviato (falso positivo)",
}

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre"]


def setup_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.5rem;}
        .rs-livello {display:inline-block; padding:0 .5rem; border:1px solid #A6A6A6; border-radius:3px;
                     font-size:.8rem; font-weight:600; line-height:1.5rem; color:#55575d; vertical-align:middle;}
        .rs-livello.alto {border-color:#C0392B; color:#C0392B; background:rgba(192,57,43,.06);}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --- Dati ------------------------------------------------------------------

@st.cache_resource(show_spinner="Analisi della rete dei sinistri in corso…")
def get_pipeline(versione: int = 0) -> dict[str, Any]:
    """Esegue la pipeline una sola volta; `versione` serve a forzare il ricalcolo."""
    return esegui_pipeline(load_config())


def pipeline() -> dict[str, Any]:
    return get_pipeline(st.session_state.get("versione_dati", 0))


def ricarica_pipeline() -> None:
    st.session_state["versione_dati"] = st.session_state.get("versione_dati", 0) + 1
    get_pipeline.clear()


def salva_soglie(soglia_media: int, soglia_alta: int, soglia_regole: int) -> None:
    with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    raw.setdefault("scoring", {}).update(soglia_media=int(soglia_media), soglia_alta=int(soglia_alta))
    raw.setdefault("asis", {})["threshold"] = int(soglia_regole)
    with DEFAULT_CONFIG_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(raw, fh, allow_unicode=True, sort_keys=False)
    ricarica_pipeline()


# --- Formati ---------------------------------------------------------------

def etichetta_livello(fascia: str) -> str:
    classe = "rs-livello alto" if fascia == "alta" else "rs-livello"
    return f"<span class='{classe}'>{LIVELLO.get(fascia, fascia)}</span>"


def numero(valore: float, decimali: int = 0) -> str:
    testo = f"{valore:,.{decimali}f}"
    return testo.replace(",", "§").replace(".", ",").replace("§", ".")


def euro(valore: float) -> str:
    return f"{numero(valore)} €"


def percentuale(valore: float, decimali: int = 0) -> str:
    return f"{numero(valore * 100, decimali)}%"


def data_it(valore: Any) -> str:
    if valore is None or (isinstance(valore, float) and pd.isna(valore)) or valore == "":
        return ""
    try:
        return pd.to_datetime(valore).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(valore)


def data_ora_it(valore: Any) -> str:
    """Timestamp UTC del database decisioni -> ora italiana gg/mm/aaaa hh:mm."""
    try:
        ts = pd.to_datetime(valore, utc=True)
    except (ValueError, TypeError):
        return str(valore)
    try:
        from zoneinfo import ZoneInfo

        ts = ts.tz_convert(ZoneInfo("Europe/Rome"))
    except Exception:  # fuso non disponibile: resta UTC
        pass
    return ts.strftime("%d/%m/%Y %H:%M")


def oggi_esteso() -> str:
    d = dt.date.today()
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"


def maschera(valore: Any) -> str:
    testo = "" if valore is None or (isinstance(valore, float) and pd.isna(valore)) else str(valore)
    if len(testo) <= 6:
        return testo
    return testo[:4] + "•••" + testo[-3:]


# --- Codici leggibili dei gruppi -------------------------------------------

def codici_gruppo(p: dict[str, Any]) -> dict[str, str]:
    """id tecnico della community -> codice leggibile "RETE-01", "RETE-02"…

    Assegnati in ordine di score di rete decrescente (a parità: più sinistri, poi id tecnico),
    così gli alert più urgenti hanno i numeri più bassi.
    """
    fdf = p["feature_df"].assign(_id=p["feature_df"]["id_gruppo"].astype(str))
    fdf = fdf[fdf["_id"] != "-1"]
    ordinati = fdf.sort_values(["score_rete", "n_sinistri", "_id"], ascending=[False, False, True])["_id"]
    cifre = max(2, len(str(len(ordinati))))
    return {g: f"RETE-{i:0{cifre}d}" for i, g in enumerate(ordinati, start=1)}


def codice_gruppo(p: dict[str, Any], id_gruppo: Any) -> str:
    return codici_gruppo(p).get(str(id_gruppo), "")


# --- Tabelle ---------------------------------------------------------------

def tabella_alert(p: dict[str, Any], gestiti: set[str] | None = None) -> pd.DataFrame:
    """Tabella degli alert. La colonna "id" (tecnica) va nascosta con COLONNA_ID_NASCOSTA."""
    gestiti = gestiti or set()
    codici = codici_gruppo(p)
    righe = []
    for a in p["alerts"]:
        f = a["feature_gruppo"]
        righe.append(
            {
                "id": a["id_gruppo"],
                "Gruppo": codici.get(a["id_gruppo"], a["id_gruppo"]),
                "Livello": LIVELLO[a["fascia"]],
                "Score di rete": a["score_rete"],
                "Sinistri": int(f.get("n_sinistri", 0)),
                "Persone": int(f.get("n_persone", 0)),
                "Importo": euro(f.get("importo_totale", 0.0)),
                "Motivazione principale": a["reason_codes"][0] if a["reason_codes"] else "",
                "Stato": "Gestito" if a["id_gruppo"] in gestiti else "Da lavorare",
            }
        )
    df = pd.DataFrame(righe)
    if not df.empty:
        df = df.sort_values("Gruppo").reset_index(drop=True)
    return df


COLONNA_ID_NASCOSTA = {"id": None}


# --- Grafo -----------------------------------------------------------------

def sottografo_gruppo(p: dict[str, Any], sinistri_ids: list[str], includi_deboli: bool = True) -> nx.Graph:
    G: nx.Graph = p["grafo"]
    nodi = {f"sinistro:{s}" for s in sinistri_ids}
    vicini = set()
    for n in nodi:
        if n not in G:
            continue
        for v in G.neighbors(n):
            tipo = G.nodes[v].get("tipo")
            if includi_deboli or tipo in {"persona", "iban", "telefono"}:
                vicini.add(v)
    return G.subgraph(nodi | vicini).copy()


def _dimensione_nodo(tipo: str, grado: int) -> int:
    if tipo == "sinistro":
        return 13
    if tipo == "iban" and grado > 1:  # IBAN condiviso da più sinistri: in evidenza
        return 18 + 2 * min(grado, 8)
    return 9 + min(grado, 8)


def figura_grafo(H: nx.Graph, altezza: int = 460) -> go.Figure:
    """Grafo sinistri-entità: colore e simbolo per tipo, professionisti in grigio."""
    if H.number_of_nodes() == 0:
        fig = go.Figure()
        fig.add_annotation(text="Nessun collegamento", showarrow=False, font=dict(color="#8a8a8a"))
        fig.update_layout(height=160, xaxis_visible=False, yaxis_visible=False,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        return fig

    pos = nx.spring_layout(H, seed=7, k=1.2 / max(1, H.number_of_nodes()) ** 0.5, iterations=80)
    traces = []
    for forza, stile in (("debole", dict(width=0.8, color="rgba(166,166,166,.45)", dash="dot")),
                         ("forte", dict(width=1.2, color="rgba(20,33,61,.35)"))):
        xs, ys = [], []
        for a, b, d in H.edges(data=True):
            if d.get("forza", "forte") != forza:
                continue
            xs += [pos[a][0], pos[b][0], None]
            ys += [pos[a][1], pos[b][1], None]
        if xs:
            traces.append(go.Scatter(x=xs, y=ys, mode="lines", line=stile, hoverinfo="skip", showlegend=False))

    for tipo, (etichetta, colore, simbolo) in TIPI_NODO.items():
        nodi = [n for n in H.nodes if H.nodes[n].get("tipo") == tipo]
        if not nodi:
            continue
        hover = []
        for n in nodi:
            valore = n.split(":", 1)[1]
            if tipo in {"iban", "telefono"}:
                valore = maschera(valore)
            hover.append(f"<b>{etichetta}</b><br>{valore}<br>Collegamenti: {H.degree(n)}")
        traces.append(
            go.Scatter(
                x=[pos[n][0] for n in nodi], y=[pos[n][1] for n in nodi], mode="markers", name=etichetta,
                marker=dict(size=[_dimensione_nodo(tipo, H.degree(n)) for n in nodi],
                            color=colore, symbol=simbolo, line=dict(width=1.5, color="#ffffff")),
                hovertext=hover, hoverinfo="text",
            )
        )
    fig = go.Figure(traces)
    fig.update_layout(
        height=altezza, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        legend=dict(orientation="h", y=-0.02, yanchor="top", x=0.5, xanchor="center", font=dict(size=11)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white"),
    )
    return fig


def vai_a_gruppo(id_gruppo: str) -> None:
    st.session_state["gruppo_selezionato"] = str(id_gruppo)
    st.switch_page("views/alert.py")
