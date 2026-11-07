from retisinistri.score_pratica import aggiungi_score_pratica, calcola_score_pratica
from retisinistri.scoring import assegna_fascia


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
