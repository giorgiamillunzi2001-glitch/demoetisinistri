"""Analisi > Confronto: regole attuali (AS-IS) vs score di rete (TO-BE)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import NEUTRO, PRINCIPALE, RISCHIO, percentuale, pipeline
from retisinistri.metrics import matrice_confusione, metriche_kpi
from retisinistri.score_pratica import aggiungi_score_pratica

LAYOUT = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=10))


def _pp(delta: float, decimali: int = 0) -> str:
    return f"{delta * 100:+.{decimali}f} pp".replace(".", ",")


def render() -> None:
    p = pipeline()
    cfg = p["config"]
    sinistri = p["sinistri"]

    st.subheader("Regole attuali vs score di rete")
    st.caption("Confronto sul singolo sinistro. Le etichette di frode sono note perché i dati sono sintetici.")

    c1, c2, c3 = st.columns(3)
    soglia_asis = c1.slider("Soglia regole attuali (AS-IS)", 0, 100, int(cfg.get("asis", {}).get("threshold", 50)), step=5)
    soglia_rete = c2.slider("Soglia score di rete (TO-BE)", 0, 100, int(cfg.get("scoring", {}).get("soglia_media", 40)), step=5)
    combina = c3.toggle("TO-BE = regole oppure rete", value=True,
                        help="Nel processo TO-BE lo score di rete affianca le regole esistenti")

    y = sinistri["label_frode"].astype(int)
    pred_asis = (sinistri["score_pratica"] >= soglia_asis).astype(int)
    pred_rete = (sinistri["score_rete"] >= soglia_rete).astype(int)
    pred_tobe = (pred_asis | pred_rete) if combina else pred_rete

    k_asis = metriche_kpi(y, pred_asis)
    k_tobe = metriche_kpi(y, pred_tobe)
    cm_asis = matrice_confusione(y, pred_asis)
    cm_tobe = matrice_confusione(y, pred_tobe)
    stp_asis = 1 - pred_asis.mean()
    stp_tobe = 1 - pred_tobe.mean()

    m = st.columns(4)
    m[0].metric("Recall", percentuale(k_tobe["recall"]), _pp(k_tobe["recall"] - k_asis["recall"]),
                help="Quota di frodi intercettate")
    m[1].metric("Precisione", percentuale(k_tobe["precision"]), _pp(k_tobe["precision"] - k_asis["precision"]),
                help="Quota di segnalazioni che sono frodi")
    m[2].metric("FPR", percentuale(k_tobe["FPR"], 1), _pp(k_tobe["FPR"] - k_asis["FPR"], 1), delta_color="inverse",
                help="Quota di sinistri regolari segnalati per errore")
    m[3].metric("STP", percentuale(stp_tobe), _pp(stp_tobe - stp_asis),
                help="Straight-through processing: pratiche liquidabili senza segnalazione")
    st.caption("Variazioni rispetto alle regole attuali.")

    sx, dx = st.columns([3, 2], gap="large")
    with sx:
        metriche = ["Recall", "Precisione", "FPR"]
        v_asis = [k_asis["recall"], k_asis["precision"], k_asis["FPR"]]
        v_tobe = [k_tobe["recall"], k_tobe["precision"], k_tobe["FPR"]]
        fig = go.Figure([
            go.Bar(name="Regole attuali", x=metriche, y=v_asis, marker_color=NEUTRO,
                   text=[percentuale(v) for v in v_asis], textposition="outside",
                   hovertemplate="%{x}: %{y:.1%}<extra>Regole attuali</extra>"),
            go.Bar(name="Score di rete", x=metriche, y=v_tobe, marker_color=PRINCIPALE,
                   text=[percentuale(v) for v in v_tobe], textposition="outside",
                   hovertemplate="%{x}: %{y:.1%}<extra>Score di rete</extra>"),
        ])
        fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, height=360,
                          yaxis=dict(tickformat=".0%", range=[0, 1.15], gridcolor="rgba(0,0,0,.06)"),
                          legend=dict(orientation="h", y=1.08), **LAYOUT)
        fig.update_traces(marker_cornerradius=4)
        st.plotly_chart(fig, width="stretch")
    with dx:
        st.markdown("**Matrice di confusione**")
        st.table(pd.DataFrame({
            "Regole attuali": [cm_asis["TP"], cm_asis["FN"], cm_asis["FP"], cm_asis["TN"]],
            "Score di rete": [cm_tobe["TP"], cm_tobe["FN"], cm_tobe["FP"], cm_tobe["TN"]],
        }, index=["Frodi intercettate (TP)", "Frodi mancate (FN)", "Falsi allarmi (FP)", "Regolari non segnalati (TN)"]))
        st.caption(f"{len(sinistri)} sinistri, di cui {int(y.sum())} fraudolenti.")

    st.markdown("**Stress test della soglia di rete**")
    righe = []
    for s in range(0, 101, 5):
        pr = (sinistri["score_rete"] >= s).astype(int)
        pr = (pred_asis | pr) if combina else pr
        k = metriche_kpi(y, pr)
        righe.append({"Soglia": s, "Recall": k["recall"], "Precisione": k["precision"], "FPR": k["FPR"], "Segnalazioni": int(pr.sum())})
    st_df = pd.DataFrame(righe)
    fig2 = go.Figure()
    for nome, col, tratto in (("Recall", PRINCIPALE, "solid"), ("Precisione", NEUTRO, "dash"), ("FPR", RISCHIO, "solid")):
        fig2.add_trace(go.Scatter(x=st_df["Soglia"], y=st_df[nome], name=nome, mode="lines", line=dict(width=2, color=col, dash=tratto),
                                  hovertemplate=f"{nome}: %{{y:.1%}}<extra></extra>"))
    fig2.add_vline(x=soglia_rete, line_dash="dot", line_color=NEUTRO, annotation_text="soglia attuale")
    fig2.update_layout(height=320, hovermode="x unified", yaxis=dict(tickformat=".0%", gridcolor="rgba(0,0,0,.06)"),
                       xaxis_title="Soglia score di rete", legend=dict(orientation="h", y=1.12), **LAYOUT)
    st.plotly_chart(fig2, width="stretch")
    with st.expander("Tabella"):
        tab = st_df.copy()
        for c in ("Recall", "Precisione"):
            tab[c] = tab[c].map(percentuale)
        tab["FPR"] = tab["FPR"].map(lambda v: percentuale(v, 1))
        st.dataframe(tab, hide_index=True, width="stretch")

    st.markdown("**Simulatore pesi delle regole attuali**")
    pesi_base = cfg.get("asis", {}).get("weights", {})
    etichette = {"importo_richiesto": "Importo > 5.000 €", "giorni_da_inizio_polizza": "Polizza < 30 giorni",
                 "orario_notturno": "Notturno", "verbale_autorita": "Senza verbale", "testimone": "Testimone"}
    cols = st.columns(5)
    nuovi = {k: col.number_input(lab, 0, 100, int(pesi_base.get(k, 0)), step=5)
             for col, (k, lab) in zip(cols, etichette.items())}
    cfg_sim = {**cfg, "asis": {**cfg.get("asis", {}), "weights": nuovi, "threshold": soglia_asis}}
    sim = aggiungi_score_pratica(sinistri.drop(columns=["score_pratica", "alert_asis"]), cfg_sim)
    k_sim = metriche_kpi(y, sim["alert_asis"].astype(int))
    r = st.columns(3)
    r[0].metric("Recall con nuovi pesi", percentuale(k_sim["recall"]), _pp(k_sim["recall"] - k_asis["recall"]))
    r[1].metric("Precisione", percentuale(k_sim["precision"]), _pp(k_sim["precision"] - k_asis["precision"]))
    r[2].metric("Segnalazioni generate", int(sim["alert_asis"].sum()), f"{int(sim['alert_asis'].sum() - pred_asis.sum()):+d}", delta_color="off")
    st.caption("I sinistri di un anello organizzato sembrano regolari presi uno per uno: anche con pesi diversi "
               "le regole sulla singola pratica li intercettano poco.")
