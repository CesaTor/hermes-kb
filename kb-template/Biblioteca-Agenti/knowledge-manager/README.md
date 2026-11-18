# Knowledge Manager

Bot di libreria per il reparto IT: tiene viva la **wiki aziendale** (`Wiki/` alla radice della KB) a
partire dai documenti in forza, dai record e dalle conoscenze raccolte dagli operatori.

## Cosa sa fare

| Skill | Cosa fa |
|---|---|
| `llm-wiki` | Il pattern LLM-wiki adattato alla KB: ingest, query, lint, provenienza, indice e log. Include `scripts/wiki_lint.py` |
| `mappa-kb` | Dove stanno le cose, chi scrive cosa, quale fonte vince, nomi e versioni |
| `knowledge-ingest` | Integra `Operatori/<nome>/proposte/knowledge/` nella wiki e nei documenti, poi chiude il file |
| `pubblica-documento` | Il canone: 4 porte, anteprima, LIFO, Archivio, registro con impronta |

La wiki è **derivata**: sintetizza e collega le fonti, non le sostituisce e non entra mai in
`documenti/`.

## Installazione

1. Copia questa cartella in `Biblioteca-Agenti/knowledge-manager/` della KB (o pubblicala come
   pacchetto certificato con il tuo flusso).
2. Aggiungi `knowledge-manager` al `bots.yaml` dell'area IT.
3. Sulla macchina dell'IT: `hermes kb install knowledge-manager`.
4. Nel `.autorizzazioni.yaml` dell'operatore IT:

   ```yaml
   operator: it
   ruolo: it
   ```

   Senza `ruolo: it` il bot non riceve i tool `kb_proposals` e `kb_updates`.
5. La wiki vive in `<radice>/Wiki/`. Alla prima conversazione il bot la inizializza (chiedendo
   dominio e perimetro) oppure legge quella esistente.

## Cosa serve lato cloud

- L'IT deve poter **leggere** tutte le cartelle `Operatori/*/proposte/` e **cancellare** i file
  `knowledge/` che ha integrato (la cancellazione è il segnale di «integrata»). Se la cancellazione
  non è concessa, il bot li sposta in `proposte/knowledge/Archivio/` con una nota.
- `Wiki/` deve essere scrivibile dall'IT; la lettura dipende dal perimetro scelto (tutti o solo
  IT/revisori). Una pagina che cita un documento riservato ne rivela l'esistenza: il perimetro va
  deciso prima.

## Controllo della wiki

```sh
python3 skills/llm-wiki/scripts/wiki_lint.py "<radice>/Wiki" --json
```

Esce con `2` se ci sono errori (wikilink rotti, frontmatter incompleto, fonti sparite), `0`
altrimenti. Gli avvisi (pagine fuori indice, orfane, troppo lunghe, fonti cambiate) non bloccano.

## Attribuzione

`skills/llm-wiki` è un adattamento della skill MIT `llm-wiki` di Hermes Agent; vedi
`skills/llm-wiki/NOTICE.md`.

## Versioni

`version` in `distribution.yaml` è il numero che il plugin confronta per aggiornare il bot. Alza la
patch a ogni modifica certificata; per una modifica sostanziale, usa la minor.
