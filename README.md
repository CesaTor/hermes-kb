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
| Proposte dell'operatore: estendono il SOUL del bot dalla sessione successiva, finché l'IT non le recepisce | `requrv_kb/prompt.py`, `library.py` |
| File non scaricati dal cloud rilevati prima di copiare | `requrv_kb/cloud_files.py` |
| Pagina **Libreria** nell'app Desktop, impostazioni, sync all'avvio | `desktop/plugin.js` + `dashboard/plugin_api.py` |
| Comandi `hermes kb ...` e `/kb ...` in chat, skill `requrv-kb:setup` | `requrv_kb/cli.py` |

Limiti noti (accettati): le schermate di impostazioni di Hermes non bloccano le modifiche a un bot
di libreria (le annulla il prossimo aggiornamento); un comando di terminale può modificare file;
la pagina Libreria risponde quando il profilo attivo nell'app è il coordinatore o un bot di libreria.

## Installazione

Serve Hermes (CLI o Desktop) con un provider già configurato nel profilo principale (per ReQurv
Hive lo fa ReQurv Bridge). Poi, a scelta:

- **Un clic** (Hermes Desktop): [installa ReQurv KB](hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1)
  — link `hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1`, conferma nel dialogo di Hermes.
- **Desktop:** Capabilities → Plugins → Install from Git → `https://github.com/CesaTor/hermes-kb`.
- **Terminale:** `hermes plugins install CesaTor/hermes-kb --enable`

Poi, una volta sola: riavvia Hermes Desktop e attiva **ReQurv KB** in Capabilities → Plugins (il
lato Desktop di un plugin parte spento). Aggiornamenti: `hermes plugins update requrv-kb`.

Collega la KB dalla pagina **Libreria** nella barra laterale, oppure:

```sh
hermes kb connect --root "/percorso/Biblioteca-Agenti" --root "/percorso/01-Marketing" --personal "/percorso/mario"
hermes kb list
hermes kb install marketing
```

I bot installati compaiono nella sezione **Bots**. Le modifiche valgono dalla conversazione successiva.

## Proposte al SOUL

Il SOUL di un bot di libreria non si modifica, ma l'utente non ha bisogno di un bot personale:

1. Quando l'utente chiede un cambiamento stabile (tono, regole, compiti), il bot lo scrive come
   proposta in `Operatori/<operatore>/proposte/<bot>.md`, un blocco `## <id>` per proposta.
2. Dalla conversazione successiva il bot applica quel file come estensione del proprio SOUL.
3. L'IT legge le proposte dalla cartella dell'operatore, inserisce quelle buone nel SOUL della
   libreria, alza la `version` e ne elenca gli id in `proposals_resolved` (o `proposals_rejected`).
4. Al riavvio dell'app tutti i bot si aggiornano; i blocchi valutati passano in
   `proposte/Archivio/` con l'esito, e il file dell'operatore resta con quelli ancora aperti.

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
