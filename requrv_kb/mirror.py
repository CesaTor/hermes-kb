"""The operator's changes to a library bot's skills, mirrored in the shared folder for the IT.

A library bot's ``SOUL.md`` is certified and is replaced by every update; an operator who wants a
different identity duplicates the bot instead. The shipped **skills** remain editable: every change
is copied to ``Operatori/<nome>/proposte/<bot>/`` in the same shape as the package, so the IT reads
it in the KB without touching the machine, and the copy survives an update that replaces the live
file. ``proposal.yaml`` records the release the copy was based on.

New skills are not mirrored: ``skills.create_dir`` already writes them in the operator's folder.
Only what the library owns lives here.

The same module keeps a backup of the built-in ``memories/MEMORY.md`` and ``USER.md`` (and the
Holographic SQLite store when present) under ``Operatori/<nome>/memoria/<bot>/``. That backup is
for the operator and the IT; it is not published as knowledge.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from . import ledger, personal
from .paths import KBError
from .yamlio import write_config

logger = logging.getLogger(__name__)

PROPOSALS_DIRNAME = "proposte"
KNOWLEDGE_DIRNAME = "knowledge"
MEMORY_DIRNAME = "memoria"
SKILLS_DIRNAME = "skills"
MANIFEST_FILENAME = "proposal.yaml"
_MEMORY_FILES = ("MEMORY.md", "USER.md")
_MEMORY_DB = "memory_store.db"
_COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".DS_Store")


def proposals_root(conn: Any) -> Path:
    return Path(conn.personal) / PROPOSALS_DIRNAME


def bot_dir(conn: Any, bot: str) -> Path:
    return proposals_root(conn) / bot


def knowledge_dir(conn: Any) -> Path:
    return proposals_root(conn) / KNOWLEDGE_DIRNAME


def memory_dir(conn: Any, bot: str) -> Path:
    return Path(conn.personal) / MEMORY_DIRNAME / bot


def manifest_path(conn: Any, bot: str) -> Path:
    return bot_dir(conn, bot) / MANIFEST_FILENAME


def read_manifest(conn: Any, bot: str) -> dict[str, Any]:
    path = manifest_path(conn, bot)
    try:
        from .yamlio import safe_load

        data = safe_load(path) if path.is_file() else {}
    except KBError:
        data = {}
    return data if isinstance(data, dict) else {}


def _copy_tree(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.staging")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(source, staging, ignore=_COPY_IGNORE)
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)


def refresh(profile: Path, conn: Any, bot: str) -> dict[str, Any]:
    """Rewrite ``proposal.yaml`` from what is in the bot's proposals folder now.

    Skills are flattened to ``skills/<name>``: the proposal is for review, and the name is what
    identifies a skill in the package at install time.
    """
    folder = bot_dir(conn, bot)
    files: dict[str, str] = {}
    skills = folder / SKILLS_DIRNAME
    if skills.is_dir():
        for child in sorted(skills.iterdir()):
            if not child.is_dir():
                continue
            value = personal.digest(child)
            if value:
                files[f"{SKILLS_DIRNAME}/{child.name}"] = value
    record = personal.read(profile)
    manifest = {
        "bot": bot,
        "operatore": str(getattr(conn, "operator", "") or ""),
        "base_version": record.get("base_version") or "",
        "aggiornato_il": datetime.now(UTC).isoformat(timespec="seconds"),
        "file": dict(sorted(files.items())),
    }
    if not files:
        shutil.rmtree(folder, ignore_errors=True)
        return manifest
    folder.mkdir(parents=True, exist_ok=True)
    write_config(manifest_path(conn, bot), manifest)
    return manifest


def mirror_skill(profile: Path, conn: Any, bot: str, name: str) -> bool:
    source = personal.skill_dir(Path(profile) / SKILLS_DIRNAME, name)
    if source is None:
        return False
    _copy_tree(source, bot_dir(conn, bot) / SKILLS_DIRNAME / name)
    personal.note_personal(Path(profile), "skill", name)
    refresh(Path(profile), conn, bot)
    return True


def adopt_existing(profile: Path, conn: Any, bot: str) -> None:
    """Copy a pre-feature personal skill into proposals without changing its hashes."""
    from . import personal as _personal

    profile = Path(profile)
    record = _personal.read(profile)
    if not record:
        return
    folder = bot_dir(conn, bot)
    for name, entry in (record.get("skills") or {}).items():
        if not isinstance(entry, dict) or not entry.get("personal_hash"):
            continue
        source = _personal.skill_dir(profile / SKILLS_DIRNAME, name)
        target = folder / SKILLS_DIRNAME / name
        if source is not None and not target.exists():
            _copy_tree(source, target)
    refresh(profile, conn, bot)


def _write_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _backup_sqlite(source: Path, target: Path) -> bool:
    """Consistent copy of a live SQLite store; skipped when the source has not changed."""
    import sqlite3

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    try:
        stat = source.stat()
    except OSError:
        return False
    try:
        if target.is_file():
            current = target.stat()
            if current.st_size == stat.st_size and current.st_mtime_ns == stat.st_mtime_ns:
                return False
    except OSError:
        pass
    handle, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(handle)
    try:
        import sqlite3

        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_db, \
                sqlite3.connect(temporary) as target_db:
            source_db.backup(target_db)
        os.replace(temporary, target)
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        return True
    except (OSError, sqlite3.Error):
        logger.debug("requrv-kb: non ho potuto copiare memory_store.db", exc_info=True)
        return False
    finally:
        Path(temporary).unlink(missing_ok=True)


def backup_memory(profile: Path, conn: Any, bot: str) -> list[str]:
    """Copy the built-in memory files (and Holographic's DB) to the operator's shared folder."""
    if ledger.read(Path(profile)) is None:
        return []
    source_dir = Path(profile) / "memories"
    target_dir = memory_dir(conn, bot)
    copied: list[str] = []
    for name in _MEMORY_FILES:
        source = source_dir / name
        if not source.is_file():
            continue
        try:
            data = source.read_bytes()
        except OSError:
            continue
        target = target_dir / name
        try:
            if target.is_file() and target.read_bytes() == data:
                continue
            _write_bytes(target, data)
            copied.append(name)
        except OSError:
            logger.debug("requrv-kb: non ho potuto copiare %s", name, exc_info=True)
    database = Path(profile) / _MEMORY_DB
    if database.is_file():
        try:
            if _backup_sqlite(database, target_dir / _MEMORY_DB):
                copied.append(_MEMORY_DB)
        except OSError:
            logger.debug("requrv-kb: backup di memory_store.db non riuscito", exc_info=True)
    return copied


def _backup_current_memory() -> None:
    from hermes_constants import get_hermes_home

    profile = Path(get_hermes_home())
    record = ledger.read(profile)
    conn = _connection()
    if record is None or conn is None:
        return
    backup_memory(profile, conn, str(record.get("bot") or profile.name))


def _owned_skill_name(profile: Path, rel: str) -> Optional[str]:
    """The shipped skill *rel* (profile-relative) belongs to, when it does."""
    record = ledger.read(profile) or {}
    for owned in record.get("paths", []):
        if not isinstance(owned, str) or not owned.endswith("/SKILL.md"):
            continue
        root = owned[:-len("/SKILL.md")]
        normal = rel.strip("/").casefold()
        if normal == root.casefold() or normal.startswith(root.casefold() + "/"):
            return root.rstrip("/").split("/")[-1]
    return None


def on_tool_call(tool_name: str = "", args: Optional[dict] = None, **_: Any) -> None:
    """``post_tool_call``: back up memory and mirror a shipped-skill write (never breaks the turn)."""
    if tool_name == "memory":
        try:
            _backup_current_memory()
        except Exception:  # a hook must never fail the tool call it observes
            logger.debug("requrv-kb: memory backup after memory tool failed", exc_info=True)
        return
    if tool_name not in {"write_file", "patch"}:
        return
    from hermes_constants import get_hermes_home

    try:
        mirror_after_write(Path(get_hermes_home()), tool_name, args if isinstance(args, dict) else {})
    except Exception:  # a hook must never fail the tool call it observes
        logger.debug("requrv-kb: mirroring after %s failed", tool_name, exc_info=True)


def on_session_start(**_: Any) -> None:
    """Back up memory that existed before the first memory tool call of the session."""
    try:
        _backup_current_memory()
    except Exception:
        logger.debug("requrv-kb: memory backup at session start failed", exc_info=True)


def on_session_end(**_: Any) -> None:
    """Back up memory changed outside a memory tool call, once per turn; no-op when unchanged."""
    try:
        _backup_current_memory()
    except Exception:
        logger.debug("requrv-kb: memory backup at session end failed", exc_info=True)


def mirror_after_write(home: Path, tool_name: str, args: dict[str, Any]) -> list[str]:
    """Mirror a successful ``write_file``/``patch`` that touched a shipped skill."""
    from . import locks

    profile = Path(home)
    record = ledger.read(profile)
    conn = _connection()
    if record is None or conn is None:
        return []
    bot = str(record.get("bot") or profile.name)
    touched: list[str] = []
    for raw in locks.patch_paths(args):
        try:
            resolved = os.path.realpath(os.path.expanduser(raw))
        except (OSError, ValueError):
            continue
        base = os.path.realpath(str(profile))
        if not resolved.startswith(base + os.sep):
            continue
        rel = os.path.relpath(resolved, base).replace(os.sep, "/")
        name = _owned_skill_name(profile, rel)
        if name and mirror_skill(profile, conn, bot, name):
            touched.append(f"skill:{name}")
    return touched


def _connection() -> Any:
    from . import connection as kb_connection

    return kb_connection.load()


def on_skill_lifecycle(skill_name: str = "", **_: Any) -> None:
    """Hermes tells us a skill changed: mirror it when it is one the library owns."""
    from hermes_constants import get_hermes_home

    profile = Path(get_hermes_home())
    record = ledger.read(profile)
    conn = _connection()
    if record is None or conn is None or not skill_name:
        return
    found = personal.skill_dir(profile / SKILLS_DIRNAME, skill_name)
    if found is None:
        return
    rel = found.relative_to(profile).as_posix()
    if _owned_skill_name(profile, rel) is None:
        return  # a personal skill: it already lives in the operator's shared folder
    mirror_skill(profile, conn, str(record.get("bot") or profile.name), skill_name)


def restore(profile: Path, conn: Any, bot: str, kind: str, name: str = "") -> None:
    """Put the operator's skill copy back over the certified file (the "keep mine" answer)."""
    if kind != "skill":
        raise KBError("Il SOUL è certificato: per un'identità personale duplica il bot.")
    folder = bot_dir(conn, bot)
    source = folder / SKILLS_DIRNAME / name
    target = personal.skill_dir(Path(profile) / SKILLS_DIRNAME, name) or Path(profile) / SKILLS_DIRNAME / name
    if not source.exists():
        raise KBError(f"La tua versione della skill «{name}» non è più nella cartella proposte.")
    _copy_tree(source, target)


def discard(profile: Path, conn: Any, bot: str, kind: str, name: str = "") -> None:
    """Drop the operator's skill copy (the "take the new one" answer)."""
    if kind != "skill":
        raise KBError("Il SOUL è certificato: per un'identità personale duplica il bot.")
    folder = bot_dir(conn, bot)
    target = folder / SKILLS_DIRNAME / name
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    else:
        target.unlink(missing_ok=True)
    refresh(Path(profile), conn, bot)
