from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from common import chip_fascia, figura_grafo, maschera, pipeline, sottografo_gruppo, vai_a_gruppo
from retisinistri.score_pratica import calcola_score_pratica
from retisinistri.scoring import assegna_fascia

p = pipeline()
cfg = p["config"]
G = p["grafo"]
sinistri = p["sinistri"]
coinv = p["coinvolgimenti"]
alerts = {a["id_gruppo"]: a for a in p["alerts"]}
soglia_asis = float(cfg.get("asis", {}).get("threshold", 50))
soglia_media = cfg.get("scoring", {}).get("soglia_media", 40)
soglia_alta = cfg.get("scoring", {}).get("soglia_alta", 70)

st.title("➕ Valuta nuova pratica")
st.caption("Inserisci i dati di un sinistro appena denunciato: il sistema calcola lo score AS-IS e verifica se è collegato a gruppi sospetti già noti.")

PERSONE_VUOTE = pd.DataFrame([
    {"id_persona": "", "ruolo": "assicurato", "telefono": ""},
    {"id_persona": "", "ruolo": "controparte", "telefono": ""},
])


def _esempio(sospetto: bool) -> None:
    if sospetto:
        top = max(p["alerts"], key=lambda a: a["score_rete"]) if p["alerts"] else None
        ids = sinistri[sinistri["id_gruppo"] == (top["id_gruppo"] if top else "")]["id_sinistro"]
        rif = coinv[coinv["id_sinistro"].isin(ids)]
        st.session_state["v_iban"] = str(rif["iban"].dropna().iloc[0]) if not rif.empty else ""
        st.session_state["v_persone"] = pd.DataFrame([
            {"id_persona": "", "ruolo": "assicurato", "telefono": str(rif["telefono"].iloc[0]) if not rif.empty else ""},
            {"id_persona": str(rif["id_persona"].iloc[1]) if len(rif) > 1 else "", "ruolo": "testimone", "telefono": ""},
        ])
        st.session_state.update(v_importo=2900.0, v_giorni=20, v_notte=True, v_verbale=False, v_testimone=True)
    else:
        st.session_state["v_iban"] = "IT1234567890123"
        st.session_state["v_persone"] = PERSONE_VUOTE.assign(telefono=["3330000001", "3330000002"])
        st.session_state.update(v_importo=1800.0, v_giorni=240, v_notte=False, v_verbale=True, v_testimone=False)
    st.session_state["v_editor_ver"] = st.session_state.get("v_editor_ver", 0) + 1


for chiave, default in {"v_importo": 2500.0, "v_giorni": 120, "v_notte": False, "v_verbale": True,
                        "v_testimone": False, "v_iban": ""}.items():
    st.session_state.setdefault(chiave, default)

b1, b2, _ = st.columns([1, 1, 3])
b1.button("🧪 Carica esempio sospetto", on_click=_esempio, args=(True,))
b2.button("🧪 Carica esempio regolare", on_click=_esempio, args=(False,))

with st.form("nuova_pratica"):
    st.markdown("#### Dati del sinistro")
    c1, c2, c3 = st.columns(3)
    id_sin = c1.text_input("ID sinistro", value=f"NEW-{dt.datetime.now():%H%M%S}")
    data = c2.date_input("Data sinistro", value=dt.date.today(), format="DD/MM/YYYY")
    importo = c3.number_input("Importo richiesto (€)", min_value=0.0, step=100.0, key="v_importo")
    c4, c5, c6, c7 = st.columns(4)
    giorni = c4.number_input("Giorni da inizio polizza", min_value=0, step=1, key="v_giorni")
    notte = c5.checkbox("Orario notturno", key="v_notte")
    verbale = c6.checkbox("Verbale autorità", key="v_verbale")
    testimone = c7.checkbox("Presenza testimone", key="v_testimone")
    c8, c9, c10 = st.columns(3)
    officina = c8.text_input("Officina", value="OFF_0001")
    avvocato = c9.text_input("Avvocato (opzionale)", value="")
    iban = c10.text_input("IBAN liquidazione", key="v_iban")

    st.markdown("#### Persone coinvolte")
    persone = st.data_editor(
        st.session_state.get("v_persone", PERSONE_VUOTE),
        num_rows="dynamic", width="stretch", key=f"v_editor_{st.session_state.get('v_editor_ver', 0)}",
        column_config={
            "id_persona": st.column_config.TextColumn("ID persona (se nota)"),
            "ruolo": st.column_config.SelectboxColumn("Ruolo", options=["assicurato", "controparte", "conducente", "testimone"], required=True),
            "telefono": st.column_config.TextColumn("Telefono"),
        },
    )
    inviato = st.form_submit_button("🔍 Valuta pratica", type="primary")

if inviato:
    pratica = {
        "importo_richiesto": importo or 0, "giorni_da_inizio_polizza": giorni or 0, "orario_notturno": notte,
        "verbale_autorita": verbale, "testimone": testimone,
    }
    score_asis = calcola_score_pratica(pratica, cfg)
    motivi_asis = []
    if (importo or 0) > 5000:
        motivi_asis.append("importo superiore a 5.000 €")
    if (giorni or 0) < 30:
        motivi_asis.append("polizza attivata da meno di 30 giorni")
    if notte:
        motivi_asis.append("sinistro in orario notturno")
    if not verbale:
        motivi_asis.append("assenza di verbale delle autorità")
    if testimone:
        motivi_asis.append("presenza di testimone")

    # Ricerca di entità forti già presenti nel grafo
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
                    collegati.setdefault(v.split(":", 1)[1], []).append(f"{tipo} {maschera(val) if tipo != 'persona' else val}")

    gruppi_coll = sorted({sinistri.set_index("id_sinistro").loc[s, "id_gruppo"] for s in collegati} - {"-1"})
    gruppi_alert = [g for g in gruppi_coll if g in alerts]
    motivi_rete = []
    if gruppi_alert:
        score_rete = max(alerts[g]["score_rete"] for g in gruppi_alert)
        for g in gruppi_alert:
            motivi_rete.append(f"collegata al gruppo sospetto {g} (score {alerts[g]['score_rete']})")
    elif collegati:
        score_rete = min(60, 15 * len(collegati))
        motivi_rete.append(f"condivide entità con {len(collegati)} sinistri già in archivio")
    else:
        score_rete = 0
    fascia = assegna_fascia(score_rete, soglia_media, soglia_alta)

    st.divider()
    st.markdown(f"## Esito valutazione · {id_sin} &nbsp; {chip_fascia(fascia)}", unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    k1.metric("Score AS-IS (regole)", f"{score_asis:.0f}/100", "alert" if score_asis >= soglia_asis else "sotto soglia",
              delta_color="inverse" if score_asis >= soglia_asis else "off")
    k2.metric("Score di rete stimato", f"{score_rete}/100")
    k3.metric("Sinistri collegati in archivio", len(collegati))

    if fascia == "alta" or score_asis >= soglia_asis:
        azione = "🔴 **Sospendere la liquidazione automatica** e inviare la pratica all'unità antifrode (SIU)."
    elif fascia == "media":
        azione = "🟠 **Approfondimento documentale** prima della liquidazione."
    else:
        azione = "🟢 **Liquidazione ordinaria** (straight-through processing)."
    st.markdown(f"**Azione suggerita:** {azione}")

    m1, m2 = st.columns(2)
    with m1.container(border=True):
        st.markdown("**Motivazioni regole AS-IS**")
        for m in motivi_asis or ["nessuna regola attivata"]:
            st.markdown(f"- {m}")
    with m2.container(border=True):
        st.markdown("**Motivazioni di rete**")
        for m in motivi_rete or ["nessun collegamento con sinistri noti"]:
            st.markdown(f"- {m}")

    if collegati:
        st.markdown("#### Collegamenti trovati")
        st.dataframe(
            pd.DataFrame([{"Sinistro": s, "Tramite": ", ".join(sorted(set(v))),
                           "Gruppo": sinistri.set_index("id_sinistro").loc[s, "id_gruppo"].replace("-1", "—")}
                          for s, v in collegati.items()]),
            hide_index=True, width="stretch",
        )
        st.plotly_chart(figura_grafo(sottografo_gruppo(p, list(collegati), includi_deboli=False), altezza=420), width="stretch")
        for g in gruppi_alert:
            if st.button(f"🚨 Apri alert gruppo {g}", key=f"v_open_{g}"):
                vai_a_gruppo(g)

    st.session_state.setdefault("pratiche_valutate", []).insert(0, {
        "ID": id_sin, "Data": data.isoformat(), "Importo": importo or 0, "Score AS-IS": round(score_asis),
        "Score rete": score_rete, "Fascia": fascia, "Collegati": len(collegati),
        "Valutata alle": dt.datetime.now().strftime("%H:%M:%S"),
    })

if st.session_state.get("pratiche_valutate"):
    st.divider()
    st.markdown("#### Pratiche valutate in questa sessione")
    storico = pd.DataFrame(st.session_state["pratiche_valutate"])
    st.dataframe(storico, hide_index=True, width="stretch",
                 column_config={"Importo": st.column_config.NumberColumn(format="€ %.2f")})
    st.download_button("⬇️ Scarica (CSV)", storico.to_csv(index=False).encode("utf-8"), "pratiche_valutate.csv", "text/csv")
