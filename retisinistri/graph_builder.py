from __future__ import annotations

import networkx as nx
import pandas as pd


def _entity_key(prefix: str, value: str | int | float | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return f"{prefix}:{str(value).strip()}"


def costruisci_grafo(sinistri: pd.DataFrame, coinvolgimenti: pd.DataFrame) -> nx.Graph:
    """Costruisce un grafo bipartito sinistri-entità."""
    G = nx.Graph()
    if sinistri.empty:
        return G

    for _, sinistro in sinistri.iterrows():
        sinistro_id = f"sinistro:{sinistro['id_sinistro']}"
        G.add_node(sinistro_id, tipo="sinistro")

        strong_entities = [
            ("persona", sinistro.get("id_persona")),
            ("iban", sinistro.get("iban_liquidazione")),
        ]
        for prefix, value in strong_entities:
            node = _entity_key(prefix, value)
            if node is not None:
                G.add_node(node, tipo=prefix)
                G.add_edge(sinistro_id, node, ruolo="sinistro", forza="forte", weight=1.0)

        weak_entities = [
            ("officina", sinistro.get("id_officina")),
            ("avvocato", sinistro.get("id_avvocato")),
            ("perito", sinistro.get("id_perito")),
        ]
        for prefix, value in weak_entities:
            node = _entity_key(prefix, value)
            if node is not None:
                G.add_node(node, tipo=prefix)
                G.add_edge(sinistro_id, node, ruolo="sinistro", forza="debole", weight=0.2)

    for _, row in coinvolgimenti.iterrows():
        sinistro_id = f"sinistro:{row['id_sinistro']}"
        if "id_persona" in row and pd.notna(row.get("id_persona")):
            person_node = _entity_key("persona", row["id_persona"])
            if person_node is not None:
                G.add_node(person_node, tipo="persona")
                G.add_edge(sinistro_id, person_node, ruolo=row.get("ruolo"), forza="forte", weight=1.0)
        for prefix, field in (("telefono", "telefono"), ("iban", "iban")):
            value = row.get(field)
            node = _entity_key(prefix, value)
            if node is not None:
                G.add_node(node, tipo=prefix)
                G.add_edge(sinistro_id, node, ruolo=row.get("ruolo"), forza="forte", weight=1.0)

    return G


def proietta_sinistri(G: nx.Graph, solo_forti: bool = True) -> nx.Graph:
    """Genera il grafo sinistro-sinistro a partire dalle entità forti."""
    H = nx.Graph()
    sinistri = [n for n in G.nodes if n.startswith("sinistro:")]
    for node in sinistri:
        H.add_node(node)

    for i, a in enumerate(sinistri):
        for b in sinistri[i + 1 :]:
            neighbors_a = set(G.neighbors(a))
            neighbors_b = set(G.neighbors(b))
            if solo_forti:
                common = {
                    n for n in neighbors_a & neighbors_b if G.nodes.get(n, {}).get("tipo") in {"persona", "iban", "telefono"}
                }
            else:
                common = neighbors_a & neighbors_b
            if common:
                H.add_edge(a, b, weight=len(common))
    return H


def aggiungi_sinistro(G: nx.Graph, sinistro: pd.Series, coinvolgimenti: pd.DataFrame) -> nx.Graph:
    """Aggiunge un nuovo sinistro al grafo senza ricostruirlo."""
    sinistro_id = f"sinistro:{sinistro['id_sinistro']}"
    G.add_node(sinistro_id, tipo="sinistro")

    for _, row in coinvolgimenti[coinvolgimenti["id_sinistro"] == sinistro["id_sinistro"]].iterrows():
        if pd.notna(row.get("id_persona")):
            G.add_edge(sinistro_id, f"persona:{row['id_persona']}", ruolo=row.get("ruolo"), forza="forte", weight=1.0)
        for prefix, field in (("telefono", "telefono"), ("iban", "iban")):
            value = row.get(field)
            if value is not None and not pd.isna(value):
                G.add_edge(sinistro_id, f"{prefix}:{value}", ruolo=row.get("ruolo"), forza="forte", weight=1.0)

    return G
