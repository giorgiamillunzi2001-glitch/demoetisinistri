from __future__ import annotations

import os

import streamlit as st
import yaml

from common import pipeline, ricarica_pipeline
from retisinistri.config import DEFAULT_CONFIG_PATH
from retisinistri.synthetic import genera_dataset

p = pipeline()
cfg = p["config"]

st.title("⚙️ Impostazioni")

tab1, tab2, tab3 = st.tabs(["🎚️ Soglie di rischio", "🧪 Dati sintetici", "🤖 Spiegazioni LLM"])

with tab1:
    st.caption("Le soglie vengono salvate in `config.yaml` e applicate a tutta l'app.")
    with st.form("soglie"):
        c1, c2, c3 = st.columns(3)
        media = c1.number_input("Soglia fascia media (score di rete)", 0, 100, int(cfg.get("scoring", {}).get("soglia_media", 40)))
        alta = c2.number_input("Soglia fascia alta (score di rete)", 0, 100, int(cfg.get("scoring", {}).get("soglia_alta", 70)))
        asis = c3.number_input("Soglia alert regole AS-IS", 0, 100, int(cfg.get("asis", {}).get("threshold", 50)))
        if st.form_submit_button("💾 Salva e ricalcola", type="primary"):
            if media >= alta:
                st.error("La soglia media deve essere inferiore alla soglia alta.")
            else:
                with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as fh:
                    raw = yaml.safe_load(fh) or {}
                raw.setdefault("scoring", {}).update(soglia_media=int(media), soglia_alta=int(alta))
                raw.setdefault("asis", {})["threshold"] = int(asis)
                with DEFAULT_CONFIG_PATH.open("w", encoding="utf-8") as fh:
                    yaml.safe_dump(raw, fh, allow_unicode=True, sort_keys=False)
                ricarica_pipeline()
                st.toast("Soglie salvate e analisi ricalcolata", icon="✅")
                st.rerun()

with tab2:
    st.caption("Rigenera il dataset sintetico con parametri diversi. Sovrascrive i file in `data/raw`.")
    with st.form("dati"):
        c1, c2, c3 = st.columns(3)
        n = c1.number_input("Numero di sinistri", 50, 2000, 200, step=50)
        anelli = c2.number_input("Anelli di frode", 0, 15, 4)
        seed = c3.number_input("Seed casuale", 0, 99999, 42)
        if st.form_submit_button("🔄 Rigenera dati e ricalcola", type="primary"):
            with st.spinner("Generazione dati e ricalcolo della rete…"):
                genera_dataset(n_sinistri=int(n), n_anelli=int(anelli), seed=int(seed))
                ricarica_pipeline()
                pipeline()
            for k in ("gruppo_selezionato", "sinistro_selezionato"):
                st.session_state.pop(k, None)
            st.toast("Nuovo dataset generato", icon="✅")
            st.rerun()
    st.caption(f"Dataset attuale: {len(p['sinistri'])} sinistri, {len(p['coinvolgimenti'])} coinvolgimenti, "
               f"{int(p['sinistri']['label_frode'].sum())} sinistri fraudolenti.")
    if st.button("♻️ Ricalcola l'analisi senza cambiare i dati"):
        ricarica_pipeline()
        st.rerun()

with tab3:
    chiave = bool(os.getenv("ANTHROPIC_API_KEY"))
    if chiave:
        st.success(f"✅ Chiave API configurata · modello `{cfg.get('llm', {}).get('model')}`")
    else:
        st.warning("Nessuna `ANTHROPIC_API_KEY` trovata: le spiegazioni usano il testo deterministico di fallback.")
    st.markdown("Per attivare l'LLM crea un file `.env` nella cartella del progetto:")
    st.code("ANTHROPIC_API_KEY=la-tua-chiave\nLLM_MODEL=claude-haiku-5-5", language="bash")
    st.caption("Riavvia l'app dopo aver modificato `.env`.")
