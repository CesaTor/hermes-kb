"""The operator's own copy of a library bot: which file diverges, and from which release.

A library bot is replaced by every update, so what the operator changed is kept aside: the same
file lives under ``Operatori/<nome>/proposte/<bot>/`` (see :mod:`mirror`) and the IT reads it from
the shared folder. This module holds only the bookkeeping, local to the profile and never synced:
the certified hash of ``SOUL.md`` and of every shipped skill at the last sync (``base_hash``), what
is live now (``live_hash``), and the operator's own copy when one exists (``personal_hash``).

From those three an update decides:

* ``reapply`` — the operator has their own copy but the library did not change that file: the
  personal copy is restored silently after the update;
* ``conflict`` — both changed: the certified version stays live and the question is left for the
  operator at the next conversation (``pending``);
* ``clean`` — nothing personal: the certified file is simply updated.

The question is answered in chat through the ``kb_personal`` tool or ``hermes kb resolve``; "keep"
puts the personal copy back over the new certified file, "take" discards it (and with it the copy
in the proposals folder, because deleting there is what tells the IT a change was integrated).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from . import package
from .paths import KBError, read_json, write_json

logger = logging.getLogger(__name__)

FILENAME = ".requrv-kb-personal.json"
_SKIP = frozenset({".git", "__pycache__", ".pytest_cache", ".DS_Store"})
KEEP, TAKE = "keep", "take"


def path(profile: Path) -> Path:
    return Path(profile) / FILENAME


def read(profile: Path) -> dict[str, Any]:
    """The record, or an empty mapping when the profile never had one."""
    data = read_json(path(profile))
    if not isinstance(data, dict) or not isinstance(data.get("skills"), dict):
        return {}
    data.setdefault("soul", {})
    data.setdefault("pending", [])
    return data


def write(profile: Path, record: dict[str, Any]) -> None:
    write_json(path(profile), record)


def forget(profile: Path) -> None:
    """Drop the record (a duplicated bot is the operator's own, not a library one)."""
    path(profile).unlink(missing_ok=True)


# --- hashes -------------------------------------------------------------------------------------

def digest(target: Path) -> Optional[str]:
    """SHA-256 of a file, or of a skill folder (relative paths included), or None when missing."""
    target = Path(target)
    stream = hashlib.sha256()
    if target.is_file() and not target.is_symlink():
        stream.update(target.read_bytes())
        return stream.hexdigest()
    if not target.is_dir() or target.is_symlink():
        return None
    found = False
    for item in sorted(target.rglob("*")):
        rel = item.relative_to(target)
        if not item.is_file() or item.is_symlink() or _SKIP.intersection(rel.parts):
            continue
        found = True
        stream.update(rel.as_posix().encode("utf-8") + b"\0")
        stream.update(item.read_bytes() + b"\0")
    return stream.hexdigest() if found else None


def skill_dir(root: Path, name: str) -> Optional[Path]:
    """The directory holding the ``SKILL.md`` of skill *name* under *root*, if any."""
    root = Path(root)
    if not name or not root.is_dir():
        return None
    matches = [md.parent for md in sorted(root.rglob("SKILL.md")) if md.parent.name.casefold() == name.casefold()]
    return matches[0] if matches else None


def _live(profile: Path, kind: str, name: str = "") -> Optional[str]:
    if kind == "soul":
        return digest(Path(profile) / "SOUL.md")
    found = skill_dir(Path(profile) / "skills", name)
    return digest(found) if found else None


def certified(pkg: package.Package) -> dict[str, Any]:
    """The hashes the package will write on the next install or update."""
    root = Path(pkg.folder)
    skills = {}
    for name in package.skill_names(pkg):
        found = skill_dir(root / "skills", name)
        skills[name] = digest(found) if found else None
    return {"soul": digest(root / "SOUL.md"), "skills": skills}


# --- the record ---------------------------------------------------------------------------------

def _entry(base: Optional[str], live: Optional[str]) -> dict[str, Any]:
    # A profile installed before this feature may already hold a personal SOUL/skill: if the live
    # content differs from the package it received, adopt it now instead of losing it on the first
    # update.
    personal = live if live is not None and live != base else None
    return {"base_hash": base, "live_hash": live, "personal_hash": personal}


def record_install(profile: Path, pkg: package.Package) -> dict[str, Any]:
    """Start the record after an install: the package's content is the base."""
    current = certified(pkg)
    record = {
        "bot": pkg.name,
        "base_version": pkg.version,
        "soul": _entry(current["soul"], _live(profile, "soul")),
        "skills": {name: _entry(hash_value, _live(profile, "skill", name))
                   for name, hash_value in current["skills"].items()},
        "pending": [],
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write(profile, record)
    return record


def ensure(profile: Path, pkg: package.Package) -> dict[str, Any]:
    """A record for a bot installed before this feature: its current files become the base.

    A file already changed by the operator is adopted as personal and marked for the first conflict,
    so the first update asks instead of silently replacing it. From then on every change is tracked.
    """
    record = read(profile)
    if record:
        return record
    record = record_install(profile, pkg)
    changed = False
    entries = [record.get("soul") or {}, *(record.get("skills") or {}).values()]
    for entry in entries:
        if entry.get("personal_hash") and entry.get("base_hash") != entry.get("live_hash"):
            entry["base_hash"] = entry.get("live_hash")
            changed = True
    if changed:
        write(profile, record)
    return record


def note_personal(profile: Path, kind: str, name: str = "") -> None:
    """Record that the live SOUL/skill is now the operator's own version."""
    record = read(profile)
    if not record:
        return
    entry = _find(record, kind, name)
    if entry is None:
        return
    live = _live(profile, kind, name)
    entry["live_hash"] = live
    entry["personal_hash"] = None if live is not None and live == entry.get("base_hash") else live
    record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    write(profile, record)


def pending(profile: Path) -> list[dict[str, Any]]:
    return [p for p in read(profile).get("pending", []) if isinstance(p, dict) and p.get("kind") in {"soul", "skill"}]


def pending_count(profile: Path) -> int:
    return len(pending(profile))


def _find(record: dict[str, Any], kind: str, name: str = "") -> Optional[dict[str, Any]]:
    if kind == "soul":
        return record.setdefault("soul", {})
    skills = record.setdefault("skills", {})
    return skills.setdefault(name, {}) if name else None


def _key(kind: str, name: str = "") -> tuple[str, str]:
    return kind, name


# --- update planning ----------------------------------------------------------------------------

def _state(entry: Optional[dict[str, Any]], incoming: Optional[str], unanswered: bool = False) -> str:
    if not entry or not incoming:
        return "clean"
    personal = entry.get("personal_hash")
    if not personal:
        return "clean"
    if unanswered or incoming != entry.get("base_hash"):
        return "conflict"
    return "reapply"


def plan(profile: Path, pkg: package.Package, conn: Any = None) -> dict[str, Any]:
    """What the update is about to do with the personal copies, computed before it runs."""
    record = ensure(profile, pkg)
    if conn is not None:
        from . import mirror

        mirror.adopt_existing(profile, conn, str(record.get("bot") or pkg.name))
    incoming = certified(pkg)
    waiting = {_key(str(p.get("kind")), str(p.get("name") or ""))
               for p in record.get("pending", []) if isinstance(p, dict)}
    return {
        "bot": record.get("bot") or pkg.name,
        "from_version": record.get("base_version"),
        "soul": _state(record.get("soul"), incoming["soul"], _key("soul", "") in waiting),
        "skills": {name: _state(entry, incoming["skills"].get(name), _key("skill", name) in waiting)
                   for name, entry in record.get("skills", {}).items()
                   if name in incoming["skills"]},
        "incoming": incoming,
    }


def apply_after_update(profile: Path, pkg: package.Package, planned: dict[str, Any],
                       conn: Any) -> dict[str, Any]:
    """Re-apply or hold back the personal copies, now that Hermes wrote the new version."""
    from . import mirror

    record = read(profile) or record_install(profile, pkg)
    bot = str(record.get("bot") or planned.get("bot") or pkg.name)
    from_version = planned.get("from_version")
    incoming = planned["incoming"]
    record["bot"] = bot
    record["base_version"] = pkg.version
    pending: dict[tuple[str, str], dict[str, Any]] = {}

    def settle(kind: str, name: str, state: str) -> None:
        entry = _find(record, kind, name)
        if entry is None:
            return
        new_hash = incoming["soul"] if kind == "soul" else incoming["skills"].get(name)
        if state == "reapply" and entry.get("personal_hash"):
            try:
                mirror.restore(profile, conn, bot, kind, name)
            except KBError:
                logger.warning("requrv-kb: la copia personale di %s non è più in proposte/", name or "SOUL")
                entry["personal_hash"] = None
        elif state == "conflict" and entry.get("personal_hash"):
            pending[_key(kind, name)] = {
                "kind": kind, "name": name, "from_version": from_version, "to_version": pkg.version,
                "since": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        else:
            entry["personal_hash"] = None
        entry["base_hash"] = new_hash
        entry["live_hash"] = _live(profile, kind, name) or new_hash
        if state == "clean":
            entry["personal_hash"] = None

    settle("soul", "", planned.get("soul") or "clean")
    for name, state in (planned.get("skills") or {}).items():
        settle("skill", name, state)

    record["pending"] = list(pending.values())
    record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    write(profile, record)
    reapplied = (["SOUL"] if planned.get("soul") == "reapply" else []) + [
        name for name, state in (planned.get("skills") or {}).items() if state == "reapply"]
    return {"bot": bot, "version": pkg.version, "reapplied": reapplied,
            "pending": [{"kind": p["kind"], "name": p["name"]} for p in record["pending"]]}


# --- the operator's decision --------------------------------------------------------------------

def decide(profile: Path, conn: Any, kind: str, name: str, choice: str) -> dict[str, Any]:
    """Apply "keep" (the personal copy goes back over the certified one) or "take" (discard it)."""
    from . import mirror

    choice = str(choice or "").strip().lower()
    if choice not in {KEEP, TAKE}:
        raise KBError("La scelta è «keep» (tengo la mia) o «take» (prendo la nuova).")
    record = read(profile)
    if not record:
        raise KBError("Questo bot non è un bot di libreria.")
    item = next((p for p in record.get("pending", [])
                 if p.get("kind") == kind and (kind == "soul" or p.get("name") == name)), None)
    if item is None:
        raise KBError(f"Non c'è nessuna versione personale da decidere per «{name or 'SOUL'}».")
    bot = str(record.get("bot") or Path(profile).name)
    entry = _find(record, kind, name)
    if entry is None:
        raise KBError(f"«{name}» non è più un file di questo bot.")
    if choice == KEEP:
        mirror.restore(profile, conn, bot, kind, name)
        entry["live_hash"] = entry.get("personal_hash")
    else:
        mirror.discard(profile, conn, bot, kind, name)
        entry["personal_hash"] = None
        entry["live_hash"] = _live(profile, kind, name) or entry.get("live_hash")
    record["pending"] = [p for p in record.get("pending", []) if p is not item]
    record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    write(profile, record)
    return {"kind": kind, "name": name, "choice": choice}


def decide_by_index(profile: Path, conn: Any, index: int, choice: str) -> dict[str, Any]:
    items = pending(profile)
    if not 0 < index <= len(items):
        raise KBError(f"Indice non valido: ci sono {len(items)} versioni personali da decidere.")
    item = items[index - 1]
    return decide(profile, conn, str(item["kind"]), str(item.get("name") or ""), choice)
