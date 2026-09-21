"""Lexically scoped environments for God Code.

Scope rule: names resolve outward through parent environments. An unbound
name does not raise — it resolves to a Symbol of that name, because in God
Code every unnamed thing is still a named spirit (this is what makes
`DECLARE seeker AS worthy` / `IF seeker IS worthy` work with no prior
binding of `worthy`).

DECLARE always defines in the *current* environment; it never rebinds an
outer scope. Use set_existing() to reshape a name that must already exist.
"""

from __future__ import annotations

from typing import Iterator

from godcode.errors import GodRuntimeError
from godcode.values import Symbol


class Environment:
    def __init__(self, parent: "Environment | None" = None):
        self.parent = parent
        self._bindings: dict[str, object] = {}

    def define(self, name: str, value: object) -> None:
        """Bind name in this environment, shadowing any outer binding."""
        self._bindings[name] = value

    def get(self, name: str) -> object:
        """Walk outward for name; return Symbol(name) if nowhere bound."""
        env: Environment | None = self
        while env is not None:
            if name in env._bindings:
                return env._bindings[name]
            env = env.parent
        return Symbol(name)

    def is_bound(self, name: str) -> bool:
        """True if name is bound in this environment or any ancestor."""
        env: Environment | None = self
        while env is not None:
            if name in env._bindings:
                return True
            env = env.parent
        return False

    def set_existing(self, name: str, value: object) -> None:
        """Reshape an already-bound name where it lives; error if unbound."""
        env: Environment | None = self
        while env is not None:
            if name in env._bindings:
                env._bindings[name] = value
                return
            env = env.parent
        raise GodRuntimeError(
            f"There is no '{name}' to reshape — it was never spoken into being."
        )

    def names(self) -> list[str]:
        """All visible names, innermost scope first, without duplicates."""
        seen: list[str] = []
        env: Environment | None = self
        while env is not None:
            for key in env._bindings:
                if key not in seen:
                    seen.append(key)
            env = env.parent
        return seen

    def items(self) -> Iterator[tuple[str, object]]:
        """(name, value) pairs for every visible name, innermost first."""
        for name in self.names():
            yield name, self.get(name)
