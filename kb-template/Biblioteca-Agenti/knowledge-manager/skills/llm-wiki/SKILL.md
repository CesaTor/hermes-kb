---
name: llm-wiki
description: Costruire e mantenere la wiki aziendale come pagine markdown collegate; ingest, query, lint.
version: 0.1.0
author: ReQurv (adattata dalla skill MIT «llm-wiki» di Hermes Agent)
license: LicenseRef-ReQurv-Proprietary
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [wiki, knowledge-base, second-brain, markdown, karpathy]
    category: knowledge
    related_skills: [mappa-kb, knowledge-ingest, pubblica-documento]
---

# LLM Wiki aziendale

La wiki è un insieme di pagine markdown collegate che **compilano** la conoscenza una volta e la
tengono aggiornata, invece di ricostruirla a ogni domanda. È il pattern di
[Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) applicato alla KB
ReQurv. La skill di partenza è `optional-skills/research/llm-wiki` di Hermes (MIT, vedi `NOTICE.md`).

**Divisione del lavoro:** l'IT sceglie le fonti e le domande; tu riassumi, colleghi, archivi e tieni
la coerenza.

## Dove sta

`Wiki/` alla radice dell'organizzazione, cioè accanto a `Biblioteca-Agenti/` (la radice che il
prompt chiama `$SECOND_BRAIN_ROOT`). Se non è unica, chiedi.

```text
Wiki/
├─ SCHEMA.md        # convenzioni, tassonomia, soglie
├─ index.md         # catalogo: una riga per pagina
├─ log.md           # registro append-only
├─ fonti/           # schede delle fonti (percorso, versione, impronta, sintesi)
├─ concetti/        # una pagina per concetto o tema
├─ entita/          # persone, aziende, prodotti, sistemi
├─ confronti/       # analisi affiancate
├─ risposte/        # risposte alle domande che vale la pena conservare
└─ _archivio/       # pagine superate
```

Le fonti **non si copiano**: stanno in `NN-Area/documenti/`, `Record/` o
`Operatori/<nome>/proposte/knowledge/`. `Wiki/fonti/` contiene solo la scheda.

## Orientati sempre, a ogni sessione

1. leggi `Wiki/SCHEMA.md` (dominio, convenzioni, tassonomia);
2. leggi `Wiki/index.md` (cosa esiste);
3. leggi le ultime 30 righe di `Wiki/log.md` (cosa è successo di recente).

Per wiki grandi (>100 pagine) cerca per parola chiave prima di creare qualcosa.

## Inizializzare la wiki

1. Chiedi all'IT il dominio e il perimetro (tutta l'azienda o un'area) e chi può leggerla.
2. Crea la struttura qui sopra.
3. Scrivi `SCHEMA.md` adattando il modello in fondo a questa skill.
4. Scrivi `index.md` con le sezioni e `log.md` con la voce di creazione.
5. Elenca le prime fonti da ingerire (documenti in forza, record, conoscenze già raccolte).

## Ingest

Una fonte tocca in genere 5–15 pagine: è il punto del pattern.

1. **Verifica la fonte.** È un documento in forza? Controlla che in `documenti/` ci sia **una sola**
   versione per titolo e che sia quella che stai leggendo. Se è un record, non si modifica.
2. **Scheda fonte.** Calcola l'impronta (`python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <file>`)
   e scrivi `Wiki/fonti/<slug>.md` con `source_type: file`, `source`, `source_version`,
   `source_hash`, `ingested`, `area` e una sintesi. (Le conoscenze degli operatori usano
   `source_type: knowledge` e non hanno hash: vedi `knowledge-ingest`.) Se la scheda esiste, confronta l'hash: uguale → salta; diverso → la fonte è
   cambiata, aggiorna le pagine collegate.
3. **Discuti i punti chiave** con l'IT (in un contesto automatico salta questo passo).
4. **Cerca l'esistente** in `index.md` e nelle pagine: estendi, non duplicare.
5. **Scrivi o aggiorna le pagine.** Nuove entità/concetti solo se rispettano le soglie dello
   `SCHEMA.md`. Ogni pagina cita le fonti nel frontmatter e, quando sintetizza 3+ fonti, con
   `^[NN-Area/documenti/file_vX.Y.ext]` sui paragrafi che vengono da una fonte precisa.
6. **Collega**: almeno 2 wikilink in uscita per pagina, e controlla che le pagine esistenti
   colleghino indietro.
7. **Aggiorna `index.md`** (sezione giusta, in ordine alfabetico, conteggio e data in testa) e
   **`log.md`**: `## [AAAA-MM-GG] ingest | <titolo fonte>`, con l'elenco dei file toccati.
8. **Riporta** i file creati e aggiornati.

## Query

1. Leggi `index.md` e individua le pagine; per wiki grandi cerca per parola chiave.
2. Leggi le pagine e rispondi **citando** `[[pagina]]` e la fonte.
3. Se la risposta è un confronto, un'analisi o una sintesi che sarebbe faticoso rifare, salvala in
   `risposte/` o `confronti/` e aggiorna indice e log. Le risposte banali non si salvano.

## Lint

1. Esegui lo script deterministico:
   `python3 <cartella skill>/scripts/wiki_lint.py <radice>/Wiki --json`
   Controlla frontmatter, wikilink rotti, pagine fuori indice, orfane, pagine troppo lunghe, fonti
   cambiate o sparite, rotazione del log.
2. Poi la parte che serve al modello: contraddizioni fra pagine, affermazioni superate da fonti più
   recenti, concetti citati senza pagina, domande aperte e fonti da cercare.
3. Sistema ciò che è sicuro; per il resto riporta, raggruppato per gravità.
4. Aggiungi in `log.md`: `## [AAAA-MM-GG] lint | N problemi`.

## Regole

- **Non modificare mai le fonti**: le correzioni vanno nelle pagine, non nei documenti.
- **Non creare pagine per menzioni di passaggio**: segui le soglie dello `SCHEMA.md`.
- **Niente tag liberi**: ogni tag deve essere nella tassonomia; aggiungilo allo `SCHEMA.md` prima.
- **Niente pagine isolate**: almeno 2 collegamenti in uscita e almeno uno in entrata.
- **Non sovrascrivere in silenzio**: se una fonte contraddice una pagina, annota entrambe le
  posizioni con data e fonte, marca `contested: true` e segnala.
- **Pagine leggibili in 30 secondi**: oltre 200 righe si dividono.
- **Archivia** ciò che è superato in `_archivio/`, togliendolo dall'indice e sostituendo i link con
  il testo «(archiviata)».
- **Chiedi prima** di un ingest che tocca più di 10 pagine esistenti.
- **Scala**: fino a ~100 fonti l'indice basta; oltre, proponi `qmd` (skill Hermes) sulla cartella
  `Wiki/`, senza cambiare il formato delle pagine.

## Modello di `SCHEMA.md`

Adatta il dominio, non copiarlo alla lettera.

```markdown
# Schema della wiki

## Dominio
[Che cosa copre questa wiki — es. «tutta l'azienda», «area 01-Strategia»]

## Convenzioni
- Nomi file: minuscolo, trattini, niente spazi (`piano-commerciale.md`).
- Frontmatter obbligatorio in ogni pagina.
- Wikilink `[[cartella/pagina]]`; almeno 2 in uscita per pagina.
- Ogni pagina nuova va in `index.md`; ogni azione in `log.md`.
- Le fonti si citano con il percorso del documento in forza (versione nel nome), mai con una copia.

## Frontmatter
---
title: Titolo
created: AAAA-MM-GG
updated: AAAA-MM-GG
type: entita | concetto | confronto | risposta
tags: [dalla tassonomia]
sources: [NN-Area/documenti/file_vX.Y.ext]
confidence: alta | media | bassa
contested: true            # solo se ci sono contraddizioni aperte
---

## Tassonomia
[10–20 tag di primo livello, legati alle aree e ai tipi. Aggiungi qui un tag prima di usarlo.]
- Aree: strategia, gestione, finanza, marketing, vendite, prodotto, operazioni, persone, legale, amministrazione
- Tipi: processo, cliente, fornitore, prodotto, decisione, rischio, metric

## Soglie
- Crea una pagina se l'entità/concetto compare in 2+ fonti o è centrale in una.
- Estendi una pagina esistente se la fonte ne parla già.
- Non creare pagine per menzioni di passaggio.
- Dividi oltre ~200 righe; archivia ciò che è superato.

## Politica di aggiornamento
1. Controlla le date: la fonte più recente di solito prevale.
2. Se sono davvero in contraddizione, tieni entrambe le posizioni con data e fonte.
3. Marca `contested: true` e segnala nel lint.
```
