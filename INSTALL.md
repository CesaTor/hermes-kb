# Installare ReQurv KB

ReQurv KB è un plugin per una installazione **ufficiale** di Hermes. Non serve un fork né un
installer separato: collega Hermes alla cartella della KB e installa i bot della
`Biblioteca-Agenti`.

## Cosa serve

- Hermes CLI o Hermes Desktop, con un modello già configurato nel profilo principale.
  Per ReQurv Hive lo configura ReQurv Bridge.
- La cartella della KB sincronizzata (Nextcloud, Drive, SharePoint) con `Biblioteca-Agenti/`,
  le aree e la cartella `Operatori/<nome>`.
- Accesso al repository GitHub del plugin:
  [CesaTor/hermes-kb](https://github.com/CesaTor/hermes-kb).

Non servono chiavi o password nel plugin: la chiave del modello resta nella configurazione di
Hermes/ReQurv Bridge.

## Percorso rapido: Hermes Desktop

1. Apri il link di installazione:

   ```text
   hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1
   ```

   Su macOS:

   ```sh
   open "hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1"
   ```

   Su Windows (PowerShell):

   ```powershell
   Start-Process 'hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1'
   ```

   Su Windows (`cmd.exe`):

   ```bat
   start "" "hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1"
   ```

2. Conferma nel dialogo di Hermes e riavvia Hermes Desktop.
3. Apri **Impostazioni → Plugin → ReQurv KB**. Se la pagina c'è, anche la parte Desktop è attiva.
4. Collega la KB dalla pagina (cartelle, operatore, cartella personale) oppure da terminale:

   ```sh
   hermes kb connect \
     --root "/percorso/Biblioteca-Agenti" \
     --root "/percorso/01-Marketing" \
     --root "/percorso/Operatori" \
     --operator mario \
     --personal "/percorso/Operatori/mario"
   hermes kb check
   hermes kb reconcile
   ```

5. Verifica i bot:

   ```sh
   hermes kb list
   hermes kb status
   ```

I bot installati compaiono nella sezione **Bots**. Le loro istruzioni valgono dalla conversazione
successiva.

## Percorso terminale

```sh
hermes plugins install CesaTor/hermes-kb --enable
hermes plugins list --plain | grep requrv-kb
```

Questo attiva la parte agente. Se usi Hermes Desktop, la parte app va accesa a parte:

1. Riavvia Hermes Desktop.
2. Vai in **Capabilities → Plugins**.
3. Attiva **ReQurv KB** e riavvia di nuovo.

Senza la parte Desktop funzionano comunque: comandi `hermes kb ...` e `/kb ...`, prompt della KB,
blocchi dei bot di libreria, cattura passiva e allineamento automatico. Servono la parte Desktop
per la pagina Impostazioni, il tema ReQurv, il layout `requrv-kb:minimal` e il controllo all'avvio.

## Installazione guidata da Hermes con `SETUP/AGENTS.md`

Questo è il percorso che permette a Hermes di fare quasi tutto da solo, come con il vecchio plugin.

1. Apri la cartella `kb-template/SETUP/` del repository e copia il file `AGENTS.md` nella cartella
   `SETUP/` della KB usando Finder (macOS) o Esplora file (Windows). La cartella `SETUP` deve stare
   accanto a `Biblioteca-Agenti`, alle aree e a `Operatori`. Se la KB ha già una copia vecchia di
   `AGENTS.md`, sostituiscila con quella del repository: le istruzioni cambiano con il plugin.

2. Apri una nuova conversazione con Hermes e scrivi:

   ```text
   Leggi il file SETUP/AGENTS.md nella cartella della KB e segui le istruzioni.
   Chiedimi conferma prima di installare.
   ```

3. Hermes deve:
   - controllare che ci sia un modello configurato;
   - installare il plugin da `CesaTor/hermes-kb`;
   - chiedere conferma prima dell'installazione;
   - collegare le cartelle della KB;
   - eseguire `hermes kb reconcile` e mostrarti i bot;
   - applicare il layout ReQurv, se la parte Desktop è attiva.

4. Se un passo fallisce, fermati: il file `AGENTS.md` chiede a Hermes di non proseguire. Controlla
   il messaggio e la sezione “Se qualcosa non va”.

**Requisito importante:** Hermes installa dal repository Git, non da questa copia locale. Perciò la
versione che Hermes installa è quella presente nel branch di default (di solito `main`) su GitHub.
Se le modifiche sono solo nel working tree e non sono state pubblicate, l'installazione guidata
prende la versione vecchia. Vedi “Commit, push e test locale”.

## Verifica dell'installazione

```sh
hermes plugins list --plain
hermes kb check
hermes kb list
hermes kb status
```

Atteso:

- `requrv-kb` compare tra i plugin attivi;
- `hermes kb check` termina con `OK` (o segnala solo file non ancora scaricati);
- `hermes kb list` mostra i bot abilitati dalle aree e dall'eventuale `.autorizzazioni.yaml`;
- `hermes kb status` mostra i bot di libreria installati.

Su Hermes Desktop, in **Impostazioni → Plugin → ReQurv KB**, devono comparire il collegamento,
l'ultimo controllo e **Controlla ora**. Il controllo parte all'avvio dell'app e a ogni nuova
conversazione con un bot; non c'è un intervallo periodico da configurare.

## Aggiornamento

```sh
hermes plugins update requrv-kb
```

Poi riavvia Hermes Desktop o il gateway, come chiede l'avviso di Hermes. I profili dei bot ricevono
la copia aggiornata del plugin al prossimo `hermes kb reconcile` o alla prossima conversazione.
Verifica con `hermes kb status`: chat, memoria e proposte restano.

## Commit, push e test locale

La domanda “devo committare?” dipende da **dove** vuoi installare:

| Scenario | Commit | Push | Cosa fare |
|---|---|---|---|
| Test sul tuo Mac, con il working tree corrente | No | No | Copia la cartella in `<HERMES_HOME>/plugins/requrv-kb` e abilita il plugin |
| Hermes deve installare da `SETUP/AGENTS.md` su un'altra macchina o home | Sì | Sì | Commit e push sul branch che il link usa (di solito `main`) |
| Installazione riproducibile per un cliente | Sì | Sì | Push e usa un commit SHA con `--ref <sha>` |
| Solo una prova locale del repository già pubblicato | No | No | `hermes plugins install CesaTor/hermes-kb --enable` usa l'ultima versione pubblicata |

**Un commit locale non basta per l'installazione da GitHub:** serve il push. Il link one-click e
`hermes plugins install CesaTor/hermes-kb` leggono il repository remoto, non il disco locale.

Per provare il working tree senza pubblicarlo, su macOS/Linux:

```sh
export HERMES_HOME="$HOME/.hermes-test"
mkdir -p "$HERMES_HOME/plugins"
rsync -a --delete \
  --exclude .git --exclude tests --exclude docs --exclude __pycache__ \
  "/percorso/requrv-kb-plugin/" "$HERMES_HOME/plugins/requrv-kb/"
HERMES_HOME="$HERMES_HOME" hermes plugins enable requrv-kb
HERMES_HOME="$HERMES_HOME" hermes plugins list --plain
```

Su Windows, copia la cartella in `%HERMES_HOME%\plugins\requrv-kb` con Esplora file o PowerShell,
poi esegui `hermes plugins enable requrv-kb`.

Per una versione bloccata:

```sh
git rev-parse HEAD                 # copia lo SHA
hermes plugins install https://github.com/CesaTor/hermes-kb --ref <sha-40-caratteri> --enable
```

Il link one-click non accetta un `--ref`: installa il branch di default. Se vuoi che tutti i tester
vedano una versione precisa, pubblicala su `main` e, per il cliente, usa l'installazione con `--ref`.

### Prima di committare

```sh
PYTHONPATH="/percorso/hermes-upstream:$PWD" python3.13 -m pytest tests -q
hermes plugins validate .
git diff --check
```

Aggiorna `version` in `plugin.yaml` se la release cambia in modo sostanziale, poi:

```sh
git add -A
git commit -m "feat: ..."
git push origin main
```

Se il repository è privato, l'installazione da un'altra macchina richiede credenziali Git o un
repository di test pubblico. Il link `hermes://` non può inventare un accesso che il computer non ha.

## Se qualcosa non va

**Il plugin non compare in `hermes plugins list`.**
Controlla di aver usato lo stesso `HERMES_HOME`/profilo di Hermes. Se hai installato da terminale,
verifica che il comando sia terminato senza errori e riavvia Hermes.

**La pagina Impostazioni non c'è.**
La parte Desktop è spenta. Vai in Capabilities → Plugins, attiva **ReQurv KB** e riavvia l'app.

**L'installazione guidata prende la versione vecchia.**
Le modifiche non sono su GitHub. Fai commit e push, oppure prova il working tree con la copia locale
descritta sopra.

**`hermes plugins install` chiede conferma o segnala uno scanner.**
È il controllo di sicurezza di Hermes. Il dialogo «Unverified» è normale per un plugin comunitario:
leggi la fonte e conferma. Se il verdetto è «dangerous», **fermati**: non usare `--force` per
aggirarlo. Un verdetto «caution», se hai verificato il repository, si può confermare leggendo
l'avviso. Il repository di questo plugin deve risultare «safe»: se non lo è, non installare.

**Non c'è un modello configurato.**
Il plugin non configura il provider. Installa o configura ReQurv Bridge (o un altro provider) nel
profilo principale, poi riprendi dal passo di collegamento.

**`hermes kb check` segnala file “non ancora scaricati”.**
Sono segnaposto del cloud. Rendi la cartella disponibile offline/mirroring nell'app di
sincronizzazione (Drive/OneDrive/Nextcloud), aspetta e ripeti il controllo.

**Windows non apre il link `hermes://`.**
Usa il percorso terminale: `hermes plugins install CesaTor/hermes-kb --enable`, poi riavvia Desktop e
attiva la parte Desktop in Capabilities → Plugins.

**La cartella della KB contiene spazi o lettere di unità.**
Metti i percorsi tra virgolette nei comandi. Il plugin gestisce i percorsi normali di Windows, ma i
segnaposto online-only e i file bloccati dall'antivirus vanno risolti prima del `reconcile`.

## Disinstallazione

```sh
hermes plugins remove requrv-kb
```

I profili dei bot restano: sono profili Hermes separati. Se vuoi rimuoverli, eliminali dalle
impostazioni dei Bot o con `hermes profile delete <nome>`. La cartella della KB non viene toccata.
