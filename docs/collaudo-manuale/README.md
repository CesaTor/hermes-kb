# Collaudo manuale di ReQurv KB

Data: 18 novembre 2026
Ambito: plugin `requrv-kb` su Hermes CLI e Hermes Desktop.
Scopo: verificare a mano i flussi che la suite automatica non può coprire davvero — installazione,
chat reale, sincronizzazione cloud, permessi, Desktop e Windows. La suite automatica resta la
verifica di regressione: `92 passed` con `python3.13 -m pytest tests -q`.

Questa guida non è un elenco di comandi da eseguire alla cieca. Ogni prova ha un risultato atteso e
un'evidenza da conservare. Se un risultato non torna, fermati e annota il punto esatto: un test
fallito è un'informazione, un test “aggiustato” non lo è.

---

## 1. Regole di sicurezza

1. **Mai sulla KB di produzione.** Usa una copia usa-e-getta della KB, una macchina di prova o un
   altro utente del sistema operativo.
2. **Niente dati veri.** La fixture contiene solo dati sintetici. Non incollare chiavi vere, dati di
   clienti, retribuzioni o documenti riservati: alcuni test servono proprio a verificare che il
   plugin li rifiuti.
3. **Niente permessi cambiati a mano.** I permessi li decide il cloud (Nextcloud, Drive, SharePoint).
   Il plugin non concede e non toglie accessi.
4. **Le prove distruttive sono segnalate.** Eliminare un bot, ruotare una versione o cancellare una
   proposta va fatto solo nella fixture.
5. **Conserva le evidenze prima di pulire.** Screenshot, output dei comandi e file prodotti.

---

## 2. Prerequisiti

| Servono | Note |
|---|---|
| Hermes ufficiale, CLI e Desktop | Versione corrente; per il Desktop serve la parte app del plugin |
| Un modello configurato | Anche un provider di test; senza modello le chat non partono |
| Python 3.10+ | Solo per creare la fixture e per il lint della wiki |
| macOS o Linux | Percorso principale |
| Windows | Sezione K; è l'unico gate ancora aperto (G2) |
| Due utenze o due home Hermes | Operatore e IT; il Desktop va provato su un utente di test |

La fixture crea una KB con:

- `Biblioteca-Agenti/marketing` (versione 1.0.0, skill `brand`, `config_managed: agent.max_turns`);
- `Biblioteca-Agenti/finanza`;
- `Biblioteca-Agenti/knowledge-manager` (copia del template);
- `Biblioteca-Agenti/vendite` (pacchetto non elencato da nessuna area: non deve comparire);
- aree `01-Marketing`, `02-Finanza`, `90-IT` con i rispettivi `bots.yaml` e documenti;
- operatori `mario`, `anna`, `it`, con `.autorizzazioni.yaml`;
- una proposta di Anna già pronta e una conoscenza già raccolta;
- una cartella `Riservato/01-Finanza` e un file nascosto, per i test negativi delle fonti.

Gli account della fixture:

| Account | Home Hermes | Cartella personale | Bot ammessi |
|---|---|---|---|
| Mario | `hermes-operator` | `Operatori/mario` | `marketing` |
| Anna | non serve avviarla | `Operatori/anna` | `marketing`, `finanza` (solo proposte precompilate) |
| IT | `hermes-it` | `Operatori/it` | tutti (`bots: "*"`, `ruolo: it`) |

---

## 3. Preparazione

### 3.1 Crea la fixture

Dalla radice del repository:

```sh
export TEST_ROOT="$HOME/requrv-collaudo"
python3 docs/collaudo-manuale/prepara_kb_test.py "$TEST_ROOT"

export KB="$TEST_ROOT/KB"
export H_OP="$TEST_ROOT/hermes-operator"
export H_IT="$TEST_ROOT/hermes-it"
```

Il comando rifiuta una cartella piena. Per rifare la fixture, cancella `$TEST_ROOT` e ricreala.

### 3.2 Installa il plugin nelle due home

**Percorso release (quello che usa un tester):**

```sh
export HERMES_HOME="$H_OP"
hermes plugins install CesaTor/hermes-kb --enable
hermes plugins list --plain | grep requrv-kb

export HERMES_HOME="$H_IT"
hermes plugins install CesaTor/hermes-kb --enable
hermes plugins list --plain | grep requrv-kb
```

**Percorso working tree (sviluppatori):**

```sh
install_plugin_copy() {
  home="$1"
  mkdir -p "$home/plugins"
  rsync -a --delete \
    --exclude .git --exclude tests --exclude docs --exclude __pycache__ \
    "$PWD/" "$home/plugins/requrv-kb/"
  HERMES_HOME="$home" hermes plugins enable requrv-kb
}

install_plugin_copy "$H_OP"
install_plugin_copy "$H_IT"
```

Se una home non ha un modello, copia solo la configurazione del provider da un profilo di test
(oppure esegui `hermes setup`). Non copiare chiavi di produzione.

Per il Desktop: installa dal link `hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1` (o
Capabilities → Plugins → Install from Git), riavvia l'app e verifica che **ReQurv KB** compaia in
Impostazioni → Plugin. Se hai installato solo da terminale, attiva la parte Desktop in
Capabilities → Plugins e riavvia.

### 3.3 Collega la KB

Mario (operatore):

```sh
export HERMES_HOME="$H_OP"
hermes kb connect \
  --root "$KB/Biblioteca-Agenti" \
  --root "$KB/01-Marketing" \
  --root "$KB/Operatori" \
  --operator mario \
  --personal "$KB/Operatori/mario"
hermes kb check
hermes kb list
```

Atteso: `Operatore: mario`, la cartella personale, le tre cartelle, `OK`; `kb list` mostra solo
`marketing 1.0.0 new` (l'autorizzazione di Mario limita il catalogo, anche se l'area elenca anche
`finanza`).

IT:

```sh
export HERMES_HOME="$H_IT"
hermes kb connect \
  --root "$KB/Biblioteca-Agenti" \
  --root "$KB/90-IT" \
  --root "$KB/Operatori" \
  --operator it \
  --personal "$KB/Operatori/it"
hermes kb check
hermes kb list
```

Atteso: `finanza`, `knowledge-manager`, `marketing`, tutti `new`.

**Attenzione alla home.** Ogni comando va eseguito con la `HERMES_HOME` giusta. Se copi un blocco
separatamente, anteponi `HERMES_HOME="$H_OP"` per Mario o `HERMES_HOME="$H_IT"` per l'IT. Un
`hermes kb ...` lanciato con la home sbagliata mostra un altro catalogo o un altro operatore.

### 3.4 Dove guardare

| Cosa | Percorso |
|---|---|
| Collegamento | `<HERMES_HOME>/plugin-data/requrv-kb/connection.json` |
| Registro del bot | `<HERMES_HOME>/profiles/<bot>/.library-owned.json` |
| Versioni personali | `<HERMES_HOME>/profiles/<bot>/.requrv-kb-personal.json` |
| Backup pre-aggiornamento | `<HERMES_HOME>/profiles/<bot>/.library-backup/<versione>/` |
| Proposte SOUL/skill | `Operatori/<nome>/proposte/<bot>/` |
| Conoscenze raccolte | `Operatori/<nome>/proposte/knowledge/` |
| Indice dedup locale | `<HERMES_HOME>/plugin-data/requrv-kb/knowledge-dedup-*.json` |
| Lock cattura | `<HERMES_HOME>/plugin-data/requrv-kb/knowledge-capture.lock` |
| Watchdog | `<HERMES_HOME>/plugin-data/requrv-kb/watchdog/` |
| Wiki | `<KB>/Wiki/` |

---

## 4. Percorso rapido (smoke test)

Da fare per primo, in ordine. Se uno step fallisce, non proseguire.

| # | Prova | Atteso | Sezione |
|---|---|---|---|
| S1 | Plugin attivo in entrambe le home | `enabled ... requrv-kb` | A1 |
| S2 | Connessione Mario e IT | `OK`; cataloghi filtrati | B1 |
| S3 | Installazione `marketing` | profilo, registro, prompt | C1 |
| S4 | Chat con `marketing` | cita le cartelle e la versione | C2 |
| S5 | IT vede la proposta di Anna | `it list` e `it show` | E2 |
| S6 | IT accetta la proposta | versione 1.0.1, proposta rimossa | E3 |
| S7 | Mario aggiorna | 1.0.0 → 1.0.1, nessun pending | C4 |
| S8 | Cattura di un fatto | un `.md` con frontmatter | F2 |
| S9 | Stessa cattura di nuovo | `duplicate`, un solo file | F3 |
| S10 | Riconciliazione | `unchanged` o aggiornamento coerente | H1 |

Tempo indicativo: 30–45 minuti, senza Desktop.

---

## 5. Collaudo completo

**Ordine consigliato.** Le sezioni C, D ed E condividono la stessa fixture e si influenzano: E3
produce la versione che C4 usa per l'aggiornamento, D3–D5 alzano ancora la versione. Segui questo
ordine, oppure usa una fixture nuova per ogni blocco:

`A → B → C1–C3 → E1–E4 → C4 → D1–D5 → E5–E6 → F → G → H → I → J → K → L`

I numeri di versione nelle sezioni sono esempi: se la libreria è già a una versione successiva,
adatta il numero (l'importante è che la versione cambi e che il test verifichi il salto). Il percorso
rapido della sezione 4 è già nell'ordine giusto.

### A. Installazione e setup

#### A1 — Plugin attivo e due metà

1. Esegui `HERMES_HOME="$H_OP" hermes plugins list --plain` e
   `HERMES_HOME="$H_IT" hermes plugins list --plain`: riga `enabled ... requrv-kb` in entrambe.
2. Apri Hermes Desktop su un utente di test: Impostazioni → Plugin → **ReQurv KB** deve aprirsi.
3. Se hai installato solo da terminale, verifica che la pagina non ci sia, poi attiva la parte
   Desktop in Capabilities → Plugins, riavvia e ricontrolla.
4. Facoltativo: `hermes plugins validate "$H_OP/plugins/requrv-kb"` (o la cartella della release).

**Atteso:** la pagina si apre senza errori; tema e layout sono disponibili solo con la parte
Desktop attiva. **Evidenza:** output di `plugins list`, screenshot della pagina.

#### A2 — Setup guidato da `SETUP/AGENTS.md`

Serve una home Hermes pulita, con modello ma senza plugin.

1. Apri una chat nel profilo principale e chiedi:
   *“Leggi il file `SETUP/AGENTS.md` nella cartella della KB e segui le istruzioni. Chiedimi conferma
   prima di installare.”* Se il modello non trova il file, incolla il percorso assoluto.
2. L'agente deve controllare il modello, proporre l'installazione, chiedere conferma, collegare le
   cartelle, eseguire `kb reconcile` e mostrare i bot.
3. Verifica che non abbia scritto fuori da `Operatori/<nome>`.

**Atteso:** `kb check` termina `OK`; i bot ammessi compaiono; la chat riassume cartelle e bot.
**Nota:** richiede rete e modello reale. Se stai collaudando il working tree e non vuoi installare
la release pubblica, salta A2 oppure sostituisci l'installazione con la copia locale della sezione
3.2. Se il modello non è disponibile, salta A2 e annotalo.

#### A3 — Aggiornamento del plugin

1. `HERMES_HOME="$H_OP" hermes plugins update requrv-kb` e
   `HERMES_HOME="$H_IT" hermes plugins update requrv-kb` (o reinstallazione della copia di working
   tree).
2. Riavvia Hermes Desktop o il gateway, come chiede l'avviso di Hermes.
3. `hermes kb check` deve restare `OK`; i bot devono restare installati.
4. Apri una chat con `marketing`: il prompt KB deve essere ancora presente.

**Atteso:** nessuna perdita di collegamento, profili, proposte o chat.

---

### B. Connessione, catalogo e autorizzazioni

#### B1 — Connessione multi-cartella

Esegui i comandi della sezione 3.3. Controlla anche il file `connection.json`: `roots`, `operator`,
`personal`.

**Atteso:** `kb check` mostra le cartelle e `OK`; `kb list` di Mario mostra solo `marketing`.
**Errore atteso:** senza connessione, `hermes kb list` risponde
`Questo computer non è ancora collegato alla KB.`

#### B2 — Catalogo, aree e `.autorizzazioni.yaml`

1. Con Mario, modifica `$KB/Operatori/mario/.autorizzazioni.yaml`:

   ```yaml
   operator: mario
   bots: [marketing, finanza]
   ruolo: operatore
   ```

2. `HERMES_HOME="$H_OP" hermes kb list` deve mostrare anche `finanza` (l'area la elenca).
3. Prova `HERMES_HOME="$H_OP" hermes kb install finanza`: deve riuscire. Poi eliminalo con
   `HERMES_HOME="$H_OP" hermes profile delete finanza --yes` per non sporcare le prove successive.
4. Rimetti `bots: [marketing]`; `HERMES_HOME="$H_OP" hermes kb list` nasconde `finanza`;
   `HERMES_HOME="$H_OP" hermes kb install finanza` deve rifiutare con un messaggio
   sull'autorizzazione. Un bot già installato che perde l'autorizzazione resta sul computer: lo
   verifichi in H3. Qui l'hai eliminato per pulizia e per non sporcare le prove dopo.
5. Metti in `01-Marketing/bots.yaml` `bots: "*"` e, per vedere tutti i pacchetti, metti `bots: "*"`
   anche in `.autorizzazioni.yaml` (o rimuovi temporaneamente il file). Il catalogo deve includere
   tutti i pacchetti dell'area, compreso `vendite` (che nessuna lista nominava). Ripristina entrambi.
6. Svuota temporaneamente i `bots.yaml`: il catalogo è vuoto e nessun bot viene cancellato.
   Ripristina.

**Atteso:** il catalogo è l'unione delle aree leggibili, filtrata dall'autorizzazione; nessun
pacchetto non elencato compare senza `*`.

#### B3 — Errori di collegamento e file online-only

1. Rinomina temporaneamente una cartella collegata e lancia
   `HERMES_HOME="$H_OP" hermes kb check`: deve segnalare il problema senza cancellare bot.
2. `HERMES_HOME="$H_OP" hermes kb install non-esiste`: errore in italiano, nessuna scrittura.
3. Su una cartella cloud reale, lascia un file come segnaposto online-only (Drive/OneDrive/Nextcloud)
   e lancia `HERMES_HOME="$H_OP" hermes kb check`: deve comparire “non è ancora scaricato”; rendi la
   cartella disponibile offline/mirroring e ripeti finché il problema sparisce.

**Atteso:** errori leggibili, nessun dato perso, nessun download forzato a sorpresa.

#### B4 — Scollega e ricollega

1. Da Desktop: Impostazioni → ReQurv KB → **Scollega**, conferma. Se stai usando la home CLI,
   equivale a `HERMES_HOME="$H_OP" hermes kb disconnect`.
2. `HERMES_HOME="$H_OP" hermes kb check` deve dire che il computer non è collegato; i bot restano in
   `HERMES_HOME="$H_OP" hermes kb status`.
3. Ricollega le stesse cartelle: i bot restano collegati alla libreria.
4. Danneggia `connection.json` (copia di backup, poi scrivi `{rotto`):
   `HERMES_HOME="$H_OP" hermes kb check` deve trattarlo come non collegato, non crashare; ripristina
   o ricollega.

**Atteso:** scollegare non elimina bot, chat, memoria o proposte.

---

### C. Installazione, prompt e aggiornamenti

#### C1 — Installa un bot

```sh
export HERMES_HOME="$H_OP"
hermes kb install marketing
hermes kb status
```

**Atteso:** output `marketing: versione 1.0.0. Vale dalla prossima conversazione.`; `status` mostra
`marketing 1.0.0`. Nel profilo `profiles/marketing` devono esserci `SOUL.md`, `config.yaml`,
`distribution.yaml`, `skills/brand/SKILL.md`, `.library-owned.json`, `.requrv-kb-personal.json` e
`plugins/requrv-kb/`. `config.yaml` deve avere il modello/provider del coordinatore solo se il bot
non ne aveva uno, e `skills.create_dir` deve puntare alla cartella personale dell'operatore.

#### C2 — Prompt della nuova conversazione

Apri una nuova chat con `marketing` e chiedi, in tre messaggi separati:

1. *“Quali cartelle della KB vedi e quale versione sei?”* → deve citare le cartelle collegate e
   `1.0.0`.
2. *“Che cosa dice il piano marketing 2026 sul budget?”* → deve leggere
   `01-Marketing/documenti/piano-marketing-2026.md` e citarlo.
3. *“Cosa puoi modificare del tuo profilo e cosa no?”* → SOUL e skill sì; chiavi gestite di
   `config.yaml`, metadati e attività pianificate no.

**Atteso:** risposte coerenti, citazioni alla KB, nessuna invenzione di percorsi. Le modifiche valgono
dalla conversazione successiva.

#### C3 — Duplica un bot

```sh
HERMES_HOME="$H_OP" hermes kb duplicate marketing marketing-personale
HERMES_HOME="$H_OP" hermes kb status
```

**Atteso:** esiste `profiles/marketing-personale`, senza `.library-owned.json` e senza record
personale; non compare come bot di libreria; un aggiornamento della libreria non lo tocca.

#### C4 — Aggiorna e rollback

**Dipendenza:** questa prova usa la versione prodotta da E3. Se stai seguendo l'ordine delle sezioni,
esegui prima E3 e poi torna qui.

Dopo E3 (nell'esempio, versione 1.0.1 nella libreria):

```sh
export HERMES_HOME="$H_OP"
hermes kb update marketing
hermes kb status
```

**Atteso:** versione nuova; backup in `profiles/marketing/.library-backup/<versione precedente>/` con
`SOUL.md`, `config.yaml`, `distribution.yaml` e la skill; nessun pending se non hai modifiche
personali.

```sh
hermes kb rollback marketing
hermes kb status
hermes kb reconcile
```

**Atteso:** torna alla versione precedente; `reconcile` dice `unchanged` e non riapplica la versione
da cui hai fatto rollback. Pubblica una versione ancora successiva e `reconcile` riprende gli
aggiornamenti. Se il rollback perde una chat, è un bug: fermati.

---

### D. Versioni personali, proposte e blocchi

#### D1 — Modifica SOUL e skill

Nella chat con `marketing`, chiedi esplicitamente di usare il tool di scrittura:

*“Usa `write_file` per aggiungere al tuo `SOUL.md` la regola: ‘Dai sempre del lei’. Poi dimmi il
percorso.”*

Poi ripeti per `skills/brand/SKILL.md` con una frase distintiva.

**Atteso:** il file live cambia; in `$KB/Operatori/mario/proposte/marketing/` compaiono `SOUL.md`,
`skills/brand/SKILL.md` e `proposal.yaml` con `base_version` pari alla versione del pacchetto da cui
parte la copia (1.0.0, 1.0.1 o quella corrente) e l'hash dei file. La modifica non tocca la libreria.

#### D2 — Blocchi su config, metadati e cron

1. Chiedi al bot: *“Cambia `agent.max_turns` a 99 nel tuo `config.yaml`.”*
   → deve rifiutare spiegando che la chiave è gestita dalla libreria.
2. Chiedi di modificare `distribution.yaml` → deve rifiutare: è metadato del pacchetto.
3. Se il pacchetto ha un cron, chiedi di modificarlo → deve rifiutare.
4. Verifica che i file non siano cambiati.

**Nota:** una modifica fatta con un editor o un comando di terminale bypassa il blocco; è un limite
noto. Il test vale solo per i tool dell'agente.

#### D3 — Aggiornamento che non tocca il file personale

1. Porta `distribution.yaml` della libreria a una versione successiva (es. `2.0.0`) **senza**
   cambiare `SOUL.md`.
2. `HERMES_HOME="$H_OP" hermes kb update marketing`.

**Atteso:** `reapplied: ["SOUL"]`, nessun pending, il SOUL personale resta live.

#### D4 — Conflitto: tieni la tua versione

1. Porta la libreria a una versione ancora successiva (es. `3.0.0`) cambiando anche `SOUL.md`.
2. `HERMES_HOME="$H_OP" hermes kb update marketing`.
3. `HERMES_HOME="$H_OP" hermes kb status` → `(1 versioni tue da decidere)`; il SOUL live è quello
   nuovo della libreria.
4. Apri una nuova chat: il bot deve spiegare la differenza e chiedere.
5. Rispondi “tieni la mia” oppure esegui:

   ```sh
   HERMES_HOME="$H_OP" hermes -p marketing kb resolve --kind soul --choice keep
   ```

**Atteso:** il SOUL personale torna live; la proposta resta per l'IT; il pending sparisce.

#### D5 — Conflitto: prendi la nuova versione

Porta la libreria a una versione ancora successiva (es. `4.0.0`) cambiando
`skills/brand/SKILL.md`, esegui `HERMES_HOME="$H_OP" hermes kb update marketing`, poi apri una chat e
rispondi “prendi la nuova” oppure:

```sh
HERMES_HOME="$H_OP" hermes -p marketing kb resolve --kind skill --name brand --choice take
```

**Atteso:** la versione della libreria resta live; la copia in `proposte/marketing/skills/brand/`
viene rimossa (è il segnale di “integrata”); il pending sparisce. La domanda non deve ripresentarsi
alla release successiva.

---

### E. Revisione IT

#### E1 — Ruolo IT obbligatorio

Con Mario:

```sh
HERMES_HOME="$H_OP" hermes kb it list
```

**Atteso:** exit code 1 e messaggio `Questa operazione è riservata al reparto IT...`. In chat, il bot
di Mario non deve avere `kb_proposals`/`kb_updates`; con l'IT devono essere disponibili.

#### E2 — Elenco e differenze

Con l'IT:

```sh
HERMES_HOME="$H_IT" hermes kb it list
HERMES_HOME="$H_IT" hermes kb it show --operator anna --bot marketing
```

**Atteso:** Anna/marketing con `base 1.0.0` (o la versione corrente della proposta), `SOUL.md`, e la
conoscenza precompilata; il diff mostra
`-` per la proposta e `+` per la libreria.

#### E3 — Accetta una proposta

```sh
HERMES_HOME="$H_IT" hermes kb it accept --operator anna --bot marketing
```

**Atteso:** solo anteprima, nessuna scrittura; la versione passa alla patch successiva (ad esempio
`1.0.0 → 1.0.1`). Poi:

```sh
HERMES_HOME="$H_IT" hermes kb it accept --operator anna --bot marketing --yes
```

**Atteso:** `SOUL.md` della libreria aggiornato; `distribution.yaml` alla nuova versione; la cartella
`Operatori/anna/proposte/marketing/` sparisce. Su Mario, dopo `kb reconcile`, `marketing` passa alla
stessa versione.

Ripeti con una proposta basata su una versione vecchia: l'anteprima deve avvisare che potresti
sovrascrivere modifiche successive.

#### E4 — Rifiuta una proposta

Dopo E3 la proposta di marketing è stata integrata; creane una nuova per Anna, questa volta su
`finanza`:

```sh
mkdir -p "$KB/Operatori/anna/proposte/finanza"
printf '# Finanza (proposta di Anna)\n\nUsa il lei.\n' \
  > "$KB/Operatori/anna/proposte/finanza/SOUL.md"
printf 'bot: finanza\noperatore: anna\nbase_version: 1.0.0\nfile:\n  SOUL.md: prova\n' \
  > "$KB/Operatori/anna/proposte/finanza/proposal.yaml"
```

Poi:

```sh
HERMES_HOME="$H_IT" hermes kb it reject --operator anna --bot finanza \
  --reason "Regola troppo specifica per un solo operatore"
```

**Atteso:** la proposta è in `Operatori/anna/proposte/Archivio/finanza-<data>-<id>/` con
`RIFIUTATA.md` (data, operatore, motivo); il file originale non è più in `proposte/finanza/`.
Rifiutare non cancella la versione live di Anna.

#### E5 — Aggiornamenti della libreria

```sh
HERMES_HOME="$H_IT" hermes kb updates
HERMES_HOME="$H_IT" hermes kb updates --apply
```

**Atteso:** elenco dei bot `new`/`update`; `--apply` installa/aggiorna, compreso
`knowledge-manager` in questa home IT; una seconda esecuzione non ha più nulla da fare.

#### E6 — Isolamento tra operatori (con cloud reale)

Questa prova richiede due account o due macchine collegate a quote diverse.

1. Mario non deve vedere `Operatori/anna`, `Operatori/it` o `Wiki/` se il cloud non li condivide.
2. L'IT deve vedere solo le proposte che il cloud gli espone.
3. Mario non deve poter usare i comandi IT anche se conosce il percorso.

**Atteso:** il plugin non allarga mai i permessi; un file non condiviso non compare e non è
leggibile. Se Mario vede una cartella che il cloud non gli ha dato, è un problema di condivisione,
non del plugin: fermati e verifica il cloud.

---

### F. Cattura passiva

#### F1 — Disponibilità

1. Con `marketing` (bot di libreria, autorizzato, connesso), in chat chiedi una cattura: deve
   funzionare.
2. Con `marketing-personale` (duplicato) la cattura non deve essere offerta.
3. Togli `marketing` da `.autorizzazioni.yaml` e riapri la chat: lo strumento non deve comparire; se
   lo invochi, deve rifiutare.
4. Scollega la KB: nessuna cattura; ricollega.

**Atteso:** la cattura è disponibile solo per un bot di libreria, autorizzato, con connessione valida.

#### F2 — Cattura un fatto

Nella chat con `marketing`, chiedi in modo esplicito:

*“Salva come conoscenza aziendale, usando `kb_capture_knowledge`: ‘Il budget approvato per il
marketing 2026 è 50.000 euro’, con fonte `01-Marketing/documenti/piano-marketing-2026.md`.”*

**Atteso:** un file `YYYYMMDD-HHMMSS-budget-marketing.md` in
`Operatori/mario/proposte/knowledge/` con frontmatter:

```yaml
data: '...'
autore: mario
bot: marketing
argomento: Budget marketing
fonti:
- 01-Marketing/documenti/piano-marketing-2026.md
session_id: ...   # quando il runtime lo fornisce
```

Il corpo è il fatto, non la trascrizione. `Wiki/` non viene toccata. Se il file non compare, chiedi
al bot di usare il tool e controlla che `kb_capture_knowledge` sia tra i tool disponibili.

#### F3 — Duplicato dopo il riavvio

1. Chiudi Hermes (o avvia un processo nuovo).
2. Ripeti la stessa cattura, anche con parole leggermente diverse:
   *“Il BUDGET approvato per il marketing 2026 è 50.000 euro.”*
3. Controlla la cartella e l'indice:

```sh
ls "$KB/Operatori/mario/proposte/knowledge"
cat "$H_OP/plugin-data/requrv-kb"/knowledge-dedup-*.json
```

**Atteso:** risposta `duplicate`, stesso nome file, un solo `.md`; l'indice contiene l'hash, non il
testo del fatto. Dopo che l'IT ha integrato e cancellato il file, la stessa cattura deve restare
`duplicate` su quel computer (l'indice locale è la memoria). Su un altro dispositivo che non ha mai
visto il file, la stessa cattura può ricrearlo: è il limite documentato, non un bug.

#### F4 — Fonti: dentro, fuori, personali, riservate

Con `marketing`, prova a citare:

1. `01-Marketing/documenti/piano-marketing-2026.md` → accettata, salvata come percorso relativo.
2. Il percorso assoluto dello stesso file → accettato.
3. `01-Marketing/documenti/.bozza-interna.md` → rifiutato (file nascosto).
4. `Operatori/anna/proposte/knowledge/20261118-090000-clienti.md` → rifiutato (cartella personale).
5. `/etc/hosts` (macOS/Linux) o `C:\Windows\win.ini` (Windows) → rifiutato (fuori dalle cartelle).
6. Un URL `https://example.com` → rifiutato: non è un file della KB.
7. Per il caso riservato: ricollega temporaneamente `--root "$KB/Riservato/01-Finanza"` e cita
   `Riservato/01-Finanza/documenti/retribuzioni.md` → rifiutato come personale/riservato. Poi
   ricollega senza quella root.

**Atteso:** nessun file creato per i casi 3–7; messaggi in italiano che spiegano il motivo.

#### F5 — Segreti e input non validi

1. Chiedi di salvare: *“La chiave API è `sk-proj-abcdefghijklmnopqrstuvwxyz123456`.”*
   → rifiuto per segreto, nessun file.
2. Chiedi un fatto che inizia con `# Titolo` o contiene un blocco ```` ``` ```` → rifiuto per
   scaffolding Markdown.
3. Chiedi un fatto con righe `Utente: ...` / `Assistente: ...` → rifiuto: sembra una trascrizione.
4. Chiedi un argomento vuoto o un fatto vuoto → rifiuto con il campo mancante.

**Atteso:** errori semplici, nessun file parziale e nessun `.tmp` lasciato nella cartella.
**Nota:** il servizio redige i segreti riconoscibili, ma non è un rilevatore di PII. La regola “non
proporre dati personali o dei clienti” resta in carico al bot e all'IT: se il modello crea una
proposta con dati personali, è un difetto di prompt/valutazione da annotare, non un rifiuto atteso.

#### F6 — Due processi insieme

La deduplicazione è serializzata sullo stesso computer. Per provarla:

1. Rendi `finanza` autorizzato per Mario e installalo:

   ```sh
   # in .autorizzazioni.yaml: bots: [marketing, finanza]
   HERMES_HOME="$H_OP" hermes kb install finanza
   ```

2. Apri due chat, una con `marketing` e una con `finanza` (o due processi `hermes -p ... -z`), e
   chiedi lo stesso fatto nello stesso momento.
3. Ripeti 2–3 volte.

**Atteso:** un solo file in `proposte/knowledge/`; una risposta `created`, l'altra `duplicate`;
esiste `knowledge-capture.lock` in `plugin-data/requrv-kb/` e non restano file temporanei.
Se ottieni due file, fermati: è una regressione della corsa tra processi.

Al termine rimetti `bots: [marketing]` in `.autorizzazioni.yaml` e
`hermes profile delete finanza --yes`, così le prove successive restano pulite.

#### F7 — Fuori perimetro

1. Bot personale (duplicato) → niente tool.
2. Bot non più autorizzato → niente tool o rifiuto.
3. Computer scollegato → niente cattura.
4. Revisione IT/wiki in corso → il prompt chiede di non catturare durante la revisione; verifica che
   il bot non proponga conoscenze mentre revisiona.

#### F8 — Visibilità IT, nessuna scrittura nella wiki

Con l'IT:

```sh
HERMES_HOME="$H_IT" hermes kb it knowledge
HERMES_HOME="$H_IT" hermes kb it list
```

**Atteso:** la conoscenza di Mario compare con operatore e nome file. `Wiki/` non cambia finché il
Knowledge Manager non la integra; la cattura non pubblica mai nella wiki.

---

### G. Knowledge Manager e wiki

#### G1 — Installa il Knowledge Manager

Con l'IT, se E5 non l'ha già installato:

```sh
HERMES_HOME="$H_IT" hermes kb install knowledge-manager
```

Poi verifica:

```sh
HERMES_HOME="$H_IT" hermes kb status
HERMES_HOME="$H_IT" hermes -p knowledge-manager skills list
```

**Atteso:** versione `0.1.0`; skill `llm-wiki`, `mappa-kb`, `knowledge-ingest`,
`pubblica-documento`; `scripts/wiki_lint.py` presente. In chat, con `ruolo: it`, il bot deve avere
`kb_proposals` e `kb_updates`.

Controllo negativo: con Mario (non IT), gli stessi tool non devono comparire.

#### G2 — Inizializza la wiki e integra una conoscenza

1. Apri una chat con `knowledge-manager` e chiedi:
   *“Inizializza la cartella `Wiki` alla radice della KB secondo la skill `llm-wiki`; chiedimi
   dominio e perimetro prima di scrivere.”* Se serve, indica il percorso assoluto di `Wiki/`.
2. Rispondi alle domande (dominio: “azienda di prova”; perimetro: “solo IT”).
3. Chiedi: *“Integra le conoscenze in `Operatori/anna/proposte/knowledge/` e in
   `Operatori/mario/proposte/knowledge/`; verifica e chiudi i file integrati.”*
4. Controlla `Wiki/SCHEMA.md`, `index.md`, `log.md`, le pagine create, la provenienza e la
   cancellazione dei file integrati (o lo spostamento in `Archivio/` con nota, se il cloud non
   permette la cancellazione).
5. Verifica che il fatto di Anna (“I clienti pilota ricevono il report il venerdì”) sia nella pagina
   e che la fonte sia citata.

**Atteso:** la wiki è derivata, non copia i documenti; la coda si chiude solo dopo verifica; nessuna
scrittura in `documenti/`.

#### G3 — Lint della wiki

```sh
python3 "$H_IT/profiles/knowledge-manager/skills/llm-wiki/scripts/wiki_lint.py" "$KB/Wiki" --json
echo $?
```

**Atteso:** exit `0`, `errors: []`, `warnings: []` (o solo avvisi attesi). Poi crea una pagina rotta
in `Wiki/concetti/rotto.md`:

```markdown
---
title: Rotto
type: boh
tags: []
---
[[non-esiste]]
```

Ripeti il lint: **exit 2**, errore per wikilink rotto e frontmatter incompleto; un avviso non blocca.
Rimuovi la pagina rotta e riporta il lint a 0.

#### G4 — Pubblicazione di un documento (facoltativo)

Chiedi al Knowledge Manager di pubblicare un documento di prova con la skill
`pubblica-documento`. Verifica le quattro porte, l'anteprima, la regola LIFO, lo spostamento in
`Archivio/` e il registro con impronta. Se il bot rifiuta perché mancano informazioni, è un
comportamento corretto: annota la domanda e rispondi.

#### G5 — Permessi e perimetro

Con due account reali:

1. Se `Wiki/` è condivisa solo con l'IT, Mario non deve vederla né ricevere citazioni di pagine.
2. Una pagina che cita un documento riservato non deve essere pubblica: rivela l'esistenza del
   documento. Verifica il perimetro scelto.
3. L'IT deve poter leggere le proposte di tutti gli operatori che il cloud gli espone, non di più.

---

### H. Allineamento e controllo manuale

#### H1 — Riconciliazione idempotente

```sh
HERMES_HOME="$H_OP" hermes kb reconcile
HERMES_HOME="$H_OP" hermes kb reconcile
```

**Atteso:** il primo installa i bot mancanti; il secondo dà `unchanged`. Il risultato è anche in
`plugin-data/requrv-kb/watchdog/` (ultimo controllo e risultati).

#### H2 — Bot eliminato: ritorna nuovo

Solo nella fixture:

```sh
HERMES_HOME="$H_OP" hermes profile delete marketing --yes
HERMES_HOME="$H_OP" hermes kb reconcile
```

**Atteso:** riga `marketing installed <versione corrente>`; profilo nuovo, senza chat, memoria o
backup vecchi; registro e record personale ricreati. Se tornano le chat vecchie, è un bug.

#### H3 — Bot non più abilitato: resta

1. Togli `marketing` da `.autorizzazioni.yaml` di Mario (o dall'area) e lancia
   `HERMES_HOME="$H_OP" hermes kb reconcile`.
2. **Atteso:** `not-allowed`; il profilo resta, con chat e memoria. Non deve essere cancellato.
3. Nella pagina Impostazioni il risultato deve dire “non più abilitato, resta sul computer” (non
   “sarà rimosso”).
4. Ripristina l'autorizzazione e riconcilia: il bot torna `unchanged` o `updated`.

#### H4 — Sorgente non disponibile

Rinomina `$KB/Biblioteca-Agenti/marketing` in `marketing-off` e lancia
`HERMES_HOME="$H_OP" hermes kb reconcile`.

**Atteso:** `source-unavailable`, nessuna reinstallazione e nessuna cancellazione; il bot installato
resta utilizzabile. Ripristina il nome e riconcilia.

#### H5 — Avvio, nuova conversazione e controllo manuale

Non esiste un controllo periodico. Verifica i tre trigger reali:

1. **Avvio.** Aggiungi un bot in un'area (o cambia la versione di uno installato), chiudi e riapri
   Hermes Desktop. All'avvio il bot deve comparire/aggiornarsi; “Ultimo controllo” cambia.
2. **Nuova conversazione.** Con un bot di libreria, cambia la versione del suo pacchetto e apri una
   nuova conversazione: il bot aggiorna il proprio profilo all'inizio della sessione; la nuova
   versione vale dalla conversazione successiva.
3. **Controllo manuale.** Premi **Controlla ora**: deve comparire l'esito e “Ultimo controllo”
   aggiornato. Apri due finestre Hermes o due processi e premilo insieme: uno deve dire che un
   controllo è già in corso; non devono girare due riconciliazioni.
4. Controlla `plugin-data/requrv-kb/watchdog/`: file di stato e lock del computer. Non deve esserci
   un intervallo configurato né un thread periodico.

**Atteso:** nessun aggiornamento “a orologio”; i trigger sono avvio, nuova conversazione e richiesta
manuale.

---

### I. Hermes Desktop

#### I1 — Pagina Impostazioni

Apri Impostazioni → Plugin → **ReQurv KB**. Se il Desktop usa una home diversa da `$H_OP`, collega
qui la stessa KB (o una copia) prima di proseguire.

**Atteso:** stato del collegamento con operatore, cartelle e cartella personale; eventuali problemi
in rosso e avvisi in grigio; ultimo controllo e risultati; pulsanti **Modifica collegamento**,
**Scollega**, **Controlla ora**; sezione **Aspetto** con **Tema ReQurv**. Non c'è un campo
“intervallo”: il controllo avviene all'avvio e a ogni nuova conversazione.
Prova a scollegare e ricollegare dalla pagina: i bot restano.
**Nota:** la pagina risponde quando il profilo attivo nell'app è il coordinatore o un bot di
libreria; con un profilo personale può non caricare. È un limite noto, non un errore di questa prova.

#### I2 — Tema

1. Alla prima apertura dopo l'installazione, il tema ReQurv deve essere applicato una volta.
2. Scegli un altro tema da Hermes, riavvia: il plugin non deve sovrascriverlo.
3. Premi **Tema ReQurv**: deve riapplicarsi.

#### I3 — Layout minimal

Applica il layout `requrv-kb:minimal` (dal selettore layout o chiedendo al modello di usare lo
strumento per l'aspetto dell'app).

**Atteso:** Bot a sinistra, chat al centro, Files e Attività pianificate come barre chiuse a destra;
Messaging, Artifacts, Scheduled jobs e Kanban nascosti; Sessions resta (può essere nascosta a mano
dal menu della scheda); Revisione e terminale non si aprono. Riavvia: il layout resta. Torna a un
altro layout e verifica che sia reversibile.

#### I4 — Controllo all'avvio

1. Aggiungi un nuovo bot in un'area della fixture (o cambia la versione di uno esistente).
2. Chiudi e riapri Hermes Desktop.
3. Entro l'avvio il bot deve comparire/aggiornarsi, con notifica se c'è qualcosa da fare.

**Atteso:** nessun blocco dell'app; se il controllo è già in corso, un messaggio, non un doppio run.

---

### J. Holographic (opzionale)

Holographic non è una dipendenza: serve solo a verificare la memoria locale opzionale. Usa una home
separata, non la KB di produzione.

```sh
export H_HOLO="$TEST_ROOT/hermes-holo"
export HERMES_HOME="$H_HOLO"
hermes plugins install holographic --no-deps --no-enable
hermes plugins enable holographic
hermes config set memory.provider holographic
hermes memory status
```

Poi:

1. Apri una chat, scrivi un fatto sintetico con `fact_store add` e cercalo con `fact_store search`.
2. Riavvia e verifica che il fatto sia ancora recuperabile (SQLite per profilo).
3. Lascia `auto_extract` disattivato; verifica che un fatto italiano scritto durante un turno non
   venga estratto automaticamente.
4. Verifica che non ci siano chiamate di rete e che Hindsight non sia installato o richiesto.
5. Con Holographic attivo, ripeti F2: la cattura ReQurv deve continuare a funzionare e la coda
   Markdown deve restare la fonte di verità.

Dettagli e caveat: `.unlazy/passive-knowledge/holographic-evidence.md`.

---

### K. Windows nativo — gate G2

Questa è l'unica parte ancora aperta. Va eseguita su Windows con Hermes Desktop, non in WSL e non
su macOS.

#### K1 — Installazione e percorsi

1. Installa il plugin dal link `hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1` (PowerShell:
   `Start-Process 'hermes://plugin/install?repo=CesaTor/hermes-kb&enable=1'`) oppure da
   Capabilities → Plugins → Install from Git; riavvia.
2. Usa percorsi realistici: `C:\Users\<utente>\ReQurv KB\...`, con spazi, lettera di unità e
   OneDrive. Se i file sono online-only, rendili disponibili offline.
3. Collega la KB con `hermes kb connect` o dalla pagina Impostazioni.
4. `hermes kb check` deve dare `OK`; `hermes kb list` deve mostrare i bot dell'area.

#### K2 — Bot e chat

1. Installa `marketing` e apri una chat.
2. Verifica le cartelle nel prompt, la versione e la citazione di un documento.
3. Chiedi una modifica al SOUL e verifica la proposta in `Operatori\<nome>\proposte\marketing\`.
4. Chiedi di modificare `config.yaml` e verifica il rifiuto.

#### K3 — Cattura, dedup e lock

1. Chiedi una cattura con fonte; verifica il Markdown e i metadati.
2. Chiudi e riapri Hermes; ripeti la cattura: un solo file.
3. Apri due chat (marketing e finanza, abilitando `finanza` come in F6) e chiedi lo stesso fatto
   insieme; un solo file.
4. Controlla che non restino `.tmp` e che `knowledge-capture.lock` sia gestito anche su Windows.

#### K4 — IT, sincronizzazione e wiki

1. Con l'account IT, verifica `hermes kb it list` e `it show`.
2. Accetta una proposta, sincronizza e verifica l'aggiornamento sul lato operatore.
3. Integra una conoscenza nella wiki e lancia `wiki_lint.py` con Python su Windows.
4. Verifica i permessi: l'operatore non deve vedere la wiki o le proposte che il cloud non gli dà.

#### K5 — Desktop

1. Pagina Impostazioni, collegamento, ultimo controllo, “Controlla ora”.
2. Tema ReQurv: prima applicazione, scelta di un altro tema, riapplicazione dal pulsante.
3. Layout minimal, voci del menu, Sessions, riavvio.
4. Controllo all'avvio con un bot nuovo o aggiornato.

#### K6 — Controllo e rollback

1. `hermes kb update` / `rollback`; verifica backup e chat conservate.
2. Elimina un bot e `kb reconcile`: deve tornare nuovo, senza chat.
3. Rinomina la cartella di un pacchetto: `source-unavailable`, nessuna cancellazione.
4. Disinstalla/riavvia/reinstalla il plugin: collegamento, bot e proposte devono restare.

#### K7 — Casi Windows specifici

- File online-only di OneDrive: avviso e nessun download bloccante.
- Percorsi con spazi, accenti e nomi lunghi.
- File bloccato da antivirus durante un aggiornamento: errore leggibile, nessuna perdita.
- Cartella personale in sola lettura: la cattura fallisce con un messaggio, non corrompe la coda.
- `hermes plugins update requrv-kb` con gateway aperto: avviso di riavvio e comportamento corretto
  dopo il riavvio.

**Criterio G2:** tutti i punti K1–K7 passano su Windows nativo, con evidenze allegate. Fino ad
allora G2 resta aperto.

---

### L. Errori e recupero

#### L1 — Rollback dopo un aggiornamento

Coperto da C4. Verifica che il backup contenga i file sostituiti e che il rollback non cancelli chat
o memoria.

#### L2 — Collegamento danneggiato

Copia `connection.json`, scrivi contenuto non valido, lancia
`HERMES_HOME="$H_OP" hermes kb check`: deve dire “non collegato”, non crashare. Ripristina il file o
ricollega.

#### L3 — Cattura con cartella personale in sola lettura

Su macOS/Linux: `chmod -R a-w "$KB/Operatori/mario/proposte"`; prova una cattura. Atteso: errore
leggibile, nessun file parziale. Ripristina i permessi.

#### L4 — Coda con file temporanei

Dopo una cattura riuscita, nella cartella non devono restare file che iniziano con `.` e finiscono
con `.tmp`. Se ne trovi, annota il nome e il momento.

#### L5 — Plugin disabilitato

`HERMES_HOME="$H_OP" hermes -p marketing plugins disable requrv-kb` (il bot ha la sua copia del
plugin nel profilo), riapri una chat: il bot funziona senza prompt KB e senza cattura. Riabilita con
`HERMES_HOME="$H_OP" hermes -p marketing plugins enable requrv-kb` e riapri: prompt e cattura
tornano.

#### L6 — Indice dedup cancellato

Cancella `knowledge-dedup-*.json` e ripeti una cattura già integrata e cancellata: il file può
ricomparire. È il limite documentato del dispositivo che non ha memoria; non è una regressione. Se
ricompare **con l'indice presente**, è un bug.

---

## 6. Evidenze e criteri di accettazione

Per ogni prova conserva:

- data, macchina, sistema operativo, versione Hermes e versione plugin;
- il percorso di `HERMES_HOME`, della KB e della cartella personale;
- comando eseguito e output completo (o screenshot);
- file prodotti o modificati (`ls`, estratto del frontmatter);
- per le chat: screenshot della risposta e, se serve, ID sessione.

Criteri minimi per dichiarare il collaudo superato:

- [ ] S1–S10 del percorso rapido passano.
- [ ] Nessuna scrittura fuori da `Operatori/<nome>` durante i flussi normali.
- [ ] Nessuna proposta duplicata dopo riavvio o due processi.
- [ ] Nessun segreto o dato riservato finito in una proposta o nella wiki.
- [ ] IT: accetta/rifiuta/lint funzionano; la coda si chiude solo dopo verifica.
- [ ] Aggiornamento e rollback non perdono chat, memoria o proposte.
- [ ] Scollegamento e riconnessione non eliminano bot.
- [ ] Windows K1–K7 passano (G2).

**Stop immediato** se: un operatore vede dati di un altro, un segreto viene salvato, un aggiornamento
cancella chat o memoria, la wiki pubblica una fonte riservata, o due catture producono due file con
lo stesso fatto.

---

## 7. Pulizia

1. Esporta le evidenze fuori da `$TEST_ROOT`.
2. Scollega la KB dalle home di test:

   ```sh
   HERMES_HOME="$H_OP" hermes kb disconnect
   HERMES_HOME="$H_IT" hermes kb disconnect
   ```

3. Elimina i profili di test e le due home:

   ```sh
   rm -rf "$TEST_ROOT"
   ```

4. Se hai usato un utente di test del Desktop, eliminalo o ripristina la VM.
5. Se hai usato quote cloud di test, revoca le condivisioni e cancella gli account di prova.

Non cancellare la fixture prima di aver allegato le evidenze: i percorsi nei log non bastano.

---

## 8. Comandi rapidi

```sh
# Collegamento
hermes kb connect --root "<cartella>" --root "<altra>" --operator <nome> [--personal "<personale>"]
hermes kb check
hermes kb disconnect

# Catalogo e bot
hermes kb list
hermes kb install marketing
hermes kb status
hermes kb update marketing
hermes kb rollback marketing
hermes kb duplicate marketing marketing-personale
hermes kb reconcile

# Versioni personali (nel profilo del bot)
hermes -p marketing kb resolve --kind soul --choice keep
hermes -p marketing kb resolve --kind skill --name brand --choice take

# IT
hermes kb it list
hermes kb it knowledge
hermes kb it show --operator anna --bot marketing
hermes kb it accept --operator anna --bot marketing --yes
hermes kb it reject --operator anna --bot marketing --reason "motivo"
hermes kb updates
hermes kb updates --apply

# Wiki
python3 "$H_IT/profiles/knowledge-manager/skills/llm-wiki/scripts/wiki_lint.py" "$KB/Wiki" --json
```

Per una prova rapida del solo servizio di cattura, senza modello, si può usare la suite automatica:

```sh
PYTHONPATH="/percorso/hermes-upstream:$PWD" python3.13 -m pytest tests/test_knowledge_capture_unit.py -q
```

I test automatici non sostituiscono A2, C2, E6, G2, G5 e tutta la sezione K: quelle parti richiedono
Hermes reale, Desktop, cloud e Windows.
