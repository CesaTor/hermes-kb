"""The Knowledge Manager's deterministic wiki lint: broken links, index, orphans, source drift."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] / "kb-template" / "Biblioteca-Agenti" / "knowledge-manager"
          / "skills" / "llm-wiki" / "scripts" / "wiki_lint.py")


def _page(title: str, kind: str, body: str, sources: str = "[]") -> str:
    return (f"---\ntitle: {title}\ncreated: 2026-11-18\nupdated: 2026-11-18\n"
            f"type: {kind}\ntags: [strategia]\nsources: {sources}\n---\n{body}\n")


def _wiki(tmp: Path, *, dirty: bool = False) -> Path:
    wiki = tmp / "Wiki"
    (wiki / "concetti").mkdir(parents=True)
    (wiki / "entita").mkdir()
    (wiki / "fonti").mkdir()
    (wiki / "SCHEMA.md").write_text("# Schema\n", encoding="utf-8")
    (wiki / "log.md").write_text("## [2026-11-18] create | Wiki inizializzata\n", encoding="utf-8")
    (wiki / "concetti" / "preventivo.md").write_text(
        _page("Preventivo", "concetto", "Vedi [[entita/cliente]].", "[01-Strategia/documenti/x_v1.0.md]"),
        encoding="utf-8")
    (wiki / "entita" / "cliente.md").write_text(
        _page("Cliente", "entita", "Vedi [[concetti/preventivo]]."), encoding="utf-8")
    index = wiki / "index.md"
    index.write_text("# Indice\n\n## Concetti\n- [[concetti/preventivo]] — il ciclo\n\n"
                     "## Entità\n- [[entita/cliente]] — chi compra\n", encoding="utf-8")
    if dirty:
        (wiki / "concetti" / "rotto.md").write_text(
            "---\ntitle: Rotto\ntype: boh\ntags: []\n---\n[[non-esiste]]\n" + "riga\n" * 260,
            encoding="utf-8")
        (tmp / "documenti").mkdir()
        (tmp / "documenti" / "x_v1.0.md").write_text("cambiato\n", encoding="utf-8")
        (wiki / "fonti" / "x.md").write_text(
            "---\ntitle: X\nsource_type: file\nsource: documenti/x_v1.0.md\nsource_hash: deadbeef\n---\n",
            encoding="utf-8")
        (wiki / "fonti" / "sparita.md").write_text(
            "---\ntitle: Sparita\nsource_type: file\nsource: documenti/non-ce.md\n---\n",
            encoding="utf-8")
    return wiki


def _run(wiki: Path) -> tuple[int, dict]:
    result = subprocess.run([sys.executable, str(SCRIPT), str(wiki), "--json"],
                            capture_output=True, text=True, timeout=60)
    return result.returncode, json.loads(result.stdout) if result.stdout.strip() else {}


def test_a_healthy_wiki_passes(tmp_path):
    code, report = _run(_wiki(tmp_path))
    assert code == 0 and report["errors"] == [] and report["warnings"] == []
    assert report["pages"] == 2


def test_a_dirty_wiki_reports_errors_and_warnings(tmp_path):
    code, report = _run(_wiki(tmp_path, dirty=True))
    assert code == 2
    errors = " | ".join(report["errors"])
    warnings = " | ".join(report["warnings"])
    assert "wikilink rotto [[non-esiste]]" in errors
    assert "frontmatter incompleto" in errors and "type «boh»" in errors
    assert "documenti/non-ce.md non esiste più" in errors
    assert "non è in index.md" in warnings
    assert "orfana" in warnings
    assert "è cambiata" in warnings
    assert "righe" in warnings
