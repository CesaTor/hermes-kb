"""Which bots this operator may install, and whether this machine also reviews proposals.

The cloud ACL decides what each account can *read*; a bot the operator can read is not necessarily
a bot they may install. The IT narrows that with a hidden, read-only file in the operator's folder::

    # Operatori/mario/.autorizzazioni.yaml
    operator: mario
    bots: [marketing, finanza-controllo]
    ruolo: operatore          # `it` for the reviewer's own folder

Missing or unreadable means "no narrowing" (every bot the areas enable), which is the behaviour
before this file existed: a lost file must not lock the whole company out of its bots.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .paths import KBError
from .yamlio import safe_load

FILENAME = ".autorizzazioni.yaml"


def path(conn: Any) -> Path:
    return Path(conn.personal) / FILENAME


def read(conn: Any) -> dict[str, Any]:
    """``{present, bots (set or None), it, error}``; never raises."""
    target = path(conn)
    if not target.is_file():
        return {"present": False, "bots": None, "it": False, "error": None}
    try:
        data = safe_load(target)
    except KBError as exc:
        return {"present": True, "bots": None, "it": False, "error": str(exc)}
    if not isinstance(data, dict):
        return {"present": True, "bots": None, "it": False,
                "error": f"{FILENAME} non contiene una mappa di impostazioni."}
    raw = data.get("bots")
    bots: Optional[set[str]] = None
    if isinstance(raw, list):
        bots = {str(item).strip() for item in raw if str(item).strip()}
    elif raw == "*":
        bots = None
    role = str(data.get("ruolo") or "").strip().lower()
    reviewer = bool(data.get("it") or data.get("revisore")) or role in {"it", "revisore", "reviewer"}
    return {"present": True, "bots": bots, "it": reviewer, "error": None}


def allowed(conn: Any) -> Optional[set[str]]:
    """The bot names this operator may install, or None when the file does not narrow anything."""
    return read(conn)["bots"]


def permits(conn: Any, name: str) -> bool:
    names = allowed(conn)
    return names is None or name in names


def is_it(conn: Any) -> bool:
    return bool(read(conn)["it"])


def refusal(name: str) -> str:
    return (f"Non hai l'autorizzazione per il bot «{name}». Il tuo file .autorizzazioni.yaml non lo "
            "elenca: chiedi all'IT della KB.")
