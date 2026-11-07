from __future__ import annotations

import streamlit as st

from views import business, confronto, decisioni, modello

st.title("Analisi")

tab_confronto, tab_business, tab_modello, tab_decisioni = st.tabs(
    ["Confronto", "Business case", "Modello", "Storico decisioni"]
)
with tab_confronto:
    confronto.render()
with tab_business:
    business.render()
with tab_modello:
    modello.render()
with tab_decisioni:
    decisioni.render()
