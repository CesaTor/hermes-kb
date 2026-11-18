"""What a library bot may not be edited while the library owns it, and what the operator may.

The operator may change the bot's ``SOUL.md`` and its shipped skills: the change is theirs, it
takes effect at the next conversation and :mod:`mirror` copies it into
``Operatori/<nome>/proposte/<bot>/`` for the IT. What stays refused is the part that is not
knowledge but wiring: ``config.yaml`` keys the package manages, the package metadata
(``distribution.yaml``, ``.library-owned.json``, this plugin's bookkeeping) and the shipped
scheduled-job definitions. A shipped skill cannot be deleted or shadowed by a new one with the same
name, because the library would restore it at the next update and the two would silently diverge.

Not covered: a shell command that rewrites a file, and edits made from the app's settings screens
(core routes no plugin can veto). The next library update restores the certified file anyway, and
what was personal is restored from the proposals folder (see :mod:`personal`).
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
_CRON_DEFINITION_ACTIONS = {"remove", "update"}
_DELETING_SKILL_ACTIONS = {"delete", "remove_file"}
_METADATA = frozenset({"distribution.yaml", ".library-owned.json", ".requrv-kb-personal.json"})


def _norm(rel: str) -> str:
    return os.path.normpath(str(rel).replace("\\", "/")).replace("\\", "/").strip("/").casefold()


def owned(profile: Path, rel_path: str) -> bool:
    """Whether the library replaces *rel_path* on update."""
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


def patch_paths(args: dict[str, Any]) -> list[str]:
    """Every path a ``write_file``/``patch`` call may touch."""
    paths = [args["path"]] if isinstance(args.get("path"), str) else []
    if isinstance(args.get("patch"), str):
        paths += [a or b for a, b in _PATCH_HEADER.findall(args["patch"])]
    return paths


def _refusal(profile: Path, rel: str) -> Optional[str]:
    """The reason *rel* is refused, or None when the operator (or the agent) may write it."""
    rel = _norm(rel)
    if rel in _METADATA:
        return "metadata"
    if rel == "config.yaml" and (ledger.read(profile) or {}).get("config_managed"):
        return "config"
    return None


def _message(profile: Path, kind: str, name: str = "") -> str:
    record = ledger.read(profile) or {}
    bot = record.get("bot") or profile.name
    if kind == "config":
        return (f"Le chiavi di config.yaml del bot «{bot}» sono gestite dalla libreria e vengono "
                "riallineate a ogni aggiornamento: chiedi all'IT di cambiarle nel pacchetto.")
    if kind == "metadata":
        return f"«{name or 'distribution.yaml'}» descrive il pacchetto del bot «{bot}» e viene riscritto a ogni aggiornamento."
    if kind == "skill-exists":
        return (f"Esiste già una skill certificata «{name}»: modificala direttamente — la tua versione "
                "resta sul tuo computer e viene copiata in proposte/ per l'IT — oppure scegli un altro nome.")
    if kind == "job":
        return (f"Le attività pianificate del bot «{bot}» sono definite dalla libreria e vengono "
                "riallineate a ogni aggiornamento: chiedi all'IT di cambiarle nel pacchetto.")
    return (f"La skill «{name}» è certificata: la libreria la ripristina al prossimo aggiornamento. "
            "Se non ti serve, non richiamarla.")


def file_refusal(paths: Iterable[str], home: Path) -> Optional[str]:
    for raw in paths:
        resolved = os.path.realpath(os.path.expanduser(raw))
        found = _owner(resolved, home)
        if found and (kind := _refusal(*found)):
            return _message(found[0], kind, os.path.basename(raw.rstrip("/\\")))
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
                return _message(home, "skill-exists", skill)
            continue
        if action not in _DELETING_SKILL_ACTIONS:
            continue  # edit/patch: the operator's version, mirrored by `mirror`
        found = _find_skill(home, skill)
        if found is not None and owned(home, found.relative_to(home).as_posix()):
            return _message(home, "skill-delete", skill)
    return None


def cron_refusal(args: dict[str, Any], home: Path) -> Optional[str]:
    record = ledger.read(home)
    job = str(args.get("job_id") or "")
    if record is None or job not in record.get("cron_job_ids", []):
        return None
    return _message(home, "job") if args.get("action") in _CRON_DEFINITION_ACTIONS else None


def pre_tool_call(tool_name: str = "", args: Optional[dict] = None, **_: Any) -> Optional[dict[str, str]]:
    """The hook: ``{"action": "block", "message": ...}`` for a write the library will undo."""
    from hermes_constants import get_hermes_home

    args = args if isinstance(args, dict) else {}
    home = Path(get_hermes_home())
    if tool_name == "write_file":
        message = file_refusal([args.get("path", "")] if args.get("path") else [], home)
    elif tool_name == "patch":
        message = file_refusal(patch_paths(args), home)
    elif tool_name == "skill_manage":
        message = skill_refusal(args, home)
    elif tool_name == "cronjob":
        message = cron_refusal(args, home)
    else:
        return None
    return {"action": "block", "message": message} if message else None
