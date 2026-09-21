"""Error hierarchy for God Code v2.0.

All errors carry line (and where known, column) numbers so the faithful
can find where the heavens objected. Messages are divine-flavored but
genuinely helpful -- never mocking.

Control-flow signals (ReturnSignal / AscendSignal) are plain Exceptions,
*not* GodCodeError subclasses, so a broad ``except GodCodeError`` in the
interpreter can never accidentally swallow a return or an ascension.
"""

from __future__ import annotations


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


class ReturnSignal(Exception):
    """Carries a rite's return value up to the rite-call boundary."""

    def __init__(self, value=None):
        super().__init__(value)
        self.value = value


class AscendSignal(Exception):
    """Raised by ASCEND; ends the creation in peace."""
