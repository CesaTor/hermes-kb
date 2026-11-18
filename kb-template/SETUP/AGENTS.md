# Installazione di ReQurv KB su questo computer

Sei Hermes e l'utente ti ha chiesto di leggere questa cartella e seguire le istruzioni. Collega questo
computer alla KB aziendale: installa il plugin ReQurv KB, collega le cartelle sincronizzate e installa
i bot della libreria. Lavora un passo alla volta, di' all'utente cosa stai facendo e fermati se un
passo fallisce.

Regole:
- Non modificare, spostare o cancellare file nella KB. L'unica cartella in cui puoi scrivere è
  `Operatori/<nome dell'utente>`.
- Non cambiare permessi o condivisioni: li decide il cloud (Nextcloud, Drive).
- Non toccare i bot che l'utente ha già creato.
- Non chiedere né scrivere password o chiavi: la chiave del modello la configura ReQurv Bridge.

## 1. Controlla i prerequisiti

1. Verifica che Hermes abbia un modello configurato nel profilo principale (`hermes config get model.default`: deve
   stampare un modello; non lanciare `hermes model`, è interattivo). Se non c'è, fermati e di' all'utente di installare prima ReQurv Bridge.
2. Se il plugin è già installato (`hermes plugins list` mostra `requrv-kb`), salta al passo 3.

## 2. Installa il plugin

Il plugin è pubblico su GitHub: `CesaTor/hermes-kb`.

- **Se l'utente usa Hermes Desktop** (preferito): apri il link di installazione, che installa e accende
  sia la parte agente sia la parte dell'app.
  - macOS: `open "hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1"`
  - Windows (PowerShell): `Start-Process 'hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1'`
  - Windows (`cmd.exe`): `start "" "hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1"`

  Chiedi all'utente di confermare nel dialogo di Hermes e di dirtelo quando ha finito.
  Il dialogo «Unverified» è normale per un plugin comunitario: l'utente deve leggere la fonte e
  confermare. Se il verdetto di sicurezza è «dangerous», non forzare l'installazione: fermati e
  mostra il messaggio.
- **Solo terminale:** `hermes plugins install CesaTor/hermes-kb --enable`. Questo accende solo la parte
  agente: avvisa l'utente che, se usa Hermes Desktop, deve accendere anche ReQurv KB in Capabilities →
  Plugins e riavviare l'app (pagina Impostazioni, controllo all'avvio e layout dipendono da quella parte).
  Anche qui, se lo scanner chiede conferma, leggere l'esito: non usare `--force` per aggirare un
  verdetto «dangerous».

Controlla con `hermes plugins list` che `requrv-kb` risulti attivo.

## 3. Trova le cartelle della KB

Questo file sta nella cartella `SETUP` della KB. Le cartelle della KB sono accanto a `SETUP`:

| Cartella | Cosa contiene |
|---|---|
| `Biblioteca-Agenti` | I bot certificati, uno per sottocartella |
| `01-…`, `02-…` (cartelle di area) | La conoscenza di ogni area e il suo `bots.yaml` (quali bot l'area abilita) |
| `Operatori/<nome>` | La cartella personale dell'utente |

1. Elenca le cartelle accanto a `SETUP` che l'utente può leggere. Le aree a cui non ha accesso non ci
   sono: è normale.
2. Alcune cartelle possono essere condivise a parte e stare altrove sul disco (per esempio la
   cartella personale). Chiedi all'utente se ha altre cartelle della KB sincronizzate e dove sono.
3. Chiedi all'utente il nome della sua cartella in `Operatori/`.

## 4. Collega la KB

Una `--root` per ogni cartella trovata (la cartella che contiene `Biblioteca-Agenti` vale per tutte le
cartelle al suo interno):

```sh
hermes kb connect --root "<cartella>" --root "<altra cartella>" --operator <nome>
```

Se la cartella personale è un'isola separata, aggiungi `--personal "<cartella personale>"`.

Poi `hermes kb check`. Se segnala file "non ancora scaricati", di' all'utente di rendere la cartella
disponibile offline nell'app di sincronizzazione (Drive: "Disponibile offline" o modalità mirroring;
Nextcloud: disattiva i file virtuali o scegli "Rendi disponibile offline" per l'intera cartella KB),
aspetta e ripeti il controllo.

**Non proseguire con `reconcile` finché `hermes kb check` non è `OK`.** I file `compressed/dataless`
(Nextcloud/OneDrive) non sono leggibili: il plugin li rifiuta con «Alcuni file della libreria non
sono ancora scaricati». Non è un errore del plugin e non si risolve con `--force`.

## 5. Installa i bot

```sh
hermes kb reconcile
```

Installa tutti i bot che le aree dell'utente abilitano. Mostra all'utente l'elenco risultante
(`hermes kb status`). Da qui in poi il plugin controlla la libreria all'avvio di Hermes e a ogni nuova
conversazione con un bot: aggiorna i bot e reinstalla quelli cancellati; **non rimuove mai** un bot
(uno non più abilitato resta, e viene segnalato come `not-allowed`). Non c'è un controllo periodico:
«Controlla ora» in Impostazioni e `hermes kb reconcile` lo fanno su richiesta.

Se l'operatore ha personalizzato il SOUL o una skill e la libreria pubblica una versione che tocca
quel file, il bot al primo uso spiega la differenza e chiede se tenere la versione dell'operatore o
prendere la nuova. La risposta si registra con il tool `kb_personal` oppure con
`hermes -p <bot> kb resolve --kind soul|skill --choice keep|take`; «tengo la mia» lascia la copia
personale, «prendo la nuova» la rimuove dalle proposte.

Se nella cartella personale c'è un `.autorizzazioni.yaml`, quello restringe i bot installabili:
se manca valgono i `bots.yaml` delle aree. Non crearlo: lo fornisce l'IT.

**Reparto IT.** Prima del setup, l'IT pubblica il pacchetto `knowledge-manager` dal template nella
libreria, aggiunge il nome al `bots.yaml` dell'area IT e assegna `ruolo: it` nel proprio
`.autorizzazioni.yaml`. Se stai configurando la macchina dell'IT, verifica che `hermes kb status`
mostri anche il Knowledge Manager. Quel bot mantiene `Wiki/` e rivede le proposte degli operatori.

## 6. Imposta l'app (solo Hermes Desktop)

Il tema ReQurv si applica da solo alla prima apertura dell'app dopo l'installazione; se l'utente ne ha
scelto un altro, il pulsante «Tema ReQurv» in Impostazioni → Plugin → ReQurv KB lo riapplica. Applica
poi il layout ReQurv con lo strumento per l'aspetto dell'app: layout `requrv-kb:minimal`. Se lo
strumento non trova il layout, la parte dell'app del plugin è spenta: chiedi all'utente di accendere
ReQurv KB in Capabilities → Plugins, riavviare Hermes Desktop e riprovare.

Il layout mostra la sezione Bot a sinistra, la chat al centro e Files e Attività pianificate come
barre laterali chiuse a destra, e nasconde le voci del menu che non servono (Messaging, Artifacts,
Scheduled jobs, Kanban). Non può nascondere la scheda Sessions accanto a Bot, né chiudere
revisione e terminale se erano aperti: restano come li ha l'utente. Avvisalo che può nascondere
Sessions dal menu della scheda (clic destro).

## 7. Chiudi

Riassumi all'utente in tre righe: cartelle collegate, bot installati, cosa fare se un bot manca
(controllare l'accesso alla cartella dell'area con l'IT). I bot nuovi compaiono nella sezione Bot;
le loro istruzioni valgono dalla prossima conversazione.
