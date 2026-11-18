"""ReQurv KB plugin entry point: CLI and slash commands, the library hooks, prompt sections, the setup skill.

Imports stay relative: one gateway process serves several profiles, each with its own copy of this
plugin (possibly at different versions), and Hermes loads each copy under its own module name. A
shared top-level name would hand every profile whichever copy was imported first.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent

_KB_PERSONAL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["list", "decide"],
                   "description": "list the operator's own versions waiting for a decision, or decide one"},
        "kind": {"type": "string", "enum": ["soul", "skill"]},
        "name": {"type": "string", "description": "skill name, when kind is skill"},
        "choice": {"type": "string", "enum": ["keep", "take"],
                   "description": "keep = the operator's version, take = the library's new one"},
    },
    "required": ["action"],
}

_KB_PROPOSALS_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["list", "show", "accept", "reject"]},
        "operator": {"type": "string", "description": "operator folder name (Operatori/<nome>)"},
        "bot": {"type": "string", "description": "bot the proposal belongs to"},
        "confirm": {"type": "boolean",
                    "description": "accept writes into the package and bumps its version: ask the user first"},
        "reason": {"type": "string", "description": "why a proposal is rejected"},
    },
    "required": ["action"],
}

_KB_UPDATES_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["list", "apply"],
                   "description": "list what the library offers, or install/update it on this computer"},
    },
    "required": ["action"],
}

_KB_CAPTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "argomento": {"type": "string",
                      "description": "titolo breve e generale della conoscenza (una riga)"},
        "fatto": {"type": "string",
                  "description": "fatto o processo nuovo, generale e riutilizzabile, con il contesto che lo rende verificabile"},
        "fonti": {"type": "array", "items": {"type": "string"},
                  "description": "percorsi dei documenti originali autorizzati letti; se non ce ne sono, la provenienza dal contesto del compito"},
    },
    "required": ["argomento", "fatto"],
}


def _connection_or_error():
    from .requrv_kb import connection as kb_connection
    from .requrv_kb.paths import KBError

    conn = kb_connection.load()
    if conn is None:
        raise KBError("Questo computer non è ancora collegato alla KB.")
    return conn


def _it_available() -> bool:
    """The IT tools exist only for an operator whose .autorizzazioni.yaml says ``ruolo: it``."""
    try:
        from .requrv_kb import authz

        conn = _connection_or_error()
        return authz.is_it(conn)
    except Exception:
        return False


def _capture_available() -> bool:
    """Passive capture only where the service says it is in scope (connected, authorized bot)."""
    try:
        from .requrv_kb import knowledge_capture

        return bool(knowledge_capture.available())
    except Exception:
        return False


def _kb_proposals(args: dict[str, Any], **_: Any) -> str:
    """The IT review loop over the operators' proposals."""
    from .requrv_kb import it
    from .requrv_kb.paths import KBError

    try:
        conn = _connection_or_error()
        action = str(args.get("action") or "list").strip().lower()
        if action == "list":
            return json.dumps({"proposals": it.proposals(conn), "knowledge": it.knowledge(conn)},
                              ensure_ascii=False)
        operator = str(args.get("operator") or "").strip()
        bot = str(args.get("bot") or "").strip()
        if not operator or not bot:
            raise KBError("Indica --operator e --bot.")
        if action == "show":
            result = it.show(conn, operator, bot)
        elif action == "accept":
            result = it.accept(conn, operator, bot, confirm=bool(args.get("confirm")))
        elif action == "reject":
            result = it.reject(conn, operator, bot, str(args.get("reason") or ""))
        else:
            raise KBError("Azione sconosciuta: usa list, show, accept o reject.")
        return json.dumps(result, ensure_ascii=False)
    except KBError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def _kb_updates(args: dict[str, Any], **_: Any) -> str:
    """What the library offers, and applying it on this computer."""
    from .requrv_kb import it, library
    from .requrv_kb.paths import KBError

    try:
        conn = _connection_or_error()
        action = str(args.get("action") or "list").strip().lower()
        offered = it.updates(conn)
        if action == "apply":
            return json.dumps({"updates": offered, "results": library.reconcile()}, ensure_ascii=False)
        return json.dumps({"updates": offered}, ensure_ascii=False)
    except KBError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def _kb_personal(args: dict[str, Any], **_: Any) -> str:
    """The operator's own SOUL/skill versions a new release collided with."""
    from .requrv_kb import personal
    from .requrv_kb.paths import KBError, active_profile

    action = str(args.get("action") or "list").strip().lower()
    try:
        if action == "list":
            return json.dumps({"pending": personal.pending(active_profile())}, ensure_ascii=False)
        if action != "decide":
            raise KBError("Azione sconosciuta: usa «list» o «decide».")
        conn = _connection_or_error()
        kind = str(args.get("kind") or "").strip().lower()
        if kind not in {"soul", "skill"}:
            raise KBError("Indica kind «soul» o «skill».")
        name = str(args.get("name") or "").strip()
        if kind == "skill" and not name:
            raise KBError("Indica il nome della skill.")
        decided = personal.decide(active_profile(), conn, kind, name, str(args.get("choice") or ""))
        return json.dumps({"decided": decided}, ensure_ascii=False)
    except KBError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def _kb_capture_knowledge(args: dict[str, Any], *, session_id: str = "", **_: Any) -> str:
    """One passive knowledge candidate, written by the service into the operator's proposals."""
    from .requrv_kb import knowledge_capture
    from .requrv_kb.paths import KBError

    payload = dict(args or {})
    payload.pop("session_id", None)  # the only session id is the one Hermes passes at runtime
    try:
        result = knowledge_capture.capture(payload, session_id=str(session_id or ""))
        return json.dumps(result, ensure_ascii=False)
    except KBError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    except OSError as exc:
        return json.dumps({"error": f"Non ho potuto salvare la conoscenza: {exc.strerror or exc}"},
                          ensure_ascii=False)


def register(ctx):
    from .requrv_kb import autosync, cli, locks, mirror, prompt

    ctx.register_cli_command("kb", "Collega la KB aziendale e gestisci i bot di libreria",
                             cli.setup_parser, cli.cli_handler)
    ctx.register_command("kb", cli.slash_handler,
                         description="KB aziendale: collega, elenca, installa e aggiorna i bot",
                         args_hint="connect|check|list|status|install|update|sync|reconcile|rollback|duplicate|resolve",
                         argument_mode="mixed")
    ctx.register_hook("pre_tool_call", locks.pre_tool_call)
    ctx.register_hook("post_tool_call", mirror.on_tool_call)
    ctx.register_hook("on_skill_lifecycle", mirror.on_skill_lifecycle)
    ctx.register_hook("on_session_start", autosync.on_session_start)
    ctx.register_tool(name="kb_personal", toolset="kb", schema=_KB_PERSONAL_SCHEMA,
                      handler=_kb_personal, emoji="🔁",
                      description=("Versioni personali del bot di libreria: elenca quelle in attesa di una "
                                   "decisione e registra la risposta dell'operatore (keep/take)."))
    ctx.register_tool(name="kb_proposals", toolset="kb", schema=_KB_PROPOSALS_SCHEMA,
                      handler=_kb_proposals, emoji="📝", check_fn=_it_available,
                      description=("Revisione IT: elenca le proposte degli operatori (SOUL, skill, knowledge), "
                                   "mostra le differenze con il pacchetto e accetta o rifiuta una modifica."))
    ctx.register_tool(name="kb_updates", toolset="kb", schema=_KB_UPDATES_SCHEMA,
                      handler=_kb_updates, emoji="🔄", check_fn=_it_available,
                      description=("Revisione IT: cosa offre la libreria che questo computer non ha ancora, "
                                   "e applicazione degli aggiornamenti."))
    ctx.register_tool(name="kb_capture_knowledge", toolset="kb", schema=_KB_CAPTURE_SCHEMA,
                      handler=_kb_capture_knowledge, emoji="📚", check_fn=_capture_available,
                      description=("Propone una conoscenza nuova e riutilizzabile (argomento, fatto, fonti) "
                                   "per la revisione IT; crea solo una bozza nella cartella personale, "
                                   "mai nella wiki condivisa."))
    ctx.register_system_prompt_section("requrv-kb.connection", prompt.section)
    ctx.register_system_prompt_section("requrv-kb.personal", prompt.personal_section)
    ctx.register_skill("setup", _ROOT / "skills" / "setup" / "SKILL.md")
    ctx.register_skill("revisione-proposte", _ROOT / "skills" / "it" / "SKILL.md")
