"""The agent cannot edit what the library replaces; the session prompt names the KB folders."""

from __future__ import annotations

import json



def _hook(hermes, home, calls):
    code = ("import json\nfrom requrv_kb.locks import pre_tool_call\n"
            f"calls = json.loads({json.dumps(json.dumps(calls))})\n"
            "print(json.dumps([pre_tool_call(tool_name=t, args=a, task_id='t') for t, a in calls]))")
    return json.loads(hermes.python(code, home))


def connected_kb_personal(hermes):
    from pathlib import Path

    return Path(json.loads((hermes.root / "plugin-data" / "requrv-kb" / "connection.json").read_text())["personal"])


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
    assert "marketing" in results[0]["message"]
    assert str(connected_kb_personal(connected) / "proposte" / "marketing.md") in results[0]["message"]


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
    assert f"($SECOND_BRAIN_ROOT nelle skill) è {kb['library'].parent}." in text
    assert "«marketing»" in text
    plain = connected.python("from requrv_kb.prompt import section; print(section({}))", connected.root)
    assert "bot di libreria" not in plain


def _sections(hermes, home):
    code = ("import json\nfrom requrv_kb.prompt import section, proposals_section\n"
            "print(json.dumps([section({}), proposals_section({})]))")
    return json.loads(hermes.python(code, home))


def test_operator_proposals_extend_the_soul_until_it_folds_them_in(connected, kb):
    from conftest import write_yaml

    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    proposals = kb["personal"] / "proposte" / "marketing.md"
    # The agent may write the proposals file: it is the operator's, not the library's.
    assert _hook(connected, bot, [["write_file", {"path": str(proposals), "content": "x"}]]) == [None]
    assert _sections(connected, bot)[1] == ""

    proposals.parent.mkdir(parents=True)
    proposals.write_text("## tono-formale\nDai sempre del lei.\nMotivo: clienti istituzionali.\n\n"
                         "## firma\nChiudi con la firma del reparto.\n")
    guidance, overlay = _sections(connected, bot)
    assert str(proposals) in guidance
    assert "Dai sempre del lei." in overlay and "Chiudi con la firma" in overlay

    # IT folds one proposal into the library SOUL and declines the other; the next sync updates the bot.
    (kb["marketing"] / "SOUL.md").write_text("# Marketing v2\nDai sempre del lei.\n")
    write_yaml(kb["marketing"] / "distribution.yaml", {
        "name": "marketing", "version": "2.0.0", "config_managed": ["agent.max_turns", "mcp_servers"],
        "proposals_resolved": ["tono-formale"], "proposals_rejected": ["firma"]})
    assert connected.kb("sync")["results"][0]["status"] == "updated"
    assert (bot / "SOUL.md").read_text().startswith("# Marketing v2")
    assert proposals.read_text() == ""
    archived = (proposals.parent / "Archivio").glob("marketing-*.md")
    text = "".join(a.read_text() for a in archived)
    assert "Recepita nella versione 2.0.0" in text and "Rifiutata nella versione 2.0.0" in text
    assert _sections(connected, bot)[1] == ""


def test_hermes_loader_renders_the_sections_inside_the_bot(connected, kb):
    """Through Hermes' own discovery, and without a process-wide module name that another profile's
    copy of the plugin (one gateway serves them all) could shadow."""
    connected.kb("install", "marketing")
    (kb["personal"] / "proposte").mkdir(parents=True)
    (kb["personal"] / "proposte" / "marketing.md").write_text("## tono\nDai del lei.\n")
    code = f"""
import json, sys
from hermes_cli.plugins import discover_plugins, render_system_prompt_sections
discover_plugins()
ids = {{s.id: s.content for s in render_system_prompt_sections({{}})}}
print(json.dumps({{"ids": sorted(ids), "text": "\\n".join(ids.values()), "top": "requrv_kb" in sys.modules}}))
"""
    out = json.loads(connected.python(code, connected.profile("marketing")))
    assert out["ids"] == ["requrv-kb.connection", "requrv-kb.proposals"]
    assert "«marketing»" in out["text"] and "Dai del lei." in out["text"]
    assert out["top"] is False  # no process-wide module name another profile's copy could shadow
