from __future__ import annotations

import pandas as pd
import streamlit as st

from common import DECISIONI, ESITI, pipeline, vai_a_gruppo
from retisinistri.decisions import dataset_riaddestramento, lista_decisioni

p = pipeline()
alerts = {a["id_gruppo"]: a for a in p["alerts"]}

st.title("⚖️ Decisioni")
st.caption("Storico delle decisioni dei liquidatori (human-in-the-loop). Gli esiti definitivi alimentano il riaddestramento del modello.")

storico = pd.DataFrame(lista_decisioni())
if storico.empty:
    st.info("Nessuna decisione registrata. Apri un alert dalla **Coda alert** e registra la tua decisione nella scheda *Decisione*.")
    st.page_link("views/alert.py", label="Vai alla coda alert", icon="🚨")
    st.stop()

ultime = storico.drop_duplicates("id_gruppo", keep="first")
c = st.columns(4)
c[0].metric("Decisioni registrate", len(storico))
c[1].metric("Alert gestiti", f"{ultime['id_gruppo'].isin(alerts).sum()} / {len(alerts)}")
c[2].metric("Frodi confermate", int((ultime["esito_finale"] == "frode_confermata").sum()))
override = ultime[ultime["id_gruppo"].isin(alerts) & (ultime["decisione"].isin(["liquidazione", "archiviazione"]))]
c[3].metric("Override del modello", f"{len(override) / max(1, len(ultime)):.0%}",
            help="Quota di gruppi segnalati dal modello che il liquidatore ha deciso di liquidare o archiviare")

f1, f2, f3 = st.columns(3)
liq = f1.multiselect("Liquidatore", sorted(storico["id_liquidatore"].unique()))
dec = f2.multiselect("Decisione", list(DECISIONI), format_func=DECISIONI.get)
esi = f3.multiselect("Esito", list(ESITI), format_func=ESITI.get)
vista = storico
if liq:
    vista = vista[vista["id_liquidatore"].isin(liq)]
if dec:
    vista = vista[vista["decisione"].isin(dec)]
if esi:
    vista = vista[vista["esito_finale"].isin(esi)]
vista = vista.assign(
    decisione=vista["decisione"].map(lambda x: DECISIONI.get(x, x)),
    esito_finale=vista["esito_finale"].map(lambda x: ESITI.get(x, x)),
    score_rete=vista["id_gruppo"].map(lambda g: alerts.get(g, {}).get("score_rete")),
)[["timestamp", "id_gruppo", "score_rete", "id_liquidatore", "decisione", "esito_finale", "note"]]

ev = st.dataframe(vista, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                  column_config={"timestamp": "Data/ora (UTC)", "id_gruppo": "Gruppo", "score_rete": "Score rete",
                                 "id_liquidatore": "Liquidatore", "decisione": "Decisione", "esito_finale": "Esito", "note": "Note"})
col_a, col_b = st.columns([1, 4])
col_a.download_button("⬇️ Esporta CSV", vista.to_csv(index=False).encode("utf-8"), "decisioni.csv", "text/csv")
if ev.selection.rows:
    g = vista.iloc[ev.selection.rows[0]]["id_gruppo"]
    if g in alerts and col_b.button(f"🚨 Apri alert gruppo {g}"):
        vai_a_gruppo(g)

st.divider()
st.subheader("🔁 Dataset per il riaddestramento")
st.caption("Gruppi con esito definitivo (frode confermata o regolare), pronti per essere usati come nuove etichette.")
ds = pd.DataFrame(dataset_riaddestramento())
if ds.empty:
    st.caption("Ancora nessun esito definitivo.")
else:
    ds["esito_finale"] = ds["esito_finale"].map(lambda x: ESITI.get(x, x))
    st.dataframe(ds, hide_index=True, width="stretch")
