"""ReQurv KB plugin entry point: CLI and slash commands, the library hooks, prompt sections, the setup skill.

Imports stay relative: one gateway process serves several profiles, each with its own copy of this
plugin (possibly at different versions), and Hermes loads each copy under its own module name. A
shared top-level name would hand every profile whichever copy was imported first.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def register(ctx):
    from .requrv_kb import autosync, cli, locks, prompt, watchdog

    ctx.register_cli_command("kb", "Collega la KB aziendale e gestisci i bot di libreria",
                             cli.setup_parser, cli.cli_handler)
    ctx.register_command("kb", cli.slash_handler,
                         description="KB aziendale: collega, elenca, installa e aggiorna i bot",
                         args_hint="connect|check|list|install|update|sync|reconcile|rollback|duplicate|status",
                         argument_mode="mixed")
    ctx.register_hook("pre_tool_call", locks.pre_tool_call)
    ctx.register_hook("on_session_start", autosync.on_session_start)
    watchdog.start()
    ctx.on_unload(watchdog.stop)
    ctx.register_system_prompt_section("requrv-kb.connection", prompt.section)
    ctx.register_system_prompt_section("requrv-kb.proposals", prompt.proposals_section)
    ctx.register_skill("setup", _ROOT / "skills" / "setup" / "SKILL.md")
