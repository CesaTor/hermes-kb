"""Which files of a library bot the library owns, and the snapshot taken before each update.

``<profile>/.library-owned.json`` marks a profile as a library bot: the files the package
wrote, its shipped cron job ids, its ``config_managed`` keys and the package folder it follows.
Before an update replaces them, those files (plus ``config.yaml`` and ``distribution.yaml``) are
copied to ``<profile>/.library-backup/<version>/``; the last :data:`KEEP_SNAPSHOTS` are kept and
:func:`rollback` restores the newest. Cron jobs merge by id and are not rolled back.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from .paths import KBError, read_json, write_json

LEDGER_FILENAME = ".library-owned.json"
BACKUP_DIRNAME = ".library-backup"
KEEP_SNAPSHOTS = 2
_META = ".snapshot-meta.json"
_ALWAYS = ("config.yaml", "distribution.yaml")


def read(profile: Path) -> Optional[dict[str, Any]]:
    data = read_json(Path(profile) / LEDGER_FILENAME)
    return data if isinstance(data, dict) and isinstance(data.get("paths"), list) else None


def write(profile: Path, **record: Any) -> None:
    write_json(Path(profile) / LEDGER_FILENAME, record)


def _slug(version: str) -> str:
    return re.sub(r"[^\w.+-]", "_", version) or "unversioned"


def snapshots(profile: Path) -> list[Path]:
    """Snapshot folders, oldest first."""
    root = Path(profile) / BACKUP_DIRNAME
    if not root.is_dir():
        return []
    return sorted((d for d in root.iterdir() if (d / _META).is_file()), key=lambda d: (d / _META).stat().st_mtime_ns)


def _copy(src: Path, dest: Path) -> None:
    if os.path.lexists(dest):
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def snapshot(profile: Path, from_version: str, to_version: str, incoming: list[str]) -> None:
    """Copy what an update to *to_version* is about to replace."""
    profile = Path(profile)
    ledger = read(profile)
    prior = list(ledger["paths"]) if ledger else []
    dest = profile / BACKUP_DIRNAME / _slug(from_version)
    if dest.exists():
        shutil.rmtree(dest)
    for rel in sorted({*prior, *incoming, *_ALWAYS}):
        src = profile / rel
        if src.is_file() and not src.is_symlink():
            _copy(src, dest / rel)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / _META).write_text(json.dumps({
        "from_version": from_version, "to_version": to_version, "had_ledger": ledger is not None,
        "prior": ledger or {}, "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    for stale in snapshots(profile)[:-KEEP_SNAPSHOTS]:
        shutil.rmtree(stale)


def _drop_added(profile: Path, current: list[str], prior: list[str]) -> None:
    for rel in sorted(set(current) - set(prior)):
        path = profile / rel
        if path.is_file() or path.is_symlink():
            path.unlink()
            for parent in path.parents:
                if parent == profile or any(parent.iterdir()):
                    break
                parent.rmdir()


def rollback(profile: Path) -> str:
    """Restore the newest snapshot; returns the restored version.

    The ledger remembers the version rolled back from (``rolled_back_from``) so the start-up sync
    does not re-apply it until the library publishes another one."""
    profile = Path(profile)
    found = snapshots(profile)
    if not found:
        raise KBError("Non c'è una versione precedente a cui tornare.")
    snap = found[-1]
    meta = json.loads((snap / _META).read_text(encoding="utf-8-sig"))
    current = read(profile) or {}
    prior = meta.get("prior") or {}
    if meta.get("had_ledger") and current:
        _drop_added(profile, current.get("paths", []), prior.get("paths", []))
    for src in sorted(p for p in snap.rglob("*") if p.is_file() and p.name != _META):
        _copy(src, profile / src.relative_to(snap))
    write(profile, **{**current, **prior, "version": meta["from_version"],
                      "cron_job_ids": current.get("cron_job_ids", prior.get("cron_job_ids", [])),
                      "rolled_back_from": meta["to_version"]})
    shutil.rmtree(snap)
    return meta["from_version"]


def can_rollback(profile: Path) -> bool:
    return bool(snapshots(profile))
