"""The agent cannot edit what the library replaces; the session prompt names the KB folders."""

from __future__ import annotations

import json



def _hook(hermes, home, calls):
    code = ("import json\nfrom requrv_kb.locks import pre_tool_call\n"
            f"calls = json.loads({json.dumps(json.dumps(calls))})\n"
            "print(json.dumps([pre_tool_call(tool_name=t, args=a, task_id='t') for t, a in calls]))")
    return json.loads(hermes.python(code, home))


def test_library_bot_content_is_locked_and_user_content_is_not(connected):
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
    assert [r and r["action"] for r in results] == ["block"] * 5 + [None] * 3
    assert "marketing" in results[0]["message"] and "duplica" in results[0]["message"].lower()


def test_another_bot_cannot_edit_a_library_bot_either(connected):
    connected.kb("install", "marketing")
    connected.kb("duplicate", "marketing", "copia")
    target = connected.profile("marketing") / "SOUL.md"
    copy = connected.profile("copia")
    blocked, own = _hook(connected, copy, [["write_file", {"path": str(target)}],
                                           ["write_file", {"path": str(copy / "SOUL.md")}]])
    assert blocked["action"] == "block" and own is None


def test_prompt_section_names_the_connected_folders(connected, kb):
    connected.kb("install", "marketing")
    text = connected.python("from requrv_kb.prompt import section; print(section({}))", connected.profile("marketing"))
    assert str(kb["library"]) in text and str(kb["personal"]) in text
    assert "«marketing»" in text
    plain = connected.python("from requrv_kb.prompt import section; print(section({}))", connected.root)
    assert "bot di libreria" not in plain
