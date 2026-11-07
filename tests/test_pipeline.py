import os

from retisinistri.explain_llm import spiega_alert
from retisinistri.pipeline import esegui_pipeline


def test_pipeline_and_fallback_explain():
    os.environ.pop("ANTHROPIC_API_KEY", None)
    pipeline = esegui_pipeline({"paths": {"processed_dir": "data/processed"}, "scoring": {"soglia_media": 40, "soglia_alta": 70}})
    assert "alerts" in pipeline
    assert pipeline["alerts"]
    text = spiega_alert({"score_rete": 72, "reason_codes": ["2 persone compaiono con ruoli diversi", "3 sinistri in 7 giorni"], "n_sinistri": 3})
    assert isinstance(text, str)
    assert len(text) > 0
