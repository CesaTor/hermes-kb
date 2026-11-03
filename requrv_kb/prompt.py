"""What a session starts with: where the KB is, and the operator's proposed SOUL additions.

A library bot's SOUL.md belongs to the library and is locked. What the user would otherwise change
in it lives in the operator's proposals file, ``<personal>/proposte/<bot>.md``, one ``## <id>``
block per proposal. The bot applies that file on top of its SOUL from the next session, so the user
never needs a personal copy; IT reads the file from the operator's island, folds the good proposals
into the library SOUL and lists their ids in ``proposals_resolved`` (or ``proposals_rejected``), and
the next sync updates every user's bot and archives those blocks (:func:`library.archive_proposals`).

Both sections are frozen into each new session's system prompt (Hermes' plugin prompt sections),
so an edit applies to the next conversation and never rewrites a cached prompt mid-session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from . import connection as kb_connection
from . import ledger
from .cloud_files import is_online_only

PROPOSALS_DIRNAME = "proposte"
# Hermes caps one plugin prompt section at 4,000 characters; keep room for the header.
_PROPOSALS_BUDGET = 3_600


def _library_bot() -> Optional[tuple[str, dict[str, Any]]]:
    from hermes_constants import get_hermes_home

    home = Path(get_hermes_home())
    record = ledger.read(home)
    return (record.get("bot") or home.name, record) if record is not None else None


def proposals_path(conn: kb_connection.Connection, bot: str) -> Path:
    return Path(conn.personal) / PROPOSALS_DIRNAME / f"{bot}.md"


def organization_root(conn: kb_connection.Connection) -> Optional[Path]:
    """The folder holding ``Biblioteca-Agenti`` (what library skills call ``$SECOND_BRAIN_ROOT``)."""
    libraries = kb_connection.library_dirs(conn.roots)
    return libraries[0].parent if len(libraries) == 1 else None


def section(_session: Mapping[str, Any] | None = None) -> str:
    conn = kb_connection.load()
    if conn is None:
        return ""
    lines = [
        "## Knowledge base aziendale (ReQurv KB)",
        "Cartelle della KB sincronizzate su questo computer:",
        *(f"- {root}" for root in conn.roots),
        f"Cartella personale dell'operatore {conn.operator}: {conn.personal}",
        *([f"La radice dell'organizzazione ($SECOND_BRAIN_ROOT nelle skill) è {root}."]
          if (root := organization_root(conn)) else []),
        "Leggi i documenti da queste cartelle e cita sempre i file da cui prendi le informazioni.",
        "Scrivi bozze e nuovi file solo nella cartella personale; i permessi del cloud decidono il resto.",
    ]
    bot = _library_bot()
    if bot is not None:
        name, record = bot
        lines += [
            f"Sei il bot di libreria «{name}» (versione {record.get('version')}). Il tuo SOUL.md è della "
            "libreria aziendale e non si modifica.",
            "Quando l'utente vuole cambiare in modo stabile il tuo comportamento, tono, regole o compiti, "
            f"scrivi la modifica come proposta in {proposals_path(conn, name)}: aggiungi un blocco che inizia "
            "con «## <id-breve>» (es. «## tono-formale»), seguito dalla regola scritta come istruzione diretta, "
            "esattamente come andrebbe nel SOUL (es. «Dai sempre del lei.»), e da una riga «Motivo: ...». "
            "Non cancellare i blocchi esistenti; per correggerne uno, modificalo.",
            "Le proposte valgono per questo operatore dalla prossima conversazione; l'IT le valuta e, se "
            "approvate, entrano nel SOUL di tutti con il prossimo aggiornamento del bot.",
        ]
    return "\n".join(lines)


def proposals_section(_session: Mapping[str, Any] | None = None) -> str:
    """The operator's proposals file for this library bot, applied as an extension of its SOUL."""
    conn = kb_connection.load()
    bot = _library_bot()
    if conn is None or bot is None:
        return ""
    path = proposals_path(conn, bot[0])
    try:
        if not path.is_file() or is_online_only(path.stat()):
            return ""
        text = path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return ""
    if not text:
        return ""
    if len(text) > _PROPOSALS_BUDGET:
        text = text[:_PROPOSALS_BUDGET].rstrip() + f"\n[... continua: leggi il file completo {path}]"
    return ("## Regole aggiuntive dell'operatore (fanno parte del tuo SOUL)\n"
            "Le regole qui sotto valgono già, in questa conversazione e in ogni risposta: seguile come il resto "
            "del tuo SOUL e, in caso di conflitto, prevalgono. Sono in attesa di revisione IT, ma questo non "
            "cambia nulla per te. Le righe «Motivo:» spiegano la regola e non vanno seguite.\n\n" + text)
