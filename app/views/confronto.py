from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import GRIGIO, SERIE, pipeline
from retisinistri.metrics import matrice_confusione, metriche_kpi
from retisinistri.score_pratica import aggiungi_score_pratica

p = pipeline()
cfg = p["config"]
sinistri = p["sinistri"]

st.title("📊 AS-IS vs TO-BE")
st.caption(
    "Confronto, sul singolo sinistro, tra le **regole tradizionali (AS-IS)** e lo **score di rete (TO-BE)**. "
    "Le etichette di frode sono note perché i dati sono sintetici. Muovi le soglie per vedere l'effetto."
)

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    soglia_asis = c1.slider("Soglia regole AS-IS", 0, 100, int(cfg.get("asis", {}).get("threshold", 50)), step=5,
                            help="Una pratica è segnalata se lo score AS-IS è ≥ soglia")
    soglia_rete = c2.slider("Soglia score di rete", 0, 100, int(cfg.get("scoring", {}).get("soglia_media", 40)), step=5,
                            help="Un sinistro è segnalato se appartiene a un gruppo con score ≥ soglia")
    combina = c3.toggle("TO-BE = regole **oppure** rete", value=True,
                        help="Il processo TO-BE affianca il modello di rete alle regole esistenti")

y = sinistri["label_frode"].astype(int)
pred_asis = (sinistri["score_pratica"] >= soglia_asis).astype(int)
pred_rete = (sinistri["score_rete"] >= soglia_rete).astype(int)
pred_tobe = (pred_asis | pred_rete) if combina else pred_rete

k_asis = metriche_kpi(y, pred_asis)
k_tobe = metriche_kpi(y, pred_tobe)
cm_asis = matrice_confusione(y, pred_asis)
cm_tobe = matrice_confusione(y, pred_tobe)

st.subheader("Indicatori chiave")
m = st.columns(4)
m[0].metric("Frodi intercettate (recall)", f"{k_tobe['recall']:.0%}", f"{(k_tobe['recall'] - k_asis['recall']) * 100:+.0f} pp vs AS-IS")
m[1].metric("Precisione degli alert", f"{k_tobe['precision']:.0%}", f"{(k_tobe['precision'] - k_asis['precision']) * 100:+.0f} pp vs AS-IS")
m[2].metric("Falsi positivi (FPR)", f"{k_tobe['FPR']:.1%}", f"{(k_tobe['FPR'] - k_asis['FPR']) * 100:+.1f} pp vs AS-IS", delta_color="inverse")
stp_asis = 1 - pred_asis.mean()
stp_tobe = 1 - pred_tobe.mean()
m[3].metric("Pratiche liquidabili in automatico", f"{stp_tobe:.0%}", f"{(stp_tobe - stp_asis) * 100:+.0f} pp vs AS-IS",
            help="Quota di pratiche senza alert (straight-through processing)")

sx, dx = st.columns([3, 2], gap="large")
with sx:
    metriche = ["Recall", "Precisione", "FPR"]
    fig = go.Figure([
        go.Bar(name="AS-IS (regole)", x=metriche, y=[k_asis["recall"], k_asis["precision"], k_asis["FPR"]],
               marker_color=GRIGIO, text=[f"{v:.0%}" for v in (k_asis["recall"], k_asis["precision"], k_asis["FPR"])],
               textposition="outside", hovertemplate="%{x}: %{y:.1%}<extra>AS-IS</extra>"),
        go.Bar(name="TO-BE (rete)", x=metriche, y=[k_tobe["recall"], k_tobe["precision"], k_tobe["FPR"]],
               marker_color=SERIE[0], text=[f"{v:.0%}" for v in (k_tobe["recall"], k_tobe["precision"], k_tobe["FPR"])],
               textposition="outside", hovertemplate="%{x}: %{y:.1%}<extra>TO-BE</extra>"),
    ])
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, height=380, yaxis=dict(tickformat=".0%", range=[0, 1.15], gridcolor="rgba(0,0,0,.06)"),
                      margin=dict(t=20, b=10), legend=dict(orientation="h", y=1.08), plot_bgcolor="rgba(0,0,0,0)")
    fig.update_traces(marker_cornerradius=4)
    st.plotly_chart(fig, width="stretch")

with dx:
    st.markdown("**Matrici di confusione** (sinistri)")
    tab = pd.DataFrame(
        {
            "": ["Frodi intercettate (TP)", "Frodi mancate (FN)", "Falsi allarmi (FP)", "Regolari non segnalati (TN)"],
            "AS-IS": [cm_asis["TP"], cm_asis["FN"], cm_asis["FP"], cm_asis["TN"]],
            "TO-BE": [cm_tobe["TP"], cm_tobe["FN"], cm_tobe["FP"], cm_tobe["TN"]],
        }
    )
    st.dataframe(tab, hide_index=True, width="stretch")
    st.caption(f"Su {len(sinistri)} sinistri, di cui {int(y.sum())} fraudolenti.")

st.divider()
st.subheader("Stress test delle soglie")
st.caption("Come cambiano recall e falsi positivi del modello di rete al variare della soglia.")
righe = []
for s in range(0, 101, 5):
    pr = (sinistri["score_rete"] >= s).astype(int)
    pr = (pred_asis | pr) if combina else pr
    k = metriche_kpi(y, pr)
    righe.append({"Soglia": s, "Recall": k["recall"], "FPR": k["FPR"], "Precisione": k["precision"], "Alert": int(pr.sum())})
st_df = pd.DataFrame(righe)
fig2 = go.Figure()
for nome, col in (("Recall", SERIE[0]), ("Precisione", SERIE[1]), ("FPR", SERIE[2])):
    fig2.add_trace(go.Scatter(x=st_df["Soglia"], y=st_df[nome], name=nome, mode="lines", line=dict(width=2, color=col),
                              hovertemplate=f"{nome}: %{{y:.1%}}<extra></extra>"))
fig2.add_vline(x=soglia_rete, line_dash="dot", line_color=GRIGIO, annotation_text="soglia attuale")
fig2.update_layout(height=340, hovermode="x unified", yaxis=dict(tickformat=".0%", gridcolor="rgba(0,0,0,.06)"),
                   xaxis_title="Soglia score di rete", margin=dict(t=20, b=10), legend=dict(orientation="h", y=1.1),
                   plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig2, width="stretch")
with st.expander("Vedi la tabella"):
    st.dataframe(st_df.style.format({"Recall": "{:.1%}", "FPR": "{:.1%}", "Precisione": "{:.1%}"}), hide_index=True, width="stretch")

st.divider()
st.subheader("Simulatore pesi regole AS-IS")
st.caption("Modifica i pesi delle regole tradizionali e osserva quante frodi verrebbero intercettate.")
pesi_base = cfg.get("asis", {}).get("weights", {})
cols = st.columns(5)
etichette = {"importo_richiesto": "Importo > 5.000 €", "giorni_da_inizio_polizza": "Polizza < 30 gg",
             "orario_notturno": "Notturno", "verbale_autorita": "Senza verbale", "testimone": "Testimone"}
nuovi = {}
for col, (k, lab) in zip(cols, etichette.items()):
    nuovi[k] = col.number_input(lab, 0, 100, int(pesi_base.get(k, 0)), step=5)
cfg_sim = {**cfg, "asis": {**cfg.get("asis", {}), "weights": nuovi, "threshold": soglia_asis}}
sim = aggiungi_score_pratica(sinistri.drop(columns=["score_pratica", "alert_asis"]), cfg_sim)
k_sim = metriche_kpi(y, sim["alert_asis"].astype(int))
r = st.columns(3)
r[0].metric("Recall con nuovi pesi", f"{k_sim['recall']:.0%}", f"{(k_sim['recall'] - k_asis['recall']) * 100:+.0f} pp")
r[1].metric("Precisione", f"{k_sim['precision']:.0%}", f"{(k_sim['precision'] - k_asis['precision']) * 100:+.0f} pp")
r[2].metric("Alert generati", int(sim["alert_asis"].sum()), f"{int(sim['alert_asis'].sum() - pred_asis.sum()):+d}", delta_color="off")
st.caption("Anche con pesi ottimizzati le regole sulla singola pratica faticano a riconoscere le frodi organizzate: "
           "i sinistri di un anello sembrano normali presi uno per uno, è la rete a renderli sospetti.")
