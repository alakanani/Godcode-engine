"""Tests for the God Code linter (godcode/linter.py + `godcode lint`).

Conventions:
  * Plugins are disabled (GODCODE_NO_PLUGINS=1) so builtin names are stable.
  * Every sample runs through the real Lexer/Parser via lint_source.
  * CLI tests call cli.main directly, the way test_cli.py does.
"""

import json
import os

os.environ["GODCODE_NO_PLUGINS"] = "1"

import pytest

from godcode import cli
from godcode.linter import Finding, lint_source


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _rules(findings):
    return [(f.rule, f.line, f.col) for f in findings]


def _has(findings, rule, line, name=None):
    for f in findings:
        if f.rule == rule and f.line == line:
            if name is None or f"'{name}'" in f.message:
                return True
    return False


# ---------------------------------------------------------------------------
# GC001: unused variable
# ---------------------------------------------------------------------------

GC001_SCROLL = """\
BEGIN CREATION
  DECLARE x AS 1
  DECLARE y AS 2
  REVEAL(y)
END CREATION
"""


def test_gc001_unused_variable():
    findings = lint_source(GC001_SCROLL)
    assert _has(findings, "GC001", 2, "x")
    assert not _has(findings, "GC001", 3, "y")


def test_gc001_nested_rite_body_counts_as_used():
    scroll = """\
BEGIN CREATION
  DECLARE x AS 1
  DEFINE RITE f()
    REVEAL(x)
  END RITE
  INVOKE f()
END CREATION
"""
    findings = lint_source(scroll)
    assert not any(f.rule == "GC001" for f in findings)


def test_gc001_loop_variable_used_in_body():
    scroll = """\
BEGIN CREATION
  FOR i IN [1, 2]
    REVEAL(i)
  ENDFOR
END CREATION
"""
    findings = lint_source(scroll)
    assert not any(f.rule == "GC001" for f in findings)


def test_gc001_unused_loop_variable():
    scroll = """\
BEGIN CREATION
  FOR i IN [1, 2]
    REVEAL("walking")
  ENDFOR
END CREATION
"""
    findings = lint_source(scroll)
    assert _has(findings, "GC001", 2, "i")


# ---------------------------------------------------------------------------
# GC002: undefined name
# ---------------------------------------------------------------------------

GC002_SCROLL = """\
BEGIN CREATION
  REVEAL(mystery)
END CREATION
"""


def test_gc002_undefined_name():
    findings = lint_source(GC002_SCROLL)
    assert _has(findings, "GC002", 2, "mystery")


def test_gc002_builtin_names_are_known():
    scroll = """\
BEGIN CREATION
  DECLARE words AS ["a", "b"]
  REVEAL(LEN(words))
  REVEAL(UPPER("shout"))
END CREATION
"""
    findings = lint_source(scroll)
    assert not any(f.rule == "GC002" for f in findings)


def test_gc002_undefined_rite_call():
    scroll = """\
BEGIN CREATION
  INVOKE no_such_rite()
END CREATION
"""
    findings = lint_source(scroll)
    assert _has(findings, "GC002", 2, "no_such_rite")


def test_gc002_imported_names_are_known(tmp_path):
    _write(tmp_path, "lib.god", """\
DEFINE RITE helper()
  REVEAL("hi")
END RITE
DECLARE shared AS 42
""")
    main = _write(tmp_path, "main.god", """\
BEGIN CREATION
  IMPORT "lib.god"
  INVOKE helper()
  REVEAL(shared)
END CREATION
""")
    findings = lint_source(open(main, encoding="utf-8").read(),
                           source_name=main)
    assert not any(f.rule == "GC002" for f in findings)


def test_gc002_unresolvable_import_suppresses_gc002(tmp_path):
    main = _write(tmp_path, "main.god", """\
BEGIN CREATION
  IMPORT "nope.god"
  REVEAL(mystery)
END CREATION
""")
    findings = lint_source(open(main, encoding="utf-8").read(),
                           source_name=main)
    assert not any(f.rule == "GC002" for f in findings)


# ---------------------------------------------------------------------------
# GC003: shadowing
# ---------------------------------------------------------------------------

GC003_SCROLL = """\
BEGIN CREATION
  DECLARE x AS 1
  DEFINE RITE f(x)
    REVEAL(x)
  END RITE
  INVOKE f(2)
  REVEAL(x)
END CREATION
"""


def test_gc003_rite_param_shadows_outer():
    findings = lint_source(GC003_SCROLL)
    assert _has(findings, "GC003", 3, "x")
    # the outer x is still referenced on the last line, so no GC001 for it
    assert not _has(findings, "GC001", 2, "x")


def test_gc003_loop_variable_shadows_outer():
    scroll = """\
BEGIN CREATION
  DECLARE i AS 0
  FOR i IN [1, 2]
    REVEAL(i)
  ENDFOR
  REVEAL(i)
END CREATION
"""
    findings = lint_source(scroll)
    assert _has(findings, "GC003", 3, "i")


def test_gc003_declare_shadows_outer():
    scroll = """\
BEGIN CREATION
  DECLARE x AS 1
  DEFINE RITE f()
    DECLARE x AS 2
    REVEAL(x)
  END RITE
  INVOKE f()
  REVEAL(x)
END CREATION
"""
    findings = lint_source(scroll)
    assert _has(findings, "GC003", 4, "x")


# ---------------------------------------------------------------------------
# GC004: empty block
# ---------------------------------------------------------------------------

GC004_SCROLL = """\
BEGIN CREATION
  IF true THEN
  ENDIF
  FOR i IN [1]
  ENDFOR
  WHILE false DO
  ENDWHILE
  DEFINE RITE empty()
  END RITE
END CREATION
"""


def test_gc004_empty_blocks():
    findings = lint_source(GC004_SCROLL)
    gc004_lines = sorted(f.line for f in findings if f.rule == "GC004")
    assert gc004_lines == [2, 4, 6, 8]


def test_gc004_empty_else_body():
    scroll = """\
BEGIN CREATION
  IF true THEN
    REVEAL("yes")
  ELSE
  ENDIF
END CREATION
"""
    findings = lint_source(scroll)
    assert _has(findings, "GC004", 2)


def test_gc004_no_else_is_not_an_empty_else():
    scroll = """\
BEGIN CREATION
  IF true THEN
    REVEAL("yes")
  ENDIF
END CREATION
"""
    findings = lint_source(scroll)
    assert not any(f.rule == "GC004" for f in findings)


# ---------------------------------------------------------------------------
# GC005: unreachable code
# ---------------------------------------------------------------------------

GC005_SCROLL = """\
BEGIN CREATION
  DEFINE RITE f()
    RETURN 1
    REVEAL("never")
  END RITE
  INVOKE f()
END CREATION
"""


def test_gc005_unreachable_after_return():
    findings = lint_source(GC005_SCROLL)
    assert _has(findings, "GC005", 4)


def test_gc005_return_inside_if_does_not_taint_outer_block():
    scroll = """\
BEGIN CREATION
  DEFINE RITE f(x)
    IF x THEN
      RETURN 1
    ENDIF
    REVEAL("still here")
  END RITE
  INVOKE f(true)
END CREATION
"""
    findings = lint_source(scroll)
    assert not any(f.rule == "GC005" for f in findings)


# ---------------------------------------------------------------------------
# GC006: re-DECLARE
# ---------------------------------------------------------------------------

GC006_SCROLL = """\
BEGIN CREATION
  DECLARE x AS 1
  DECLARE x AS 2
  REVEAL(x)
END CREATION
"""


def test_gc006_redeclare_same_scope():
    findings = lint_source(GC006_SCROLL)
    assert _has(findings, "GC006", 3, "x")


def test_gc006_separate_scopes_are_fine():
    scroll = """\
BEGIN CREATION
  FOR i IN [1]
    DECLARE x AS i
    REVEAL(x)
  ENDFOR
  FOR j IN [2]
    DECLARE x AS j
    REVEAL(x)
  ENDFOR
END CREATION
"""
    findings = lint_source(scroll)
    assert not any(f.rule == "GC006" for f in findings)


# ---------------------------------------------------------------------------
# clean scroll: no findings
# ---------------------------------------------------------------------------

CLEAN_SCROLL = """\
BEGIN CREATION
  DECLARE name AS "world"
  DEFINE RITE greet(who)
    REVEAL("hello {who}")
  END RITE
  INVOKE greet(name)
END CREATION
"""


def test_clean_scroll_has_no_findings():
    assert lint_source(CLEAN_SCROLL) == []


def test_finding_record_shape():
    findings = lint_source(GC001_SCROLL)
    assert findings
    f = findings[0]
    assert isinstance(f, Finding)
    assert (f.line, f.col, f.rule) == (2, 3, "GC001")
    assert f.message == "unused variable 'x'"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_lint_help_mentions_lint(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "lint" in capsys.readouterr().out


def test_lint_cli_text_output(tmp_path, capsys):
    scroll = _write(tmp_path, "t.god", GC001_SCROLL)
    with pytest.raises(SystemExit) as exc:
        cli.main(["lint", scroll])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "line 2, col 3 [GC001] unused variable 'x'" in out


def test_lint_cli_clean_exit_zero(tmp_path, capsys):
    scroll = _write(tmp_path, "clean.god", CLEAN_SCROLL)
    rc = cli.main(["lint", scroll])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_lint_cli_json(tmp_path, capsys):
    scroll = _write(tmp_path, "t.god", GC001_SCROLL)
    with pytest.raises(SystemExit) as exc:
        cli.main(["lint", "--json", scroll])
    assert exc.value.code == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["tool"] == "godcode"
    assert doc["command"] == "lint"
    assert doc["file"] == scroll
    assert doc["ok"] is False
    assert doc["findings"] == [
        {"line": 2, "col": 3, "rule": "GC001",
         "message": "unused variable 'x'"}
    ]


def test_lint_cli_json_clean(tmp_path, capsys):
    scroll = _write(tmp_path, "clean.god", CLEAN_SCROLL)
    rc = cli.main(["lint", "--json", scroll])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["ok"] is True
    assert doc["findings"] == []


def test_lint_cli_missing_file(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["lint", "no_such_scroll.god"])
    assert exc.value.code == 1
    assert "no_such_scroll.god" in capsys.readouterr().err


def test_lint_cli_parse_error(tmp_path, capsys):
    scroll = _write(tmp_path, "bad.god", "BEGIN CREATION\n  DECLARE\n")
    with pytest.raises(SystemExit) as exc:
        cli.main(["lint", scroll])
    assert exc.value.code == 1
    assert capsys.readouterr().err != ""
