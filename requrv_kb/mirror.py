"""The operator's changes, mirrored in the shared folder for the IT to review.

A library bot can be edited: its ``SOUL.md`` and its shipped skills are the operator's while they
use it (the library replaces them on update, see :mod:`personal`). Every edit is copied here —
``Operatori/<nome>/proposte/<bot>/`` — in the same shape as the package, so the IT reads the change
in the KB without touching the machine, and so the copy survives an update that replaces the live
file. ``proposal.yaml`` records the release the copy was based on, which is what makes the question
"keep yours or take the new one?" answerable.

New skills are not mirrored: ``skills.create_dir`` already writes them in the operator's folder.
Only what the library owns lives here.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from . import ledger, personal
from .paths import KBError
from .yamlio import write_config

logger = logging.getLogger(__name__)

PROPOSALS_DIRNAME = "proposte"
KNOWLEDGE_DIRNAME = "knowledge"
SKILLS_DIRNAME = "skills"
MANIFEST_FILENAME = "proposal.yaml"
_COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".DS_Store")


def proposals_root(conn: Any) -> Path:
    return Path(conn.personal) / PROPOSALS_DIRNAME


def bot_dir(conn: Any, bot: str) -> Path:
    return proposals_root(conn) / bot


def knowledge_dir(conn: Any) -> Path:
    return proposals_root(conn) / KNOWLEDGE_DIRNAME


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


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


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
    soul = folder / "SOUL.md"
    if soul.is_file():
        value = personal.digest(soul)
        if value:
            files["SOUL.md"] = value
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


def mirror_soul(profile: Path, conn: Any, bot: str) -> bool:
    source = Path(profile) / "SOUL.md"
    if not source.is_file():
        return False
    _copy_file(source, bot_dir(conn, bot) / "SOUL.md")
    personal.note_personal(Path(profile), "soul")
    refresh(Path(profile), conn, bot)
    return True


def mirror_skill(profile: Path, conn: Any, bot: str, name: str) -> bool:
    source = personal.skill_dir(Path(profile) / SKILLS_DIRNAME, name)
    if source is None:
        return False
    _copy_tree(source, bot_dir(conn, bot) / SKILLS_DIRNAME / name)
    personal.note_personal(Path(profile), "skill", name)
    refresh(Path(profile), conn, bot)
    return True


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
    """``post_tool_call``: mirror a SOUL/skill write that just landed (never breaks the turn)."""
    if tool_name not in {"write_file", "patch"}:
        return
    from hermes_constants import get_hermes_home

    try:
        mirror_after_write(Path(get_hermes_home()), tool_name, args if isinstance(args, dict) else {})
    except Exception:  # a hook must never fail the tool call it observes
        logger.debug("requrv-kb: mirroring after %s failed", tool_name, exc_info=True)


def mirror_after_write(home: Path, tool_name: str, args: dict[str, Any]) -> list[str]:
    """Mirror a successful ``write_file``/``patch`` that touched the SOUL or a shipped skill."""
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
        if rel.casefold() == "soul.md" and mirror_soul(profile, conn, bot):
            touched.append("soul")
            continue
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
    """Put the operator's copy back over the certified file (the "keep mine" answer)."""
    folder = bot_dir(conn, bot)
    if kind == "soul":
        source, target = folder / "SOUL.md", Path(profile) / "SOUL.md"
    else:
        source = folder / SKILLS_DIRNAME / name
        target = personal.skill_dir(Path(profile) / SKILLS_DIRNAME, name) or Path(profile) / SKILLS_DIRNAME / name
    if not source.exists():
        raise KBError(f"La tua versione di «{name or 'SOUL'}» non è più nella cartella proposte.")
    if source.is_dir():
        _copy_tree(source, target)
    else:
        _copy_file(source, target)


def discard(profile: Path, conn: Any, bot: str, kind: str, name: str = "") -> None:
    """Drop the operator's copy (the "take the new one" answer)."""
    folder = bot_dir(conn, bot)
    target = folder / "SOUL.md" if kind == "soul" else folder / SKILLS_DIRNAME / name
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    else:
        target.unlink(missing_ok=True)
    refresh(Path(profile), conn, bot)
