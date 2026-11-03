"""A disposable Hermes install with this plugin, driven through the real ``hermes`` CLI.

Run with an upstream Hermes checkout importable (``PYTHONPATH=<hermes-agent>``) and its
``scripts/run_tests.sh``; no provider or network request is made.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

PLUGIN_SRC = Path(__file__).resolve().parents[1]
SECRET = "requrv_sk_test_secret_value"
_yaml = YAML(typ="safe")


def write_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        _yaml.dump(data, stream)


def read_yaml(path: Path):
    return _yaml.load(path.read_text(encoding="utf-8"))


class Install:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.user = tmp / "user"
        self.root = self.user / ".hermes"
        plugin = self.root / "plugins" / "requrv-kb"
        shutil.copytree(PLUGIN_SRC, plugin, ignore=shutil.ignore_patterns(
            "tests", ".git", "__pycache__", ".pytest_cache", "dist"))
        self.plugin = plugin
        write_yaml(self.root / "config.yaml", {
            "model": {"default": "requrv-small-3.8", "provider": "custom:requrv",
                      "base_url": "https://hive.requrv.ai/api/v1"},
            "providers": {"requrv": {"name": "ReQurv", "api": "https://hive.requrv.ai/api/v1",
                                     "api_key": SECRET, "models": {"requrv-small-3.8": {}}},
                          "other": {"name": "Other", "api": "https://other.invalid", "api_key": "never-copy"}},
            "plugins": {"enabled": ["requrv-kb"]},
        })
        (self.root / ".env").write_text("TELEGRAM_BOT_TOKEN=never-copy-this\n", encoding="utf-8")
        self.env = {**os.environ, "HOME": str(self.user), "USERPROFILE": str(self.user),
                    "HERMES_HOME": str(self.root)}
        for key in ("HERMES_PROFILE", "HERMES_CONFIG_PATH", "HERMES_DISTRIBUTION"):
            self.env.pop(key, None)

    def hermes(self, *args: str, profile: str = "default", ok: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run([sys.executable, "-m", "hermes_cli.main", "-p", profile, *args],
                                env=self.env, cwd=self.tmp, capture_output=True, text=True, timeout=300)
        if ok:
            assert result.returncode == 0, result.stdout + result.stderr
        return result

    def kb(self, *args: str, ok: bool = True):
        result = self.hermes("kb", "--json", *args, ok=ok)
        return json.loads(result.stdout)

    def python(self, code: str, profile_home: Path) -> str:
        """Run *code* inside a process bound to *profile_home*, with the plugin package importable."""
        env = {**self.env, "HERMES_HOME": str(profile_home),
               "PYTHONPATH": os.pathsep.join([str(self.plugin), self.env.get("PYTHONPATH", "")])}
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout.strip()

    def profile(self, name: str) -> Path:
        return self.root / "profiles" / name


def make_kb(tmp: Path) -> dict[str, Path]:
    """Separate islands, as an operator receives them from Nextcloud."""
    sync = tmp / "Nextcloud"
    library = sync / "Biblioteca-Agenti"
    marketing = library / "marketing"
    (marketing / "skills" / "brand").mkdir(parents=True)
    write_yaml(marketing / "distribution.yaml", {
        "name": "marketing", "version": "1.0.0", "description": "Bot del marketing",
        "config_managed": ["agent.max_turns", "mcp_servers"],
    })
    (marketing / "SOUL.md").write_text("# Marketing v1\n", encoding="utf-8")
    (marketing / "skills" / "brand" / "SKILL.md").write_text(
        "---\nname: brand\ndescription: Domande sul brand.\n---\n# Brand\n", encoding="utf-8")
    write_yaml(marketing / "config.yaml", {"agent": {"max_turns": 20},
                                           "mcp_servers": {"docs": {"command": "docs-v1"}}})
    hidden = library / "finanza"
    hidden.mkdir()
    write_yaml(hidden / "distribution.yaml", {"name": "finanza", "version": "1.0.0"})
    (hidden / "SOUL.md").write_text("# Finanza\n", encoding="utf-8")
    area = sync / "01-Marketing"
    area.mkdir()
    write_yaml(area / "bots.yaml", {"bots": ["marketing", "vendite"]})
    personal = sync / "mario"
    personal.mkdir()
    return {"library": library, "area": area, "personal": personal, "marketing": marketing}


@pytest.fixture
def hermes(tmp_path):
    return Install(tmp_path)


@pytest.fixture
def kb(tmp_path):
    return make_kb(tmp_path)


@pytest.fixture
def connected(hermes, kb):
    hermes.kb("connect", "--root", str(kb["library"]), "--root", str(kb["area"]),
              "--personal", str(kb["personal"]))
    return hermes
