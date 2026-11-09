import pandas as pd

from retisinistri import synthetic
from retisinistri.synthetic import genera_dataset


def test_genera_dataset_shape_and_seed_reproducibility(tmp_path, monkeypatch):
    # Scrive in una cartella temporanea: il test non deve sovrascrivere i dati dell'app in data/raw
    monkeypatch.setattr(synthetic, "RAW_DIR", tmp_path)
    sinistri_1, coinvolgimenti_1 = genera_dataset(n_sinistri=200, n_anelli=4, seed=42)
    sinistri_2, coinvolgimenti_2 = genera_dataset(n_sinistri=200, n_anelli=4, seed=42)
    assert len(sinistri_1) == 200
    assert len(sinistri_2) == 200
    assert sinistri_1.equals(sinistri_2)
    assert not coinvolgimenti_1.empty
    assert set(sinistri_1.columns) >= {"id_sinistro", "label_frode", "importo_richiesto"}
    assert (tmp_path / "sinistri.csv").exists()


def test_dati_senza_indizi_di_frode(tmp_path, monkeypatch):
    monkeypatch.setattr(synthetic, "RAW_DIR", tmp_path)
    sinistri, coinvolgimenti = genera_dataset(n_sinistri=600, n_anelli=8, seed=42, n_gruppi_legittimi=8)
    testo = pd.concat([sinistri.drop(columns=["label_frode"]).astype(str), coinvolgimenti.astype(str)]).to_csv()
    for indizio in ("FRAUD", "fraud", "FR0"):
        assert indizio not in testo


def test_calibrazione_ivass(tmp_path, monkeypatch):
    from retisinistri.config import load_config
    from retisinistri.score_pratica import aggiungi_score_pratica

    monkeypatch.setattr(synthetic, "RAW_DIR", tmp_path)
    sinistri, _ = genera_dataset(n_sinistri=2000, n_anelli=8, seed=42, n_gruppi_legittimi=8)
    # importo medio vicino al costo medio IVASS (4.962 €), con circa il 15% di sinistri con lesioni
    assert 4500 <= sinistri["importo_richiesto"].mean() <= 5500
    assert 0.10 <= sinistri["lesioni"].mean() <= 0.20
    # le regole attuali segnalano circa il 24% dei sinistri, come gli indicatori di anomalia del mercato
    quota = aggiungi_score_pratica(sinistri, load_config())["alert_asis"].mean()
    assert 0.18 <= quota <= 0.30
    # più anomalie al Sud che al Nord; la provincia resta vietata nel modello
    area = sinistri["provincia"].map(lambda p: synthetic.PROVINCE[p][0])
    segnalati = aggiungi_score_pratica(sinistri, load_config())["alert_asis"]
    assert segnalati[area == "campania"].mean() > segnalati[area == "nord"].mean()
    from retisinistri.models import FORBIDDEN_FEATURES
    assert "provincia" in FORBIDDEN_FEATURES
