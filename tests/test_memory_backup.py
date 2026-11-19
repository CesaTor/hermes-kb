"""Built-in memory and Holographic's store are backed up under the operator's folder."""

from __future__ import annotations

import json
import sqlite3


def _backup(connected, profile: str = "marketing") -> list[str]:
    code = """
import json
from pathlib import Path
from hermes_constants import get_hermes_home
from requrv_kb import connection, mirror
profile = Path(get_hermes_home())
print(json.dumps(mirror.backup_memory(profile, connection.load(), %r)))
""" % profile
    return json.loads(connected.python(code, connected.profile(profile)))


def test_memory_files_are_mirrored_and_change_detection_skips_rewrites(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "memories").mkdir(exist_ok=True)
    (bot / "memories" / "MEMORY.md").write_text("Fatto locale\n", encoding="utf-8")
    (bot / "memories" / "USER.md").write_text("Preferenza\n", encoding="utf-8")

    assert sorted(_backup(connected)) == ["MEMORY.md", "USER.md"]
    target = kb["personal"] / "memoria" / "marketing"
    assert (target / "MEMORY.md").read_text() == "Fatto locale\n"
    assert (target / "USER.md").read_text() == "Preferenza\n"
    assert _backup(connected) == []

    (bot / "memories" / "MEMORY.md").write_text("Fatto aggiornato\n", encoding="utf-8")
    assert _backup(connected) == ["MEMORY.md"]
    assert (target / "MEMORY.md").read_text() == "Fatto aggiornato\n"


def test_holographic_store_is_copied_consistently(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    with sqlite3.connect(bot / "memory_store.db") as db:
        db.execute("create table facts (id integer primary key, content text)")
        db.execute("insert into facts (content) values ('fatto sintetico')")

    assert _backup(connected) == ["memory_store.db"]
    target = kb["personal"] / "memoria" / "marketing" / "memory_store.db"
    assert target.is_file()
    with sqlite3.connect(target) as db:
        assert db.execute("select content from facts").fetchone() == ("fatto sintetico",)
    assert _backup(connected) == []


def test_a_duplicated_personal_bot_does_not_write_to_the_shared_memory_folder(connected, kb):
    connected.kb("install", "marketing")
    connected.kb("duplicate", "marketing", "copia")
    copy = connected.profile("copia")
    (copy / "memories").mkdir(exist_ok=True)
    (copy / "memories" / "MEMORY.md").write_text("personale\n", encoding="utf-8")
    assert _backup(connected, "copia") == []
    assert not (kb["personal"] / "memoria" / "copia").exists()
