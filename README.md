# ReQurv KB — plugin per Hermes

Collega una installazione **ufficiale** di Hermes (CLI e Desktop) alla KB aziendale sincronizzata
(Nextcloud, Drive) e installa i bot della **Biblioteca-Agenti** come profili Hermes. Sostituisce
la distribuzione ReAgent: niente fork, niente installer propri. Il provider (ReQurv Hive) lo
configura ReQurv Bridge; il plugin lo copia nei bot che installa.

Guida completa all'installazione, aggiornamento e installazione guidata da Hermes:
[INSTALL.md](INSTALL.md).

## Cosa fa

| Funzione | Dove |
|---|---|
| Collegamento della KB: più cartelle ("isole"), operatore, cartella personale | `requrv_kb/connection.py` |
| Catalogo: unione dei `bots.yaml` delle aree leggibili (`*` = tutti; nessuna lista = vuoto) | `requrv_kb/library.py` |
| Installazione, aggiornamento, rollback, duplica come bot personale | `requrv_kb/library.py` sopra `hermes profile install/update/create` |
| `config_managed`: chiavi di `config.yaml` che la libreria tiene allineate | `requrv_kb/profile_config.py` |
| Backup prima di ogni aggiornamento (ultime 2 versioni) e rollback | `requrv_kb/ledger.py`, `library.py` |
| SOUL e skill del bot modificabili dall'operatore: restano live e vengono copiati in `proposte/` | `requrv_kb/locks.py`, `mirror.py` |
| Chiavi gestite di `config.yaml`, metadati del pacchetto e cron: restano bloccati | `requrv_kb/locks.py` (hook `pre_tool_call`) |
| Versioni personali: a ogni release che tocca un file modificato si chiede in chat «tieni la tua o prendi la nuova» | `requrv_kb/personal.py`, `prompt.py`, tool `kb_personal` |
| Provider del coordinatore copiato nel bot (modello, endpoint `providers.<nome>`, chiave) | `requrv_kb/profile_config.py` |
| Percorsi della KB nel prompt di ogni nuova sessione | `requrv_kb/prompt.py` |
| File non scaricati dal cloud rilevati prima di copiare | `requrv_kb/cloud_files.py` |
| Allineamento automatico: installa i bot abilitati che mancano e aggiorna quelli cambiati (all'avvio e a ogni nuova conversazione); `hermes kb reconcile`. Non rimuove mai un bot | `requrv_kb/watchdog.py`, `requrv_kb/library.py` |
| Autorizzazioni per operatore: `.autorizzazioni.yaml` nella cartella personale restringe i bot installabili | `requrv_kb/authz.py` |
| Cattura passiva di fatti e pratiche riutilizzabili durante le conversazioni con i bot di libreria | `requrv_kb/knowledge_capture.py`, tool `kb_capture_knowledge` |
| Revisione IT: proposte e conoscenze di tutti gli operatori, differenze, accetta/rifiuta, aggiornamenti | `requrv_kb/it.py`, tool `kb_proposals`/`kb_updates`, skill `revisione-proposte` |
| Impostazioni → Plugin → **ReQurv KB**: collegamento, ultimo controllo, «Controlla ora» (nessuna pagina Libreria) | `desktop/plugin.js` + `dashboard/plugin_api.py` |
| Tema ReQurv (colori e font Syne incorporati, licenza OFL in `desktop/OFL-syne.txt`), scelto una sola volta alla prima attivazione; «Tema ReQurv» in Impostazioni lo riapplica | `desktop/plugin.js` |
| Layout `requrv-kb:minimal` e voci del menu laterale nascoste (Messaging, Artifacts, Scheduled jobs, Kanban) | `desktop/plugin.js` |
| Comandi `hermes kb ...` e `/kb ...` in chat, skill `requrv-kb:setup` | `requrv_kb/cli.py` |

Limiti noti (accettati): le schermate di impostazioni di Hermes non passano dai blocchi del plugin (ma
l'aggiornamento successivo riallinea i file di libreria); un comando di terminale può modificare file;
le impostazioni di ReQurv KB rispondono quando il profilo attivo nell'app è il coordinatore o un bot di
libreria.

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

**Senza la parte Desktop** funzionano: allineamento automatico (all'avvio e a ogni nuova conversazione), blocchi dei bot di libreria, percorsi della KB nel prompt, comandi `hermes kb ...` e `/kb ...`, skill `requrv-kb:setup`. **Serve la parte Desktop** per: la pagina Impostazioni → Plugin → ReQurv KB, il
controllo all'avvio dell'app, il tema ReQurv, il layout «ReQurv minimal» (id `requrv-kb:minimal`, applicabile
anche dal modello con lo strumento `set_theme`) e la scelta delle voci del menu laterale.

Per far fare l'installazione a Hermes, `kb-template/SETUP/AGENTS.md` va copiato nella cartella `SETUP`
della KB: Hermes semplice lo legge e segue i passi (installa il plugin, collega le cartelle, installa i
bot, applica il layout). Il flusso completo, con verifica e problemi comuni, è in
[INSTALL.md](INSTALL.md).

Collega la KB da Impostazioni → Plugin → **ReQurv KB**, oppure:

```sh
hermes kb connect --root "/percorso/Biblioteca-Agenti" --root "/percorso/01-Marketing" --personal "/percorso/mario"
hermes kb list
hermes kb install marketing
hermes kb status            # mostra anche le versioni personali da decidere
hermes kb resolve --kind soul --choice keep
hermes kb it list           # revisione IT
hermes kb updates --apply
```

I bot installati compaiono nella sezione **Bots**. Le modifiche valgono dalla conversazione successiva.

## Versioni personali e revisione IT

Il SOUL e le skill di un bot di libreria si possono modificare: la modifica vale da subito per
quell'operatore e il plugin la copia in `Operatori/<nome>/proposte/<bot>/` (con `proposal.yaml`, la
versione del pacchetto da cui parte). Chiavi gestite di `config.yaml`, metadati e cron restano invece
rifiutati, perché la libreria li riallinea.

Quando la libreria pubblica una versione che tocca un file modificato:

- se il file certificato **non è cambiato**, la copia personale viene riapplicata in silenzio;
- se è **cambiato**, resta live la versione personale; quella nuova viene conservata e il bot, al
  primo uso, spiega le differenze e chiede se tenere la propria o prendere la nuova. La risposta si
  registra con il tool `kb_personal` (o `hermes kb resolve`) e vale per quella skill/quel SOUL fino
  alla release successiva.

Il **reparto IT** ha un proprio operatore con `ruolo: it` in `.autorizzazioni.yaml`: i tool
`kb_proposals` e `kb_updates` (e i comandi `hermes kb it …`) gli mostrano le proposte di tutti gli
operatori, le differenze con il pacchetto, e gli permettono di integrare una proposta (bump della
patch nel `distribution.yaml`, cancellazione della proposta) o di archiviarla con un motivo. La skill
`revisione-proposte` descrive il ciclo e i criteri. Le conoscenze raccolte in
`proposte/knowledge/` si integrano nella documentazione e **poi** si cancellano: la cancellazione è
il segnale di «integrata».

### Cattura passiva

Durante il normale lavoro, un bot di libreria abilitato può riconoscere un fatto operativo o una
pratica riutilizzabile e salvarli con `kb_capture_knowledge`. L'operatore continua a usare il bot
come al solito. La selezione dei fatti avviene durante il turno con lo stesso modello Hermes.
Il bot deve salvare una breve sintesi fondata ed escludere credenziali, dati personali o dei clienti,
informazioni riservate, ipotesi e dettagli utili soltanto al task in corso.

Ogni elemento va in `Operatori/<nome>/proposte/knowledge/` in Markdown, con autore, bot, data,
argomento, fonti documentali quando disponibili e riferimento alla sessione. Le fonti documentali
devono essere file nelle cartelle collegate. La scrittura è locale e il client cloud sincronizza la
cartella con i suoi permessi. La deduplicazione locale riduce le proposte ripetute: se due bot
terminano un turno nello stesso momento sullo stesso computer, il controllo e la scrittura sono
serializzati e nasce una sola proposta. La deduplicazione resta locale al computer; il controllo
finale è dell'IT nella wiki.

Il Knowledge Manager, con ruolo IT, apre la coda tramite `kb_proposals`. Verifica il fatto, la
provenienza e i permessi del pubblico della pagina, aggiorna wiki, indice e log, esegue
`wiki_lint.py` e chiude la proposta dopo la verifica. La pubblicazione resta sotto controllo IT.

### Memoria locale opzionale

Holographic è un provider di memoria Hermes con archivio SQLite per profilo. Per provarlo su un
profilo di test, installa **Holographic**, selezionalo come provider di memoria e prova `fact_store`
scrivendo un fatto sintetico e cercandolo in una nuova sessione. Controlla la versione installata
perché il catalogo può servire una release precedente. Lascia `auto_extract` disattivato durante
la prova. La ricerca di fatti scritti in italiano funziona, mentre `auto_extract` riconosce inglese,
russo, cinese e francese. La coda Markdown della KB è gestita da ReQurv.
[Documentazione Holographic](https://github.com/itpartypattaya/hermes-plugin-holographic)

### Knowledge Manager e wiki

Per il reparto IT c'è un pacchetto starter in
`kb-template/Biblioteca-Agenti/knowledge-manager/`: un bot che mantiene la wiki aziendale in
`<radice>/Wiki/` (pattern LLM-wiki: `SCHEMA.md`, `index.md`, `log.md`, pagine collegate con
provenienza verso i documenti in forza), integra le conoscenze raccolte in
`Operatori/<nome>/proposte/knowledge/` e pubblica documenti con il canone (LIFO, Archivio, registro
con impronta). Skill: `llm-wiki` (con `scripts/wiki_lint.py`), `mappa-kb`, `knowledge-ingest`,
`pubblica-documento`. Il bot riceve i tool `kb_proposals`/`kb_updates` solo con `ruolo: it`.

`.autorizzazioni.yaml` (nascosto, nella cartella personale, scritto dall'IT con ACL di sola lettura):

```yaml
operator: mario
bots: [marketing, finanza-controllo]   # assente o "*" = tutti i bot visibili
ruolo: operatore                       # `it` per il revisore
```

### Collaudo in Hermes Desktop su Windows

1. Con due utenze di prova, sincronizza la KB su Windows e assegna i permessi del documentale
   per bot, aree e cartelle operatori. Da Hermes Desktop chiedi di leggere `SETUP/AGENTS.md` e
   conferma l'installazione. Verifica che compaiano i bot consentiti.
2. Con un bot di reparto, descrivi una regola operativa di prova mentre chiedi un normale
   aiuto di lavoro. Controlla che appaia un Markdown con i metadati dell'operatore. Ripeti il
   fatto dopo il riavvio e controlla che la coda contenga ancora una sola proposta.
3. Con il Knowledge Manager e il ruolo IT, verifica che la proposta sia leggibile dopo la
   sincronizzazione, integrala nella wiki di prova e verifica che il lint passi prima di chiuderla.
   Controlla con l'operatore che la wiki sia accessibile secondo i permessi assegnati e che il
   bot di reparto non disponga delle azioni di revisione IT.

## Struttura della KB

```text
Biblioteca-Agenti/<bot>/   distribution.yaml, SOUL.md, skills/, config.yaml (opz.), cron/ (opz.)
NN-Area/bots.yaml          bots: [marketing, ...]
Operatori/<nome>/          skills/ (personali), .autorizzazioni.yaml
  proposte/<bot>/          SOUL.md, skills/<nome>/, proposal.yaml
  proposte/knowledge/      conoscenze raccolte (un .md per elemento)
Wiki/                      wiki aziendale (la scrive il Knowledge Manager)
```

`distribution.yaml`: `name`, `version`, `description`, opzionali `config_managed: [chiave.puntata, ...]`,
`proposals_resolved` / `proposals_rejected` (non usati dal flusso attuale: la proposta si chiude
integrandola o archiviandola). Un pacchetto può contenere solo i file di un bot: un `.env`, una
memoria o una chat nel pacchetto ne bloccano l'installazione.

## Tema e layout (Hermes Desktop)

**Tema.** Il plugin registra il tema «ReQurv» (palette chiara e scura dal sito, font Syne con licenza OFL)
e lo seleziona **una volta**, alla prima attivazione della parte Desktop; lo ricorda nello storage del
plugin, quindi chi sceglie poi un altro tema non viene mai sovrascritto. Impostazioni → Plugin →
ReQurv KB → «Tema ReQurv» lo riapplica. I font sono incorporati in `desktop/plugin.js` (base64) e
iniettati in un tag `<style>`: un plugin non ha file statici da servire.

**Layout `requrv-kb:minimal`.** Un layout di plugin è solo l'albero dei pannelli; Hermes apre ogni pannello
che l'albero nomina e un plugin non può dichiarare pannelli «a riposo». L'albero nomina quindi solo:
Bot (da solo, a sinistra), chat (al centro), Files e Attività pianificate (a destra, come barre chiuse).
Sessions, revisione e terminale non sono nominati: Hermes li riprende dal layout precedente così come sono.

- Sessions è un pannello che si può solo nascondere e non c'è modo pubblico di nasconderlo da un plugin:
  riappare come scheda accanto a Bot (l'utente la nasconde dal menu della scheda, clic destro).
- Revisione e terminale non si aprono (non sono nominati). Possono però comparire come schede nella
  colonna di sinistra se il layout precedente li teneva in zone proprie; il terminale chiuso resta una
  scheda inattiva.
- Files e Attività pianificate restano chiusi solo se Attività pianificate è registrato quando si applica
  il layout (Bot Mode attivo); altrimenti l'apertura di Files riapre la colonna destra e l'utente le richiude.
- Voci del menu laterale nascoste (contributo pubblico `sidebarNav.prefs`, finisce se il plugin si spegne):
  Messaging, Artifacts, Scheduled jobs, Kanban. Restano Nuova sessione e Capabilities (non nascondibile).

## Allineamento automatico

Il plugin allinea i bot alla libreria **all'avvio di Hermes** e **a ogni nuova conversazione** con un
bot di libreria (questa solo per aggiornare quel bot). «Controlla ora» in Impostazioni → Plugin →
ReQurv KB, oppure `hermes kb reconcile`, lo fanno subito. **Non c'è un controllo periodico e non c'è
un thread in background.**

Un controllo:

- **installa** ogni bot abilitato dalle aree e non installato: un bot eliminato dall'utente torna
  all'avvio o alla conversazione successiva, **nuovo e senza le sue chat e la sua memoria** (il
  registro, i backup e le chat stanno nella cartella del profilo e se ne vanno con lui);
- **aggiorna** i bot la cui versione è cambiata;
- **segnala** come `not-allowed` i bot che le aree non abilitano più, senza toccarli: chat, memoria e
  profilo restano dove sono, e l'operatore decide se eliminarli.

I risultati (`installed`, `updated`, `unchanged`, `error`, `source-unavailable`, `not-allowed`) sono
nei log e in Impostazioni. Un **lease valido per tutto il computer** in
`<radice Hermes>/plugin-data/requrv-kb/watchdog/` impedisce a due controlli manuali o all'avvio di
sovrapporsi: un file con l'ora dell'ultimo controllo e un lock di file non bloccante (`fcntl` su
POSIX, `msvcrt` su Windows). Se un processo muore, il sistema operativo rilascia il lock.


## Test

Contro un checkout di Hermes ufficiale (nessuna richiesta al provider, home temporanee):

```sh
cd <hermes-agent>
PYTHONPATH="$PWD:/percorso/requrv-kb-plugin" <python dell'ambiente di test> -m pytest /percorso/requrv-kb-plugin/tests -q
```

Per il collaudo manuale su Hermes reale, Desktop, cloud e Windows: [Guida al collaudo manuale](docs/collaudo-manuale/README.md).
