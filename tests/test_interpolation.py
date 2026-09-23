"""Tests for string interpolation: "grace upon {name}".

``{expr}`` inside a double-quoted string breathes the expression's revealed
value into the string. ``{{`` and ``}}`` write a plain brace; a lone ``}``
stays a plain brace.
"""

import pytest

from godcode import run_source
from godcode.errors import GodCodeError


def revealed(src: str) -> str:
    result = run_source(src)
    assert result.ok, f"expected ok, got error: {result.error}"
    return result.output


def test_interpolates_a_name():
    out = revealed(
        'BEGIN CREATION\nDECLARE name AS "seeker"\nREVEAL("grace upon {name}")\nEND CREATION'
    )
    assert out == "grace upon seeker"


def test_interpolates_expressions():
    out = revealed(
        "BEGIN CREATION\nDECLARE a AS 6\nDECLARE b AS 7\n"
        'REVEAL("{a} times {b} is {a * b}")\nEND CREATION'
    )
    assert out == "6 times 7 is 42"


def test_interpolates_builtin_calls():
    out = revealed(
        'BEGIN CREATION\nDECLARE name AS "world"\nREVEAL("{UPPER(name)}, {LEN(name)} letters")\nEND CREATION'
    )
    assert out == "WORLD, 5 letters"


def test_interpolates_lists_and_comparisons():
    out = revealed(
        "BEGIN CREATION\nDECLARE xs AS [1, 2, 3]\n"
        'REVEAL("count {LEN(xs)}, first {xs[0]}, even {2 IS 2}")\nEND CREATION'
    )
    assert out == "count 3, first 1, even true"


def test_interpolates_symbols_and_void():
    out = revealed(
        "BEGIN CREATION\n"
        'REVEAL("unnamed {worthy}")\n'
        "DEFINE RITE quiet()\nEND RITE\n"
        'REVEAL("rite returns {INVOKE quiet()}")\n'
        "END CREATION"
    )
    assert out == "unnamed worthy\nrite returns void"


def test_adjacent_and_repeated_braces():
    out = revealed(
        'BEGIN CREATION\nDECLARE who AS "seeker"\nREVEAL("{who}{who}")\nEND CREATION'
    )
    assert out == "seekerseeker"


def test_double_braces_escape():
    out = revealed(
        'BEGIN CREATION\nREVEAL("plain {{ braces }} stay")\nEND CREATION'
    )
    assert out == "plain { braces } stay"


def test_mixed_escape_and_interpolation():
    out = revealed(
        'BEGIN CREATION\nDECLARE n AS 7\nREVEAL("{{{n}}}")\nEND CREATION'
    )
    assert out == "{7}"


def test_lone_close_brace_stays_literal():
    out = revealed('BEGIN CREATION\nREVEAL("a } b")\nEND CREATION')
    assert out == "a } b"


def test_nested_string_with_interpolation():
    out = revealed(
        'BEGIN CREATION\nDECLARE n AS 3\nREVEAL("nested {\\"inner {n}\\"}")\nEND CREATION'
    )
    assert out == "nested inner 3"


def test_plain_strings_unaffected():
    out = revealed('BEGIN CREATION\nREVEAL("no braces here")\nEND CREATION')
    assert out == "no braces here"


def test_interpolation_inside_rite():
    out = revealed(
        "BEGIN CREATION\n"
        "DEFINE RITE greet(name)\n"
        '    REVEAL("peace upon {name}")\n'
        "END RITE\n"
        'INVOKE greet("household")\n'
        "END CREATION"
    )
    assert out == "peace upon household"


def test_interpolation_in_declare():
    out = revealed(
        'BEGIN CREATION\nDECLARE name AS "dawn"\nDECLARE greeting AS "good {name}"\nREVEAL(greeting)\nEND CREATION'
    )
    assert out == "good dawn"


def test_unterminated_brace_is_friendly():
    result = run_source('BEGIN CREATION\nREVEAL("oops {name")\nEND CREATION')
    assert not result.ok
    assert "never sealed" in result.error


def test_empty_braces_is_friendly():
    result = run_source('BEGIN CREATION\nREVEAL("empty {}")\nEND CREATION')
    assert not result.ok
    assert "empty braces" in result.error


def test_broken_expression_inside_braces():
    result = run_source('BEGIN CREATION\nREVEAL("{name + }")\nEND CREATION')
    assert not result.ok
    assert isinstance(result.error, str)


def test_unbound_name_becomes_symbol():
    out = revealed('BEGIN CREATION\nREVEAL("hello {stranger}")\nEND CREATION')
    assert out == "hello stranger"


def test_works_in_sandbox():
    from godcode.sandbox import run_sandboxed

    output = run_sandboxed(
        'BEGIN CREATION\nDECLARE n AS 21\nREVEAL("doubled {n * 2}")\nEND CREATION'
    )
    assert output == ["doubled 42"]


def test_fmt_round_trips_interpolation(tmp_path):
    from godcode.cli import CanonicalFormatter
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    src = 'BEGIN CREATION\nDECLARE name AS "seeker"\nREVEAL("grace upon {name}")\nEND CREATION\n'
    program = Parser(Lexer(src).lex()).parse()
    assert CanonicalFormatter().format(program) == (
        'BEGIN CREATION\n  DECLARE name AS "seeker"\n  REVEAL("grace upon {name}")\nEND CREATION\n'
    )


def test_check_json_reports_brace_diagnostics(tmp_path):
    import json
    import subprocess
    import sys

    scroll = tmp_path / "bad.god"
    scroll.write_text('BEGIN CREATION\nREVEAL("oops {name")\nEND CREATION\n')
    proc = subprocess.run(
        [sys.executable, "-m", "godcode", "check", "--json", str(scroll)],
        capture_output=True, text=True, cwd=".",
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["diagnostics"][0]["code"] == "PARSE_ERROR"
    assert "never sealed" in payload["diagnostics"][0]["message"]
