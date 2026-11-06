"""The reconcile pass (watchdog), through the real Hermes CLI: install what is missing, update, leave the rest."""

from __future__ import annotations

from conftest import write_yaml


def by_bot(results):
    return {r["bot"]: r for r in results}


def test_a_missing_allowed_bot_is_installed_and_the_next_pass_changes_nothing(connected):
    first = by_bot(connected.kb("reconcile")["results"])
    assert first["marketing"]["action"] == "installed" and first["marketing"]["to"] == "1.0.0"
    assert (connected.profile("marketing") / "SOUL.md").is_file()
    assert [r["action"] for r in connected.kb("reconcile")["results"]] == ["unchanged"]


def test_a_deleted_bot_comes_back_fresh_without_its_chats(connected):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    (bot / "memories").mkdir(exist_ok=True)
    (bot / "memories" / "MEMORY.md").write_text("ricordo")
    connected.hermes("profile", "delete", "marketing", "--yes")
    assert not bot.exists()  # the ledger and the backups lived in the profile: gone with it
    assert connected.kb("list")["entries"][0]["status"] == "new"

    result = by_bot(connected.kb("reconcile")["results"])["marketing"]
    assert result["action"] == "installed"
    assert (bot / "SOUL.md").is_file() and (bot / ".library-owned.json").is_file()
    assert not (bot / "memories" / "MEMORY.md").exists()
    assert not (connected.root / "profiles" / ".deleted" / "marketing").exists()  # Hermes sees it as live again
    assert "marketing" in connected.hermes("profile", "list").stdout
    assert [r["action"] for r in connected.kb("reconcile")["results"]] == ["unchanged"]


def test_reinstall_survives_the_remains_of_a_half_deleted_profile(connected):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    connected.hermes("profile", "delete", "marketing", "--yes")
    (bot / "logs").mkdir(parents=True)  # a locked file or a late writer left the folder behind
    (bot / "logs" / "agent.log").write_text("resto")
    (bot / ".library-owned.json").write_text('{"paths": [], "source": "/vecchio"}')

    assert connected.kb("status")["bots"] == []  # a deleted bot is not a library bot, whatever its folder holds
    assert by_bot(connected.kb("reconcile")["results"])["marketing"]["action"] == "installed"
    assert not (bot / "logs" / "agent.log").exists()
    assert (bot / "SOUL.md").is_file()


def disallow(kb):
    write_yaml(kb["area"] / "bots.yaml", {"bots": ["vendite"]})


def test_a_library_bot_no_longer_allowed_is_removed_on_the_second_pass(connected, kb):
    connected.kb("install", "marketing")
    disallow(kb)
    write_yaml(kb["marketing"] / "distribution.yaml", {"name": "marketing", "version": "2.0.0"})

    first = by_bot(connected.kb("reconcile")["results"])["marketing"]
    assert (first["action"], first["from"]) == ("pending-removal", "1.0.0")
    assert (connected.profile("marketing") / "SOUL.md").is_file()  # a first strike only marks; no update either
    assert connected.kb("status")["bots"][0]["version"] == "1.0.0"

    assert by_bot(connected.kb("reconcile")["results"])["marketing"]["action"] == "removed"
    assert not connected.profile("marketing").exists()
    assert connected.kb("reconcile")["results"] == []


def test_a_bot_allowed_again_between_two_passes_loses_its_strike(connected, kb):
    connected.kb("install", "marketing")
    disallow(kb)
    assert by_bot(connected.kb("reconcile")["results"])["marketing"]["action"] == "pending-removal"
    write_yaml(kb["area"] / "bots.yaml", {"bots": ["marketing"]})
    assert by_bot(connected.kb("reconcile")["results"])["marketing"]["action"] == "unchanged"
    disallow(kb)
    assert by_bot(connected.kb("reconcile")["results"])["marketing"]["action"] == "pending-removal"
    assert connected.profile("marketing").exists()


def test_duplicates_and_user_created_bots_are_never_removed(connected, kb):
    connected.kb("install", "marketing")
    connected.kb("duplicate", "marketing", "Marketing mio")
    connected.hermes("profile", "create", "mio-bot", "--no-alias")
    disallow(kb)
    for expected in ({"marketing"}, {"marketing"}, set()):  # strike, removal, nothing left to report
        assert {r["bot"] for r in connected.kb("reconcile")["results"]} == expected
    assert not connected.profile("marketing").exists()
    assert connected.profile("marketing-mio").is_dir() and connected.profile("mio-bot").is_dir()
    assert not (connected.profile("marketing-mio") / ".library-owned.json").exists()


def test_nothing_is_removed_when_a_folder_or_list_cannot_be_read(connected, kb):
    connected.kb("install", "marketing")
    disallow(kb)
    assert by_bot(connected.kb("reconcile")["results"])["marketing"]["action"] == "pending-removal"
    (kb["area"] / "bots.yaml").write_text("bots: [non chiuso\n")  # unreadable list (as after a damaged sync)
    assert connected.kb("reconcile")["results"] == []
    kb["area"].rename(kb["area"].with_name("01-Spostata"))  # area gone from the connected roots
    assert connected.kb("reconcile")["results"] == []
    assert connected.profile("marketing").is_dir()
    # the strike survived the unsure passes, and a later sure pass completes it
    kb["area"].with_name("01-Spostata").rename(kb["area"])
    disallow(kb)
    assert by_bot(connected.kb("reconcile")["results"])["marketing"]["action"] == "removed"


def test_a_bot_that_was_never_allowed_is_not_installed(connected, kb):
    assert "finanza" not in by_bot(connected.kb("reconcile")["results"])
    assert not connected.profile("finanza").exists()


def test_a_changed_version_is_applied(connected, kb):
    connected.kb("install", "marketing")
    write_yaml(kb["marketing"] / "distribution.yaml", {"name": "marketing", "version": "2.0.0"})
    (kb["marketing"] / "SOUL.md").write_text("# Marketing v2\n")
    result = by_bot(connected.kb("reconcile")["results"])["marketing"]
    assert (result["action"], result["from"], result["to"]) == ("updated", "1.0.0", "2.0.0")
    assert (connected.profile("marketing") / "SOUL.md").read_text() == "# Marketing v2\n"


def test_a_missing_library_folder_is_reported_not_reinstalled(connected, kb):
    connected.kb("install", "marketing")
    kb["marketing"].rename(kb["marketing"].with_name("spostato"))  # the package now lives elsewhere
    results = connected.kb("reconcile")["results"]
    assert [(r["bot"], r["action"]) for r in results] == [("marketing", "source-unavailable")]


def test_a_personal_bot_with_the_same_name_is_never_overwritten(connected):
    connected.hermes("profile", "create", "marketing", "--no-alias")
    result = by_bot(connected.kb("reconcile")["results"])["marketing"]
    assert result["action"] == "error" and "Esiste già" in result["error"]
    assert not (connected.profile("marketing") / ".library-owned.json").exists()


def test_the_interval_is_a_setting_that_survives_reconnecting(connected, kb):
    assert connected.python(
        "from requrv_kb import connection as c\nprint(c.load().watchdog_minutes)\n"
        "c.set_watchdog_minutes(10)\nk = c.load()\nc.save(c.connect(list(k.roots), personal=k.personal))\nprint(c.load().watchdog_minutes)",
        connected.root).split() == ["30", "10"]
