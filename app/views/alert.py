from __future__ import annotations

import pandas as pd
import streamlit as st

from common import (
    DECISIONI,
    ESITI,
    chip_fascia,
    euro,
    figura_grafo,
    maschera,
    pipeline,
    sottografo_gruppo,
    tabella_alert,
    vai_a_sinistro,
)
from retisinistri.decisions import lista_decisioni, salva_decisione
from retisinistri.explain_llm import spiega_alert

p = pipeline()
alerts = {a["id_gruppo"]: a for a in p["alerts"]}

st.title("🚨 Coda alert")
st.caption("Gruppi di sinistri collegati con score di rete in fascia media o alta. Seleziona una riga per aprire il dettaglio.")

if not alerts:
    st.success("Nessun alert aperto.")
    st.stop()

# --- Filtri ---------------------------------------------------------------
decisi = {d["id_gruppo"] for d in lista_decisioni()}
f1, f2, f3 = st.columns([2, 2, 3])
fasce = f1.segmented_control("Fascia", ["alta", "media"], selection_mode="multi", default=["alta", "media"],
                             format_func=lambda x: {"alta": "🔴 Alta", "media": "🟠 Media"}[x])
stato = f2.segmented_control("Stato", ["tutti", "da lavorare", "gestiti"], default="tutti")
score_min = f3.slider("Score di rete minimo", 0, 100, 0)

df = tabella_alert(p)
df["Stato"] = df["Gruppo"].map(lambda g: "✅ Gestito" if g in decisi else "🕒 Da lavorare")
df = df[df["Gruppo"].map(lambda g: alerts[g]["fascia"] in (fasce or []))]
df = df[df["Score rete"] >= score_min]
if stato == "da lavorare":
    df = df[~df["Gruppo"].isin(decisi)]
elif stato == "gestiti":
    df = df[df["Gruppo"].isin(decisi)]
df = df.reset_index(drop=True)

evento = st.dataframe(
    df,
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Score rete": st.column_config.ProgressColumn("Score rete", min_value=0, max_value=100, format="%d"),
        "Importo totale": st.column_config.NumberColumn(format="€ %.0f"),
    },
)

selezionato = None
if evento.selection.rows:
    selezionato = df.iloc[evento.selection.rows[0]]["Gruppo"]
elif st.session_state.get("gruppo_selezionato") in alerts:
    selezionato = st.session_state["gruppo_selezionato"]

opzioni = list(df["Gruppo"]) or list(alerts)
if selezionato not in opzioni:
    selezionato = opzioni[0]
selezionato = st.selectbox("Gruppo da analizzare", opzioni, index=opzioni.index(selezionato),
                           format_func=lambda g: f"Gruppo {g} · score {alerts[g]['score_rete']}")
st.session_state["gruppo_selezionato"] = selezionato

# --- Dettaglio ------------------------------------------------------------
a = alerts[selezionato]
f = a["feature_gruppo"]
sinistri = p["sinistri"]
ids = sinistri.loc[sinistri["id_gruppo"] == str(selezionato), "id_sinistro"].tolist()
coinv = p["coinvolgimenti"][p["coinvolgimenti"]["id_sinistro"].isin(ids)]

st.divider()
st.markdown(f"## Gruppo {selezionato} &nbsp; {chip_fascia(a['fascia'])}", unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Score di rete", f"{a['score_rete']}/100")
k2.metric("Score AS-IS medio", f"{a['score_pratica_medio']:.0f}/100", help="Punteggio delle regole tradizionali sulla singola pratica")
k3.metric("Sinistri", int(f["n_sinistri"]))
k4.metric("Persone coinvolte", int(f["n_persone"]))
k5.metric("Importo richiesto", euro(f["importo_totale"]))

tab_perche, tab_rete, tab_sinistri, tab_persone, tab_decisione = st.tabs(
    ["💡 Perché è segnalato", "🕸️ Rete", "📋 Sinistri", "👥 Persone e contatti", "⚖️ Decisione"]
)

with tab_perche:
    st.markdown("#### Reason code")
    for r in a["reason_codes"] or ["Nessun reason code disponibile"]:
        st.markdown(f"<div class='rs-reason'>{r}</div>", unsafe_allow_html=True)

    st.markdown("#### Spiegazione per il liquidatore")
    chiave = f"spiegazione_{selezionato}"
    if st.button("✨ Genera spiegazione", key=f"btn_{chiave}"):
        with st.spinner("Generazione in corso…"):
            st.session_state[chiave] = spiega_alert(a)
    if chiave in st.session_state:
        st.info(st.session_state[chiave])
        st.caption("Generata da LLM se configurato (ANTHROPIC_API_KEY), altrimenti dal testo deterministico. "
                   "Dati sensibili mascherati e numeri verificati contro l'input.")

    st.markdown("#### Indicatori di rete")
    ind = pd.DataFrame(
        [
            ("Finestra temporale", f"{int(f['finestra_giorni'])} giorni"),
            ("Sinistri per IBAN", f"{f['sinistri_per_iban']:.1f}"),
            ("Sinistri per telefono", f"{f['sinistri_per_telefono']:.1f}"),
            ("Quota officina più frequente", f"{f['quota_officina_top']:.0%}"),
            ("Quota avvocato più frequente", f"{f['quota_avvocato_top']:.0%}"),
            ("Persone con più ruoli", f"{int(f['persone_multi_ruolo'])}"),
            ("Densità della rete", f"{f['densita']:.2f}"),
            ("Ricorrenze testimone", f"{int(f['testimone_ricorrente_max'])}"),
            ("Anomaly score", f"{a['anomaly_score']:.2f}"),
        ],
        columns=["Indicatore", "Valore"],
    )
    st.dataframe(ind, hide_index=True, width="stretch")

with tab_rete:
    deboli = st.toggle("Mostra anche officine, periti e avvocati (legami deboli)", value=True)
    H = sottografo_gruppo(p, ids, includi_deboli=deboli)
    st.plotly_chart(figura_grafo(H), width="stretch")
    st.caption("Passa il mouse sui nodi per i dettagli. IBAN e telefoni sono mascherati.")

with tab_sinistri:
    cols = ["id_sinistro", "data_sinistro", "data_denuncia", "importo_richiesto", "giorni_da_inizio_polizza",
            "orario_notturno", "verbale_autorita", "id_officina", "id_avvocato", "score_pratica", "alert_asis"]
    tab = sinistri[sinistri["id_sinistro"].isin(ids)][cols].sort_values("data_sinistro")
    ev = st.dataframe(
        tab, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        column_config={
            "importo_richiesto": st.column_config.NumberColumn("Importo", format="€ %.2f"),
            "score_pratica": st.column_config.NumberColumn("Score AS-IS"),
            "alert_asis": st.column_config.CheckboxColumn("Alert AS-IS"),
        },
        key=f"tab_sin_{selezionato}",
    )
    n_asis = int(tab["alert_asis"].sum())
    st.caption(f"Le regole AS-IS avrebbero segnalato **{n_asis} su {len(tab)}** sinistri di questo gruppo.")
    if ev.selection.rows:
        sid = tab.iloc[ev.selection.rows[0]]["id_sinistro"]
        if st.button(f"Apri scheda sinistro {sid}"):
            vai_a_sinistro(sid)

with tab_persone:
    persone = (
        coinv.groupby("id_persona")
        .agg(
            ruoli=("ruolo", lambda r: ", ".join(sorted(set(r)))),
            sinistri=("id_sinistro", "nunique"),
            telefoni=("telefono", lambda t: ", ".join(sorted({maschera(x) for x in t.dropna()}))),
            iban=("iban", lambda t: ", ".join(sorted({maschera(x) for x in t.dropna()}))),
        )
        .reset_index()
        .sort_values("sinistri", ascending=False)
    )
    st.dataframe(persone, hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown("**Telefoni condivisi**")
    tel = coinv.groupby("telefono")["id_sinistro"].nunique().sort_values(ascending=False)
    c1.dataframe(tel[tel > 1].rename("sinistri").rename_axis("telefono").reset_index()
                 .assign(telefono=lambda d: d["telefono"].map(maschera)), hide_index=True, width="stretch")
    c2.markdown("**IBAN condivisi**")
    ib = coinv.groupby("iban")["id_sinistro"].nunique().sort_values(ascending=False)
    c2.dataframe(ib[ib > 1].rename("sinistri").rename_axis("iban").reset_index()
                 .assign(iban=lambda d: d["iban"].map(maschera)), hide_index=True, width="stretch")

with tab_decisione:
    storico = lista_decisioni(selezionato)
    with st.form(f"form_dec_{selezionato}", clear_on_submit=True):
        st.markdown("Registra la tua decisione. Viene salvata nello storico e, se l'esito è definitivo, usata per il riaddestramento.")
        c1, c2, c3 = st.columns(3)
        liquidatore = c1.text_input("ID liquidatore", value=st.session_state.get("id_liquidatore", "LQ-001"))
        decisione = c2.selectbox("Decisione", list(DECISIONI), format_func=DECISIONI.get)
        esito = c3.selectbox("Esito", list(ESITI), format_func=ESITI.get)
        note = st.text_area("Note", placeholder="Es. verificati IBAN condivisi, richiesta documentazione all'officina…")
        if st.form_submit_button("💾 Salva decisione", type="primary"):
            if not liquidatore.strip():
                st.error("Inserisci l'ID del liquidatore.")
            else:
                st.session_state["id_liquidatore"] = liquidatore.strip()
                salva_decisione(f"alert-{selezionato}", str(selezionato), liquidatore.strip(), decisione, esito, note)
                st.toast(f"Decisione registrata per il gruppo {selezionato}", icon="✅")
                st.rerun()
    st.markdown("#### Storico del gruppo")
    if storico:
        st.dataframe(pd.DataFrame(storico), hide_index=True, width="stretch")
    else:
        st.caption("Nessuna decisione registrata per questo gruppo.")
