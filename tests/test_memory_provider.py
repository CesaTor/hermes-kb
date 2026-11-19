"""Company memory-provider setting and per-profile configuration."""

from __future__ import annotations

import json

from requrv_kb import memory_provider
from requrv_kb.yamlio import load_config


def test_the_company_setting_persists_in_the_connection(connected):
    code = """
import json
from requrv_kb import connection
connection.set_memory_provider('holographic')
print(json.dumps(connection.load().to_dict()))
"""
    data = json.loads(connected.python(code, connected.root))
    assert data["memory_provider"] == "holographic"


def test_configure_sets_and_clears_the_profile_provider(connected):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    assert memory_provider.configure(bot) is True
    assert load_config(bot / "config.yaml")["memory"]["provider"] == "holographic"
    assert memory_provider.configure(bot) is False
    assert memory_provider.configure(bot, provider="") is True
    assert "memory" not in load_config(bot / "config.yaml") or \
        "provider" not in load_config(bot / "config.yaml").get("memory", {})


def test_status_reports_plugin_and_provider_per_bot(connected):
    connected.kb("install", "marketing")
    bot = connected.profile("marketing")
    memory_provider.configure(bot)
    (bot / "plugins" / "holographic").mkdir(parents=True, exist_ok=True)
    status = json.loads(connected.hermes("kb", "--json", "memory", "status").stdout)
    assert status["provider"] == ""
    assert status["bots"] == [{"profile": "marketing", "plugin": True,
                               "configured": True, "provider": "holographic"}]
