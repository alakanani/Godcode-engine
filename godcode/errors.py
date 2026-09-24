"""Error hierarchy for God Code v2.0.

All errors carry line (and where known, column) numbers so the faithful
can find where the heavens objected. Messages are divine-flavored but
genuinely helpful -- never mocking.

Control-flow signals (ReturnSignal / AscendSignal) are plain Exceptions,
*not* GodCodeError subclasses, so a broad ``except GodCodeError`` in the
interpreter can never accidentally swallow a return or an ascension.
"""

from __future__ import annotations

import difflib


class GodCodeError(Exception):
    """Base class for every God Code failure. ``line``/``col`` are 1-based."""

    def __init__(self, msg: str, line: int | None = None, col: int | None = None):
        super().__init__(msg)
        self.msg = msg
        self.line = line
        self.col = col

    def __str__(self) -> str:
        if self.line is None or f"line {self.line}" in self.msg:
            return self.msg
        loc = f" (line {self.line}"
        if self.col is not None:
            loc += f", col {self.col}"
        return self.msg + loc + ")"


class LexerError(GodCodeError):
    """The source could not be turned into tokens."""


class ParseError(GodCodeError):
    """The tokens did not form a holy grammar."""


class GodRuntimeError(GodCodeError):
    """The creation failed while it was being brought to life.

    Named to avoid clashing with the builtin RuntimeError.
    """


class SandboxViolation(GodCodeError):
    """A power the sandbox withholds.

    Raised when a creation running under ``godcode.sandbox`` reaches for
    something its policy does not grant: a forbidden scroll, a denied
    rite (such as ASK when stdin is closed), a spent step budget, or an
    expired time grant. Carries a line number like every other
    GodCodeError, so the faithful can see exactly where the heavens
    objected.
    """


class ReturnSignal(Exception):
    """Carries a rite's return value up to the rite-call boundary."""

    def __init__(self, value=None):
        super().__init__(value)
        self.value = value


class AscendSignal(Exception):
    """Raised by ASCEND; ends the creation in peace."""


def suggest_similar(name, candidates, *, n: int = 1, cutoff: float = 0.6):
    """Return the closest candidate to *name*, or None when nothing is close.

    Matching is case-insensitive; the returned candidate keeps its own
    casing. Used so the heavens can answer a misspelled name with a
    gentle \"Did you mean ...?\" instead of a bare rejection.
    """
    wanted = str(name).lower()
    lowered = {}
    for candidate in candidates:
        lowered.setdefault(str(candidate).lower(), str(candidate))
    if wanted in lowered:
        return None  # an exact name needs no suggestion
    matches = difflib.get_close_matches(wanted, list(lowered), n=n, cutoff=cutoff)
    return lowered[matches[0]] if matches else None


def with_suggestion(message: str, name, candidates) -> str:
    """Append a gentle \"Did you mean 'X'?\" to *message* when one fits."""
    suggestion = suggest_similar(name, candidates)
    if suggestion is None:
        return message
    return f"{message} Did you mean '{suggestion}'?"


def format_error(source: str, err: GodCodeError) -> str:
    """Render an error for a human: the message, then the offending line.

    The offending source line is shown with a gutter, and a caret marks the
    column when one is known. Quietly degrades to the bare message when the
    line or column cannot be shown.
    """
    lines = [str(err)]
    line_no = getattr(err, "line", None)
    if isinstance(line_no, int) and line_no >= 1:
        src_lines = source.splitlines()
        if line_no <= len(src_lines):
            text = src_lines[line_no - 1]
            gutter = f"  {line_no} | "
            lines.append(gutter + text)
            col = getattr(err, "col", None)
            if isinstance(col, int) and 1 <= col <= len(text) + 1:
                lines.append(" " * len(gutter) + " " * (col - 1) + "^")
    return "\n".join(lines)


def format_call_trace(trace: list[dict]) -> list[str]:
    """Render a rite call stack for humans, beneath the gentle error.

    One ``Called by`` line per call, oldest first, with
    ``(most recent call last)`` beneath them. An empty trace gives no lines:
    an error raised at the top level (no rite calls) shows no trace section.
    """
    if not trace:
        return []
    lines: list[str] = []
    for frame in trace:
        rite = frame.get("rite", "<rite>")
        line = frame.get("line")
        if isinstance(line, int):
            lines.append(f"Called by {rite} at line {line}")
        else:
            lines.append(f"Called by {rite}")
    lines.append("(most recent call last)")
    return lines
