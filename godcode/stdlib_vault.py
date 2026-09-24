"""God Code standard library, part 1: the vault of JSON and the filesystem.

This module holds builtins that read and write the outer world: parsing
and rendering JSON, and reading, writing, and listing files. It is kept
apart from the interpreter core so the language's heart stays small.

Wiring
------
``register(interp)`` adds the builtins to ``interp._builtins``. Each
builtin is a plain callable ``(args, line)`` in the style of the core
builtins (arity through ``interp._arity``, plain-word GodRuntimeError
messages).

Sandbox honesty
---------------
READ_FILE, WRITE_FILE, LIST_DIR, and FILE_EXISTS reach the host
filesystem. When the interpreter runs under ``godcode.sandbox``, the
sandbox guard (``interp._sandbox_guard``, installed by
``Sandbox.install``) carries the policy, and these builtins honor it:

* writes are refused unless the policy grants ``allow_write``;
* reads are refused unless the policy grants ``allow_read_paths``,
  and then only under one of the granted directories.

JSON_PARSE and JSON_STRING are pure and need no grant.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from godcode.errors import GodRuntimeError, SandboxViolation
from godcode.values import Contract, RiteFunction, Symbol

__all__ = ["register"]


# ------------------------------------------------------------ value helpers


def _as_word(interp, name: str, value: Any, line) -> str:
    """Take a God Code word as plain text. Symbols give up their text."""
    if isinstance(value, Symbol):
        return str(value)
    if isinstance(value, str):
        return value
    raise GodRuntimeError(
        f"{name} needs a word, but a {interp.type_name(value)} was offered.",
        line,
    )


def _from_json(value: Any) -> Any:
    """Turn a json.loads result into God Code values.

    Objects become maps, arrays become lists, null becomes void.
    Numbers, words, and booleans cross over unchanged.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_from_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _from_json(item) for key, item in value.items()}
    raise GodRuntimeError(f"JSON_PARSE met a value it cannot carry: {value!r}.")


def _to_json_text(interp, value: Any, line) -> str:
    """Render a God Code value as compact JSON.

    Raises a plain GodRuntimeError for values JSON cannot carry:
    rites, contracts, symbols, non-word map keys, and numbers with no
    JSON shape (infinity, not-a-number).
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Symbol):
        raise GodRuntimeError(
            "JSON_STRING cannot carry a symbol. "
            "Only words, numbers, booleans, lists, and maps have a JSON shape.",
            line,
        )
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        try:
            return json.dumps(value, allow_nan=False)
        except ValueError:
            raise GodRuntimeError(
                "JSON_STRING cannot carry a number with no JSON shape, "
                "like infinity or not-a-number.",
                line,
            ) from None
    if isinstance(value, list):
        inner = ",".join(_to_json_text(interp, item, line) for item in value)
        return "[" + inner + "]"
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if isinstance(key, Symbol) or not isinstance(key, str):
                raise GodRuntimeError(
                    "JSON_STRING needs map keys that are words. "
                    f"A {interp.type_name(key)} key was found.",
                    line,
                )
            parts.append(json.dumps(key) + ":" + _to_json_text(interp, item, line))
        return "{" + ",".join(parts) + "}"
    if isinstance(value, RiteFunction):
        raise GodRuntimeError(
            "JSON_STRING cannot carry a rite. Rites have no JSON shape.",
            line,
        )
    if isinstance(value, Contract):
        raise GodRuntimeError(
            "JSON_STRING cannot carry a contract. Contracts have no JSON shape.",
            line,
        )
    raise GodRuntimeError(
        f"JSON_STRING cannot carry {interp.type_name(value)}. "
        "Only words, numbers, booleans, lists, and maps have a JSON shape.",
        line,
    )


# ------------------------------------------------------------ sandbox guard


def _guard(interp):
    """The sandbox guard, if this interpreter runs under godcode.sandbox."""
    return getattr(interp, "_sandbox_guard", None)


def _check_read_grant(interp, rite: str, path: str, line) -> None:
    """Refuse filesystem reads the sandbox policy does not grant.

    No guard means no sandbox: the read proceeds. Under a guard, reads
    need ``allow_read_paths``, and the resolved path must lie under one
    of the granted directories (the same rule the sandbox applies to
    scroll imports).
    """
    guard = _guard(interp)
    if guard is None:
        return
    allowed = guard.policy.allow_read_paths
    if not allowed:
        raise SandboxViolation(
            f"The sandbox withholds this power: the rite {rite} would read "
            "from the outer world. It is not granted.",
            line,
        )
    resolved = os.path.realpath(path)
    for base in allowed:
        base_resolved = os.path.realpath(base)
        if resolved == base_resolved or resolved.startswith(base_resolved + os.sep):
            return
    raise SandboxViolation(
        f"The sandbox withholds this power: the rite {rite} may not read "
        f"'{path}'. It lies outside the granted paths.",
        line,
    )


def _check_write_grant(interp, path: str, line) -> None:
    """Refuse filesystem writes the sandbox policy does not grant."""
    guard = _guard(interp)
    if guard is None:
        return
    if not guard.policy.allow_write:
        raise SandboxViolation(
            "The sandbox withholds this power: the rite WRITE_FILE would "
            f"write '{path}' to the outer world. It is not granted.",
            line,
        )


# ------------------------------------------------------------------ register


def register(interp) -> None:
    """Add the vault builtins to ``interp._builtins``.

    Idempotent: calling it twice simply replaces the same six entries.
    """
    arity = interp._arity

    def json_parse(args, line):
        arity("JSON_PARSE", args, 1, line)
        text = _as_word(interp, "JSON_PARSE", args[0], line)
        try:
            return _from_json(json.loads(text))
        except json.JSONDecodeError as exc:
            raise GodRuntimeError(
                f"JSON_PARSE could not read that word as JSON. {exc.msg}: "
                f"line {exc.lineno} column {exc.colno}.",
                line,
            ) from None

    def json_string(args, line):
        arity("JSON_STRING", args, 1, line)
        return _to_json_text(interp, args[0], line)

    def read_file(args, line):
        arity("READ_FILE", args, 1, line)
        path = _as_word(interp, "READ_FILE", args[0], line)
        _check_read_grant(interp, "READ_FILE", path, line)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            raise GodRuntimeError(
                f"READ_FILE could not read '{path}'. {exc.strerror or exc}.",
                line,
            ) from None

    def write_file(args, line):
        arity("WRITE_FILE", args, 2, line)
        path = _as_word(interp, "WRITE_FILE", args[0], line)
        text = _as_word(interp, "WRITE_FILE", args[1], line)
        _check_write_grant(interp, path, line)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                return handle.write(text)
        except OSError as exc:
            raise GodRuntimeError(
                f"WRITE_FILE could not write '{path}'. {exc.strerror or exc}.",
                line,
            ) from None

    def file_exists(args, line):
        arity("FILE_EXISTS", args, 1, line)
        path = _as_word(interp, "FILE_EXISTS", args[0], line)
        _check_read_grant(interp, "FILE_EXISTS", path, line)
        return os.path.exists(path)

    def list_dir(args, line):
        arity("LIST_DIR", args, 1, line)
        path = _as_word(interp, "LIST_DIR", args[0], line)
        _check_read_grant(interp, "LIST_DIR", path, line)
        if not os.path.isdir(path):
            raise GodRuntimeError(
                f"LIST_DIR needs a directory, but '{path}' is not one.",
                line,
            )
        try:
            entries = os.listdir(path)
        except OSError as exc:
            raise GodRuntimeError(
                f"LIST_DIR could not open '{path}'. {exc.strerror or exc}.",
                line,
            ) from None
        return sorted(str(entry) for entry in entries)

    builtins: dict[str, Callable[..., Any]] = {
        "JSON_PARSE": json_parse,
        "JSON_STRING": json_string,
        "READ_FILE": read_file,
        "WRITE_FILE": write_file,
        "FILE_EXISTS": file_exists,
        "LIST_DIR": list_dir,
    }
    interp._builtins.update(builtins)
