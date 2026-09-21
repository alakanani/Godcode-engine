"""Language server for God Code (v3.0, Pillar 4).

A minimal Language Server Protocol implementation over stdio, hand-rolled
on top of the stdlib — no third-party dependencies. JSON-RPC 2.0 messages
are framed with ``Content-Length`` headers, per the LSP base protocol.

Lifecycle::

    godcode lsp                      # start serving on stdin/stdout

Diagnostics are produced by the real lexer/parser pipeline (the same
logic ``godcode check`` uses): opening or changing a ``.god`` scroll
re-parses it and publishes the divine errors as LSP diagnostics.

Protocol notes:
  * All logging goes to stderr. stdout is the protocol channel — nothing
    else may ever be written there.
  * Unknown methods answer with JSON-RPC error -32601 ("Method not found").
  * Malformed frames are skipped; the server keeps serving.
"""

from __future__ import annotations

import json
import re
import sys

# ---------------------------------------------------------------------------
# Divine documentation table (hover + completion)
# ---------------------------------------------------------------------------

LSP_DOCS: dict[str, str] = {
    # -- block sentinels -------------------------------------------------
    "BEGIN CREATION": (
        "**BEGIN CREATION**\n\n"
        "Speak, and let there be a program. Every scroll opens its works "
        "with `BEGIN CREATION` and closes them with `END CREATION`.\n\n"
        "```godcode\nBEGIN CREATION\n  REVEAL(\"Let there be light\")\n"
        "  ASCEND\nEND CREATION\n```"
    ),
    "END CREATION": (
        "**END CREATION**\n\n"
        "The seal upon the scroll — it closes what `BEGIN CREATION` opened. "
        "No works may follow it.\n\n"
        "```godcode\nEND CREATION\n```"
    ),
    "DEFINE RITE": (
        "**DEFINE RITE**\n\n"
        "Establish a rite — a named ceremony of statements that may be "
        "invoked again and again. Closed with `END RITE`; a rite may "
        "`RETURN` a value to its caller.\n\n"
        "```godcode\nDEFINE RITE bless(name)\n"
        "  REVEAL(\"Blessed be \" + name)\nEND RITE\n```"
    ),
    "END RITE": (
        "**END RITE**\n\n"
        "The closing of a rite begun with `DEFINE RITE`. All ceremonies "
        "must be sealed.\n\n"
        "```godcode\nEND RITE\n```"
    ),
    "BREATHE LIFE INTO": (
        "**BREATHE LIFE INTO**\n\n"
        "Awaken a declared vessel so it may be used. A name must be "
        "`DECLARE`d before the breath is given.\n\n"
        "```godcode\nDECLARE vessel AS 0\nBREATHE LIFE INTO vessel\n```"
    ),
    # -- keywords --------------------------------------------------------
    "BEGIN": (
        "**BEGIN**\n\n"
        "The opening word of creation — always paired with `CREATION`. "
        "See `BEGIN CREATION`.\n\n```godcode\nBEGIN CREATION\n```"
    ),
    "CREATION": (
        "**CREATION**\n\n"
        "The body of all works — paired with `BEGIN` to open a scroll and "
        "with `END` to close it. See `BEGIN CREATION`.\n\n"
        "```godcode\nBEGIN CREATION\n  ASCEND\nEND CREATION\n```"
    ),
    "DECLARE": (
        "**DECLARE**\n\n"
        "Bring a name into being and bind it to a value. "
        "Every vessel must be declared before the breath is given.\n\n"
        "```godcode\nDECLARE tribes AS 12\n```"
    ),
    "AS": (
        "**AS**\n\n"
        "The binding word — it joins a declared name to its value, as "
        "in `DECLARE x AS 1`.\n\n```godcode\nDECLARE x AS 1\n```"
    ),
    "IF": (
        "**IF**\n\n"
        "Weigh a condition; if it holds true, the words between `THEN` "
        "and `ENDIF` come to pass.\n\n"
        "```godcode\nIF faith > fear THEN\n  REVEAL(\"walk on\")\nENDIF\n```"
    ),
    "THEN": (
        "**THEN**\n\n"
        "Marks the start of the true branch after an `IF` condition. "
        "Closed by `ENDIF` (or `ELSE`).\n\n```godcode\nIF x THEN\n  REVEAL(x)\n"
        "ENDIF\n```"
    ),
    "ELSE": (
        "**ELSE**\n\n"
        "The other path — when the `IF` condition proves false, these "
        "words come to pass instead.\n\n"
        "```godcode\nIF x THEN\n  REVEAL(\"yes\")\nELSE\n"
        "  REVEAL(\"no\")\nENDIF\n```"
    ),
    "ENDIF": (
        "**ENDIF**\n\n"
        "The seal upon an `IF` weighing. Every `IF` must be closed.\n\n"
        "```godcode\nENDIF\n```"
    ),
    "FOR": (
        "**FOR**\n\n"
        "Walk through every member of a list or range, naming each one "
        "in turn, until `ENDFOR`.\n\n"
        "```godcode\nFOR tribe IN RANGE(12)\n  REVEAL(tribe)\nENDFOR\n```"
    ),
    "IN": (
        "**IN**\n\n"
        "The walking word — `FOR name IN list` binds each member in turn.\n\n"
        "```godcode\nFOR star IN heavens\n  REVEAL(star)\nENDFOR\n```"
    ),
    "ENDFOR": (
        "**ENDFOR**\n\n"
        "The seal upon a `FOR` walk. Every journey must end.\n\n"
        "```godcode\nENDFOR\n```"
    ),
    "WHILE": (
        "**WHILE**\n\n"
        "Repeat the works between `DO` and `ENDWHILE` for as long as the "
        "condition holds true.\n\n"
        "```godcode\nWHILE night < dawn DO\n  REVEAL(\"watch\")\nENDWHILE\n```"
    ),
    "DO": (
        "**DO**\n\n"
        "Marks the start of the repeated works in a `WHILE` loop.\n\n"
        "```godcode\nWHILE x DO\n  REVEAL(x)\nENDWHILE\n```"
    ),
    "ENDWHILE": (
        "**ENDWHILE**\n\n"
        "The seal upon a `WHILE` vigil.\n\n```godcode\nENDWHILE\n```"
    ),
    "DEFINE": (
        "**DEFINE**\n\n"
        "The first word of a rite's establishment — always paired with "
        "`RITE`. See `DEFINE RITE`.\n\n```godcode\nDEFINE RITE bless()\n"
        "END RITE\n```"
    ),
    "RITE": (
        "**RITE**\n\n"
        "A named ceremony of statements. Paired with `DEFINE` to open "
        "and `END` to close. See `DEFINE RITE`.\n\n"
        "```godcode\nDEFINE RITE bless()\nEND RITE\n```"
    ),
    "INVOKE": (
        "**INVOKE**\n\n"
        "Call a rite by name, offering it arguments in the ancient manner.\n\n"
        "```godcode\nINVOKE bless(\"the meek\")\n```"
    ),
    "RETURN": (
        "**RETURN**\n\n"
        "Offer a value back from a rite to the one who invoked it. "
        "A rite without `RETURN` yields the void.\n\n"
        "```godcode\nRETURN manna * 2\n```"
    ),
    "IMPORT": (
        "**IMPORT**\n\n"
        "Bring another scroll into this creation, that its works may "
        "serve here.\n\n```godcode\nIMPORT \"psalms.god\"\n```"
    ),
    "REVEAL": (
        "**REVEAL**\n\n"
        "Speak a value aloud — the scroll's voice, printing to the world "
        "beyond.\n\n```godcode\nREVEAL(\"The heavens declare\")\n```"
    ),
    "BREATHE": (
        "**BREATHE**\n\n"
        "The first word of awakening — always `BREATHE LIFE INTO name`. "
        "See `BREATHE LIFE INTO`.\n\n"
        "```godcode\nBREATHE LIFE INTO vessel\n```"
    ),
    "LIFE": (
        "**LIFE**\n\n"
        "The middle word of `BREATHE LIFE INTO` — the breath itself.\n\n"
        "```godcode\nBREATHE LIFE INTO vessel\n```"
    ),
    "INTO": (
        "**INTO**\n\n"
        "The directing word of `BREATHE LIFE INTO name`.\n\n"
        "```godcode\nBREATHE LIFE INTO vessel\n```"
    ),
    "PROPHESY": (
        "**PROPHESY**\n\n"
        "Utter a fixed word into the scroll — a literal prophecy of text.\n\n"
        "```godcode\nPROPHESY \"and it was good\"\n```"
    ),
    "ASCEND": (
        "**ASCEND**\n\n"
        "End the run in peace. Nothing after `ASCEND` shall come to pass.\n\n"
        "```godcode\nASCEND\n```"
    ),
    "SEAL": (
        "**SEAL**\n\n"
        "Set a value under seal — it is recorded in the covenant ledger "
        "and may not be altered thereafter.\n\n```godcode\nSEAL covenant\n```"
    ),
    "TESTIFY": (
        "**TESTIFY**\n\n"
        "Bear witness to a value — affirm it before the heavens.\n\n"
        "```godcode\nTESTIFY manna > 0\n```"
    ),
    "BLESS": (
        "**BLESS**\n\n"
        "Confer blessing upon a name, marking it favored.\n\n"
        "```godcode\nBLESS the_meek\n```"
    ),
    "ANOINT": (
        "**ANOINT**\n\n"
        "Anoint a name for a holy purpose, setting it apart.\n\n"
        "```godcode\nANOINT the_chosen\n```"
    ),
    "REFLECT": (
        "**REFLECT**\n\n"
        "Pause and contemplate — a still point in the works.\n\n"
        "```godcode\nREFLECT\n```"
    ),
    "AND": (
        "**AND**\n\n"
        "Join two truths; the whole holds only if both hold.\n\n"
        "```godcode\nIF faith AND works THEN\n```"
    ),
    "OR": (
        "**OR**\n\n"
        "Offer two truths; the whole holds if either holds.\n\n"
        "```godcode\nIF mercy OR grace THEN\n```"
    ),
    "NOT": (
        "**NOT**\n\n"
        "Turn a truth upon its head.\n\n```godcode\nIF NOT fear THEN\n```"
    ),
    "TRUE": (
        "**TRUE**\n\n"
        "The eternal yes.\n\n```godcode\nDECLARE amen AS true\n```"
    ),
    "FALSE": (
        "**FALSE**\n\n"
        "The eternal no.\n\n```godcode\nDECLARE doubt AS false\n```"
    ),
    "VOID": (
        "**VOID**\n\n"
        "The absence of all things — what a rite yields when it returns "
        "nothing.\n\n```godcode\nDECLARE emptiness AS void\n```"
    ),
    "IS": (
        "**IS**\n\n"
        "The weighing word — reserved for divine comparisons.\n\n"
        "```godcode\n# reserved\n```"
    ),
    "END": (
        "**END**\n\n"
        "The closing word — paired with `CREATION` or `RITE` to seal a "
        "block.\n\n```godcode\nEND CREATION\n```"
    ),
    # -- built-ins -------------------------------------------------------
    "LEN": (
        "**LEN**(value)\n\n"
        "Measure the length of a string or a list, and the number shall "
        "be revealed.\n\n```godcode\nREVEAL(LEN(\"firmament\"))\n```"
    ),
    "STR": (
        "**STR**(value)\n\n"
        "Turn anything into its spoken form — a string.\n\n"
        "```godcode\nREVEAL(STR(40) + \" days\")\n```"
    ),
    "NUM": (
        "**NUM**(value)\n\n"
        "Turn a string into a number, that it may be weighed and counted.\n\n"
        "```godcode\nDECLARE years AS NUM(\"40\")\n```"
    ),
    "TYPE": (
        "**TYPE**(value)\n\n"
        "Discern the kind of a thing — its type, named aloud.\n\n"
        "```godcode\nREVEAL(TYPE(manna))\n```"
    ),
    "RANDOM": (
        "**RANDOM**(bound)\n\n"
        "Cast lots — draw a whole number from 0 up to (but not including) "
        "`bound`.\n\n```godcode\nDECLARE lot AS RANDOM(12)\n```"
    ),
    "RANGE": (
        "**RANGE**(stop) / **RANGE**(start, stop)\n\n"
        "Number the days — produce the sequence of whole numbers from "
        "0 (or `start`) up to `stop`.\n\n```godcode\n"
        "FOR day IN RANGE(7)\n  REVEAL(day)\nENDFOR\n```"
    ),
    "PUSH": (
        "**PUSH**(list, value)\n\n"
        "Add to the multitude — append `value` to the end of `list`.\n\n"
        "```godcode\nPUSH(tribes, \"Benjamin\")\n```"
    ),
    "UPPER": (
        "**UPPER**(text)\n\n"
        "Lift every letter to the heavens — uppercase the string.\n\n"
        "```godcode\nREVEAL(UPPER(\"hosanna\"))\n```"
    ),
    "LOWER": (
        "**LOWER**(text)\n\n"
        "Humble every letter — lowercase the string.\n\n"
        "```godcode\nREVEAL(LOWER(\"HOSANNA\"))\n```"
    ),
    "SPLIT": (
        "**SPLIT**(text, separator)\n\n"
        "Divide the word — split `text` into a list at each `separator`.\n\n"
        "```godcode\nDECLARE words AS SPLIT(\"loaves fishes\", \" \")\n```"
    ),
    "JOIN": (
        "**JOIN**(list, separator)\n\n"
        "Gather the scattered — join a list of strings with `separator`.\n\n"
        "```godcode\nREVEAL(JOIN(words, \" \"))\n```"
    ),
    "ASK": (
        "**ASK**([prompt])\n\n"
        "Seek counsel — read a line from the one who runs the scroll.\n\n"
        "```godcode\nDECLARE name AS ASK(\"What is your name? \")\n```"
    ),
    "BEHOLD": (
        "**BEHOLD**()\n\n"
        "Mark the present hour — the current time, in the heavens' own "
        "notation.\n\n```godcode\nREVEAL(BEHOLD())\n```"
    ),
    "REVERSE": (
        "**REVERSE**(value)\n\n"
        "Turn it back upon itself — reverse a string or a list.\n\n"
        "```godcode\nREVEAL(REVERSE(\"stressed\"))\n```"
    ),
}

# Phrases matched as whole units on hover (case-insensitive).
_PHRASES = ("BEGIN CREATION", "END CREATION", "DEFINE RITE", "END RITE",
            "BREATHE LIFE INTO")

# Snippet-style completions: (label, insertText, detail).
_SNIPPETS: tuple[tuple[str, str, str], ...] = (
    ("BEGIN CREATION … END CREATION",
     "BEGIN CREATION\n\t$0\nEND CREATION",
     "Open a new scroll"),
    ("DECLARE … AS …", "DECLARE ${1:name} AS ${2:value}$0",
     "Declare a vessel"),
    ("IF … THEN … ENDIF",
     "IF ${1:condition} THEN\n\t$0\nENDIF",
     "Weigh a condition"),
    ("FOR … IN … ENDFOR",
     "FOR ${1:item} IN ${2:list}\n\t$0\nENDFOR",
     "Walk a multitude"),
    ("WHILE … DO … ENDWHILE",
     "WHILE ${1:condition} DO\n\t$0\nENDWHILE",
     "Keep a vigil"),
    ("DEFINE RITE … END RITE",
     "DEFINE RITE ${1:name}(${2:params})\n\t$0\nEND RITE",
     "Establish a rite"),
    ("INVOKE …", "INVOKE ${1:name}(${2:args})$0", "Call a rite"),
)

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# ---------------------------------------------------------------------------
# Diagnostics — the real parser, same as `godcode check`
# ---------------------------------------------------------------------------

def check_source(text: str) -> list[dict]:
    """Parse *text* and return LSP diagnostics (empty when pure)."""
    from godcode.errors import GodCodeError
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    try:
        Parser(Lexer(text).lex()).parse()
    except GodCodeError as err:
        line = max((err.line or 1) - 1, 0)  # LSP lines are 0-based
        lines = text.splitlines()
        line_len = len(lines[line]) if line < len(lines) else 0
        start_char = max((err.col or 1) - 1, 0)
        start_char = min(start_char, max(line_len - 1, 0))
        end_char = min(start_char + 1, line_len)
        return [{
            "range": {
                "start": {"line": line, "character": start_char},
                "end": {"line": line, "character": end_char},
            },
            "severity": 1,  # Error
            "source": "godcode",
            "message": str(err),
        }]
    return []


# ---------------------------------------------------------------------------
# Hover
# ---------------------------------------------------------------------------

def _phrase_at(line_text: str, char: int) -> str | None:
    upper = line_text.upper()
    for phrase in _PHRASES:
        start = 0
        while True:
            idx = upper.find(phrase, start)
            if idx < 0:
                break
            if idx <= char <= idx + len(phrase):
                return phrase
            start = idx + 1
    return None


def hover_word(line_text: str, char: int) -> str | None:
    """Return the doc-table key under the cursor, or None."""
    phrase = _phrase_at(line_text, char)
    if phrase is not None:
        return phrase
    for match in _WORD_RE.finditer(line_text):
        if match.start() <= char <= match.end():
            return match.group(0).upper()
    return None


def hover_markdown(word: str | None) -> str | None:
    if word is None:
        return None
    return LSP_DOCS.get(word)


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------

_COMPLETION_KEYWORDS = sorted(LSP_DOCS)
_BUILTINS = ("LEN", "STR", "NUM", "TYPE", "RANDOM", "RANGE", "PUSH",
             "UPPER", "LOWER", "SPLIT", "JOIN", "ASK", "BEHOLD", "REVERSE")


def completion_items() -> list[dict]:
    items: list[dict] = []
    for kw in _COMPLETION_KEYWORDS:
        items.append({
            "label": kw,
            "kind": 14,  # Keyword
            "detail": "God Code " + ("built-in" if kw in _BUILTINS
                                     else "keyword"),
            "insertText": kw,
        })
    for label, insert, detail in _SNIPPETS:
        items.append({
            "label": label,
            "kind": 15,  # Snippet
            "detail": detail,
            "insertText": insert,
            "insertTextFormat": 2,  # Snippet
        })
    return items


# ---------------------------------------------------------------------------
# The server
# ---------------------------------------------------------------------------

def _log(message: str) -> None:
    sys.stderr.write(f"[godcode-lsp] {message}\n")
    sys.stderr.flush()


class LanguageServer:
    """Hand-rolled LSP server over stdio."""

    def __init__(self,
                 stdin: "io.BufferedReader | None" = None,
                 stdout: "io.BufferedWriter | None" = None) -> None:
        import io
        self.stdin = stdin or sys.stdin.buffer
        self.stdout = stdout or sys.stdout.buffer
        self.documents: dict[str, str] = {}
        self._shutdown = False
        self._handlers = {
            "initialize": self._on_initialize,
            "initialized": self._on_initialized,
            "shutdown": self._on_shutdown,
            "exit": self._on_exit,
            "textDocument/didOpen": self._on_did_open,
            "textDocument/didChange": self._on_did_change,
            "textDocument/hover": self._on_hover,
            "textDocument/completion": self._on_completion,
        }

    # -- transport --------------------------------------------------------
    def _read_message(self) -> dict | None:
        """Read one Content-Length framed message. None on clean EOF."""
        headers: dict[str, str] = {}
        while True:
            line = self.stdin.readline()
            if not line:
                return None  # EOF
            line = line.decode("latin-1").strip()
            if not line:
                break
            if ":" in line:
                name, _, value = line.partition(":")
                headers[name.strip().lower()] = value.strip()
        try:
            length = int(headers.get("content-length", ""))
        except (TypeError, ValueError):
            _log("malformed frame: bad Content-Length; skipping")
            return {}
        try:
            body = self._read_exact(length)
        except EOFError:
            _log("malformed frame: truncated body; skipping")
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            _log(f"malformed frame: {exc}; skipping")
            return {}

    def _read_exact(self, length: int) -> bytes:
        body = b""
        while len(body) < length:
            chunk = self.stdin.read(length - len(body))
            if not chunk:
                raise EOFError("truncated frame")
            body += chunk
        return body

    def _write(self, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.stdout.write(
            f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        self.stdout.flush()

    def _notify(self, method: str, params: dict) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _respond(self, msg_id, result) -> None:
        self._write({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def _error(self, msg_id, code: int, message: str) -> None:
        self._write({"jsonrpc": "2.0", "id": msg_id,
                     "error": {"code": code, "message": message}})

    # -- main loop ----------------------------------------------------------
    def serve(self) -> int:
        _log("the sanctuary opens (stdio)")
        while True:
            message = self._read_message()
            if message is None:
                _log("stdin closed; ascending")
                return 1 if not self._shutdown else 0
            if not message:
                continue  # malformed frame: already logged, keep serving
            method = message.get("method")
            handler = self._handlers.get(method) if method else None
            msg_id = message.get("id")
            if handler is None:
                _log(f"unknown method: {method!r}")
                if msg_id is not None:
                    self._error(msg_id, -32601,
                                f"Method not found: {method}")
                continue
            try:
                stop = handler(msg_id, message.get("params") or {})
            except Exception as exc:  # never let a handler kill the server
                _log(f"handler for {method} failed: {exc}")
                if msg_id is not None:
                    self._error(msg_id, -32603,
                                f"Internal error: {exc}")
                continue
            if stop:
                return 0
        # pragma: no cover - unreachable

    # -- handlers -------------------------------------------------------------
    def _on_initialize(self, msg_id, params: dict) -> None:  # noqa: ARG002
        _log("initialize received")
        self._respond(msg_id, {
            "capabilities": {
                "textDocumentSync": 1,  # Full
                "hoverProvider": True,
                "completionProvider": {"triggerCharacters": []},
            },
            "serverInfo": {"name": "godcode-lsp", "version": "3.0.0"},
        })

    def _on_initialized(self, msg_id, params: dict) -> None:  # noqa: ARG002
        _log("initialized; no-op")

    def _on_shutdown(self, msg_id, params: dict) -> None:  # noqa: ARG002
        _log("shutdown requested")
        self._shutdown = True
        if msg_id is not None:
            self._respond(msg_id, None)

    def _on_exit(self, msg_id, params: dict) -> bool:  # noqa: ARG002
        _log("exit; the sanctuary rests")
        return True

    def _on_did_open(self, msg_id, params: dict) -> None:  # noqa: ARG002
        doc = params.get("textDocument", {})
        uri = doc.get("uri", "")
        text = doc.get("text", "")
        self.documents[uri] = text
        self._publish_diagnostics(uri, text)

    def _on_did_change(self, msg_id, params: dict) -> None:  # noqa: ARG002
        doc = params.get("textDocument", {})
        uri = doc.get("uri", "")
        text = self.documents.get(uri, "")
        for change in params.get("contentChanges", []):
            if "range" not in change:  # full-document sync
                text = change.get("text", "")
        self.documents[uri] = text
        self._publish_diagnostics(uri, text)

    def _publish_diagnostics(self, uri: str, text: str) -> None:
        diagnostics = check_source(text)
        _log(f"diagnostics for {uri}: {len(diagnostics)} error(s)")
        self._notify("textDocument/publishDiagnostics",
                     {"uri": uri, "diagnostics": diagnostics})

    def _on_hover(self, msg_id, params: dict) -> None:
        doc = params.get("textDocument", {})
        uri = doc.get("uri", "")
        pos = params.get("position", {})
        line_no = pos.get("line", 0)
        char = pos.get("character", 0)
        text = self.documents.get(uri, "")
        lines = text.splitlines()
        line_text = lines[line_no] if 0 <= line_no < len(lines) else ""
        word = hover_word(line_text, char)
        markdown = hover_markdown(word)
        _log(f"hover at {uri}:{line_no}:{char} -> {word!r}")
        self._respond(msg_id, {"contents": {"kind": "markdown",
                                            "value": markdown}}
                      if markdown else None)

    def _on_completion(self, msg_id, params: dict) -> None:  # noqa: ARG002
        self._respond(msg_id, completion_items())


def serve() -> int:
    """Entry point for ``godcode lsp``."""
    return LanguageServer().serve()
