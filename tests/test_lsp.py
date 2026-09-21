"""Tests for the God Code language server (godcode/lsp.py).

Each test drives a real ``godcode lsp`` server over stdio with canned
JSON-RPC frames. All waits are bounded — nothing here may hang.
"""
from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading

import pytest

CMD = [sys.executable, "-m", "godcode", "lsp"]
TIMEOUT = 10  # seconds; generous but strictly bounded

BROKEN = "BEGIN CREATION\n  DECLARE x AS 1\n  DECLARE y\nEND CREATION\n"
CLEAN = "BEGIN CREATION\n  REVEAL(\"Let there be light\")\n  ASCEND\nEND CREATION\n"


def frame(message: dict) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


class ServerHarness:
    """A running ``godcode lsp`` subprocess with a message pump."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)
        self.inbox: queue.Queue = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()
        self._next_id = 0

    # -- transport -----------------------------------------------------
    def _pump(self) -> None:
        out = self.proc.stdout
        assert out is not None
        while True:
            headers: dict[str, str] = {}
            while True:
                line = out.readline()
                if not line:
                    self.inbox.put(None)  # EOF sentinel
                    return
                line = line.decode("latin-1").strip()
                if not line:
                    break
                name, _, value = line.partition(":")
                headers[name.strip().lower()] = value.strip()
            try:
                length = int(headers["content-length"])
            except (KeyError, ValueError):
                continue
            body = b""
            while len(body) < length:
                chunk = out.read(length - len(body))
                if not chunk:
                    self.inbox.put(None)
                    return
                body += chunk
            self.inbox.put(json.loads(body.decode("utf-8")))

    def send(self, message: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(frame(message))
        self.proc.stdin.flush()

    def request(self, method: str, params: dict | None = None) -> int:
        self._next_id += 1
        self.send({"jsonrpc": "2.0", "id": self._next_id,
                   "method": method, "params": params or {}})
        return self._next_id

    def notify(self, method: str, params: dict | None = None) -> None:
        self.send({"jsonrpc": "2.0", "method": method,
                   "params": params or {}})

    def wait_for(self, predicate, timeout: float = TIMEOUT) -> dict:
        """Wait for the next message matching predicate; fail on timeout."""
        import time
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                pytest.fail("timed out waiting for server message")
            try:
                message = self.inbox.get(timeout=remaining)
            except queue.Empty:
                pytest.fail("timed out waiting for server message")
            if message is None:
                pytest.fail("server closed stdout unexpectedly")
            if predicate(message):
                return message

    def wait_response(self, msg_id: int) -> dict:
        return self.wait_for(lambda m: m.get("id") == msg_id)

    def wait_notification(self, method: str) -> dict:
        return self.wait_for(lambda m: m.get("method") == method)

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                self.notify("exit")
            self.proc.wait(timeout=TIMEOUT)
        except (BrokenPipeError, OSError):
            pass
        finally:
            if self.proc.poll() is None:
                self.proc.kill()


@pytest.fixture()
def server():
    harness = ServerHarness()
    yield harness
    harness.close()


def did_open(uri: str, text: str) -> dict:
    return {"jsonrpc": "2.0", "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": uri, "text": text}}}


# ---------------------------------------------------------------------------
# handshake
# ---------------------------------------------------------------------------

def test_initialize_returns_capabilities(server: ServerHarness) -> None:
    msg_id = server.request("initialize", {})
    response = server.wait_response(msg_id)
    assert "error" not in response
    caps = response["result"]["capabilities"]
    assert caps["textDocumentSync"] == 1
    assert caps["hoverProvider"] is True
    assert caps["completionProvider"]["triggerCharacters"] == []
    server.notify("initialized")


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------

def test_did_open_broken_program_reports_error_line(server: ServerHarness) -> None:
    server.notify("initialize")  # handshake not required, tolerated
    server.send(did_open("file:///broken.god", BROKEN))
    note = server.wait_notification("textDocument/publishDiagnostics")
    params = note["params"]
    assert params["uri"] == "file:///broken.god"
    diags = params["diagnostics"]
    assert len(diags) == 1
    diag = diags[0]
    assert diag["severity"] == 1
    # `DECLARE y` is on source line 3 -> LSP line 2 (0-based)
    assert diag["range"]["start"]["line"] == 2
    assert diag["range"]["end"]["line"] == 2
    assert diag["range"]["end"]["character"] > \
        diag["range"]["start"]["character"]
    assert "AS" in diag["message"]


def test_did_open_clean_program_reports_no_diagnostics(server: ServerHarness) -> None:
    server.send(did_open("file:///clean.god", CLEAN))
    note = server.wait_notification("textDocument/publishDiagnostics")
    assert note["params"]["diagnostics"] == []


def test_did_change_updates_diagnostics(server: ServerHarness) -> None:
    uri = "file:///changing.god"
    server.send(did_open(uri, CLEAN))
    note = server.wait_notification("textDocument/publishDiagnostics")
    assert note["params"]["diagnostics"] == []
    server.notify("textDocument/didChange",
                  {"textDocument": {"uri": uri},
                   "contentChanges": [{"text": BROKEN}]})
    note = server.wait_notification("textDocument/publishDiagnostics")
    diags = note["params"]["diagnostics"]
    assert len(diags) == 1
    assert diags[0]["severity"] == 1


# ---------------------------------------------------------------------------
# hover
# ---------------------------------------------------------------------------

def test_hover_on_reveal_returns_markdown(server: ServerHarness) -> None:
    uri = "file:///hover.god"
    server.send(did_open(uri, CLEAN))
    server.wait_notification("textDocument/publishDiagnostics")
    # CLEAN line 1 is `  REVEAL("Let there be light")`; character 4 is on REVEAL
    msg_id = server.request(
        "textDocument/hover",
        {"textDocument": {"uri": uri},
         "position": {"line": 1, "character": 4}})
    response = server.wait_response(msg_id)
    result = response["result"]
    assert result is not None
    contents = result["contents"]
    assert contents["kind"] == "markdown"
    assert "**REVEAL**" in contents["value"]
    assert "Speak a value aloud" in contents["value"]


def test_hover_on_begin_creation_phrase(server: ServerHarness) -> None:
    uri = "file:///phrase.god"
    server.send(did_open(uri, CLEAN))
    server.wait_notification("textDocument/publishDiagnostics")
    msg_id = server.request(
        "textDocument/hover",
        {"textDocument": {"uri": uri},
         "position": {"line": 0, "character": 8}})
    response = server.wait_response(msg_id)
    value = response["result"]["contents"]["value"]
    assert "**BEGIN CREATION**" in value


def test_hover_on_unknown_word_returns_null(server: ServerHarness) -> None:
    uri = "file:///unknown.god"
    server.send(did_open(uri, CLEAN))
    server.wait_notification("textDocument/publishDiagnostics")
    # character 20 on line 1 is inside the string literal, not a word
    msg_id = server.request(
        "textDocument/hover",
        {"textDocument": {"uri": uri},
         "position": {"line": 1, "character": 20}})
    response = server.wait_response(msg_id)
    assert response["result"] is None


# ---------------------------------------------------------------------------
# completion
# ---------------------------------------------------------------------------

def test_completion_returns_keywords_and_snippets(server: ServerHarness) -> None:
    uri = "file:///complete.god"
    server.send(did_open(uri, CLEAN))
    server.wait_notification("textDocument/publishDiagnostics")
    msg_id = server.request(
        "textDocument/completion",
        {"textDocument": {"uri": uri},
         "position": {"line": 1, "character": 2}})
    response = server.wait_response(msg_id)
    items = response["result"]
    by_label = {item["label"]: item for item in items}
    # keywords
    assert "REVEAL" in by_label
    assert "ASCEND" in by_label
    assert "DECLARE" in by_label
    assert by_label["REVEAL"]["insertText"] == "REVEAL"
    assert by_label["REVEAL"]["kind"] == 14
    # built-ins
    assert "LEN" in by_label
    assert "RANGE" in by_label
    # snippet-style items
    snippets = [i for i in items if i.get("insertTextFormat") == 2]
    assert snippets, "expected snippet completions"
    creation = by_label["BEGIN CREATION … END CREATION"]
    assert "BEGIN CREATION" in creation["insertText"]
    assert creation["detail"]


# ---------------------------------------------------------------------------
# robustness
# ---------------------------------------------------------------------------

def test_unknown_method_returns_jsonrpc_error(server: ServerHarness) -> None:
    msg_id = server.request("textDocument/unknownRite", {})
    response = server.wait_response(msg_id)
    assert response["error"]["code"] == -32601
    assert "Method not found" in response["error"]["message"]


def test_malformed_frame_does_not_kill_server(server: ServerHarness) -> None:
    assert server.proc.stdin is not None
    server.proc.stdin.write(b"Content-Length: banana\r\n\r\n")
    server.proc.stdin.flush()
    # the server must keep serving afterwards
    msg_id = server.request("initialize", {})
    response = server.wait_response(msg_id)
    assert "error" not in response
    assert response["result"]["capabilities"]["hoverProvider"] is True


def test_shutdown_and_exit(server: ServerHarness) -> None:
    msg_id = server.request("shutdown", {})
    response = server.wait_response(msg_id)
    assert response["result"] is None
    server.notify("exit")
    assert server.proc.wait(timeout=TIMEOUT) == 0
