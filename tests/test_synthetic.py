import pandas as pd

from retisinistri.synthetic import genera_dataset


def test_genera_dataset_shape_and_seed_reproducibility():
    sinistri_1, coinvolgimenti_1 = genera_dataset(n_sinistri=200, n_anelli=4, seed=42)
    sinistri_2, coinvolgimenti_2 = genera_dataset(n_sinistri=200, n_anelli=4, seed=42)
    assert len(sinistri_1) == 200
    assert len(sinistri_2) == 200
    assert sinistri_1.equals(sinistri_2)
    assert not coinvolgimenti_1.empty
    assert set(sinistri_1.columns) >= {"id_sinistro", "label_frode", "importo_richiesto"}
