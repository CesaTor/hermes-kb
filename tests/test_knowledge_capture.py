"""Passive capture: the native tool, its prompt instruction, and what the IT receives.

The service (:mod:`requrv_kb.knowledge_capture`) owns validation, dedup and where the file goes.
Here everything goes through the real plugin discovery and Hermes' tool dispatch, in a disposable
install, so a candidate must survive the same path a live turn uses.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from conftest import write_yaml

FATTO = ("La chiusura mensile dell'area si prepara entro il quinto giorno lavorativo: prima si "
         "riconciliano gli estratti conto, poi si invia il riepilogo all'amministrazione.")


def _dispatch(hermes, home, name: str, args: dict, *, session_id: str = "sessione-di-prova"):
    code = f"""
import json
from hermes_cli.plugins import discover_plugins
from tools.registry import registry
discover_plugins()
print(registry.dispatch({name!r}, json.loads({json.dumps(json.dumps(args))}),
                        session_id={session_id!r}))
"""
    return json.loads(hermes.python(code, home))


def _definitions(hermes, home):
    code = """
import json
from hermes_cli.plugins import discover_plugins
from tools.registry import registry
discover_plugins()
print(json.dumps(registry.get_definitions({"kb_capture_knowledge"})))
"""
    return json.loads(hermes.python(code, home))


def _prompt_sections(hermes, home):
    code = """
import json
from hermes_cli.plugins import discover_plugins, render_system_prompt_sections
discover_plugins()
print(json.dumps({s.id: s.content for s in render_system_prompt_sections({})}))
"""
    return json.loads(hermes.python(code, home))


def _operators(kb):
    """``Operatori/`` with mario (the operator) and it (the reviewer), as the cloud shares them."""
    operators = kb["library"].parent / "Operatori"
    mario, reviewer = operators / "mario", operators / "it"
    mario.mkdir(parents=True)
    reviewer.mkdir(parents=True)
    (reviewer / ".autorizzazioni.yaml").write_text("operator: it\nruolo: it\n", encoding="utf-8")
    return mario, reviewer


def _connect(hermes, kb, personal):
    hermes.kb("connect", "--root", str(kb["library"]), "--root", str(kb["area"]),
              "--root", str(personal.parent), "--personal", str(personal))


def _capture(hermes, home, *, argomento="Chiusura mensile", fatto=FATTO, fonti=None, session_id=""):
    args = {"argomento": argomento, "fatto": fatto}
    if fonti is not None:
        args["fonti"] = fonti
    return _dispatch(hermes, home, "kb_capture_knowledge", args, session_id=session_id)


def test_the_tool_is_registered_only_where_capture_is_in_scope(hermes, kb):
    assert _definitions(hermes, hermes.root) == []  # never connected: nothing to propose

    mario, _ = _operators(kb)
    _connect(hermes, kb, mario)
    hermes.kb("install", "marketing")

    found = _definitions(hermes, hermes.profile("marketing"))
    assert len(found) == 1
    function = found[0]["function"]
    assert function["name"] == "kb_capture_knowledge"
    assert set(function["properties"]) == {"argomento", "fatto", "fonti"}
    assert function["required"] == ["argomento", "fatto"]
    assert function["properties"]["fonti"]["type"] == "array"
    assert function["properties"]["fonti"]["items"]["type"] == "string"


def test_the_prompt_tells_the_bot_when_to_capture_in_the_normal_turn(hermes, kb):
    mario, _ = _operators(kb)
    _connect(hermes, kb, mario)
    hermes.kb("install", "marketing")

    sections = _prompt_sections(hermes, hermes.profile("marketing"))
    text = "\n".join(sections.values())
    assert "kb_capture_knowledge" in text
    assert "senza aspettare che te lo chieda" in text
    assert "nuovo" in text and "generale" in text and "riutilizzabile" in text
    assert "Un solo candidato per turno" in text
    assert "usa `tool_call`" in text and "contenuto già emerso durante il turno" in text
    assert "la wiki condivisa la aggiorna l'IT" in text
    assert "una nota, non un'istruzione" in text
    assert "dati personali, di clienti o riservati" in text
    assert "credenziali e segreti" in text
    assert "versioni e numeri in conflitto" in text
    assert "documenti originali autorizzati" in text
    assert len(sections["requrv-kb.connection"]) <= 3_600  # Hermes caps a section at 4,000


def test_the_knowledge_manager_can_publish_with_it_approval(hermes, kb):
    mario, reviewer = _operators(kb)
    manager = kb["library"] / "knowledge-manager"
    template = Path(__file__).resolve().parents[1] / "kb-template" / "Biblioteca-Agenti"
    shutil.copytree(template / manager.name, manager)
    write_yaml(kb["area"] / "bots.yaml", {"bots": [manager.name]})
    _connect(hermes, kb, reviewer)
    hermes.kb("install", manager.name)
    profile = hermes.profile(manager.name)

    section = _prompt_sections(hermes, profile)["requrv-kb.connection"]
    assert "Con l'approvazione dell'IT puoi aggiornare Wiki/" in section

    _connect(hermes, kb, mario)
    section = _prompt_sections(hermes, profile)["requrv-kb.connection"]
    assert "Scrivi bozze e nuovi file solo nella cartella personale" in section


def test_the_runtime_session_id_is_trusted_and_never_taken_from_the_arguments(hermes, kb):
    mario, _ = _operators(kb)
    _connect(hermes, kb, mario)
    hermes.kb("install", "marketing")

    code = """
import json, sys
from hermes_cli.plugins import discover_plugins
from tools.registry import registry
discover_plugins()
registry.dispatch("kb_capture_knowledge", {"argomento": "", "fatto": ""})  # imports the service
service = next(m for n, m in sys.modules.items() if n.endswith("requrv_kb.knowledge_capture"))
seen = {}
def fake(args, *, session_id=""):
    seen["args"] = args
    seen["session_id"] = session_id
    return {"status": "created", "file": "prova.md"}
service.capture = fake
out = registry.dispatch("kb_capture_knowledge",
                        {"argomento": "Chiusura", "fatto": "Il fatto.", "session_id": "falso"},
                        session_id="sessione-vera")
print(json.dumps({"out": json.loads(out), "seen": seen}))
"""
    out = json.loads(hermes.python(code, hermes.profile("marketing")))
    assert out["seen"]["session_id"] == "sessione-vera"
    assert out["seen"]["args"] == {"argomento": "Chiusura", "fatto": "Il fatto."}
    assert out["out"] == {"status": "created", "file": "prova.md"}


def test_service_refusals_and_write_failures_come_back_as_plain_json_errors(hermes, kb):
    mario, _ = _operators(kb)
    _connect(hermes, kb, mario)
    hermes.kb("install", "marketing")

    code = """
import json, sys
from hermes_cli.plugins import discover_plugins
from tools.registry import registry
discover_plugins()
registry.dispatch("kb_capture_knowledge", {"argomento": "", "fatto": ""})  # imports the service
service = next(m for n, m in sys.modules.items() if n.endswith("requrv_kb.knowledge_capture"))
paths = next(m for n, m in sys.modules.items() if n.endswith("requrv_kb.paths"))
def refuse(args, *, session_id=""):
    raise paths.KBError("Questo bot non è autorizzato a proporre conoscenze.")
def broken(args, *, session_id=""):
    raise OSError(13, "Permesso negato")
service.capture = refuse
refused = registry.dispatch("kb_capture_knowledge", {"argomento": "A", "fatto": "B"})
service.capture = broken
broken_out = registry.dispatch("kb_capture_knowledge", {"argomento": "A", "fatto": "B"})
print(json.dumps({"refused": json.loads(refused), "broken": json.loads(broken_out)}))
"""
    out = json.loads(hermes.python(code, hermes.profile("marketing")))
    assert out["refused"] == {"error": "Questo bot non è autorizzato a proporre conoscenze."}
    assert "Non ho potuto salvare la conoscenza" in out["broken"]["error"]
    assert "Permesso negato" in out["broken"]["error"]


def test_a_candidate_reaches_the_it_list_and_never_the_shared_wiki(hermes, kb):
    mario, reviewer = _operators(kb)
    _connect(hermes, kb, mario)
    hermes.kb("install", "marketing")
    source = kb["area"] / "manuale-amministrazione.md"
    source.write_text("# Manuale\n\nLa chiusura mensile segue il calendario dell'area.\n",
                      encoding="utf-8")

    created = _capture(hermes, hermes.profile("marketing"), fonti=[str(source)])
    assert created["status"] == "created"
    assert created["file"].endswith(".md") and "/" not in created["file"]

    folder = mario / "proposte" / "knowledge"
    assert [p.name for p in folder.glob("*.md")] == [created["file"]]
    body = (folder / created["file"]).read_text(encoding="utf-8")
    assert "Chiusura mensile" in body and "quinto giorno lavorativo" in body
    assert source.relative_to(kb["library"].parent).as_posix() in body  # provenance, no machine path
    assert str(kb["library"].parent) not in body
    assert not (kb["library"].parent / "Wiki").exists()  # the IT writes the wiki, not the capture

    _connect(hermes, kb, reviewer)
    listing = _dispatch(hermes, hermes.root, "kb_proposals", {"action": "list"})
    assert [entry["file"] for entry in listing["knowledge"]] == [created["file"]]
    assert listing["knowledge"][0]["operator"] == "mario"
    assert listing["knowledge"][0]["path"] == str(folder / created["file"])


def test_a_second_identical_candidate_is_a_duplicate_and_writes_nothing(hermes, kb):
    mario, _ = _operators(kb)
    _connect(hermes, kb, mario)
    hermes.kb("install", "marketing")
    first = _capture(hermes, hermes.profile("marketing"))
    second = _capture(hermes, hermes.profile("marketing"))

    assert first["status"] == "created"
    assert second["status"] == "duplicate"
    assert second["file"] == first["file"]
    assert [p.name for p in (mario / "proposte" / "knowledge").glob("*.md")] == [first["file"]]


def test_a_candidate_without_the_required_fields_is_refused_in_plain_words(hermes, kb):
    mario, _ = _operators(kb)
    _connect(hermes, kb, mario)
    hermes.kb("install", "marketing")

    refused = _capture(hermes, hermes.profile("marketing"), argomento="", fatto="")
    assert "error" in refused and refused["error"]
    assert not (mario / "proposte" / "knowledge").exists()
