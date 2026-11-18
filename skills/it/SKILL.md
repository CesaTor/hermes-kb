---
name: revisione-proposte
description: Rivedere le proposte degli operatori (SOUL, skill, conoscenze) e gestire gli aggiornamenti della KB.
---

# Revisione delle proposte — reparto IT

Usa questa skill quando l'utente (IT) chiede di vedere cosa hanno proposto gli operatori, di
valutare una modifica a un bot o di allineare i bot della libreria. I tool `kb_proposals` e
`kb_updates` sono disponibili solo se il tuo `.autorizzazioni.yaml` contiene `ruolo: it`.

## Il ciclo

1. **Elenca** — `kb_proposals` con `action: list`: per ogni operatore e bot vedi i file cambiati e la
   versione del pacchetto da cui la proposta parte (`base_version`).
2. **Guarda le differenze** — `action: show` con `operator` e `bot`: le righe `-` sono la versione
   dell'operatore, le `+` quella certificata. Se ti serve il file intero, leggilo dal percorso
   restituito.
3. **Discuti** — riassumi in tre righe cosa cambia e perché. Non accettare nulla senza che l'IT
   abbia detto di sì.
4. **Accetta o rifiuta** —
   - `action: accept` **senza** `confirm` restituisce il piano (file, versione attuale e nuova).
     Rilancia con `confirm: true` solo dopo il sì esplicito.
   - `action: reject` con un `reason`: la proposta va in `proposte/Archivio/` con `RIFIUTATA.md`.
     Non cancellarla mai: la cancellazione significa «integrata».

## Criteri per accettare

- **Generale, non personale**: la modifica ha senso per tutti gli operatori del bot? Se serve solo a
  uno, resta la sua versione personale e la proposta si rifiuta spiegando perché.
- **Nessun segreto**: chiavi, token, password, dati di clienti o informazioni personali non entrano
  nel pacchetto.
- **Coerente con il SOUL certificato**: una proposta che contraddice l'identità del bot va riscritta,
  non accettata così com'è.
- **Skill con script**: Python, senza percorsi assoluti, senza dipendenze fuori da quelle già
  dichiarate; apri `scripts/` prima di accettare.
- **Nessuna cancellazione silenziosa**: se la proposta rimuove contenuto, chiedi il motivo e
  riportalo nel riepilogo.

## Versioni e aggiornamenti

- `accept` alza la patch (`1.4.0 → 1.4.1`) nel `distribution.yaml` del pacchetto. Se la modifica è
  sostanziale, proponi all'IT un salto di minor (`1.5.0`) e fallo a mano nel file.
- Dopo l'accettazione i bot degli operatori ricevono la versione al controllo successivo (ogni 30
  minuti, all'avvio e a ogni nuova conversazione). Chi aveva una versione personale di quel file
  riceverà la domanda «tieni la tua o prendi la nuova?».
- `kb_updates` con `action: list` dice cosa la libreria offre e questo computer non ha; `apply`
  installa e aggiorna qui. Non è la stessa cosa di accettare una proposta: quello cambia il
  pacchetto per tutti.

## Conoscenze raccolte

I file in `Operatori/<nome>/proposte/knowledge/` sono cose che gli operatori hanno scoperto su
azienda e flussi. Non si «approvano»: si integrano nella documentazione condivisa (documenti
dell'area, con le regole di pubblicazione) e **poi** si cancellano dalla cartella. Se non servono,
spostali in `proposte/Archivio/` con il motivo: la cancellazione resta il segnale di «integrata».

## Nel dubbio

Fermati e chiedi all'IT. Non accettare una proposta per chiudere una coda, non modificare il
pacchetto con strumenti diversi da `kb_proposals`, non toccare la cartella personale di un
operatore oltre a leggerla.
