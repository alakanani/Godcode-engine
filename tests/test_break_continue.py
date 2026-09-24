"""Tests for BREAK and CONTINUE (God Code loop control).

Chosen semantics (documented in docs/LANGUAGE_REFERENCE.md):
  * BREAK releases the innermost enclosing FOR/WHILE loop at once;
    CONTINUE skips to its next turn.
  * Loop signals are implemented as plain exceptions (BreakSignal /
    ContinueSignal in godcode/errors.py), following the exact pattern
    RETURN uses with ReturnSignal.
  * Signals never cross a rite boundary. The parser binds every BREAK /
    CONTINUE to a lexically enclosing loop at parse time: a rite body
    resets loop depth, so BREAK/CONTINUE with no enclosing loop is a
    PARSE_ERROR, even when the rite is defined inside a loop. The
    interpreter's _call_rite additionally converts any stray signal into
    a plain runtime error (only reachable from hand-built ASTs).

Conventions:
  * Plugins are disabled (GODCODE_NO_PLUGINS=1) so runs are hermetic.
  * Interpreter tests run source text through run_source and read output.
  * CLI tests call cli.main directly, the way test_cli.py does.
"""

import json
import os

os.environ["GODCODE_NO_PLUGINS"] = "1"

import pytest

from godcode import cli
from godcode import ast as A
from godcode.errors import GodRuntimeError, ParseError
from godcode.interpreter import Interpreter
from godcode.lexer import Lexer
from godcode.linter import lint_source
from godcode.parser import Parser


# ------------------------------------------------------------------ helpers


@pytest.fixture
def interp(tmp_path):
    return Interpreter(log_path=str(tmp_path / "godcode.log"))


def run(interp, source):
    """Run source text; return the revealed lines."""
    del interp.output[:]
    interp.run_source(source)
    return interp.output


def parse(source):
    return Parser(Lexer(source).lex()).parse()


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


# ------------------------------------------------------------ BREAK in loops


def test_break_exits_for(interp):
    out = run(interp, """\
BEGIN CREATION
  FOR n IN RANGE(1, 10)
    IF n IS 4 THEN
      BREAK
    ENDIF
    REVEAL(n)
  ENDFOR
  REVEAL("after")
END CREATION
""")
    assert out == ["1", "2", "3", "after"]


def test_break_exits_while(interp):
    out = run(interp, """\
BEGIN CREATION
  DECLARE count AS 0
  WHILE TRUE DO
    DECLARE count AS count + 1
    IF count IS 3 THEN
      BREAK
    ENDIF
  ENDWHILE
  REVEAL(count)
END CREATION
""")
    assert out == ["3"]


def test_break_in_inner_loop_only(interp):
    out = run(interp, """\
BEGIN CREATION
  FOR outer IN RANGE(1, 4)
    FOR inner IN RANGE(1, 10)
      IF inner IS 3 THEN
        BREAK
      ENDIF
      REVEAL("o{outer} i{inner}")
    ENDFOR
  ENDFOR
END CREATION
""")
    assert out == ["o1 i1", "o1 i2", "o2 i1", "o2 i2", "o3 i1", "o3 i2"]


def test_break_skips_rest_of_body(interp):
    # Statements after BREAK in the same iteration never run.
    out = run(interp, """\
BEGIN CREATION
  FOR n IN RANGE(1, 6)
    BREAK
    REVEAL("never")
  ENDFOR
  REVEAL("done")
END CREATION
""")
    assert out == ["done"]


# --------------------------------------------------------- CONTINUE in loops


def test_continue_skips_iteration_in_for(interp):
    out = run(interp, """\
BEGIN CREATION
  FOR n IN RANGE(1, 6)
    IF n % 2 IS 0 THEN
      CONTINUE
    ENDIF
    REVEAL(n)
  ENDFOR
END CREATION
""")
    assert out == ["1", "3", "5"]


def test_continue_skips_iteration_in_while(interp):
    out = run(interp, """\
BEGIN CREATION
  DECLARE count AS 0
  WHILE count < 5 DO
    DECLARE count AS count + 1
    IF count % 2 IS 0 THEN
      CONTINUE
    ENDIF
    REVEAL(count)
  ENDWHILE
END CREATION
""")
    assert out == ["1", "3", "5"]


def test_continue_in_inner_loop_only(interp):
    out = run(interp, """\
BEGIN CREATION
  FOR outer IN RANGE(1, 3)
    FOR inner IN RANGE(1, 4)
      IF inner IS 2 THEN
        CONTINUE
      ENDIF
      REVEAL("o{outer} i{inner}")
    ENDFOR
  ENDFOR
END CREATION
""")
    assert out == ["o1 i1", "o1 i3", "o2 i1", "o2 i3"]


# ------------------------------------------------------------------ lexical


def test_keywords_are_case_insensitive(interp):
    out = run(interp, """\
BEGIN CREATION
  FOR n IN RANGE(1, 10)
    IF n IS 2 THEN
      break
    ENDIF
    REVEAL(n)
  ENDFOR
  DECLARE count AS 0
  WHILE count < 5 DO
    DECLARE count AS count + 1
    IF count IS 1 THEN
      continue
    ENDIF
    REVEAL(count)
  ENDWHILE
END CREATION
""")
    assert out == ["1", "2", "3", "4", "5"]


def test_break_outside_loop_is_parse_error():
    with pytest.raises(ParseError) as exc:
        parse("BEGIN CREATION\n  BREAK\nEND CREATION\n")
    assert "inside a loop" in str(exc.value)


def test_continue_outside_loop_is_parse_error():
    with pytest.raises(ParseError) as exc:
        parse("BEGIN CREATION\n  CONTINUE\nEND CREATION\n")
    assert "inside a loop" in str(exc.value)


def test_break_after_loop_closed_is_parse_error():
    with pytest.raises(ParseError):
        parse("""\
BEGIN CREATION
  FOR n IN RANGE(3)
    REVEAL(n)
  ENDFOR
  BREAK
END CREATION
""")


def test_continue_in_if_without_loop_is_parse_error():
    with pytest.raises(ParseError):
        parse("""\
BEGIN CREATION
  IF TRUE THEN
    CONTINUE
  ENDIF
END CREATION
""")


# ------------------------------------------------------- rite boundary rule


def test_break_in_rite_without_loop_is_parse_error():
    # Even when the rite is defined inside a loop, its body is a fresh
    # boundary: the signal must not reach the caller's loop.
    with pytest.raises(ParseError) as exc:
        parse("""\
BEGIN CREATION
  DEFINE RITE seek()
    BREAK
  END RITE
END CREATION
""")
    assert "inside a loop" in str(exc.value)


def test_break_in_rite_defined_inside_loop_is_parse_error():
    with pytest.raises(ParseError):
        parse("""\
BEGIN CREATION
  FOR n IN RANGE(3)
    DEFINE RITE seek()
      BREAK
    END RITE
  ENDFOR
END CREATION
""")


def test_rite_with_own_loop_breaks_only_its_loop(interp):
    # The rite's BREAK releases the rite's loop; the caller's loop
    # continues untouched.
    out = run(interp, """\
BEGIN CREATION
  DEFINE RITE seek()
    DECLARE n AS 0
    WHILE n < 100 DO
      DECLARE n AS n + 1
      IF n IS 7 THEN
        BREAK
      ENDIF
    ENDWHILE
    RETURN n
  END RITE
  FOR round IN RANGE(1, 4)
    DECLARE result AS seek()
    REVEAL("round {round} found {result}")
  ENDFOR
END CREATION
""")
    assert out == [
        "round 1 found 7",
        "round 2 found 7",
        "round 3 found 7",
    ]


def test_signal_crossing_rite_boundary_is_runtime_error(interp):
    # The parser never produces this shape, but a hand-built AST can:
    # a bare Break inside a rite body must end in a plain error at the
    # rite's threshold, never in the caller's loop.
    body = [A.Break(line=1, col=1)]
    rite = A.DefineRite(name="rogue", params=[], body=body, line=1, col=1)
    loop = A.ForLoop(
        var="n",
        iterable=A.CallExpr(callee="RANGE", args=[A.Literal(value=3)],
                            line=2, col=1),
        body=[A.ExprStmt(
            expr=A.CallExpr(callee="rogue", args=[], line=2, col=1),
            line=2, col=1)],
        line=2, col=1,
    )
    program = A.Program(statements=[A.CreationBlock(
        statements=[rite, loop], line=1, col=1)], line=1, col=1)
    with pytest.raises(GodRuntimeError) as exc:
        interp.run(program)
    assert "threshold of a rite" in str(exc.value)


# ------------------------------------------------------------------- linter


def test_linter_accepts_break_continue(interp):
    findings = lint_source("""\
BEGIN CREATION
  FOR n IN RANGE(1, 10)
    IF n IS 4 THEN
      BREAK
    ENDIF
    IF n % 2 IS 0 THEN
      CONTINUE
    ENDIF
    REVEAL(n)
  ENDFOR
END CREATION
""")
    assert findings == []


def test_linter_gc005_flags_code_after_break():
    findings = lint_source("""\
BEGIN CREATION
  FOR n IN RANGE(3)
    BREAK
    REVEAL("never")
  ENDFOR
END CREATION
""")
    rules = [(f.rule, f.line) for f in findings]
    assert ("GC005", 4) in rules


def test_linter_gc005_flags_code_after_continue():
    findings = lint_source("""\
BEGIN CREATION
  WHILE TRUE DO
    CONTINUE
    REVEAL("never")
  ENDWHILE
END CREATION
""")
    rules = [(f.rule, f.line) for f in findings]
    assert ("GC005", 4) in rules


def test_linter_gc005_still_reports_return(interp):
    findings = lint_source("""\
BEGIN CREATION
  DEFINE RITE f()
    RETURN 1
    REVEAL("never")
  END RITE
END CREATION
""")
    assert any(f.rule == "GC005" and "RETURN" in f.message for f in findings)


# --------------------------------------------------------------- formatter


def test_fmt_round_trip(tmp_path, capsys):
    scroll = _write(tmp_path, "bc.god", """\
BEGIN CREATION
  FOR n IN RANGE(1, 6)
    IF n IS 4 THEN
      BREAK
    ENDIF
    IF n % 2 IS 0 THEN
      CONTINUE
    ENDIF
    REVEAL(n)
  ENDFOR
END CREATION
""")
    rc = cli.main(["fmt", scroll])
    assert rc == 0
    out = capsys.readouterr().out
    assert "BREAK" in out and "CONTINUE" in out
    # The canonical form parses again to the same statements.
    again = parse(out)
    assert type(again.statements[0].statements[0]).__name__ == "ForLoop"
    body_kinds = [type(s).__name__ for s in
                  again.statements[0].statements[0].body]
    assert body_kinds == ["IfStmt", "IfStmt", "Reveal"]


# --------------------------------------------------------------- CLI end to


def test_cli_check_json_rejects_break_outside_loop(tmp_path, capsys):
    scroll = _write(tmp_path, "bad.god",
                    "BEGIN CREATION\n  BREAK\nEND CREATION\n")
    with pytest.raises(SystemExit) as exc:
        cli.main(["check", "--json", scroll])
    assert exc.value.code == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["ok"] is False
    assert doc["diagnostics"][0]["code"] == "PARSE_ERROR"
    assert "inside a loop" in doc["diagnostics"][0]["message"]


def test_cli_run_sandbox_json_exercises_break_continue(tmp_path, capsys):
    scroll = _write(tmp_path, "ok.god", """\
BEGIN CREATION
  FOR outer IN RANGE(1, 4)
    FOR inner IN RANGE(1, 10)
      IF inner IS 3 THEN
        BREAK
      ENDIF
      REVEAL("o{outer} i{inner}")
    ENDFOR
  ENDFOR
END CREATION
""")
    rc = cli.main(["run", "--sandbox", "--json", scroll])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["ok"] is True
    assert doc["output"] == ["o1 i1", "o1 i2", "o2 i1", "o2 i2",
                             "o3 i1", "o3 i2"]
