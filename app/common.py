"""Funzioni condivise tra le pagine dell'app RetiSinistri."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retisinistri.config import load_config  # noqa: E402
from retisinistri.pipeline import esegui_pipeline  # noqa: E402

# Palette di riferimento (validata per daltonismo) e colori di stato riservati
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
GRIGIO = "#8a8984"
STATO = {"alta": "#d03b3b", "media": "#fab219", "bassa": "#0ca30c"}
ICONA_FASCIA = {"alta": "🔴", "media": "🟠", "bassa": "🟢"}
ETICHETTA_FASCIA = {"alta": "Alta", "media": "Media", "bassa": "Bassa"}

TIPI_NODO = {
    # tipo: (etichetta, colore, simbolo)
    "sinistro": ("Sinistro", SERIE[0], "circle"),
    "persona": ("Persona", SERIE[1], "diamond"),
    "iban": ("IBAN", SERIE[2], "square"),
    "telefono": ("Telefono", SERIE[2], "triangle-up"),
    "officina": ("Officina", GRIGIO, "cross"),
    "avvocato": ("Avvocato", GRIGIO, "x"),
    "perito": ("Perito", GRIGIO, "star"),
}

ESITI = {
    "in_corso": "In corso",
    "frode_confermata": "Frode confermata",
    "regolare": "Regolare",
}
DECISIONI = {
    "approfondimento": "Approfondimento (SIU)",
    "liquidazione": "Liquidazione regolare",
    "sospensione": "Sospensione pagamento",
    "archiviazione": "Archiviazione alert",
}


def setup_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2rem;}
        .rs-hero {padding: 1.4rem 1.6rem; border-radius: 14px;
                  background: linear-gradient(135deg, #0d366b 0%, #2a78d6 100%); color: #fff;}
        .rs-hero h1 {color:#fff; margin:0 0 .3rem 0; font-size: 2rem;}
        .rs-hero p {color:#e6eefb; margin:0; font-size: 1.05rem;}
        .rs-chip {display:inline-block; padding:.15rem .6rem; border-radius:999px;
                  font-size:.8rem; font-weight:600; border:1px solid rgba(0,0,0,.08);}
        .rs-reason {padding:.5rem .8rem; border-left:4px solid #2a78d6; background:rgba(42,120,214,.07);
                    border-radius:4px; margin-bottom:.4rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner="Analisi della rete dei sinistri in corso…")
def get_pipeline(versione: int = 0) -> dict[str, Any]:
    """Esegue la pipeline una sola volta; `versione` serve a forzare il ricalcolo."""
    return esegui_pipeline(load_config())


def pipeline() -> dict[str, Any]:
    return get_pipeline(st.session_state.get("versione_dati", 0))


def ricarica_pipeline() -> None:
    st.session_state["versione_dati"] = st.session_state.get("versione_dati", 0) + 1
    get_pipeline.clear()


def chip_fascia(fascia: str) -> str:
    colore = STATO.get(fascia, GRIGIO)
    return (
        f"<span class='rs-chip' style='background:{colore}22;color:inherit;border-color:{colore}'>"
        f"{ICONA_FASCIA.get(fascia, '⚪')} Rischio {ETICHETTA_FASCIA.get(fascia, fascia)}</span>"
    )


def euro(valore: float) -> str:
    return f"€ {valore:,.0f}".replace(",", ".")


def maschera(valore: Any) -> str:
    testo = "" if valore is None or (isinstance(valore, float) and pd.isna(valore)) else str(valore)
    if len(testo) <= 6:
        return testo
    return testo[:4] + "•••" + testo[-3:]


def tabella_alert(p: dict[str, Any]) -> pd.DataFrame:
    righe = []
    for a in p["alerts"]:
        f = a["feature_gruppo"]
        righe.append(
            {
                "Gruppo": a["id_gruppo"],
                "Fascia": f"{ICONA_FASCIA[a['fascia']]} {ETICHETTA_FASCIA[a['fascia']]}",
                "Score rete": a["score_rete"],
                "Sinistri": int(f.get("n_sinistri", 0)),
                "Persone": int(f.get("n_persone", 0)),
                "Finestra (gg)": int(f.get("finestra_giorni", 0)),
                "Importo totale": f.get("importo_totale", 0.0),
                "Score AS-IS medio": round(a["score_pratica_medio"], 1),
                "Motivazione principale": a["reason_codes"][0] if a["reason_codes"] else "—",
            }
        )
    df = pd.DataFrame(righe)
    if not df.empty:
        df = df.sort_values("Score rete", ascending=False).reset_index(drop=True)
    return df


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


def figura_grafo(H: nx.Graph, altezza: int = 520, evidenzia: set[str] | None = None) -> go.Figure:
    """Disegna un grafo sinistri-entità con plotly (colore + simbolo per tipo)."""
    evidenzia = evidenzia or set()
    if H.number_of_nodes() == 0:
        fig = go.Figure()
        fig.add_annotation(text="Nessun collegamento da mostrare", showarrow=False)
        fig.update_layout(height=200, xaxis_visible=False, yaxis_visible=False)
        return fig

    pos = nx.spring_layout(H, seed=7, k=1.2 / max(1, H.number_of_nodes()) ** 0.5, iterations=80)
    traces = []

    for forza, stile in (("debole", dict(width=1, color="rgba(138,137,132,.35)", dash="dot")),
                         ("forte", dict(width=1.6, color="rgba(82,81,78,.55)"))):
        xs, ys = [], []
        for a, b, d in H.edges(data=True):
            if d.get("forza", "forte") != forza:
                continue
            xs += [pos[a][0], pos[b][0], None]
            ys += [pos[a][1], pos[b][1], None]
        if xs:
            traces.append(go.Scatter(x=xs, y=ys, mode="lines", line=stile, hoverinfo="skip",
                                     name=f"Legame {forza}", showlegend=True))

    for tipo, (etichetta, colore, simbolo) in TIPI_NODO.items():
        nodi = [n for n in H.nodes if H.nodes[n].get("tipo") == tipo]
        if not nodi:
            continue
        hover, dims, linee = [], [], []
        for n in nodi:
            valore = n.split(":", 1)[1]
            if tipo in {"iban", "telefono"}:
                valore = maschera(valore)
            hover.append(f"<b>{etichetta}</b><br>{valore}<br>Collegamenti: {H.degree(n)}")
            dims.append(16 if tipo == "sinistro" else 11 + min(H.degree(n), 10))
            linee.append(3 if n in evidenzia else 2)
        traces.append(
            go.Scatter(
                x=[pos[n][0] for n in nodi], y=[pos[n][1] for n in nodi], mode="markers",
                name=etichetta,
                marker=dict(size=dims, color=colore, symbol=simbolo,
                            line=dict(width=linee, color=["#0b0b0b" if n in evidenzia else "#ffffff" for n in nodi])),
                hovertext=hover, hoverinfo="text",
            )
        )
    fig = go.Figure(traces)
    fig.update_layout(
        height=altezza, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        legend=dict(orientation="h", y=-0.02), plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white"),
    )
    return fig


def vai_a_gruppo(id_gruppo: str) -> None:
    st.session_state["gruppo_selezionato"] = str(id_gruppo)
    st.switch_page("views/alert.py")


def vai_a_sinistro(id_sinistro: str) -> None:
    st.session_state["sinistro_selezionato"] = str(id_sinistro)
    st.switch_page("views/sinistri.py")
