"""Online-only ("dataless" / placeholder) cloud-sync files on the control host.

Drive, Nextcloud and OneDrive clients can leave a file as a stub whose bytes download on first
read. Reading one blocks on the network (or fails offline), so callers that copy from a synced
folder ask first. Both platforms report the state in ``stat()`` bits Python already exposes:
``st_flags`` on macOS (``SF_DATALESS``) and ``st_file_attributes`` on Windows (the RECALL/OFFLINE
attributes). Elsewhere neither attribute exists and nothing is ever a placeholder.
"""

from __future__ import annotations

import os
from pathlib import Path

# macOS sys/stat.h SF_DATALESS (``stat.SF_DATALESS`` only exists from Python 3.13).
_SF_DATALESS = 0x40000000
# Windows winnt.h: FILE_ATTRIBUTE_OFFLINE | RECALL_ON_OPEN | RECALL_ON_DATA_ACCESS.
_WIN_PLACEHOLDER_ATTRS = 0x1000 | 0x40000 | 0x400000


def _stat_flags(st: os.stat_result) -> tuple[int, int]:
    """``(macOS st_flags, Windows st_file_attributes)`` of a stat result; 0 where not exposed."""
    return getattr(st, "st_flags", 0), getattr(st, "st_file_attributes", 0)


def is_online_only(st: os.stat_result) -> bool:
    """Whether a stat result describes an online-only placeholder whose content is not on disk."""
    bsd_flags, win_attrs = _stat_flags(st)
    return bool(bsd_flags & _SF_DATALESS or win_attrs & _WIN_PLACEHOLDER_ATTRS)


def find_online_only(root: Path, limit: int = 5) -> list[Path]:
    """Up to *limit* online-only entries at or under *root* (symlinks are not followed)."""
    found: list[Path] = []
    pending = [Path(root)]
    while pending and len(found) < limit:
        path = pending.pop()
        try:
            st = path.lstat()
        except OSError:
            continue
        if is_online_only(st):
            found.append(path)
        elif path.is_dir() and not path.is_symlink():
            try:
                pending.extend(sorted(path.iterdir(), reverse=True))
            except OSError:
                continue  # unreadable folder: the copy that follows reports it with its own error
    return found
