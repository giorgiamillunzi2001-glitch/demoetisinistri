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

## Sezioni dell'app

| Sezione | Cosa puoi fare |
|---|---|
| 🏠 **Home** | KPI principali, priorità del giorno, azioni rapide, ultime decisioni |
| 🚨 **Coda alert** | Filtra i gruppi sospetti, apri il dettaglio: reason code, spiegazione, grafo, sinistri, persone e contatti condivisi, registra la decisione |
| 📋 **Sinistri** | Cerca per ID, persona, IBAN, telefono, officina…; scheda completa con collegamenti diretti; esporta CSV |
| 🕸️ **Esplora la rete** | Grafo dei gruppi sospetti, singolo gruppo, hub (officine/avvocati/periti più collegati) |
| ➕ **Valuta nuova pratica** | Inserisci un nuovo sinistro: score AS-IS, collegamenti con gruppi noti, azione suggerita (con esempi precaricati) |
| 📊 **AS-IS vs TO-BE** | Confronto regole tradizionali vs score di rete con soglie regolabili, stress test, simulatore pesi |
| 💶 **Business case** | Valore economico con ipotesi modificabili e scenari |
| ⚖️ **Decisioni** | Storico delle decisioni, filtri, export, dataset per riaddestramento |
| 🧠 **Modello** | Importanza dei segnali, champion vs challenger, guardrail di governance |
| ⚙️ **Impostazioni** | Soglie di rischio (salvate in `config.yaml`), rigenerazione dati sintetici, stato LLM |

## Spiegazioni con LLM (opzionale)

Copia `.env.example` in `.env` e inserisci `ANTHROPIC_API_KEY`. Senza chiave l'app usa un testo
deterministico di fallback, quindi funziona comunque.

## Struttura

```text
app/
  main.py          entry point e navigazione
  common.py        cache della pipeline, grafici, stile
  views/           una pagina per sezione
retisinistri/      backend: grafo, community, feature, modelli, scoring, decisioni, API FastAPI
data/raw/          dataset sintetico (sinistri, coinvolgimenti)
data/processed/    output della pipeline e database decisioni (SQLite)
tests/             test automatici (py -m pytest -q)
```

API REST opzionale: `py -m uvicorn retisinistri.api:app --reload`.

## Limiti

Dati sintetici: le performance non sono rappresentative del mondo reale. Lo score è un indicatore
di sospetto, non una prova; la decisione spetta sempre al liquidatore.
