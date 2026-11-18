"""One library reconciliation, run at app start, on demand, or by `hermes kb reconcile`.

There is no periodic timer and no background thread: the bot update is checked when Hermes starts,
when a library bot starts a new conversation, and when the operator asks for it. A machine-wide
lease under the default Hermes root keeps two checks from overlapping, even when several profiles
or processes are open; the OS releases the lock if a process dies.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from . import connection as kb_connection
from .paths import data_dir, read_json, write_json

logger = logging.getLogger(__name__)

_STATE_DIRNAME = "watchdog"
_LAST_RUN = "last-run.json"
_LOCK_FILE = "lease.lock"


def state_dir() -> Path:
    return data_dir() / _STATE_DIRNAME


def _lock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    # POSIX: closing the handle releases the flock


@contextlib.contextmanager
def lease(path: Path | None = None, *, timeout: float = 0) -> Iterator[bool]:
    """Yield whether the local lock could be acquired within the supplied timeout."""
    path = path if path is not None else state_dir() / _LOCK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as handle:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"\0")  # msvcrt locks a byte range, so there must be a byte to lock
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                _lock(handle)
                break
            except OSError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    yield False
                    return
                time.sleep(min(remaining, 0.05))
        try:
            yield True
        finally:
            _unlock(handle)


def last_run() -> Optional[dict[str, Any]]:
    data = read_json(state_dir() / _LAST_RUN)
    return data if isinstance(data, dict) and isinstance(data.get("at"), (int, float)) else None


def summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    actions = [r.get("action") for r in results]
    return {"installed": actions.count("installed"), "updated": actions.count("updated"),
            "errors": actions.count("error") + actions.count("source-unavailable"),
            "not_allowed": actions.count("not-allowed")}


def status(clock: Callable[[], float] = time.time) -> dict[str, Any]:
    """What the settings page shows: whether the computer is connected and the last check."""
    conn = kb_connection.load()
    record = last_run()
    return {"connected": conn is not None,
            "last_run": ({"at": record["at"], "results": record.get("results", []),
                          "summary": summarize(record.get("results", [])), "error": record.get("error")}
                         if record else None),
            "now": clock()}


def _reconcile_and_record(reconcile: Callable[[], list[dict[str, Any]]], clock: Callable[[], float]) -> dict[str, Any]:
    """Run one reconcile and store its outcome; a run that crashed is stored too, so it is not lost."""
    results: list[dict[str, Any]] = []
    error: Optional[str] = None
    try:
        results = reconcile()
    except Exception as exc:  # noqa: BLE001 - the outcome is recorded and shown, never lost
        logger.exception("requrv-kb reconcile failed")
        error = str(exc) or type(exc).__name__
    record = {"at": clock(), "results": results, "error": error}
    write_json(state_dir() / _LAST_RUN, record)
    for result in results:
        if result.get("action") != "unchanged":
            logger.info("requrv-kb reconcile %s: %s %s", result.get("profile"), result.get("action"),
                        result.get("error", ""))
    return record


def run(*, clock: Callable[[], float] = time.time,
        reconcile: Optional[Callable[[], list[dict[str, Any]]]] = None) -> Optional[dict[str, Any]]:
    """Run one reconciliation under the machine-wide lease; None when not connected or already busy."""
    if reconcile is None:
        from . import library

        reconcile = library.reconcile
    if kb_connection.load() is None:
        return None
    with lease() as held:
        if not held:
            return None
        return _reconcile_and_record(reconcile, clock)
