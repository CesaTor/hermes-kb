"""What a library bot refuses: the wiring the library owns, not the operator's own knowledge."""

from __future__ import annotations

import json


def _hook(hermes, home, calls):
    code = ("import json\nfrom requrv_kb.locks import pre_tool_call\n"
            f"calls = json.loads({json.dumps(json.dumps(calls))})\n"
            "print(json.dumps([pre_tool_call(tool_name=t, args=a, task_id='t') for t, a in calls]))")
    return json.loads(hermes.python(code, home))


def test_only_managed_config_and_package_metadata_are_locked(connected):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "skills" / "mia").mkdir()
    (bot / "skills" / "mia" / "SKILL.md").write_text("---\nname: mia\ndescription: x\n---\n")
    results = _hook(connected, bot, [
        ["write_file", {"path": str(bot / "SOUL.md"), "content": "x"}],
        ["patch", {"patch": f"*** Begin Patch\n*** Update File: {bot / 'skills' / 'brand' / 'SKILL.md'}\n"}],
        ["skill_manage", {"action": "edit", "name": "brand"}],
        ["write_file", {"path": str(bot / "skills" / "brand" / "notes.md"), "content": "x"}],
        ["write_file", {"path": str(bot / "config.yaml"), "content": "x"}],
        ["skill_manage", {"action": "edit", "name": "mia"}],
        ["write_file", {"path": str(bot / "notes.md"), "content": "x"}],
        ["read_file", {"path": str(bot / "SOUL.md")}],
    ])
    assert [r and r["action"] for r in results] == [None] * 4 + ["block"] + [None] * 3
    assert "config.yaml" in results[4]["message"] and "marketing" in results[4]["message"]


def test_package_metadata_is_refused(connected):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    results = _hook(connected, bot, [
        ["write_file", {"path": str(bot / "distribution.yaml"), "content": "name: altro\n"}],
        ["write_file", {"path": str(bot / ".library-owned.json"), "content": "{}"}],
    ])
    assert [r["action"] for r in results] == ["block", "block"]


def test_another_bot_cannot_change_a_library_bots_managed_config(connected):
    connected.kb("install", "marketing")
    connected.kb("duplicate", "marketing", "copia")
    target = connected.profile("marketing") / "config.yaml"
    copy = connected.profile("copia")
    blocked, own = _hook(connected, copy, [["write_file", {"path": str(target)}],
                                           ["write_file", {"path": str(copy / "SOUL.md")}]])
    assert blocked["action"] == "block" and own is None


def test_prompt_section_names_the_connected_folders_and_what_may_be_edited(connected, kb):
    connected.kb("install", "marketing")
    text = connected.python("from requrv_kb.prompt import section; print(section({}))", connected.profile("marketing"))
    assert str(kb["library"]) in text and str(kb["personal"]) in text
    assert f"($SECOND_BRAIN_ROOT nelle skill) è {kb['library'].parent}." in text
    assert "«marketing»" in text and "puoi modificarli su richiesta" in text
    assert str(kb["personal"] / "proposte" / "marketing") in text
    plain = connected.python("from requrv_kb.prompt import section; print(section({}))", connected.root)
    assert "bot di libreria" not in plain


def test_hermes_loader_renders_the_sections_inside_the_bot(connected):
    """Through Hermes' own discovery, and without a process-wide module name that another profile's
    copy of the plugin (one gateway serves them all) could shadow."""
    connected.kb("install", "marketing")
    code = """
import json, sys
from hermes_cli.plugins import discover_plugins, render_system_prompt_sections
discover_plugins()
ids = {s.id: s.content for s in render_system_prompt_sections({})}
print(json.dumps({"ids": sorted(ids), "text": "\\n".join(ids.values()), "top": "requrv_kb" in sys.modules}))
"""
    out = json.loads(connected.python(code, connected.profile("marketing")))
    # The personal section stays empty (and Hermes omits it) until a release collides with an edit.
    assert out["ids"] == ["requrv-kb.connection"]
    assert "«marketing»" in out["text"]
    assert out["top"] is False  # no process-wide module name another profile's copy could shadow
