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
  - Windows: `start "" "hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1"`

  Chiedi all'utente di confermare nel dialogo di Hermes e di dirtelo quando ha finito.
- **Solo terminale:** `hermes plugins install CesaTor/hermes-kb --enable`. Questo accende solo la parte
  agente: avvisa l'utente che, se usa Hermes Desktop, deve accendere anche ReQurv KB in Capabilities →
  Plugins e riavviare l'app (pagina Impostazioni, controllo all'avvio e layout dipendono da quella parte).

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
Nextcloud: disattiva i file virtuali per quella cartella), aspetta e ripeti il controllo.

## 5. Installa i bot

```sh
hermes kb reconcile
```

Installa tutti i bot che le aree dell'utente abilitano. Mostra all'utente l'elenco risultante
(`hermes kb status`). Da qui in poi il plugin controlla da solo ogni 30 minuti: aggiorna i bot,
reinstalla quelli cancellati e rimuove quelli aziendali non più abilitati.

## 6. Imposta l'app (solo Hermes Desktop)

Applica il layout ReQurv con lo strumento per l'aspetto dell'app: layout `requrv-kb:minimal`. Se lo
strumento non trova il layout, la parte dell'app del plugin è spenta: chiedi all'utente di accendere
ReQurv KB in Capabilities → Plugins, riavviare Hermes Desktop e riprovare.

## 7. Chiudi

Riassumi all'utente in tre righe: cartelle collegate, bot installati, cosa fare se un bot manca
(controllare l'accesso alla cartella dell'area con l'IT). I bot nuovi compaiono nella sezione Bot;
le loro istruzioni valgono dalla prossima conversazione.
