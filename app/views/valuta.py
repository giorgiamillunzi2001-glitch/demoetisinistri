from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from common import LIVELLO, codici_gruppo, euro, figura_grafo, maschera, pipeline, sottografo_gruppo, vai_a_gruppo
from retisinistri.score_pratica import calcola_score_pratica
from retisinistri.scoring import assegna_fascia

p = pipeline()
cfg = p["config"]
G = p["grafo"]
sinistri = p["sinistri"]
coinv = p["coinvolgimenti"]
alerts = {a["id_gruppo"]: a for a in p["alerts"]}
gruppo_di = sinistri.set_index("id_sinistro")["id_gruppo"]
codici = codici_gruppo(p)
soglia_regole = float(cfg.get("asis", {}).get("threshold", 50))
soglia_media = cfg.get("scoring", {}).get("soglia_media", 40)
soglia_alta = cfg.get("scoring", {}).get("soglia_alta", 70)

st.title("Nuova denuncia")

PERSONE_VUOTE = pd.DataFrame([
    {"id_persona": "", "ruolo": "assicurato", "telefono": ""},
    {"id_persona": "", "ruolo": "controparte", "telefono": ""},
])


def _esempio(sospetto: bool) -> None:
    if sospetto:
        # Sinistro dall'aspetto normale (0 punti per le regole attuali) ma con telefono e IBAN
        # già usati dal gruppo più rischioso: lo intercetta solo l'analisi di rete.
        top = max(p["alerts"], key=lambda a: a["score_rete"]) if p["alerts"] else None
        ids = sinistri[sinistri["id_gruppo"] == (top["id_gruppo"] if top else "")]["id_sinistro"]
        rif = coinv[coinv["id_sinistro"].isin(ids)]
        iban_top = rif["iban"].dropna().astype(str).value_counts()
        tel_top = rif["telefono"].dropna().astype(str).value_counts()
        st.session_state["v_iban"] = iban_top.index[0] if not iban_top.empty else ""
        st.session_state["v_persone"] = pd.DataFrame([
            {"id_persona": "", "ruolo": "assicurato", "telefono": tel_top.index[0] if not tel_top.empty else ""},
            {"id_persona": "", "ruolo": "controparte", "telefono": "3339876543"},
        ])
        st.session_state.update(v_importo=2400.0, v_giorni=400, v_notte=False, v_verbale=True, v_testimone=False)
    else:
        st.session_state["v_iban"] = "IT1234567890123"
        st.session_state["v_persone"] = PERSONE_VUOTE.assign(telefono=["3330000001", "3330000002"])
        st.session_state.update(v_importo=1800.0, v_giorni=240, v_notte=False, v_verbale=True, v_testimone=False)
    st.session_state.pop("v_risultato", None)
    st.session_state["v_editor_ver"] = st.session_state.get("v_editor_ver", 0) + 1


for chiave, default in {"v_importo": 2500.0, "v_giorni": 120, "v_notte": False, "v_verbale": True,
                        "v_testimone": False, "v_iban": ""}.items():
    st.session_state.setdefault(chiave, default)

b1, b2, _ = st.columns([1, 1, 3])
b1.button("Esempio sospetto", on_click=_esempio, args=(True,), width="stretch")
b2.button("Esempio regolare", on_click=_esempio, args=(False,), width="stretch")

with st.form("nuova_pratica"):
    c1, c2, c3 = st.columns(3)
    id_sin = c1.text_input("Numero sinistro", value=f"NEW-{dt.datetime.now():%H%M%S}")
    data = c2.date_input("Data sinistro", value=dt.date.today(), format="DD/MM/YYYY")
    importo = c3.number_input("Importo richiesto (€)", min_value=0.0, step=100.0, format="%.0f", key="v_importo")
    c4, c5, c6, c7 = st.columns(4)
    giorni = c4.number_input("Giorni dalla stipula", min_value=0, step=1, key="v_giorni")
    notte = c5.checkbox("Orario notturno", key="v_notte")
    verbale = c6.checkbox("Verbale autorità", key="v_verbale")
    testimone = c7.checkbox("Presenza testimone", key="v_testimone")
    c8, c9, c10 = st.columns(3)
    officina = c8.text_input("Officina", value="OFF_0001")
    avvocato = c9.text_input("Avvocato (facoltativo)", value="")
    iban = c10.text_input("IBAN liquidazione", key="v_iban")

    st.markdown("**Persone coinvolte**")
    persone = st.data_editor(
        st.session_state.get("v_persone", PERSONE_VUOTE),
        num_rows="dynamic", width="stretch", key=f"v_editor_{st.session_state.get('v_editor_ver', 0)}",
        column_config={
            "id_persona": st.column_config.TextColumn("Codice persona (se noto)"),
            "ruolo": st.column_config.SelectboxColumn("Ruolo", options=["assicurato", "controparte", "conducente", "testimone"], required=True),
            "telefono": st.column_config.TextColumn("Telefono"),
        },
    )
    inviato = st.form_submit_button("Valuta", type="primary")

AZIONE_ANTIFRODE = "Proposta: approfondimento dell'ufficio antifrode · decide il liquidatore"
AZIONE_VERIFICA = "Proposta: verifica documentale"
AZIONE_ORDINARIA = "Liquidazione ordinaria"
AIUTO_SCORE_STIMATO = (
    "Se la denuncia condivide IBAN, telefono o persone con un gruppo segnalato, eredita lo score di rete "
    "di quel gruppo (il più alto, se i gruppi sono più di uno). Se è collegata solo a sinistri non segnalati "
    "vale 15 punti per ogni sinistro collegato, fino a un massimo di 60. Senza collegamenti vale 0."
)


def _valuta(id_sin, data, importo, giorni, notte, verbale, testimone, iban, persone) -> dict:
    """Calcola la valutazione e la restituisce come dizionario (salvato poi in session_state)."""
    pratica = {
        "importo_richiesto": importo or 0, "giorni_da_inizio_polizza": giorni or 0, "orario_notturno": notte,
        "verbale_autorita": verbale, "testimone": testimone,
    }
    punteggio = calcola_score_pratica(pratica, cfg)
    motivi_regole = []
    if (importo or 0) > 5000:
        motivi_regole.append("importo superiore a 5.000 €")
    if (giorni or 0) < 30:
        motivi_regole.append("polizza stipulata da meno di 30 giorni")
    if notte:
        motivi_regole.append("sinistro in orario notturno")
    if not verbale:
        motivi_regole.append("assenza di verbale delle autorità")
    if testimone:
        motivi_regole.append("presenza di testimone")

    # Ricerca di persone, IBAN e telefoni già presenti in archivio
    chiavi = []
    if iban.strip():
        chiavi.append(("iban", iban.strip()))
    for _, r in persone.iterrows():
        if str(r.get("id_persona") or "").strip():
            chiavi.append(("persona", str(r["id_persona"]).strip()))
        if str(r.get("telefono") or "").strip():
            chiavi.append(("telefono", str(r["telefono"]).strip()))

    collegati: dict[str, list[str]] = {}
    for tipo, val in chiavi:
        nodo = f"{tipo}:{val}"
        if nodo in G:
            for v in G.neighbors(nodo):
                if v.startswith("sinistro:"):
                    nome = {"iban": "IBAN", "telefono": "telefono", "persona": "persona"}[tipo]
                    collegati.setdefault(v.split(":", 1)[1], []).append(f"{nome} {val if tipo == 'persona' else maschera(val)}")

    gruppi_alert = sorted({gruppo_di[s] for s in collegati} & set(alerts), key=lambda g: codici.get(g, g))
    motivi_rete = []
    if gruppi_alert:
        score_rete = max(alerts[g]["score_rete"] for g in gruppi_alert)
        motivi_rete = [f"collegata al gruppo {codici[g]} (score di rete {alerts[g]['score_rete']})" for g in gruppi_alert]
    elif collegati:
        score_rete = min(60, 15 * len(collegati))
        motivi_rete = [f"condivide dati con {len(collegati)} sinistri in archivio"]
    else:
        score_rete = 0
    fascia = assegna_fascia(score_rete, soglia_media, soglia_alta)

    if fascia == "alta" or punteggio >= soglia_regole:
        azione = AZIONE_ANTIFRODE
    elif fascia == "media":
        azione = AZIONE_VERIFICA
    else:
        azione = AZIONE_ORDINARIA

    if gruppi_alert:
        esito = f"Collegato al gruppo {', '.join(codici[g] for g in gruppi_alert)} · livello {LIVELLO[fascia]}"
    elif collegati:
        esito = f"Collegato a {len(collegati)} sinistri in archivio · livello {LIVELLO[fascia]}"
    elif azione == AZIONE_ORDINARIA:
        esito = "Nessun collegamento sospetto · liquidazione ordinaria"
    else:
        esito = "Nessun collegamento sospetto"

    return {
        "id_sin": id_sin, "data": data, "importo": importo or 0, "punteggio": punteggio, "score_rete": score_rete,
        "fascia": fascia, "azione": azione, "esito": esito, "collegati": collegati, "gruppi_alert": gruppi_alert,
        "motivi_regole": motivi_regole, "motivi_rete": motivi_rete,
    }


if inviato:
    st.session_state["v_risultato"] = _valuta(id_sin, data, importo, giorni, notte, verbale, testimone, iban, persone)
    r = st.session_state["v_risultato"]
    st.session_state.setdefault("pratiche_valutate", []).insert(0, {
        "Sinistro": r["id_sin"], "Data sinistro": f"{r['data']:%d/%m/%Y}", "Importo": euro(r["importo"]),
        "Punteggio regole attuali": round(r["punteggio"]), "Score di rete": r["score_rete"], "Livello": LIVELLO[r["fascia"]],
        "Sinistri collegati": len(r["collegati"]), "Valutata alle": dt.datetime.now().strftime("%H:%M"),
    })

# Il risultato si mostra dalla session_state: resta visibile (e i pulsanti funzionano) anche dopo un rerun
r = st.session_state.get("v_risultato")
if r:
    st.divider()
    st.subheader(r["esito"])
    st.caption(f"Sinistro {r['id_sin']} del {r['data']:%d/%m/%Y} · {euro(r['importo'])}")
    if r["azione"] != AZIONE_ORDINARIA or r["collegati"]:
        st.markdown(f"**{r['azione']}**")

    k1, k2, k3 = st.columns(3)
    k1.metric("Punteggio regole attuali", f"{r['punteggio']:.0f}/100",
              help=f"Le regole attuali segnalano la pratica da {soglia_regole:.0f} punti in su")
    k2.metric("Score di rete stimato (dal gruppo collegato)", f"{r['score_rete']}/100", help=AIUTO_SCORE_STIMATO)
    k3.metric("Sinistri collegati in archivio", len(r["collegati"]))

    m1, m2 = st.columns(2)
    with m1:
        st.markdown("**Motivazioni regole attuali**")
        st.markdown("\n".join(f"- {m}" for m in r["motivi_regole"]) or "Nessuna regola attivata.")
    with m2:
        st.markdown("**Motivazioni di rete**")
        st.markdown("\n".join(f"- {m}" for m in r["motivi_rete"]) or "Nessun collegamento con sinistri in archivio.")

    if r["collegati"]:
        st.markdown("**Collegamenti trovati**")
        st.dataframe(
            pd.DataFrame([{"Sinistro": s, "Tramite": ", ".join(sorted(set(v))),
                           "Gruppo": codici.get(gruppo_di.get(s, "-1"), "")}
                          for s, v in r["collegati"].items()]),
            hide_index=True, width="stretch",
        )
        st.plotly_chart(figura_grafo(sottografo_gruppo(p, list(r["collegati"]), includi_deboli=False), altezza=400),
                        width="stretch")
        for g in r["gruppi_alert"]:
            if g in codici and st.button(f"Apri {codici[g]}", key=f"v_open_{g}", type="primary"):
                vai_a_gruppo(g)

if st.session_state.get("pratiche_valutate"):
    st.divider()
    st.markdown("**Denunce valutate in questa sessione**")
    storico = pd.DataFrame(st.session_state["pratiche_valutate"])
    st.dataframe(storico, hide_index=True, width="stretch")
    st.download_button("Scarica CSV", storico.to_csv(index=False).encode("utf-8"), "denunce_valutate.csv", "text/csv")
