"""Clockwork — the exemplary God Code plugin (Pillar 3).

Time verbs, namespaced as ``clockwork.*`` and called through SUMMON::

    REVEAL(SUMMON("clockwork.now"))          -- ISO-8601 timestamp (UTC)
    SUMMON("clockwork.sleep_ms", 250)        -- rest for 250 milliseconds
    SUMMON("clockwork.mark", "psalm")        -- start a stopwatch named "psalm"
    REVEAL(SUMMON("clockwork.elapsed_ms", "psalm"))

Install it by placing this file in ``./plugins`` or ``~/.godcode/plugins`` —
no configuration, no restart ceremony beyond starting the interpreter.

Trust note: plugins are trusted host code.  ``sleep_ms`` really sleeps the
host process; a mischievous plugin could do worse.  Only install plugins from
sources you trust, and set GODCODE_NO_PLUGINS=1 when running untrusted
scrolls in a locked-down environment.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

PLUGIN_API_VERSION = 1

_marks: dict[str, float] = {}


def _now() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _sleep_ms(ms) -> float:
    """Sleep *ms* milliseconds; returns the milliseconds slept."""
    try:
        amount = float(ms)
    except (TypeError, ValueError):
        raise ValueError(f"sleep_ms needs a number of milliseconds, not {ms!r}")
    if amount < 0:
        raise ValueError("sleep_ms cannot sleep a negative span")
    time.sleep(amount / 1000.0)
    return amount


def _mark(name) -> str:
    """Start (or restart) a stopwatch called *name*; returns the name."""
    key = str(name)
    _marks[key] = time.perf_counter()
    return key


def _elapsed_ms(name) -> float:
    """Milliseconds since ``mark(name)`` was last called."""
    key = str(name)
    try:
        start = _marks[key]
    except KeyError:
        raise ValueError(f"no mark named {key!r} — call mark({key!r}) first") from None
    return (time.perf_counter() - start) * 1000.0


def register(interpreter):
    """The plugin contract: add our verbs to the interpreter."""
    interpreter.register_plugin_verb("clockwork.now", _now, plugin="clockwork")
    interpreter.register_plugin_verb("clockwork.sleep_ms", _sleep_ms, plugin="clockwork")
    interpreter.register_plugin_verb("clockwork.mark", _mark, plugin="clockwork")
    interpreter.register_plugin_verb("clockwork.elapsed_ms", _elapsed_ms, plugin="clockwork")
