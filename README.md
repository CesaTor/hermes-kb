# ReQurv KB — plugin per Hermes

Collega una installazione **ufficiale** di Hermes (CLI e Desktop) alla KB aziendale sincronizzata
(Nextcloud, Drive) e installa i bot della **Biblioteca-Agenti** come profili Hermes. Sostituisce
la distribuzione ReAgent: niente fork, niente installer propri. Il provider (ReQurv Hive) lo
configura ReQurv Bridge; il plugin lo copia nei bot che installa.

## Cosa fa

| Funzione | Dove |
|---|---|
| Collegamento della KB: più cartelle ("isole"), operatore, cartella personale | `requrv_kb/connection.py` |
| Catalogo: unione dei `bots.yaml` delle aree leggibili (`*` = tutti; nessuna lista = vuoto) | `requrv_kb/library.py` |
| Installazione, aggiornamento, sync a ogni avvio dell'app, rollback, duplica come bot personale | `requrv_kb/library.py` sopra `hermes profile install/update/create` |
| `config_managed`: chiavi di `config.yaml` che la libreria tiene allineate | `requrv_kb/profile_config.py` |
| Backup prima di ogni aggiornamento (ultime 2 versioni), proposte archiviate | `requrv_kb/ledger.py`, `library.py` |
| Bot di libreria non modificabili dall'agente (file, skill, attività pianificate) | `requrv_kb/locks.py` (hook `pre_tool_call`) |
| Provider del coordinatore copiato nel bot (modello, endpoint `providers.<nome>`, chiave) | `requrv_kb/profile_config.py` |
| Percorsi della KB nel prompt di ogni nuova sessione | `requrv_kb/prompt.py` |
| File non scaricati dal cloud rilevati prima di copiare | `requrv_kb/cloud_files.py` |
| Pagina **Libreria** nell'app Desktop, impostazioni, sync all'avvio | `desktop/plugin.js` + `dashboard/plugin_api.py` |
| Comandi `hermes kb ...` e `/kb ...` in chat, skill `requrv-kb:setup` | `requrv_kb/cli.py` |

Limiti noti (accettati): le schermate di impostazioni di Hermes non bloccano le modifiche a un bot
di libreria (le annulla il prossimo aggiornamento); un comando di terminale può modificare file;
la pagina Libreria risponde quando il profilo attivo nell'app è il coordinatore o un bot di libreria.

## Installazione

1. Copia questa cartella in `~/.hermes/plugins/requrv-kb` (Windows: `%LOCALAPPDATA%\hermes\plugins\requrv-kb`
   o la cartella `plugins` dell'installazione Hermes).
2. Abilita il lato agente nel profilo coordinatore: `hermes plugins enable requrv-kb`.
3. Riavvia Hermes Desktop, poi **Capabilities → Plugins → ReQurv KB → attiva** (il lato Desktop di
   un pacchetto parte disattivato).
4. Apri **Libreria** nella barra laterale e collega le cartelle, oppure:

```sh
hermes kb connect --root "/percorso/Biblioteca-Agenti" --root "/percorso/01-Marketing" --personal "/percorso/mario"
hermes kb list
hermes kb install marketing
```

I bot installati compaiono nella sezione **Bots**. Le modifiche valgono dalla conversazione successiva.

## Struttura della KB

```text
Biblioteca-Agenti/<bot>/   distribution.yaml, SOUL.md, skills/, config.yaml (opz.), cron/ (opz.)
NN-Area/bots.yaml          bots: [marketing, ...]
Operatori/<nome>/          cartella personale: skills/, proposte/<bot>.md
```

`distribution.yaml`: `name`, `version`, `description`, opzionali `config_managed: [chiave.puntata, ...]`,
`proposals_resolved` / `proposals_rejected`. Un pacchetto può contenere solo i file di un bot: un
`.env`, una memoria o una chat nel pacchetto ne bloccano l'installazione.

## Test

Contro un checkout di Hermes ufficiale (nessuna richiesta al provider, home temporanee):

```sh
cd <hermes-agent> && PYTHONPATH=$PWD <python dell'ambiente di test> -m pytest /percorso/requrv-kb-plugin/tests -q
```
