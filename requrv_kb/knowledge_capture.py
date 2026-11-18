"""Passive knowledge capture: a candidate Markdown file in the operator's proposals folder.

When a normal conversation teaches the bot something worth keeping, it calls this service with a
short topic, a self-contained fact and, optionally, the files the fact comes from. Nothing is
published: the only knowledge file written is in ``Operatori/<nome>/proposte/knowledge/`` (see
:func:`mirror.knowledge_dir`), one ``AAAAMMGG-HHMMSS-<slug>.md`` per item, as the Knowledge Manager
and the ``knowledge-ingest`` skill expect. The IT integrates the fact into the wiki or an area
document and then deletes the file; deleting is the signal that it was integrated, not approving it.

The model supplies only the three arguments. Provenance — author, bot and session — comes from the
running profile and connection, never from a model-chosen path or field: the target folder, the
author and the bot cannot be selected by the caller, and the transcript is never stored.

Safety is intentionally narrow and explicit:

* input is bounded, control/format characters and Markdown frontmatter/code scaffolding are refused;
* source files must exist, stay inside the connected KB roots, and not be hidden, personal
  (``Operatori/``), restricted (``Riservato/``) or secret-key material; symlinks are resolved before
  the check, so one cannot escape a shared root;
* Hermes' secret redaction runs with ``force=True`` and any change means the capture is refused.
  This catches straightforward leaks (API keys, passwords, connection strings). It is not a PII
  detector and does not claim to catch every personal datum: the operator and the IT remain
  responsible for what a proposal contains.

Dedup is by the normalized fact (Unicode compatibility form, case-folded, punctuation and spacing
collapsed), stored as a hash. The key is the fact, not the topic or the bot: the proposals folder
belongs to the operator, and a second bot describing the same thing should not add a second file.
Two places are consulted: the candidate files currently in the shared
``proposte/knowledge/`` folder, so a second device that received them also sees the duplicate, and a
small local index under the plugin data folder. The local index is what keeps a fact from being
proposed again after the IT **deleted** the file it integrated. The trade-off is deliberate: a device
that never saw the deleted file can propose the same fact again, and a local index cannot know what
was never synchronised to it. On one computer the folder check and the write are serialized across
Hermes processes by a lock in the plugin's local data folder, so two bots finishing a turn together
produce one candidate. Best effort is the honest guarantee here; the IT's dedup in the wiki remains
the final one.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import logging
import os
import re
import tempfile
import threading
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from .cloud_files import is_online_only
from .paths import KBError

logger = logging.getLogger(__name__)

MAX_ARGOMENTO = 120
MAX_FATTO = 4_000
MAX_FONTI = 20
MAX_FONTE = 1_024
MAX_SESSION_ID = 200
MAX_FACTS = 2_000
MAX_SCAN_BYTES = 64_000
_MAX_COLLISION = 20
_ALLOWED_ARGS = frozenset({"argomento", "fatto", "fonti"})
_SENSITIVE_NAMES = frozenset({"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"})
_TRANSCRIPT_LINE = re.compile(
    r"^\s*(?:utente|assistente|user|assistant|human|system|sistema)\s*:", re.IGNORECASE | re.MULTILINE)
_FRONTMATTER_LINE = re.compile(r"^\s*(?:---+|\.\.\.)\s*$", re.MULTILINE)
_HEADING = re.compile(r"^\s*#{1,6}\s")
_URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_LOCK = threading.Lock()
_LOCK_TIMEOUT = 10.0


@contextlib.contextmanager
def _process_lock() -> Iterator[None]:
    """Serialize the dedup check and the write across Hermes processes on this computer.

    A lock file in the plugin's local data folder is enough: two profiles share the install root,
    and two captures racing on the same synced folder on the same machine take the same file.
    POSIX uses ``flock``; Windows uses ``msvcrt.locking``. A crash releases the lock with the
    process, and a machine that cannot create the file keeps the previous best-effort behaviour
    instead of blocking the capture.
    """
    from .paths import data_dir

    try:
        directory = data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        stream = (directory / "knowledge-capture.lock").open("a+b")
    except OSError:
        logger.debug("requrv-kb: cattura senza lock tra processi", exc_info=True)
        yield
        return

    acquired = False
    try:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + _LOCK_TIMEOUT
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    logger.debug("requrv-kb: lock di cattura non ottenuto entro il tempo previsto")
                    break
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        stream.close()


# --- availability -------------------------------------------------------------------------------


def available() -> bool:
    """Whether this bot may propose knowledge right now.

    A capture needs the saved connection, an active profile the library installed (its ownership
    ledger), a bot the readable areas still list in ``bots.yaml`` and a bot the operator's
    ``.autorizzazioni.yaml`` still permits. Every failure is a quiet ``False``: the tool simply is
    not offered, and :func:`capture` explains the reason if called anyway.
    """
    try:
        _context()
        return True
    except Exception:  # availability must never break registration or a session
        return False


def _context() -> tuple[Any, Path, str]:
    """``(connection, active profile, bot)``, or a :class:`KBError` saying why capture is closed."""
    from . import authz, ledger, library
    from . import connection as kb_connection
    from .paths import active_profile

    conn = kb_connection.load()
    if conn is None:
        raise KBError("Questo computer non è ancora collegato alla KB: la cattura non è disponibile.")
    profile = active_profile()
    record = ledger.read(profile)
    if record is None:
        raise KBError("Questo bot non è un bot della libreria: la cattura è riservata ai bot "
                      "installati dalla libreria.")
    bot = str(record.get("bot") or profile.name)
    lists = library.read_allowlists(conn)
    if not (lists["wildcard"] or bot in lists["allowed"]):
        raise KBError(f"Il bot «{bot}» non è più tra quelli abilitati dalle aree della KB "
                      "(bots.yaml): chiedi all'IT, oppure non proporre questa conoscenza.")
    if not authz.permits(conn, bot):
        raise KBError(authz.refusal(bot))
    return conn, profile, bot


# --- input validation ---------------------------------------------------------------------------


def _clean(value: Any, label: str, *, limit: int, multiline: bool) -> str:
    if not isinstance(value, str):
        raise KBError(f"Il campo «{label}» deve essere un testo.")
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise KBError(f"Il campo «{label}» è vuoto.")
    if len(text) > limit:
        raise KBError(f"Il campo «{label}» supera i {limit} caratteri: accorcialo.")
    if not multiline and "\n" in text:
        raise KBError(f"Il campo «{label}» deve stare su una riga.")
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in text
           if not (multiline and char in "\n\t")):
        raise KBError(f"Il campo «{label}» contiene un carattere di controllo.")
    return text


def _refuse_scaffolding(text: str, label: str) -> None:
    if "```" in text or "~~~" in text:
        raise KBError(f"Il campo «{label}» contiene un blocco di codice Markdown: scrivi solo il testo.")
    if _FRONTMATTER_LINE.search(text):
        raise KBError(f"Il campo «{label}» contiene un delimitatore di frontmatter: scrivi solo il testo.")
    if _HEADING.match(text):
        raise KBError(f"Il campo «{label}» inizia come un titolo Markdown: scrivi solo il testo.")


def _refuse_secrets(text: str, label: str) -> None:
    """Run Hermes' redaction forcibly; a changed string is a leak we refuse to persist."""
    try:
        from agent.redact import redact_sensitive_text

        redacted = redact_sensitive_text(text, force=True)
    except Exception as exc:  # fail closed: a capture must not bypass the secret boundary
        raise KBError("Non riesco a verificare i segreti nel testo: riprova tra poco.") from exc
    if redacted != text:
        raise KBError(f"Il campo «{label}» contiene un segreto o una credenziale: rimuovilo e riprova.")


def _validate_args(args: Any) -> tuple[str, str, list[str]]:
    if not isinstance(args, dict):
        raise KBError("Gli argomenti della cattura non sono validi.")
    extra = [key for key in args if key not in _ALLOWED_ARGS]
    if extra:
        raise KBError("La cattura accetta solo «argomento», «fatto» e «fonti»: "
                      f"«{extra[0]}» non è un campo valido. La provenienza la aggiunge il runtime.")
    if "argomento" not in args or "fatto" not in args:
        raise KBError("La cattura richiede «argomento» e «fatto».")
    argomento = _clean(args.get("argomento"), "argomento", limit=MAX_ARGOMENTO, multiline=False)
    fatto = _clean(args.get("fatto"), "fatto", limit=MAX_FATTO, multiline=True)
    _refuse_scaffolding(argomento, "argomento")
    _refuse_scaffolding(fatto, "fatto")
    if _TRANSCRIPT_LINE.search(fatto):
        raise KBError("Il campo «fatto» sembra una trascrizione della conversazione: riassumi il "
                      "fatto in una frase autosufficiente.")
    if not _normalized_fact(fatto):
        raise KBError("Il campo «fatto» non contiene parole.")
    _refuse_secrets(argomento, "argomento")
    _refuse_secrets(fatto, "fatto")

    raw = args.get("fonti")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise KBError("Il campo «fonti» deve essere un elenco di percorsi.")
    if len(raw) > MAX_FONTI:
        raise KBError(f"Indica al massimo {MAX_FONTI} fonti.")
    if not all(isinstance(item, str) for item in raw):
        raise KBError("Ogni fonte deve essere un percorso scritto come testo.")
    return argomento, fatto, [item.strip() for item in raw]


# --- paths --------------------------------------------------------------------------------------


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _inside(path: Path, roots: list[Path] | tuple[Path, ...]) -> bool:
    for root in roots:
        try:
            if path == root or path.is_relative_to(root):
                return True
        except (OSError, ValueError):
            continue
    return False


def _organization_root(conn: Any) -> Optional[Path]:
    from .prompt import organization_root

    return organization_root(conn)


def _connected_roots(conn: Any) -> list[Path]:
    """The islands this computer actually received; a citation must stay inside one of them."""
    found: list[Path] = []
    for raw in conn.roots:
        path = _resolve(Path(raw))
        if path not in found:
            found.append(path)
    return found


def _kb_roots(conn: Any) -> list[Path]:
    """The organization root first (for ``KB-root relative`` paths), then each connected island."""
    found: list[Path] = []
    for candidate in (_organization_root(conn), *_connected_roots(conn)):
        if candidate is not None and candidate not in found:
            found.append(_resolve(candidate))
    return found


def _path_candidates(conn: Any, text: str) -> list[Path]:
    raw = Path(text)
    if raw.is_absolute():
        return [raw]
    return [root / raw for root in _kb_roots(conn)]


def _source_path(conn: Any, raw: str) -> Path:
    text = raw.strip()
    if not text:
        raise KBError("Una fonte ha un percorso vuoto.")
    if len(text) > MAX_FONTE:
        raise KBError(f"Un percorso di fonte supera i {MAX_FONTE} caratteri.")
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in text):
        raise KBError("Un percorso di fonte contiene un carattere di controllo.")
    if _URL.match(text):
        raise KBError(f"«{text}» è un indirizzo web, non un file della KB: indica il file che hai letto.")
    _refuse_secrets(text, "fonti")

    roots = _connected_roots(conn)
    outside: Optional[Path] = None
    restricted: Optional[Path] = None
    for candidate in _path_candidates(conn, text):
        path = _resolve(candidate)
        if not path.is_file():
            continue
        if _personal_or_restricted(conn, path):
            restricted = path
            continue
        if not _inside(path, roots):
            outside = path
            continue
        return path
    if restricted is not None:
        raise KBError(f"La fonte «{text}» è in una cartella personale o riservata e non può essere citata.")
    if outside is not None:
        raise KBError(f"La fonte «{text}» non è in una cartella collegata della KB.")
    raise KBError(f"La fonte «{text}» non esiste o non è un file leggibile.")


def _personal_or_restricted(conn: Any, path: Path) -> bool:
    personal = _resolve(Path(conn.personal))
    if _inside(path, [personal]):
        return True
    absolute = [part.casefold() for part in path.parts]
    if "operatori" in absolute or "riservato" in absolute:
        return True
    for base in _connected_roots(conn):
        if not _inside(path, [base]):
            continue
        relative = [part.casefold() for part in path.relative_to(base).parts]
        if any(part.startswith(".") for part in relative):
            return True
    return path.name.casefold() in _SENSITIVE_NAMES


def _display_path(conn: Any, path: Path) -> str:
    """The path relative to the KB root, so the shared proposal does not carry a machine layout."""
    for base in _kb_roots(conn):
        if _inside(path, [base]):
            relative = path.relative_to(base).as_posix()
            if relative:
                return relative
    return path.as_posix()


# --- dedup --------------------------------------------------------------------------------------


def _normalized_fact(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).split())


def _fingerprint(text: str) -> str:
    return hashlib.sha256(_normalized_fact(text).encode("utf-8")).hexdigest()


def _body(text: str) -> str:
    """The fact body of a proposal, without its YAML frontmatter."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() in {"---", "..."}:
                return "\n".join(lines[index + 1:])
        return ""
    return text


def _state_path(conn: Any) -> Path:
    from .paths import data_dir

    key = hashlib.sha256(str(_resolve(Path(conn.personal))).encode("utf-8")).hexdigest()[:10]
    operator = re.sub(r"[^A-Za-z0-9._-]+", "_", str(conn.operator))[:40] or "operatore"
    return data_dir() / f"knowledge-dedup-{operator}-{key}.json"


def _state(conn: Any) -> dict[str, Any]:
    from .paths import read_json

    data = read_json(_state_path(conn))
    facts = data.get("facts") if isinstance(data, dict) else None
    return facts if isinstance(facts, dict) else {}


def _remember(conn: Any, digest: str, file_name: str) -> None:
    """Record the fact's hash, never the fact; local bookkeeping is best effort."""
    from .paths import read_json, write_json

    path = _state_path(conn)
    data = read_json(path)
    facts = data.get("facts") if isinstance(data, dict) and isinstance(data.get("facts"), dict) else {}
    facts.pop(digest, None)
    facts[digest] = {"file": file_name, "at": datetime.now(UTC).isoformat(timespec="seconds")}
    while len(facts) > MAX_FACTS:
        facts.pop(next(iter(facts)))
    try:
        write_json(path, {"schema": 1, "facts": facts})
    except OSError:
        logger.debug("requrv-kb: non ho potuto aggiornare l'indice locale delle conoscenze", exc_info=True)


def _folder_duplicate(folder: Path, wanted: str) -> Optional[str]:
    """The name of an existing proposal with the same normalized fact, if the folder has one."""
    for path in sorted(folder.glob("*.md")):
        if path.is_symlink():  # a synced link must not pull an outside file into the dedup read
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if is_online_only(stat) or stat.st_size > MAX_SCAN_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if _normalized_fact(_body(text)) == wanted:
            return path.name
    return None


# --- writing ------------------------------------------------------------------------------------


def _knowledge_folder(conn: Any) -> Path:
    from . import mirror

    personal = Path(conn.personal)
    if not personal.is_dir():
        raise KBError("La cartella personale non è disponibile: la cattura resta sul computer.")
    base = _resolve(personal)
    folder = mirror.knowledge_dir(conn)
    parent = folder.parent
    if parent.exists() and not _inside(_resolve(parent), [base]):
        raise KBError("La cartella delle proposte punta fuori dalla tua cartella personale: "
                      "controlla il collegamento e riprova.")
    if folder.is_symlink():
        raise KBError("La cartella delle proposte è un collegamento: non ci scrivo una conoscenza. "
                      "Sostituiscila con una cartella normale e riprova.")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        resolved = _resolve(folder)
    except OSError as exc:
        raise KBError("Non riesco a creare la cartella proposte/knowledge nella tua cartella personale.") from exc
    if not resolved.is_dir() or not _inside(resolved, [base]):
        raise KBError("La cartella delle proposte non è nella tua cartella personale: "
                      "controlla il collegamento e riprova.")
    return folder


def _slug(argomento: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", argomento).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")
    return text[:48] or "conoscenza"


def _render(argomento: str, fatto: str, fonti: list[str], *, autore: str, bot: str,
            session_id: str, data: str) -> str:
    from io import StringIO

    from ruamel.yaml import YAML

    frontmatter: dict[str, Any] = {
        "data": data,
        "autore": autore,
        "bot": bot,
        "argomento": argomento,
        "fonti": list(fonti),
    }
    if session_id:
        frontmatter["session_id"] = session_id
    stream = StringIO()
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.allow_unicode = True
    yaml.dump(frontmatter, stream)
    return f"---\n{stream.getvalue()}---\n\n{fatto}\n"


def _create_exclusive(path: Path, text: str) -> None:
    """Publish *text* at *path* only if nothing is there, and only once it is complete.

    A temporary file in the same folder is filled and synced first, then hard-linked to the final
    name: the link is atomic and fails with ``FileExistsError`` when another process won. A
    filesystem without hard links falls back to ``O_EXCL``; the content is still bounded and written
    before the handle is closed.
    """
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise
        except OSError as exc:
            no_links = {errno.EPERM, errno.EACCES, errno.EXDEV,
                        getattr(errno, "ENOTSUP", -1), getattr(errno, "EOPNOTSUPP", -1)}
            if exc.errno not in no_links:
                raise
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
    finally:
        Path(temporary).unlink(missing_ok=True)


def _store(folder: Path, *, argomento: str, fatto: str, fonti: list[str], autore: str,
           bot: str, session_id: str, wanted: str) -> tuple[str, bool]:
    """Write a candidate; ``(file name, duplicate)``. Collisions are compared by normalized fact."""
    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}-{_slug(argomento)}"
    text = _render(argomento, fatto, fonti, autore=autore, bot=bot, session_id=session_id,
                   data=now.isoformat(timespec="seconds"))
    for index in range(1, _MAX_COLLISION + 1):
        name = f"{base}.md" if index == 1 else f"{base}-{index}.md"
        path = folder / name
        try:
            _create_exclusive(path, text)
            return name, False
        except FileExistsError:
            if path.is_symlink():  # do not follow a synced link while comparing an existing candidate
                continue
            try:
                existing = path.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                existing = ""
            if _normalized_fact(_body(existing)) == wanted:
                return name, True
    raise KBError("Ci sono troppe conoscenze con lo stesso argomento nello stesso secondo: "
                  "riprova tra poco.")


# --- the operation ------------------------------------------------------------------------------


def capture(args: dict[str, Any], *, session_id: str = "") -> dict[str, str]:
    """Propose one fact, returning ``{"status": "created"|"duplicate", "file": <basename>}``.

    ``args`` may contain only ``argomento``, ``fatto`` and ``fonti``. ``fonti`` is a list of absolute
    paths or paths relative to the KB root; an empty or missing list means the fact is proposed
    without external provenance. ``session_id`` comes from the runtime, not from the model.

    The same normalized fact is never written twice: a match in the shared folder or in the local
    index returns ``duplicate`` and the existing file name, even after the IT deleted that file.
    """
    conn, _profile, bot = _context()
    argomento, fatto, raw_fonti = _validate_args(args)
    session = ""
    if session_id:
        if not isinstance(session_id, str):
            raise KBError("L'identificativo della sessione non è valido.")
        session = _clean(session_id, "session_id", limit=MAX_SESSION_ID,
                         multiline=False) if session_id.strip() else ""

    fonti = [_display_path(conn, _source_path(conn, raw)) for raw in raw_fonti]
    wanted = _normalized_fact(fatto)
    digest = _fingerprint(fatto)

    with _LOCK, _process_lock():
        known = _state(conn).get(digest)
        if isinstance(known, dict) and isinstance(known.get("file"), str):
            name = os.path.basename(known["file"])
            if name:
                return {"status": "duplicate", "file": name}
        folder = _knowledge_folder(conn)
        duplicate = _folder_duplicate(folder, wanted)
        if duplicate is not None:
            _remember(conn, digest, duplicate)
            return {"status": "duplicate", "file": duplicate}
        try:
            name, is_duplicate = _store(folder, argomento=argomento, fatto=fatto, fonti=fonti,
                                        autore=str(conn.operator), bot=bot, session_id=session,
                                        wanted=wanted)
        except OSError as exc:
            raise KBError("Non riesco a scrivere la proposta nella cartella personale: "
                          "controlla lo spazio e i permessi e riprova.") from exc
        _remember(conn, digest, name)
        return {"status": "duplicate" if is_duplicate else "created", "file": name}
