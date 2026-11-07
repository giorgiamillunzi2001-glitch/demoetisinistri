import pandas as pd
import pytest

from retisinistri.models import valida_feature_vietate


def test_forbidden_features_raise_error():
    df = pd.DataFrame({"provincia": ["MI"], "n_sinistri": [3]})
    with pytest.raises(ValueError):
        valida_feature_vietate(df)
