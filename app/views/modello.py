"""Analisi > Modello: coefficienti, champion/challenger, governance, dati e LLM."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import SERIE, numero, percentuale, pipeline, ricarica_pipeline
from retisinistri.decisions import monitoraggio
from retisinistri.models import FORBIDDEN_FEATURES
from retisinistri.synthetic import genera_dataset

NOMI = {
    "n_sinistri": "Numero di sinistri", "n_persone": "Numero di persone", "persone_multi_ruolo": "Persone con più ruoli",
    "quota_multi_ruolo": "Quota persone multi-ruolo", "sinistri_per_iban": "Sinistri per IBAN",
    "sinistri_per_telefono": "Sinistri per telefono", "quota_officina_top": "Concentrazione officina",
    "quota_avvocato_top": "Concentrazione avvocato", "finestra_giorni": "Finestra temporale (giorni)",
    "densita": "Densità della rete", "testimone_ricorrente_max": "Testimone ricorrente",
    "importo_totale": "Importo totale", "score_pratica_medio": "Punteggio regole attuali medio",
    "anomaly_score": "Anomaly score",
}


def render() -> None:
    p = pipeline()
    fdf = p["feature_df"]
    cols = p["model_cols"]

    st.subheader("Peso dei segnali")
    coef = pd.DataFrame([{"Segnale": NOMI.get(k, k), "Coefficiente": v, "Odds ratio": float(np.exp(v))}
                         for k, v in p["coefficienti"].items()]).sort_values("Coefficiente")
    fig = go.Figure(go.Bar(
        x=coef["Coefficiente"], y=coef["Segnale"], orientation="h", marker_cornerradius=4,
        marker_color=[SERIE[1] if v > 0 else SERIE[0] for v in coef["Coefficiente"]],
        hovertemplate="%{y}<br>β = %{x:.3f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#52514e", line_width=1)
    fig.update_layout(height=440, margin=dict(t=10, b=10), xaxis=dict(title="Coefficiente standardizzato (β)", gridcolor="rgba(0,0,0,.06)"),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
    st.caption("Champion: regressione logistica su feature standardizzate. Arancione: aumenta il rischio. Blu: lo riduce.")
    with st.expander("Tabella coefficienti"):
        tab = coef.sort_values("Coefficiente", ascending=False).copy()
        tab["Coefficiente"] = tab["Coefficiente"].map(lambda v: numero(v, 3))
        tab["Odds ratio"] = tab["Odds ratio"].map(lambda v: numero(v, 2))
        st.dataframe(tab, hide_index=True, width="stretch")

    st.subheader("Champion vs challenger")
    X = fdf[cols].fillna(0)
    conf = pd.DataFrame({
        "Gruppo": fdf["id_gruppo"].astype(str), "Sinistri": fdf["n_sinistri"].astype(int),
        "Champion (logistica)": np.round(p["model"].predict_proba(X)[:, 1] * 100).astype(int),
        "Challenger (gradient boosting)": np.round(p["challenger"].predict_proba(X)[:, 1] * 100).astype(int),
        "Etichetta reale": fdf["label_frode"].map({1: "frode", 0: "regolare"}),
    })
    conf["Differenza"] = conf["Challenger (gradient boosting)"] - conf["Champion (logistica)"]
    st.dataframe(conf, hide_index=True, width="stretch",
                 column_config={c: st.column_config.ProgressColumn(c, min_value=0, max_value=100, format="%d")
                                for c in ["Champion (logistica)", "Challenger (gradient boosting)"]})
    st.caption("Il challenger gira in shadow mode: produce score solo per confronto e non genera alert.")

    st.subheader("Governance")
    mon = monitoraggio()
    c = st.columns(3)
    c[0].metric("PSI", numero(mon["psi"], 2), help="Stabilità della popolazione: < 0,10 stabile · 0,10–0,25 da monitorare · > 0,25 instabile")
    c[1].metric("Override rate", percentuale(mon["override_rate"]))
    c[2].metric("FPR per provincia (max)", percentuale(mon["fpr_provincia"]))
    st.caption("Valori di monitoraggio dimostrativi.")
    st.markdown(
        f"""
- Feature vietate bloccate in addestramento: {', '.join(sorted(FORBIDDEN_FEATURES))}
- Mascheramento di IBAN, telefoni e codici fiscali nei testi inviati all'LLM e nell'interfaccia
- Controllo dei numeri: se la spiegazione LLM cita numeri assenti dall'input si usa il testo standard
- Testo standard automatico se l'LLM non è disponibile
- Nessuna decisione automatica: ogni esito è registrato con liquidatore e note
"""
    )

    st.subheader("Dati sintetici")
    st.caption(f"Dataset attuale: {len(p['sinistri'])} sinistri, {len(p['coinvolgimenti'])} coinvolgimenti, "
               f"{int(p['sinistri']['label_frode'].sum())} sinistri fraudolenti.")
    with st.form("dati"):
        c1, c2, c3 = st.columns(3)
        n = c1.number_input("Numero di sinistri", 50, 2000, 200, step=50)
        anelli = c2.number_input("Anelli di frode", 0, 15, 4)
        seed = c3.number_input("Seed", 0, 99999, 42)
        rigenera = st.form_submit_button("Rigenera dati")
    if rigenera:
        with st.spinner("Generazione dati e ricalcolo della rete…"):
            genera_dataset(n_sinistri=int(n), n_anelli=int(anelli), seed=int(seed))
            ricarica_pipeline()
        for k in ("gruppo_selezionato", "ultimo_salvataggio"):
            st.session_state.pop(k, None)
        st.rerun()
    if st.button("Ricalcola senza cambiare i dati"):
        ricarica_pipeline()
        st.rerun()

    st.subheader("Spiegazioni LLM")
    if os.getenv("ANTHROPIC_API_KEY"):
        st.write(f"Chiave API configurata. Modello: `{p['config'].get('llm', {}).get('model')}`.")
    else:
        st.write("Chiave API non configurata: le spiegazioni usano il testo standard.")
    st.caption("Per attivarla aggiungi ANTHROPIC_API_KEY nel file .env (in locale) o nei Secrets di Streamlit Cloud, poi riavvia l'app.")
