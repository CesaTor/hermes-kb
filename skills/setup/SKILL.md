---
name: setup
description: Collegare questo computer alla KB aziendale ReQurv e installare i bot della libreria.
---

# Collegare la KB aziendale

Usa questa skill quando l'utente vuole collegare la KB, vedere i bot disponibili o installarne uno.

1. Chiedi il percorso locale delle cartelle sincronizzate (Nextcloud, Drive): la libreria
   `Biblioteca-Agenti`, le cartelle di area (`01-Marketing`, ...) e la cartella personale in
   `Operatori/<nome>`. Possono essere cartelle separate.
2. Collega con il comando, una `--root` per cartella:
   `/kb connect --root "<cartella>" --root "<altra cartella>" --operator <nome>`
3. Controlla con `/kb check`. Un file "non ancora scaricato" va reso disponibile offline nell'app
   di sincronizzazione.
4. `/kb list` mostra i bot offerti; `/kb install <nome>` installa, `/kb update <nome>` aggiorna,
   `/kb rollback <nome>` torna alla versione precedente.
5. Il **SOUL** di un bot di libreria è certificato e viene sostituito a ogni aggiornamento: non si
   modifica. Per un'identità propria, duplica il bot con `/kb duplicate <nome> "<nome copia>"`.
6. Le **skill** si possono personalizzare: la modifica resta sul computer e viene copiata in
   `proposte/<bot>/` per l'IT. Se una nuova versione tocca la stessa skill, il bot chiede se tenere
   la propria o prendere la nuova (`/kb resolve --kind skill --name <nome> --choice keep|take`).
7. Il plugin copia `MEMORY.md`, `USER.md` e, se Holographic è attivo, `memory_store.db` in
   `Operatori/<nome>/memoria/<bot>/`. È un backup di lavoro, non una pagina della wiki.
8. Le chiavi gestite di `config.yaml` e le attività pianificate non si modificano: sono della libreria.
9. Se sei il reparto IT (`ruolo: it` in `.autorizzazioni.yaml`): `/kb it list`, `/kb it show`,
   `/kb it accept --yes`, `/kb it reject --reason`, `/kb updates --apply`.

Le nuove istruzioni valgono dalla prossima conversazione. I permessi delle cartelle li decide il
cloud: il plugin non concede né toglie accessi.
