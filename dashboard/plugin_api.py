"""ReQurv KB routes, mounted by Hermes at ``/api/plugins/requrv-kb/`` for the Desktop half.

Every handler runs the blocking service in a worker thread (the gateway's event loop answers
every other Desktop request). Refusals come back as HTTP 400 with a sentence in ``detail``.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


def _load_service():
    """This copy's ``requrv_kb`` package under a name unique to its folder (see ``__init__.py``)."""
    package_dir = Path(__file__).resolve().parent.parent / "requrv_kb"
    # Folder and code version: a `hermes plugins update` in a running gateway loads the new code.
    stamp = max(f.stat().st_mtime_ns for f in package_dir.glob("*.py"))
    name = "requrv_kb_" + hashlib.sha256(f"{package_dir}:{stamp}".encode()).hexdigest()[:12]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            name, package_dir / "__init__.py", submodule_search_locations=[str(package_dir)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return (importlib.import_module(f"{name}.connection"), importlib.import_module(f"{name}.library"),
            importlib.import_module(f"{name}.watchdog"), importlib.import_module(f"{name}.paths").KBError)


kb_connection, library, watchdog, KBError = _load_service()

router = APIRouter()


async def _call(fn: Callable[..., Any], *args: Any) -> Any:
    try:
        return await asyncio.to_thread(fn, *args)
    except (KBError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ConnectBody(BaseModel):
    roots: list[str]
    operator: Optional[str] = None
    personal: Optional[str] = None


class NameBody(BaseModel):
    name: str


class ProfileBody(BaseModel):
    profile: str


class WatchdogBody(BaseModel):
    minutes: int


class DuplicateBody(BaseModel):
    profile: str
    name: str


def _connection_view() -> dict[str, Any]:
    conn = kb_connection.load()
    if conn is None:
        return {"connection": None, "check": None}
    return {"connection": conn.to_dict(), "check": kb_connection.check(conn, deep=False).to_dict()}


def _connect(body: ConnectBody) -> dict[str, Any]:
    conn = kb_connection.connect(body.roots, operator=body.operator, personal=body.personal)
    result = kb_connection.check(conn)
    if not result.ok:
        raise KBError(" ".join(result.problems))
    kb_connection.save(conn)
    return {"connection": conn.to_dict(), "check": result.to_dict()}


@router.get("/connection")
async def get_connection():
    return await _call(_connection_view)


@router.post("/connection")
async def post_connection(body: ConnectBody):
    return await _call(_connect, body)


@router.delete("/connection")
async def delete_connection():
    await _call(kb_connection.disconnect)
    return {"connection": None, "check": None}


@router.get("/library")
async def get_library():
    return await _call(library.catalog)


@router.get("/bots")
async def get_bots():
    return {"bots": await _call(library.status)}


@router.post("/library/install")
async def install(body: NameBody):
    return await _call(library.install, body.name)


@router.post("/library/update")
async def update(body: ProfileBody):
    return await _call(library.update, body.profile)


@router.post("/library/rollback")
async def rollback(body: ProfileBody):
    return await _call(library.rollback, body.profile)


@router.post("/library/sync")
async def sync():
    return {"results": await _call(library.sync)}


@router.post("/library/duplicate")
async def duplicate(body: DuplicateBody):
    return await _call(library.duplicate, body.profile, body.name)


def _watchdog_set(body: WatchdogBody) -> dict[str, Any]:
    kb_connection.set_watchdog_minutes(body.minutes)
    return watchdog.status()


def _reconcile_now() -> dict[str, Any]:
    """Check now, whatever the interval; ``busy`` when another process holds the machine-wide lease."""
    if kb_connection.load() is None:
        raise KBError("Questo computer non è ancora collegato alla KB.")
    record = watchdog.run(force=True)
    return {"busy": record is None, **watchdog.status()}


@router.get("/watchdog")
async def get_watchdog():
    return await _call(watchdog.status)


@router.post("/watchdog")
async def post_watchdog(body: WatchdogBody):
    return await _call(_watchdog_set, body)


@router.post("/watchdog/reconcile")
async def post_reconcile():
    return await _call(_reconcile_now)
