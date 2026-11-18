#!/usr/bin/env python3
"""Health check for the Knowledge Manager wiki.

Standard library only, so the bot can run it with the Python that ships with Hermes.

    python3 wiki_lint.py <cartella Wiki> [--root <radice KB>] [--json]

Checks: frontmatter, broken wikilinks, pages missing from index.md, orphan pages, pages over the
size limit, source cards whose document changed (hash) or disappeared, and log rotation.
Exit 0 = clean (warnings allowed), 2 = errors, 1 = usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PAGE_DIRS = ("concetti", "entita", "confronti", "risposte")
REQUIRED = ("title", "created", "updated", "type", "tags", "sources")
TYPES = {"entita", "concetto", "confronto", "risposta"}
CONFIDENCE = {"alta", "media", "bassa"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
LOG_ENTRY = re.compile(r"^##\s+\[\d{4}-\d{2}-\d{2}\]", re.MULTILINE)


def _strip(value: str) -> str:
    return value.strip().strip('"').strip("'")


def _value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [_strip(item) for item in inner.split(",") if item.strip()] if inner else []
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    return _strip(raw)


def frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """``(frontmatter, body)`` with the small YAML subset a wiki page uses."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text
    data: dict[str, Any] = {}
    key = ""
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            key, raw = match.group(1), match.group(2)
            data[key] = _value(raw)
            continue
        item = re.match(r"^\s*-\s*(.+)$", line)
        if item and key:
            data.setdefault(key, [])
            if not isinstance(data[key], list):
                data[key] = []
            data[key].append(_strip(item.group(1)))
    return data, "\n".join(lines[end + 1:])


def digest(path: Path) -> str:
    stream = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            stream.update(chunk)
    return stream.hexdigest()


def page_key(path: Path, wiki: Path) -> str:
    return path.relative_to(wiki).with_suffix("").as_posix()


def matching_keys(target: str, keys: set[str]) -> set[str]:
    """The pages a ``[[link]]`` points at: exact path first, then a unique basename."""
    clean = target.strip().lstrip("./").removesuffix(".md").strip("/")
    if clean in keys:
        return {clean}
    base = clean.split("/")[-1]
    return {key for key in keys if key.split("/")[-1] == base}


def check(wiki: Path, root: Path, max_lines: int, max_log: int) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    pages: list[tuple[Path, dict[str, Any], str]] = []
    for folder in PAGE_DIRS:
        for path in sorted((wiki / folder).rglob("*.md")) if (wiki / folder).is_dir() else []:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            data, body = frontmatter(text)
            pages.append((path, data, body))

    keys = {page_key(path, wiki) for path, _data, _body in pages}

    for path, data, body in pages:
        rel = path.relative_to(wiki).as_posix()
        missing = [key for key in REQUIRED if key not in data]
        if missing:
            errors.append(f"{rel}: frontmatter incompleto ({', '.join(missing)})")
        if data.get("type") not in TYPES:
            errors.append(f"{rel}: type «{data.get('type')}» non valido")
        for field in ("created", "updated"):
            value = str(data.get(field) or "")
            if value and not DATE.fullmatch(value):
                errors.append(f"{rel}: {field} non è AAAA-MM-GG ({value})")
        if not isinstance(data.get("tags", []), list) or not data.get("tags"):
            warnings.append(f"{rel}: nessun tag")
        if data.get("confidence") and data["confidence"] not in CONFIDENCE:
            warnings.append(f"{rel}: confidence «{data['confidence']}» fuori scala")
        if len(body.splitlines()) > max_lines:
            warnings.append(f"{rel}: {len(body.splitlines())} righe (> {max_lines}), da dividere")
        for target in LINK.findall(body):
            if not matching_keys(target, keys):
                errors.append(f"{rel}: wikilink rotto [[{target}]]")

    index = wiki / "index.md"
    indexed = set()
    if index.is_file():
        for target in LINK.findall(index.read_text(encoding="utf-8-sig", errors="replace")):
            clean = target.strip().lstrip("./").removesuffix(".md").strip("/")
            indexed.add(clean)
            indexed.add(clean.split("/")[-1])
    for key in sorted(keys):
        if key not in indexed and key.split("/")[-1] not in indexed:
            warnings.append(f"{key}: non è in index.md")

    inbound = {key: 0 for key in keys}
    for path, _data, body in pages:
        rel = page_key(path, wiki)
        for target in LINK.findall(body):
            for key in matching_keys(target, keys):
                if key != rel:
                    inbound[key] += 1
    for key, count in sorted(inbound.items()):
        if count == 0:
            warnings.append(f"{key}: nessun collegamento in entrata (orfana)")

    sources = wiki / "fonti"
    for card in sorted(sources.glob("*.md")) if sources.is_dir() else []:
        data, _body = frontmatter(card.read_text(encoding="utf-8-sig", errors="replace"))
        if str(data.get("source_type") or "file") == "knowledge":
            continue  # the operator's file is removed once integrated: nothing to hash
        source = str(data.get("source") or "")
        expected = str(data.get("source_hash") or "")
        rel = card.relative_to(wiki).as_posix()
        if not source:
            warnings.append(f"{rel}: manca «source»")
            continue
        target = (root / source).resolve()
        if not target.is_file():
            errors.append(f"{rel}: la fonte {source} non esiste più")
            continue
        if not expected:
            warnings.append(f"{rel}: manca «source_hash»")
        elif digest(target) != expected:
            warnings.append(f"{rel}: la fonte {source} è cambiata, rileggila")

    log = wiki / "log.md"
    if log.is_file():
        entries = len(LOG_ENTRY.findall(log.read_text(encoding="utf-8-sig", errors="replace")))
        if entries > max_log:
            warnings.append(f"log.md: {entries} voci (> {max_log}), ruotalo in log-YYYY.md")

    return {"wiki": str(wiki), "pages": len(pages), "errors": errors, "warnings": warnings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controlla la wiki del Knowledge Manager.")
    parser.add_argument("wiki", help="cartella Wiki (quella con SCHEMA.md, index.md, log.md)")
    parser.add_argument("--root", help="radice della KB per risolvere i percorsi delle fonti "
                                       "(predefinita: la cartella che contiene Wiki)")
    parser.add_argument("--max-lines", type=int, default=200)
    parser.add_argument("--max-log", type=int, default=500)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    wiki = Path(args.wiki).expanduser().resolve()
    if not wiki.is_dir():
        print(f"wiki_lint: {wiki} non è una cartella", file=sys.stderr)
        return 1
    root = Path(args.root).expanduser().resolve() if args.root else wiki.parent
    report = check(wiki, root, args.max_lines, args.max_log)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Wiki: {report['wiki']} · {report['pages']} pagine")
        print(f"Errori: {len(report['errors'])} · Avvisi: {len(report['warnings'])}")
        for item in report["errors"]:
            print(f"✗ {item}")
        for item in report["warnings"]:
            print(f"! {item}")
        if not report["errors"] and not report["warnings"]:
            print("OK")
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
