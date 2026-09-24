"""Tests for gentler errors: "Did you mean?" suggestions and source-line
rendering (format_error) in the human CLI."""

import pytest

from godcode.environment import Environment
from godcode.errors import (
    GodRuntimeError,
    format_error,
    suggest_similar,
    with_suggestion,
)
from godcode.interpreter import Interpreter


def _run(source: str):
    """Run a creation; return the GodRuntimeError it raises."""
    interp = Interpreter()
    with pytest.raises(GodRuntimeError) as exc:
        interp.run_source(source, source_name="test.god")
    return exc.value


# ------------------------------------------------------------------ suggest_similar


class TestSuggestSimilar:
    def test_close_rite_name_found(self):
        assert suggest_similar("BLESSIN", ["BLESSING", "BLESS"]) == "BLESSING"

    def test_nothing_close_returns_none(self):
        assert suggest_similar("ZZZQQQ", ["BLESSING", "GRACE"]) is None

    def test_matching_is_case_insensitive(self):
        assert suggest_similar("blessin", ["BLESSING"]) == "BLESSING"

    def test_exact_name_needs_no_suggestion(self):
        assert suggest_similar("BLESSING", ["BLESSING"]) is None

    def test_empty_candidates(self):
        assert suggest_similar("BLESSIN", []) is None


class TestWithSuggestion:
    def test_appends_when_close(self):
        msg = with_suggestion("no such rite", "BLESSIN", ["BLESSING"])
        assert msg == "no such rite Did you mean 'BLESSING'?"

    def test_unchanged_when_nothing_close(self):
        msg = with_suggestion("no such rite", "ZZZQQQ", ["BLESSING"])
        assert msg == "no such rite"


# ------------------------------------------------------- interpreter messages


class TestInterpreterSuggestions:
    def test_unknown_rite_suggests(self):
        err = _run(
            "BEGIN CREATION\n"
            "  DEFINE RITE BLESSING(name)\n"
            "    RETURN name\n"
            "  END RITE\n"
            "  INVOKE BLESSIN(\"seeker\")\n"
            "END CREATION\n"
        )
        assert "Did you mean 'BLESSING'?" in str(err)

    def test_unknown_rite_no_suggestion_when_far(self):
        err = _run("BEGIN CREATION\n  INVOKE ZZZQQQ(\"seeker\")\nEND CREATION\n")
        assert "Did you mean" not in str(err)

    def test_unknown_builtin_suggests(self):
        err = _run('BEGIN CREATION\n  REVEAL(UPPE("grace"))\nEND CREATION\n')
        assert "Did you mean 'UPPER'?" in str(err)

    def test_breathe_suggests_close_name(self):
        err = _run(
            "BEGIN CREATION\n"
            '  DECLARE word AS "grace"\n'
            "  BREATHE LIFE INTO wrod\n"
            "END CREATION\n"
        )
        assert "Did you mean 'word'?" in str(err)

    def test_bless_suggests_close_name(self):
        err = _run(
            "BEGIN CREATION\n"
            '  DECLARE pact AS contract("everlasting")\n'
            "  BLESS patc\n"
            "END CREATION\n"
        )
        assert "Did you mean 'pact'?" in str(err)

    def test_map_missing_key_suggests(self):
        err = _run(
            "BEGIN CREATION\n"
            "  DECLARE receipt AS ANCHOR(\"grace\")\n"
            '  REVEAL(receipt["anchor_hsh"])\n'
            "END CREATION\n"
        )
        assert "Did you mean 'anchor_hash'?" in str(err)

    def test_reshape_suggests_close_name(self):
        env = Environment()
        env.define("grace", 1)
        with pytest.raises(GodRuntimeError) as exc:
            env.set_existing("graec", 2)
        assert "Did you mean 'grace'?" in str(exc.value)


# ---------------------------------------------------------------- format_error


class TestFormatError:
    SOURCE = "BEGIN CREATION\n  INVOKE BLESSIN(\"seeker\")\nEND CREATION\n"

    def _err(self, line=None, col=None):
        return GodRuntimeError("There is no rite named 'BLESSIN'.", line, col)

    def test_line_shown_with_gutter(self):
        out = format_error(self.SOURCE, self._err(line=2))
        assert "There is no rite named 'BLESSIN'." in out
        assert '  2 |   INVOKE BLESSIN("seeker")' in out
        assert "^" not in out

    def test_caret_marks_column(self):
        out = format_error(self.SOURCE, self._err(line=2, col=11))
        lines = out.splitlines()
        assert lines[1] == '  2 |   INVOKE BLESSIN("seeker")'
        assert lines[2] == " " * len("  2 | ") + " " * 10 + "^"

    def test_no_line_degrades_to_message(self):
        out = format_error(self.SOURCE, self._err())
        assert out == "There is no rite named 'BLESSIN'."

    def test_out_of_range_line_degrades(self):
        out = format_error(self.SOURCE, self._err(line=99))
        assert out == "There is no rite named 'BLESSIN'. (line 99)"

    def test_out_of_range_column_skips_caret(self):
        out = format_error(self.SOURCE, self._err(line=2, col=500))
        assert "^" not in out


# ------------------------------------------------------------ CLI integration


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


class TestCliErrorRendering:
    def test_run_shows_source_line(self, tmp_path, capsys):
        from godcode import cli

        scroll = _write(
            tmp_path,
            "broken.god",
            "BEGIN CREATION\n"
            "  DEFINE RITE BLESSING(name)\n"
            '    RETURN "grace upon " + name\n'
            "  END RITE\n"
            '  INVOKE BLESSIN("seeker")\n'
            "END CREATION\n",
        )
        with pytest.raises(SystemExit) as exc:
            cli.main(["run", str(scroll), "--log", str(tmp_path / "run.log")])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "Did you mean 'BLESSING'?" in err
        assert '  5 |   INVOKE BLESSIN("seeker")' in err

    def test_check_shows_source_line_and_caret(self, tmp_path, capsys):
        from godcode import cli

        scroll = _write(tmp_path, "bad.god", "BEGIN CREATION\n  REVEAL(\nEND CREATION\n")
        with pytest.raises(SystemExit) as exc:
            cli.main(["check", str(scroll)])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "  2 |   REVEAL(" in err

    def test_run_json_diagnostic_carries_suggestion(self, tmp_path, capsys):
        import json

        from godcode import cli

        scroll = _write(
            tmp_path,
            "broken.god",
            "BEGIN CREATION\n  INVOKE BLESSIN(\"seeker\")\nEND CREATION\n",
        )
        with pytest.raises(SystemExit) as exc:
            cli.main(["run", "--json", str(scroll), "--log", str(tmp_path / "r.log")])
        assert exc.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert "Did you mean" in payload["error"]["message"]

    def test_sandbox_run_shows_source_line(self, tmp_path, capsys):
        from godcode import cli

        scroll = _write(
            tmp_path,
            "broken.god",
            "BEGIN CREATION\n  INVOKE BLESSIN(\"seeker\")\nEND CREATION\n",
        )
        with pytest.raises(SystemExit) as exc:
            cli.main(["run", "--sandbox", str(scroll), "--log", str(tmp_path / "r.log")])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "  2 |   INVOKE BLESSIN" in err
