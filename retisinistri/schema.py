from __future__ import annotations

from typing import Literal, TypedDict


class PersonaRaw(TypedDict, total=False):
    nome: str
    cognome: str
    codice_fiscale: str
    telefono: str
    email: str


class Coinvolgimento(TypedDict):
    id_sinistro: str
    id_persona: str
    ruolo: Literal["assicurato", "controparte", "testimone", "conducente"]
    telefono: str | None
    email: str | None
    targa: str | None
    iban: str | None


class Sinistro(TypedDict):
    id_sinistro: str
    data_sinistro: str
    data_denuncia: str
    provincia: str
    importo_richiesto: float
    orario_notturno: bool
    verbale_autorita: bool
    cai_firmato_entrambi: bool
    giorni_da_inizio_polizza: int
    id_officina: str
    id_perito: str | None
    id_avvocato: str | None
    iban_liquidazione: str
    label_frode: int | None
