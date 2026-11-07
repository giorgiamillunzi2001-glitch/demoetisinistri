from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Legge il file di configurazione YAML e unifica le variabili d'ambiente."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        return {}
    load_dotenv(ROOT / ".env", override=False)
    config.setdefault("llm", {})
    config["llm"]["api_key"] = os.getenv("ANTHROPIC_API_KEY")
    config["llm"]["model"] = os.getenv("LLM_MODEL", config["llm"].get("model", "claude-haiku-5-5"))
    return config


def config_path() -> Path:
    return DEFAULT_CONFIG_PATH
