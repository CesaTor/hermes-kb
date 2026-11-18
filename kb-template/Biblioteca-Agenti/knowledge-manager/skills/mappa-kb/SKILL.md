---
name: mappa-kb
description: Dove stanno le cose nella KB aziendale, chi scrive cosa e quale fonte vince.
version: 0.1.0
author: ReQurv
license: LicenseRef-ReQurv-Proprietary
metadata:
  hermes:
    tags: [kb, struttura, permessi, convenzioni]
    category: knowledge
---

# Mappa della KB

Usa questa skill per rispondere a «dove sta…?», per sapere dove puoi scrivere e per non confondere
una fonte con una sintesi. La radice dell'organizzazione è la cartella che contiene
`Biblioteca-Agenti/` (nel prompt: `$SECOND_BRAIN_ROOT`).

## L'albero

```text
<radice>/
├─ Biblioteca-Agenti/<bot>/     # pacchetti certificati: distribution.yaml, SOUL.md, skills/, config.yaml
├─ 00-Anima-Aziendale/          # identità, valori, visione (A0/A1)
├─ NN-Area/                     # una per funzione aziendale (01-Strategia … 10-Amministrativa)
│  ├─ documenti/                # documenti attivi, UNA versione in forza per titolo
│  ├─ Proposte/                 # modifiche in attesa (sotto-cartelle per proponente)
│  ├─ Archivio/                 # versioni precedenti, mai eliminate
│  ├─ Record/                   # record immutabili (contratti, fatture, approvazioni)
│  ├─ indice.md                 # mappa dei collegamenti, curata dal proprietario/revisore
│  └─ bots.yaml                 # bot abilitati nell'area
├─ 90-Sistema/                  # governance: Tabella-Permessi.md, Registro-Pubblicazioni/, guida
├─ Operatori/<nome>/            # spazio personale
│  ├─ skills/                   # skill personali (sincronizzate)
│  ├─ proposte/<bot>/           # SOUL e skill modificate dall'operatore
│  └─ proposte/knowledge/       # conoscenze raccolte, da integrare
├─ SETUP/                       # motore (ristretta): RUNBOOK, autorizzazioni, istruzioni
└─ Wiki/                        # la wiki aziendale (la scrive il Knowledge Manager)
```

`Wiki/` è **derivata**: sintetizza e collega le fonti, non le sostituisce e non entra mai in
`documenti/`.

## Chi scrive cosa

| Cartella | Scrive | Legge |
|---|---|---|
| `Biblioteca-Agenti/<bot>/` | il revisore IT | gli utenti dell'area del bot + IT |
| `NN-Area/documenti/` | gli utenti dell'area, tramite la skill `pubblica-documento` | gli utenti dell'area |
| `NN-Area/Archivio/` | la skill `pubblica-documento` (solo spostamenti) | gli utenti dell'area |
| `NN-Area/Record/` | gli utenti dell'area, solo creando | gli utenti dell'area |
| `NN-Area/indice.md` | proprietario/revisore | gli utenti dell'area |
| `90-Sistema/` | IT (tabella, guida); chi pubblica (registro) | tutti |
| `Operatori/<nome>/` | l'operatore e i suoi bot | l'operatore, IT |
| `Wiki/` | il Knowledge Manager | dipende dal perimetro deciso |

I permessi veri li dà il cloud: se una cartella non è nella tua copia locale, non esiste per te.

## Nomi e versioni

- Documento in forza: `titolo_vX.Y.estensione` — `X.0` contenuto nuovo, `X.1` correzione. Il titolo
  comprende l'estensione: `piano.docx` e `piano.xlsx` sono documenti diversi.
- Archivio: stessa struttura, con la data nel nome quando serve.
- Registro pubblicazioni: `AAAAMMGG-HHMMSS_<autore>_<titolo>-<estensione>.md`, un file per
  pubblicazione, mai modificato.
- Proposte di un operatore: `Operatori/<nome>/proposte/<bot>/{SOUL.md, skills/…, proposal.yaml}`.
- Conoscenze: `Operatori/<nome>/proposte/knowledge/AAAAMMGG-HHMMSS-<slug>.md`.

## Quale fonte vince

1. **Documento in forza** in `documenti/` (una sola versione per titolo) — per i documenti.
2. **Record** in `Record/` — immutabili: non si correggono, se ne crea uno nuovo.
3. **Wiki** — sintesi derivata: utile per capire e navigare, non è la fonte ufficiale.
4. **Proposte e conoscenze** — materiale in attesa: non sono policy finché non sono integrate.

Se due file in `documenti/` hanno lo stesso titolo, **fermati e segnala**: la regola LIFO è rotta.

## Cosa non tocchi

`Record/`, i documenti in forza, `Archivio/`, `90-Sistema/` e le cartelle personali degli operatori
oltre alla lettura. Per pubblicare o correggere un documento usi solo `pubblica-documento`; per le
conoscenze, `knowledge-ingest`.
