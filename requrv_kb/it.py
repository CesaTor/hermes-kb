"""The IT reviewer: read the operators' proposals, fold them into the library, manage updates.

The IT is an operator folder too, with ``ruolo: it`` in its ``.autorizzazioni.yaml``. Its machine
can read every ``Operatori/<nome>/proposte/`` the cloud ACL exposes; these functions are the
review loop over that folder:

* ``proposals`` — what is waiting, per operator and bot, with the release it is based on;
* ``show`` — the diff between the operator's copy and the certified package;
* ``accept`` — write the copy into ``Biblioteca-Agenti/<bot>/``, bump the manifest's patch version
  and remove the proposal (deleting it is how the operator learns it was integrated);
* ``reject`` — move the proposal to ``proposte/Archivio/`` with a reason, because deleting it
  would read as "integrated";
* ``updates`` — what the library offers that this computer has not installed yet.

Nothing here runs on its own: accepting writes into the shared KB, so it needs ``confirm=True``
(the tool asks the operator first) and an IT role.
"""

from __future__ import annotations

import difflib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import authz, connection as kb_connection, package, personal
from . import mirror
from .paths import KBError
from .yamlio import load_config, write_config

_MAX_DIFF = 4_000


def operator_dirs(conn: kb_connection.Connection) -> list[Path]:
    """Every operator folder this machine can read, the IT one included."""
    found = {p.resolve() for p in kb_connection.operator_dirs(conn.roots)}
    personal_dir = Path(conn.personal)
    found.add(personal_dir.resolve())
    if personal_dir.parent.name.casefold() == kb_connection.OPERATORS_DIRNAME.casefold():
        found |= {child.resolve() for child in personal_dir.parent.iterdir() if child.is_dir()}
    return sorted(found)


def require_it(conn: kb_connection.Connection) -> None:
    if not authz.is_it(conn):
        raise KBError("Questa operazione è riservata al reparto IT: aggiungi «ruolo: it» al tuo "
                      ".autorizzazioni.yaml, oppure chiedi all'IT.")


def _package(conn: kb_connection.Connection, bot: str) -> package.Package:
    for library in kb_connection.library_dirs(conn.roots):
        try:
            folders = sorted(library.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            continue
        for folder in folders:
            if not folder.is_dir() or not (folder / package.MANIFEST).is_file():
                continue
            try:
                pkg = package.read(folder)
            except KBError:
                continue
            if pkg.name == bot:
                return pkg
    raise KBError(f"La libreria non ha un pacchetto per «{bot}».")


# --- reading ------------------------------------------------------------------------------------

def proposals(conn: kb_connection.Connection) -> list[dict[str, Any]]:
    """Everything waiting for review, across the operators this machine can read."""
    found: list[dict[str, Any]] = []
    for operator in operator_dirs(conn):
        root = operator / mirror.PROPOSALS_DIRNAME
        if not root.is_dir():
            continue
        for folder in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
            if not folder.is_dir() or folder.name == mirror.KNOWLEDGE_DIRNAME:
                continue
            manifest = mirror.read_manifest(_AsOperator(operator), folder.name)
            files = sorted((manifest.get("file") or {}).keys())
            if not files and not (folder / "SOUL.md").is_file():
                continue
            found.append({
                "operator": operator.name,
                "bot": folder.name,
                "base_version": manifest.get("base_version") or "",
                "updated_at": manifest.get("aggiornato_il") or "",
                "files": files,
                "path": str(folder),
            })
    return found


class _AsOperator:
    """A ``Connection``-shaped view of one operator folder, for the mirror helpers."""

    def __init__(self, folder: Path):
        self.personal = str(folder)
        self.operator = folder.name
        self.roots: tuple[str, ...] = ()


def knowledge(conn: kb_connection.Connection) -> list[dict[str, Any]]:
    """The knowledge files operators captured, with the operator they came from."""
    found: list[dict[str, Any]] = []
    for operator in operator_dirs(conn):
        folder = operator / mirror.PROPOSALS_DIRNAME / mirror.KNOWLEDGE_DIRNAME
        if not folder.is_dir():
            continue
        for item in sorted(folder.glob("*.md")):
            found.append({"operator": operator.name, "file": item.name, "path": str(item)})
    return found


def updates(conn: kb_connection.Connection) -> list[dict[str, Any]]:
    """Bots the library offers that this computer has not installed, or has an older version of."""
    from . import library

    return [{"bot": entry["name"], "version": entry["version"], "status": entry["status"],
             "installed_version": entry.get("installed_version")}
            for entry in library.catalog()["entries"] if entry["status"] in {"new", "update"}]


def show(conn: kb_connection.Connection, operator: str, bot: str) -> dict[str, Any]:
    """The operator's copy against the certified package, file by file."""
    operator_dir = next((p for p in operator_dirs(conn) if p.name == operator), None)
    if operator_dir is None:
        raise KBError(f"Non vedo la cartella dell'operatore «{operator}».")
    proposal = operator_dir / mirror.PROPOSALS_DIRNAME / bot
    if not proposal.is_dir():
        raise KBError(f"«{operator}» non ha proposte per il bot «{bot}».")
    pkg = _package(conn, bot)
    diffs: dict[str, str] = {}
    soul = proposal / "SOUL.md"
    if soul.is_file():
        diffs["SOUL.md"] = _diff(soul, Path(pkg.folder) / "SOUL.md")
    skills = proposal / "skills"
    if skills.is_dir():
        for child in sorted(skills.iterdir()):
            if not child.is_dir():
                continue
            current = personal.skill_dir(Path(pkg.folder) / "skills", child.name)
            diffs[f"skills/{child.name}"] = _diff(child / "SKILL.md",
                                                  (current / "SKILL.md") if current else Path("/non-esiste"))
    return {"operator": operator, "bot": bot,
            "base_version": mirror.read_manifest(_AsOperator(operator_dir), bot).get("base_version") or "",
            "files": diffs}


def _diff(left: Path, right: Path) -> str:
    try:
        one = left.read_text(encoding="utf-8-sig").splitlines()
        two = right.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return ""
    text = "\n".join(difflib.unified_diff(one, two, fromfile=f"proposta ({left.name})",
                                          tofile=f"libreria ({right.name})", lineterm="", n=3))
    return text[:_MAX_DIFF] + ("\n[...]" if len(text) > _MAX_DIFF else "")


# --- writing ------------------------------------------------------------------------------------

def _bump(version: str) -> str:
    parts = [part for part in str(version or "0.1.0").split(".")]
    while len(parts) < 3:
        parts.append("0")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except ValueError:
        parts[-1] = "1"
    return ".".join(parts)


def accept(conn: kb_connection.Connection, operator: str, bot: str, *, confirm: bool = False) -> dict[str, Any]:
    """Fold an operator's copy into the package and bump the release."""
    require_it(conn)
    operator_dir = next((p for p in operator_dirs(conn) if p.name == operator), None)
    if operator_dir is None:
        raise KBError(f"Non vedo la cartella dell'operatore «{operator}».")
    proposal = operator_dir / mirror.PROPOSALS_DIRNAME / bot
    if not proposal.is_dir():
        raise KBError(f"«{operator}» non ha proposte per il bot «{bot}».")
    pkg = _package(conn, bot)
    base = str(mirror.read_manifest(_AsOperator(operator_dir), bot).get("base_version") or "")
    plan = {"bot": bot, "operator": operator, "from_version": pkg.version,
            "to_version": _bump(pkg.version), "base_version": base,
            "stale": bool(base and base != pkg.version),
            "files": sorted([p.relative_to(proposal).as_posix() for p in proposal.rglob("*")
                             if p.is_file() and p.name != mirror.MANIFEST_FILENAME])}
    if not confirm:
        warning = (" La proposta parte dalla versione " + base +
                   ", il pacchetto è alla " + pkg.version +
                   ": potresti sovrascrivere modifiche successive." if plan["stale"] else "")
        return {"confirm_required": True, "plan": plan,
                "message": "Scrivo la proposta nel pacchetto e alzo la versione. Confermi?" + warning}
    target = Path(pkg.folder)
    if (proposal / "SOUL.md").is_file():
        shutil.copy2(proposal / "SOUL.md", target / "SOUL.md")
    skills = proposal / "skills"
    if skills.is_dir():
        (target / "skills").mkdir(exist_ok=True)
        for child in sorted(skills.iterdir()):
            if not child.is_dir():
                continue
            current = personal.skill_dir(target / "skills", child.name) or target / "skills" / child.name
            shutil.rmtree(current, ignore_errors=True)
            shutil.copytree(child, current)
    manifest_path = target / package.MANIFEST
    manifest = load_config(manifest_path)
    manifest["version"] = plan["to_version"]
    write_config(manifest_path, manifest)
    shutil.rmtree(proposal, ignore_errors=True)
    return {"accepted": plan, "next": "I bot degli operatori ricevono la nuova versione al prossimo controllo."}


def reject(conn: kb_connection.Connection, operator: str, bot: str, reason: str = "") -> dict[str, Any]:
    """Move the proposal aside with a reason; deleting it would read as ``integrated``."""
    require_it(conn)
    operator_dir = next((p for p in operator_dirs(conn) if p.name == operator), None)
    if operator_dir is None:
        raise KBError(f"Non vedo la cartella dell'operatore «{operator}».")
    proposal = operator_dir / mirror.PROPOSALS_DIRNAME / bot
    if not proposal.is_dir():
        raise KBError(f"«{operator}» non ha proposte per il bot «{bot}».")
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    archive = operator_dir / mirror.PROPOSALS_DIRNAME / "Archivio" / f"{bot}-{stamp}-{uuid4().hex[:6]}"
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(proposal), str(archive))
    (archive / "RIFIUTATA.md").write_text(
        f"# Proposta rifiutata — {bot}\n\n"
        f"- Data: {datetime.now(UTC).isoformat(timespec='seconds')}\n"
        f"- Operatore: {operator}\n"
        f"- Motivo: {reason.strip() or '(non indicato)'}\n", encoding="utf-8")
    return {"rejected": {"operator": operator, "bot": bot, "archived_at": str(archive), "reason": reason}}
