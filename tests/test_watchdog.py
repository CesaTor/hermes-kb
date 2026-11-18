"""The on-demand reconciliation: lease, status and recorded outcome, with a fake clock."""

from __future__ import annotations

import threading

import pytest

from conftest import PLUGIN_SRC


class Clock:
    def __init__(self, now: float = 1_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, minutes: float) -> None:
        self.now += minutes * 60


@pytest.fixture
def wd(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.syspath_prepend(str(PLUGIN_SRC))
    from requrv_kb import connection, watchdog

    connection.save(connection.Connection(("/kb",), "mario", "/kb/mario"))
    return watchdog


class Reconcile:
    def __init__(self, during=None):
        self.calls, self.during = 0, during

    def __call__(self):
        self.calls += 1
        if self.during:
            self.during()
        return [{"bot": "marketing", "profile": "marketing", "action": "installed", "to": "1.0.0"}]


def test_nothing_runs_while_the_computer_is_not_connected(wd):
    from requrv_kb import connection

    connection.disconnect()
    fake = Reconcile()
    assert wd.run(clock=Clock(), reconcile=fake) is None and fake.calls == 0


def test_a_manual_run_records_the_outcome(wd):
    clock, fake = Clock(), Reconcile()
    record = wd.run(clock=clock, reconcile=fake)
    assert record["results"][0]["action"] == "installed"
    assert wd.status(clock)["last_run"] == {
        "at": clock.now, "results": record["results"],
        "summary": {"installed": 1, "updated": 0, "errors": 0, "not_allowed": 0}, "error": None,
    }


def test_the_lease_keeps_two_runs_from_overlapping(wd):
    clock, inner_runs = Clock(), []

    def second_process():
        inner_runs.append(wd.run(clock=clock, reconcile=Reconcile()))
        other = threading.Thread(target=lambda: inner_runs.append(wd.run(clock=clock, reconcile=Reconcile())))
        other.start()
        other.join()

    outer = wd.run(clock=clock, reconcile=Reconcile(during=second_process))
    assert outer is not None and inner_runs == [None, None]
    assert wd.run(clock=clock, reconcile=Reconcile()) is not None  # released afterwards


def test_a_crashed_reconcile_is_recorded(wd):
    clock = Clock()

    def boom():
        raise RuntimeError("giù")

    record = wd.run(clock=clock, reconcile=boom)
    assert record["error"] == "giù"
    assert wd.status(clock)["last_run"]["error"] == "giù"
    # The next manual/startup call is allowed to retry: there is no interval to wait for.
    fake = Reconcile()
    assert wd.run(clock=clock, reconcile=fake) is not None and fake.calls == 1


def test_status_has_no_interval_or_background_thread(wd):
    status = wd.status(Clock())
    assert "interval_minutes" not in status and "next_due" not in status
    assert not hasattr(wd, "start") and not hasattr(wd, "stop") and not hasattr(wd, "Watchdog")
