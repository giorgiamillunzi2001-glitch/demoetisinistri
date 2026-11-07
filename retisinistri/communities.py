from __future__ import annotations

import networkx as nx


def trova_gruppi(G_proiettato: nx.Graph, metodo: str = "louvain", seed: int = 42, resolution: float = 1.0) -> dict[str, int]:
    """Restituisce la mappa sinistro → id_gruppo."""
    mapping: dict[str, int] = {}
    if G_proiettato.number_of_nodes() == 0:
        return mapping

    if metodo == "connected_components":
        componenti = list(nx.connected_components(G_proiettato))
    elif metodo == "louvain":
        try:
            from networkx.algorithms.community import louvain_communities

            componenti = louvain_communities(G_proiettato, seed=seed, resolution=resolution)
        except Exception:
            componenti = list(nx.connected_components(G_proiettato))
    else:
        componenti = list(nx.connected_components(G_proiettato))

    all_nodes = set(G_proiettato.nodes)
    assigned = set()
    for idx, comp in enumerate(componenti):
        nodes = sorted(comp)
        if len(nodes) >= 3:
            for node in nodes:
                mapping[node.replace("sinistro:", "")] = idx
                assigned.add(node)
        else:
            for node in nodes:
                mapping[node.replace("sinistro:", "")] = -1
                assigned.add(node)

    for node in sorted(all_nodes - assigned):
        mapping[node.replace("sinistro:", "")] = -1
    return mapping
