"""Bot library behaviour through the real Hermes CLI: catalogue, install, update, rollback, sync."""

from __future__ import annotations

from conftest import SECRET, read_yaml, write_yaml


def test_plugin_passes_hermes_doctor(hermes):
    hermes.hermes("plugins", "doctor", str(hermes.plugin), "--ci")


def test_catalogue_is_the_union_of_readable_area_lists(connected, kb):
    listing = connected.kb("list")
    assert [e["name"] for e in listing["entries"]] == ["marketing"]  # finanza: no area enables it
    assert listing["entries"][0]["status"] == "new"
    assert listing["allowlist"]["missing"] == ["vendite"]


def test_no_area_list_means_an_empty_catalogue(hermes, kb):
    hermes.kb("connect", "--root", str(kb["library"]), "--personal", str(kb["personal"]))
    assert hermes.kb("list")["entries"] == []


def test_install_gives_the_bot_the_coordinators_provider_and_nothing_else(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    assert (bot / "SOUL.md").read_text() == "# Marketing v1\n"
    assert (bot / "skills" / "brand" / "SKILL.md").is_file()
    config = read_yaml(bot / "config.yaml")
    assert config["model"]["provider"] == "custom:requrv"
    assert config["providers"] == {"requrv": {"name": "ReQurv", "api": "https://hive.requrv.ai/api/v1",
                                              "api_key": SECRET, "models": {"requrv-small-3.8": {}}}}
    assert config["skills"]["create_dir"] == str(kb["personal"] / "skills")
    assert "requrv-kb" in config["plugins"]["enabled"]
    env = (bot / ".env").read_text() if (bot / ".env").exists() else ""
    assert "never-copy-this" not in env
    assert connected.kb("list")["entries"][0]["status"] == "installed"


def test_package_with_private_content_is_refused(connected, kb):
    (kb["marketing"] / ".env").write_text("PACKAGE_SECRET=x\n")
    result = connected.hermes("kb", "install", "marketing", ok=False)
    assert result.returncode == 1 and ".env" in result.stdout
    assert not connected.profile("marketing").exists()


def test_update_refreshes_managed_keys_keeps_user_data_and_can_roll_back(connected, kb):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    config = read_yaml(bot / "config.yaml")
    config["display"] = {"personality": "mine"}
    config["agent"]["max_turns"] = 99  # a managed key the user changed: the update restores the library's
    write_yaml(bot / "config.yaml", config)
    (bot / "memories").mkdir(exist_ok=True)
    (bot / "memories" / "MEMORY.md").write_text("ricordo")
    (bot / "skills" / "mia").mkdir()
    (bot / "skills" / "mia" / "SKILL.md").write_text("---\nname: mia\ndescription: x\n---\n")

    write_yaml(kb["marketing"] / "distribution.yaml", {
        "name": "marketing", "version": "2.0.0", "config_managed": ["agent.max_turns", "mcp_servers"]})
    (kb["marketing"] / "SOUL.md").write_text("# Marketing v2\n")
    write_yaml(kb["marketing"] / "config.yaml", {"agent": {"max_turns": 30}})
    assert connected.kb("list")["entries"][0]["status"] == "update"
    assert connected.kb("update", "marketing")["from_version"] == "1.0.0"

    config = read_yaml(bot / "config.yaml")
    assert (bot / "SOUL.md").read_text() == "# Marketing v2\n"
    assert config["agent"]["max_turns"] == 30
    assert "mcp_servers" not in config  # a managed key the package dropped disappears
    assert config["display"] == {"personality": "mine"}
    assert (bot / "memories" / "MEMORY.md").read_text() == "ricordo"
    assert (bot / "skills" / "mia" / "SKILL.md").is_file()

    assert connected.kb("rollback", "marketing")["version"] == "1.0.0"
    assert (bot / "SOUL.md").read_text() == "# Marketing v1\n"
    assert read_yaml(bot / "config.yaml")["mcp_servers"] == {"docs": {"command": "docs-v1"}}
    # The start-up sync does not re-apply the version the user rolled back from...
    assert connected.kb("sync")["results"][0]["status"] == "unchanged"
    # ...until the library publishes another one.
    write_yaml(kb["marketing"] / "distribution.yaml", {"name": "marketing", "version": "3.0.0"})
    result = connected.kb("sync")["results"][0]
    assert (result["status"], result["to"]) == ("updated", "3.0.0")


def test_sync_reports_a_missing_library_folder(connected, kb):
    connected.kb("install", "marketing")
    kb["marketing"].rename(kb["marketing"].with_name("spostato"))
    assert connected.kb("sync")["results"][0]["status"] == "source-unavailable"


def test_duplicate_is_a_personal_bot_outside_the_library(connected):
    connected.kb("install", "marketing")
    assert connected.kb("duplicate", "marketing", "Marketing mio")["profile"] == "marketing-mio"
    copy = connected.profile("marketing-mio")
    assert (copy / "SOUL.md").read_text() == "# Marketing v1\n"
    assert not (copy / ".library-owned.json").exists() and not (copy / "distribution.yaml").exists()
    assert [b["profile"] for b in connected.kb("status")["bots"]] == ["marketing"]
