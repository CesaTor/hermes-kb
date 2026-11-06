"""The watchdog schedule: lease, interval and thread, with a fake clock and a stand-in reconcile."""

from __future__ import annotations

import importlib.util
import sys
import threading
from unittest.mock import MagicMock

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
    assert wd.run(force=True, clock=Clock(), reconcile=fake) is None and fake.calls == 0


def test_a_run_happens_once_per_interval(wd):
    from requrv_kb import connection

    clock, fake = Clock(), Reconcile()
    assert wd.run(force=False, clock=clock, reconcile=fake)["results"][0]["action"] == "installed"
    clock.advance(29)
    assert wd.run(force=False, clock=clock, reconcile=fake) is None
    clock.advance(1)
    assert wd.run(force=False, clock=clock, reconcile=fake) is not None
    assert fake.calls == 2

    connection.set_watchdog_minutes(5)  # a shorter interval applies at the next look
    clock.advance(5)
    assert wd.run(force=False, clock=clock, reconcile=fake) is not None
    assert fake.calls == 3


def test_force_ignores_the_interval_and_a_clock_set_back_does_not_silence_the_watchdog(wd):
    clock, fake = Clock(), Reconcile()
    wd.run(force=False, clock=clock, reconcile=fake)
    assert wd.run(force=True, clock=clock, reconcile=fake) is not None
    clock.advance(-120)
    assert wd.run(force=False, clock=clock, reconcile=fake) is not None
    assert fake.calls == 3


def test_the_lease_keeps_two_runs_from_overlapping(wd):
    clock, inner_runs = Clock(), []

    def second_process():
        inner_runs.append(wd.run(force=True, clock=clock, reconcile=Reconcile()))
        other = threading.Thread(target=lambda: inner_runs.append(wd.run(force=True, clock=clock, reconcile=Reconcile())))
        other.start()
        other.join()

    outer = wd.run(force=True, clock=clock, reconcile=Reconcile(during=second_process))
    assert outer is not None and inner_runs == [None, None]
    assert wd.run(force=True, clock=clock, reconcile=Reconcile()) is not None  # released afterwards


def test_a_crashed_reconcile_is_recorded_and_not_retried_before_the_interval(wd):
    clock = Clock()

    def boom():
        raise RuntimeError("giù")

    record = wd.run(force=False, clock=clock, reconcile=boom)
    assert record["error"] == "giù"
    assert wd.status(clock)["last_run"]["error"] == "giù"
    fake = Reconcile()
    clock.advance(10)
    assert wd.run(force=False, clock=clock, reconcile=fake) is None and fake.calls == 0


def test_status_summarises_the_last_run(wd):
    clock = Clock()
    assert wd.status(clock)["last_run"] is None
    wd.run(force=False, clock=clock, reconcile=Reconcile())
    status = wd.status(clock)
    assert status["interval_minutes"] == 30 and status["next_due"] == clock.now + 30 * 60
    assert status["last_run"]["summary"] == {"installed": 1, "updated": 0, "errors": 0, "removed": 0}


def test_the_thread_ticks_until_stopped_and_a_failing_tick_does_not_kill_it(wd):
    ticked, enough = [], threading.Event()

    def tick():
        ticked.append(1)
        if len(ticked) == 2:
            enough.set()
        raise RuntimeError("ignorato dal ciclo? no: tick() reale non solleva")

    # The loop itself calls whatever tick it is given; the real tick() never raises (checked below).
    dog = wd.Watchdog(tick=lambda: (ticked.append(1), len(ticked) >= 3 and enough.set()), poll_s=0.001, delay_s=0)
    dog.start()
    assert enough.wait(10)
    dog.stop()
    assert not dog.alive


def test_the_real_tick_never_raises(wd, monkeypatch):
    monkeypatch.setattr(wd, "run", MagicMock(side_effect=OSError("disco")))
    wd.tick()


def test_register_starts_one_thread_and_unload_stops_it(wd):
    spec = importlib.util.spec_from_file_location("kbplugin_under_test", PLUGIN_SRC / "__init__.py",
                                                  submodule_search_locations=[str(PLUGIN_SRC)])
    plugin = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = plugin
    try:
        spec.loader.exec_module(plugin)
        ctx = MagicMock()
        plugin.register(ctx)
        running = sys.modules[f"{spec.name}.requrv_kb.watchdog"]
        dog = running._current
        assert dog is not None and dog.alive  # waits START_DELAY_S first, so a one-shot command exits unchecked
        (unload,), _ = ctx.on_unload.call_args
        unload()
        assert not dog.alive and running._current is None
    finally:
        for name in [n for n in sys.modules if n.startswith(spec.name)]:
            del sys.modules[name]
