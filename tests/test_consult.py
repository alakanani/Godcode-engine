"""Tests for God Code v4.0 -- CONSULT, the local Spirit oracle."""

import os

import pytest

from godcode.errors import GodRuntimeError
from godcode.interpreter import Interpreter
from godcode.sandbox import run_sandboxed
from godcode.spirit import SpiritEngine


def _interp(with_spirit=True):
    return Interpreter(
        spirit=SpiritEngine() if with_spirit else None, log_path=None
    )


class TestCounsel:
    def test_counsel_is_two_to_three_sentences(self):
        counsel = SpiritEngine().counsel("How should I structure this covenant?")
        assert isinstance(counsel, str) and counsel.strip()
        sentences = [s for s in counsel.split(". ") if s.strip()]
        assert 2 <= len(sentences) <= 3

    def test_counsel_names_the_question_and_intent(self):
        counsel = SpiritEngine().counsel("How should I structure this covenant?")
        assert "How should I structure this covenant?" in counsel
        assert "Anchor a covenant" in counsel
        assert "counsel of heaven" in counsel


class TestConsultBuiltin:
    def test_consult_returns_counsel_string(self):
        interp = _interp()
        interp.run_source(
            'BEGIN CREATION\n  REVEAL(CONSULT("How should I structure this covenant?"))\nEND CREATION\n'
        )
        (line,) = interp.output
        assert "counsel of heaven" in line

    def test_consult_case_insensitive(self):
        interp = _interp()
        interp.run_source(
            'BEGIN CREATION\n  REVEAL(consult("How should I structure this covenant?"))\nEND CREATION\n'
        )
        assert interp.output[0].startswith("Concerning")

    def test_consult_without_spirit_is_gentle(self):
        interp = _interp(with_spirit=False)
        interp.run_source(
            'BEGIN CREATION\n  REVEAL(CONSULT("What now?"))\nEND CREATION\n'
        )
        assert "silent" in interp.output[0].lower()

    def test_consult_needs_a_question_word(self):
        interp = _interp()
        with pytest.raises(GodRuntimeError):
            interp.run_source("BEGIN CREATION\n  REVEAL(CONSULT(42))\nEND CREATION\n")

    def test_consult_demo_example_runs_clean_in_sandbox(self):
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        source = open(os.path.join(repo, "examples", "consult_demo.god"),
                      encoding="utf-8").read()
        output = run_sandboxed(source)
        assert len(output) == 2
        assert all("counsel of heaven" in line for line in output)
