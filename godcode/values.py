"""Divine value types for God Code.

In God Code, every unnamed thing is still a named spirit: a bare word with
no binding evaluates to a Symbol rather than raising an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class Symbol(str):
    """A bare word with no binding — a named spirit.

    A str subclass, so Symbol("worthy") compares equal to "worthy" by text
    and behaves like a string everywhere, while remaining distinguishable
    via isinstance checks (e.g. FOR loops refuse to iterate a mere Symbol).
    Symbols are always truthy.
    """

    def __new__(cls, name: str) -> "Symbol":
        return super().__new__(cls, name)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Symbol({str(self)!r})"


@dataclass
class Contract:
    """A covenant created by the `contract(name)` rite.

    Contracts can be breathed into (alive), blessed, and anointed; SEAL
    records their state in the covenant ledger.
    """

    name: str
    alive: bool = False
    blessed: bool = False
    anointed: bool = False

    def __str__(self) -> str:
        return f'contract("{self.name}")'


@dataclass
class RiteFunction:
    """A user-defined rite: name, parameter names, body, and closure env."""

    name: str
    params: list[str] = field(default_factory=list)
    body: list[Any] = field(default_factory=list)
    closure_env: Any = None  # godcode.environment.Environment (Any avoids a cycle)

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"rite {self.name}"
