import pandas as pd

from retisinistri.features import calcola_feature_gruppo


def test_calcola_feature_gruppo_builds_metric_keys():
    sinistri = pd.DataFrame([
        {"id_sinistro": "S01", "id_officina": "OFF1", "id_avvocato": "AVV1", "score_pratica": 15.0, "importo_richiesto": 3000.0, "data_sinistro": "2024-01-01"},
        {"id_sinistro": "S02", "id_officina": "OFF1", "id_avvocato": "AVV1", "score_pratica": 20.0, "importo_richiesto": 4500.0, "data_sinistro": "2024-02-02"},
        {"id_sinistro": "S03", "id_officina": "OFF2", "id_avvocato": "AVV1", "score_pratica": 50.0, "importo_richiesto": 2000.0, "data_sinistro": "2024-02-05"},
    ])
    coinvolgimenti = pd.DataFrame([
        {"id_sinistro": "S01", "id_persona": "P1", "ruolo": "assicurato", "telefono": "3331", "email": "a@a.it", "targa": "A1", "iban": "IT1"},
        {"id_sinistro": "S01", "id_persona": "P2", "ruolo": "testimone", "telefono": "3332", "email": "b@a.it", "targa": "A2", "iban": "IT1"},
        {"id_sinistro": "S02", "id_persona": "P1", "ruolo": "controparte", "telefono": "3331", "email": "c@a.it", "targa": "A3", "iban": "IT1"},
        {"id_sinistro": "S03", "id_persona": "P3", "ruolo": "assicurato", "telefono": "3333", "email": "d@a.it", "targa": "A4", "iban": "IT2"},
    ])
    G = __import__("networkx", fromlist=["Graph"]).Graph()
    for sid in ["S01", "S02", "S03"]:
        G.add_node(f"sinistro:{sid}")
    features = calcola_feature_gruppo(["S01", "S02", "S03"], sinistri, coinvolgimenti, G)
    assert features["n_sinistri"] == 3
    assert "densita" in features
    assert "score_pratica_medio" in features
