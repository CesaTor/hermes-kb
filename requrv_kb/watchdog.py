"""The watchdog: every interval (30 minutes by default) bring the bots in line with the library.

Every Hermes process that loads the plugin (one per profile, plus CLI runs) starts a thread
(:func:`start`), so the schedule is a machine-wide **lease** under the default Hermes root, never
a per-process timer: a run happens only when the last one finished at least one interval ago and
no other process holds the lock. The lock is a non-blocking OS file lock (``fcntl.flock`` on
POSIX, ``msvcrt.locking`` on Windows), released by the OS if the holder dies, so a crash never
leaves a stale lease.

Hermes exposes no signal telling a long-running server from a one-shot ``hermes kb ...`` run at
registration, so the thread waits :data:`START_DELAY_S` before its first check: a short command
exits before ever reconciling, a Desktop or gateway process does not.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from . import connection as kb_connection
from .paths import data_dir, read_json, write_json

logger = logging.getLogger(__name__)

POLL_S = 300  # how often the thread looks at the lease
START_DELAY_S = 60
_STATE_DIRNAME = "watchdog"
_LAST_RUN = "last-run.json"
_LOCK_FILE = "lease.lock"
_STOP_JOIN_S = 5


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
def lease() -> Iterator[bool]:
    """Yield True while this process holds the machine-wide lock, False when another one does."""
    path = state_dir() / _LOCK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as handle:
        if path.stat().st_size == 0:
            handle.write(b"\0")  # msvcrt locks a byte range, so there must be a byte to lock
            handle.flush()
        try:
            _lock(handle)
        except OSError:
            yield False
            return
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
            "removed": actions.count("removed")}


def _interval_s() -> Optional[float]:
    conn = kb_connection.load()
    return conn.watchdog_minutes * 60 if conn else None


def status(clock: Callable[[], float] = time.time) -> dict[str, Any]:
    """What the settings page shows: the interval, the last check with its results, when the next is due."""
    conn = kb_connection.load()
    record = last_run()
    minutes = conn.watchdog_minutes if conn else kb_connection.DEFAULT_WATCHDOG_MINUTES
    due = record["at"] + minutes * 60 if record else None
    return {"connected": conn is not None, "interval_minutes": minutes,
            "min_minutes": kb_connection.MIN_WATCHDOG_MINUTES,
            "last_run": ({"at": record["at"], "results": record.get("results", []),
                          "summary": summarize(record.get("results", [])), "error": record.get("error")}
                         if record else None),
            "next_due": due if conn else None, "now": clock()}


def _reconcile_and_record(reconcile: Callable[[], list[dict[str, Any]]], clock: Callable[[], float]) -> dict[str, Any]:
    """Run one reconcile and store its outcome; a run that crashed is stored too, so it is not retried hot."""
    results: list[dict[str, Any]] = []
    error: Optional[str] = None
    try:
        results = reconcile()
    except Exception as exc:  # noqa: BLE001 - the outcome is recorded and shown, never lost
        logger.exception("requrv-kb watchdog: reconcile failed")
        error = str(exc) or type(exc).__name__
    record = {"at": clock(), "results": results, "error": error}
    write_json(state_dir() / _LAST_RUN, record)
    for result in results:
        if result.get("action") != "unchanged":
            logger.info("requrv-kb watchdog %s: %s %s", result.get("profile"), result.get("action"),
                        result.get("error", ""))
    return record


def run(*, force: bool, clock: Callable[[], float] = time.time,
        reconcile: Optional[Callable[[], list[dict[str, Any]]]] = None) -> Optional[dict[str, Any]]:
    """Reconcile if the lease allows it; the stored record, or None when nothing ran.

    Nothing runs when the computer is not connected, when another process holds the lease, or (unless
    *force*) when the last run is younger than the interval."""
    if reconcile is None:
        from . import library

        reconcile = library.reconcile
    interval = _interval_s()
    if interval is None:
        return None

    def due() -> bool:
        previous = last_run()
        now = clock()
        # A stored time in the future (the clock was set back) must not silence the watchdog.
        return force or previous is None or not 0 <= now - previous["at"] < interval

    if not due():
        return None
    with lease() as held:
        if not held or not due():  # another process may have finished a run while we waited for the lock
            return None
        return _reconcile_and_record(reconcile, clock)


def tick() -> None:
    """One look at the schedule, as the thread does it; never raises."""
    try:
        run(force=False)
    except Exception:  # noqa: BLE001 - a background thread must outlive any failure
        logger.exception("requrv-kb watchdog: check failed")


class Watchdog:
    """A daemon thread that calls *tick* after *delay_s*, then every *poll_s*, until stopped."""

    def __init__(self, tick: Callable[[], None] = tick, poll_s: float = POLL_S, delay_s: float = START_DELAY_S):
        self._tick, self._poll, self._delay = tick, poll_s, delay_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="requrv-kb-watchdog", daemon=True)

    def _loop(self) -> None:
        wait = self._delay
        while not self._stop.wait(wait):
            self._tick()
            wait = self._poll

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(_STOP_JOIN_S)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()


_current: Optional[Watchdog] = None
_guard = threading.Lock()


def start() -> Watchdog:
    """Start this process's watchdog thread (replacing one left by a previous load of the plugin)."""
    global _current
    with _guard:
        if _current is not None:
            _current.stop()
        _current = Watchdog()
        _current.start()
        return _current


def stop() -> None:
    global _current
    with _guard:
        if _current is not None:
            _current.stop()
            _current = None
