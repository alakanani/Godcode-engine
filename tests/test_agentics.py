"""Tests for Mini-Pillar 5 — Agentics (`godcode check/run --json`)."""
import json

import pytest

from godcode import cli

PURE = """\
BEGIN CREATION
  DECLARE answer AS 40 + 2
  REVEAL(answer)
END CREATION
"""

BROKEN = "DECLARE AS\n"

BOOM = """\
BEGIN CREATION
  REVEAL("before")
  BREATHE LIFE INTO ghost
  REVEAL("after")
END CREATION
"""

SEALED = """\
BEGIN CREATION
  DECLARE vow AS "kept"
  SEAL(vow)
  REVEAL("sealed")
END CREATION
"""


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


# ---------------------------------------------------------------- check --json
def test_check_json_valid(tmp_path, capsys):
    scroll = _write(tmp_path, "pure.god", PURE)
    rc, payload = _main_json(["check", "--json", scroll], capsys)
    assert rc == 0
    assert payload == {
        "tool": "godcode",
        "command": "check",
        "file": scroll,
        "ok": True,
        "diagnostics": [],
    }


def test_check_json_broken(tmp_path, capsys):
    scroll = _write(tmp_path, "broken.god", BROKEN)
    rc, payload = _main_json(["check", "--json", scroll], capsys)
    assert rc == 1
    assert payload["tool"] == "godcode"
    assert payload["command"] == "check"
    assert payload["ok"] is False
    assert len(payload["diagnostics"]) == 1
    diag = payload["diagnostics"][0]
    assert diag["line"] == 1
    assert diag["code"] == "PARSE_ERROR"
    assert diag["severity"] == "error"
    assert diag["message"]  # non-empty
    assert "col" in diag and "hint" in diag


def test_check_json_missing_file(tmp_path, capsys):
    rc, payload = _main_json(
        ["check", "--json", str(tmp_path / "nope.god")], capsys)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["diagnostics"][0]["code"] == "FILE_ERROR"


# ------------------------------------------------------------------ run --json
def test_run_json_success(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep covenant.chain + logs out of the repo
    scroll = _write(tmp_path, "pure.god", PURE)
    rc, payload = _main_json(["run", "--json", scroll], capsys)
    assert rc == 0
    assert payload["tool"] == "godcode"
    assert payload["command"] == "run"
    assert payload["ok"] is True
    assert payload["output"] == ["42"]
    assert payload["error"] is None
    assert payload["seals"] == []
    assert isinstance(payload["stats"]["ms"], int)


def test_run_json_runtime_error(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scroll = _write(tmp_path, "boom.god", BOOM)
    rc, payload = _main_json(["run", "--json", scroll], capsys)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["output"] == ["before"]  # lines revealed before the error
    err = payload["error"]
    assert err["code"] == "RUNTIME_ERROR"
    assert err["line"] == 3
    assert err["message"]


def test_run_json_seals(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scroll = _write(tmp_path, "sealed.god", SEALED)
    rc, payload = _main_json(["run", "--json", scroll], capsys)
    assert rc == 0
    assert payload["ok"] is True
    assert len(payload["seals"]) == 1
    seal = payload["seals"][0]
    assert seal["block"] == 0
    assert len(seal["hash"]) == 64


# ------------------------------------------------------------ output hygiene
def test_json_output_is_single_clean_document(tmp_path, capsys):
    scroll = _write(tmp_path, "pure.god", PURE)
    try:
        cli.main(["check", "--json", scroll])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert captured.out.strip().startswith("{")
    assert captured.out.strip().endswith("}")
    json.loads(captured.out)  # no non-JSON noise on stdout
