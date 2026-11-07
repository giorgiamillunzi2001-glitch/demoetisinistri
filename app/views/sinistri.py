from __future__ import annotations

import streamlit as st

from common import ETICHETTA_FASCIA, ICONA_FASCIA, chip_fascia, euro, figura_grafo, maschera, pipeline, sottografo_gruppo, vai_a_gruppo

p = pipeline()
sinistri = p["sinistri"].copy()
coinv = p["coinvolgimenti"]

st.title("📋 Sinistri")
st.caption("Cerca e filtra i sinistri; seleziona una riga per vedere la scheda completa e i collegamenti.")

# --- Filtri ---------------------------------------------------------------
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    testo = c1.text_input("🔎 Cerca", placeholder="ID sinistro, persona, officina, avvocato, IBAN, telefono…")
    fasce = c2.multiselect("Fascia di rete", ["alta", "media", "bassa"], default=[],
                           format_func=lambda x: f"{ICONA_FASCIA[x]} {ETICHETTA_FASCIA[x]}")
    solo_asis = c3.selectbox("Alert AS-IS", ["Tutti", "Solo segnalati", "Solo non segnalati"])
    imp_max = float(sinistri["importo_richiesto"].max())
    importo = c4.slider("Importo (€)", 0.0, imp_max, (0.0, imp_max), step=100.0)

df = sinistri
if testo:
    t = testo.strip().lower()
    match_coinv = coinv[
        coinv[["id_persona", "telefono", "iban", "email", "targa"]].astype(str).apply(lambda col: col.str.lower().str.contains(t, regex=False)).any(axis=1)
    ]["id_sinistro"]
    mask = df[["id_sinistro", "id_officina", "id_avvocato", "id_perito", "iban_liquidazione"]].astype(str).apply(
        lambda col: col.str.lower().str.contains(t, regex=False)).any(axis=1)
    df = df[mask | df["id_sinistro"].isin(match_coinv)]
if fasce:
    df = df[df["fascia"].isin(fasce)]
if solo_asis == "Solo segnalati":
    df = df[df["alert_asis"]]
elif solo_asis == "Solo non segnalati":
    df = df[~df["alert_asis"]]
df = df[(df["importo_richiesto"] >= importo[0]) & (df["importo_richiesto"] <= importo[1])]

vista = df[["id_sinistro", "data_sinistro", "importo_richiesto", "score_pratica", "alert_asis", "score_rete", "fascia", "id_gruppo", "id_officina"]].copy()
vista["fascia"] = vista["fascia"].map(lambda x: f"{ICONA_FASCIA[x]} {ETICHETTA_FASCIA[x]}")
vista["id_gruppo"] = vista["id_gruppo"].replace("-1", "—")
vista = vista.sort_values(["score_rete", "score_pratica"], ascending=False).reset_index(drop=True)

st.caption(f"{len(vista)} sinistri trovati su {len(sinistri)}")
ev = st.dataframe(
    vista, hide_index=True, width="stretch", height=320, on_select="rerun", selection_mode="single-row",
    column_config={
        "id_sinistro": "Sinistro", "data_sinistro": "Data",
        "importo_richiesto": st.column_config.NumberColumn("Importo", format="€ %.2f"),
        "score_pratica": st.column_config.ProgressColumn("Score AS-IS", min_value=0, max_value=100, format="%d"),
        "alert_asis": st.column_config.CheckboxColumn("Alert AS-IS"),
        "score_rete": st.column_config.ProgressColumn("Score rete", min_value=0, max_value=100, format="%d"),
        "fascia": "Fascia", "id_gruppo": "Gruppo", "id_officina": "Officina",
    },
)

st.download_button("⬇️ Esporta elenco (CSV)", vista.to_csv(index=False).encode("utf-8"), "sinistri_filtrati.csv", "text/csv")

sel = None
if ev.selection.rows:
    sel = vista.iloc[ev.selection.rows[0]]["id_sinistro"]
elif st.session_state.get("sinistro_selezionato") in set(sinistri["id_sinistro"]):
    sel = st.session_state["sinistro_selezionato"]
if sel is None:
    st.info("👆 Seleziona un sinistro dalla tabella per aprire la scheda.")
    st.stop()
st.session_state["sinistro_selezionato"] = sel

# --- Scheda sinistro ------------------------------------------------------
s = sinistri[sinistri["id_sinistro"] == sel].iloc[0]
st.divider()
st.markdown(f"## Sinistro {sel} &nbsp; {chip_fascia(s['fascia'])}", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Importo richiesto", euro(s["importo_richiesto"]))
m2.metric("Score AS-IS", f"{s['score_pratica']:.0f}/100", "segnalato" if s["alert_asis"] else "non segnalato",
          delta_color="inverse" if s["alert_asis"] else "off")
m3.metric("Score di rete", f"{s['score_rete']}/100")
m4.metric("Giorni da inizio polizza", int(s["giorni_da_inizio_polizza"]))

sx, dx = st.columns([2, 3], gap="large")
with sx:
    st.markdown("#### Dati della pratica")
    dati = {
        "Data sinistro": s["data_sinistro"], "Data denuncia": s["data_denuncia"], "Provincia": s["provincia"],
        "Orario notturno": "Sì" if s["orario_notturno"] else "No",
        "Verbale autorità": "Sì" if s["verbale_autorita"] else "No",
        "CAI firmato da entrambi": "Sì" if s["cai_firmato_entrambi"] else "No",
        "Officina": s["id_officina"], "Perito": s["id_perito"], "Avvocato": s["id_avvocato"],
        "IBAN liquidazione": maschera(s["iban_liquidazione"]),
    }
    for k, v in dati.items():
        st.markdown(f"**{k}:** {v}")

    st.markdown("#### Persone coinvolte")
    pers = coinv[coinv["id_sinistro"] == sel][["id_persona", "ruolo", "telefono", "targa"]].copy()
    pers["telefono"] = pers["telefono"].map(maschera)
    st.dataframe(pers, hide_index=True, width="stretch")

    if s["id_gruppo"] != "-1":
        st.warning(f"Questo sinistro fa parte del **gruppo {s['id_gruppo']}**.")
        if st.button(f"🚨 Apri l'alert del gruppo {s['id_gruppo']}", type="primary"):
            vai_a_gruppo(s["id_gruppo"])
    else:
        st.success("Nessun gruppo sospetto collegato a questo sinistro.")

with dx:
    st.markdown("#### Collegamenti diretti")
    H = sottografo_gruppo(p, [sel], includi_deboli=True)
    # aggiunge i sinistri che condividono entità forti
    G = p["grafo"]
    altri = set()
    for n in list(H.nodes):
        if G.nodes[n].get("tipo") in {"persona", "iban", "telefono"}:
            altri |= {v.split(":", 1)[1] for v in G.neighbors(n) if v.startswith("sinistro:")}
    altri.discard(sel)
    H = sottografo_gruppo(p, [sel, *sorted(altri)], includi_deboli=False) if altri else H
    st.plotly_chart(figura_grafo(H, altezza=430, evidenzia={f"sinistro:{sel}"}), width="stretch")
    if altri:
        st.caption(f"Collegato tramite persone/IBAN/telefoni a {len(altri)} altri sinistri: {', '.join(sorted(altri)[:12])}{'…' if len(altri) > 12 else ''}")
    else:
        st.caption("Nessun altro sinistro condivide persone, IBAN o telefoni con questa pratica.")
