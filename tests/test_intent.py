"""Tests for God Code v4.0 -- the intent layer (DECLARE INTENT, resolve_intent)."""

import json

import pytest

from godcode import cli
from godcode.ast import Declare, DeclareIntent
from godcode.errors import ParseError
from godcode.interpreter import Interpreter
from godcode.lexer import Lexer
from godcode.parser import Parser
from godcode.spirit import SpiritEngine


def _parse(src):
    return Parser(Lexer(src).lex()).parse()


def _creation(src):
    program = _parse(src)
    return program.statements[0].statements


def _interp():
    return Interpreter(spirit=SpiritEngine(), log_path=None)


ALIGNED_SCROLL = """\
BEGIN CREATION
  DECLARE INTENT "bring peace to the household" ON evening_blessing
  DEFINE RITE evening_blessing()
    REVEAL("peace upon this house")
  END RITE
  INVOKE evening_blessing()
END CREATION
"""

DRIFT_SCROLL = """\
BEGIN CREATION
  DECLARE INTENT "bring peace to the household" ON war_drum
  DEFINE RITE war_drum()
    DECLARE tally AS 1 + 2
    REVEAL(tally)
  END RITE
  INVOKE war_drum()
END CREATION
"""


# ------------------------------------------------------------------ parsing


class TestDeclareIntentParsing:
    def test_declare_intent_parses(self):
        (stmt,) = _creation('BEGIN CREATION\n  DECLARE INTENT "bring peace" ON rite1\nEND CREATION\n')
        assert isinstance(stmt, DeclareIntent)
        assert stmt.text == "bring peace"
        assert stmt.rite == "rite1"

    def test_keywords_are_case_insensitive(self):
        (stmt,) = _creation('BEGIN CREATION\n  declare intent "bring peace" on rite1\nEND CREATION\n')
        assert isinstance(stmt, DeclareIntent)
        assert stmt.text == "bring peace"

    def test_plain_declare_named_intent_still_works(self):
        # `DECLARE intent AS x` must not take the intent path.
        (stmt,) = _creation("BEGIN CREATION\n  DECLARE intent AS 5\nEND CREATION\n")
        assert isinstance(stmt, Declare)
        assert stmt.name == "intent"

    def test_missing_on_is_a_parse_error(self):
        with pytest.raises(ParseError):
            _parse('BEGIN CREATION\n  DECLARE INTENT "bring peace" rite1\nEND CREATION\n')

    def test_missing_quotes_is_a_parse_error(self):
        with pytest.raises(ParseError):
            _parse("BEGIN CREATION\n  DECLARE INTENT peace ON rite1\nEND CREATION\n")


# ------------------------------------------------------------------ spirit


class TestResolveIntent:
    def test_resolve_intent_keys(self):
        result = SpiritEngine().resolve_intent("bring peace to the household")
        assert set(result) == {"intent", "confidence", "spiritual_intent",
                               "suggestion", "keywords", "aligned_with"}
        assert result["intent"] == "Blessing of peace"
        assert result["aligned_with"] == []

    def test_aligned_with_names_declared_intents(self):
        spirit = SpiritEngine()
        spirit.declare_intent("evening_blessing", "bring peace to the household")
        spirit.declare_intent("war_drum", "count the harvest tally")
        result = spirit.resolve_intent("peace for the whole household tonight")
        assert len(result["aligned_with"]) == 1
        entry = result["aligned_with"][0]
        assert entry["rite"] == "evening_blessing"
        assert entry["declared"] == "bring peace to the household"
        assert "peace" in entry["shared_keywords"]

    def test_intents_aligned_true_and_false(self):
        spirit = SpiritEngine()
        aligned = spirit.classify("peace upon this house")
        assert spirit.intents_aligned("bring peace to the household", aligned) is True
        drifted = spirit.classify("xqzwk blarg zzzfnord tally seven")
        assert spirit.intents_aligned("bring peace to the household", drifted) is False

    def test_tie_break_prefers_the_true_theme(self):
        # "reveal" also appears in an unrelated row; the peace row must win
        # the tie because its vocabulary explains more of the input.
        result = SpiritEngine().classify('REVEAL("peace upon this house")')
        assert result["intent"] == "Blessing of peace"


# ------------------------------------------------------------------ runtime


class TestDeclareIntentRuntime:
    def test_aligned_invocation_blesses_and_records(self, capsys):
        interp = _interp()
        interp.run_source(ALIGNED_SCROLL)
        out = capsys.readouterr().out
        assert "[INTENT] evening_blessing walks in its declared intent" in out
        assert "[WARNING]" not in out
        assert interp.intent_checks == [
            {"rite": "evening_blessing",
             "declared": "bring peace to the household",
             "discerned": "Blessing of peace",
             "confidence": interp.intent_checks[0]["confidence"],
             "aligned": True}
        ]
        assert interp.intent_checks[0]["confidence"] > 0

    def test_drift_warns_but_never_fails_the_run(self, capsys):
        interp = _interp()
        interp.run_source(DRIFT_SCROLL)  # must not raise
        out = capsys.readouterr().out
        assert "[WARNING] war_drum drifts from its declared intent" in out
        assert "The Spirit counsels; it does not condemn." in out
        assert "3" in interp.output  # the rite still ran to completion
        (check,) = interp.intent_checks
        assert check["rite"] == "war_drum"
        assert check["aligned"] is False

    def test_intent_without_spirit_is_silent(self, capsys):
        interp = Interpreter(log_path=None)  # no spirit bound
        interp.run_source(ALIGNED_SCROLL)
        assert interp.intent_checks == []
        assert "[WARNING]" not in capsys.readouterr().out

    def test_intent_demo_example_runs_clean_in_sandbox(self):
        import os

        from godcode.sandbox import run_sandboxed_with_interpreter

        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        source = open(os.path.join(repo, "examples", "intent_demo.god"),
                      encoding="utf-8").read()
        output, interp = run_sandboxed_with_interpreter(source)
        assert output  # REVEAL lines captured
        assert len(interp.intent_checks) == 2
        assert interp.intent_checks[0]["aligned"] is True
        assert interp.intent_checks[1]["aligned"] is False


# ------------------------------------------------------------------ CLI


class TestIntentCLI:
    def test_intent_human_output(self, capsys):
        rc = cli.main(["intent", "bring peace to the household"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "[INTENT]" in out
        assert "Blessing of peace" in out

    def test_intent_json(self, capsys):
        try:
            rc = cli.main(["intent", "--json", "bring peace to the household"])
        except SystemExit as exc:
            rc = exc.code
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["command"] == "intent"
        assert payload["result"]["intent"] == "Blessing of peace"
        assert payload["result"]["aligned_with"] == []

    def test_run_json_carries_intents_array(self, tmp_path, capsys):
        scroll = tmp_path / "aligned.god"
        scroll.write_text(ALIGNED_SCROLL, encoding="utf-8")
        try:
            rc = cli.main(["run", "--json", str(scroll)])
        except SystemExit as exc:
            rc = exc.code
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        (entry,) = payload["intents"]
        assert entry["rite"] == "evening_blessing"
        assert entry["aligned"] is True
        assert entry["discerned"] == "Blessing of peace"

    def test_run_sandbox_json_carries_intents_array(self, tmp_path, capsys):
        scroll = tmp_path / "drift.god"
        scroll.write_text(DRIFT_SCROLL, encoding="utf-8")
        try:
            rc = cli.main(["run", "--sandbox", "--json", str(scroll)])
        except SystemExit as exc:
            rc = exc.code
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        (entry,) = payload["intents"]
        assert entry["aligned"] is False

    def test_fmt_round_trip(self, tmp_path, capsys):
        scroll = tmp_path / "intent.god"
        scroll.write_text(ALIGNED_SCROLL, encoding="utf-8")
        rc = cli.main(["fmt", str(scroll)])
        assert rc == 0
        out = capsys.readouterr().out
        assert 'DECLARE INTENT "bring peace to the household" ON evening_blessing' in out
        # The canonical form parses back to the same statement.
        stmts = _creation(out)
        stmt = stmts[0]
        assert isinstance(stmt, DeclareIntent)
        assert stmt.text == "bring peace to the household"
        assert stmt.rite == "evening_blessing"
