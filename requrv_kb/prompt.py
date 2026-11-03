"""The KB context a session starts with: where the company folders are on this computer.

Frozen into each new session's system prompt (Hermes' plugin prompt sections), so a change of
connection applies to the next conversation and never rewrites a cached prompt mid-session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import connection as kb_connection
from . import ledger


def section(_session: Mapping[str, Any] | None = None) -> str:
    conn = kb_connection.load()
    if conn is None:
        return ""
    from hermes_constants import get_hermes_home

    record = ledger.read(Path(get_hermes_home()))
    lines = [
        "## Knowledge base aziendale (ReQurv KB)",
        "Cartelle della KB sincronizzate su questo computer:",
        *(f"- {root}" for root in conn.roots),
        f"Cartella personale dell'operatore {conn.operator}: {conn.personal}",
        "Leggi i documenti da queste cartelle e cita sempre i file da cui prendi le informazioni.",
        "Scrivi bozze e nuovi file solo nella cartella personale; i permessi del cloud decidono il resto.",
    ]
    if record is not None:
        bot = record.get("bot") or Path(get_hermes_home()).name
        lines.append(f"Sei il bot di libreria «{bot}» (versione {record.get('version')}). Le modifiche alle tue "
                     f"istruzioni si propongono in {Path(conn.personal) / 'proposte' / (bot + '.md')}, "
                     "un blocco «## <id>» per proposta.")
    return "\n".join(lines)
