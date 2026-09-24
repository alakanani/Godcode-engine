"""Date, time, and web rites for the God Code standard library (part 2).

``register(interp)`` adds four rites to an interpreter's ``_builtins``:

- ``DATE_TODAY()`` — today's local date as a word: ``"2026-09-24"``.
- ``TIME_NOW()`` — the current local time as an ISO 8601 word.
- ``FORMAT_DATE(date_text, pattern)`` — a ``"YYYY-MM-DD"`` word shaped by
  a strftime-style pattern word.
- ``HTTP_GET(url)`` — the body of an HTTP GET request, as a UTF-8 word.

The names avoid ``NOW`` and ``TODAY`` on purpose: the bundled scroll
``godcode/scrolls/time.god`` already defines rites by those names, and a
builtin would shadow them. ``DATE_TODAY``, ``TIME_NOW``, ``FORMAT_DATE``,
and ``HTTP_GET`` keep their distance.

``HTTP_GET`` follows redirects and waits up to ten seconds. Under
``godcode run --sandbox`` the rite is withheld when the policy denies
network (see ``godcode/sandbox.py``): it raises instead of reaching out.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import date, datetime

from godcode.errors import GodRuntimeError

__all__ = ["register"]

_HTTP_TIMEOUT_SECONDS = 10


def register(interp) -> None:
    """Add the date/time and web rites to ``interp._builtins``.

    Each rite is a callable taking ``(args, line)``, in the same shape as
    the core builtins in ``godcode/interpreter.py``.
    """
    builtins = interp._builtins

    def date_today(args, line):
        interp._arity("DATE_TODAY", args, 0, line)
        return date.today().isoformat()

    def time_now(args, line):
        interp._arity("TIME_NOW", args, 0, line)
        return datetime.now().astimezone().isoformat()

    def format_date(args, line):
        interp._arity("FORMAT_DATE", args, 2, line)
        date_text, pattern = args
        if not isinstance(date_text, str):
            raise GodRuntimeError(
                "FORMAT_DATE needs the date as a word, not "
                f"{interp.type_name(date_text)}.",
                line,
            )
        if not isinstance(pattern, str):
            raise GodRuntimeError(
                "FORMAT_DATE needs the pattern as a word, not "
                f"{interp.type_name(pattern)}.",
                line,
            )
        try:
            day = datetime.strptime(date_text.strip(), "%Y-%m-%d")
        except ValueError:
            raise GodRuntimeError(
                f"FORMAT_DATE cannot read '{date_text}' as a date. "
                "Write it YYYY-MM-DD.",
                line,
            ) from None
        return day.strftime(str(pattern))

    def http_get(args, line):
        interp._arity("HTTP_GET", args, 1, line)
        url = args[0]
        if not isinstance(url, str):
            raise GodRuntimeError(
                "HTTP_GET needs the address as a word, not "
                f"{interp.type_name(url)}.",
                line,
            )
        request = urllib.request.Request(
            str(url), headers={"User-Agent": "GodCode"}
        )
        try:
            with urllib.request.urlopen(
                request, timeout=_HTTP_TIMEOUT_SECONDS
            ) as response:
                body = response.read()
        except Exception:
            # Every network failure — refused, unroutable, timed out,
            # bad address — is answered the same plain way. It never
            # hangs past the timeout and never succeeds silently.
            raise GodRuntimeError(
                f"HTTP_GET could not reach '{url}'. The web did not answer.",
                line,
            ) from None
        return body.decode("utf-8", errors="replace")

    builtins["DATE_TODAY"] = date_today
    builtins["TIME_NOW"] = time_now
    builtins["FORMAT_DATE"] = format_date
    builtins["HTTP_GET"] = http_get
