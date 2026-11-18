# Knowledge Manager: skill consolidate per la wiki aziendale

Data: 18 novembre 2026. Ricerca fatta su Hermes **upstream** (checkout `upstream/main`), sul gist di
Karpathy e sui progetti che lo implementano. Obiettivo: scegliere le skill da dare al bot IT
«Knowledge Manager» e adattarle alla KB ReQurv, senza inventare un formato nuovo.

## 1. Il pattern

[Karpathy, *llm-wiki*](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (4 aprile
2026) descrive tre strati e tre operazioni:

| Strato | Cosa | Chi scrive |
|---|---|---|
| Fonti grezze | articoli, paper, trascrizioni, documenti | le persone; il modello le legge soltanto |
| Wiki | pagine markdown collegate fra loro: entità, concetti, confronti, risposte | il modello |
| Schema | `SCHEMA.md` / `AGENTS.md`: convenzioni, tassonomia, soglie | persone + modello |

Operazioni: **ingest** (una fonte tocca 10–15 pagine), **query** (risposta con citazioni, e le
risposte buone diventano pagine), **lint** (contraddizioni, collegamenti rotti, pagine orfane,
affermazioni vecchie). Due file speciali: `index.md` (catalogo con una riga per pagina) e `log.md`
(registro append-only). La frase che riassume il tutto: *«Obsidian è l'IDE, l'LLM è il programmatore,
la wiki è il codice»*.

Perché serve a un'azienda: la conoscenza viene **compilata una volta e tenuta aggiornata**, invece di
essere ricostruita a ogni domanda; le contraddizioni si vedono quando si ingerisce, non quando il
cliente è in riunione. Il limite dichiarato è la scala: l'indice funziona fino a ~100 fonti e qualche
centinaio di pagine; oltre serve una ricerca vera (§4).

## 2. Cosa esiste già, e quanto è consolidato

| Progetto | Cosa dà | Verdetto per noi |
|---|---|---|
| **`llm-wiki`** in Hermes upstream (`optional-skills/research/llm-wiki`, v2.1.0, MIT) | La skill completa: tre strati, `SCHEMA.md`, `index.md`, `log.md`, ingest/query/lint, provenienza con `^[fonte]`, frontmatter, soglie di creazione pagina, rotazione del log, Obsidian | **Base scelta.** È già scritta, manutenuta e senza runtime aggiuntivo |
| [**llm-wiki-compiler**](https://github.com/atomicstrata/llm-wiki-compiler) (`llmwiki`, MIT, 2,3k★) | CLI/MCP che compila le fonti in pagine tipizzate, con citazioni, code di review, `lint`, `eval`, OKF, viewer, provider multipli | Utile se serve un **processo batch con gate di review**; costa Node 24, uno stato proprio e una seconda fonte di verità. Da valutare dopo il pilot |
| [**second-brain-skill**](https://github.com/ChavesLiu/second-brain-skill) (MIT) | Skill per Claude Code con `/wiki init`, `ingest`, `query`, script | Stessa idea, meno matura; utile come confronto, non come dipendenza |
| [**qmd**](https://github.com/tobi/qmd) (MIT) + skill Hermes `qmd` | Ricerca locale ibrida (BM25 + vettori + reranking) su file markdown | **Opzione a scala**, consigliata dallo stesso Karpathy oltre ~100 fonti. Non serve al pilot |
| **`code-wiki`** in Hermes upstream | Skill con template per documentare un repository (README, architettura, moduli, diagrammi) | Utile per documentare il **plugin**, non i documenti aziendali |
| **`obsidian`** in Hermes upstream | Lettura/scrittura di un vault Obsidian | Solo come visualizzatore della cartella `Wiki/`; non è richiesto |
| [**awesome-llm-wiki**](https://github.com/gavischneider/awesome-llm-wiki) | Indice di implementazioni (MindBase, Kompl, Link, Nimbalyst, …) | Riferimento per idee: «estendi, non creare», «non sovrascrivere in silenzio», log per le query |
| **Memory provider** Hermes (`prefetch`) | Conoscenza iniettata a ogni turno | Complementare, non sostituisce la wiki: la wiki è un artefatto leggibile e revisionabile |

## 3. L'adattamento alla KB ReQurv

La skill upstream assume una cartella `~/wiki` con `raw/` immutabile. Da noi le fonti **esistono
già** e non vanno duplicate: sono i `documenti/` delle aree (LIFO, una versione in forza), i `Record/`
e le conoscenze raccolte dagli operatori. Quindi:

| Pattern | Nella KB |
|---|---|
| `raw/` | **Non si copia**: le fonti restano `NN-Area/documenti/...` e `Record/...`. In `Wiki/fonti/` va una **scheda fonte** con percorso, versione, hash e sintesi |
| `wiki/` | `Wiki/` alla radice dell'organizzazione (accanto a `Biblioteca-Agenti`), scritta dal Knowledge Manager |
| `SCHEMA.md` | `Wiki/SCHEMA.md`, con la tassonomia delle aree e le soglie |
| `index.md`, `log.md` | `Wiki/index.md`, `Wiki/log.md` |
| Ingest | da un documento dell'area, da un record o da `Operatori/<nome>/proposte/knowledge/*.md` |
| Provenienza | percorso + versione + hash del documento, non una copia |
| Lint | script deterministico (`scripts/wiki_lint.py`) + controllo del modello su contraddizioni e qualità |
| Review | il Knowledge Manager è IT: le sue modifiche alla wiki sono il suo lavoro; per i **documenti** vale il canone (skill `pubblica-documento`) |
| Knowledge degli operatori | si integra nella wiki o in un documento dell'area, poi **si cancella** dalla cartella proposte: la cancellazione è il segnale di «integrata» |

Cosa **non** cambia: la wiki è derivata. Non sostituisce i documenti in forza, non entra in
`documenti/`, non si sincronizza come un documento ufficiale. Se un documento cambia, la scheda fonte
lo rileva con l'hash e la pagina risulta da rileggere.

## 4. La scala, dichiarata

- fino a ~100 fonti e qualche centinaio di pagine: `index.md` basta (pattern originale);
- oltre: `qmd` sulla cartella `Wiki/` (skill Hermes già presente) oppure la ricerca ibrida di
  `llmwiki`; la wiki resta la stessa;
- la ricerca per parole del manuale (§3.11) resta il minimo; la wiki aggiunge la sintesi, non
  sostituisce il catalogo.

## 5. Cosa è stato creato

Pacchetto starter in `kb-template/Biblioteca-Agenti/knowledge-manager/`:

| File | Ruolo |
|---|---|
| `SOUL.md` | identità del Knowledge Manager: bibliotecario aziendale, IT, citazioni obbligatorie |
| `skills/llm-wiki/` | la skill adattata (tre strati, ingest/query/lint, provenienza, soglie) + `scripts/wiki_lint.py` |
| `skills/mappa-kb/` | dove stanno le cose: aree, `documenti/`, `Archivio/`, `Record/`, `indice.md`, `proposte/`, `Wiki/`, registro pubblicazioni |
| `skills/knowledge-ingest/` | dal file `proposte/knowledge/*.md` alla wiki o al documento d'area, con la regola «cancellare = integrata» |
| `skills/pubblica-documento/` | il canone del manuale: 4 porte, anteprima, LIFO, Archivio, registro con impronta |
| `NOTICE.md` (dentro la skill) | attribuzione MIT della skill di partenza |

Il pacchetto non contiene `config.yaml`: provider, `skills.create_dir` e plugin vengono già seminati
dal plugin ReQurv KB all'installazione. Il bot va installato dalla libreria come gli altri; perché
sia IT, il suo `.autorizzazioni.yaml` deve avere `ruolo: it`.

## 6. Cosa resta da decidere

1. **Dove vive la wiki**: proposta `Wiki/` alla radice dell'organizzazione. Alternative: `90-Sistema/Wiki/`
   (governance) o una wiki per area. La scelta cambia gli ACL.
2. **Chi la legge**: tutti gli operatori (come la guida) o solo IT + revisori? La wiki sintetizza
   documenti che hanno ACL diverse: una pagina può rivelare l'esistenza di un documento riservato.
   Serve una regola: la wiki non cita documenti che il lettore non può aprire, oppure si tiene per area.
3. **Chi la scrive**: solo il Knowledge Manager, o anche i bot d'area? Oggi la skill assume il KM.
4. **`llmwiki` CLI**: se il pilot chiede review gate e OKF, valutarlo; per ora la skill Hermes basta.
5. **`qmd`**: aggiungerlo quando la wiki supera ~100 fonti, non prima.
