"""The IT reviewer: proposals across operators, accept into the package, reject aside."""

from __future__ import annotations

import json

from conftest import read_yaml, write_yaml


def _proposal(operator, bot, soul: str, skill: str | None = None) -> None:
    folder = operator / "proposte" / bot
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SOUL.md").write_text(soul, encoding="utf-8")
    (folder / "proposal.yaml").write_text(
        f"bot: {bot}\noperatore: {operator.name}\nbase_version: 1.0.0\nfile:\n  SOUL.md: abc\n",
        encoding="utf-8")
    if skill:
        target = folder / "skills" / "brand"
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(skill, encoding="utf-8")


def _it_connected(hermes, kb):
    operators = kb["library"].parent / "Operatori"
    anna, reviewer = operators / "anna", operators / "it"
    anna.mkdir(parents=True)
    reviewer.mkdir(parents=True)
    (reviewer / ".autorizzazioni.yaml").write_text("operator: it\nruolo: it\n", encoding="utf-8")
    hermes.kb("connect", "--root", str(kb["library"]), "--root", str(kb["area"]),
              "--root", str(operators), "--personal", str(reviewer))
    return anna, reviewer


def test_it_lists_and_shows_proposals_across_operators(hermes, kb):
    anna, _ = _it_connected(hermes, kb)
    _proposal(anna, "marketing", "# Marketing v1\nDai del lei.\n", "# Brand nostro\n")
    knowledge = anna / "proposte" / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "20261117-154501-clienti.md").write_text("# Clienti\n", encoding="utf-8")

    listing = hermes.kb("it", "list")
    assert [(p["operator"], p["bot"]) for p in listing["proposals"]] == [("anna", "marketing")]
    assert listing["proposals"][0]["base_version"] == "1.0.0"
    assert listing["knowledge"][0]["file"] == "20261117-154501-clienti.md"

    shown = hermes.kb("it", "show", "--operator", "anna", "--bot", "marketing")
    assert "Dai del lei." in shown["files"]["SOUL.md"]
    assert "Brand nostro" in shown["files"]["skills/brand"]


def test_accept_writes_the_package_bumps_the_version_and_clears_the_proposal(hermes, kb):
    anna, _ = _it_connected(hermes, kb)
    _proposal(anna, "marketing", "# Marketing v1\nDai del lei.\n")

    plan = hermes.kb("it", "accept", "--operator", "anna", "--bot", "marketing")
    assert plan["confirm_required"] and plan["plan"]["to_version"] == "1.0.1"
    assert (kb["marketing"] / "SOUL.md").read_text() == "# Marketing v1\n"  # nothing written yet

    done = hermes.kb("it", "accept", "--operator", "anna", "--bot", "marketing", "--yes")
    assert done["accepted"]["to_version"] == "1.0.1"
    assert (kb["marketing"] / "SOUL.md").read_text() == "# Marketing v1\nDai del lei.\n"
    assert read_yaml(kb["marketing"] / "distribution.yaml")["version"] == "1.0.1"
    assert not (anna / "proposte" / "marketing").exists()


def test_reject_archives_the_proposal_with_a_reason(hermes, kb):
    anna, _ = _it_connected(hermes, kb)
    _proposal(anna, "marketing", "# Marketing mio\n", "# Brand mio\n")

    out = hermes.kb("it", "reject", "--operator", "anna", "--bot", "marketing",
                    "--reason", "troppo specifico per un operatore")
    assert not (anna / "proposte" / "marketing").exists()
    archives = list((anna / "proposte" / "Archivio").iterdir())
    assert len(archives) == 1 and out["rejected"]["archived_at"] == str(archives[0])
    note = (archives[0] / "RIFIUTATA.md").read_text()
    assert "troppo specifico" in note and "anna" in note
    assert (archives[0] / "SOUL.md").read_text() == "# Marketing mio\n"


def test_the_review_commands_are_refused_without_the_it_role(hermes, kb):
    hermes.kb("connect", "--root", str(kb["library"]), "--root", str(kb["area"]),
              "--personal", str(kb["personal"]))
    refused = hermes.hermes("kb", "it", "list", ok=False)
    assert refused.returncode == 1 and "riservata al reparto IT" in refused.stdout


def test_updates_lists_and_applies_what_the_library_offers(hermes, kb):
    _it_connected(hermes, kb)
    offered = hermes.kb("updates")
    assert [(u["bot"], u["status"]) for u in offered["updates"]] == [("marketing", "new")]
    applied = hermes.kb("updates", "--apply")
    assert any(r["action"] == "installed" for r in applied["results"])
    assert hermes.kb("updates")["updates"] == []


def test_the_it_tools_are_registered_and_gated(hermes, kb):
    anna, _ = _it_connected(hermes, kb)
    _proposal(anna, "marketing", "# Marketing v1\nDai del lei.\n")
    code = """
import json
from hermes_cli.plugins import discover_plugins
from tools.registry import registry
discover_plugins()
wanted = {"kb_personal", "kb_proposals", "kb_updates"}
print(json.dumps(sorted(d["function"]["name"] for d in registry.get_definitions(wanted))))
"""
    assert json.loads(hermes.python(code, hermes.root)) == ["kb_personal", "kb_proposals", "kb_updates"]

    hermes.kb("connect", "--root", str(kb["library"]), "--root", str(kb["area"]),
              "--personal", str(kb["personal"]))  # mario: no `ruolo: it`
    assert json.loads(hermes.python(code, hermes.root)) == ["kb_personal"]
