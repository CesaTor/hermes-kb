"""Library bots are read-only to the agent: what the next update replaces cannot be edited.

A ``pre_tool_call`` hook blocks the agent's file writes, skill edits and scheduled-job edits
that touch library-owned content (the ledger's files, a shipped skill's folder, a shipped job, a
``config.yaml`` with ``config_managed`` keys). Everything the user or agent created stays
editable. To customise a library bot, duplicate it: the copy has no ledger and no lock.

Not covered: a shell command that rewrites a file, and edits made from the app's settings
screens (core routes no plugin can veto). The next library update restores owned content anyway.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from . import ledger
from .paths import profiles_root

_SKILL_MD = "/skill.md"
_PATCH_HEADER = re.compile(r"^\*\*\*\s+(?:Add|Update|Delete)\s+File:\s*(.+?)\s*$|^\*\*\*\s+Move\s+to:\s*(.+?)\s*$",
                           re.MULTILINE)
_SKILL_WRITES = {"edit", "patch", "delete", "write_file", "remove_file"}
# Pause, resume, run and cancel change a job's state; these change the definition the library ships.
_CRON_DEFINITION_ACTIONS = {"remove", "update"}
_NOUNS = {"file": "Questo file", "skill": "Questa skill", "job": "Questa attività pianificata"}


def _message(profile: Path, kind: str) -> str:
    record = ledger.read(profile) or {}
    bot = record.get("bot") or profile.name
    return (f"{_NOUNS[kind]} appartiene al bot di libreria «{bot}» e viene sostituito a ogni aggiornamento. "
            "Per personalizzarlo, duplica il bot come bot personale.")


def _norm(rel: str) -> str:
    return os.path.normpath(str(rel).replace("\\", "/")).replace("\\", "/").strip("/").casefold()


def owned(profile: Path, rel_path: str) -> bool:
    """Whether the library replaces *rel_path* (profile-relative) on update."""
    record = ledger.read(profile)
    rel = _norm(rel_path)
    if record is None or rel in ("", "."):
        return False
    if rel == "config.yaml":
        return bool(record.get("config_managed"))
    paths = [_norm(p) for p in record.get("paths", []) if isinstance(p, str)]
    skill_roots = [p[:-len(_SKILL_MD)] for p in paths if p.endswith(_SKILL_MD)]
    return (any(rel == p or rel.startswith(p + "/") or p.startswith(rel + "/") for p in paths)
            or any(rel == root or rel.startswith(root + "/") for root in skill_roots))


def _owner(resolved: str, home: Path) -> Optional[tuple[Path, str]]:
    """``(profile, relative path)`` when *resolved* lies in a named profile or the active home."""
    for root, per_profile in ((os.path.realpath(profiles_root()), True), (os.path.realpath(home), False)):
        if not resolved.startswith(root + os.sep):
            continue
        rel = resolved[len(root) + 1:]
        if not per_profile:
            return Path(root), rel
        name, _, inner = rel.partition(os.sep)
        return Path(root) / name, inner
    return None


def _patch_paths(args: dict[str, Any]) -> list[str]:
    paths = [args["path"]] if isinstance(args.get("path"), str) else []
    if isinstance(args.get("patch"), str):
        paths += [a or b for a, b in _PATCH_HEADER.findall(args["patch"])]
    return paths


def file_refusal(paths: Iterable[str], home: Path) -> Optional[str]:
    for raw in paths:
        resolved = os.path.realpath(os.path.expanduser(raw))
        found = _owner(resolved, home)
        if found and owned(*found):
            return _message(found[0], "file")
    return None


def _find_skill(home: Path, name: str) -> Optional[Path]:
    root = home / "skills"
    if not name or not root.is_dir():
        return None
    return next((md.parent for md in root.rglob("SKILL.md") if md.parent.name == name), None)


def skill_refusal(args: dict[str, Any], home: Path) -> Optional[str]:
    if ledger.read(home) is None:
        return None
    ops = args.get("operations") if isinstance(args.get("operations"), list) else [args]
    for op in (o if isinstance(o, dict) else {} for o in ops):
        action = op.get("action") or args.get("action")
        skill = op.get("name") or args.get("name") or ""
        if action == "create":
            category = str(op.get("category") or args.get("category") or "").strip()
            if category and skill and owned(home, f"skills/{category}/{skill}"):
                return _message(home, "skill")
            continue
        if action not in _SKILL_WRITES:
            continue
        found = _find_skill(home, skill)
        if found is not None and owned(home, found.relative_to(home).as_posix()):
            return _message(home, "skill")
    return None


def cron_refusal(args: dict[str, Any], home: Path) -> Optional[str]:
    record = ledger.read(home)
    job = str(args.get("job_id") or "")
    if record is None or job not in record.get("cron_job_ids", []):
        return None
    return _message(home, "job") if args.get("action") in _CRON_DEFINITION_ACTIONS else None


def pre_tool_call(tool_name: str = "", args: Optional[dict] = None, **_: Any) -> Optional[dict[str, str]]:
    """The hook: ``{"action": "block", "message": ...}`` for a write to library-owned content."""
    from hermes_constants import get_hermes_home

    args = args if isinstance(args, dict) else {}
    home = Path(get_hermes_home())
    if tool_name == "write_file":
        message = file_refusal([args.get("path", "")] if args.get("path") else [], home)
    elif tool_name == "patch":
        message = file_refusal(_patch_paths(args), home)
    elif tool_name == "skill_manage":
        message = skill_refusal(args, home)
    elif tool_name == "cronjob":
        message = cron_refusal(args, home)
    else:
        return None
    return {"action": "block", "message": message} if message else None
