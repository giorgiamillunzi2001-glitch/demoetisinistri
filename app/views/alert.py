from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from common import (
    DECISIONI,
    data_it,
    data_ora_it,
    etichetta_livello,
    euro,
    figura_grafo,
    maschera,
    numero,
    percentuale,
    pipeline,
    sottografo_gruppo,
    tabella_alert,
)
from retisinistri.decisions import lista_decisioni, salva_decisione
from retisinistri.explain_llm import spiega_alert

p = pipeline()
alerts = {a["id_gruppo"]: a for a in p["alerts"]}
sinistri = p["sinistri"]

st.title("Alert")

if not alerts:
    st.write("Nessun alert aperto.")
    st.stop()

# --- Filtri ---------------------------------------------------------------
gestiti = {d["id_gruppo"] for d in lista_decisioni()}
chiave_tabella = f"tabella_alert_{st.session_state.get('tabella_alert_ver', 0)}"


def _azzera_selezione_tabella() -> None:
    st.session_state["tabella_alert_ver"] = st.session_state.get("tabella_alert_ver", 0) + 1


def _cerca() -> None:
    """La ricerca sceglie il gruppo solo nel momento in cui viene digitata."""
    codice = st.session_state.get("cerca_sinistro", "").strip().upper()
    st.session_state.pop("esito_ricerca", None)
    if not codice:
        return
    trovato = sinistri[sinistri["id_sinistro"].str.upper() == codice]
    if trovato.empty:
        st.session_state["esito_ricerca"] = ("warning", f"Sinistro {codice} non trovato.")
        return
    g = trovato.iloc[0]["id_gruppo"]
    if g in alerts:
        st.session_state["gruppo_selezionato"] = g
        st.session_state["da_ricerca"] = True
        _azzera_selezione_tabella()
    else:
        st.session_state["esito_ricerca"] = ("info", f"Sinistro {codice} non collegato a gruppi sospetti.")


def _cancella() -> None:
    st.session_state["cerca_sinistro"] = ""
    st.session_state.pop("esito_ricerca", None)


f1, f2, f3, f4 = st.columns([2, 3, 3, 1], vertical_alignment="bottom")
livelli = f1.segmented_control("Livello", ["Alto", "Medio"], selection_mode="multi", default=["Alto", "Medio"],
                               on_change=_azzera_selezione_tabella)
stato = f2.segmented_control("Stato", ["Tutti", "Da lavorare", "Gestiti"], default="Tutti",
                            on_change=_azzera_selezione_tabella)
f3.text_input("Cerca sinistro", placeholder="es. S00012", key="cerca_sinistro", on_change=_cerca)
f4.button("Cancella", on_click=_cancella, width="stretch")

esito = st.session_state.get("esito_ricerca")
if esito:
    (st.warning if esito[0] == "warning" else st.info)(esito[1])

# spazio tra i filtri e la tabella: la barra strumenti della tabella non copre "Cancella"
st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

df = tabella_alert(p, gestiti)
df = df[df["Livello"].isin(livelli or [])]
if stato == "Da lavorare":
    df = df[df["Stato"] == "Da lavorare"]
elif stato == "Gestiti":
    df = df[df["Stato"] == "Gestito"]
df = df.reset_index(drop=True)


def _riga_selezionata() -> None:
    righe = st.session_state[chiave_tabella].selection.rows
    if righe and righe[0] < len(df):
        st.session_state["gruppo_selezionato"] = df.iloc[righe[0]]["Gruppo"]


st.dataframe(
    df,
    hide_index=True,
    width="stretch",
    on_select=_riga_selezionata,
    selection_mode="single-row",
    key=chiave_tabella,
    column_config={"Score di rete": st.column_config.ProgressColumn("Score di rete", min_value=0, max_value=100, format="%d")},
)

selezionato = st.session_state.get("gruppo_selezionato")
da_ricerca = st.session_state.pop("da_ricerca", False)
if selezionato not in alerts or (not da_ricerca and selezionato not in set(df["Gruppo"])):
    # Nessuna scelta valida o gruppo escluso dai filtri: si apre il primo gruppo visibile
    if df.empty:
        st.stop()
    selezionato = df.iloc[0]["Gruppo"]
st.session_state["gruppo_selezionato"] = selezionato

# --- Dettaglio del gruppo ------------------------------------------------
a = alerts[selezionato]
f = a["feature_gruppo"]
ids = sinistri.loc[sinistri["id_gruppo"] == str(selezionato), "id_sinistro"].tolist()
coinv = p["coinvolgimenti"][p["coinvolgimenti"]["id_sinistro"].isin(ids)]

st.divider()
st.markdown(f"<h2 style='margin-bottom:0'>Gruppo {selezionato} &nbsp;{etichetta_livello(a['fascia'])}</h2>", unsafe_allow_html=True)
st.caption(f"{int(f['n_sinistri'])} sinistri · {int(f['n_persone'])} persone · {euro(f['importo_totale'])}")

m1, m2, m3 = st.columns(3)
m1.metric("Score di rete", f"{a['score_rete']}/100")
m2.metric("Punteggio regole attuali (media)", f"{a['score_pratica_medio']:.0f}/100")
m3.metric("Finestra temporale", f"{int(f['finestra_giorni'])} giorni", help="Giorni tra il primo e l'ultimo sinistro del gruppo")

sx, dx = st.columns([2, 3], gap="large")
with sx:
    st.subheader("Motivazioni")
    st.markdown("\n".join(f"- {r}" for r in a["reason_codes"]) or "Nessuna motivazione disponibile.")
    chiave = f"spiegazione_{selezionato}"
    if st.button("Genera spiegazione"):
        with st.spinner("Generazione in corso…"):
            st.session_state[chiave] = spiega_alert(a)
    if chiave in st.session_state:
        with st.container(border=True):
            st.write(st.session_state[chiave])
with dx:
    st.plotly_chart(figura_grafo(sottografo_gruppo(p, ids)), width="stretch")

# --- Decisione ------------------------------------------------------------
st.subheader("Decisione")
note = st.text_input("Note (facoltative)", key=f"note_{selezionato}")
b1, b2, _ = st.columns([1, 1, 2])
scelta = None
if b1.button("Avvia approfondimento", type="primary", width="stretch"):
    scelta = "approfondimento"
if b2.button("Archivia (falso positivo)", width="stretch"):
    scelta = "archiviazione"
if scelta:
    liquidatore = str(st.session_state.get("id_liquidatore", "")).strip()
    if not liquidatore:
        st.warning("Inserisci l'ID liquidatore nella barra laterale.")
    else:
        salva_decisione(f"alert-{selezionato}", str(selezionato), liquidatore, scelta, "in_corso", note)
        st.session_state["ultimo_salvataggio"] = (
            selezionato,
            f"Decisione registrata: {DECISIONI[scelta]} · {dt.datetime.now():%d/%m/%Y %H:%M} · {liquidatore}",
        )
        st.rerun()

salvato = st.session_state.get("ultimo_salvataggio")
if salvato and salvato[0] == selezionato:
    st.success(salvato[1])

storico = lista_decisioni(selezionato)
if storico:
    st.caption("Decisioni precedenti  \n" + "  \n".join(
        f"{data_ora_it(d['timestamp'])} · {DECISIONI.get(d['decisione'], d['decisione'])} · {d['id_liquidatore']}"
        + (f" · {d['note']}" if d["note"] else "")
        for d in storico[:5]
    ))

# --- Approfondimenti ------------------------------------------------------
with st.expander("Sinistri del gruppo"):
    tab = sinistri[sinistri["id_sinistro"].isin(ids)].sort_values("data_sinistro")
    vista = pd.DataFrame({
        "Sinistro": tab["id_sinistro"],
        "Data sinistro": tab["data_sinistro"].map(data_it),
        "Data denuncia": tab["data_denuncia"].map(data_it),
        "Importo": tab["importo_richiesto"].map(euro),
        "Giorni dalla stipula": tab["giorni_da_inizio_polizza"],
        "Notturno": tab["orario_notturno"].map({True: "Sì", False: "No"}),
        "Verbale autorità": tab["verbale_autorita"].map({True: "Sì", False: "No"}),
        "Officina": tab["id_officina"],
        "Avvocato": tab["id_avvocato"],
        "Punteggio regole attuali": tab["score_pratica"].astype(int),
    })
    st.dataframe(vista, hide_index=True, width="stretch")
    st.caption(f"Le regole attuali segnalano {int(tab['alert_asis'].sum())} sinistri su {len(tab)}.")

with st.expander("Persone e contatti"):
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
        .rename(columns={"id_persona": "Persona", "ruoli": "Ruoli", "sinistri": "Sinistri",
                         "telefoni": "Telefoni", "iban": "IBAN"})
    )
    st.dataframe(persone, hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    tel = coinv.groupby("telefono")["id_sinistro"].nunique()
    tel = tel[tel > 1].sort_values(ascending=False)
    c1.markdown("**Telefoni condivisi**")
    c1.dataframe(pd.DataFrame({"Telefono": tel.index.map(maschera), "Sinistri": tel.values}), hide_index=True, width="stretch")
    ib = coinv.groupby("iban")["id_sinistro"].nunique()
    ib = ib[ib > 1].sort_values(ascending=False)
    c2.markdown("**IBAN condivisi**")
    c2.dataframe(pd.DataFrame({"IBAN": ib.index.map(maschera), "Sinistri": ib.values}), hide_index=True, width="stretch")

with st.expander("Indicatori tecnici"):
    ind = pd.DataFrame(
        [
            ("Finestra temporale", f"{int(f['finestra_giorni'])} giorni"),
            ("Sinistri per IBAN", numero(f["sinistri_per_iban"], 1)),
            ("Sinistri per telefono", numero(f["sinistri_per_telefono"], 1)),
            ("Quota officina più frequente", percentuale(f["quota_officina_top"])),
            ("Quota avvocato più frequente", percentuale(f["quota_avvocato_top"])),
            ("Persone con più ruoli", str(int(f["persone_multi_ruolo"]))),
            ("Densità della rete", numero(f["densita"], 2)),
            ("Ricorrenze testimone", str(int(f["testimone_ricorrente_max"]))),
            ("Indice di anomalia", numero(a["anomaly_score"], 2)),
        ],
        columns=["Indicatore", "Valore"],
    )
    st.dataframe(ind, hide_index=True, width="stretch")
