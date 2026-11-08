import pytest

import retisinistri.decisions as decisions


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
