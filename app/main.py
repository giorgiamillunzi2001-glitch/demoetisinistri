"""Entry point dell'app RetiSinistri.

Avvio:  streamlit run app/main.py
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="RetiSinistri", page_icon=":material/hub:", layout="wide")

from common import pipeline, salva_soglie, setup_page_style

from retisinistri.decisions import azzera_decisioni

setup_page_style()

nav = st.navigation(
    [
        st.Page("views/home.py", title="Panoramica", icon=":material/dashboard:", default=True),
        st.Page("views/alert.py", title="Segnalazioni", icon=":material/report:", url_path="segnalazioni"),
        st.Page("views/valuta.py", title="Nuova denuncia", icon=":material/add_circle:"),
        st.Page("views/analisi.py", title="Analisi", icon=":material/insights:"),
    ]
)

p = pipeline()
cfg = p["config"]
st.session_state.setdefault("id_liquidatore", "LQ-001")

with st.sidebar:
    st.markdown("**RetiSinistri**")
    st.text_input("ID liquidatore", key="id_liquidatore")
    st.metric("Segnalazioni aperte", len(p["alerts"]))

    with st.expander("Impostazioni"):
        with st.form("soglie", border=False):
            media = st.number_input("Soglia livello medio", 0, 100, int(cfg.get("scoring", {}).get("soglia_media", 40)))
            alta = st.number_input("Soglia livello alto", 0, 100, int(cfg.get("scoring", {}).get("soglia_alta", 70)))
            regole = st.number_input("Soglia regole attuali", 0, 100, int(cfg.get("asis", {}).get("threshold", 50)))
            if st.form_submit_button("Salva"):
                if media >= alta:
                    st.error("La soglia media deve essere inferiore a quella alta.")
                else:
                    salva_soglie(media, alta, regole)
                    st.rerun()

        st.divider()
        messaggio = st.session_state.pop("storico_azzerato", None)
        if messaggio:
            st.success(messaggio)
        if not st.session_state.get("conferma_azzera"):
            if st.button("Azzera storico demo", help="Cancella tutte le decisioni e gli esiti registrati"):
                st.session_state["conferma_azzera"] = True
                st.rerun()
        else:
            st.warning("Cancellare tutte le decisioni e gli esiti registrati? L'operazione non si può annullare.")
            si, no = st.columns(2)
            if si.button("Conferma", type="primary"):
                n = azzera_decisioni()
                for k in ("conferma_azzera", "ultimo_salvataggio", "esito_registrato"):
                    st.session_state.pop(k, None)
                st.session_state["storico_azzerato"] = f"Storico azzerato: {n} decisioni cancellate."
                st.rerun()
            if no.button("Annulla"):
                st.session_state.pop("conferma_azzera", None)
                st.rerun()

    st.caption("Prototipo · dati sintetici")

nav.run()
