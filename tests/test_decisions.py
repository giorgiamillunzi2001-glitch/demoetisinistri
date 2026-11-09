import pytest

from retisinistri import decisions


def test_registra_esito_chiude_decisione_e_popola_riaddestramento(tmp_path, monkeypatch):
    monkeypatch.setattr(decisions, "DB_PATH", tmp_path / "decisions.sqlite")
    decisions.salva_decisione("alert-7", "7", "LQ-001", "approfondimento", "in_corso", "verifica IBAN")
    assert decisions.dataset_riaddestramento() == []

    riga = decisions.lista_decisioni()[0]
    decisions.registra_esito(riga["id_decisione"], "frode_confermata", "LQ-002", "confermato dal SIU")

    aggiornata = decisions.lista_decisioni()[0]
    assert aggiornata["esito_finale"] == "frode_confermata"
    assert "verifica IBAN" in aggiornata["note"] and "LQ-002" in aggiornata["note"]
    assert [d["id_gruppo"] for d in decisions.dataset_riaddestramento()] == ["7"]

    with pytest.raises(ValueError):  # un esito già chiuso non si riapre
        decisions.registra_esito(riga["id_decisione"], "regolare", "LQ-001")
    with pytest.raises(ValueError):
        decisions.registra_esito(riga["id_decisione"], "in_corso", "LQ-001")


def test_monitoraggio_calcolato_dai_dati(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(decisions, "DB_PATH", tmp_path / "decisions.sqlite")
    sinistri = pd.DataFrame({
        "data_sinistro": [f"2023-01-{d:02d}" for d in range(1, 25)],
        "score_rete": [0] * 10 + [50, 80] + [0] * 8 + [50, 50, 80, 80],
        "provincia": ["P01"] * 12 + ["P02"] * 12,
        "label_frode": [0] * 24,
    })
    vuoto = decisions.monitoraggio(sinistri, gruppi_segnalati={"1", "2"})
    assert vuoto["override_rate"] is None  # nessuna decisione: "n.d."
    assert vuoto["psi"] is not None and vuoto["psi"] > 0
    assert vuoto["provincia_max"] == "P02" and abs(vuoto["fpr_provincia"] - 4 / 12) < 1e-9

    decisions.salva_decisione("a1", "1", "LQ-001", "archiviazione", "regolare")
    decisions.salva_decisione("a2", "2", "LQ-001", "approfondimento", "in_corso")
    assert decisions.monitoraggio(sinistri, gruppi_segnalati={"1", "2"})["override_rate"] == 0.5
    assert decisions.azzera_decisioni() == 2 and decisions.lista_decisioni() == []
