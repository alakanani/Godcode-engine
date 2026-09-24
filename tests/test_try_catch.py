"""Tests for TRY/CATCH error handling and uncaught-error call traces."""

import json

import pytest

from godcode import cli
from godcode.errors import GodRuntimeError, ParseError, SandboxViolation
from godcode.interpreter import Interpreter
from godcode.linter import lint_source
from godcode.sandbox import run_sandboxed

CAUGHT = """\
BEGIN CREATION
TRY
  DECLARE x AS 1 / 0
  REVEAL("not reached")
CATCH
  REVEAL("caught: {ERROR}")
ENDTRY
REVEAL("after")
END CREATION
"""

NAMED = """\
BEGIN CREATION
TRY
  DECLARE x AS 1 / 0
CATCH trouble
  REVEAL("trouble was: {trouble}")
ENDTRY
END CREATION
"""

NO_ERROR = """\
BEGIN CREATION
TRY
  REVEAL("steady")
CATCH
  REVEAL("must not run")
ENDTRY
REVEAL("after")
END CREATION
"""

RITE_ERROR = """\
BEGIN CREATION
DEFINE RITE risky()
  DECLARE x AS 1 / 0
END RITE
TRY
  INVOKE risky()
  REVEAL("not reached")
CATCH
  REVEAL("caught from rite")
ENDTRY
REVEAL("after")
END CREATION
"""

NESTED = """\
BEGIN CREATION
TRY
  TRY
    DECLARE x AS 1 / 0
  CATCH inner_err
    REVEAL("inner: {inner_err}")
    DECLARE y AS 1 / 0
  ENDTRY
CATCH outer_err
  REVEAL("outer: {outer_err}")
ENDTRY
REVEAL("done")
END CREATION
"""

CATCH_RAISES = """\
BEGIN CREATION
TRY
  DECLARE x AS 1 / 0
CATCH
  DECLARE y AS 1 / 0
ENDTRY
END CREATION
"""

RETURN_IN_TRY = """\
BEGIN CREATION
DEFINE RITE early()
  TRY
    RETURN 42
  CATCH
    REVEAL("must not run")
  ENDTRY
END RITE
REVEAL(INVOKE early())
END CREATION
"""

ASCEND_IN_TRY = """\
BEGIN CREATION
TRY
  ASCEND
CATCH
  REVEAL("must not run")
ENDTRY
REVEAL("never")
END CREATION
"""

TRACE_SCROLL = """\
BEGIN CREATION
DEFINE RITE innermost()
  DECLARE x AS 1 / 0
END RITE
DEFINE RITE middle()
  INVOKE innermost()
END RITE
DEFINE RITE outer()
  INVOKE middle()
END RITE
INVOKE outer()
END CREATION
"""

EXPECTED_TRACE = [
    {"rite": "outer", "line": 11},
    {"rite": "middle", "line": 9},
    {"rite": "innermost", "line": 6},
]

TOP_LEVEL_ERROR = """\
BEGIN CREATION
DECLARE x AS 1 / 0
END CREATION
"""


def _run(source: str):
    """Run a creation; return (output lines, interpreter)."""
    interp = Interpreter()
    interp.run_source(source, source_name="test.god")
    return interp.output, interp


def _fails(source: str):
    """Run a creation that must raise GodRuntimeError; return the error."""
    interp = Interpreter()
    with pytest.raises(GodRuntimeError) as exc:
        interp.run_source(source, source_name="test.god")
    return exc.value


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _main_json(argv, capsys):
    """Run the CLI, returning (rc, parsed_stdout_json)."""
    try:
        rc = cli.main(argv)  # main() only raises SystemExit on non-zero
    except SystemExit as exc:
        rc = exc.code
    out = capsys.readouterr().out
    return rc, json.loads(out)  # raises if stdout is not pure JSON


# ------------------------------------------------------- TRY / CATCH semantics


class TestTryCatch:
    def test_caught_error_runs_catch_and_binds_error(self):
        output, _ = _run(CAUGHT)
        assert "not reached" not in output
        assert output[0].startswith("caught: ")
        assert "Division by nothing is not permitted" in output[0]
        assert output[1] == "after"

    def test_named_catch_binding(self):
        output, _ = _run(NAMED)
        assert len(output) == 1
        assert output[0].startswith("trouble was: ")
        assert "Division by nothing is not permitted" in output[0]

    def test_no_error_skips_catch(self):
        output, _ = _run(NO_ERROR)
        assert output == ["steady", "after"]

    def test_error_in_called_rite_is_caught(self):
        output, _ = _run(RITE_ERROR)
        assert output == ["caught from rite", "after"]

    def test_nested_try_inner_handles_inner_error(self):
        output, _ = _run(NESTED)
        assert len(output) == 3
        assert output[0].startswith("inner: ")
        assert "Division by nothing is not permitted" in output[0]
        # The error raised inside the inner CATCH propagates outward.
        assert output[1].startswith("outer: ")
        assert output[2] == "done"

    def test_error_inside_catch_propagates(self):
        err = _fails(CATCH_RAISES)
        assert "Division by nothing is not permitted" in err.msg

    def test_return_inside_try_still_returns(self):
        output, _ = _run(RETURN_IN_TRY)
        assert output == ["42"]

    def test_ascend_inside_try_still_ends_run(self):
        output, _ = _run(ASCEND_IN_TRY)
        assert output == []  # CATCH never ran; the run ascended in peace

    def test_bound_message_is_the_plain_message(self):
        err = _fails(CATCH_RAISES)
        output, _ = _run(
            "BEGIN CREATION\n"
            "TRY\n"
            "  DECLARE x AS 1 / 0\n"
            "CATCH msg\n"
            "  REVEAL(msg)\n"
            "ENDTRY\n"
            "END CREATION\n"
        )
        # The CATCH sees the clean message, without the "(line N)" suffix.
        assert output == [err.msg]
        assert "(line" not in output[0]

    def test_parse_error_still_fails_before_running(self):
        with pytest.raises(ParseError):
            Interpreter().run_source(
                "BEGIN CREATION\nTRY\n  REVEAL(1)\nCATCH\n  REVEAL(2)\n"
                "END CREATION\n",
                source_name="test.god",
            )

    def test_sandbox_violation_is_not_caught(self):
        # SandboxViolation is a GodCodeError but not a GodRuntimeError:
        # the sandbox's boundaries cannot be swallowed by TRY.
        scroll = (
            "BEGIN CREATION\n"
            "TRY\n"
            '  DECLARE name AS ASK("Who goes there? ")\n'
            "CATCH\n"
            '  REVEAL("must not run")\n'
            "ENDTRY\n"
            "END CREATION\n"
        )
        with pytest.raises(SandboxViolation):
            run_sandboxed(scroll)

    def test_caught_error_inside_sandbox_still_works(self):
        output = run_sandboxed(CAUGHT)
        assert output[0].startswith("caught: ")
        assert output[1] == "after"


# ---------------------------------------------------------------- call traces


class TestCallTrace:
    def test_trace_snapshot_on_error(self):
        err = _fails(TRACE_SCROLL)
        assert err.call_trace == EXPECTED_TRACE

    def test_trace_json(self, tmp_path, capsys):
        scroll = _write(tmp_path, "trace.god", TRACE_SCROLL)
        rc, payload = _main_json(["run", "--json", str(scroll)], capsys)
        assert rc == 1
        error = payload["error"]
        # Every existing field is unchanged; "trace" is the only addition.
        assert error["line"] == 3
        assert error["code"] == "RUNTIME_ERROR"
        assert error["severity"] == "error"
        assert "Division by nothing is not permitted" in error["message"]
        assert error["hint"]
        assert error["trace"] == EXPECTED_TRACE

    def test_trace_json_sandbox(self, tmp_path, capsys):
        scroll = _write(tmp_path, "trace.god", TRACE_SCROLL)
        rc, payload = _main_json(
            ["run", "--sandbox", "--json", str(scroll)], capsys)
        assert rc == 1
        assert payload["error"]["trace"] == EXPECTED_TRACE

    def test_trace_text_below_gentle_error(self, tmp_path, capsys):
        scroll = _write(tmp_path, "trace.god", TRACE_SCROLL)
        with pytest.raises(SystemExit) as exc:
            cli.main(["run", str(scroll), "--log", str(tmp_path / "run.log")])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        # The gentle rendering is preserved exactly: message, source line.
        assert "Division by nothing is not permitted" in err
        assert "3 |   DECLARE x AS 1 / 0" in err
        # The trace goes underneath, oldest call first.
        pos_outer = err.index("Called by outer at line 11")
        pos_middle = err.index("Called by middle at line 9")
        pos_inner = err.index("Called by innermost at line 6")
        assert pos_outer < pos_middle < pos_inner
        assert err.index("(most recent call last)") > pos_inner

    def test_trace_text_sandbox(self, tmp_path, capsys):
        scroll = _write(tmp_path, "trace.god", TRACE_SCROLL)
        with pytest.raises(SystemExit) as exc:
            cli.main(["run", "--sandbox", str(scroll)])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "Called by outer at line 11" in err
        assert "Called by innermost at line 6" in err
        assert "(most recent call last)" in err

    def test_no_trace_section_at_top_level(self, tmp_path, capsys):
        scroll = _write(tmp_path, "top.god", TOP_LEVEL_ERROR)
        rc, payload = _main_json(["run", "--json", str(scroll)], capsys)
        assert rc == 1
        assert payload["error"]["trace"] == []
        with pytest.raises(SystemExit):
            cli.main(["run", str(scroll), "--log", str(tmp_path / "run.log")])
        assert "Called by" not in capsys.readouterr().err


# ------------------------------------------------------------------ tooling


class TestTryCatchTooling:
    def test_fmt_round_trip(self, tmp_path, capsys):
        scroll = _write(tmp_path, "try.god", CAUGHT)
        assert cli.main(["fmt", scroll]) == 0
        first = capsys.readouterr().out
        assert "TRY" in first
        assert "CATCH" in first
        assert "ENDTRY" in first
        again = _write(tmp_path, "try2.god", first)
        assert cli.main(["fmt", again]) == 0
        assert capsys.readouterr().out == first
        # The formatted scroll runs the same as the original.
        out1, _ = _run(CAUGHT)
        out2, _ = _run(first)
        assert out1 == out2

    def test_fmt_preserves_named_catch(self, tmp_path, capsys):
        scroll = _write(tmp_path, "named.god", NAMED)
        assert cli.main(["fmt", scroll]) == 0
        assert "CATCH trouble" in capsys.readouterr().out

    def test_lint_try_catch_clean(self):
        findings = lint_source(
            "BEGIN CREATION\n"
            "TRY\n"
            '  REVEAL(LEN("grace"))\n'
            "CATCH trouble\n"
            '  REVEAL("trouble was: {trouble}")\n'
            "ENDTRY\n"
            "END CREATION\n",
            source_name="try.god",
        )
        assert findings == []

    def test_lint_bare_catch_binding_not_flagged(self):
        findings = lint_source(CAUGHT, source_name="try.god")
        rules = {(f.rule, f.message) for f in findings}
        # The implicit ERROR binding is never an undefined or unused name.
        assert not any("ERROR" in message for _, message in rules)

    def test_lint_empty_bodies_flagged(self):
        findings = lint_source(
            "BEGIN CREATION\nTRY\nCATCH\nENDTRY\nEND CREATION\n",
            source_name="try.god",
        )
        rules = {f.rule for f in findings}
        assert "GC004" in rules

    def test_lint_walks_try_bodies(self):
        # An undefined name inside TRY is still reported: the linter
        # walks the new nodes instead of skipping them.
        findings = lint_source(
            "BEGIN CREATION\n"
            "TRY\n"
            "  REVEAL(no_such_name)\n"
            "CATCH\n"
            "  REVEAL(1)\n"
            "ENDTRY\n"
            "END CREATION\n",
            source_name="try.god",
        )
        assert any(f.rule == "GC002" and "no_such_name" in f.message
                   for f in findings)
