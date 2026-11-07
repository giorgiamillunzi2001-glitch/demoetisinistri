import pandas as pd

from retisinistri.communities import trova_gruppi
from retisinistri.graph_builder import costruisci_grafo, proietta_sinistri


def test_graph_projection_excludes_hub_officina_links():
    sinistri = pd.DataFrame([
        {"id_sinistro": "S1", "id_officina": "OFF_HUB", "id_avvocato": "AVV_1", "id_perito": "PER_1", "iban_liquidazione": "IT1", "id_persona": "P1"},
        {"id_sinistro": "S2", "id_officina": "OFF_HUB", "id_avvocato": "AVV_2", "id_perito": "PER_2", "iban_liquidazione": "IT2", "id_persona": "P2"},
    ])
    coinvolgimenti = pd.DataFrame([
        {"id_sinistro": "S1", "id_persona": "P1", "ruolo": "assicurato", "telefono": "333111", "email": "a@b.it", "targa": "AA1", "iban": "IT1"},
        {"id_sinistro": "S2", "id_persona": "P2", "ruolo": "assicurato", "telefono": "333222", "email": "b@b.it", "targa": "AA2", "iban": "IT2"},
    ])
    G = costruisci_grafo(sinistri, coinvolgimenti)
    H = proietta_sinistri(G, solo_forti=True)
    assert not H.has_edge("sinistro:S1", "sinistro:S2")
    groups = trova_gruppi(H)
    assert all(value == -1 for value in groups.values())
