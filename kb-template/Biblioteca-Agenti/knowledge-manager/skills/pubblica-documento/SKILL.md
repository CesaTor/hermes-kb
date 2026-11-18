---
name: pubblica-documento
description: Pubblicare una nuova versione di un documento d'area con archivio e registro, senza stati a metà.
version: 0.1.0
author: ReQurv
license: LicenseRef-ReQurv-Proprietary
metadata:
  hermes:
    tags: [documenti, versioni, archivio, registro, it]
    category: knowledge
    related_skills: [mappa-kb, llm-wiki]
---

# Pubblicare un documento

La pubblicazione è **una procedura sola**, non una serie di passi improvvisati. Si lancia solo a
pubblicazione approvata, mai alla fine di ogni interazione. Se un passo fallisce, la procedura si
ferma e non lascia stati a metà.

## Prima: le 4 porte

1. **Dove** — è un'area che l'operatore può scrivere? (Lo decide il cloud.)
2. **Cosa** — è un documento vivente (versionato) o un record (immutabile)?
3. **Come** — leggi la versione in forza *prima* di scrivere: `X.0` se il contenuto cambia in modo
   sostanziale, `X.1` se è una correzione.
4. **Record** — se è un record, si **crea** e non si modifica mai.

Poi mostra l'anteprima in chat e aspetta l'approvazione:

```text
<titolo> · azione (nuova / nuova versione / archivio) · <area> · a chi sarà visibile
```

L'ultimo campo è obbligatorio: è l'unico punto in cui i permessi si vedono.

## La procedura

1. **Trova la versione in forza.** In `NN-Area/documenti/` deve esserci **una sola** versione per
   titolo (il titolo comprende l'estensione). Se ce ne sono due, o se trovi file con «conflicted
   copy»/«conflitto» nel nome, o un file aperto (`~$…`, `.~lock.…`), **fermati e segnala**.
2. **Calcola la versione nuova** (`X.0` o `X.1`) e il nome: `titolo_vX.Y.estensione`.
3. **Scrivi il nuovo file** in `documenti/`.
4. **Sposta la versione precedente** in `Archivio/`, con la data nel nome se serve. Mai eliminare.
5. **Crea la voce di registro** in `90-Sistema/Registro-Pubblicazioni/`:
   nome `AAAAMMGG-HHMMSS_<autore>_<titolo>-<estensione>.md`, un file nuovo per ogni pubblicazione
   (non modificare quelli esistenti), contenuto:

   ```markdown
   # Pubblicazione
   - Data: AAAA-MM-GG HH:MM
   - Titolo: <titolo>
   - Autore: <operatore>
   - Versione: X.Y
   - Area: NN-Area
   - Origine: bot | modifica manuale
   - Impronta: <sha256 del file>
   - Sintesi: <una riga>
   ```

   Impronta: `python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <file>`
6. **Verifica**: in `documenti/` c'è una sola versione per titolo; la precedente è in `Archivio/`;
   la voce di registro esiste e ha l'impronta giusta. Riporta l'esito.
7. Se il registro **non è scrivibile**, la pubblicazione non è conclusa: segnala e fermati
   (principio: fermati, segnala, chiedi).

## Modifica manuale dichiarata

Se l'operatore dice «ho modificato a mano il documento X»:

1. verifica che il file sia davvero diverso dall'ultima impronta registrata;
2. archivia la versione precedente;
3. crea la voce di registro con `Origine: modifica manuale`, la nuova impronta e la nota;
4. l'operatore decide se è `X.0` o `X.1`.

## Record

Un record (contratto, fattura, approvazione) si crea con un nome che non collide e **non si
modifica né si elimina**. Se serve correggerlo, si crea un nuovo record che cita il precedente.

## Non fare

- Non pubblicare senza anteprima e approvazione.
- Non modificare un file esistente in `documenti/`: si crea la versione nuova e si archivia la
  vecchia.
- Non toccare `Record/`.
- Non lasciare un file in `documenti/` senza voce di registro.
- Non chiamare «registrata» una pubblicazione il cui registro è fallito.
