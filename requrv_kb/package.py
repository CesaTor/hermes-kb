"""A bot package in the library: a Hermes profile distribution folder, read straight from the KB.

Hermes' own installer copies the package (``hermes profile install``) and rewrites the profile's
``distribution.yaml`` with the fields it knows, so the library-only fields
(``config_managed``, ``proposals_resolved``/``rejected``) are always read from the package
itself. A package may hold only what a bot is made of; anything else is refused before Hermes
copies it, so a misplaced ``.env`` or memory folder never reaches a profile.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .cloud_files import find_online_only
from .paths import KBError, valid_profile_name
from .yamlio import safe_load

MANIFEST = "distribution.yaml"
ALLOWED_ENTRIES = frozenset({MANIFEST, "SOUL.md", "config.yaml", "mcp.json", "skills", "cron", ".env.template",
                             "README.md", "AGENTS.md"})
_IGNORED = frozenset({".DS_Store", "Thumbs.db", "desktop.ini", "__pycache__", ".git"})
CRON_STORE = ("cron", "jobs.json")


@dataclass(frozen=True)
class Package:
    folder: Path
    name: str
    version: str
    description: str = ""
    author: str = ""
    env_requires: tuple[dict[str, Any], ...] = ()
    config_managed: tuple[str, ...] = ()
    proposals_resolved: tuple[str, ...] = ()
    proposals_rejected: tuple[str, ...] = ()
    distribution_owned: tuple[str, ...] = field(default_factory=tuple)


def _strings(raw: Any, label: str) -> tuple[str, ...]:
    if not raw:
        return ()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise KBError(f"Nel pacchetto, «{label}» deve essere un elenco di testi.")
    return tuple(dict.fromkeys(item.strip() for item in raw if item.strip()))


def _config_managed(raw: Any) -> tuple[str, ...]:
    keys = _strings(raw, "config_managed")
    for key in keys:
        if any(not part.strip() for part in key.split(".")):
            raise KBError(f"Nel pacchetto, «config_managed» contiene una chiave non valida: {key!r}.")
    return keys


def read(folder: Path) -> Package:
    """The package at *folder*; raises :class:`KBError` with a sentence a person can act on."""
    path = folder / MANIFEST
    if not path.is_file():
        raise KBError("Questa voce della libreria è incompleta: manca la descrizione del bot.")
    data = safe_load(path)
    if not isinstance(data, dict):
        raise KBError("La descrizione del bot non è valida.")
    name = data.get("name")
    if not isinstance(name, str) or not valid_profile_name(name):
        raise KBError(f"Il nome del bot in {folder.name} non è valido (minuscole, cifre, - e _).")
    env = data.get("env_requires") or []
    if not isinstance(env, list):
        raise KBError("Nel pacchetto, «env_requires» deve essere un elenco.")
    return Package(
        folder=folder, name=name, version=str(data.get("version") or "0.1.0"),
        description=str(data.get("description") or ""), author=str(data.get("author") or ""),
        env_requires=tuple({"name": str(e.get("name", "")), "description": str(e.get("description", "")),
                            "required": bool(e.get("required", True))} for e in env if isinstance(e, dict)),
        config_managed=_config_managed(data.get("config_managed")),
        proposals_resolved=_strings(data.get("proposals_resolved"), "proposals_resolved"),
        proposals_rejected=_strings(data.get("proposals_rejected"), "proposals_rejected"),
        distribution_owned=_strings(data.get("distribution_owned"), "distribution_owned"),
    )


def assert_downloaded(path: Path) -> None:
    if find_online_only(path, limit=1):
        raise KBError("Alcuni file della libreria non sono ancora scaricati. Nell'app di Drive o Nextcloud "
                      "rendi la cartella disponibile offline, attendi la sincronizzazione e riprova.")


def assert_installable(pkg: Package) -> None:
    """Refuse a package that holds more than a bot is made of, or symlinks, or online-only files."""
    assert_downloaded(pkg.folder)
    for entry in pkg.folder.iterdir():
        if entry.name in _IGNORED:
            continue
        if entry.name not in ALLOWED_ENTRIES:
            raise KBError(f"Il pacchetto {pkg.name} contiene «{entry.name}», che un bot non può ricevere.")
    for path in pkg.folder.rglob("*"):
        if path.is_symlink():
            raise KBError(f"Il pacchetto {pkg.name} contiene collegamenti simbolici: non è installabile.")


def _files(root: Path, rel: tuple[str, ...]):
    if root.name in _IGNORED or root.is_symlink():
        return
    if root.is_dir():
        for child in sorted(root.iterdir()):
            yield from _files(child, (*rel, child.name))
    else:
        yield rel


def owned_paths(pkg: Package, *, preserve_config: bool) -> list[str]:
    """Profile-relative posix paths the Hermes installer writes from *pkg* (its ownership ledger)."""
    declared = [p.strip("/") for p in pkg.distribution_owned]
    tops = declared or [e.name for e in pkg.folder.iterdir()]
    paths = {MANIFEST}
    for top in tops:
        parts = tuple(p for p in top.split("/") if p)
        if not parts or parts[0] not in ALLOWED_ENTRIES:
            continue
        for rel in _files(pkg.folder.joinpath(*parts), parts):
            if rel == CRON_STORE or rel[0] == "cron":
                continue  # cron definitions merge by id into the profile's store: tracked as job ids
            if rel == ("config.yaml",) and preserve_config:
                continue
            paths.add(".env.EXAMPLE" if rel == (".env.template",) else "/".join(rel))
    return sorted(paths)


def cron_job_ids(pkg: Package) -> list[str]:
    store = pkg.folder.joinpath(*CRON_STORE)
    try:
        data = json.loads(store.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    if isinstance(jobs, dict):
        jobs = [{**v, "id": v.get("id") or k} for k, v in jobs.items() if isinstance(v, dict)]
    if not isinstance(jobs, list):
        return []
    return sorted({str(j["id"]) for j in jobs if isinstance(j, dict) and j.get("id")})


def skill_names(pkg: Package) -> list[str]:
    root = pkg.folder / "skills"
    if not root.is_dir():
        return []
    return sorted({md.parent.name for md in root.rglob("SKILL.md")})


def staged_config(pkg: Package) -> Optional[Path]:
    path = pkg.folder / "config.yaml"
    return path if path.is_file() else None
