"""Optional Holographic memory provider for library bots.

Holographic is a separate Hermes plugin, not a dependency of this one. The company setting in
``connection.json`` opts in for every library bot on this computer: :func:`ensure` installs the
plugin in that bot's profile, enables it and sets ``memory.provider: holographic``. A failure leaves
the bot on the built-in memory and is reported to the caller; it never blocks the bot.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from . import connection as kb_connection
from .paths import KBError, named_profiles
from .yamlio import load_config, write_config

logger = logging.getLogger(__name__)

PROVIDER = "holographic"
PLUGIN = "holographic"


def installed(profile: Path) -> bool:
    return (Path(profile) / "plugins" / PLUGIN).is_dir()


def configured(profile: Path) -> bool:
    try:
        config = load_config(Path(profile) / "config.yaml")
    except (OSError, KBError):
        return False
    memory = config.get("memory") if isinstance(config, dict) else None
    return isinstance(memory, dict) and memory.get("provider") == PROVIDER


def configure(profile: Path, provider: str = PROVIDER) -> bool:
    """Set or clear ``memory.provider`` in one profile; returns whether the file changed."""
    path = Path(profile) / "config.yaml"
    try:
        config = load_config(path)
    except (OSError, KBError):
        config = {}
    if not isinstance(config, dict):
        config = {}
    memory = config.get("memory") if isinstance(config.get("memory"), dict) else {}
    before = dict(memory)
    if provider:
        memory["provider"] = provider
    else:
        memory.pop("provider", None)
    if memory == before:
        return False
    if memory:
        config["memory"] = memory
    else:
        config.pop("memory", None)
    write_config(path, config)
    return True


def status(profile: Path) -> dict[str, Any]:
    return {"profile": Path(profile).name, "plugin": installed(Path(profile)),
            "configured": configured(Path(profile)), "provider": PROVIDER}


def ensure(profile: Path, *, install: bool = True) -> dict[str, Any]:
    """Install/enable Holographic in *profile* and point its memory provider at it."""
    profile = Path(profile)
    result = {"profile": profile.name, "provider": PROVIDER, "installed": installed(profile),
              "configured": False, "error": None}
    if not result["installed"]:
        if not install:
            result["error"] = "Holographic non è installato in questo profilo."
            return result
        from . import hermes

        try:
            hermes.run(["plugins", "install", PLUGIN, "--enable", "--yes-deps"], profile=profile.name)
        except KBError as exc:
            result["error"] = str(exc)
            logger.info("requrv-kb: Holographic non installato in %s: %s", profile.name, exc)
            return result
        result["installed"] = installed(profile)
        if not result["installed"]:
            result["error"] = "Holographic non risulta installato dopo il comando."
            return result
    else:
        from . import hermes

        try:
            hermes.run(["plugins", "enable", PLUGIN], profile=profile.name)
        except KBError as exc:
            # An already-enabled plugin may return a non-zero status on older Hermes; only the
            # provider setting matters, so keep the detail and continue.
            logger.debug("requrv-kb: plugins enable holographic in %s: %s", profile.name, exc)
    try:
        configure(profile)
    except OSError as exc:
        result["error"] = str(exc)
        return result
    result["configured"] = configured(profile)
    return result


def ensure_all(*, install: bool = True) -> list[dict[str, Any]]:
    """Apply Holographic to every library bot installed on this computer."""
    from . import ledger

    results: list[dict[str, Any]] = []
    for profile in named_profiles():
        if ledger.read(profile) is None:
            continue
        results.append(ensure(profile, install=install))
    return results


def disable_all() -> list[dict[str, Any]]:
    """Return every library bot to the built-in memory provider; keep the plugin installed."""
    from . import ledger

    results: list[dict[str, Any]] = []
    for profile in named_profiles():
        if ledger.read(profile) is None:
            continue
        try:
            changed = configure(profile, provider="")
            results.append({"profile": profile.name, "configured": changed, "error": None})
        except OSError as exc:
            results.append({"profile": profile.name, "configured": False, "error": str(exc)})
    return results


def company_setting() -> str:
    conn = kb_connection.load()
    return conn.memory_provider if conn else ""
