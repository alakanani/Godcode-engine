"""Tests for the God Code stdlib scrolls (spec section 9).

Each scroll is loaded from godcode/scrolls/*.god, parsed and run through the
spec interfaces (godcode.lexer.Lexer, godcode.parser.Parser,
godcode.interpreter.Interpreter), then each rite is invoked with sample
arguments via REVEAL and the revealed output is asserted.

NOTE: the lexer/parser/interpreter are built by a sibling agent. If they are
not present yet, this module skips instead of failing.
"""

import re
from pathlib import Path

import pytest

try:
    from godcode.lexer import Lexer
    from godcode.parser import Parser
    from godcode.interpreter import Interpreter

    HAVE_ENGINE = True
except ImportError:
    HAVE_ENGINE = False

pytestmark = pytest.mark.skipif(
    not HAVE_ENGINE, reason="godcode lexer/parser/interpreter not yet built by sibling agent"
)

SCROLLS = Path(__file__).resolve().parent.parent / "godcode" / "scrolls"


def invoke(scroll_name, calls):
    """Run a scroll, REVEAL each call expression, return the output lines."""
    src = (SCROLLS / scroll_name).read_text(encoding="utf-8")
    prog_src = src + "\n" + "\n".join(f"REVEAL({c})" for c in calls) + "\n"
    prog = Parser(Lexer(prog_src).lex()).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp.output


def test_math_scroll():
    out = invoke(
        "math.god",
        [
            "SQRT(16)",
            "POW(2, 10)",
            "ABS(0 - 7)",
            "ABS(7)",
            "MIN(3, 9)",
            "MAX(3, 9)",
            "FACTORIAL(5)",
            "FACTORIAL(0)",
            "IS_EVEN(4)",
            "IS_EVEN(7)",
        ],
    )
    assert abs(float(out[0]) - 4.0) < 1e-6  # SQRT(16) ~= 4
    assert out[1] == "1024"  # POW(2, 10)
    assert out[2] == "7" and out[3] == "7"  # ABS
    assert out[4] == "3" and out[5] == "9"  # MIN / MAX
    assert out[6] == "120" and out[7] == "1"  # FACTORIAL
    assert out[8] == "1" and out[9] == "0"  # IS_EVEN


def test_strings_scroll():
    out = invoke(
        "strings.god",
        [
            'SHOUT("hosanna")',
            'WHISPER("LOUD NOISE")',
            'LEN(WORDS("a b c"))',
            'LEN(CHARS("abc"))',
            'CHARS("abc")[1]',
            'FIRST("alpha")',
            'LAST("alpha")',
        ],
    )
    assert out[0] == "HOSANNA!"
    assert out[1] == "loud noise"
    assert out[2] == "3"  # WORDS splits on space
    assert out[3] == "3"  # CHARS yields one entry per character
    assert out[4] == "b"
    assert out[5] == "a"
    assert out[6] == "a"


def test_lists_scroll():
    out = invoke(
        "lists.god",
        [
            "SUM([1, 2, 3])",
            "AVG([2, 4])",
            "CONTAINS([1, 2, 3], 2)",
            "CONTAINS([1, 2, 3], 9)",
            "SECOND([10, 20, 30])",
            "LEN(TAIL([1, 2, 3, 4]))",
            "TAIL([1, 2, 3, 4])[0]",
            "COUNT([1, 2, 2, 3], 2)",
        ],
    )
    assert out[0] == "6"
    assert float(out[1]) == 3.0
    assert out[2] == "1" and out[3] == "0"
    assert out[4] == "20"
    assert out[5] == "3" and out[6] == "2"  # TAIL drops the head
    assert out[7] == "2"


def test_time_scroll():
    out = invoke("time.god", ["NOW()", "TODAY()"])
    assert out[0].strip()  # NOW beholds a timestamp
    assert re.match(r"\d{4}-\d{2}-\d{2}", out[1])  # TODAY yields a date


def test_prophecy_scroll():
    out = invoke(
        "prophecy.god",
        ["PROPHESY_NUMBER(10)", "CAST_LOTS()", 'CHOOSE(["a", "b", "c"])'],
    )
    assert 0 <= int(out[0]) < 10
    assert int(out[1]) in (0, 1)
    assert out[2] in ("a", "b", "c")


def test_covenant_scroll():
    src = (SCROLLS / "covenant.god").read_text(encoding="utf-8")
    prog_src = (
        src + '\nREVEAL(NEW_COVENANT("ark"))\nINVOKE SEAL_COVENANT(contract("noah"))\n'
    )
    prog = Parser(Lexer(prog_src).lex()).parse()
    interp = Interpreter()
    interp.run(prog)  # must complete without error (no ledger bound -> warns only)
    assert "ark" in interp.output[-1]
