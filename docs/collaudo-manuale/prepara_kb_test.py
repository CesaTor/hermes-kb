#!/usr/bin/env python3
"""Create a disposable synthetic KB for the ReQurv KB manual test runbook.

Usage:
    python3 prepara_kb_test.py /tmp/requrv-collaudo

The target must not exist, or be an empty directory. Nothing outside it is touched. The fixture has
no real company data, no credentials and no provider key: use it with a disposable Hermes home or a
test machine.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KNOWLEDGE_MANAGER = REPO / "kb-template" / "Biblioteca-Agenti" / "knowledge-manager"
SETUP_AGENTS = REPO / "kb-template" / "SETUP" / "AGENTS.md"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build(root: Path) -> None:
    kb = root / "KB"
    library = kb / "Biblioteca-Agenti"

    marketing = library / "marketing"
    write(marketing / "distribution.yaml", """\
name: marketing
version: 1.0.0
description: "Bot di prova per il collaudo ReQurv KB"
author: ReQurv Test
config_managed:
  - agent.max_turns
""")
    write(marketing / "SOUL.md", """\
# Marketing (prova)

Rispondi in italiano e cita i documenti della KB.
""")
    write(marketing / "skills" / "brand" / "SKILL.md", """\
---
name: brand
description: Domande sul brand e sui materiali di marketing.
---
# Brand

Il brand di prova usa il colore blu e un tono informale.
""")
    write(marketing / "config.yaml", """\
agent:
  max_turns: 20
""")

    finanza = library / "finanza"
    write(finanza / "distribution.yaml", """\
name: finanza
version: 1.0.0
description: "Bot di prova per il collaudo ReQurv KB"
author: ReQurv Test
""")
    write(finanza / "SOUL.md", """\
# Finanza (prova)

Rispondi in italiano e cita il listino quando parli di prezzi.
""")

    # A package no area lists: it must never appear in the catalogue.
    vendite = library / "vendite"
    write(vendite / "distribution.yaml", """\
name: vendite
version: 1.0.0
description: "Pacchetto non abilitato: non deve comparire"
author: ReQurv Test
""")
    write(vendite / "SOUL.md", "# Vendite (prova)\n")

    if not KNOWLEDGE_MANAGER.is_dir():
        raise SystemExit(f"Template Knowledge Manager non trovato: {KNOWLEDGE_MANAGER}")
    shutil.copytree(KNOWLEDGE_MANAGER, library / "knowledge-manager")

    write(kb / "SETUP" / "AGENTS.md", SETUP_AGENTS.read_text(encoding="utf-8"))

    write(kb / "01-Marketing" / "bots.yaml", "bots:\n- marketing\n- finanza\n")
    write(kb / "01-Marketing" / "documenti" / "piano-marketing-2026.md", """\
# Piano marketing 2026

Il budget approvato è 50.000 euro. La campagna parte a marzo.
""")
    write(kb / "01-Marketing" / "documenti" / ".bozza-interna.md", """\
# Bozza interna

Questo file è nascosto e non deve essere citabile.
""")
    write(kb / "02-Finanza" / "bots.yaml", "bots:\n- marketing\n- finanza\n")
    write(kb / "02-Finanza" / "documenti" / "listino-2026.md", """\
# Listino 2026

Il listino aumenta del 5% da gennaio.
""")
    write(kb / "90-IT" / "bots.yaml", "bots:\n- knowledge-manager\n- marketing\n- finanza\n")
    write(kb / "90-IT" / "documenti" / "linee-guida-it.md", """\
# Linee guida IT

Le proposte si verificano prima di pubblicare una pagina nella wiki.
""")
    write(kb / "Riservato" / "01-Finanza" / "documenti" / "retribuzioni.md", """\
# Retribuzioni

Dato riservato: non deve mai entrare in una proposta o nella wiki.
""")

    operators = kb / "Operatori"
    write(operators / "mario" / ".autorizzazioni.yaml", """\
operator: mario
bots: [marketing]
ruolo: operatore
""")
    write(operators / "mario" / "skills" / ".gitkeep", "")
    write(operators / "anna" / ".autorizzazioni.yaml", """\
operator: anna
bots: [marketing, finanza]
ruolo: operatore
""")
    write(operators / "it" / ".autorizzazioni.yaml", """\
operator: it
bots: "*"
ruolo: it
""")

    # A proposal already waiting, so the IT review can be tested before any chat.
    anna_proposal = operators / "anna" / "proposte" / "marketing"
    write(anna_proposal / "SOUL.md", """\
# Marketing (proposta di Anna)

Rispondi in italiano, dai del lei e cita sempre la fonte.
""")
    write(anna_proposal / "proposal.yaml", """\
bot: marketing
operatore: anna
base_version: 1.0.0
aggiornato_il: "2026-11-18T09:00:00+00:00"
file:
  SOUL.md: "prova"
""")
    write(operators / "anna" / "proposte" / "knowledge" / "20261118-090000-clienti.md", """\
---
data: "2026-11-18T09:00:00+00:00"
autore: anna
bot: marketing
argomento: "Clienti pilota"
fonti: []
session_id: "sessione-di-prova"
---

I clienti pilota ricevono il report il venerdì.
""")

    (root / "hermes-operator").mkdir(parents=True, exist_ok=True)
    (root / "hermes-it").mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea una KB sintetica per il collaudo manuale.")
    parser.add_argument("target", type=Path, help="Cartella nuova o vuota dove creare la fixture")
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        print(f"ERRORE: {target} esiste e non è vuota. Scegli una cartella nuova.", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    build(target)
    print(f"Fixture creata in: {target}")
    print(f"KB:               {target / 'KB'}")
    print(f"HERMES_OPERATOR:  {target / 'hermes-operator'}")
    print(f"HERMES_IT:        {target / 'hermes-it'}")
    print()
    print("Prossimo passo: installa il plugin nelle due home e collega la KB.")
    print("Le istruzioni esatte sono nella guida, sezione 4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
