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
