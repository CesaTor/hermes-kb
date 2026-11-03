"""ReQurv KB plugin entry point: CLI and slash commands, the library lock hook, the setup skill."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _package():
    # One copy of the service for both halves: dashboard/plugin_api.py imports it the same way.
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import requrv_kb.autosync
    import requrv_kb.cli
    import requrv_kb.locks
    import requrv_kb.prompt

    return requrv_kb


def register(ctx):
    kb = _package()
    ctx.register_cli_command("kb", "Collega la KB aziendale e gestisci i bot di libreria",
                             kb.cli.setup_parser, kb.cli.cli_handler)
    ctx.register_command("kb", kb.cli.slash_handler,
                         description="KB aziendale: collega, elenca, installa e aggiorna i bot",
                         args_hint="connect|check|list|install|update|sync|rollback|duplicate|status",
                         argument_mode="mixed")
    ctx.register_hook("pre_tool_call", kb.locks.pre_tool_call)
    ctx.register_hook("on_session_start", kb.autosync.on_session_start)
    ctx.register_system_prompt_section("requrv-kb.connection", kb.prompt.section)
    ctx.register_system_prompt_section("requrv-kb.proposals", kb.prompt.proposals_section)
    ctx.register_skill("setup", _ROOT / "skills" / "setup" / "SKILL.md")
