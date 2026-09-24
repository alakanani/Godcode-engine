"""Tests for the God Code interactive debugger (v5.0).

Covers ``godcode/debugger.py`` (DebugSession), ``godcode/debug_cli.py``
(the ``godcode debug`` command), and ``godcode/dap.py`` (the DAP server).

Conventions:
  * Plugins are disabled (GODCODE_NO_PLUGINS=1) so runs are hermetic.
  * Session tests drive DebugSession programmatically with a scripted
    on_pause driver that records pauses and auto-resumes.
  * CLI tests run ``python3 -m godcode debug`` in a subprocess with piped
    stdin. Fixtures are written with the tmp_path pytest fixture.
  * The DAP test is fully in-process over two socket pairs; the adapter's
    serve() loop runs on a worker thread. We never send ``disconnect``
    (it calls os._exit).
"""

import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

os.environ["GODCODE_NO_PLUGINS"] = "1"

import pytest

from godcode.dap import DebugAdapter
from godcode.debugger import DebugSession
from godcode.interpreter import Interpreter

REPO = Path(__file__).resolve().parent.parent

# A small scroll with a rite call. Line numbers are load-bearing:
#   1: BEGIN CREATION
#   2: DECLARE x
#   3: DEFINE RITE greet
#   4:   REVEAL inside the rite
#   5: END RITE
#   6: INVOKE greet
#   7: REVEAL("done")
#   8: END CREATION
SCRIPT = """\
BEGIN CREATION
  DECLARE x AS 1
  DEFINE RITE greet(name)
    REVEAL("hello {name}")
  END RITE
  INVOKE greet("world")
  REVEAL("done")
END CREATION
"""


def _write_scroll(tmp_path, name="scroll.god", text=SCRIPT):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _run_session(path, *, stop_on_entry=False, breakpoints=(), driver):
    interp = Interpreter(log_path=None)
    session = DebugSession()
    driver.session = session
    session.on_pause = driver.on_pause
    session.stop_on_entry = stop_on_entry
    for line in breakpoints:
        session.add_breakpoint(path, line)
    session.attach(interp)
    session.run_file(path)
    return interp, session


class _Driver:
    """Scripted on_pause: records every pause, answers from a plan.

    plan: a list of resume actions consumed in order (falls back to
    "continue" when exhausted), or plan_fn(pause_info) -> action.
    """

    def __init__(self, session=None, plan=(), plan_fn=None):
        self.session = session
        self.plan = list(plan)
        self.plan_fn = plan_fn
        self.pauses = []

    def on_pause(self, pause_info):
        frame = pause_info["frame"]
        self.pauses.append(
            {
                "reason": pause_info["reason"],
                "line": pause_info["line"],
                "frame": frame.name,
                "depth": len(pause_info["frames"]),
                "info": pause_info,
            }
        )
        if self.plan_fn is not None:
            action = self.plan_fn(pause_info)
        elif self.plan:
            action = self.plan.pop(0)
        else:
            action = "continue"
        self.session.resume(action)

    def summary(self):
        return [
            (p["reason"], p["line"], p["frame"]) for p in self.pauses
        ]


# ------------------------------------------------------- session unit tests


def test_breakpoint_hit_pauses_once_then_finishes(tmp_path):
    path = _write_scroll(tmp_path)
    driver = _Driver()
    interp, session = _run_session(path, breakpoints=(7,), driver=driver)
    assert driver.summary() == [("breakpoint", 7, "<creation>")]
    assert session.pause_count == 1
    assert session.finished is True
    assert session.error is None
    assert interp.output == ["hello world", "done"]


def test_stepping_order_step_over_skips_rite_body(tmp_path):
    path = _write_scroll(tmp_path)
    driver = _Driver(
        plan=["step_over", "step_over", "step_over", "step_in", "continue"]
    )
    _run_session(path, stop_on_entry=True, driver=driver)
    assert driver.summary() == [
        ("entry", 1, "<creation>"),
        ("step", 2, "<creation>"),
        ("step", 3, "<creation>"),
        ("step", 6, "<creation>"),  # step_over: the rite body never pauses
        ("step", 4, "greet"),  # step_in: descends into the rite
    ]


def test_step_out_returns_to_caller_frame(tmp_path):
    path = _write_scroll(tmp_path)

    def plan_fn(pause_info):
        if pause_info["frame"].name == "greet":
            return "step_out"
        return "continue"

    driver = _Driver(plan_fn=plan_fn)
    _run_session(path, breakpoints=(4,), driver=driver)
    assert driver.summary() == [
        ("breakpoint", 4, "greet"),
        ("step", 7, "<creation>"),  # next pause is back in the caller
    ]


def test_locals_inspection_inside_rite(tmp_path):
    path = _write_scroll(tmp_path)
    captured = {}

    driver = _Driver()
    orig_on_pause = driver.on_pause

    def on_pause(pause_info):
        orig_on_pause(pause_info)
        frame = pause_info["frame"]
        captured["locals"] = dict(driver.session.frame_locals(frame))
        captured["found"], captured["value"] = driver.session.lookup("name")
        captured["missing"] = driver.session.lookup("no_such_name")

    driver.on_pause = on_pause
    _run_session(path, breakpoints=(4,), driver=driver)

    assert driver.summary() == [("breakpoint", 4, "greet")]
    assert captured["locals"]["name"] == "world"  # the rite param is visible
    assert captured["found"] is True
    assert captured["value"] == "world"
    assert captured["missing"] == (False, None)


def test_stack_frames_show_creation_then_rite(tmp_path):
    path = _write_scroll(tmp_path)
    captured = {}

    driver = _Driver()
    orig_on_pause = driver.on_pause

    def on_pause(pause_info):
        orig_on_pause(pause_info)
        session = driver.session
        captured["names"] = [f.name for f in session.frames]
        captured["depths"] = [f.depth for f in session.frames]
        captured["depth"] = session.depth

    driver.on_pause = on_pause
    _run_session(path, breakpoints=(4,), driver=driver)

    assert captured["names"] == ["<creation>", "greet"]
    assert captured["depths"] == [1, 2]  # depth increments on enter_rite
    assert captured["depth"] == 2


def test_breakpoints_add_remove_clear_per_source(tmp_path):
    scroll_a = _write_scroll(tmp_path, name="a.god")
    scroll_b = _write_scroll(tmp_path, name="b.god")
    session = DebugSession()

    session.add_breakpoint(scroll_a, 5)
    assert session.breakpoints_for(scroll_a) == {5}

    session.add_breakpoint(scroll_a, 7)
    session.remove_breakpoint(scroll_a, 5)
    assert session.breakpoints_for(scroll_a) == {7}

    # removing a line that was never set is a no-op
    session.remove_breakpoint(scroll_a, 42)
    assert session.breakpoints_for(scroll_a) == {7}

    # clearing one source leaves the other alone
    session.add_breakpoint(scroll_b, 2)
    session.clear_breakpoints(scroll_a)
    assert session.breakpoints_for(scroll_a) == set()
    assert session.breakpoints_for(scroll_b) == {2}

    # clearing everything
    session.clear_breakpoints()
    assert session.breakpoints_for(scroll_b) == set()
    assert session.breakpoints == {}


# ----------------------------------------------------------------- CLI tests


def _debug_cli(scroll, stdin_text):
    """Run ``python3 -m godcode debug <scroll>`` with piped stdin."""
    env = dict(os.environ)
    env["GODCODE_NO_PLUGINS"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "godcode", "debug", str(scroll)],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        timeout=60,
    )


CLI_SCROLL = """\
BEGIN CREATION
  DECLARE greeting AS "hello debugger"
  REVEAL(greeting)
END CREATION
"""


def test_cli_breakpoint_pause_and_quit(tmp_path):
    scroll = _write_scroll(tmp_path, text=CLI_SCROLL)
    proc = _debug_cli(scroll, "break 2\ncontinue\nquit\n")
    assert proc.returncode == 0
    assert "paused at" in proc.stdout
    assert "breakpoint" in proc.stdout
    # the breakpoint line itself is shown with a marker
    assert 'DECLARE greeting AS "hello debugger"' in proc.stdout


def test_cli_locals_shows_declared_variable(tmp_path):
    scroll = _write_scroll(tmp_path, text=CLI_SCROLL)
    proc = _debug_cli(scroll, "break 3\ncontinue\nlocals\nquit\n")
    assert proc.returncode == 0
    assert "greeting" in proc.stdout
    assert "hello debugger" in proc.stdout


def test_cli_missing_file_exits_1(tmp_path):
    missing = tmp_path / "no_such_scroll.god"
    proc = _debug_cli(str(missing), "quit\n")
    assert proc.returncode == 1
    assert "cannot read" in proc.stderr


# ----------------------------------------------------------------- DAP test


def _dap_frame(message: dict) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return (
        f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
    )


class _DapClient:
    """Minimal in-process DAP client over two socket pairs."""

    def __init__(self, scroll):
        self.scroll = scroll
        req_r, self._req_w = socket.socketpair()  # client -> adapter
        self._resp_r, resp_w = socket.socketpair()  # adapter -> client
        self._adapter = DebugAdapter(
            stdin=req_r.makefile("rb"), stdout=resp_w.makefile("wb")
        )
        self._in = self._resp_r.makefile("rb")
        self._resp_r.settimeout(20)
        self._out = self._req_w.makefile("wb")
        self._seq = 0
        self._thread = threading.Thread(
            target=self._adapter.serve, daemon=True, name="dap-test-server"
        )

    def start(self):
        self._thread.start()

    def send(self, command, arguments=None):
        self._seq += 1
        self._out.write(
            _dap_frame(
                {
                    "seq": self._seq,
                    "type": "request",
                    "command": command,
                    "arguments": arguments or {},
                }
            )
        )
        self._out.flush()
        return self._seq

    def read(self):
        """Read one framed message from the adapter."""
        headers = {}
        while True:
            line = self._in.readline()
            assert line, "EOF from the debug adapter"
            line = line.decode("latin-1").strip()
            if not line:
                break
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        length = int(headers["content-length"])
        body = b""
        while len(body) < length:
            chunk = self._in.read(length - len(body))
            assert chunk, "truncated frame from the debug adapter"
            body += chunk
        return json.loads(body.decode("utf-8"))

    def close(self):
        self._out.close()
        self._req_w.shutdown(socket.SHUT_WR)  # EOF for serve()
        self._thread.join(timeout=10)
        assert not self._thread.is_alive(), "adapter thread did not stop"


def test_dap_round_trip(tmp_path):
    scroll = _write_scroll(tmp_path, name="dap.god", text=CLI_SCROLL)
    client = _DapClient(scroll)
    try:
        client.start()
        client.send("initialize", {"adapterID": "godcode"})
        client.send(
            "launch", {"program": scroll, "stopOnEntry": True}
        )
        client.send(
            "setBreakpoints",
            {
                "source": {"path": scroll},
                "breakpoints": [{"line": 3}],
            },
        )
        client.send("configurationDone")

        # Collect until every launch-phase message plus the entry stop
        # has arrived (the worker's stopped event may interleave).
        responses = {}
        entry_stop = None
        want = {"initialize", "launch", "setBreakpoints", "configurationDone"}
        while not (want <= set(responses) and entry_stop is not None):
            message = client.read()
            if message.get("type") == "response":
                responses[message["command"]] = message
            elif (
                message.get("type") == "event"
                and message.get("event") == "stopped"
            ):
                body = message.get("body", {})
                if body.get("reason") == "entry":
                    entry_stop = message

        # initialize: capabilities are present
        init_body = responses["initialize"]["body"]
        assert "capabilities" in init_body
        assert init_body["capabilities"]["supportsConfigurationDoneRequest"] is True

        # launch and configuration handshake answered fine
        assert responses["launch"]["success"] is True
        assert responses["configurationDone"]["success"] is True

        # setBreakpoints verified the requested line
        bp_body = responses["setBreakpoints"]["body"]["breakpoints"]
        assert [bp["line"] for bp in bp_body] == [3]
        assert all(bp["verified"] for bp in bp_body)

        # the stopped event carries reason "entry"
        assert entry_stop["body"]["threadId"] == 1

        # threads
        client.send("threads", {"threadId": 1})
        threads = _response_body(client, "threads")
        assert threads["threads"] == [{"id": 1, "name": "creation"}]

        # stackTrace: sane shape, creation frame at the bottom
        client.send("stackTrace", {"threadId": 1})
        stack = _response_body(client, "stackTrace")
        frames = stack["stackFrames"]
        assert len(frames) >= 1
        assert frames[0]["name"] == "<creation>"
        assert isinstance(frames[0]["line"], int)
        assert frames[0]["source"]["path"] == scroll
        assert stack["totalFrames"] == len(frames)

        # scopes -> variables: sane shapes
        client.send("scopes", {"frameId": 0})
        scopes = _response_body(client, "scopes")["scopes"]
        assert scopes and scopes[0]["name"] == "Locals"
        var_ref = scopes[0]["variablesReference"]
        assert var_ref != 0

        client.send("variables", {"variablesReference": var_ref})
        variables = _response_body(client, "variables")["variables"]
        assert isinstance(variables, list)
        for var in variables:
            assert {"name", "value", "type"} <= set(var)

        # continue: the pending breakpoint fires next
        client.send("continue", {"threadId": 1})
        bp_stop = _wait_event(client, "stopped")
        assert bp_stop["body"]["reason"] == "breakpoint"

        # the declared variable is visible through evaluate at the stop
        client.send(
            "evaluate", {"expression": "greeting", "frameId": 0}
        )
        evaluation = _response_body(client, "evaluate")
        assert "hello debugger" in evaluation["result"]

        # continue: the program runs to completion
        client.send("continue", {"threadId": 1})
        terminated = _wait_event(client, "terminated")
        assert terminated["event"] == "terminated"
    finally:
        client.close()


def _response_body(client, command):
    """Read messages until the response for `command` arrives."""
    while True:
        message = client.read()
        if message.get("type") == "response" and message.get("command") == command:
            assert message["success"] is True, message
            return message.get("body", {})


def _wait_event(client, event):
    """Read messages until an event named `event` arrives."""
    while True:
        message = client.read()
        if message.get("type") == "event" and message.get("event") == event:
            return message
