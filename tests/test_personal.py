"""The operator's personal skill versions: certified SOUL, editable skills, keep/take."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import write_yaml


def _edit(install, home: Path, rel: str, content: str) -> dict:
    """A ``write_file`` as the agent does it: the guard runs, then the write and the mirror."""
    target = home / rel
    code = f"""
import json
from pathlib import Path
from requrv_kb import locks, mirror
target = Path({str(target)!r})
content = {content!r}
args = {{"path": str(target), "content": content}}
blocked = locks.pre_tool_call(tool_name="write_file", args=args)
if blocked is None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    mirror.on_tool_call(tool_name="write_file", args=args)
print(json.dumps({{"blocked": blocked}}))
"""
    return json.loads(install.python(code, home))


def _kb_as(install, profile: str, *args: str) -> dict:
    return json.loads(install.hermes("kb", "--json", *args, profile=profile).stdout)


def _publish(kb, version: str, brand: str | None = None) -> None:
    write_yaml(kb["marketing"] / "distribution.yaml", {
        "name": "marketing", "version": version, "config_managed": ["agent.max_turns", "mcp_servers"]})
    if brand is not None:
        (kb["marketing"] / "skills" / "brand" / "SKILL.md").write_text(brand, encoding="utf-8")


MIO_BRAND = "---\nname: brand\ndescription: Domande sul brand.\n---\n# Brand nostro\n"
MIO_SOUL = "# Marketing v1\nDai sempre del lei.\n"


def test_soul_is_certified_and_a_skill_edit_is_mirrored(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    assert "SOUL" in _edit(connected, bot, "SOUL.md", MIO_SOUL)["blocked"]["message"]
    assert _edit(connected, bot, "skills/brand/SKILL.md", MIO_BRAND)["blocked"] is None

    folder = kb["personal"] / "proposte" / "marketing"
    assert (folder / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND
    manifest = (folder / "proposal.yaml").read_text()
    assert "base_version: 1.0.0" in manifest and "skills/brand" in manifest
    assert not (folder / "SOUL.md").exists()
    assert connected.kb("status")["bots"][0]["pending"] == 0


def test_an_update_that_did_not_touch_the_skill_keeps_it_silently(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    _edit(connected, bot, "skills/brand/SKILL.md", MIO_BRAND)
    _publish(kb, "2.0.0")  # version bump, same skill
    result = connected.kb("update", "marketing")
    assert result["reapplied"] == ["brand"] and result["pending"] == []
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND


def test_a_manual_skill_edit_is_detected_on_the_next_update(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "skills" / "brand" / "SKILL.md").write_text(MIO_BRAND, encoding="utf-8")  # editor
    _publish(kb, "2.0.0", brand="# Brand v2\n")

    result = connected.kb("update", "marketing")
    assert result["pending"] == [{"kind": "skill", "name": "brand"}]
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND
    assert (kb["personal"] / "proposte" / "marketing" / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND
    assert _kb_as(connected, "marketing", "resolve", "--kind", "skill", "--name", "brand",
                  "--choice", "keep")["choice"] == "keep"
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND


def test_a_skill_from_before_the_feature_is_adopted_on_the_first_update(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / ".requrv-kb-personal.json").unlink()
    (bot / "skills" / "brand" / "SKILL.md").write_text(MIO_BRAND, encoding="utf-8")
    _publish(kb, "2.0.0", brand="# Brand v2\n")

    result = connected.kb("update", "marketing")
    assert result["pending"] == [{"kind": "skill", "name": "brand"}]
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND
    assert _kb_as(connected, "marketing", "resolve", "--kind", "skill", "--name", "brand",
                  "--choice", "keep")["choice"] == "keep"
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND


def test_a_manual_skill_edit_is_surfaced_at_the_next_prompt(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "skills" / "brand" / "SKILL.md").write_text(MIO_BRAND, encoding="utf-8")

    prompt = connected.python("from requrv_kb.prompt import personal_section; print(personal_section({}))",
                              bot)
    assert "AZIONE OBBLIGATORIA" in prompt and "Vuoi tenere la tua versione o prendere la nuova?" in prompt
    assert "Brand nostro" in prompt
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND
    assert connected.kb("status")["bots"][0]["pending"] == 1

    assert _kb_as(connected, "marketing", "resolve", "--kind", "skill", "--name", "brand",
                  "--choice", "keep")["choice"] == "keep"
    assert connected.kb("status")["bots"][0]["pending"] == 0


def test_pre_llm_call_injects_the_question_once_per_session(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "skills" / "brand" / "SKILL.md").write_text(MIO_BRAND, encoding="utf-8")
    code = """
import json
from requrv_kb import prompt
print(json.dumps(prompt.pre_llm_call(session_id="s1"), ensure_ascii=False))
print(json.dumps(prompt.pre_llm_call(session_id="s1"), ensure_ascii=False))
print(json.dumps(prompt.pre_llm_call(session_id="s2"), ensure_ascii=False))
"""
    lines = connected.python(code, bot).splitlines()
    assert "Vuoi tenere la tua versione o prendere la nuova?" in lines[0]
    assert json.loads(lines[1]) is None
    assert "Vuoi tenere la tua versione o prendere la nuova?" in lines[2]


def test_take_applies_the_certified_skill(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    _edit(connected, bot, "skills/brand/SKILL.md", MIO_BRAND)
    _publish(kb, "2.0.0", brand="# Brand v2\n")
    connected.kb("update", "marketing")

    assert _kb_as(connected, "marketing", "resolve", "--kind", "skill", "--name", "brand",
                  "--choice", "take")["choice"] == "take"
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == "# Brand v2\n"
    assert not (kb["personal"] / "proposte" / "marketing" / "skills" / "brand").exists()
    assert connected.kb("status")["bots"][0]["pending"] == 0
