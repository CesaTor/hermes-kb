"""``hermes kb ...`` and ``/kb ...``: one parser, one service, readable or JSON output."""

from __future__ import annotations

import argparse
import json
import shlex
from typing import Any, Callable

from . import connection as kb_connection
from . import library
from .paths import KBError


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # the slash command must not exit the process
        raise KBError(message)


def setup_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Output leggibile da programmi")
    sub = parser.add_subparsers(dest="kb_action", metavar="COMANDO")
    link = sub.add_parser("connect", help="Collega le cartelle sincronizzate della KB")
    link.add_argument("--root", action="append", required=True, help="Cartella della KB (ripetibile)")
    link.add_argument("--operator", help="Nome della tua cartella in Operatori/")
    link.add_argument("--personal", help="La tua cartella personale, se è un'isola separata")
    sub.add_parser("disconnect", help="Scollega questo computer dalla KB (i bot restano)")
    sub.add_parser("check", help="Controlla le cartelle collegate")
    sub.add_parser("list", help="Elenca i bot che la libreria ti offre")
    sub.add_parser("status", help="Elenca i bot di libreria installati")
    sub.add_parser("sync", help="Aggiorna tutti i bot di libreria")
    for action, text in (("install", "Installa un bot"), ("update", "Aggiorna un bot"),
                         ("rollback", "Torna alla versione precedente di un bot")):
        sub.add_parser(action, help=text).add_argument("bot")
    dup = sub.add_parser("duplicate", help="Copia un bot in un bot personale modificabile")
    dup.add_argument("bot")
    dup.add_argument("name", help="Nome della copia")
    parser.set_defaults(kb_action="check")


def _connect(a) -> dict[str, Any]:
    conn = kb_connection.connect(a.root, operator=a.operator, personal=a.personal)
    kb_connection.save(conn)
    return {"connection": conn.to_dict(), "check": kb_connection.check(conn).to_dict()}


def _check(_a) -> dict[str, Any]:
    conn = kb_connection.load()
    if conn is None:
        raise KBError('Questo computer non è collegato alla KB: usa «hermes kb connect --root "<cartella>"».')
    return {"connection": conn.to_dict(), "check": kb_connection.check(conn).to_dict()}


_ACTIONS: dict[str, Callable[[Any], Any]] = {
    "connect": _connect,
    "disconnect": lambda a: (kb_connection.disconnect(), {"disconnected": True})[1],
    "check": _check,
    "list": lambda a: library.catalog(),
    "status": lambda a: {"bots": library.status()},
    "sync": lambda a: {"results": library.sync()},
    "install": lambda a: library.install(a.bot),
    "update": lambda a: library.update(a.bot),
    "rollback": lambda a: library.rollback(a.bot),
    "duplicate": lambda a: library.duplicate(a.bot, a.name),
}


def _text(action: str, result: dict[str, Any]) -> str:
    if action in {"connect", "check"}:
        c, chk = result["connection"], result["check"]
        lines = [f"Operatore: {c['operator']}", f"Cartella personale: {c['personal']}", "Cartelle:",
                 *(f"  {r}" for r in c["roots"])]
        lines += [f"✗ {p}" for p in chk["problems"]] + [f"! {w}" for w in chk["warnings"]]
        return "\n".join(lines + (["OK"] if chk["ok"] else []))
    if action == "list":
        rows = [f"{e['name']:<24} {e['version']:<10} {e['status']}" + (f"  ({e['error']})" if e["error"] else "")
                for e in result["entries"]]
        return "\n".join(rows) or "La libreria non ti offre bot: controlla i bots.yaml delle tue aree."
    if action == "status":
        return "\n".join(f"{b['profile']:<24} {b['version']}" for b in result["bots"]) or "Nessun bot di libreria."
    if action == "sync":
        return "\n".join(f"{r['profile']:<24} {r['status']}" + (f"  {r['to']}" if r["status"] == "updated" else "")
                         for r in result["results"]) or "Nessun bot di libreria."
    if action in {"install", "update", "rollback"}:
        return f"{result['profile']}: versione {result['version']}. Vale dalla prossima conversazione."
    if action == "duplicate":
        return f"Creato il bot personale «{result['profile']}»."
    return "Fatto."


def execute(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    action = args.kb_action or "check"
    return action, _ACTIONS[action](args)


def cli_handler(args: argparse.Namespace) -> int:
    try:
        action, result = execute(args)
    except (KBError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False) if args.json else f"kb: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else _text(action, result))
    return 0


def slash_handler(raw: str) -> str:
    parser = _Parser(prog="/kb", add_help=False)
    setup_parser(parser)
    try:
        args = parser.parse_args(shlex.split(raw or ""))
        action, result = execute(args)
    except (KBError, OSError, ValueError) as exc:
        return f"KB: {exc}"
    return _text(action, result)
