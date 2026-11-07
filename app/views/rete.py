from __future__ import annotations

import networkx as nx
import streamlit as st

from common import ETICHETTA_FASCIA, ICONA_FASCIA, figura_grafo, pipeline, sottografo_gruppo, vai_a_gruppo

p = pipeline()
G: nx.Graph = p["grafo"]
sinistri = p["sinistri"]
alerts = {a["id_gruppo"]: a for a in p["alerts"]}

st.title("🕸️ Esplora la rete")
st.caption("Visualizza i collegamenti tra sinistri e le entità che li legano. Le entità forti (persone, IBAN, telefoni) definiscono i gruppi.")

c1, c2, c3 = st.columns(3)
c1.metric("Nodi nel grafo", f"{G.number_of_nodes():,}".replace(",", "."))
c2.metric("Collegamenti", f"{G.number_of_edges():,}".replace(",", "."))
c3.metric("Legami sinistro–sinistro", p["grafo_proiettato"].number_of_edges(), help="Coppie di sinistri che condividono almeno un'entità forte")

modalita = st.segmented_control(
    "Cosa vuoi vedere?", ["Gruppi sospetti", "Un singolo gruppo", "Hub: entità più collegate"], default="Gruppi sospetti"
)

gruppi = sorted({g for g in sinistri["id_gruppo"] if g != "-1"}, key=lambda g: -alerts.get(g, {}).get("score_rete", 0))

if modalita == "Gruppi sospetti":
    deboli = st.toggle("Includi officine, periti e avvocati", value=False)
    ids = sinistri[sinistri["id_gruppo"].isin(gruppi)]["id_sinistro"].tolist()
    H = sottografo_gruppo(p, ids, includi_deboli=deboli)
    st.plotly_chart(figura_grafo(H, altezza=650), width="stretch")
    st.caption("Ogni cluster corrisponde a un gruppo individuato dalla community detection (Louvain).")

elif modalita == "Un singolo gruppo":
    if not gruppi:
        st.info("Nessun gruppo disponibile.")
        st.stop()

    def etichetta(g: str) -> str:
        a = alerts.get(g)
        n = int((sinistri["id_gruppo"] == g).sum())
        if a:
            return f"Gruppo {g} · {ICONA_FASCIA[a['fascia']]} score {a['score_rete']} · {n} sinistri"
        return f"Gruppo {g} · 🟢 nessun alert · {n} sinistri"

    g = st.selectbox("Gruppo", gruppi, format_func=etichetta)
    ids = sinistri[sinistri["id_gruppo"] == g]["id_sinistro"].tolist()
    st.plotly_chart(figura_grafo(sottografo_gruppo(p, ids), altezza=600), width="stretch")
    if g in alerts and st.button("🚨 Apri il dettaglio dell'alert", type="primary"):
        vai_a_gruppo(g)

else:
    tipo = st.radio("Tipo di entità", ["officina", "avvocato", "perito", "persona", "iban", "telefono"], horizontal=True)
    righe = []
    for n, d in G.nodes(data=True):
        if d.get("tipo") != tipo:
            continue
        claims = [v.split(":", 1)[1] for v in G.neighbors(n) if v.startswith("sinistro:")]
        sub = sinistri[sinistri["id_sinistro"].isin(claims)]
        righe.append({
            "Entità": n.split(":", 1)[1],
            "Sinistri collegati": len(claims),
            "Di cui in gruppi sospetti": int(sub["fascia"].isin(["alta", "media"]).sum()),
            "Importo totale": float(sub["importo_richiesto"].sum()),
        })
    import pandas as pd

    df = pd.DataFrame(righe).sort_values("Sinistri collegati", ascending=False).head(25)
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"Importo totale": st.column_config.NumberColumn(format="€ %.0f")})
    st.caption(
        "Un hub molto frequentato non è di per sé sospetto: ad esempio un'officina convenzionata può servire molti "
        "clienti regolari. Per questo officine, periti e avvocati sono legami *deboli* e non formano i gruppi."
    )
    if not df.empty:
        scelta = st.selectbox("Visualizza i collegamenti di", df["Entità"].tolist())
        nodo = f"{tipo}:{scelta}"
        claims = [v.split(":", 1)[1] for v in G.neighbors(nodo) if v.startswith("sinistro:")]
        H = sottografo_gruppo(p, claims, includi_deboli=tipo in {"officina", "avvocato", "perito"})
        st.plotly_chart(figura_grafo(H, altezza=550, evidenzia={nodo}), width="stretch")

st.caption(f"Legenda fasce: {', '.join(f'{ICONA_FASCIA[k]} {v}' for k, v in ETICHETTA_FASCIA.items())}")
