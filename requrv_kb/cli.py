"""``hermes kb ...`` and ``/kb ...``: one parser, one service, readable or JSON output."""

from __future__ import annotations

import argparse
import json
import shlex
from typing import Any, Callable

from . import connection as kb_connection
from . import library, personal
from .paths import KBError, active_profile


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
    sub.add_parser("reconcile", help="Installa i bot abilitati che mancano e aggiorna gli altri (come il controllo automatico)")
    for action, text in (("install", "Installa un bot"), ("update", "Aggiorna un bot"),
                         ("rollback", "Torna alla versione precedente di un bot")):
        sub.add_parser(action, help=text).add_argument("bot")
    dup = sub.add_parser("duplicate", help="Copia un bot in un bot personale modificabile")
    dup.add_argument("bot")
    dup.add_argument("name", help="Nome della copia")
    resolve = sub.add_parser("resolve", help="Tieni la tua versione o prendi quella nuova della libreria")
    resolve.add_argument("--kind", choices=["skill"], required=True)
    resolve.add_argument("--name", default="", help="Nome della skill")
    resolve.add_argument("--choice", choices=["keep", "take"], required=True,
                         help="keep = tengo la mia, take = prendo la nuova")
    review = sub.add_parser("it", help="Revisione IT: proposte degli operatori e aggiornamenti")
    review_sub = review.add_subparsers(dest="it_action", metavar="AZIONE")
    review_sub.add_parser("list", help="Elenca le proposte in attesa")
    review_sub.add_parser("knowledge", help="Elenca le conoscenze raccolte dagli operatori")
    show = review_sub.add_parser("show", help="Mostra le differenze con il pacchetto")
    accept = review_sub.add_parser("accept", help="Integra una proposta nel pacchetto e alza la versione")
    reject = review_sub.add_parser("reject", help="Archivia una proposta con un motivo")
    for command in (show, accept, reject):
        command.add_argument("--operator", required=True)
        command.add_argument("--bot", required=True)
    accept.add_argument("--yes", action="store_true", help="Conferma la scrittura nel pacchetto")
    reject.add_argument("--reason", default="", help="Perché la proposta non entra")
    updates = sub.add_parser("updates", help="Cosa offre la libreria e applicazione degli aggiornamenti")
    updates.add_argument("--apply", action="store_true", help="Installa e aggiorna adesso")
    memory = sub.add_parser("memory", help="Memoria Holographic opzionale per i bot di libreria")
    memory.add_argument("action", nargs="?", choices=["status", "enable", "disable"], default="status")
    memory.add_argument("--all", action="store_true", help="Tutti i bot di libreria di questo computer")
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


def _resolve(a) -> dict[str, Any]:
    conn = kb_connection.load()
    if conn is None:
        raise KBError("Questo computer non è collegato alla KB.")
    if a.kind == "skill" and not a.name:
        raise KBError("Indica il nome della skill: --kind skill --name <nome>.")
    return personal.decide(active_profile(), conn, a.kind, a.name, a.choice)


def _require_connection():
    conn = kb_connection.load()
    if conn is None:
        raise KBError("Questo computer non è collegato alla KB.")
    return conn


def _review(a) -> dict[str, Any]:
    from . import it

    conn = _require_connection()
    it.require_it(conn)
    action = a.it_action or "list"
    if action == "list":
        return {"proposals": it.proposals(conn), "knowledge": it.knowledge(conn)}
    if action == "knowledge":
        return {"knowledge": it.knowledge(conn)}
    if action == "show":
        return it.show(conn, a.operator, a.bot)
    if action == "accept":
        return it.accept(conn, a.operator, a.bot, confirm=bool(a.yes))
    if action == "reject":
        return it.reject(conn, a.operator, a.bot, a.reason)
    raise KBError(f"Azione sconosciuta: {action}.")


def _updates(a) -> dict[str, Any]:
    from . import it

    conn = _require_connection()
    offered = it.updates(conn)
    if not a.apply:
        return {"updates": offered}
    return {"updates": offered, "results": library.reconcile()}


def _memory(a) -> dict[str, Any]:
    from . import memory_provider

    conn = _require_connection()
    action = a.action or "status"
    if action == "status":
        return {"provider": conn.memory_provider,
                "bots": [memory_provider.status(p) for p in _library_profiles()]}
    if not a.all:
        raise KBError("Indica --all: la scelta Holographic vale per tutti i bot di libreria.")
    if action == "enable":
        conn = kb_connection.set_memory_provider(memory_provider.PROVIDER)
        return {"provider": conn.memory_provider, "results": memory_provider.ensure_all()}
    kb_connection.set_memory_provider("")
    return {"provider": "", "results": memory_provider.disable_all()}


def _library_profiles() -> list:
    from . import ledger
    from .paths import named_profiles

    return [p for p in named_profiles() if ledger.read(p) is not None]


_ACTIONS: dict[str, Callable[[Any], Any]] = {
    "connect": _connect,
    "disconnect": lambda a: (kb_connection.disconnect(), {"disconnected": True})[1],
    "check": _check,
    "list": lambda a: library.catalog(),
    "status": lambda a: {"bots": library.status()},
    "sync": lambda a: {"results": library.sync()},
    "reconcile": lambda a: {"results": library.reconcile()},
    "install": lambda a: library.install(a.bot),
    "update": lambda a: library.update(a.bot),
    "rollback": lambda a: library.rollback(a.bot),
    "duplicate": lambda a: library.duplicate(a.bot, a.name),
    "resolve": _resolve,
    "it": _review,
    "updates": _updates,
    "memory": _memory,
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
        return "\n".join(f"{b['profile']:<24} {b['version']}"
                         + (f"  ({b['pending']} versioni tue da decidere)" if b.get("pending") else "")
                         for b in result["bots"]) or "Nessun bot di libreria."
    if action == "sync":
        return "\n".join(f"{r['profile']:<24} {r['status']}" + (f"  {r['to']}" if r["status"] == "updated" else "")
                         for r in result["results"]) or "Nessun bot di libreria."
    if action == "reconcile":
        return "\n".join(f"{r['profile']:<24} {r['action']}" + (f"  {r['to']}" if r["action"] in {"installed", "updated"} else "")
                         + (f"  {r['error']}" if r.get("error") else "") for r in result["results"]) or "Nessun bot di libreria."
    if action in {"install", "update", "rollback"}:
        return f"{result['profile']}: versione {result['version']}. Vale dalla prossima conversazione."
    if action == "duplicate":
        return f"Creato il bot personale «{result['profile']}»."
    if action == "resolve":
        if result["choice"] == "keep":
            return (f"Tengo la tua versione della skill «{result['name']}». "
                    "Vale dalla prossima conversazione.")
        return (f"Prendo la nuova versione della skill «{result['name']}»; la tua copia è stata "
                "rimossa dalle proposte.")
    if action == "it":
        return _review_text(result)
    if action == "updates":
        return _updates_text(result)
    if action == "memory":
        if "bots" in result:
            rows = [f"{b['profile']:<24} plugin {'sì' if b['plugin'] else 'no':<3} "
                    f"provider {'sì' if b['configured'] else 'no'}" for b in result["bots"]]
            return f"Provider aziendale: {result['provider'] or 'built-in'}\n" + "\n".join(rows)
        rows = [f"{r['profile']:<24} {'ok' if not r.get('error') else r['error']}" for r in result["results"]]
        return f"Provider aziendale: {result['provider'] or 'built-in'}\n" + "\n".join(rows)
    return "Fatto."


def _review_text(result: dict[str, Any]) -> str:
    if "proposals" in result:
        rows = [f"{p['operator']:<14} {p['bot']:<22} base {p['base_version'] or '—':<8} "
                f"{', '.join(p['files']) or '—'}" for p in result["proposals"]]
        knowledge = len(result.get("knowledge") or [])
        return ("\n".join(rows) or "Nessuna proposta in attesa.") + \
               (f"\n{knowledge} conoscenze raccolte in proposte/knowledge/." if knowledge else "")
    if "knowledge" in result:
        rows = [f"{k['operator']:<14} {k['file']}" for k in result["knowledge"]]
        return "\n".join(rows) or "Nessuna conoscenza raccolta."
    if "files" in result:
        parts = [f"### {name}\n{diff or '(nessuna differenza leggibile)'}"
                 for name, diff in (result["files"] or {}).items()]
        return "\n\n".join(parts) or "Nessun file da confrontare."
    if result.get("confirm_required"):
        plan = result["plan"]
        text = (f"Pronto a integrare {len(plan['files'])} file di «{plan['bot']}» ({plan['operator']}) "
                f"e a portare la versione da {plan['from_version']} a {plan['to_version']}.")
        if plan.get("stale"):
            text += (f"\nAttenzione: la proposta parte dalla {plan['base_version']}, "
                     f"il pacchetto è alla {plan['from_version']}: potresti sovrascrivere modifiche successive.")
        return text + " Rilancia con --yes per confermare."
    if "accepted" in result:
        plan = result["accepted"]
        return (f"Integrata la proposta di «{plan['operator']}» per «{plan['bot']}»: "
                f"versione {plan['from_version']} → {plan['to_version']}.")
    if "rejected" in result:
        rejected = result["rejected"]
        return f"Proposta archiviata in {rejected['archived_at']} con il motivo indicato."
    return "Fatto."


def _updates_text(result: dict[str, Any]) -> str:
    rows = [f"{u['bot']:<24} {u['status']:<8} {u['version']}"
            + (f" (installata {u['installed_version']})" if u.get("installed_version") else "")
            for u in result["updates"]]
    text = "\n".join(rows) or "Nessun aggiornamento disponibile."
    if "results" in result:
        done = [f"  {r['bot']}: {r['action']}" for r in result["results"]]
        text += "\nApplicati:\n" + ("\n".join(done) if done else "  nessuna modifica.")
    return text


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
