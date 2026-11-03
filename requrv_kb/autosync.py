"""Library updates without the app: a new conversation with a library bot checks its package.

``on_session_start`` fires on the first turn, after the session prompt is built, so the check runs
in the background and a new version applies from the next conversation (never mid-conversation).
The check is one manifest read when nothing changed; it runs at most once per bot per
:data:`MIN_INTERVAL_S` in a process.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from . import ledger

logger = logging.getLogger(__name__)
MIN_INTERVAL_S = 300
_last: dict[str, float] = {}
_guard = threading.Lock()


def _run(profile: Path) -> None:
    from . import library

    for result in library.sync(only=profile):
        if result["status"] != "unchanged":
            logger.info("requrv-kb sync %s: %s %s", result["profile"], result["status"], result.get("error", ""))


def on_session_start(**_: Any) -> None:
    from hermes_constants import get_hermes_home

    profile = Path(get_hermes_home())
    if ledger.read(profile) is None:
        return
    key = str(profile)
    with _guard:
        if time.monotonic() - _last.get(key, -MIN_INTERVAL_S) < MIN_INTERVAL_S:
            return
        _last[key] = time.monotonic()
    from agent.memory_provider import spawn_context_thread

    spawn_context_thread(_run, name="requrv-kb-sync", args=(profile,)).start()
