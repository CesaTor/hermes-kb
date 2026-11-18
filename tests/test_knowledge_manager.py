"""The Knowledge Manager starter package installs as a normal library bot."""

from __future__ import annotations

import shutil
from pathlib import Path

from conftest import write_yaml

PACKAGE = (Path(__file__).resolve().parents[1] / "kb-template" / "Biblioteca-Agenti" / "knowledge-manager")


def test_the_knowledge_manager_package_installs(connected, kb):
    shutil.copytree(PACKAGE, kb["library"] / "knowledge-manager")
    write_yaml(kb["area"] / "bots.yaml", {"bots": ["marketing", "knowledge-manager"]})
    assert connected.kb("install", "knowledge-manager")["version"] == "0.1.0"

    bot = connected.profile("knowledge-manager")
    assert "Knowledge Manager" in (bot / "SOUL.md").read_text(encoding="utf-8")
    for skill in ("llm-wiki", "mappa-kb", "knowledge-ingest", "pubblica-documento"):
        assert (bot / "skills" / skill / "SKILL.md").is_file()
    assert (bot / "skills" / "llm-wiki" / "scripts" / "wiki_lint.py").is_file()
    assert connected.kb("status")["bots"][0]["version"] == "0.1.0"
    listed = connected.hermes("skills", "list", profile="knowledge-manager").stdout
    assert "llm-wiki" in listed and "mappa-kb" in listed


def test_the_package_ships_only_what_a_bot_may_receive(connected, kb):
    """The plugin refuses a package with `.env`, memory or a chat; this one is clean."""
    from requrv_kb import package

    pkg = package.read(PACKAGE)
    package.assert_installable(pkg)
    assert pkg.name == "knowledge-manager"
    assert set(pkg.distribution_owned) == {"distribution.yaml", "SOUL.md", "skills", "README.md"}
