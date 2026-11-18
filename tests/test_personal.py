"""The operator's own SOUL/skill: mirrored in proposte/, re-applied or asked on update."""

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


def _publish(kb, version: str, soul: str | None = None, brand: str | None = None) -> None:
    write_yaml(kb["marketing"] / "distribution.yaml", {
        "name": "marketing", "version": version, "config_managed": ["agent.max_turns", "mcp_servers"]})
    if soul is not None:
        (kb["marketing"] / "SOUL.md").write_text(soul, encoding="utf-8")
    if brand is not None:
        (kb["marketing"] / "skills" / "brand" / "SKILL.md").write_text(brand, encoding="utf-8")


MIO_SOUL = "# Marketing v1\nDai sempre del lei.\n"
MIO_BRAND = "---\nname: brand\ndescription: Domande sul brand.\n---\n# Brand nostro\n"


def test_an_edit_is_mirrored_in_the_operators_proposals_with_its_base_version(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    assert _edit(connected, bot, "SOUL.md", MIO_SOUL)["blocked"] is None
    assert _edit(connected, bot, "skills/brand/SKILL.md", MIO_BRAND)["blocked"] is None

    folder = kb["personal"] / "proposte" / "marketing"
    assert (folder / "SOUL.md").read_text() == MIO_SOUL
    assert (folder / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND
    manifest = (folder / "proposal.yaml").read_text()
    assert "base_version: 1.0.0" in manifest and "skills/brand" in manifest
    assert connected.kb("status")["bots"][0]["pending"] == 0  # nothing to ask yet


def test_an_update_that_did_not_touch_the_file_keeps_the_operators_version_silently(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    _edit(connected, bot, "SOUL.md", MIO_SOUL)
    _publish(kb, "2.0.0")  # version bump, same SOUL
    result = connected.kb("update", "marketing")
    assert result["reapplied"] == ["SOUL"] and result["pending"] == []
    assert (bot / "SOUL.md").read_text() == MIO_SOUL


def test_a_manual_soul_edit_is_detected_on_the_next_update(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "SOUL.md").write_text(MIO_SOUL, encoding="utf-8")  # editor, not the write tool
    _publish(kb, "2.0.0", soul="# Marketing v2\n")

    result = connected.kb("update", "marketing")
    assert result["pending"] == [{"kind": "soul", "name": ""}]
    assert (bot / "SOUL.md").read_text() == MIO_SOUL  # the personal version never leaves the profile
    assert (kb["personal"] / "proposte" / "marketing" / "SOUL.md").read_text() == MIO_SOUL
    assert _kb_as(connected, "marketing", "resolve", "--kind", "soul", "--choice", "keep")["choice"] == "keep"
    assert (bot / "SOUL.md").read_text() == MIO_SOUL


def test_a_personal_soul_from_before_the_feature_is_adopted_on_the_first_update(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / ".requrv-kb-personal.json").unlink()  # simulates a bot installed before personal versions
    (bot / "SOUL.md").write_text(MIO_SOUL, encoding="utf-8")
    _publish(kb, "2.0.0", soul="# Marketing v2\n")

    result = connected.kb("update", "marketing")
    assert result["pending"] == [{"kind": "soul", "name": ""}]
    assert (bot / "SOUL.md").read_text() == MIO_SOUL
    assert _kb_as(connected, "marketing", "resolve", "--kind", "soul", "--choice", "keep")["choice"] == "keep"
    assert (bot / "SOUL.md").read_text() == MIO_SOUL


def test_a_manual_edit_is_surfaced_at_the_next_prompt_without_an_update(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "SOUL.md").write_text(MIO_SOUL, encoding="utf-8")  # editor, no update, no write hook

    prompt = connected.python("from requrv_kb.prompt import personal_section; print(personal_section({}))",
                              bot)
    assert "AZIONE OBBLIGATORIA" in prompt and "Vuoi tenere la tua versione o prendere la nuova?" in prompt
    assert "Dai sempre del lei." in prompt
    assert (bot / "SOUL.md").read_text() == MIO_SOUL
    assert connected.kb("status")["bots"][0]["pending"] == 1

    assert _kb_as(connected, "marketing", "resolve", "--kind", "soul", "--choice", "keep")["choice"] == "keep"
    assert (bot / "SOUL.md").read_text() == MIO_SOUL
    assert connected.kb("status")["bots"][0]["pending"] == 0


def test_a_library_change_asks_and_keep_restores_the_personal_version(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    _edit(connected, bot, "SOUL.md", MIO_SOUL)
    _edit(connected, bot, "skills/brand/SKILL.md", MIO_BRAND)
    _publish(kb, "2.0.0", soul="# Marketing v2\n", brand="# Brand v2\n")

    result = connected.kb("update", "marketing")
    assert sorted((p["kind"], p["name"]) for p in result["pending"]) == [("skill", "brand"), ("soul", "")]
    assert (bot / "SOUL.md").read_text() == MIO_SOUL  # personal version stays live
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND
    assert connected.kb("status")["bots"][0]["pending"] == 2

    prompt = connected.python("from requrv_kb.prompt import personal_section; print(personal_section({}))",
                              bot)
    assert "AZIONE OBBLIGATORIA" in prompt and "kb_personal" in prompt
    assert "Dai sempre del lei." in prompt and "Brand nostro" in prompt

    assert _kb_as(connected, "marketing", "resolve", "--kind", "soul", "--choice", "keep")["choice"] == "keep"
    assert (bot / "SOUL.md").read_text() == MIO_SOUL
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == MIO_BRAND

    assert _kb_as(connected, "marketing", "resolve", "--kind", "skill", "--name", "brand",
                  "--choice", "take")["choice"] == "take"
    assert (bot / "skills" / "brand" / "SKILL.md").read_text() == "# Brand v2\n"
    assert not (kb["personal"] / "proposte" / "marketing" / "skills" / "brand").exists()
    assert connected.kb("status")["bots"][0]["pending"] == 0


def test_the_question_stays_until_answered_and_a_new_release_does_not_overwrite(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    _edit(connected, bot, "SOUL.md", MIO_SOUL)
    _publish(kb, "2.0.0", soul="# Marketing v2\n")
    connected.kb("update", "marketing")
    _publish(kb, "3.0.0")  # another bump, same SOUL as 2.0.0
    result = connected.kb("update", "marketing")
    assert result["pending"] == [{"kind": "soul", "name": ""}]
    assert (bot / "SOUL.md").read_text() == MIO_SOUL


def test_the_personal_authorisation_file_narrows_the_catalogue(connected, kb):
    write_yaml(kb["area"] / "bots.yaml", {"bots": ["marketing", "finanza"]})
    assert [e["name"] for e in connected.kb("list")["entries"]] == ["finanza", "marketing"]
    (kb["personal"] / ".autorizzazioni.yaml").write_text("operator: mario\nbots: [marketing]\n",
                                                         encoding="utf-8")
    assert [e["name"] for e in connected.kb("list")["entries"]] == ["marketing"]
    refused = connected.hermes("kb", "install", "finanza", ok=False)
    assert refused.returncode == 1 and "autorizzazione" in refused.stdout


def test_a_bot_no_longer_allowed_stays_with_its_chats(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "memories").mkdir(exist_ok=True)
    (bot / "memories" / "MEMORY.md").write_text("ricordo", encoding="utf-8")
    write_yaml(kb["area"] / "bots.yaml", {"bots": ["vendite"]})
    for _ in range(2):
        result = {r["bot"]: r for r in connected.kb("reconcile")["results"]}["marketing"]
        assert result["action"] == "not-allowed"
        assert bot.is_dir() and (bot / "memories" / "MEMORY.md").read_text() == "ricordo"
