from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import SERIE, pipeline
from retisinistri.decisions import monitoraggio
from retisinistri.models import FORBIDDEN_FEATURES

p = pipeline()
fdf = p["feature_df"]
cols = p["model_cols"]

st.title("🧠 Modello")
st.caption("Trasparenza sul modello di scoring: quali segnali pesano, come si confronta il challenger e quali guardrail sono attivi.")

NOMI = {
    "n_sinistri": "Numero di sinistri", "n_persone": "Numero di persone", "persone_multi_ruolo": "Persone con più ruoli",
    "quota_multi_ruolo": "Quota persone multi-ruolo", "sinistri_per_iban": "Sinistri per IBAN",
    "sinistri_per_telefono": "Sinistri per telefono", "quota_officina_top": "Concentrazione officina",
    "quota_avvocato_top": "Concentrazione avvocato", "finestra_giorni": "Finestra temporale (gg)",
    "densita": "Densità della rete", "testimone_ricorrente_max": "Testimone ricorrente",
    "importo_totale": "Importo totale", "score_pratica_medio": "Score AS-IS medio", "anomaly_score": "Anomaly score",
}

tab1, tab2, tab3 = st.tabs(["📈 Importanza dei segnali", "🥊 Champion vs Challenger", "🛡️ Governance"])

with tab1:
    coef = pd.DataFrame([{"Segnale": NOMI.get(k, k), "Coefficiente": v, "Odds ratio": float(np.exp(v))}
                         for k, v in p["coefficienti"].items()]).sort_values("Coefficiente")
    fig = go.Figure(go.Bar(
        x=coef["Coefficiente"], y=coef["Segnale"], orientation="h", marker_cornerradius=4,
        marker_color=[SERIE[1] if v > 0 else SERIE[0] for v in coef["Coefficiente"]],
        hovertemplate="%{y}<br>β = %{x:.3f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#52514e", line_width=1)
    fig.update_layout(height=470, margin=dict(t=10, b=10), xaxis=dict(title="Coefficiente standardizzato (β)", gridcolor="rgba(0,0,0,.06)"),
                      plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
    st.caption("🟧 arancione: aumenta il rischio · 🟦 blu: lo riduce. Champion: regressione logistica su feature standardizzate.")
    with st.expander("Tabella coefficienti"):
        st.dataframe(coef.sort_values("Coefficiente", ascending=False), hide_index=True, width="stretch",
                     column_config={"Coefficiente": st.column_config.NumberColumn(format="%.3f"),
                                    "Odds ratio": st.column_config.NumberColumn(format="%.2f")})

with tab2:
    X = fdf[cols].fillna(0)
    prob_ch = p["model"].predict_proba(X)[:, 1]
    prob_cl = p["challenger"].predict_proba(X)[:, 1]
    conf = pd.DataFrame({
        "Gruppo": fdf["id_gruppo"].astype(str), "Sinistri": fdf["n_sinistri"].astype(int),
        "Champion (logistica)": np.round(prob_ch * 100).astype(int),
        "Challenger (gradient boosting)": np.round(prob_cl * 100).astype(int),
        "Etichetta reale": fdf["label_frode"].map({1: "frode", 0: "regolare"}),
    })
    conf["Differenza"] = conf["Challenger (gradient boosting)"] - conf["Champion (logistica)"]
    st.dataframe(conf, hide_index=True, width="stretch",
                 column_config={c: st.column_config.ProgressColumn(c, min_value=0, max_value=100, format="%d")
                                for c in ["Champion (logistica)", "Challenger (gradient boosting)"]})
    st.caption("Il challenger gira in *shadow mode*: produce score solo per confronto e non genera alert. "
               "Con pochi gruppi sintetici entrambi i modelli separano bene le classi: le performance non sono rappresentative del reale.")

with tab3:
    mon = monitoraggio()
    c = st.columns(3)
    c[0].metric("PSI (stabilità popolazione)", f"{mon['psi']:.2f}", help="< 0.10 stabile · 0.10–0.25 da monitorare · > 0.25 instabile")
    c[1].metric("Override rate", f"{mon['override_rate']:.0%}")
    c[2].metric("FPR per provincia (max)", f"{mon['fpr_provincia']:.0%}")
    st.caption("Valori di monitoraggio dimostrativi.")
    st.markdown("#### Guardrail attivi")
    st.markdown(
        f"""
- 🚫 **Feature vietate** bloccate in addestramento: `{', '.join(sorted(FORBIDDEN_FEATURES))}`
- 🔒 **Mascheramento** di IBAN, telefoni e codici fiscali nei testi inviati all'LLM e nella UI
- 🔢 **Controllo numeri**: se la spiegazione LLM cita numeri assenti dall'input, si usa il testo deterministico
- 🧯 **Fallback** automatico se l'LLM non è disponibile
- 🧑‍⚖️ **Human-in-the-loop**: nessuna decisione automatica, ogni esito è registrato con liquidatore e note
"""
    )
