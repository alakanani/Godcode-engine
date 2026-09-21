"""God Code v3.0 — the language of divine computation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__version__ = "3.0.0"


@dataclass
class RunResult:
    """The outcome of running God Code from a host program.

    ``output`` is the captured REVEAL output (lines joined with ``\\n``);
    ``return_value`` is the value of a top-level ``RETURN`` (if the scroll
    ascends that way) or of the last expression statement evaluated, else
    ``None``; ``error`` is the divine error message (with line number) when
    the run failed; ``ok`` tells whether the run completed.
    """

    output: str = ""
    return_value: Any = None
    error: str | None = None
    ok: bool = False


def run_source(source: str, *, filename: str = "<string>") -> RunResult:
    """Run God Code source from a host program and capture the outcome.

    REVEAL output is captured per-interpreter (via the interpreter's ``emit``
    hook), so this is safe to call many times in one process.  Plugin
    auto-loading still applies unless ``GODCODE_NO_PLUGINS=1`` is set.
    Embedding runs do not write the audit log.
    """
    from godcode.errors import GodCodeError, ReturnSignal
    from godcode.interpreter import Interpreter

    lines: list[str] = []
    interpreter = Interpreter(log_path=None)
    interpreter.emit = lines.append
    try:
        interpreter.run_source(source, source_name=filename)
    except ReturnSignal as ret:
        # A top-level RETURN becomes the run's return value.
        return RunResult(
            output="\n".join(lines), return_value=ret.value, error=None, ok=True
        )
    except GodCodeError as err:
        return RunResult(
            output="\n".join(lines),
            return_value=None,
            error=str(err),
            ok=False,
        )
    except Exception as exc:  # a host/plugin failure outside the divine errors
        return RunResult(
            output="\n".join(lines),
            return_value=None,
            error=f"the outer world faltered: {exc!r}",
            ok=False,
        )
    return RunResult(
        output="\n".join(lines),
        return_value=interpreter.last_value,
        error=None,
        ok=True,
    )


def run_file(path: str | Path) -> RunResult:
    """Run a God Code scroll file from a host program; see :func:`run_source`."""
    try:
        source = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return RunResult(
            output="",
            return_value=None,
            error=f"cannot read '{path}': {exc.strerror or exc}",
            ok=False,
        )
    return run_source(source, filename=str(path))


__all__ = ["__version__", "RunResult", "run_source", "run_file"]
