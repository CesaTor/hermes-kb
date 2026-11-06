"""Where things live: the install root, its profiles and the plugin's machine-wide settings.

The KB connection belongs to the computer, not to one bot: every profile of the install reads
the same file, so a library bot (running in its own profile) sees the folders the coordinator
connected. Profiles follow Hermes' documented layout ``<root>/profiles/<name>``.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

PLUGIN_ID = "requrv-kb"
_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class KBError(ValueError):
    """A refusal or failure whose message is shown to a person as it is."""


def install_root() -> Path:
    """The Hermes install root (``~/.hermes`` or an explicit ``HERMES_HOME`` root), never a profile."""
    from hermes_constants import get_default_hermes_root

    return Path(get_default_hermes_root())


def profiles_root() -> Path:
    return install_root() / "profiles"


def valid_profile_name(name: str) -> bool:
    return bool(_PROFILE_RE.fullmatch(name or "")) and name != "default"


def profile_dir(name: str) -> Path:
    if name == "default":
        return install_root()
    if not valid_profile_name(name):
        raise KBError(f"«{name}» non è un nome di bot valido.")
    return profiles_root() / name


def deletion_marker(name: str) -> Path:
    """Where ``hermes profile delete`` records that a named profile was deleted.

    The marker outlives the folder: Hermes ignores a marked profile even if files of it linger, and
    ``hermes profile create`` is what clears it."""
    return profiles_root() / ".deleted" / name


def named_profiles() -> list[Path]:
    root = profiles_root()
    try:
        return sorted(p for p in root.iterdir()
                      if p.is_dir() and valid_profile_name(p.name) and not deletion_marker(p.name).exists())
    except OSError:
        return []


def data_dir() -> Path:
    return install_root() / "plugin-data" / PLUGIN_ID


def settings_path() -> Path:
    return data_dir() / "connection.json"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    """The parsed file, or None when absent or unreadable (bookkeeping is never fatal)."""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
