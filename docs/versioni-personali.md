# Versioni personali delle skill, memoria e reparto IT

Data: 18 novembre 2026. Implementato in questa repository, verificato contro Hermes **upstream**
(`upstream/main`, non il fork ReAgent).

## Le decisioni

| Tema | Scelta |
|---|---|
| Prodotto | Hermes-first: il plugin è il prodotto, nessun server; la KB sincronizzata è il canale |
| SOUL di libreria | Certificato e sovrascritto a ogni update; per un'identità propria si duplica il bot |
| Skill di libreria | Modificabili dall'operatore, live nel profilo, copiate in `proposte/` |
| `config.yaml` gestito, metadati, cron | Restano rifiutati: la libreria li riallinea |
| Skill nuove | Nascono in `Operatori/<nome>/skills` via `skills.create_dir` |
| Conflitto su una skill | Si chiede in chat; «tengo la mia» = la copia personale resta com'è |
| Rimozione automatica dei bot | Eliminata: un bot non più abilitato resta, marcato `not-allowed` |
| Proposte chiuse | Accettata = cancellata dal pacchetto; rifiutata = in `proposte/Archivio/` con motivo |
| Knowledge | Solo l'autore la legge; cattura passiva con proposta Markdown |
| Memoria built-in | `MEMORY.md`/`USER.md` per profilo; backup in `Operatori/<nome>/memoria/<bot>/` |
| Holographic | Opzionale, SQLite per profilo; il DB entra nello stesso backup, non nella wiki |
| Autorizzazioni | `.autorizzazioni.yaml` nascosto nella cartella personale, scritto dall'IT |
| Due macchine | Ci si affida al sync; copie in conflitto fermano il bot |

## File

Nel profilo (locale, mai sincronizzato):

- `.library-owned.json` — cosa possiede la libreria (già esistente);
- `.requrv-kb-personal.json` — per ogni skill: `base_hash` (certificato all'ultimo sync),
  `live_hash`, `personal_hash`, `base_version`, `pending`;
- `.requrv-kb-incoming/<versione>/` — la nuova versione certificata messa da parte durante un
  conflitto, pronta per «prendo la nuova».

Nella cartella personale (condivisa):

```text
Operatori/<nome>/
├─ .autorizzazioni.yaml
├─ skills/                          # create_dir
├─ memoria/<bot>/                   # MEMORY.md, USER.md, memory_store.db (Holographic)
└─ proposte/
   ├─ knowledge/                    # un .md per conoscenza (cattura passiva)
   └─ <bot>/
      ├─ proposal.yaml              # bot, operatore, base_version, aggiornato_il, hash dei file
      └─ skills/<nome>/             # cartella intera (SKILL.md + scripts/ + asset)
```

## Flussi

**Scrittura.** `pre_tool_call` blocca il `SOUL.md` dei bot di libreria e rimanda al clone personale.
Lascia passare le skill; `on_skill_lifecycle` copia la skill in `proposte/<bot>/` e aggiorna gli
hash. La modifica è già live: il bot la usa dalla conversazione successiva.

**Memoria.** `post_tool_call` sul tool `memory`, più `on_session_start`/`on_session_end`, copiano
`memories/MEMORY.md`, `memories/USER.md` e, se presente, `memory_store.db` di Holographic in
`Operatori/<nome>/memoria/<bot>/`. La copia è solo se il contenuto è cambiato. Non è pubblicazione:
l'IT la legge secondo le ACL e decide se promuovere qualcosa nella wiki.

**Update.** Il controllo della libreria parte all'avvio di Hermes e a ogni nuova conversazione con
un bot; non c'è un timer periodico. `SOUL.md` viene sempre aggiornato dal pacchetto. `personal.plan`
legge gli hash delle skill prima che Hermes scriva. Poi, per ogni skill:

| Stato | Cosa succede |
|---|---|
| `clean` | si aggiorna il certificato |
| `reapply` (personale, certificato invariato) | la copia personale torna sopra, in silenzio |
| `conflict` (personale, certificato cambiato) | resta live la personale; la nuova è conservata in locale e la domanda va in `pending` |

La sezione di prompt `requrv-kb.personal` porta al bot il diff (`-` la tua, `+` la nuova) e le
istruzioni per chiedere. La risposta passa dal tool `kb_personal` o da `hermes kb resolve`.

**Decisione.** `keep` mantiene la skill personale live; `take` applica la nuova versione conservata
e cancella la copia da `proposte/`. In entrambi i casi `base_version` diventa la nuova, quindi la
domanda non si ripete finché la libreria non cambia di nuovo.

## Autorizzazioni

`.autorizzazioni.yaml` nella cartella personale:

```yaml
operator: mario
bots: [marketing, finanza-controllo]   # assente o "*" = tutti i visibili
ruolo: operatore                       # `it` abilita i tool di revisione
```

Se manca o è illeggibile non restringe nulla. Il catalogo è l'intersezione fra i `bots.yaml`
visibili e questo elenco; `install` rifiuta con un messaggio che nomina l'IT.

## Reparto IT

Un operatore con `ruolo: it` riceve i tool `kb_proposals` e `kb_updates` (schema in
`__init__.py`, implementazione in `requrv_kb/it.py`, skill `revisione-proposte`).

| Azione | Effetto |
|---|---|
| `list` | proposte e conoscenze di tutti gli operatori leggibili, con `base_version` |
| `show` | diff proposta ↔ pacchetto, file per file |
| `accept` | senza `confirm` restituisce il piano; con `confirm` scrive nei file del pacchetto, alza la patch (`1.4.0 → 1.4.1`) e cancella la proposta |
| `reject` | sposta in `proposte/Archivio/<bot>-<data>/` con `RIFIUTATA.md` e il motivo |
| `updates` | cosa la libreria offre e `apply` per installare/aggiornare su questa macchina |

`accept` segnala `stale` quando la proposta parte da una versione diversa da quella attuale del
pacchetto: l'IT può decidere, ma lo sa.

## Cosa manca

1. **Cattura automatica delle conoscenze** a fine turno (LLM + transcript): il punto più delicato,
   da fare con un suo spike. L'elenco IT (`proposte/knowledge/`) c'è già.
2. **Pannello Desktop** per conflitti e revisione (oggi solo CLI e tool).
3. **Delezione di una skill certificata**: oggi rifiutata; una proposta non sa rappresentarla.
4. **Dedup delle conoscenze** dopo l'integrazione (la cancellazione è il segnale, ma un fatto può
   essere riestratto).
5. **ACL cloud** per far leggere all'IT tutte le cartelle personali: configurazione, non codice.

## Verifica

Tutti i test (98) girano contro Hermes upstream in un worktree separato:

```sh
cd <checkout upstream> && PYTHONPATH=$PWD python3 -m pytest <plugin>/tests -q
```

`tests/test_personal.py` copre mirror, riapplicazione silenziosa, conflitto, `keep`/`take`,
autorizzazioni e `not-allowed`; `tests/test_it.py` copre elenco, diff, accettazione con bump,
rifiuto con archivio, `updates` e il gating dei tool sul ruolo IT.
