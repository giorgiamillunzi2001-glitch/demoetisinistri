"""Analisi > Business case."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import PRINCIPALE, RISCHIO, euro, numero, percentuale, pipeline

from retisinistri.metrics import business_case, parametri_reali

AIUTO_QUOTA = ("Oggi l'antifrode di mercato vale circa il 2% del costo dei sinistri; "
               "ipotesi: il grafo aggiunge un quarto in più, cioè lo 0,5%.")


def render() -> None:
    cfg = pipeline()["config"]
    b = cfg.get("business", {})
    cal = cfg.get("calibrazione", {}) or {}

    st.subheader("Business case")
    st.caption("Ipotesi didattiche, modificabili.")

    c1, c2, c3 = st.columns(3)
    premi = c1.number_input("Premi RC auto annui (€)", 0, 10_000_000_000, int(b.get("premi_rc_auto", 239_300_000)), step=1_000_000)
    loss = c2.slider("Loss ratio", 0.40, 1.00, float(b.get("loss_ratio", 0.75)), 0.01)
    quota = c3.slider("Frodi extra evitate (% del costo dei sinistri)", 0.0, 3.0,
                      float(b.get("quota_frodi_extra_evitate", 0.005)) * 100, 0.1, format="%.1f%%",
                      help=AIUTO_QUOTA) / 100
    c4, c5, c6, c7 = st.columns(4)
    costi = c4.number_input("Costi annui di esercizio (€)", 0, 50_000_000, int(b.get("costi_annui", 300_000)), step=10_000)
    una_tantum = c5.number_input("Investimento iniziale (€)", 0, 50_000_000, int(b.get("costo_una_tantum", 500_000)), step=10_000)
    costo_ind = c6.number_input("Costo per indagine (€)", 0, 10_000, int(b.get("costo_indagine", 150)), step=10)
    n_indagini = c7.number_input("Indagini all'anno", 0, 1_000_000, 1000, step=100)

    scenario = {"business": {"premi_rc_auto": premi, "loss_ratio": loss, "quota_frodi_extra_evitate": quota,
                             "costi_annui": costi, "costo_una_tantum": una_tantum}, "calibrazione": cal}
    bc = business_case(scenario)
    costo_indagini = n_indagini * costo_ind
    netto = bc["valore_annuo"] - costo_indagini
    payback = una_tantum / netto * 12 if netto > 0 else None

    k = st.columns(4)
    k[0].metric("Frodi evitate all'anno", euro(bc["valore_avviato"]))
    k[1].metric("Valore netto annuo", euro(netto), help="Frodi evitate − costi annui − costo delle indagini")
    k[2].metric("Risultato primo anno", euro(netto - una_tantum))
    k[3].metric("Rientro investimento", f"{numero(payback, 1)} mesi" if payback else "non raggiunto")
    st.caption(
        f"Costo dei sinistri: {euro(bc['costo_sinistri'])} all'anno (premi × loss ratio), pari a circa "
        f"{numero(bc['sinistri_annui'])} sinistri con il costo medio IVASS di {euro(bc['costo_medio_sinistro'])}. "
        f"Frodi evitate = costo dei sinistri × {numero(quota * 100, 1).removesuffix(',0')}%. "
        f"Costo indagini: {euro(costo_indagini)} all'anno ({numero(n_indagini)} indagini × {euro(costo_ind)})."
    )
    st.caption(AIUTO_QUOTA)
    if netto <= 0:
        st.warning("Con queste ipotesi il progetto non genera valore positivo.")

    p = pipeline()
    sn = p["sinistri"]
    frodi = int(sn["label_frode"].sum())
    soglia = int(p["config"].get("scoring", {}).get("soglia_media", 40))
    intercettate = int(((sn["score_rete"] >= soglia) & (sn["label_frode"] == 1)).sum())
    if frodi:
        st.caption(
            f"Nel prototipo lo score di rete intercetta {intercettate} sinistri fraudolenti su {frodi} "
            f"(recall {percentuale(intercettate / frodi)}, soglia {soglia}). La quota di frodi extra evitate qui sopra "
            "è un'ipotesi prudente e volutamente molto più bassa: la recall è misurata su dati sintetici e non è "
            "trasferibile così com'è al portafoglio reale."
        )

    st.markdown("**Scenari di efficacia**")
    righe = []
    for q in [0.003, 0.005, 0.01, 0.015, 0.02]:
        r = business_case({"business": {**scenario["business"], "quota_frodi_extra_evitate": q}})
        righe.append({"Frodi extra evitate": f"{numero(q * 100, 1).removesuffix(',0')}%", "Valore netto annuo": r["valore_annuo"] - costo_indagini,
                      "Primo anno": r["primo_anno"] - costo_indagini})
    df = pd.DataFrame(righe)
    colori = [PRINCIPALE if v >= 0 else RISCHIO for v in df["Valore netto annuo"]]
    fig = go.Figure(go.Bar(x=df["Frodi extra evitate"], y=df["Valore netto annuo"], marker_color=colori, marker_cornerradius=4,
                           text=[euro(v) for v in df["Valore netto annuo"]], textposition="outside",
                           hovertemplate="Quota %{x}<br>Valore netto: %{y:,.0f} €<extra></extra>"))
    fig.add_hline(y=0, line_color="#52514e", line_width=1)
    fig.update_layout(height=340, yaxis=dict(title="€ all'anno", gridcolor="rgba(0,0,0,.06)"),
                      xaxis=dict(title="Quota di frodi extra evitate", type="category"), margin=dict(t=30, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", separators=",.")
    st.plotly_chart(fig, width="stretch")
    st.caption("Blu scuro: valore netto positivo. Rosso: negativo.")
    tab = df.copy()
    for c in ("Valore netto annuo", "Primo anno"):
        tab[c] = tab[c].map(euro)
    st.dataframe(tab, hide_index=True, width="stretch")

    righe_reali = parametri_reali(cfg)
    if righe_reali:
        st.markdown("**Parametri reali usati**")
        st.dataframe(pd.DataFrame([{
            "Parametro": r["parametro"],
            "Valore": euro(r["valore"]) if r["formato"] == "euro" else percentuale(r["valore"], 1).replace(",0%", "%"),
            "Anno": r["anno"], "Fonte": r["fonte"],
        } for r in righe_reali]), hide_index=True, width="stretch")
