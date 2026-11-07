from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import STATO, euro, pipeline
from retisinistri.metrics import business_case

p = pipeline()
cfg = p["config"]
b = cfg.get("business", {})

st.title("💶 Business case")
st.caption("Stima del valore economico dell'analisi di rete. Le ipotesi sono didattiche: modificale per costruire i tuoi scenari.")

with st.container(border=True):
    st.markdown("**Ipotesi**")
    c1, c2, c3 = st.columns(3)
    premi = c1.number_input("Premi RC auto annui (€)", 0, 10_000_000_000, int(b.get("premi_rc_auto", 239_300_000)), step=1_000_000)
    loss = c2.slider("Loss ratio", 0.40, 1.00, float(b.get("loss_ratio", 0.75)), 0.01)
    quota = c3.slider("Frodi extra evitate (% dei sinistri pagati)", 0.0, 3.0, float(b.get("quota_frodi_extra_evitate", 0.01)) * 100, 0.1,
                      format="%.1f%%") / 100
    c4, c5, c6 = st.columns(3)
    costi = c4.number_input("Costi annui di esercizio (€)", 0, 50_000_000, int(b.get("costi_annui", 300_000)), step=10_000)
    una_tantum = c5.number_input("Investimento iniziale (€)", 0, 50_000_000, int(b.get("costo_una_tantum", 500_000)), step=10_000)
    costo_ind = c6.number_input("Costo per indagine (€)", 0, 10_000, int(b.get("costo_indagine", 150)), step=10)
    n_indagini = st.number_input("Pratiche inviate in indagine all'anno a seguito degli alert", 0, 1_000_000, 1000, step=100)

scenario = {"business": {"premi_rc_auto": premi, "loss_ratio": loss, "quota_frodi_extra_evitate": quota,
                         "costi_annui": costi, "costo_una_tantum": una_tantum}}
bc = business_case(scenario)
costo_indagini = n_indagini * costo_ind
netto_con_indagini = bc["valore_annuo"] - costo_indagini
payback = una_tantum / netto_con_indagini * 12 if netto_con_indagini > 0 else None

k = st.columns(4)
k[0].metric("Frodi evitate / anno", euro(bc["valore_avviato"]))
k[1].metric("Valore netto annuo", euro(netto_con_indagini), help="Frodi evitate − costi annui − costo indagini sugli alert")
k[2].metric("Risultato primo anno", euro(netto_con_indagini - una_tantum))
k[3].metric("Rientro investimento", f"{payback:.1f} mesi" if payback else "non raggiunto")

if netto_con_indagini <= 0:
    st.error("⚠️ Con queste ipotesi il progetto non genera valore positivo.")

st.caption(f"Costo indagini: {euro(costo_indagini)} / anno ({n_indagini:,} pratiche × {euro(costo_ind)}).".replace(",", "."))

st.divider()
st.subheader("Scenari di efficacia")
quote = [0.003, 0.005, 0.01, 0.015, 0.02]
righe = []
for q in quote:
    s = {"business": {**scenario["business"], "quota_frodi_extra_evitate": q}}
    r = business_case(s)
    righe.append({"Frodi extra evitate": f"{q:.1%}", "Valore netto annuo": r["valore_annuo"] - costo_indagini,
                  "Primo anno": r["primo_anno"] - costo_indagini})
df = pd.DataFrame(righe)
colori = [STATO["bassa"] if v >= 0 else STATO["alta"] for v in df["Valore netto annuo"]]
fig = go.Figure(go.Bar(x=df["Frodi extra evitate"], y=df["Valore netto annuo"], marker_color=colori, marker_cornerradius=4,
                       text=[euro(v) for v in df["Valore netto annuo"]], textposition="outside",
                       hovertemplate="Quota %{x}<br>Valore netto: € %{y:,.0f}<extra></extra>"))
fig.add_hline(y=0, line_color="#52514e", line_width=1)
fig.update_layout(height=360, yaxis=dict(title="€ / anno", gridcolor="rgba(0,0,0,.06)"), xaxis_title="Quota di frodi extra evitate",
                  margin=dict(t=30, b=10), plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, width="stretch")
st.caption("🟢 valore positivo · 🔴 valore negativo")
st.dataframe(df.style.format({"Valore netto annuo": "€ {:,.0f}", "Primo anno": "€ {:,.0f}"}), hide_index=True, width="stretch")
