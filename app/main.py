"""Entry point dell'app RetiSinistri.

Avvio:  streamlit run app/main.py
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="RetiSinistri · Antifrode RC Auto", page_icon="🕸️", layout="wide")

from common import pipeline, setup_page_style  # noqa: E402

setup_page_style()

pagine = {
    "": [
        st.Page("views/home.py", title="Home", icon="🏠", default=True),
    ],
    "Operatività": [
        st.Page("views/alert.py", title="Coda alert", icon="🚨"),
        st.Page("views/sinistri.py", title="Sinistri", icon="📋"),
        st.Page("views/rete.py", title="Esplora la rete", icon="🕸️"),
        st.Page("views/valuta.py", title="Valuta nuova pratica", icon="➕"),
    ],
    "Analisi": [
        st.Page("views/confronto.py", title="AS-IS vs TO-BE", icon="📊"),
        st.Page("views/business.py", title="Business case", icon="💶"),
    ],
    "Governance": [
        st.Page("views/decisioni.py", title="Decisioni", icon="⚖️"),
        st.Page("views/modello.py", title="Modello", icon="🧠"),
        st.Page("views/impostazioni.py", title="Impostazioni", icon="⚙️"),
    ],
}

nav = st.navigation(pagine)

with st.sidebar:
    st.markdown("### 🕸️ RetiSinistri")
    st.caption("Prototipo antifrode per sinistri RC auto · dati sintetici")
    p = pipeline()
    n_alta = sum(1 for a in p["alerts"] if a["fascia"] == "alta")
    st.metric("Alert aperti", len(p["alerts"]), help="Gruppi in fascia media o alta")
    if n_alta:
        st.caption(f"🔴 {n_alta} in fascia alta")

nav.run()
