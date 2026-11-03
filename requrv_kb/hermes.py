"""Hermes' public CLI, run by the same Python that runs this plugin (no shell, no PATH lookup).

Profile installs, updates and copies go through ``hermes profile ...``: the documented
surface, so the plugin keeps working when Hermes reorganises its internals.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from .paths import KBError, install_root

TIMEOUT_S = 300


def run(args: list[str], profile: Optional[str] = None) -> str:
    argv = [sys.executable, "-m", "hermes_cli.main"]
    if profile:
        argv += ["-p", profile]
    argv += args
    env = {**os.environ, "HERMES_HOME": str(install_root())}
    try:
        result = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=TIMEOUT_S, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise KBError("Hermes non ha risposto in tempo: riprova tra poco.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise KBError(f"Hermes ha rifiutato l'operazione: {detail[-1] if detail else 'errore sconosciuto'}")
    return result.stdout.strip()
