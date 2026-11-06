"""The bot library: list what the KB offers, install, update, sync, roll back and duplicate bots.

Each ``<NN-Area>/bots.yaml`` the operator can read declares ``bots: [name, ...]`` (``*`` = all);
the library offers their union, taken from the ``Biblioteca-Agenti`` packages. No area lists →
an empty catalogue: the cloud share decides who sees what, the app only filters.

Installs and updates run Hermes' ``profile install`` / ``profile update`` on the package folder
itself, so the profile records the KB folder as its source. Around them this module keeps the
ownership ledger and pre-update snapshot (:mod:`.ledger`), applies ``config_managed`` keys, and
seeds the provider, the personal skills folder and the plugin (:mod:`.profile_config`).
"""

from __future__ import annotations

import os
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from . import connection as kb_connection
from . import hermes, ledger, package, profile_config
from .paths import (KBError, atomic_write_text, data_dir, deletion_marker, named_profiles, profile_dir, read_json,
                    valid_profile_name, write_json)
from .yamlio import safe_load

_LOCK = threading.RLock()
ALLOWLIST_FILENAME = "bots.yaml"
WILDCARD = "*"
ARCHIVE_DIRNAME = "Archivio"


def _require_connection() -> kb_connection.Connection:
    conn = kb_connection.load()
    if conn is None:
        raise KBError("Questo computer non è ancora collegato alla KB.")
    return conn


# --- catalogue ---------------------------------------------------------------------------------

def read_allowlists(conn: kb_connection.Connection) -> dict[str, Any]:
    allowed: set[str] = set()
    wildcard = False
    areas: list[str] = []
    unreadable: list[str] = []
    for area in kb_connection.area_dirs(conn.roots):
        path = area / ALLOWLIST_FILENAME
        if not path.is_file():
            continue
        try:
            data = safe_load(path)
        except KBError:
            unreadable.append(area.name)
            continue
        names = data.get("bots") if isinstance(data, dict) else None
        if names == WILDCARD:
            names = [WILDCARD]
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            unreadable.append(area.name)
            continue
        areas.append(area.name)
        for name in (n.strip() for n in names):
            wildcard = wildcard or name == WILDCARD
            if name and name != WILDCARD:
                allowed.add(name)
    return {"areas": areas, "unreadable": unreadable, "wildcard": wildcard, "allowed": allowed}


def _installed() -> dict[str, tuple[Path, dict[str, Any]]]:
    """Library bots on this computer, by package folder: ``{source: (profile, ledger)}``."""
    found = {}
    for profile in named_profiles():
        record = ledger.read(profile)
        if record and record.get("source"):
            found[os.path.normcase(str(record["source"]))] = (profile, record)
    return found


def _entry(pkg: package.Package, installed) -> dict[str, Any]:
    match = installed.get(os.path.normcase(str(pkg.folder)))
    profile, record = match if match else (None, None)
    status = "new" if record is None else ("installed" if record.get("version") == pkg.version else "update")
    return {
        "name": pkg.name, "version": pkg.version, "description": pkg.description, "author": pkg.author,
        "source": str(pkg.folder), "env_requires": list(pkg.env_requires), "skills": package.skill_names(pkg),
        "has_cron": bool(package.cron_job_ids(pkg)), "status": status,
        "installed_profile": profile.name if profile else None,
        "installed_version": record.get("version") if record else None, "error": None,
        "can_rollback": bool(profile and ledger.can_rollback(profile)),
    }


def _error_entry(folder: Path, exc: Exception) -> dict[str, Any]:
    return {"name": folder.name, "version": "", "description": "", "author": "", "source": str(folder),
            "env_requires": [], "skills": [], "has_cron": False, "status": "error",
            "installed_profile": None, "installed_version": None, "error": str(exc), "can_rollback": False}


def _packages(conn: kb_connection.Connection) -> list[tuple[Path, Optional[package.Package], Optional[Exception]]]:
    found = []
    for library in kb_connection.library_dirs(conn.roots):
        try:
            folders = sorted(library.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            continue
        for folder in folders:
            if not folder.is_dir() or folder.name.startswith(".") or not (folder / package.MANIFEST).exists():
                continue
            try:
                package.assert_downloaded(folder / package.MANIFEST)
                found.append((folder, package.read(folder), None))
            except KBError as exc:
                found.append((folder, None, exc))
    return found


def catalog() -> dict[str, Any]:
    """The bots the connected areas enable, with their install status."""
    conn = _require_connection()
    lists = read_allowlists(conn)
    installed = _installed()
    entries: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for folder, pkg, error in _packages(conn):
        if pkg is None:
            entries.append(_error_entry(folder, error))
            continue
        if not lists["wildcard"] and pkg.name not in lists["allowed"]:
            continue
        if pkg.name in seen:
            entries.append(_error_entry(folder, KBError(
                f"Due pacchetti si chiamano «{pkg.name}» ({seen[pkg.name]} e {folder}): rinominane uno.")))
            continue
        seen[pkg.name] = str(folder)
        entries.append(_entry(pkg, installed))
    offered = {e["name"] for e in entries}
    return {
        "entries": entries,
        "allowlist": {"areas": lists["areas"], "unreadable": lists["unreadable"],
                      "configured": bool(lists["areas"] or lists["unreadable"]),
                      "missing": sorted(lists["allowed"] - offered)},
    }


def _offered(name: str) -> package.Package:
    for entry in catalog()["entries"]:
        if entry["name"] == name and entry["status"] != "error":
            return package.read(Path(entry["source"]))
    raise KBError(f"La libreria non offre (o non ti mostra) il bot «{name}».")


# --- install / update / rollback ---------------------------------------------------------------

def _record(profile: Path, pkg: package.Package, *, preserve_config: bool, **extra: Any) -> None:
    previous = ledger.read(profile) or {}
    paths = set(package.owned_paths(pkg, preserve_config=preserve_config))
    if preserve_config:
        paths |= {p for p in previous.get("paths", []) if p == "config.yaml"}
    ledger.write(profile, version=pkg.version, source=str(pkg.folder), paths=sorted(paths),
                 cron_job_ids=package.cron_job_ids(pkg), config_managed=list(pkg.config_managed),
                 bot=pkg.name, updated_at=datetime.now(UTC).isoformat(timespec="seconds"), **extra)


def _after_copy(profile: Path, conn: kb_connection.Connection) -> None:
    profile_config.seed_provider(profile)
    profile_config.seed_skills_dir(profile, kb_connection.personal_skills_dir(conn))
    activate_plugin(profile)


def activate_plugin(profile: Path) -> None:
    """Keep this plugin's copy in the bot current and enabled there.

    A gateway already serving the bot loads a new copy when it next re-discovers that profile's
    plugins (at the latest on restart); a newly installed bot is discovered with it on first use."""
    profile_config.install_plugin_copy(profile)
    profile_config.enable_plugin(profile)


def _clear_deleted_remains(target: Path) -> bool:
    """Prepare *target* for a bot Hermes deleted; True when the name carries a deletion marker.

    Deleting a bot removes its profile folder with the ledger and backups inside, so what comes
    back is a fresh bot. Remains of a delete that failed half way (a locked file) are cleared here;
    a folder Hermes never deleted is somebody's bot and is left alone."""
    deleted = deletion_marker(target.name).exists()
    if target.exists():
        if not deleted:
            raise KBError(f"Esiste già un bot chiamato «{target.name}» su questo computer.")
        try:
            shutil.rmtree(target)
        except OSError as exc:
            raise KBError(f"Non riesco a ripulire i resti del bot «{target.name}» eliminato: "
                          "chiudi Hermes e riprova.") from exc
    return deleted


def _install(pkg: package.Package, conn: kb_connection.Connection) -> dict[str, Any]:
    package.assert_installable(pkg)
    target = profile_dir(pkg.name)
    redo = _clear_deleted_remains(target)
    args = ["profile", "install", str(pkg.folder), "--name", pkg.name, "--yes"]
    if redo:
        # Only `profile create` clears the deletion marker, and install then needs --force over its shell.
        hermes.run(["profile", "create", pkg.name, "--no-alias"])
        args.append("--force")
    try:
        hermes.run(args)
    except KBError:
        if redo:  # do not strand an empty bot that would block every later attempt
            try:
                hermes.run(["profile", "delete", pkg.name, "--yes"])
            except KBError:
                pass
        raise
    _record(target, pkg, preserve_config=False)
    _after_copy(target, conn)
    return {"profile": pkg.name, "version": pkg.version, "from_version": None}


def install(name: str) -> dict[str, Any]:
    with _LOCK:
        conn = _require_connection()
        return _install(_offered(name), conn)


def _library_profile(profile_name: str) -> tuple[Path, dict[str, Any]]:
    target = profile_dir(profile_name)
    record = ledger.read(target) if target.is_dir() else None
    if record is None:
        raise KBError(f"«{profile_name}» non è un bot della libreria.")
    return target, record


def _update(target: Path, record: dict[str, Any], pkg: package.Package, conn: kb_connection.Connection) -> dict[str, Any]:
    package.assert_installable(pkg)
    from_version = str(record.get("version") or "")
    ledger.snapshot(target, from_version, pkg.version, package.owned_paths(pkg, preserve_config=True))
    hermes.run(["profile", "update", target.name, "--yes"])
    profile_config.apply_managed(target, package.staged_config(pkg), pkg.config_managed)
    _record(target, pkg, preserve_config=True)
    _after_copy(target, conn)
    archive_proposals(pkg, conn)
    return {"profile": target.name, "version": pkg.version, "from_version": from_version}


def update(profile_name: str) -> dict[str, Any]:
    with _LOCK:
        conn = _require_connection()
        target, record = _library_profile(profile_name)
        source = Path(str(record["source"]))
        if not source.is_dir():
            raise KBError("La cartella della libreria non è disponibile.")
        return _update(target, record, package.read(source), conn)


def rollback(profile_name: str) -> dict[str, Any]:
    with _LOCK:
        target, _ = _library_profile(profile_name)
        return {"profile": target.name, "version": ledger.rollback(target)}


def _sync_profile(profile: Path, record: dict[str, Any], conn: kb_connection.Connection) -> dict[str, Any]:
    result: dict[str, Any] = {"profile": profile.name, "from": record.get("version"),
                              "to": record.get("version"), "status": "unchanged"}
    try:
        source = Path(str(record["source"]))
        if not source.is_dir():
            raise FileNotFoundError
        package.assert_downloaded(source / package.MANIFEST)
        pkg = package.read(source)
        if pkg.version not in (record.get("version"), record.get("rolled_back_from")):
            result["to"] = _update(profile, record, pkg, conn)["version"]
            result["status"] = "updated"
    except FileNotFoundError:
        result.update(status="source-unavailable", error="La cartella della libreria non è disponibile.")
    except KBError as exc:
        result.update(status="error", error=str(exc))
    return result


def sync(only: Optional[Path] = None) -> list[dict[str, Any]]:
    """Bring library bots (every one, or just *only*) to the version their package offers now.

    Safe at every app start and session start: a package folder that is gone or not downloaded
    reports ``source-unavailable``; a version the user rolled back from is not re-applied until
    the library publishes another one."""
    results: list[dict[str, Any]] = []
    conn = kb_connection.load()
    if conn is None:
        return results
    with _LOCK:
        for profile in ([only] if only is not None else named_profiles()):
            record = ledger.read(profile)
            if record and record.get("source"):
                activate_plugin(profile)  # a plugin update reaches every bot
                results.append(_sync_profile(profile, record, conn))
    return results


def _outcome(bot: str, profile: str, action: str, **extra: Any) -> dict[str, Any]:
    return {"bot": bot, "profile": profile, "action": action, **{k: v for k, v in extra.items() if v is not None}}


def _named_allowed(lists: dict[str, Any], name: str) -> bool:
    return lists["wildcard"] or name in lists["allowed"]


def _pending_path() -> Path:
    return data_dir() / "watchdog" / "pending-removal.json"


def _removal_is_safe(conn: kb_connection.Connection, lists: dict[str, Any]) -> bool:
    """Whether "this bot is not in the library" can be trusted: every folder was read, every list parsed.

    An offline drive or a folder not yet downloaded looks exactly like a library that dropped a bot,
    so any doubt (unreadable root, list or area, files not downloaded, no area list at all) means no removal."""
    return kb_connection.check(conn).ok and not lists["unreadable"] and bool(lists["areas"])


def _remove_not_allowed(profile: Path, bot: str, version: Any, pending: set[str], strikes: set[str]) -> dict[str, Any]:
    """Two strikes in a row, then Hermes' own ``profile delete`` (chats and memory go with the bot)."""
    strikes.add(profile.name)
    if profile.name not in pending:
        return _outcome(bot, profile.name, "pending-removal", **{"from": version})
    try:
        hermes.run(["profile", "delete", profile.name, "--yes"])
    except KBError as exc:  # e.g. the bot is in use: try again at the next pass
        return _outcome(bot, profile.name, "pending-removal", **{"from": version}, error=str(exc))
    strikes.discard(profile.name)
    return _outcome(bot, profile.name, "removed", **{"from": version})


def reconcile() -> list[dict[str, Any]]:
    """Bring this computer in line with the library: install what the areas allow and is missing
    (deleted by the user, or never installed), update the installed bots, and remove library bots
    the areas no longer allow.

    Only profiles carrying the library ledger are ever removed (bots the user created or duplicated
    have none), only when every folder and list was read, and only on the second pass in a row that
    finds them not allowed. Results are ``{bot, profile, action, from?, to?, error?}`` with ``action``
    one of ``installed``, ``updated``, ``unchanged``, ``error``, ``source-unavailable``,
    ``pending-removal``, ``removed``."""
    results: list[dict[str, Any]] = []
    conn = kb_connection.load()
    if conn is None:
        return results
    with _LOCK:
        lists = read_allowlists(conn)
        entries = catalog()["entries"]
        installed = _installed()
        listed = {os.path.normcase(e["source"]) for e in entries if e["status"] != "error"}
        broken = {os.path.normcase(e["source"]) for e in entries if e["status"] == "error"}
        present = {profile.name for profile, _ in installed.values()}
        for entry in entries:
            name = entry["name"]
            if entry["status"] == "error":
                if _named_allowed(lists, name):
                    results.append(_outcome(name, name, "error", error=entry["error"]))
            elif entry["status"] == "new" and name not in present:  # present under another source: the sync below
                try:
                    done = _install(package.read(Path(entry["source"])), conn)
                    results.append(_outcome(name, name, "installed", to=done["version"]))
                except (KBError, OSError) as exc:
                    results.append(_outcome(name, name, "error", error=str(exc)))
        safe = _removal_is_safe(conn, lists)
        pending = set(read_json(_pending_path()) or [])
        strikes: set[str] = set() if safe else set(pending)  # an unsure pass neither adds nor clears strikes
        for source, (profile, record) in installed.items():
            bot = str(record.get("bot") or profile.name)
            gone = source not in listed and source not in broken and Path(str(record["source"])).is_dir()
            if gone and safe:
                results.append(_remove_not_allowed(profile, bot, record.get("version"), pending, strikes))
                continue
            if gone:
                continue
            for done in sync(only=profile):
                results.append(_outcome(bot, profile.name, done["status"], **{"from": done["from"], "to": done["to"]},
                                        error=done.get("error")))
        write_json(_pending_path(), sorted(strikes))
    return results


def status() -> list[dict[str, Any]]:
    return [{"profile": p.name, "bot": r.get("bot", p.name), "version": r.get("version"), "source": r.get("source"),
             "rolled_back_from": r.get("rolled_back_from"), "can_rollback": ledger.can_rollback(p)}
            for p in named_profiles() if (r := ledger.read(p))]


# --- duplicate ---------------------------------------------------------------------------------

def _slug(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.strip().lower())
    return "-".join(part for part in cleaned.split("-") if part)[:64]


def duplicate(source_profile: str, name: str) -> dict[str, Any]:
    """Copy a bot into a personal profile that no library update reaches (and no lock applies to)."""
    with _LOCK:
        source = profile_dir(source_profile)
        if not source.is_dir():
            raise KBError(f"Il bot «{source_profile}» non esiste.")
        new_id = _slug(name)
        if not valid_profile_name(new_id):
            raise KBError("Dai alla copia un nome con lettere o cifre.")
        target = profile_dir(new_id)
        if target.exists():
            raise KBError(f"Esiste già un bot chiamato «{new_id}». Scegli un altro nome.")
        hermes.run(["profile", "create", new_id, "--clone-from", source_profile, "--no-alias"])
        for leftover in (ledger.LEDGER_FILENAME, package.MANIFEST):
            (target / leftover).unlink(missing_ok=True)
        shutil.rmtree(target / ledger.BACKUP_DIRNAME, ignore_errors=True)
        profile_config.seed_provider(target)
    return {"profile": new_id}


# --- operator proposals ------------------------------------------------------------------------

def _split_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    import re

    heads = list(re.finditer(r"^##\s+\[?([^\s\]]+)\]?", text, re.MULTILINE))
    if not heads:
        return text.rstrip(), []
    blocks = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        blocks.append((head.group(1), text[head.start():end].rstrip()))
    return text[:heads[0].start()].rstrip(), blocks


def archive_proposals(pkg: package.Package, conn: kb_connection.Connection) -> None:
    """Move the operator's proposals a new release incorporated or declined to ``proposte/Archivio``."""
    resolved = set(pkg.proposals_resolved) | set(pkg.proposals_rejected)
    from .prompt import proposals_path

    path = proposals_path(conn, pkg.name)
    if not resolved or not path.is_file():
        return
    preamble, blocks = _split_blocks(path.read_text(encoding="utf-8-sig"))
    moved = [(pid, block) for pid, block in blocks if pid in resolved]
    if not moved:
        return
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    entries = [f"> {'Rifiutata' if pid in pkg.proposals_rejected else 'Recepita'} nella versione {pkg.version}\n\n{block}"
               for pid, block in moved]
    atomic_write_text(path.parent / ARCHIVE_DIRNAME / f"{pkg.name}-{stamp}-{uuid4().hex[:8]}.md",
                      f"# Proposte archiviate — {pkg.name} {pkg.version}\n\n" + "\n\n".join(entries) + "\n")
    kept = ([preamble] if preamble else []) + [block for pid, block in blocks if pid not in resolved]
    atomic_write_text(path, ("\n\n".join(kept).rstrip() + "\n") if kept else "")
