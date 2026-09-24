"""Machine-readable output for AI agents (Mini-Pillar 5 — Agentics).

This module turns God Code diagnostics and run results into stable JSON
payloads an agent can parse without scraping divine prose. The CLI wires
it in behind ``--json`` on the ``run`` and ``check`` commands.

Error-code mapping choice
-------------------------
Codes are a small, stable, language-agnostic vocabulary derived from the
v2.0 exception hierarchy in :mod:`godcode.errors` (there is no
``GodCodeSyntaxError`` class in v2.0, so the mapping below is explicit):

    LexerError       -> LEXER_ERROR
    ParseError       -> PARSE_ERROR
    GodRuntimeError  -> RUNTIME_ERROR

Any other ``GodCodeError`` subclass falls back to a mechanical
CamelCase -> UPPER_SNAKE conversion of its class name
(e.g. ``FooBarError`` -> ``FOO_BAR_ERROR``). Failures that are not God
Code failures at all (an unreadable scroll file) use ``FILE_ERROR``,
which is not an exception class.

Capture choice
--------------
``run`` output is captured with :func:`contextlib.redirect_stdout` into
a :class:`io.StringIO` around the interpreter call — no dependency on
any capture hooks from sibling pillars.

Seals
-----
After the run we diff the interpreter's bound ``ledger`` (when present)
against its block count before the run. Blocks sealed during the run are
reported as ``{"block": <index>, "hash": <sha>}``. When no ledger is
bound or it cannot be read, ``seals`` is ``[]`` — never an error.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import time
from pathlib import Path

TOOL_NAME = "godcode"

# ---------------------------------------------------------------------------
# error codes
# ---------------------------------------------------------------------------
_CODE_MAP = {
    "LexerError": "LEXER_ERROR",
    "ParseError": "PARSE_ERROR",
    "GodRuntimeError": "RUNTIME_ERROR",
}

_HINTS = {
    "LEXER_ERROR": (
        "Scan the reported line for stray symbols or an unterminated "
        "string; God Code strings use double quotes."
    ),
    "PARSE_ERROR": (
        "Every scroll needs BEGIN CREATION ... END CREATION; comparisons "
        "use IS / IS NOT, and every block needs its closer "
        "(ENDIF, ENDFOR, ENDWHILE, END RITE)."
    ),
    "RUNTIME_ERROR": (
        "The scroll parsed but stumbled while running — DECLARE every "
        "name before use and re-read the reported line."
    ),
    "FILE_ERROR": "Check the path — the scroll must exist and be readable.",
}


def _to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


def error_code(err) -> str:
    """Map a God Code exception to its stable machine code."""
    name = type(err).__name__
    if name in _CODE_MAP:
        return _CODE_MAP[name]
    snake = _to_snake(name)
    return snake if snake.endswith("_ERROR") else snake + "_ERROR"


def hint_for(code: str) -> str | None:
    """One-line actionable suggestion for a code, or None."""
    return _HINTS.get(code)


def diagnostic(err, *, severity: str = "error") -> dict:
    """Turn a GodCodeError into a JSON-serializable diagnostic dict."""
    code = error_code(err)
    # err.msg is the clean message; str(err) may append "(line N)" which
    # would duplicate the structured line/col fields below.
    return {
        "line": getattr(err, "line", None),
        "col": getattr(err, "col", None),
        "code": code,
        "severity": severity,
        "message": getattr(err, "msg", None) or str(err),
        "hint": hint_for(code),
    }


def error_trace(err) -> list[dict]:
    """The ``run --json`` trace array for a failed run.

    A list of ``{"rite": name, "line": call-site line}``, oldest call first
    (the most recent call is last). Empty when the error rose at the top
    level, before any rite was called. The interpreter snapshots
    ``err.call_trace`` when the error first rises, before the call stack
    unwinds.
    """
    return [
        {"rite": frame.get("rite"), "line": frame.get("line")}
        for frame in (getattr(err, "call_trace", None) or [])
    ]


def _file_error_diagnostic(path: str, exc: OSError) -> dict:
    detail = exc.strerror or str(exc)
    return {
        "line": None,
        "col": None,
        "code": "FILE_ERROR",
        "severity": "error",
        "message": f"godcode: cannot read '{path}': {detail}",
        "hint": hint_for("FILE_ERROR"),
    }


# ---------------------------------------------------------------------------
# payload builders
# ---------------------------------------------------------------------------
def check_payload(file: str, ok: bool, diagnostics: list[dict]) -> dict:
    return {
        "tool": TOOL_NAME,
        "command": "check",
        "file": file,
        "ok": ok,
        "diagnostics": diagnostics,
    }


def run_payload(file: str, ok: bool, output: list[str],
                seals: list[dict], error: dict | None, ms: int,
                intents: list[dict] | None = None) -> dict:
    return {
        "tool": TOOL_NAME,
        "command": "run",
        "file": file,
        "ok": ok,
        "output": output,
        "seals": seals,
        "intents": intents if intents is not None else [],
        "error": error,
        "stats": {"ms": ms},
    }


def emit(payload: dict) -> None:
    """Write one JSON document to stdout; nothing else may be printed."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# --json command implementations (called from godcode.cli)
# ---------------------------------------------------------------------------
def cmd_check_json(args) -> int:
    """`godcode check --json FILE`. Exit 0 if pure, 1 if diagnostics."""
    from godcode.errors import GodCodeError
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        emit(check_payload(args.file, False, [_file_error_diagnostic(args.file, exc)]))
        return 1
    try:
        Parser(Lexer(source).lex()).parse()
    except GodCodeError as err:
        emit(check_payload(args.file, False, [diagnostic(err)]))
        return 1
    emit(check_payload(args.file, True, []))
    return 0


def _ledger_block_count(interp) -> int | None:
    ledger = getattr(interp, "ledger", None)
    if ledger is None:
        return None
    try:
        return len(ledger.read_all())
    except Exception:
        return None


def _new_seals(interp, before: int | None) -> list[dict]:
    """Best-effort list of covenant blocks sealed during the run."""
    if before is None:
        return []
    ledger = getattr(interp, "ledger", None)
    if ledger is None:
        return []
    try:
        blocks = ledger.read_all()[before:]
    except Exception:
        return []
    seals = []
    for block in blocks:
        if isinstance(block, dict) and "hash" in block:
            seals.append({"block": block.get("index"), "hash": block.get("hash")})
    return seals


def cmd_run_json(args) -> int:
    """`godcode run --json FILE`. Exit 0 on success, 1 on failure."""
    from godcode.errors import GodCodeError
    from godcode.cli import _make_interpreter  # shared with the plain run path

    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        emit(run_payload(args.file, False, [], [], _file_error_diagnostic(args.file, exc), 0))
        return 1

    interp = _make_interpreter(args.log)
    seals_before = _ledger_block_count(interp)

    buf = io.StringIO()
    error: dict | None = None
    start = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        try:
            interp.run_source(source, source_name=args.file)
        except GodCodeError as err:
            error = diagnostic(err)
            error["trace"] = error_trace(err)
    ms = int((time.perf_counter() - start) * 1000)

    output = buf.getvalue().splitlines()
    seals = _new_seals(interp, seals_before)
    intents = list(getattr(interp, "intent_checks", []) or [])
    emit(run_payload(args.file, error is None, output, seals, error, ms,
                     intents=intents))
    return 0 if error is None else 1
