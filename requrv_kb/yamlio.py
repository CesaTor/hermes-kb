"""YAML reads and comment-preserving config writes, with ruamel (a Hermes core dependency)."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .paths import KBError, atomic_write_text


def _round_trip() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml


def safe_load(path: Path) -> Any:
    try:
        return YAML(typ="safe").load(path.read_text(encoding="utf-8-sig"))
    except (OSError, YAMLError, UnicodeError) as exc:
        raise KBError(f"Non riesco a leggere {path.name}: il file non è YAML valido.") from exc


def load_config(path: Path) -> Any:
    """A profile's ``config.yaml`` as a round-trip mapping (empty when absent)."""
    if not path.is_file():
        return _round_trip().load("{}")
    try:
        data = _round_trip().load(path.read_text(encoding="utf-8-sig"))
    except (OSError, YAMLError, UnicodeError) as exc:
        raise KBError(f"Non riesco a leggere {path}: correggi il file e riprova.") from exc
    if data is None:
        return _round_trip().load("{}")
    if not isinstance(data, dict):
        raise KBError(f"{path} non contiene una mappa di impostazioni.")
    return data


def write_config(path: Path, data: Any) -> None:
    stream = StringIO()
    _round_trip().dump(data, stream)
    atomic_write_text(path, stream.getvalue())


def plain(value: Any) -> Any:
    """A deep copy as plain dict/list/scalars, for comparisons and JSON."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value
