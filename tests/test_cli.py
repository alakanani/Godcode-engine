"""Tests for the God Code CLI (godcode/cli.py)."""
import pytest

from godcode import cli

SCROLL = """\
BEGIN CREATION
  DECLARE answer AS 40 + 2
  REVEAL(answer)
END CREATION
"""


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_run_declare_reveal(tmp_path, capsys):
    scroll = _write(tmp_path, "t.god", SCROLL)
    rc = cli.main(["run", str(scroll), "--log", str(tmp_path / "run.log")])
    assert rc == 0
    assert "42" in capsys.readouterr().out


def test_run_missing_file(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", "no_such_scroll.god"])
    assert exc.value.code == 1
    assert "no_such_scroll.god" in capsys.readouterr().err


def test_check_valid(tmp_path, capsys):
    scroll = _write(tmp_path, "pure.god", SCROLL)
    rc = cli.main(["check", str(scroll)])
    assert rc == 0
    assert "is pure" in capsys.readouterr().out


def test_check_invalid(tmp_path, capsys):
    scroll = _write(tmp_path, "broken.god", "DECLARE AS\n")
    with pytest.raises(SystemExit) as exc:
        cli.main(["check", str(scroll)])
    assert exc.value.code == 1
    assert capsys.readouterr().err.strip() != ""


def test_fmt_canonical(tmp_path, capsys):
    messy = ("begin creation\n"
             "declare x as 1+2*3\n"
             "if x is 7 then reveal(\"seven\") else reveal(\"other\")\n"
             "reveal(x)\n"
             "end creation\n")
    scroll = _write(tmp_path, "messy.god", messy)
    rc = cli.main(["fmt", str(scroll)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "BEGIN CREATION" in out
    assert "END CREATION" in out
    assert "DECLARE x AS 1 + 2 * 3" in out
    assert "IF x == 7 THEN" in out
    assert "ENDIF" in out
    assert '  REVEAL("seven")' in out


def test_fmt_in_place(tmp_path):
    scroll = _write(tmp_path, "messy.god", "begin creation\nreveal(1)\nend creation\n")
    rc = cli.main(["fmt", str(scroll), "--in-place"])
    assert rc == 0
    text = scroll.read_text(encoding="utf-8")
    assert text.startswith("BEGIN CREATION\n")
    assert "  REVEAL(1)\n" in text


def test_ledger_verify_intact(tmp_path, capsys):
    from godcode.ledger import CovenantLedger

    chain = tmp_path / "covenant.chain"
    ledger = CovenantLedger(str(chain))
    ledger.seal({"sealed": "light"})
    rc = cli.main(["ledger", "verify", "--file", str(chain)])
    assert rc == 0
    assert "intact" in capsys.readouterr().out


def test_ledger_verify_tampered(tmp_path, capsys):
    from godcode.ledger import CovenantLedger

    chain = tmp_path / "covenant.chain"
    ledger = CovenantLedger(str(chain))
    ledger.seal({"sealed": "light"})
    lines = chain.read_text(encoding="utf-8").splitlines()
    lines[-1] = lines[-1].replace("light", "darkness")
    chain.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        cli.main(["ledger", "verify", "--file", str(chain)])
    assert exc.value.code == 1
    assert "broken" in capsys.readouterr().out


def test_repl_quit(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: ":quit")
    rc = cli.main(["repl"])
    assert rc == 0
    assert "God Code Live Mode" in capsys.readouterr().out
