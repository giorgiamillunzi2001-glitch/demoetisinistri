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


def test_caso_non_perfetto(tmp_path, monkeypatch):
    """Sul dataset di default (600 sinistri, 8 anelli, 8 gruppi legittimi, seed 42) il caso non deve
    essere perfetto: qualche anello prudente resta sotto soglia e il challenger non separa tutto."""
    from retisinistri import synthetic
    from retisinistri.config import load_config
    from retisinistri.metrics import metriche_kpi

    monkeypatch.setattr(synthetic, "RAW_DIR", tmp_path)
    synthetic.genera_dataset(n_sinistri=600, n_anelli=8, seed=42, n_gruppi_legittimi=8)
    cfg = load_config()
    cfg["paths"] = dict(cfg.get("paths", {}), raw_dir=str(tmp_path), processed_dir=str(tmp_path))
    p = esegui_pipeline(cfg)
    s, f = p["sinistri"], p["feature_df"]
    soglia = cfg["scoring"]["soglia_media"]
    recall_rete = ((s["score_rete"] >= soglia) & (s["label_frode"] == 1)).sum() / s["label_frode"].sum()
    auc_challenger = metriche_kpi(f["label_frode"], (f["score_challenger"] >= soglia).astype(int), f["score_challenger"])["AUC"]
    assert recall_rete < 1.0
    assert auc_challenger < 0.99
