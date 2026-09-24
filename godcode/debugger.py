"""Interactive debugging for God Code (v5.0).

A :class:`DebugSession` plugs into the interpreter through the small hook
surface on ``Interpreter`` (``interpreter.debugger``):

* ``before_stmt(stmt, env)`` — called before every statement executes.
* ``enter_rite(rite, env)`` / ``exit_rite(rite)`` — around rite bodies.
* ``enter_file(path)`` / ``exit_file()`` — around imported scrolls.

When a pause condition is met (breakpoint, step, or stop-on-entry) the
session calls ``on_pause(pause_info)`` and blocks until the driver calls
``resume(action)``. The CLI driver answers inline; the DAP driver answers
from its message loop while the program runs on a worker thread.

Hook contract for driver authors::

    session = DebugSession()
    session.on_pause = my_handler          # must call session.resume(action)
    session.add_breakpoint("/path/scroll.god", 12)
    session.attach(interpreter)            # sets interpreter.debugger
    session.stop_on_entry = True           # pause at the first statement
    session.run_file("/path/scroll.god")   # lex, parse, run, manage sources

Resume actions: ``"continue"``, ``"step_in"``, ``"step_over"``,
``"step_out"``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

RESUME_ACTIONS = ("continue", "step_in", "step_over", "step_out")

_PAUSE_BREAKPOINT = "breakpoint"
_PAUSE_STEP = "step"
_PAUSE_ENTRY = "entry"


@dataclass
class DebugFrame:
    """One frame of the paused call stack."""

    name: str  # rite name, or "<creation>" for the top level
    env: Any = None  # godcode.environment.Environment
    stmt: Any = None  # statement about to execute (or None)
    source: str = ""
    depth: int = 0

    @property
    def line(self) -> int | None:
        return getattr(self.stmt, "line", None)


class DebugSession:
    """Drives a paused/stepped run of a God Code program."""

    def __init__(self) -> None:
        self.breakpoints: dict[str, set[int]] = {}
        self.frames: list[DebugFrame] = []
        self.on_pause: Callable[[dict], None] | None = None
        self.stop_on_entry = False
        self.interpreter = None
        # stepping state
        self._step_mode = "run"  # run | step_in | step_over | step_out
        self._step_depth = 0
        self._pause_once = False
        # sources
        self._source_stack: list[str] = []
        # pause machinery
        self._resume_event = threading.Event()
        self._resume_event.set()
        self.resume_action = "continue"
        self.pause_info: dict | None = None
        self.pause_count = 0
        self.finished = False
        self.error: Any = None

    # ------------------------------------------------------------ breakpoints

    @staticmethod
    def _norm(source: str) -> str:
        try:
            return str(Path(source).resolve())
        except OSError:
            return str(source)

    def add_breakpoint(self, source: str, line: int) -> None:
        self.breakpoints.setdefault(self._norm(source), set()).add(int(line))

    def remove_breakpoint(self, source: str, line: int) -> None:
        self.breakpoints.get(self._norm(source), set()).discard(int(line))

    def clear_breakpoints(self, source: str | None = None) -> None:
        if source is None:
            self.breakpoints.clear()
        else:
            self.breakpoints.pop(self._norm(source), None)

    def breakpoints_for(self, source: str) -> set[int]:
        return set(self.breakpoints.get(self._norm(source), set()))

    # ----------------------------------------------------------------- sources

    @property
    def current_source(self) -> str:
        return self._source_stack[-1] if self._source_stack else ""

    def push_source(self, source: str) -> None:
        self._source_stack.append(self._norm(source))

    def pop_source(self) -> None:
        if self._source_stack:
            self._source_stack.pop()

    # ------------------------------------------------------------------ attach

    def attach(self, interpreter) -> "DebugSession":
        """Plug this session into an interpreter's hook surface."""
        self.interpreter = interpreter
        interpreter.debugger = self
        return self

    def detach(self) -> None:
        if self.interpreter is not None:
            self.interpreter.debugger = None
        self.interpreter = None

    # --------------------------------------------------------------------- run

    def run_file(self, path: str | Path):
        """Lex, parse, and run a scroll under this session.

        Returns the interpreter. Runtime errors propagate to the caller;
        ``self.error`` records them and ``self.finished`` is set either way.
        """
        from godcode.lexer import Lexer
        from godcode.parser import Parser

        if self.interpreter is None:
            raise RuntimeError("DebugSession has no interpreter — call attach() first.")
        resolved = str(Path(path).resolve())
        source = Path(path).read_text(encoding="utf-8")
        program = Parser(Lexer(source).lex()).parse()
        if self.stop_on_entry:
            self._pause_once = True
        self.push_source(resolved)
        try:
            self.interpreter.run(program, source_name=resolved)
        except Exception as err:  # noqa: BLE001 - recorded for the driver
            self.error = err
            raise
        finally:
            self.pop_source()
            self.finished = True
        return self.interpreter

    # ---------------------------------------------------------- interpreter hooks

    @property
    def depth(self) -> int:
        return len(self.frames)

    def _current_frame(self, env) -> DebugFrame:
        if not self.frames:
            self.frames.append(
                DebugFrame(name="<creation>", env=env,
                           source=self.current_source, depth=1)
            )
        frame = self.frames[-1]
        frame.env = env
        return frame

    def before_stmt(self, stmt, env) -> None:
        frame = self._current_frame(env)
        frame.stmt = stmt
        reason = self._pause_reason(stmt)
        if reason is not None:
            self._pause(reason, stmt, frame)

    def enter_rite(self, rite, env) -> None:
        self.frames.append(
            DebugFrame(name=getattr(rite, "name", "<rite>"), env=env,
                       source=self.current_source,
                       depth=len(self.frames) + 1)
        )

    def exit_rite(self, rite) -> None:
        if self.frames:
            self.frames.pop()
        # step_out lands on the next statement back in the caller.
        if self._step_mode == "step_out" and len(self.frames) < self._step_depth:
            self._step_mode = "step_over"
            self._step_depth = len(self.frames)
            self._pause_once = True

    def enter_file(self, path: str) -> None:
        self.push_source(path)

    def exit_file(self) -> None:
        self.pop_source()

    # ------------------------------------------------------------------ pausing

    def _pause_reason(self, stmt) -> str | None:
        if self._pause_once:
            self._pause_once = False
            return _PAUSE_ENTRY if self.pause_count == 0 else _PAUSE_STEP
        if self._step_mode == "step_in":
            return _PAUSE_STEP
        if self._step_mode == "step_over" and len(self.frames) <= self._step_depth:
            return _PAUSE_STEP
        if self._step_mode == "run":
            line = getattr(stmt, "line", None)
            if line is not None and line in self.breakpoints.get(self.current_source, ()):
                return _PAUSE_BREAKPOINT
        return None

    def _pause(self, reason: str, stmt, frame: DebugFrame) -> None:
        self.pause_count += 1
        self.pause_info = {
            "reason": reason,
            "stmt": stmt,
            "frame": frame,
            "frames": list(self.frames),
            "source": self.current_source,
            "line": getattr(stmt, "line", None),
            "pause_count": self.pause_count,
        }
        self._resume_event.clear()
        try:
            if self.on_pause is not None:
                self.on_pause(self.pause_info)
            else:  # no driver: behave like "continue" so runs never hang
                self.resume("continue")
        finally:
            self._resume_event.wait()
        self._apply_resume()

    def resume(self, action: str) -> None:
        """Answer a pause. Safe to call from any thread."""
        if action not in RESUME_ACTIONS:
            raise ValueError(f"unknown resume action: {action!r}")
        self.resume_action = action
        self._resume_event.set()

    def _apply_resume(self) -> None:
        action = self.resume_action
        if action == "continue":
            self._step_mode = "run"
        elif action == "step_in":
            self._step_mode = "step_in"
        elif action == "step_over":
            self._step_mode = "step_over"
            self._step_depth = len(self.frames)
        elif action == "step_out":
            self._step_mode = "step_out"
            self._step_depth = len(self.frames)

    # --------------------------------------------------------------- inspection

    def render_value(self, value) -> str:
        if self.interpreter is not None:
            return self.interpreter.stringify(value)
        return str(value)

    def type_name(self, value) -> str:
        if self.interpreter is not None:
            return self.interpreter.type_name(value)
        return type(value).__name__

    def frame_locals(self, frame: DebugFrame) -> list[tuple[str, Any]]:
        """(name, value) pairs visible in a frame, innermost first."""
        if frame.env is None:
            return []
        try:
            return list(frame.env.items())
        except Exception:  # noqa: BLE001 - defensive; never break a pause
            return []

    def lookup(self, name: str, frame: DebugFrame | None = None):
        """Resolve a name in a frame's environment. Returns (found, value)."""
        frame = frame or (self.frames[-1] if self.frames else None)
        if frame is None or frame.env is None:
            return False, None
        env = frame.env
        while env is not None:
            bindings = getattr(env, "_bindings", {})
            if name in bindings:
                return True, bindings[name]
            env = getattr(env, "parent", None)
        return False, None

    def source_lines(self, source: str | None = None) -> list[str]:
        """Source lines of a file for context display (1-based indexing)."""
        path = source or self.current_source
        try:
            return Path(path).read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
