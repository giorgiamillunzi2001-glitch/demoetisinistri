from __future__ import annotations

import json
import os
import re
import warnings
from typing import Any


def _maschera_valore(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if any(ch.isdigit() for ch in text):
        digits = re.findall(r"\d", text)
        if len(digits) >= 4:
            return text[:4] + "****" + text[-4:]
    return text


def _maschera_input(alert: dict[str, Any]) -> dict[str, Any]:
    masked = json.loads(json.dumps(alert, default=str, ensure_ascii=False))
    if isinstance(masked, dict):
        for key, value in masked.items():
            if "iban" in key.lower() or "telefono" in key.lower() or "cf" in key.lower():
                if isinstance(value, str):
                    masked[key] = _maschera_valore(value)
        # Maschera anche i campi di persone
        if "persone" in masked:
            for item in masked["persone"]:
                if isinstance(item, dict):
                    for key in ("telefono", "iban", "codice_fiscale"):
                        if key in item and isinstance(item[key], str):
                            item[key] = _maschera_valore(item[key])
    return masked


def _numbers_in_text(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def _fallback_reason_text(reason_codes: list[str]) -> str:
    if not reason_codes:
        return "Il gruppo mostra una concentrazione di collegamenti e richieste ravvicinate, con elevata probabilità di frode organizzata. Verificare la coerenza dei ruoli, degli IBAN e dei contatti prima di proseguire con l'approfondimento."
    joined = "; ".join(reason_codes[:3])
    return (
        f"Questo gruppo è stato segnalato per {joined}. "
        "Le evidenze indicano un collegamento di rete tra più sinistri; verificare i ruoli, i contatti e gli IBAN condivisi prima di qualsiasi decisione."
    )


def spiega_alert(alert: dict[str, Any]) -> str:
    """Genera la spiegazione dell'alert usando il fallback deterministico se l'LLM non è disponibile."""
    reason_codes = alert.get("reason_codes", [])
    numbers = set()
    for key, value in alert.items():
        if key != "reason_codes" and key != "persone":
            if isinstance(value, (int, float)):
                numbers.add(str(int(value)))
    masked = _maschera_input(alert)
    prompt = (
        "Sei un assistente per il team antifrode di una compagnia assicurativa. "
        "Spiega a un liquidatore, in italiano semplice e in massimo 120 parole, perché questo gruppo di sinistri è stato segnalato e cosa verificare per primo. "
        "Usa SOLO i dati forniti, non inventare fatti. Ricorda che è un sospetto, non una prova: la decisione spetta al liquidatore."
    )
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")
        import anthropic

        model = os.getenv("LLM_MODEL", "claude-haiku-5-5")
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=400,
            temperature=0.2,
            system=prompt,
            messages=[{"role": "user", "content": json.dumps(masked, ensure_ascii=False)}],
            timeout=15,
        )
        text = response.content[0].text
        if not text:
            raise ValueError("Empty answer")
        text_numbers = _numbers_in_text(text)
        if text_numbers - numbers:
            warnings.warn("LLM response contains numbers absent from input; fallback activated.")
            return _fallback_reason_text(reason_codes)
        return text
    except Exception:
        return _fallback_reason_text(reason_codes)
