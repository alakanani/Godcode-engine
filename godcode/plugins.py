"""Pillar 3 — plugins and the SUMMON foreign-function interface.

A plugin is a plain Python module living in a plugins directory.  On load it
exposes::

    PLUGIN_API_VERSION = 1

    def register(interpreter):
        interpreter.register_plugin_verb("myns.myverb", myverb, plugin="myns")

The interpreter calls ``register(interpreter)`` at startup, so the plugin can
add new built-in verbs through the same ``_builtins`` mechanism the v2 core
verbs use.  God Code calls those verbs through the ``SUMMON`` FFI verb::

    SUMMON("myns.myverb", arg1, arg2)

Plugins are **trusted host code**: they run with the full power of Python,
and SUMMON calls into them bypass any sandbox policy *by design*.  Every
plugin verb is recorded with ``trusted=True`` on the interpreter
(``interpreter.plugin_verb_info``) so a future sandbox pillar can consult the
marker when deciding what a scroll may touch.

Set ``GODCODE_NO_PLUGINS=1`` in the environment to skip plugin auto-loading
entirely.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import re
import sys
import types
from pathlib import Path
from typing import Any, Callable

from godcode.values import Contract, RiteFunction, Symbol  # noqa: F401  (re-exported for plugin authors)

PLUGIN_API_VERSION = 1
"""Version of the plugin contract this engine speaks."""

ENTRY_POINT_GROUP = "godcode_plugins"
"""importlib.metadata entry-point group for installed plugins (best-effort)."""

DISABLE_ENV_VAR = "GODCODE_NO_PLUGINS"
"""Set to "1" to skip plugin auto-loading entirely."""


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def default_plugin_dirs() -> list[Path]:
    """Where plugins are looked for: ``./plugins`` then ``~/.godcode/plugins``."""
    dirs = [Path.cwd() / "plugins"]
    try:
        dirs.append(Path.home() / ".godcode" / "plugins")
    except Exception:  # pragma: no cover - exotic platforms without a home
        pass
    return dirs


def _warn(message: str) -> None:
    print(f"godcode: plugin warning: {message}", file=sys.stderr)


def _iter_plugin_files(dirs: list[Path]):
    """Yield ``(stem, path)`` for each candidate plugin file in *dirs*."""
    for directory in dirs:
        try:
            if not directory.is_dir():
                continue
            entries = sorted(directory.iterdir())
        except OSError as exc:
            _warn(f"cannot scan {directory}: {exc}")
            continue
        for path in entries:
            if not path.is_file() or path.suffix != ".py":
                continue
            stem = path.stem
            if stem == "__init__" or stem.startswith(("_", ".")):
                continue
            yield stem, path


def _module_name_for(stem: str) -> str:
    safe = re.sub(r"[^0-9a-zA-Z_]", "_", stem)
    if not safe or safe[0].isdigit():
        safe = "_" + safe
    return f"godcode_plugin_{safe}"


def _import_from_path(stem: str, path: Path) -> types.ModuleType:
    """Import the module at *path* without touching ``sys.path``."""
    name = _module_name_for(stem)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot build a module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    # NOTE: deliberately *not* cached in sys.modules — each interpreter gets a
    # freshly executed plugin module, so plugin state never leaks between runs.
    spec.loader.exec_module(module)
    return module


def _entry_point_plugins() -> dict[str, Any]:
    """Best-effort load of the ``godcode_plugins`` entry-point group."""
    found: dict[str, Any] = {}
    try:
        entry_points = importlib.metadata.entry_points()
    except Exception as exc:  # pragma: no cover - metadata backend missing
        _warn(f"could not read entry points: {exc}")
        return found
    try:
        if hasattr(entry_points, "select"):  # Python 3.10+ EntryPoints
            selected = entry_points.select(group=ENTRY_POINT_GROUP)
        else:  # pragma: no cover - legacy dict-style interface
            selected = entry_points.get(ENTRY_POINT_GROUP, ())
    except Exception as exc:
        _warn(f"could not select {ENTRY_POINT_GROUP!r} entry points: {exc}")
        return found
    for ep in selected:
        try:
            found[ep.name] = ep.load()
        except Exception as exc:
            _warn(f"entry-point plugin {ep.name!r} failed to load: {exc}")
    return found


def discover_plugins(dirs: list[Path] | None = None) -> dict[str, Any]:
    """Import every plugin module found and return ``{name: module}``.

    *dirs* defaults to :func:`default_plugin_dirs`, with the
    ``godcode_plugins`` entry-point group consulted afterwards (later sources
    shadow earlier ones on name clashes).

    A module that fails to import is skipped with a warning on stderr — a
    broken plugin never crashes the host run.
    """
    if dirs is None:
        dirs = default_plugin_dirs()
    discovered: dict[str, Any] = {}
    for stem, path in _iter_plugin_files(dirs):
        try:
            discovered[stem] = _import_from_path(stem, path)
        except Exception as exc:
            _warn(f"plugin {path} failed to import ({exc}) — skipped")
    for name, module in _entry_point_plugins().items():
        discovered[name] = module
    return discovered


def load_plugins(interpreter, dirs: list[Path] | None = None) -> list[str]:
    """Discover plugins and call ``register(interpreter)`` on each.

    Returns the names of the plugins whose ``register()`` ran cleanly.  A
    missing ``register()``, a ``PLUGIN_API_VERSION`` mismatch, or an
    exception inside ``register()`` only produces a stderr warning — never
    an exception, so startup always survives a bad plugin.
    """
    loaded: list[str] = []
    for name, module in discover_plugins(dirs).items():
        api = getattr(module, "PLUGIN_API_VERSION", 1)
        if api != PLUGIN_API_VERSION:
            _warn(
                f"plugin {name!r} speaks API version {api}, "
                f"this engine speaks {PLUGIN_API_VERSION} — skipped"
            )
            continue
        register = getattr(module, "register", None)
        if not callable(register):
            _warn(f"plugin {name!r} exposes no register(interpreter) — skipped")
            continue
        try:
            register(interpreter)
        except Exception as exc:
            _warn(f"plugin {name!r} register() failed ({exc}) — skipped")
            continue
        loaded.append(name)
    return loaded


# ---------------------------------------------------------------------------
# value conversion: God Code <-> Python
# ---------------------------------------------------------------------------
#
# God Code values already *are* Python objects inside the interpreter, so most
# conversions are the identity.  The table below is the contract plugin
# authors can rely on:
#
#   God Code number   <-> Python int / float        (identity)
#   God Code string   <-> Python str               (identity)
#   God Code boolean  <-> Python bool              (identity)
#   God Code void     <-> Python None              (identity)
#   God Code list     <-> Python list              (recursive)
#   God Code symbol   <-> Symbol, a str subclass   (identity)
#   God Code contract <-> Contract                 (opaque, identity)
#   God Code rite     <-> RiteFunction             (opaque, identity)
#
# Anything else a plugin returns (dict, set, tuple, custom objects, ...)
# passes through opaquely, except tuples which become lists recursively.
# REVEAL renders opaque values with str().

def to_python(value: Any) -> Any:
    """Convert a God Code value to the Python value a plugin receives.

    Identity for every documented God Code value; see the table above.
    """
    return value


def to_godcode(value: Any) -> Any:
    """Convert a plugin's Python return value back into a God Code value.

    Tuples become lists (recursively); every other value passes through
    as-is.  Values with no God Code counterpart (dicts, sets, custom
    objects) travel opaquely and are rendered with ``str()`` by REVEAL.
    """
    if isinstance(value, tuple):
        return [to_godcode(item) for item in value]
    if isinstance(value, list):
        return [to_godcode(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# interpreter mixin helpers (kept here so interpreter.py stays small)
# ---------------------------------------------------------------------------

def make_verb_adapter(name: str, func: Callable[..., Any]):
    """Wrap a plain ``func(*args)`` into the ``(args, line)`` builtin shape.

    Arguments are converted God Code -> Python, the return value Python ->
    God Code.  A plugin exception becomes a line-numbered GodRuntimeError;
    divine errors pass through untouched.
    """
    from godcode.errors import GodCodeError, GodRuntimeError

    def _adapter(args: list, line):
        py_args = [to_python(arg) for arg in args]
        try:
            result = func(*py_args)
        except GodCodeError:
            raise
        except Exception as exc:
            raise GodRuntimeError(
                f"The '{name}' verb faltered in the outer world: {exc}",
                line,
            ) from exc
        return to_godcode(result)

    _adapter.__name__ = f"plugin:{name}"
    _adapter.__doc__ = getattr(func, "__doc__", None)
    return _adapter
