"""Analisi > Storico decisioni."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from common import DECISIONI, ESITI, codici_gruppo, data_ora_it, percentuale, pipeline, vai_a_gruppo
from retisinistri.decisions import dataset_riaddestramento, lista_decisioni


def render() -> None:
    p = pipeline()
    alerts = {a["id_gruppo"]: a for a in p["alerts"]}
    codici = codici_gruppo(p)

    st.subheader("Storico decisioni")
    storico = pd.DataFrame(lista_decisioni())
    if storico.empty:
        st.write("Nessuna decisione registrata.")
        return

    ultime = storico.drop_duplicates("id_gruppo", keep="first")
    override = ultime[ultime["id_gruppo"].isin(alerts) & ultime["decisione"].isin(["liquidazione", "archiviazione"])]
    c = st.columns(4)
    c[0].metric("Decisioni registrate", len(storico))
    c[1].metric("Segnalazioni gestite", f"{int(ultime['id_gruppo'].isin(alerts).sum())} su {len(alerts)}")
    c[2].metric("Frodi confermate", int((ultime["esito_finale"] == "frode_confermata").sum()))
    c[3].metric("Override del modello", percentuale(len(override) / max(1, len(ultime))),
                help="Gruppi segnalati che il liquidatore ha archiviato o liquidato")

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
    vista = pd.DataFrame({
        "Data e ora": vista["timestamp"].map(data_ora_it),
        "id": vista["id_gruppo"],
        "Gruppo": vista["id_gruppo"].map(lambda g: codici.get(g, "non più attivo")),
        "Score di rete": vista["id_gruppo"].map(lambda g: alerts.get(g, {}).get("score_rete")),
        "Liquidatore": vista["id_liquidatore"],
        "Decisione": vista["decisione"].map(lambda x: DECISIONI.get(x, x)),
        "Esito": vista["esito_finale"].map(lambda x: ESITI.get(x, x)),
        "Note": vista["note"],
    })

    ev = st.dataframe(vista, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                      key="storico_decisioni", column_config={"id": None})
    a, b = st.columns([1, 4])
    a.download_button("Esporta CSV", vista.drop(columns=["id"]).to_csv(index=False).encode("utf-8"), "decisioni.csv", "text/csv")
    if ev.selection.rows:
        g = vista.iloc[ev.selection.rows[0]]["id"]
        if g in alerts and b.button(f"Apri {codici[g]}"):
            vai_a_gruppo(g)

    st.markdown("**Dataset per il riaddestramento**")
    ds = pd.DataFrame(dataset_riaddestramento())
    if ds.empty:
        st.caption("Nessun gruppo con esito definitivo (frode confermata o regolare).")
    else:
        st.dataframe(pd.DataFrame({
            "Gruppo": ds["id_gruppo"].map(lambda g: codici.get(g, "non più attivo")), "Decisione": ds["decisione"].map(lambda x: DECISIONI.get(x, x)),
            "Esito": ds["esito_finale"].map(lambda x: ESITI.get(x, x)), "Note": ds["note"],
        }), hide_index=True, width="stretch")
