"""In-process sandbox for God Code v3.0 — Pillar 1 ("Strong Foundations").

Runs a God Code creation under a deny-by-default :class:`SandboxPolicy`:
every side-effecting power (scroll imports outside the consecrated paths,
the ASK rite that speaks with the outer world, and — should such rites
ever be added — file, network, or subprocess powers) is withheld unless
the policy explicitly grants it. A step budget and a wall-clock grant
bound runaway creations.

Entry points
------------
``run_sandboxed(source, policy, source_name)``
    Lex, parse, and run ``source`` under ``policy``; returns the list of
    REVEAL lines captured during the run.

``apply_policy(interpreter, policy)``
    Install the sandbox hooks on an existing ``Interpreter``; returns the
    ``Sandbox`` guard.

``SandboxPolicy.strict(...)``
    The policy the CLI uses: no writes, no network, no subprocesses, no
    stdin, scroll imports limited to the stdlib scrolls and (optionally)
    the creation's own directory, a 5-second time grant, and a 100,000
    step budget.

Honest limits (see docs/sandbox.md): this is an *in-process* sandbox —
a cooperative audit of the tree-walker, not OS-level isolation. It
cannot contain a hostile program that escapes the interpreter, and it
cannot cap memory.
"""

from __future__ import annotations

import contextlib
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from godcode.errors import GodCodeError, SandboxViolation

__all__ = [
    "SandboxPolicy",
    "Sandbox",
    "SandboxViolation",
    "apply_policy",
    "run_sandboxed",
]


def _stdlib_scrolls_dir() -> str:
    return str(Path(__file__).parent / "scrolls")


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
@dataclass
class SandboxPolicy:
    """What a sandboxed creation is permitted to do. Deny-by-default.

    ``allow_read_paths``
        Approved directories for filesystem *reads*. ``None`` (the
        default) denies all reads; a tuple of directories grants reads
        under those trees. (No file-reading rites exist in v2.0; this is
        enforced should any be added.)
    ``allow_write`` / ``allow_network`` / ``allow_subprocess``
        Filesystem writes, network access, subprocess spawning. All deny
        by default; no such rites exist in v2.0, so granting them is
        currently a no-op recorded for future rites.
    ``allow_stdin``
        Whether the ASK rite may speak with the outer world (``input()``).
        Denied by default.
    ``allowed_import_paths``
        Approved directories for IMPORT of scrolls. Empty (the default)
        denies every import. Each entry is a directory; a scroll is
        allowed if its real path lies under one of them.
    ``timeout_seconds``
        Wall-clock grant for the whole run. ``None`` or ``<= 0``
        disables the grant (not recommended).
    ``max_steps``
        Step budget: every statement dispatch and every expression
        evaluation counts one step, bounding both runaway loops and
        unbounded rite recursion.
    """

    allow_read_paths: tuple[str, ...] | None = None
    allow_write: bool = False
    allow_network: bool = False
    allow_subprocess: bool = False
    allow_stdin: bool = False
    allowed_import_paths: tuple[str, ...] = ()
    timeout_seconds: float | None = 5.0
    max_steps: int = 100_000

    @classmethod
    def strict(
        cls,
        *,
        source_dir: str | None = None,
        timeout_seconds: float | None = 5.0,
    ) -> "SandboxPolicy":
        """The CLI's strict policy: deny everything, bless the stdlib.

        Scroll imports are allowed from the bundled stdlib scrolls and,
        when given, the creation's own directory — nothing else.
        """
        paths = [_stdlib_scrolls_dir()]
        if source_dir:
            paths.append(str(source_dir))
        return cls(
            allowed_import_paths=tuple(paths),
            timeout_seconds=timeout_seconds,
        )


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------
# Builtin rite name -> SandboxPolicy attribute that must be truthy for the
# rite to run. God Code v2.0 has no file/network/subprocess rites, so the
# registry currently holds only ASK; it is the extension point for future
# side-effecting rites (e.g. "FETCH" -> "allow_network").
_SIDE_EFFECT_RITES: dict[str, str] = {
    "ASK": "allow_stdin",
}

_HOOKS = ("_exec_stmt", "_eval_expr", "_call", "_exec_import")


class Sandbox:
    """Enforces a :class:`SandboxPolicy` on a live Interpreter.

    Installed hooks (see :meth:`install`):

    * ``_exec_stmt`` / ``_eval_expr`` — count one step per statement
      dispatch and expression evaluation; check the step budget and the
      wall-clock grant; record the current line for divine errors.
    * ``_call`` — refuse side-effecting rites the policy does not grant
      (ASK today; the registry above grows with the language).
    * ``_exec_import`` — resolve the scroll, then refuse any path
      outside ``allowed_import_paths``.
    """

    def __init__(self, interpreter: Any, policy: SandboxPolicy):
        self.interpreter = interpreter
        self.policy = policy
        self.steps = 0
        self.started_at: float | None = None
        self.current_line: int | None = None
        self._originals: dict[str, Callable] = {}
        self._allowed_import_dirs = [
            os.path.realpath(p) for p in policy.allowed_import_paths
        ]

    # -- installation ---------------------------------------------------

    def install(self) -> "Sandbox":
        """Wrap the interpreter's dispatch points. Idempotent."""
        interp = self.interpreter
        if self._originals:
            return self
        for name in _HOOKS:
            original = getattr(interp, name)
            self._originals[name] = original
            setattr(interp, name, self._wrap(name, original))
        return self

    def uninstall(self) -> None:
        """Restore the interpreter's original dispatch points."""
        for name, original in self._originals.items():
            setattr(self.interpreter, name, original)
        self._originals.clear()

    def _wrap(self, name: str, original: Callable) -> Callable:
        if name == "_exec_stmt":
            def exec_stmt(stmt, env):
                self.tick(stmt)
                return original(stmt, env)
            return exec_stmt
        if name == "_eval_expr":
            def eval_expr(expr, env):
                self.tick(expr)
                return original(expr, env)
            return eval_expr
        if name == "_call":
            def call(rite_name, args, env, line):
                self.check_rite(rite_name, line)
                return original(rite_name, args, env, line)
            return call
        if name == "_exec_import":
            def exec_import(stmt, env):
                line = getattr(stmt, "line", None)
                path = self.interpreter._resolve_import(stmt.path, line)
                self.check_import_path(path, stmt.path, line)
                return original(stmt, env)
            return exec_import
        raise AssertionError(f"unknown hook: {name}")  # pragma: no cover

    # -- enforcement -----------------------------------------------------

    def tick(self, node: Any) -> None:
        """Count one interpreter step; enforce budget and time grant."""
        self.steps += 1
        line = getattr(node, "line", None)
        if line is not None:
            self.current_line = line
        if self.steps > self.policy.max_steps:
            raise SandboxViolation(
                "The sandbox withholds this power: the creation has taken "
                f"more than {self.policy.max_steps:,} steps — "
                "the step budget is spent, and the cycle is released.",
                self.current_line,
            )
        if self.started_at is not None and self.policy.timeout_seconds:
            elapsed = time.monotonic() - self.started_at
            if elapsed > self.policy.timeout_seconds:
                raise SandboxViolation(
                    "The sandbox withholds this power: the appointed time "
                    f"({self.policy.timeout_seconds:g}s) is spent — "
                    "the creation is released in peace.",
                    self.current_line,
                )

    def check_rite(self, name: str, line: int | None) -> None:
        """Refuse side-effecting rites the policy does not grant."""
        need = _SIDE_EFFECT_RITES.get(str(name).upper())
        if need is not None and not getattr(self.policy, need, False):
            divine = {
                "ASK": "the rite ASK would speak with the outer world",
            }.get(str(name).upper(), f"the rite {name}")
            raise SandboxViolation(
                f"The sandbox withholds this power: {divine} — "
                "it is not granted.",
                line,
            )

    def check_import_path(
        self, path: Path, requested: str, line: int | None
    ) -> None:
        """Refuse scrolls outside the consecrated import paths."""
        resolved = os.path.realpath(path)
        for allowed in self._allowed_import_dirs:
            if resolved == allowed or resolved.startswith(allowed + os.sep):
                return
        raise SandboxViolation(
            "The sandbox withholds this power: the scroll "
            f"'{requested}' lies outside the consecrated paths — "
            "it may not be breathed in.",
            line,
        )


def apply_policy(interpreter: Any, policy: SandboxPolicy) -> Sandbox:
    """Install sandbox hooks on ``interpreter``; return the guard.

    One guard per interpreter; the hooks stay installed until
    ``guard.uninstall()`` is called.
    """
    return Sandbox(interpreter, policy).install()


# ---------------------------------------------------------------------------
# Timeout: POSIX signal alarm with a wall-clock fallback
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _time_limit(seconds: float | None, guard: Sandbox):
    """Raise SandboxViolation from a POSIX alarm when the grant expires.

    The wall-clock check in :meth:`Sandbox.tick` is the fallback (and the
    only enforcement on platforms without ``setitimer``, or outside the
    main thread, where signals cannot be armed).
    """
    armed = False
    old_handler = None

    def _handler(signum, frame):  # noqa: ARG001
        raise SandboxViolation(
            "The sandbox withholds this power: the appointed time "
            f"({seconds:g}s) is spent — the creation is released in peace.",
            guard.current_line,
        )

    try:
        if seconds and hasattr(signal, "setitimer"):
            old_handler = signal.signal(signal.SIGALRM, _handler)
            signal.setitimer(signal.ITIMER_REAL, seconds)
            armed = True
    except (ValueError, OSError, RuntimeError):
        armed = False  # not the main thread, or signals unavailable
    try:
        yield
    finally:
        if armed:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old_handler)
            except (ValueError, OSError, RuntimeError):
                pass


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------
def run_sandboxed(
    source: str,
    policy: SandboxPolicy | None = None,
    source_name: str = "<sandbox>",
) -> list[str]:
    """Run God Code ``source`` under ``policy``; return captured REVEAL lines.

    Uses the strict policy when none is given. Spirit, covenant ledger,
    and the audit log are left unbound — they write to the host world,
    which the sandbox does not permit. Host plugin auto-loading is
    disabled for the run (via the plugin system's own opt-out):
    plugins are trusted host code that runs outside any policy, so a
    deny-by-default sandbox must not breathe them in unasked.
    Raises :class:`SandboxViolation` (a GodCodeError, line-numbered)
    when the creation reaches beyond its grant.
    """
    from godcode import plugins
    from godcode.interpreter import Interpreter

    policy = policy or SandboxPolicy.strict()
    env_var = plugins.DISABLE_ENV_VAR
    previous = os.environ.get(env_var)
    os.environ[env_var] = "1"
    try:
        interpreter = Interpreter(log_path=None, interactive=False)
    finally:
        if previous is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = previous
    guard = apply_policy(interpreter, policy)
    guard.started_at = time.monotonic()
    try:
        with _time_limit(policy.timeout_seconds, guard):
            interpreter.run_source(source, source_name=source_name)
    except RecursionError:
        raise SandboxViolation(
            "The sandbox withholds this power: the rites called upon "
            "themselves past the deep places — the recursion budget is "
            "spent, and the cycle is released.",
            guard.current_line,
        ) from None
    finally:
        guard.started_at = None
    return list(interpreter.output)
