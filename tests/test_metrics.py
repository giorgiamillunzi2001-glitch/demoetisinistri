import numpy as np

from retisinistri.metrics import business_case, matrice_confusione, metriche_kpi


def test_metrics_and_business_case():
    matrix = matrice_confusione([1, 1, 0, 0], [1, 0, 1, 0])
    assert matrix["TP"] == 1
    assert matrix["FP"] == 1
    assert matrix["FN"] == 1
    assert matrix["TN"] == 1

    kpis = metriche_kpi([1, 1, 0, 0], [1, 0, 1, 0], [0.9, 0.3, 0.8, 0.2])
    assert kpis["recall"] >= 0.0
    assert kpis["precision"] >= 0.0
    assert "AUC" in kpis

    bc = business_case({"business": {"premi_rc_auto": 239_300_000, "loss_ratio": 0.75, "quota_frodi_extra_evitate": 0.01, "costi_annui": 300_000, "costo_una_tantum": 500_000}})
    assert bc["valore_annuo"] > 0
