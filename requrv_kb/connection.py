"""The KB connection: the synced folders ("islands") this computer received, and the operator.

Nextcloud, Drive and SharePoint cannot narrow a share below a folder already shared read-write,
so every permission boundary is its own share: ``Biblioteca-Agenti/``, each ``NN-Area/``,
``Riservato/<Area>/`` and ``Operatori/<nome>/`` arrive as separate sync roots. A connection is
therefore a list of roots, each either an island itself or a folder holding islands, plus the
operator's personal folder. Nothing here enforces access: the cloud account does.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from .cloud_files import find_online_only
from .paths import KBError, read_json, settings_path, write_json

LIBRARY_DIRNAME = "Biblioteca-Agenti"
OPERATORS_DIRNAME = "Operatori"
SYSTEM_DIRNAME = "90-Sistema"
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                     *(f"lpt{i}" for i in range(1, 10))}


@dataclass(frozen=True)
class Connection:
    roots: tuple[str, ...]
    operator: str
    personal: str
    connected_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "roots": list(self.roots)}


@dataclass(frozen=True)
class Check:
    """``problems`` block use, ``warnings`` do not."""

    problems: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    libraries: tuple[str, ...] = ()
    areas: tuple[str, ...] = ()
    personal: str = ""

    @property
    def ok(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, **{k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}}


def valid_operator(name: str) -> bool:
    if not isinstance(name, str) or not name or name in {".", ".."} or name[-1:] in {".", " "}:
        return False
    if any(ord(char) < 32 or char in '<>:"/\\|?*' for char in name):
        return False
    return name.split(".", 1)[0].casefold() not in _WINDOWS_RESERVED


def normalize_path(raw: str) -> Path:
    text = str(raw).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    if not text:
        raise KBError("Il percorso della cartella è vuoto.")
    path = Path(os.path.expandvars(os.path.expanduser(text)))
    if not path.is_absolute():
        raise KBError(f"Usa un percorso completo, non «{raw}».")
    try:
        return path.resolve()
    except OSError:
        return path


def _readable_dir(path: Path) -> bool:
    return path.is_dir() and os.access(path, os.R_OK | os.X_OK)


def _children(path: Path) -> list[Path]:
    try:
        return sorted((c for c in path.iterdir() if c.is_dir() and not c.name.startswith(".")),
                      key=lambda c: c.name.casefold())
    except OSError:
        return []


def is_area_name(name: str) -> bool:
    return len(name) > 3 and name[:2].isdigit() and name[2] == "-"


def library_dirs(roots: tuple[str, ...]) -> list[Path]:
    """Every ``Biblioteca-Agenti`` island among or directly under the roots."""
    found: dict[str, Path] = {}
    for raw in roots:
        root = Path(raw)
        candidate = root if root.name.casefold() == LIBRARY_DIRNAME.casefold() else root / LIBRARY_DIRNAME
        if _readable_dir(candidate):
            found[str(candidate)] = candidate
    return list(found.values())


def area_dirs(roots: tuple[str, ...]) -> list[Path]:
    """Every readable ``NN-Area`` island among or directly under the roots (``Riservato/`` included)."""
    found: dict[str, Path] = {}
    for raw in roots:
        root = Path(raw)
        if is_area_name(root.name):
            found[str(root)] = root
            continue
        for child in _children(root):
            if is_area_name(child.name):
                found[str(child)] = child
            elif child.name.casefold() == "riservato":
                for area in _children(child):
                    if is_area_name(area.name):
                        found[str(area)] = area
    return list(found.values())


def _operator_candidates(roots: tuple[str, ...]) -> list[Path]:
    found: dict[str, Path] = {}
    for raw in roots:
        root = Path(raw)
        container = root if root.name.casefold() == OPERATORS_DIRNAME.casefold() else root / OPERATORS_DIRNAME
        for child in _children(container) if container.is_dir() else []:
            found[str(child)] = child
    return list(found.values())


def connect(roots: list[str], operator: Optional[str] = None, personal: Optional[str] = None) -> Connection:
    """Validate the folders and pick the operator's personal folder; nothing is saved."""
    if not roots:
        raise KBError("Indica almeno una cartella della KB.")
    resolved: list[str] = []
    for raw in roots:
        path = normalize_path(raw)
        if not _readable_dir(path):
            raise KBError(f"La cartella {path} non esiste o non è leggibile.")
        if str(path) not in resolved:
            resolved.append(str(path))
    resolved_roots = tuple(resolved)
    personal_path = normalize_path(personal) if personal else None
    if personal_path is not None and not _readable_dir(personal_path):
        raise KBError(f"La cartella personale {personal_path} non esiste o non è leggibile.")
    candidates = _operator_candidates(resolved_roots)
    if operator:
        if not valid_operator(operator):
            raise KBError("Il nome dell'operatore deve essere un nome di cartella valido.")
        matches = [c for c in candidates if c.name.casefold() == operator.casefold()]
        if personal_path is None:
            if len(matches) != 1:
                raise KBError(f"Non trovo la cartella Operatori/{operator}: indicala come cartella personale.")
            personal_path = matches[0]
        name = matches[0].name if matches else operator
    elif personal_path is not None:
        name = personal_path.name
    elif len(candidates) == 1:
        personal_path, name = candidates[0], candidates[0].name
    else:
        raise KBError("Non riesco a capire qual è la tua cartella personale: indica l'operatore.")
    if not valid_operator(name):
        raise KBError("Il nome dell'operatore deve essere un nome di cartella valido.")
    return Connection(resolved_roots, name, str(personal_path),
                      datetime.now(UTC).isoformat(timespec="seconds"))


def save(connection: Connection) -> None:
    write_json(settings_path(), connection.to_dict())


def load() -> Optional[Connection]:
    """The saved connection, or None when the computer was never connected (or the file is damaged)."""
    data = read_json(settings_path())
    if not isinstance(data, dict):
        return None
    roots, operator, personal = data.get("roots"), data.get("operator"), data.get("personal")
    if (not isinstance(roots, list) or not roots or not all(isinstance(r, str) for r in roots)
            or not isinstance(operator, str) or not valid_operator(operator) or not isinstance(personal, str)):
        return None
    return Connection(tuple(roots), operator, personal, str(data.get("connected_at") or ""))


def disconnect() -> None:
    settings_path().unlink(missing_ok=True)


def personal_skills_dir(connection: Connection) -> Path:
    return Path(connection.personal) / "skills"


def check(connection: Connection, *, deep: bool = True) -> Check:
    """What the connected folders offer, and what is missing; ``deep`` also finds online-only files."""
    problems: list[str] = []
    warnings: list[str] = []
    for raw in connection.roots:
        if not _readable_dir(Path(raw)):
            problems.append(f"La cartella {raw} non è più disponibile.")
    libraries = library_dirs(connection.roots)
    areas = area_dirs(connection.roots)
    if not libraries:
        problems.append(f"Nessuna cartella {LIBRARY_DIRNAME} tra quelle collegate.")
    if not areas:
        warnings.append("Nessuna cartella di area (es. 01-Marketing): il catalogo dei bot sarà vuoto.")
    if not _readable_dir(Path(connection.personal)):
        warnings.append("La cartella personale non è disponibile: le nuove skill restano sul computer.")
    if deep:
        for folder in [*libraries, *areas]:
            online = find_online_only(folder, limit=1)
            if online:
                problems.append(f"{online[0]} non è ancora scaricato: rendi la cartella disponibile offline.")
                break
    return Check(tuple(problems), tuple(warnings), tuple(map(str, libraries)), tuple(map(str, areas)),
                 connection.personal)
