from retisinistri.score_pratica import aggiungi_score_pratica, calcola_score_pratica
from retisinistri.scoring import assegna_fascia, motivazioni


def test_score_pratica_and_fascia():
    item = {
        "importo_richiesto": 6000,
        "giorni_da_inizio_polizza": 10,
        "orario_notturno": True,
        "verbale_autorita": False,
        "testimone": True,
    }
    score = calcola_score_pratica(item)
    assert score >= 80
    assert assegna_fascia(35) == "bassa"
    assert assegna_fascia(55) == "media"
    assert assegna_fascia(75) == "alta"

    df = [{**item, "id_sinistro": "S1"}, {**item, "id_sinistro": "S2", "importo_richiesto": 1000, "testimone": False}]
    out = aggiungi_score_pratica(__import__("pandas").DataFrame(df))
    assert "score_pratica" in out.columns
    assert out["alert_asis"].dtype == bool

FEATURE = {"n_sinistri": 9, "iban_distinti": 1, "telefoni_distinti": 2, "persone_multi_ruolo": 0,
           "testimone_ricorrente_max": 0, "finestra_giorni": 400}


def test_iban_citato_solo_se_contributo_positivo():
    coefs = {"sinistri_per_iban": 0.5, "sinistri_per_telefono": 0.5, "n_sinistri": 0.5}
    con_iban = motivazioni(FEATURE, {"sinistri_per_iban": 0.8, "sinistri_per_telefono": -0.2, "n_sinistri": 0.1}, coefs)
    assert con_iban == ["9 sinistri su 1 solo IBAN"]
    senza_iban = motivazioni(FEATURE, {"sinistri_per_iban": -0.3, "sinistri_per_telefono": 0.4, "n_sinistri": 0.1}, coefs)
    assert senza_iban == ["9 sinistri su 2 telefoni"]


def test_iban_mai_citato_se_il_modello_lo_pesa_al_contrario():
    coefs = {"sinistri_per_iban": -0.3, "n_sinistri": 0.5}
    frasi = motivazioni(FEATURE, {"sinistri_per_iban": 0.9, "n_sinistri": 0.2}, coefs)
    assert frasi == ["9 sinistri collegati tra loro"]
