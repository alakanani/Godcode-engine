"""Agent tool bridge for God Code v4.0 -- "Intent & Chain".

MCP-compatible tool schemas plus a stdio JSON-RPC 2.0 bridge, with no
third-party dependencies. ``godcode tools`` prints the schemas;
``godcode bridge`` speaks the protocol so any MCP-compatible agent host
can check, run, consult, resolve intent, and verify chains.
"""
from __future__ import annotations

import json
from pathlib import Path

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "check",
        "description": (
            "Lex and parse a God Code scroll without running it. "
            "Returns ok plus diagnostics with line, column, error code, "
            "and a fix hint."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string",
                         "description": "Path to the .god scroll"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "run",
        "description": (
            "Run a God Code scroll and capture its output. "
            "Runs inside the deny-by-default sandbox unless sandbox is false."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string",
                         "description": "Path to the .god scroll"},
                "sandbox": {"type": "boolean",
                            "description": "Use the sandbox (default true)"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "consult",
        "description": (
            "Ask the Spirit Engine -- the local oracle -- a question. "
            "Returns two to three sentences of counsel. No external calls."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string",
                             "description": "The question to lay before the Spirit"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "intent",
        "description": (
            "Resolve the spiritual intent behind words with the Spirit "
            "Engine: intent, confidence, spiritual intent, suggestion, "
            "keywords, and declared intents the words align with."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string",
                         "description": "Words to resolve the intent of"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "anchor_verify",
        "description": (
            "Verify a blockchain anchor receipt (as returned by ANCHOR) "
            "against its anchor chain."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "receipt": {"type": "object",
                            "description": "The anchor receipt map"},
            },
            "required": ["receipt"],
        },
    },
    {
        "name": "ledger_verify",
        "description": (
            "Verify the covenant chain and the anchor chain for tampering."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string",
                         "description": "Covenant chain file (default covenant.chain)"},
                "anchor_file": {"type": "string",
                                "description": "Anchor chain file (default anchors.chain)"},
            },
            "required": [],
        },
    },
]

_TOOLS_BY_NAME = {t["name"]: t for t in TOOL_SCHEMAS}


# ---------------------------------------------------------------------------
# tool implementations (each returns a plain-JSON result dict)
# ---------------------------------------------------------------------------
def tool_check(arguments: dict) -> dict:
    from godcode import agentics
    from godcode.errors import GodCodeError
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    file = arguments.get("file")
    if not isinstance(file, str):
        return {"ok": False, "error": "check needs 'file' as a string path"}
    try:
        source = Path(file).read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": f"cannot read '{file}': {exc.strerror or exc}"}
    try:
        Parser(Lexer(source).lex()).parse()
    except GodCodeError as err:
        return {"ok": False, "diagnostics": [agentics.diagnostic(err)]}
    return {"ok": True, "diagnostics": []}


def tool_run(arguments: dict) -> dict:
    from godcode.errors import GodCodeError

    file = arguments.get("file")
    if not isinstance(file, str):
        return {"ok": False, "error": "run needs 'file' as a string path"}
    sandbox = arguments.get("sandbox", True)
    try:
        source = Path(file).read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": f"cannot read '{file}': {exc.strerror or exc}"}
    if sandbox:
        from godcode.sandbox import run_sandboxed

        try:
            output = run_sandboxed(source, source_name=file)
        except GodCodeError as err:
            return {"ok": False, "output": [], "error": str(err)}
        return {"ok": True, "output": output, "error": None}
    from godcode.cli import _make_interpreter
    import contextlib
    import io

    interp = _make_interpreter(None)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            interp.run_source(source, source_name=file)
    except GodCodeError as err:
        return {"ok": False,
                "output": buf.getvalue().splitlines(),
                "error": str(err)}
    return {"ok": True, "output": buf.getvalue().splitlines(), "error": None}


def tool_consult(arguments: dict) -> dict:
    from godcode.spirit import SpiritEngine

    question = arguments.get("question")
    if not isinstance(question, str):
        return {"ok": False, "error": "consult needs 'question' as a string"}
    try:
        counsel = SpiritEngine().counsel(question)
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"the oracle faltered: {exc}"}
    return {"ok": True, "counsel": counsel}


def tool_intent(arguments: dict) -> dict:
    from godcode.spirit import SpiritEngine

    text = arguments.get("text")
    if not isinstance(text, str):
        return {"ok": False, "error": "intent needs 'text' as a string"}
    try:
        result = SpiritEngine().resolve_intent(text)
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"the Spirit faltered: {exc}"}
    return {"ok": True, "result": result}


def tool_anchor_verify(arguments: dict) -> dict:
    from godcode.chain import default_adapters

    receipt = arguments.get("receipt")
    if not isinstance(receipt, dict):
        return {"ok": False, "error": "anchor_verify needs 'receipt' as an object"}
    chain_name = receipt.get("chain", "simulated")
    adapter = default_adapters().get(chain_name)
    if adapter is None:
        return {"ok": False,
                "error": f"unknown chain '{chain_name}'"}
    valid = adapter.verify(receipt)
    return {
        "ok": True,
        "valid": valid,
        "message": ("the anchor stands" if valid
                    else "the anchor does not verify"),
    }


def tool_ledger_verify(arguments: dict) -> dict:
    from godcode.chain import SimulatedChainAdapter
    from godcode.ledger import CovenantLedger

    file = arguments.get("file", "covenant.chain")
    anchor_file = arguments.get("anchor_file", "anchors.chain")
    cov_ok, cov_msg = CovenantLedger(file).verify()
    anc_ok, anc_msg = SimulatedChainAdapter(anchor_file).verify_chain()
    return {
        "ok": True,
        "covenants": {"ok": cov_ok, "message": cov_msg},
        "anchors": {"ok": anc_ok, "message": anc_msg},
    }


_TOOL_FUNCS = {
    "check": tool_check,
    "run": tool_run,
    "consult": tool_consult,
    "intent": tool_intent,
    "anchor_verify": tool_anchor_verify,
    "ledger_verify": tool_ledger_verify,
}


def call_tool(name: str, arguments: dict) -> dict:
    """Run one tool by name; always returns a JSON-safe result dict."""
    func = _TOOL_FUNCS.get(name)
    if func is None:
        return {"ok": False,
                "error": f"unknown tool '{name}'",
                "known_tools": sorted(_TOOL_FUNCS)}
    if not isinstance(arguments, dict):
        return {"ok": False, "error": "arguments must be an object"}
    try:
        return func(arguments)
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"the tool faltered: {exc!r}"}


# ---------------------------------------------------------------------------
# `godcode tools`
# ---------------------------------------------------------------------------
def cmd_tools(args) -> int:
    """Print the MCP-compatible tool schemas (--json for machines)."""
    if getattr(args, "json", False):
        print(json.dumps({"tools": TOOL_SCHEMAS}, ensure_ascii=False, indent=2))
        return 0
    print("God Code tools (MCP-compatible):")
    for tool in TOOL_SCHEMAS:
        required = ", ".join(tool["inputSchema"].get("required", [])) or "none"
        print(f"  {tool['name']}({required}): {tool['description']}")
    print("Speak them through `godcode bridge`, the stdio JSON-RPC loop.")
    return 0


# ---------------------------------------------------------------------------
# `godcode bridge` -- stdio JSON-RPC 2.0
# ---------------------------------------------------------------------------
_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


def _response_ok(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _response_err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": message}}


def _handle_initialize(params: dict) -> dict:
    from godcode import __version__

    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "godcode-bridge", "version": __version__},
    }


def _handle_tools_call(params: dict) -> dict:
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str):
        raise _BridgeError(_INVALID_PARAMS, "tools/call needs 'name' as a string")
    result = call_tool(name, arguments if isinstance(arguments, dict) else {})
    content = [{"type": "text",
                "text": json.dumps(result, ensure_ascii=False)}]
    payload = {"content": content}
    if not result.get("ok", True):
        payload["isError"] = True
    return payload


class _BridgeError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _dispatch(method: str, params: dict):
    if method == "initialize":
        return _handle_initialize(params)
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOL_SCHEMAS}
    if method == "tools/call":
        return _handle_tools_call(params)
    raise _BridgeError(_METHOD_NOT_FOUND, f"no such method '{method}'")


def cmd_bridge(args) -> int:  # noqa: ARG001
    """Serve the tool bridge: JSON-RPC 2.0 over stdio, one request per line."""
    import sys

    stdin, stdout = sys.stdin, sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_response_err(None, _PARSE_ERROR,
                                                 "the request was not JSON"))
                         + "\n")
            stdout.flush()
            continue
        req_id = request.get("id") if isinstance(request, dict) else None
        # Notifications carry no id and get no answer.
        is_notification = isinstance(request, dict) and "id" not in request
        try:
            if not isinstance(request, dict) or "method" not in request:
                raise _BridgeError(_INVALID_REQUEST,
                                   "a request needs a 'method'")
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise _BridgeError(_INVALID_PARAMS,
                                   "'params' must be an object")
            result = _dispatch(request["method"], params)
        except _BridgeError as err:
            response = _response_err(req_id, err.code, err.message)
        except Exception as exc:  # pragma: no cover - defensive
            response = _response_err(req_id, _INTERNAL_ERROR,
                                     f"the bridge faltered: {exc!r}")
        else:
            if is_notification:
                continue
            response = _response_ok(req_id, result)
        if is_notification:
            continue
        stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        stdout.flush()
    return 0
