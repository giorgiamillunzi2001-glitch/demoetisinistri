# RetiSinistri – App antifrode RC auto

Applicazione web interattiva che individua le **frodi organizzate** nei sinistri RC auto collegando
sinistri, persone, IBAN e telefoni in un grafo, segnalando i gruppi sospetti e supportando il
liquidatore nella decisione (human-in-the-loop). Tutti i dati sono **sintetici**.

## Avvio rapido

**Windows:** doppio clic su `avvia_app.bat`.

Oppure da terminale nella cartella del progetto:

```bash
py -m pip install -r requirements.txt
py -m streamlit run app/main.py
```

L'app si apre su http://localhost:8501. Il primo caricamento richiede qualche secondo (analisi della rete).

## Pagine

| Pagina | Contenuto |
|---|---|
| **Panoramica** | Indicatori principali, tabella degli alert prioritari (clic su una riga per aprire il gruppo), ultime decisioni |
| **Alert** | Filtri per livello e stato, ricerca di un sinistro, elenco dei gruppi in alert. Dettaglio del gruppo: motivazioni, spiegazione, grafo, decisione (approfondimento o archiviazione), sinistri, persone e contatti, indicatori tecnici |
| **Nuova denuncia** | Valutazione di un nuovo sinistro: punteggio delle regole attuali, collegamenti con gruppi sospetti, azione suggerita |
| **Analisi** | Schede *Confronto* (regole attuali vs score di rete), *Business case*, *Modello* (coefficienti, challenger, governance, rigenerazione dati, stato LLM) e *Storico decisioni* |

Nella barra laterale: ID liquidatore (usato per registrare le decisioni) e, in *Impostazioni*, le soglie di rischio salvate in `config.yaml`.

## Spiegazioni con LLM (opzionale)

Copia `.env.example` in `.env` e inserisci `ANTHROPIC_API_KEY`. Senza chiave l'app usa un testo
deterministico di fallback, quindi funziona comunque.

## Struttura

```text
app/
  main.py          entry point, navigazione e barra laterale
  common.py        cache della pipeline, formati, grafo, stile
  views/           home, alert, valuta, analisi (+ confronto, business, modello, decisioni usati dalle schede di Analisi)
retisinistri/      backend: grafo, community, feature, modelli, scoring, decisioni, API FastAPI
data/raw/          dataset sintetico (sinistri, coinvolgimenti)
data/processed/    output della pipeline e database decisioni (SQLite)
tests/             test automatici (py -m pytest -q)
```

API REST opzionale: `py -m uvicorn retisinistri.api:app --reload`.

## Limiti

Dati sintetici: le performance non sono rappresentative del mondo reale. Lo score è un indicatore
di sospetto, non una prova; la decisione spetta sempre al liquidatore.
