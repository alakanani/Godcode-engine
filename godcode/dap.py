"""Debug Adapter Protocol server for God Code (v5.0).

A minimal DAP implementation over stdio, hand-rolled on top of the stdlib.
Messages are framed with ``Content-Length`` headers, exactly like
:mod:`godcode.lsp`.

Lifecycle::

    godcode dap                       # start serving on stdin/stdout

The message loop runs on the main thread. ``launch`` builds an interpreter
the same way ``godcode run`` does, attaches a
:class:`godcode.debugger.DebugSession`, and starts the scroll on a daemon
worker thread. Pauses surface as ``stopped`` events; the worker thread
blocks inside the session until a ``continue`` / ``next`` / ``stepIn`` /
``stepOut`` request resumes it.

Protocol notes:
  * All logging goes to stderr. stdout is the protocol channel. Nothing
    else may ever be written there (REVEAL output is forwarded as DAP
    ``output`` events instead).
  * Unknown commands answer with JSON-RPC error -32601 ("Method not found").
  * Malformed frames are skipped; the server keeps serving.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import threading

from godcode.debugger import DebugSession
from godcode.errors import GodCodeError

# A handler that already sent its own response returns this, so the
# dispatcher does not answer twice (used by launch and disconnect).
_HANDLED = object()

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")

_CAPABILITIES = {
    "supportsConfigurationDoneRequest": True,
    "supportsEvaluateForHovers": False,
}


def _log(message: str) -> None:
    sys.stderr.write(f"[godcode-dap] {message}\n")
    sys.stderr.flush()


class DebugAdapter:
    """Hand-rolled DAP server over stdio."""

    def __init__(self,
                 stdin: io.BufferedReader | None = None,
                 stdout: io.BufferedWriter | None = None) -> None:
        self.stdin = stdin or sys.stdin.buffer
        self.stdout = stdout or sys.stdout.buffer
        self._write_lock = threading.Lock()
        self._seq = 0
        self._session: DebugSession | None = None
        self._worker: threading.Thread | None = None
        self._pending_breakpoints: dict[str, set[int]] = {}
        # Variable references: id -> ("frame_locals", frame_id)
        #                   or ("value", python_value). Allocated from 1.
        self._var_refs: dict[int, tuple] = {}
        self._next_var_ref = 1
        self._handlers = {
            "initialize": self._on_initialize,
            "launch": self._on_launch,
            "configurationDone": self._on_configuration_done,
            "setBreakpoints": self._on_set_breakpoints,
            "threads": self._on_threads,
            "stackTrace": self._on_stack_trace,
            "scopes": self._on_scopes,
            "variables": self._on_variables,
            "evaluate": self._on_evaluate,
            "continue": self._on_continue,
            "next": self._on_next,
            "stepIn": self._on_step_in,
            "stepOut": self._on_step_out,
            "disconnect": self._on_disconnect,
        }

    # ------------------------------------------------------------ transport
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

    def _next_seq(self) -> int:
        with self._write_lock:
            self._seq += 1
            return self._seq

    def _write(self, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        frame = (f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
                 + body)
        with self._write_lock:
            self.stdout.write(frame)
            self.stdout.flush()

    def _send_response(self, request_seq, command: str,
                       success: bool = True,
                       body: dict | None = None,
                       message: str = "") -> None:
        payload: dict = {
            "seq": self._next_seq(),
            "type": "response",
            "request_seq": request_seq,
            "success": success,
            "command": command,
        }
        if success:
            if body is not None:
                payload["body"] = body
        elif message:
            payload["message"] = message
        self._write(payload)

    def _send_event(self, event: str, body: dict | None = None) -> None:
        payload: dict = {
            "seq": self._next_seq(),
            "type": "event",
            "event": event,
        }
        if body is not None:
            payload["body"] = body
        self._write(payload)

    def _send_jsonrpc_error(self, msg_id, code: int,
                            message: str) -> None:
        self._write({"jsonrpc": "2.0", "id": msg_id,
                     "error": {"code": code, "message": message}})

    def _send_output(self, text: str, category: str = "stdout") -> None:
        if not text.endswith("\n"):
            text += "\n"
        self._send_event("output",
                         {"category": category, "output": text})

    # ------------------------------------------------------------ main loop
    def serve(self) -> int:
        _log("the debug adapter opens (stdio)")
        while True:
            message = self._read_message()
            if message is None:
                _log("stdin closed; ascending")
                return 0
            if not message:
                continue  # malformed frame: already logged, keep serving
            self._dispatch(message)

    def _dispatch(self, message: dict) -> None:
        command = message.get("command") or message.get("method")
        seq = message.get("seq", message.get("id"))
        if not command:
            _log("message with no command; ignoring")
            return
        handler = self._handlers.get(command)
        if handler is None:
            _log(f"unknown command: {command!r}")
            if seq is not None:
                self._send_jsonrpc_error(seq, -32601,
                                         f"Method not found: {command}")
            return
        args = message.get("arguments") or message.get("params") or {}
        try:
            result = handler(seq, command, args)
        except Exception as exc:  # never let a handler kill the server
            _log(f"handler for {command} failed: {exc}")
            if seq is not None:
                self._send_response(seq, command, success=False,
                                    message=str(exc))
            return
        if result is _HANDLED or seq is None:
            return
        self._send_response(seq, command, success=True, body=result)

    # ------------------------------------------------------ session helpers
    def _require_session(self) -> DebugSession:
        if self._session is None:
            raise RuntimeError("no program is launched")
        return self._session

    def _frames_innermost_first(self) -> list:
        session = self._session
        if session is None:
            return []
        return list(reversed(session.frames))

    def _frame_by_id(self, frame_id: int):
        frames = self._frames_innermost_first()
        if 0 <= frame_id < len(frames):
            return frames[frame_id]
        return None

    def _alloc_var_ref(self, entry: tuple) -> int:
        ref = self._next_var_ref
        self._next_var_ref += 1
        self._var_refs[ref] = entry
        return ref

    @staticmethod
    def _children_of(value) -> list[tuple[str, object]]:
        if isinstance(value, list):
            return [(str(i), item) for i, item in enumerate(value)]
        if isinstance(value, dict):
            return [(str(key), item) for key, item in value.items()]
        return []

    def _variable(self, name: str, value) -> dict:
        session = self._require_session()
        ref = 0
        if isinstance(value, (list, dict)):
            ref = self._alloc_var_ref(("value", value))
        return {
            "name": str(name),
            "value": session.render_value(value),
            "type": session.type_name(value),
            "variablesReference": ref,
        }

    # -------------------------------------------------------------- handlers
    def _on_initialize(self, seq, command, args: dict):  # noqa: ARG002
        _log("initialize received")
        result = {"capabilities": dict(_CAPABILITIES)}
        # Respond first so the client sees a clean handshake ordering.
        self._send_response(seq, command, success=True, body=result)
        self._send_event("initialized")
        return _HANDLED

    def _on_launch(self, seq, command, args: dict):
        if self._session is not None:
            raise RuntimeError("a program is already launched")
        program = args.get("program")
        if not program:
            raise RuntimeError("launch requires a 'program' path")
        stop_on_entry = args.get("stopOnEntry", True)
        _log(f"launch: {program} (stopOnEntry={stop_on_entry})")

        from godcode.cli import _make_interpreter

        interpreter = _make_interpreter(None)
        session = DebugSession()
        for path, lines in self._pending_breakpoints.items():
            for line in sorted(lines):
                session.add_breakpoint(path, line)
        self._pending_breakpoints.clear()

        original_emit = interpreter.emit

        def _emit(line: str, _orig=original_emit) -> None:
            _orig(line)  # printed, as `godcode run` does
            self._send_output(str(line), category="stdout")

        interpreter.emit = _emit
        session.on_pause = self._on_pause
        session.attach(interpreter)
        session.stop_on_entry = bool(stop_on_entry)
        self._session = session

        # Answer before the worker starts, so the client never sees a
        # stopped event ahead of the launch response.
        self._send_response(seq, command, success=True, body={})
        worker = threading.Thread(
            target=self._run_program,
            args=(session, str(program)),
            daemon=True,
            name="godcode-dap-worker",
        )
        self._worker = worker
        worker.start()
        return _HANDLED

    def _run_program(self, session: DebugSession, program: str) -> None:
        try:
            session.run_file(program)
        except GodCodeError as err:
            _log(f"program error: {err}")
            self._send_output(str(err), category="stderr")
            self._send_event("terminated")
            return
        except Exception as err:  # noqa: BLE001 - never die silently
            _log(f"worker failed: {err}")
            self._send_output(f"{type(err).__name__}: {err}",
                              category="stderr")
            self._send_event("terminated")
            return
        _log("program finished")
        self._send_event("terminated")
        self._send_event("exited", {"exitCode": 0})

    def _on_pause(self, pause_info: dict) -> None:
        reason = pause_info.get("reason", "pause")
        line = pause_info.get("line")
        source = pause_info.get("source")
        _log(f"paused: {reason} at {source}:{line}")
        # The session blocks inside _pause until a request handler calls
        # session.resume(); this handler only announces the stop.
        self._send_event("stopped", {
            "reason": reason,
            "threadId": 1,
            "allThreadsStopped": True,
        })

    def _on_configuration_done(self, seq, command,  # noqa: ARG002
                               args: dict):  # noqa: ARG002
        _log("configuration done")
        return {}

    def _on_set_breakpoints(self, seq, command, args: dict):  # noqa: ARG002
        source = args.get("source") or {}
        path = source.get("path", "")
        lines: list[int] = []
        for bp in args.get("breakpoints") or []:
            line = (bp or {}).get("line")
            if isinstance(line, int):
                lines.append(line)
        if self._session is not None:
            self._session.clear_breakpoints(path)
            for line in lines:
                self._session.add_breakpoint(path, line)
        else:
            # Arrived before launch; applied when the session is created.
            self._pending_breakpoints[path] = set(lines)
        norm = DebugSession._norm(path) if path else ""
        _log(f"breakpoints for {norm or path}: {lines}")
        return {"breakpoints": [
            {"verified": True, "line": n,
             "source": {"name": os.path.basename(norm) if norm else "",
                        "path": norm}}
            for n in lines
        ]}

    def _on_threads(self, seq, command, args: dict):  # noqa: ARG002
        return {"threads": [{"id": 1, "name": "creation"}]}

    def _on_stack_trace(self, seq, command, args: dict):  # noqa: ARG002
        out = []
        for i, frame in enumerate(self._frames_innermost_first()):
            src = frame.source or ""
            out.append({
                "id": i,
                "name": frame.name,
                "line": frame.line or 1,
                "column": 1,
                "source": {
                    "name": os.path.basename(src) if src else "scroll",
                    "path": src,
                },
            })
        return {"stackFrames": out, "totalFrames": len(out)}

    def _on_scopes(self, seq, command, args: dict):  # noqa: ARG002
        frame_id = args.get("frameId", 0)
        ref = self._alloc_var_ref(("frame_locals", frame_id))
        return {"scopes": [
            {"name": "Locals", "variablesReference": ref,
             "expensive": False}
        ]}

    def _on_variables(self, seq, command, args: dict):  # noqa: ARG002
        entry = self._var_refs.get(args.get("variablesReference", 0))
        pairs: list[tuple[str, object]] = []
        if entry is not None:
            if entry[0] == "frame_locals":
                frame = self._frame_by_id(entry[1])
                if frame is not None:
                    pairs = self._require_session().frame_locals(frame)
            elif entry[0] == "value":
                pairs = self._children_of(entry[1])
        return {"variables": [self._variable(name, value)
                              for name, value in pairs[:50]]}

    def _on_evaluate(self, seq, command, args: dict):  # noqa: ARG002
        session = self._require_session()
        expr = str(args.get("expression", "")).strip()
        frame = self._frame_by_id(args.get("frameId", 0))
        name = expr if _IDENT_RE.match(expr) else None
        if name is not None:
            found, value = session.lookup(name, frame)
            if found:
                return {
                    "result": session.render_value(value),
                    "type": session.type_name(value),
                    "variablesReference": 0,
                }
        return {"result": f"no '{expr}' is bound here.",
                "variablesReference": 0}

    def _on_continue(self, seq, command, args: dict):  # noqa: ARG002
        self._require_session().resume("continue")
        return {"allThreadsContinued": True}

    def _on_next(self, seq, command, args: dict):  # noqa: ARG002
        self._require_session().resume("step_over")
        return {"allThreadsContinued": True}

    def _on_step_in(self, seq, command, args: dict):  # noqa: ARG002
        self._require_session().resume("step_in")
        return {"allThreadsContinued": True}

    def _on_step_out(self, seq, command, args: dict):  # noqa: ARG002
        self._require_session().resume("step_out")
        return {"allThreadsContinued": True}

    def _on_disconnect(self, seq, command, args: dict):  # noqa: ARG002
        self._send_response(seq, command, success=True, body={})
        _log("disconnect; ascending")
        os._exit(0)


def serve() -> int:
    """Entry point for ``godcode dap``."""
    return DebugAdapter().serve()
