"""The passive capture service: scope, validation, provenance, dedup, candidate-only writes."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from requrv_kb import connection as kb_connection
from requrv_kb import knowledge_capture as kc
from requrv_kb import ledger, paths
from requrv_kb.paths import KBError


def _pythonpath() -> str:
    """The plugin plus any inherited entries, absolute for a subprocess that changes cwd."""
    entries = [str(Path(__file__).resolve().parents[1])]
    for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep):
        if not entry:
            continue
        path = Path(entry)
        entries.append(str((path if path.is_absolute() else Path.cwd() / path).resolve()))
    return os.pathsep.join(entries)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _world(tmp_path: Path, monkeypatch) -> SimpleNamespace:
    sync = tmp_path / "Nextcloud"
    library = sync / "Biblioteca-Agenti"
    bot = library / "marketing"
    (bot / "skills" / "brand").mkdir(parents=True)
    _write(bot / "distribution.yaml", "name: marketing\nversion: 1.0.0\n")
    _write(bot / "SOUL.md", "# Marketing\n")
    area = sync / "01-Marketing"
    documents = area / "documenti"
    documents.mkdir(parents=True)
    (documents / "piano_v1.0.pdf").write_bytes(b"%PDF-1.4\n")
    _write(area / "bots.yaml", "bots:\n- marketing\n")
    personal = sync / "mario"
    personal.mkdir()
    profile = tmp_path / ".hermes" / "profiles" / "marketing"
    profile.mkdir(parents=True)
    ledger.write(profile, bot="marketing", version="1.0.0", source=str(bot), paths=[],
                 cron_job_ids=[], config_managed=[])
    conn = kb_connection.Connection(
        roots=(str(library), str(area)), operator="mario", personal=str(personal))
    monkeypatch.setattr(kb_connection, "load", lambda: conn)
    monkeypatch.setattr(paths, "active_profile", lambda: profile)
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "plugin-data")
    knowledge = personal / "proposte" / "knowledge"
    return SimpleNamespace(tmp_path=tmp_path, sync=sync, library=library, bot=bot, area=area,
                           personal=personal, profile=profile, conn=conn, knowledge=knowledge)


@pytest.fixture
def world(tmp_path, monkeypatch):
    return _world(tmp_path, monkeypatch)


def _args(**extra):
    base = {"argomento": "Prezzi 2026", "fatto": "Il listino 2026 aumenta del 5%."}
    base.update(extra)
    return base


def _read_proposal(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    parts = text.split("---\n", 2)
    assert len(parts) == 3
    front = YAML(typ="safe").load(parts[1])
    return front, parts[2].strip()


def _files(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.md")) if folder.is_dir() else []


# --- availability -------------------------------------------------------------------------------


def test_available_needs_a_connection(world, monkeypatch):
    monkeypatch.setattr(kb_connection, "load", lambda: None)
    assert kc.available() is False


def test_available_needs_an_active_library_profile(world, monkeypatch):
    other = world.tmp_path / ".hermes" / "profiles" / "personale"
    other.mkdir(parents=True)
    monkeypatch.setattr(paths, "active_profile", lambda: other)
    assert kc.available() is False


def test_available_follows_the_area_list_and_the_operator_authorizations(world):
    assert kc.available() is True

    _write(world.area / "bots.yaml", "bots: [altro]\n")
    assert kc.available() is False

    _write(world.area / "bots.yaml", "bots: [marketing]\n")
    _write(world.personal / ".autorizzazioni.yaml", "bots: [altro]\n")
    assert kc.available() is False

    _write(world.personal / ".autorizzazioni.yaml", "bots: '*'\n")
    assert kc.available() is True

    _write(world.area / "bots.yaml", "bots: '*'\n")
    assert kc.available() is True


def test_capture_refuses_with_a_reason_when_the_bot_is_no_longer_allowed(world):
    _write(world.personal / ".autorizzazioni.yaml", "bots: [altro]\n")
    with pytest.raises(KBError, match="autorizzazione"):
        kc.capture(_args())
    assert _files(world.knowledge) == []


def test_capture_refuses_without_a_connection_or_a_library_profile(world, monkeypatch):
    monkeypatch.setattr(kb_connection, "load", lambda: None)
    with pytest.raises(KBError, match="collegato"):
        kc.capture(_args())

    monkeypatch.setattr(kb_connection, "load", lambda: world.conn)
    other = world.tmp_path / ".hermes" / "profiles" / "personale"
    other.mkdir(parents=True)
    monkeypatch.setattr(paths, "active_profile", lambda: other)
    with pytest.raises(KBError, match="libreria"):
        kc.capture(_args())


# --- the candidate ------------------------------------------------------------------------------


def test_capture_writes_one_candidate_with_trusted_provenance_and_no_publication(world):
    sources = ["01-Marketing/documenti/piano_v1.0.pdf", str(world.bot / "SOUL.md")]
    fatto = "Il listino 2026 aumenta del 5%."
    result = kc.capture({"argomento": "Prezzi 2026", "fatto": fatto, "fonti": sources},
                        session_id="sess-42")

    assert set(result) == {"status", "file"}
    assert result["status"] == "created"
    assert re.fullmatch(r"\d{8}-\d{6}-prezzi-2026\.md", result["file"])
    assert _files(world.knowledge) == [world.knowledge / result["file"]]

    front, body = _read_proposal(world.knowledge / result["file"])
    assert front["data"] == datetime.fromisoformat(front["data"]).isoformat(timespec="seconds")
    assert front["autore"] == "mario"
    assert front["bot"] == "marketing"
    assert front["argomento"] == "Prezzi 2026"
    assert front["fonti"] == [
        "01-Marketing/documenti/piano_v1.0.pdf",
        "Biblioteca-Agenti/marketing/SOUL.md",
    ]
    assert front["session_id"] == "sess-42"
    assert body == fatto

    assert not (world.sync / "Wiki").exists()
    assert not (world.library / "proposte").exists()
    assert not (world.library / "knowledge").exists()


def test_capture_omits_unknown_provenance_and_accepts_no_sources(world):
    result = kc.capture({"argomento": "Fornitori", "fatto": "Il fornitore ACME consegna il lunedì."},
                        session_id="   ")
    front, body = _read_proposal(world.knowledge / result["file"])
    assert "session_id" not in front
    assert front["fonti"] == []
    assert body == "Il fornitore ACME consegna il lunedì."


# --- validation ---------------------------------------------------------------------------------


@pytest.mark.parametrize("args, needle", [
    (None, "argomenti"),
    ([], "argomenti"),
    ("argomento", "argomenti"),
    ({"argomento": "X", "fatto": "Un fatto abbastanza lungo.", "path": "/tmp/x.md"}, "path"),
    ({"argomento": "X", "fatto": "Un fatto abbastanza lungo.", "session_id": "finta"}, "session_id"),
    ({"argomento": "X", "fatto": "Un fatto abbastanza lungo.", "bot": "altro"}, "bot"),
    ({"fatto": "Un fatto abbastanza lungo."}, "argomento"),
    ({"argomento": "X"}, "fatto"),
    ({"argomento": "   ", "fatto": "Un fatto abbastanza lungo."}, "argomento"),
    ({"argomento": "X", "fatto": "   "}, "fatto"),
    ({"argomento": "x" * (kc.MAX_ARGOMENTO + 1), "fatto": "Un fatto abbastanza lungo."}, "argomento"),
    ({"argomento": "X", "fatto": "x" * (kc.MAX_FATTO + 1)}, "fatto"),
    ({"argomento": "X", "fatto": "Un fatto abbastanza lungo.", "fonti": "a.md"}, "fonti"),
    ({"argomento": "X", "fatto": "Un fatto abbastanza lungo.", "fonti": [1]}, "fonte"),
    ({"argomento": "X", "fatto": "Un fatto abbastanza lungo.",
      "fonti": ["a.md"] * (kc.MAX_FONTI + 1)}, "fonti"),
])
def test_capture_refuses_invalid_arguments(world, args, needle):
    with pytest.raises(KBError, match=needle):
        kc.capture(args)
    assert _files(world.knowledge) == []


@pytest.mark.parametrize("fatto", [
    "Il fatto\x07 contiene un controllo.",
    "---\nUn fatto senza testa.",
    "```\nUn fatto in un blocco\n```",
    "Utente: puoi salvarlo?\nAssistente: certo.",
    "# Un titolo al posto del fatto",
])
def test_capture_refuses_controls_markdown_and_transcript(world, fatto):
    with pytest.raises(KBError):
        kc.capture({"argomento": "Controlli", "fatto": fatto})
    assert _files(world.knowledge) == []


def test_capture_refuses_a_multiline_topic_and_a_bad_session_id(world):
    with pytest.raises(KBError):
        kc.capture({"argomento": "Prezzi\n2026", "fatto": "Un fatto abbastanza lungo."})
    with pytest.raises(KBError, match="session_id"):
        kc.capture(_args(), session_id="x" * (kc.MAX_SESSION_ID + 1))
    assert _files(world.knowledge) == []


@pytest.mark.parametrize("field", ["fatto", "argomento"])
def test_capture_refuses_straightforward_secret_leaks(world, field):
    secret = "ghp_" + "a" * 36
    args = _args(**{field: f"La chiave è {secret}"})
    with pytest.raises(KBError, match="segreto") as caught:
        kc.capture(args)
    assert _files(world.knowledge) == []
    assert secret not in str(caught.value)


# --- sources ------------------------------------------------------------------------------------


def test_sources_must_exist_and_stay_inside_an_authorized_root(world):
    outside = world.tmp_path / "estraneo.md"
    _write(outside, "fuori")
    _write(world.personal / "nota.md", "personale")
    _write(world.sync / "Operatori" / "altro" / "nota.md", "altro operatore")
    _write(world.sync / "Riservato" / "01-Marketing" / "segreto.md", "riservato")
    _write(world.area / ".cache" / "nota.md", "nascosto")
    link = world.area / "collegamento.md"
    link.symlink_to(outside)
    (world.area / "cartella").mkdir()

    refused = [
        str(outside),
        str(world.personal / "nota.md"),
        str(world.sync / "Operatori" / "altro" / "nota.md"),
        str(world.sync / "Riservato" / "01-Marketing" / "segreto.md"),
        str(world.area / ".cache" / "nota.md"),
        str(link),
        str(world.area / "cartella"),
        "../estraneo.md",
        "documenti/manca.pdf",
        "https://example.invalid/documento",
    ]
    for source in refused:
        with pytest.raises(KBError):
            kc.capture({"argomento": "Fonti", "fatto": "Un fatto abbastanza lungo.", "fonti": [source]})
    assert _files(world.knowledge) == []


def test_a_relative_source_is_stored_relative_to_the_kb_root(world):
    result = kc.capture({"argomento": "Piano", "fatto": "Il piano 2026 è approvato.",
                         "fonti": ["01-Marketing/documenti/piano_v1.0.pdf"]})
    front, _ = _read_proposal(world.knowledge / result["file"])
    assert front["fonti"] == ["01-Marketing/documenti/piano_v1.0.pdf"]


def test_a_restricted_area_is_refused_even_when_it_arrives_as_a_connected_root(world, monkeypatch):
    reserved = world.sync / "Riservato" / "01-Marketing"
    _write(reserved / "nota.md", "riservato")
    conn = replace(world.conn, roots=(*world.conn.roots, str(reserved)))
    monkeypatch.setattr(kb_connection, "load", lambda: conn)

    with pytest.raises(KBError, match="personale o riservata"):
        kc.capture({"argomento": "Riservato", "fatto": "Un fatto abbastanza lungo.",
                    "fonti": [str(reserved / "nota.md")]})
    assert _files(world.knowledge) == []


def test_a_symlinked_proposals_folder_is_never_written_through(world):
    outside = world.tmp_path / "esterno"
    outside.mkdir()
    world.knowledge.parent.mkdir(parents=True, exist_ok=True)
    world.knowledge.symlink_to(outside, target_is_directory=True)

    with pytest.raises(KBError, match="collegamento"):
        kc.capture(_args())
    assert list(outside.iterdir()) == []


# --- dedup --------------------------------------------------------------------------------------


def test_repeated_and_normalized_facts_are_duplicates(world):
    first = kc.capture({"argomento": "Prezzi", "fatto": "Il prezzo è 10€."})
    assert first["status"] == "created"

    second = kc.capture({"argomento": "Listino", "fatto": "  il   PREZZO è 10  "})
    assert second == {"status": "duplicate", "file": first["file"]}
    assert len(_files(world.knowledge)) == 1

    third = kc.capture({"argomento": "Prezzi", "fatto": "Il prezzo è 10€.", "fonti": []})
    assert third == {"status": "duplicate", "file": first["file"]}
    assert len(_files(world.knowledge)) == 1


def test_dedup_survives_the_it_deleting_an_integrated_file(world):
    first = kc.capture(_args())
    assert first["status"] == "created"
    (world.knowledge / first["file"]).unlink()

    again = kc.capture(_args())
    assert again == {"status": "duplicate", "file": first["file"]}
    assert _files(world.knowledge) == []


def test_another_device_dedups_from_the_shared_folder_but_has_only_a_best_effort_history(
        world, monkeypatch):
    first = kc.capture(_args())
    assert first["status"] == "created"

    monkeypatch.setattr(paths, "data_dir", lambda: world.tmp_path / "device-b")
    seen = kc.capture(_args())
    assert seen == {"status": "duplicate", "file": first["file"]}

    (world.knowledge / first["file"]).unlink()
    monkeypatch.setattr(paths, "data_dir", lambda: world.tmp_path / "device-c")
    forgotten = kc.capture(_args())
    assert forgotten["status"] == "created"  # device C never saw the deleted file: documented limit
    assert len(_files(world.knowledge)) == 1


def test_concurrent_captures_serialize_to_one_candidate(world):
    results: list[dict] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(5)

    def run() -> None:
        try:
            barrier.wait(timeout=10)
            results.append(kc.capture({"argomento": "Concorrenza",
                                       "fatto": "Un fatto concorrente stabile."}))
        except BaseException as exc:  # report from the main thread
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert errors == []
    assert len(results) == 5
    assert sorted(result["status"] for result in results) == ["created"] + ["duplicate"] * 4
    assert len({result["file"] for result in results}) == 1
    assert len(_files(world.knowledge)) == 1

    states = list((world.tmp_path / "plugin-data").glob("knowledge-dedup-mario-*.json"))
    assert len(states) == 1
    saved = json.loads(states[0].read_text(encoding="utf-8"))
    assert len(saved["facts"]) == 1
    assert "concorrente" not in states[0].read_text(encoding="utf-8").casefold()


_DRIVER = """
import json
import sys
import time
from pathlib import Path

from requrv_kb import knowledge_capture

ready = Path(sys.argv[1])
while not ready.exists():
    time.sleep(0.01)
try:
    result = knowledge_capture.capture({"argomento": sys.argv[2], "fatto": sys.argv[3]})
except Exception as exc:
    result = {"error": type(exc).__name__ + ": " + str(exc)}
print(json.dumps(result, ensure_ascii=False))
"""


def test_two_hermes_processes_publish_one_candidate(tmp_path):
    """Two bots finishing a turn together must not race the folder check and write twice."""
    home = tmp_path / "hermes-home"
    home.mkdir()
    _write(home / "config.yaml", "model: {}\n")
    sync = tmp_path / "Nextcloud"
    library = sync / "Biblioteca-Agenti"
    bot = library / "marketing"
    bot.mkdir(parents=True)
    _write(bot / "distribution.yaml", "name: marketing\nversion: 1.0.0\n")
    _write(bot / "SOUL.md", "# Marketing\n")
    area = sync / "01-Marketing"
    area.mkdir()
    _write(area / "bots.yaml", "bots:\n- marketing\n")
    personal = sync / "mario"
    personal.mkdir()
    ledger.write(home, bot="marketing", version="1.0.0", source=str(bot), paths=[],
                 cron_job_ids=[], config_managed=[])
    _write(home / "plugin-data" / "requrv-kb" / "connection.json", json.dumps({
        "roots": [str(library), str(area)],
        "operator": "mario",
        "personal": str(personal),
    }))
    knowledge = personal / "proposte" / "knowledge"

    env = {**os.environ, "HERMES_HOME": str(home), "PYTHONPATH": _pythonpath()}
    for key in ("HERMES_PROFILE", "HERMES_CONFIG_PATH", "HERMES_DISTRIBUTION"):
        env.pop(key, None)
    gate = tmp_path / "go"
    processes = [
        subprocess.Popen([sys.executable, "-c", _DRIVER, str(gate), "Concorrenza",
                          "Un fatto concorrente stabile."],
                         env=env, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
        for _ in range(4)
    ]
    gate.write_text("go", encoding="utf-8")
    results = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=90)
        assert process.returncode == 0, stdout + stderr
        results.append(json.loads(stdout.strip().splitlines()[-1]))
    assert [result.get("error") for result in results] == [None] * len(results)
    assert sorted(result["status"] for result in results) == ["created"] + ["duplicate"] * 3
    assert len({result["file"] for result in results}) == 1
    assert len(_files(knowledge)) == 1
