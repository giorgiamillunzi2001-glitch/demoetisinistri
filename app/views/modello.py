"""Analisi > Modello: coefficienti, champion/challenger, governance, dati e LLM."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import (
    NEUTRO,
    PRINCIPALE,
    RISCHIO,
    codici_gruppo,
    numero,
    percentuale,
    pipeline,
    ricarica_pipeline,
)

from retisinistri.decisions import monitoraggio
from retisinistri.metrics import metriche_kpi
from retisinistri.models import FORBIDDEN_FEATURES
from retisinistri.synthetic import genera_dataset

NOMI = {
    "n_sinistri": "Numero di sinistri", "n_persone": "Numero di persone", "persone_multi_ruolo": "Persone con più ruoli",
    "quota_multi_ruolo": "Quota persone multi-ruolo", "sinistri_per_iban": "Sinistri per IBAN",
    "sinistri_per_telefono": "Sinistri per telefono", "quota_officina_top": "Concentrazione officina",
    "quota_avvocato_top": "Concentrazione avvocato", "finestra_giorni": "Finestra temporale (giorni)",
    "densita": "Densità della rete", "testimone_ricorrente_max": "Stesso testimone in più sinistri",
    "importo_totale": "Importo totale", "score_pratica_medio": "Punteggio regole attuali medio",
    "anomaly_score": "Anomaly score",
}


def _calibrazione(fdf: pd.DataFrame, p: dict) -> None:
    """Reliability diagram (probabilità calibrate fuori campione) e distribuzione degli score."""
    if "prob_calibrata" not in fdf.columns or fdf["label_frode"].nunique() < 2:
        return
    st.subheader("Calibrazione")
    c1, c2 = st.columns(2, gap="large")

    with c1:
        bins = np.linspace(0, 1, 6)
        fasce = pd.cut(fdf["prob_calibrata"], bins, include_lowest=True)
        tab = fdf.groupby(fasce, observed=True).agg(
            prevista=("prob_calibrata", "mean"), osservata=("label_frode", "mean"), gruppi=("label_frode", "size")
        ).reset_index(drop=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=NEUTRO, dash="dash", width=1),
                                 name="Calibrazione perfetta", hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=tab["prevista"], y=tab["osservata"], mode="lines+markers", name="Modello",
            line=dict(color=PRINCIPALE, width=2), marker=dict(size=8 + 2 * tab["gruppi"], color=PRINCIPALE),
            customdata=tab["gruppi"],
            hovertemplate="Probabilità prevista %{x:.0%}<br>Frodi osservate %{y:.0%}<br>Gruppi: %{customdata}<extra></extra>",
        ))
        fig.update_layout(height=340, margin=dict(t=10, b=10),
                          xaxis=dict(title="Probabilità prevista (calibrata)", tickformat=".0%", range=[0, 1], gridcolor="rgba(0,0,0,.06)"),
                          yaxis=dict(title="Quota di frodi osservata", tickformat=".0%", range=[0, 1.02], gridcolor="rgba(0,0,0,.06)"),
                          legend=dict(orientation="h", y=1.08), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption(f"Probabilità calibrate fuori campione (sono lo score di rete). "
                   f"{len(fdf)} gruppi in 5 fasce: con così pochi gruppi la curva è indicativa.")

    with c2:
        fig2 = go.Figure()
        for etichetta, valore, colore in (("Gruppi legittimi", 0, NEUTRO), ("Frodi", 1, RISCHIO)):
            sotto = fdf[fdf["label_frode"] == valore]["score_rete"]
            fig2.add_trace(go.Histogram(x=sotto, name=etichetta, marker_color=colore, xbins=dict(start=0, end=100, size=10),
                                        hovertemplate="Score %{x}<br>Gruppi: %{y}<extra>" + etichetta + "</extra>"))
        cfg = p["config"].get("scoring", {})
        for soglia, nome in ((cfg.get("soglia_media", 40), "medio"), (cfg.get("soglia_alta", 70), "alto")):
            fig2.add_vline(x=soglia, line_dash="dot", line_color=PRINCIPALE, annotation_text=f"livello {nome}")
        fig2.update_layout(barmode="overlay", height=340, margin=dict(t=10, b=10),
                           xaxis=dict(title="Score di rete", range=[0, 100]), yaxis=dict(title="Gruppi", gridcolor="rgba(0,0,0,.06)"),
                           legend=dict(orientation="h", y=1.08), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig2.update_traces(opacity=0.85)
        st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
        st.caption("Distribuzione degli score di rete: probabilità calibrata fuori campione, massimo 99. "
                   "La probabilità assoluta stimata è nella tabella Champion vs challenger.")


def render() -> None:
    p = pipeline()
    fdf = p["feature_df"]

    st.subheader("Peso dei segnali")
    coef = pd.DataFrame([{"Segnale": NOMI.get(k, k), "Coefficiente": v, "Odds ratio": float(np.exp(v))}
                         for k, v in p["coefficienti"].items()]).sort_values("Coefficiente")
    fig = go.Figure(go.Bar(
        x=coef["Coefficiente"], y=coef["Segnale"], orientation="h", marker_cornerradius=4,
        marker_color=[RISCHIO if v > 0 else NEUTRO for v in coef["Coefficiente"]],
        hovertemplate="%{y}<br>β = %{x:.3f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#52514e", line_width=1)
    fig.update_layout(height=440, margin=dict(t=10, b=10), xaxis=dict(title="Coefficiente standardizzato (β)", gridcolor="rgba(0,0,0,.06)"),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
    C = p.get("C_champion")
    st.caption("Champion: regressione logistica con regolarizzazione L2 su 6 segnali di rete standardizzati"
               + (f" (C = {numero(C, 2)}, scelto in cross-validation)" if C is not None else "")
               + ". Officine, avvocati e periti sono esclusi: sono segnali secondari. "
               "Rosso: aumenta il rischio. Grigio: lo riduce.")
    metodo = p.get("metodo_score", "")
    if metodo.startswith("cross_validation"):
        k = metodo.split("_")[2]
        st.caption(f"Lo score di ogni gruppo è calcolato in cross-validation a {k} fold: "
                   "viene da un modello addestrato senza quel gruppo, quindi le metriche di confronto non sono gonfiate.")
    else:
        st.caption("Gruppi troppo pochi per la cross-validation: score calcolato sul modello addestrato con tutti i gruppi.")
    with st.expander("Tabella coefficienti"):
        tab = coef.sort_values("Coefficiente", ascending=False).copy()
        tab["Coefficiente"] = tab["Coefficiente"].map(lambda v: numero(v, 3))
        tab["Odds ratio"] = tab["Odds ratio"].map(lambda v: numero(v, 2))
        st.dataframe(tab, hide_index=True, width="stretch")

    st.subheader("Champion vs challenger")
    soglia = int(p["config"].get("scoring", {}).get("soglia_media", 40))
    prev = percentuale(p.get("prevalenza_attesa", 0.05))
    nome_prob = f"Probabilità assoluta stimata (prevalenza {prev})"
    y = fdf["label_frode"].astype(int)
    righe = []
    for nome, col in (("Champion (logistica)", "score_rete"), ("Challenger (gradient boosting)", "score_challenger")):
        if col not in fdf.columns:
            continue
        k = metriche_kpi(y, (fdf[col] >= soglia).astype(int), fdf[col]) if y.nunique() == 2 else None
        righe.append({"Modello": nome,
                      "AUC": numero(k["AUC"], 2) if k else "n.d.",
                      f"Recall (soglia {soglia})": percentuale(k["recall"]) if k else "n.d.",
                      f"Precisione (soglia {soglia})": percentuale(k["precision"]) if k else "n.d."})
    st.table(pd.DataFrame(righe).set_index("Modello"))
    st.caption("Metriche fuori campione per entrambi, a livello di gruppo: stessa cross-validation, ogni gruppo è valutato "
               "da modelli addestrati senza di lui. Il challenger gira in shadow mode e non genera segnalazioni.")

    conf = pd.DataFrame({
        "Gruppo": fdf["id_gruppo"].astype(str).map(codici_gruppo(p)), "Sinistri": fdf["n_sinistri"].astype(int),
        "Champion (logistica)": fdf["score_rete"].astype(int),
        "Challenger (gradient boosting)": fdf.get("score_challenger", pd.Series(0, index=fdf.index)).astype(int),
        nome_prob: (fdf["prob_frode"] * 100).round(1),
        "Etichetta reale": fdf["label_frode"].map({1: "frode", 0: "regolare"}),
    })
    conf["Differenza"] = conf["Challenger (gradient boosting)"] - conf["Champion (logistica)"]
    st.dataframe(conf.sort_values("Gruppo"), hide_index=True, width="stretch",
                 column_config={**{c: st.column_config.ProgressColumn(c, min_value=0, max_value=99, format="%d")
                                   for c in ["Champion (logistica)", "Challenger (gradient boosting)"]},
                                nome_prob: st.column_config.NumberColumn(nome_prob, format="%.1f%%")})
    st.markdown(
        "Lo **score di rete** (0-99) è un indice di rischio per ordinare i casi ed è l'unico valore mostrato nelle "
        f"pagine operative; la **probabilità assoluta stimata** riporta la stessa stima alla prevalenza attesa di "
        f"frode nella realtà ({prev}) ed è quella da usare nei calcoli economici."
    )

    _calibrazione(fdf, p)

    st.subheader("Governance")
    sc = p["config"].get("scoring", {})
    mon = monitoraggio(p["sinistri"], {a["id_gruppo"] for a in p["alerts"]},
                       int(sc.get("soglia_media", 40)), int(sc.get("soglia_alta", 70)))
    nd = "n.d."
    c = st.columns(3)
    c[0].metric("PSI", numero(mon["psi"], 2) if mon["psi"] is not None else nd,
                help="Stabilità della distribuzione dello score di rete dei sinistri (non collegato, basso, medio, alto): "
                     "prima metà del dataset contro seconda metà, per data del sinistro. "
                     "< 0,10 stabile · 0,10–0,25 da monitorare · > 0,25 instabile")
    c[1].metric("Override rate", percentuale(mon["override_rate"]) if mon["override_rate"] is not None else nd,
                help="Dallo storico decisioni: quota di segnalazioni decise in cui il liquidatore ha archiviato o "
                     "liquidato (ultima decisione per gruppo). n.d. se non ci sono ancora decisioni.")
    c[2].metric("Falsi allarmi per provincia (max)",
                f"{percentuale(mon['fpr_provincia'], 1)} · {mon['provincia_max']}" if mon["fpr_provincia"] is not None else nd,
                help="Quota di sinistri regolari con score di rete pari o superiore alla soglia media, per provincia "
                     "(province con almeno 10 sinistri regolari). Solo controllo di equità: la provincia non è un input del modello.")
    if mon["fpr_per_provincia"] is not None:
        with st.expander("Falsi allarmi per provincia"):
            t = mon["fpr_per_provincia"].rename(columns={"provincia": "Provincia", "regolari": "Sinistri regolari",
                                                         "falsi_allarmi": "Falsi allarmi", "fpr": "Quota"})
            t["Quota"] = t["Quota"].map(lambda v: percentuale(v, 1))
            st.dataframe(t, hide_index=True, width="stretch")
    st.caption("Valori calcolati dai dati del prototipo; n.d. quando non sono calcolabili.")
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
        c1, c2, c3, c4 = st.columns(4)
        n = c1.number_input("Numero di sinistri", 50, 3000, 600, step=50)
        anelli = c2.number_input("Anelli di frode", 0, 30, 8)
        legittimi = c3.number_input("Gruppi legittimi collegati", 0, 30, 8, help="Famiglie e flotte aziendali")
        seed = c4.number_input("Seed", 0, 99999, 42)
        rigenera = st.form_submit_button("Rigenera dati")
    if rigenera:
        with st.spinner("Generazione dati e ricalcolo della rete…"):
            genera_dataset(n_sinistri=int(n), n_anelli=int(anelli), seed=int(seed), n_gruppi_legittimi=int(legittimi))
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
