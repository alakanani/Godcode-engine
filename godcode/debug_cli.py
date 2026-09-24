"""Interactive CLI driver for the God Code debugger.

Implements ``godcode debug <file.god>``: the scroll runs under a
:class:`godcode.debugger.DebugSession`, and every pause opens a small
gdb-style console on stdin/stdout. The interpreter is built exactly the
way ``godcode run`` builds it, so the debug run can never drift from a
plain run.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROMPT = "(god) "


class _QuitDebug(Exception):
    """Raised to leave the debugger. Caught by cmd_debug."""


class _PauseLoop:
    """Answers ``DebugSession.on_pause`` with an interactive console.

    Runs on the interpreter's own thread: every command either answers
    inline (break, print, locals, stack, help) or ends the pause with
    ``session.resume(action)``. Quitting raises :class:`_QuitDebug` after
    releasing the session's resume event, because the session waits on
    that event even when ``on_pause`` raises.
    """

    _RESUME_COMMANDS = {
        "continue": "continue",
        "c": "continue",
        "run": "continue",
        "next": "step_over",
        "n": "step_over",
        "step": "step_in",
        "si": "step_in",
        "out": "step_out",
    }

    def __init__(self, session) -> None:
        self.session = session
        self._last_resume = "continue"

    # ------------------------------------------------------------ entry point
    def handle(self, pause_info: dict) -> None:
        self._show_pause(pause_info)
        while True:
            try:
                raw = input(PROMPT)
            except EOFError:
                self._quit()
            except KeyboardInterrupt:
                print()
                self._quit()
            text = raw.strip()
            if not text:
                # gdb-style: an empty line repeats the last resume command.
                self._do_resume(self._last_resume)
                return
            if self._dispatch(text, pause_info):
                return

    # ---------------------------------------------------------------- display
    def _show_pause(self, pause_info: dict) -> None:
        reason = pause_info.get("reason", "step")
        line = pause_info.get("line")
        source = pause_info.get("source") or ""
        name = Path(source).name if source else "<unknown scroll>"
        print(f"paused at {name}:{line} ({reason})")
        lines = self.session.source_lines(source) if source else []
        if isinstance(line, int) and 1 <= line <= len(lines):
            first = max(1, line - 1)
            last = min(len(lines), line + 1)
            for num in range(first, last + 1):
                marker = "=>" if num == line else "  "
                print(f"{marker} {num:>4} | {lines[num - 1]}")

    # --------------------------------------------------------------- commands
    def _dispatch(self, text: str, pause_info: dict) -> bool:
        """Run one command. Returns True when the pause is over."""
        word, _, rest = text.partition(" ")
        word = word.lower()
        arg = rest.strip()

        resume = self._RESUME_COMMANDS.get(word)
        if resume is not None:
            if arg:
                print(f"'{word}' takes no arguments.")
                return False
            self._do_resume(resume)
            return True

        if word in ("break", "b"):
            self._cmd_break(arg)
        elif word in ("print", "p"):
            self._cmd_print(arg)
        elif word == "locals":
            self._cmd_locals(pause_info)
        elif word in ("stack", "bt"):
            self._cmd_stack()
        elif word == "help":
            self._cmd_help()
        elif word in ("quit", "q"):
            self._quit()
        else:
            print(f"Unknown command: '{word}'. Type 'help' for the list.")
        return False

    def _do_resume(self, action: str) -> None:
        self._last_resume = action
        self.session.resume(action)

    def _quit(self) -> None:
        # Release the session's wait first: it blocks on the resume event
        # even when on_pause raises, and we must not hang it.
        self.session.resume("continue")
        raise _QuitDebug()

    # -- break ---------------------------------------------------------
    def _cmd_break(self, arg: str) -> None:
        session = self.session
        source = session.current_source
        name = Path(source).name if source else "<unknown scroll>"
        if not arg:
            lines = sorted(session.breakpoints_for(source))
            if not lines:
                print("No breakpoints set.")
            else:
                listed = ", ".join(f"{name}:{num}" for num in lines)
                print(f"Breakpoints: {listed}")
            return
        try:
            lineno = int(arg.split()[0])
            if lineno < 1:
                raise ValueError
        except ValueError:
            print("Usage: break <line>. Give a line number, like 'break 3'.")
            return
        session.add_breakpoint(source, lineno)
        print(f"Breakpoint set at {name}:{lineno}.")

    # -- print ---------------------------------------------------------
    def _cmd_print(self, arg: str) -> None:
        if not arg:
            print("Usage: print <name>.")
            return
        name = arg.split()[0]
        found, value = self.session.lookup(name)
        if not found:
            print(f"'{name}' is not bound here.")
        else:
            print(f"{name} = {self.session.render_value(value)}")

    # -- locals --------------------------------------------------------
    def _cmd_locals(self, pause_info: dict) -> None:
        session = self.session
        frame = pause_info.get("frame")
        if frame is None and session.frames:
            frame = session.frames[-1]
        pairs = session.frame_locals(frame) if frame is not None else []
        if not pairs:
            print("No names are bound in this frame.")
            return
        for name, value in pairs:
            rendered = session.render_value(value)
            typename = session.type_name(value)
            print(f"{name} = {rendered} ({typename})")

    # -- stack ---------------------------------------------------------
    def _cmd_stack(self) -> None:
        frames = self.session.frames
        if not frames:
            print("The stack is empty.")
            return
        for i, frame in enumerate(reversed(frames)):
            marker = " (current)" if i == 0 else ""
            print(f"#{i} {frame.name} at {self._frame_loc(frame)}{marker}")

    @staticmethod
    def _frame_loc(frame) -> str:
        source = getattr(frame, "source", "") or ""
        name = Path(source).name if source else "<unknown scroll>"
        line = frame.line
        return f"{name}:{line}" if isinstance(line, int) else name

    # -- help ----------------------------------------------------------
    def _cmd_help(self) -> None:
        print("Commands:")
        print("  break <line> (b)   set a breakpoint; 'break' alone lists them")
        print("  continue (c), run  resume the scroll")
        print("  next (n)           step over the next statement")
        print("  step (si)          step into the next call")
        print("  out                step out of the current rite")
        print("  print <name> (p)   show the value of a bound name")
        print("  locals             show every name visible in this frame")
        print("  stack (bt)         show the call stack, innermost first")
        print("  help               this list")
        print("  quit (q)           leave the debugger; the scroll does not finish")
        print("An empty line repeats the last resume command. Ctrl-D quits.")


# ---------------------------------------------------------------------------
# debug
# ---------------------------------------------------------------------------
def cmd_debug(args) -> int:
    from godcode.cli import _make_interpreter
    from godcode.debugger import DebugSession
    from godcode.errors import GodCodeError, format_error

    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"godcode: cannot read '{args.file}': {exc.strerror or exc}",
              file=sys.stderr)
        return 1

    interp = _make_interpreter(log_path=None)
    session = DebugSession()
    loop = _PauseLoop(session)
    session.on_pause = loop.handle
    session.stop_on_entry = True
    for lineno in getattr(args, "breaks", None) or []:
        session.add_breakpoint(args.file, lineno)
    session.attach(interp)
    try:
        session.run_file(args.file)
    except _QuitDebug:
        print("The debugger ascends. The scroll rests unfinished.")
        return 0
    except GodCodeError as err:
        print(format_error(source, err), file=sys.stderr)
        return 1
    print("The scroll has finished its course. Amen.")
    return 0
