"""ReQurv KB routes, mounted by Hermes at ``/api/plugins/requrv-kb/`` for the Desktop half.

Every handler runs the blocking service in a worker thread (the gateway's event loop answers
every other Desktop request). Refusals come back as HTTP 400 with a sentence in ``detail``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from requrv_kb import connection as kb_connection  # noqa: E402  (after the path setup above)
from requrv_kb import library  # noqa: E402
from requrv_kb.paths import KBError  # noqa: E402

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
