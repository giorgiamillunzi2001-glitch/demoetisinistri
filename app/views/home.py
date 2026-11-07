from __future__ import annotations

import streamlit as st

from common import ICONA_FASCIA, chip_fascia, euro, pipeline, vai_a_gruppo
from retisinistri.decisions import lista_decisioni

p = pipeline()
sinistri = p["sinistri"]
alerts = sorted(p["alerts"], key=lambda a: a["score_rete"], reverse=True)

st.markdown(
    """
    <div class="rs-hero">
      <h1>Benvenuto in RetiSinistri</h1>
      <p>Individua le frodi organizzate collegando sinistri, persone, IBAN e telefoni.
      Il sistema segnala i gruppi sospetti, spiega il perché e lascia la decisione al liquidatore.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

# --- KPI principali -------------------------------------------------------
gruppi = {g for g in p["communities"].values() if g != -1}
importo_rischio = sum(a["feature_gruppo"].get("importo_totale", 0) for a in alerts)
decisioni = lista_decisioni()
gestiti = {d["id_gruppo"] for d in decisioni}

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Sinistri analizzati", f"{len(sinistri):,}".replace(",", "."))
c2.metric("Gruppi collegati", len(gruppi), help="Community con almeno 3 sinistri legati da persone, IBAN o telefoni")
c3.metric("Alert di rete", len(alerts), help="Gruppi con score di rete in fascia media o alta")
c4.metric("Importo a rischio", euro(importo_rischio), help="Somma degli importi richiesti nei gruppi in alert")
c5.metric("Alert da lavorare", len([a for a in alerts if a["id_gruppo"] not in gestiti]))

st.divider()

# --- Priorità del giorno + azioni rapide ----------------------------------
sx, dx = st.columns([3, 2], gap="large")
with sx:
    st.subheader("🚨 Priorità del giorno")
    if not alerts:
        st.success("Nessun gruppo sospetto rilevato.")
    for a in alerts[:5]:
        f = a["feature_gruppo"]
        with st.container(border=True):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                stato = "✅ gestito" if a["id_gruppo"] in gestiti else "🕒 da lavorare"
                st.markdown(
                    f"**Gruppo {a['id_gruppo']}** &nbsp; {chip_fascia(a['fascia'])} &nbsp; "
                    f"score **{a['score_rete']}**/100 · {stato}",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"{int(f['n_sinistri'])} sinistri · {int(f['n_persone'])} persone · "
                    f"{euro(f['importo_totale'])} richiesti · " + " · ".join(a["reason_codes"])
                )
            with col_b:
                if st.button("Apri", key=f"home_open_{a['id_gruppo']}", width="stretch", type="primary"):
                    vai_a_gruppo(a["id_gruppo"])

with dx:
    st.subheader("⚡ Azioni rapide")
    st.page_link("views/alert.py", label="Lavora la coda alert", icon="🚨")
    st.page_link("views/valuta.py", label="Valuta una nuova pratica", icon="➕")
    st.page_link("views/rete.py", label="Esplora la rete dei collegamenti", icon="🕸️")
    st.page_link("views/sinistri.py", label="Cerca un sinistro", icon="📋")
    st.page_link("views/confronto.py", label="Confronta regole AS-IS e modello", icon="📊")

    st.subheader("🕒 Ultime decisioni")
    if decisioni:
        for d in decisioni[:4]:
            st.caption(f"{d['timestamp']} · Gruppo {d['id_gruppo']} · **{d['decisione']}** → {d['esito_finale']} ({d['id_liquidatore']})")
    else:
        st.caption("Nessuna decisione ancora registrata.")

st.divider()

# --- Come funziona --------------------------------------------------------
st.subheader("Come funziona")
passi = [
    ("1️⃣", "Collega", "Sinistri, persone, IBAN e telefoni diventano un grafo."),
    ("2️⃣", "Raggruppa", "La community detection trova gruppi di sinistri legati da entità forti."),
    ("3️⃣", "Valuta", "Un modello spiegabile assegna uno score di rete 0-100 e i reason code."),
    ("4️⃣", "Decidi", "Il liquidatore approfondisce, decide e l'esito alimenta il riaddestramento."),
]
cols = st.columns(4)
for col, (icona, titolo, testo) in zip(cols, passi):
    with col.container(border=True):
        st.markdown(f"### {icona} {titolo}")
        st.caption(testo)

st.info(
    "ℹ️ Tutti i dati sono **sintetici**. Lo score è un indicatore di sospetto, non una prova: "
    "la decisione finale spetta sempre al liquidatore.",
)
st.caption(f"Legenda fasce: {ICONA_FASCIA['alta']} alta · {ICONA_FASCIA['media']} media · {ICONA_FASCIA['bassa']} bassa")
