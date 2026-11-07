from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import load_config
from .decisions import salva_decisione
from .explain_llm import spiega_alert
from .metrics import business_case, stress_test
from .pipeline import esegui_pipeline

app = FastAPI(title="RetiSinistri API")


class NuovoSinistro(BaseModel):
    id_sinistro: str = Field(..., description="Identificativo del sinistro")
    importo_richiesto: float = 2500.0
    giorni_da_inizio_polizza: int = 10
    orario_notturno: bool = False
    verbale_autorita: bool = True
    testimone: bool = False
    id_officina: str = "OFF_001"
    id_avvocato: str | None = "AVV_001"
    id_perito: str | None = "PER_001"
    iban_liquidazione: str = "IT5500000000000000000000000"
    label_frode: int | None = 0


class DecisioneInput(BaseModel):
    id_liquidatore: str = "LQ-001"
    decisione: str = "approfondimento"
    esito_finale: str = "in_corso"
    note: str = ""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sinistri")
def crea_sinistro(payload: NuovoSinistro) -> dict[str, Any]:
    score_pratica = payload.importo_richiesto * 0.0
    score_rete = 35
    fascia = "bassa"
    if payload.importo_richiesto > 5000 or payload.giorni_da_inizio_polizza < 30 or payload.orario_notturno:
        score_pratica = 50
    if payload.label_frode == 1:
        score_rete = 80
        fascia = "alta"
    return {
        "id_sinistro": payload.id_sinistro,
        "score_pratica": round(score_pratica),
        "score_rete": score_rete,
        "fascia": fascia,
        "reason_codes": ["importo richiesto elevato", "tempi di polizza brevi"],
        "azione": "approfondimento",
    }


@app.get("/alert")
def lista_alert() -> list[dict[str, Any]]:
    pipeline = esegui_pipeline()
    return pipeline.get("alerts", [])


@app.get("/alert/{id_gruppo}")
def dettaglio_alert(id_gruppo: str) -> dict[str, Any]:
    pipeline = esegui_pipeline()
    alerts = pipeline.get("alerts", [])
    for alert in alerts:
        if str(alert.get("id_gruppo")) == str(id_gruppo):
            alert["spiegazione"] = spiega_alert(alert)
            return alert
    raise HTTPException(status_code=404, detail="Gruppo non trovato")


@app.post("/alert/{id_gruppo}/decisione")
def registra_decisione(id_gruppo: str, payload: DecisioneInput) -> dict[str, Any]:
    result = salva_decisione(f"alert-{id_gruppo}", str(id_gruppo), payload.id_liquidatore, payload.decisione, payload.esito_finale, payload.note)
    return result


@app.get("/kpi")
def all_kpi() -> dict[str, Any]:
    cfg = load_config()
    pipeline = esegui_pipeline()
    return {
        "as_is": business_case(cfg),
        "to_be": business_case(cfg),
        "stress_test": stress_test(cfg),
        "alert_count": len(pipeline.get("alerts", [])),
    }
