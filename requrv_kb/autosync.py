"""Library updates without the app: a new conversation with a library bot checks its package.

``on_session_start`` fires on the first turn, after the session prompt is built, so the check runs
in the background and a new version applies from the next conversation (never mid-conversation).
When nothing changed the check is one manifest read; one check per bot runs at a time.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from . import ledger

logger = logging.getLogger(__name__)
_running: set[str] = set()
_guard = threading.Lock()


def _run(profile: Path) -> None:
    from . import library

    try:
        for result in library.sync(only=profile):
            if result["status"] != "unchanged":
                logger.info("requrv-kb sync %s: %s %s", result["profile"], result["status"], result.get("error", ""))
    finally:
        with _guard:
            _running.discard(str(profile))


def on_session_start(**_: Any) -> None:
    from hermes_constants import get_hermes_home

    profile = Path(get_hermes_home())
    if ledger.read(profile) is None:
        return
    with _guard:
        if str(profile) in _running:
            return
        _running.add(str(profile))
    from agent.memory_provider import spawn_context_thread

    spawn_context_thread(_run, name="requrv-kb-sync", args=(profile,)).start()
