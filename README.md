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
| Installazione, aggiornamento, rollback, duplica come bot personale | `requrv_kb/library.py` sopra `hermes profile install/update/create` |
| `config_managed`: chiavi di `config.yaml` che la libreria tiene allineate | `requrv_kb/profile_config.py` |
| Backup prima di ogni aggiornamento (ultime 2 versioni), proposte archiviate | `requrv_kb/ledger.py`, `library.py` |
| Bot di libreria non modificabili dall'agente (file, skill, attività pianificate) | `requrv_kb/locks.py` (hook `pre_tool_call`) |
| Provider del coordinatore copiato nel bot (modello, endpoint `providers.<nome>`, chiave) | `requrv_kb/profile_config.py` |
| Percorsi della KB nel prompt di ogni nuova sessione | `requrv_kb/prompt.py` |
| Proposte dell'operatore: estendono il SOUL del bot dalla sessione successiva, finché l'IT non le recepisce | `requrv_kb/prompt.py`, `library.py` |
| File non scaricati dal cloud rilevati prima di copiare | `requrv_kb/cloud_files.py` |
| Allineamento automatico: installa i bot abilitati che mancano, aggiorna, rimuove quelli non più consentiti (ogni 30 min, all'avvio, a ogni nuova conversazione); `hermes kb reconcile` | `requrv_kb/watchdog.py`, `requrv_kb/library.py` |
| Impostazioni → Plugin → **ReQurv KB**: collegamento, intervallo, ultimo controllo, «Controlla ora» (nessuna pagina Libreria) | `desktop/plugin.js` + `dashboard/plugin_api.py` |
| Comandi `hermes kb ...` e `/kb ...` in chat, skill `requrv-kb:setup` | `requrv_kb/cli.py` |

Limiti noti (accettati): le schermate di impostazioni di Hermes non bloccano le modifiche a un bot
di libreria (le annulla il prossimo aggiornamento); un comando di terminale può modificare file;
le impostazioni di ReQurv KB rispondono quando il profilo attivo nell'app è il coordinatore o un bot di libreria.

## Installazione

Serve Hermes (CLI o Desktop) con un provider già configurato nel profilo principale (per ReQurv
Hive lo fa ReQurv Bridge). Poi, a scelta:

- **Un clic** (Hermes Desktop): [installa ReQurv KB](hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1)
  — link `hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1`, conferma nel dialogo di Hermes.
- **Desktop:** Capabilities → Plugins → Install from Git → `https://github.com/CesaTor/hermes-kb`.
- **Terminale:** `hermes plugins install CesaTor/hermes-kb --enable`

Installando da Hermes Desktop (link `hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1` oppure
Install from Git con enable) si accende anche la parte Desktop: riavvia l'app e basta. Solo
l'installazione da terminale (`hermes plugins install … --enable`) lascia spenta la parte Desktop: per
usarla, riavvia Hermes Desktop e attiva **ReQurv KB** in Capabilities → Plugins. Aggiornamenti:
`hermes plugins update requrv-kb`.

**Senza la parte Desktop** funzionano: allineamento automatico (watchdog, ogni 30 minuti mentre Hermes è
aperto), blocchi dei bot di libreria, percorsi della KB nel prompt, comandi `hermes kb ...` e `/kb ...`,
skill `requrv-kb:setup`. **Serve la parte Desktop** per: la pagina Impostazioni → Plugin → ReQurv KB, il
controllo all'avvio dell'app e il layout «ReQurv minimal» (id `requrv-kb:minimal`, applicabile anche dal
modello con lo strumento `set_theme`).

Per far fare l'installazione a Hermes, `kb-template/SETUP/AGENTS.md` va copiato nella cartella `SETUP`
della KB: Hermes semplice lo legge e segue i passi (installa il plugin, collega le cartelle, installa i
bot, applica il layout).

Collega la KB da Impostazioni → Plugin → **ReQurv KB**, oppure:

```sh
hermes kb connect --root "/percorso/Biblioteca-Agenti" --root "/percorso/01-Marketing" --personal "/percorso/mario"
hermes kb list
hermes kb install marketing
```

I bot installati compaiono nella sezione **Bots**. Le modifiche valgono dalla conversazione successiva.

## Allineamento automatico

Mentre Hermes (Desktop o gateway) è aperto, il plugin allinea i bot alla libreria **ogni 30 minuti**
(impostabile, minimo 5, in Impostazioni → Plugin → ReQurv KB), **all'avvio dell'app** e **a ogni nuova
conversazione** con un bot di libreria (questa solo per aggiornare quel bot). «Controlla ora» o
`hermes kb reconcile` lo fanno subito. Un controllo:

- **installa** ogni bot abilitato dalle aree e non installato: un bot eliminato dall'utente torna entro
  un intervallo, **nuovo e senza le sue chat e la sua memoria** (il registro, i backup e le chat stanno
  nella cartella del profilo e se ne vanno con lui);
- **aggiorna** i bot la cui versione è cambiata;
- **rimuove** i bot aziendali non più consentiti, insieme a chat e memoria, con `hermes profile delete`:
  solo quelli installati dalla libreria (con il suo registro), mai i bot creati o duplicati dall'utente;
  solo se tutte le cartelle e gli elenchi `bots.yaml` sono stati letti; e solo al **secondo controllo
  consecutivo** che li trova non consentiti (il primo li segna come `pending-removal`). Se una cartella
  non è leggibile (rete assente, Drive non montato, file non scaricati) non si rimuove nulla; un bot in uso
  viene riprovato al controllo successivo.

I risultati (`installed`, `updated`, `unchanged`, `error`, `source-unavailable`, `pending-removal`,
`removed`) sono nei log e in Impostazioni. Ogni processo Hermes avvia un thread che guarda ogni 5 minuti,
ma l'esecuzione è decisa da un **lease valido per tutto il computer** in `<radice Hermes>/plugin-data/requrv-kb/watchdog/`:
un file con l'ora dell'ultimo controllo e un lock di file non bloccante (`fcntl` su POSIX, `msvcrt` su
Windows), così gira al massimo un controllo alla volta e uno per intervallo, qualunque sia il numero di
profili o processi. Il thread aspetta 60 s prima del primo controllo, quindi un comando `hermes ...`
di breve durata non fa nulla.

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
