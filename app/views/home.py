from __future__ import annotations

import streamlit as st

from common import DECISIONI, data_ora_it, euro, oggi_esteso, pipeline, tabella_alert, vai_a_gruppo
from retisinistri.decisions import lista_decisioni

p = pipeline()
alerts = p["alerts"]
decisioni = lista_decisioni()
gestiti = {d["id_gruppo"] for d in decisioni}

st.markdown(
    f"<h1 style='margin-bottom:0'>Panoramica "
    f"<span style='font-size:1rem;font-weight:400;color:#8a8a8a'>{oggi_esteso()}</span></h1>",
    unsafe_allow_html=True,
)

importo_rischio = sum(a["feature_gruppo"].get("importo_totale", 0) for a in alerts)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sinistri analizzati", f"{len(p['sinistri']):,}".replace(",", "."))
c2.metric("Alert aperti", len(alerts))
c3.metric("Importo a rischio", euro(importo_rischio), help="Somma degli importi richiesti nei gruppi in alert")
c4.metric("Da lavorare", len([a for a in alerts if a["id_gruppo"] not in gestiti]))

st.subheader("Alert prioritari")
df = tabella_alert(p, gestiti).head(5)
if df.empty:
    st.write("Nessun alert aperto.")
else:
    ev = st.dataframe(
        df.drop(columns=["Persone"]),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=f"home_alert_{st.session_state.get('home_alert_ver', 0)}",
        column_config={"Score di rete": st.column_config.NumberColumn(format="%d")},
    )
    if ev.selection.rows:
        # Nuova chiave alla prossima visita: la tabella torna senza selezione
        st.session_state["home_alert_ver"] = st.session_state.get("home_alert_ver", 0) + 1
        vai_a_gruppo(df.iloc[ev.selection.rows[0]]["Gruppo"])

if decisioni:
    righe = [
        f"{data_ora_it(d['timestamp'])} · Gruppo {d['id_gruppo']} · {DECISIONI.get(d['decisione'], d['decisione'])} · {d['id_liquidatore']}"
        for d in decisioni[:3]
    ]
    st.caption("Ultime decisioni  \n" + "  \n".join(righe))
