"""Tests for the God Code test runner (godcode/tester.py + `godcode test`).

Conventions:
  * Plugins are disabled (GODCODE_NO_PLUGINS=1) so runs are deterministic.
  * The runner is exercised through the real CLI: each test spawns
    `python3 -m godcode test <dir>` in a subprocess and asserts on the
    exit code and the report, the way a user would meet it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ["GODCODE_NO_PLUGINS"] = "1"

import pytest

from godcode import tester

REPO = Path(__file__).resolve().parents[1]


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _run_cli(*argv, cwd=None):
    """Run `python3 -m godcode ...` as a user would; return CompletedProcess."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "godcode", *argv],
        cwd=str(cwd or REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


PASSING_SCROLL = """\
BEGIN CREATION
  DECLARE base AS 40
  DEFINE RITE TEST_addition()
    TESTIFY base + 2 IS 42
  END RITE
  DEFINE RITE TEST_truth()
    TESTIFY 1 IS 1
  END RITE
END CREATION
"""


def _cli(tmp_path, *argv):
    return _run_cli("test", str(tmp_path), *argv, cwd=tmp_path)


def test_all_pass_exits_zero_and_reports(tmp_path):
    _write(tmp_path, "test_math.god", PASSING_SCROLL)
    proc = _cli(tmp_path)
    assert proc.returncode == 0
    out = proc.stdout
    assert "PASS  test_math.god :: TEST_addition" in out
    assert "PASS  test_math.god :: TEST_truth" in out
    assert "2 passed, 0 failed." in out


def test_testify_failure_fails_with_message(tmp_path):
    _write(tmp_path, "test_broken.god", """\
BEGIN CREATION
  DEFINE RITE TEST_lie()
    TESTIFY 1 IS 2
  END RITE
END CREATION
""")
    proc = _cli(tmp_path)
    assert proc.returncode == 1
    assert "FAIL  test_broken.god :: TEST_lie :: The testimony has failed" in proc.stdout
    assert "0 passed, 1 failed." in proc.stdout


def test_runtime_error_fails_with_message(tmp_path):
    _write(tmp_path, "test_boom.god", """\
BEGIN CREATION
  DEFINE RITE TEST_ghost()
    BREATHE LIFE INTO ghost
  END RITE
END CREATION
""")
    proc = _cli(tmp_path)
    assert proc.returncode == 1
    assert "FAIL  test_boom.god :: TEST_ghost" in proc.stdout
    assert "ghost" in proc.stdout
    assert "0 passed, 1 failed." in proc.stdout


def test_non_test_files_are_ignored(tmp_path):
    # A TEST_ rite in a file that is NOT named test_*.god / *_test.god
    # must never run.
    _write(tmp_path, "helper.god", """\
BEGIN CREATION
  DEFINE RITE TEST_sneaky()
    TESTIFY 1 IS 2
  END RITE
END CREATION
""")
    _write(tmp_path, "notes.txt", "TEST_fake()")
    proc = _cli(tmp_path)
    assert proc.returncode == 0
    assert "0 passed, 0 failed." in proc.stdout
    assert "PASS" not in proc.stdout
    assert "FAIL" not in proc.stdout


def test_star_test_suffix_is_discovered(tmp_path):
    _write(tmp_path, "math_test.god", PASSING_SCROLL)
    proc = _cli(tmp_path)
    assert proc.returncode == 0
    assert "PASS  math_test.god :: TEST_addition" in proc.stdout


def test_subdirectories_are_not_entered(tmp_path):
    sub = tmp_path / "nested"
    sub.mkdir()
    _write(sub, "test_deep.god", """\
BEGIN CREATION
  DEFINE RITE TEST_deep()
    TESTIFY 1 IS 2
  END RITE
END CREATION
""")
    proc = _cli(tmp_path)
    assert proc.returncode == 0
    assert "0 passed, 0 failed." in proc.stdout


def test_file_with_no_test_rites_is_noted_not_failed(tmp_path):
    _write(tmp_path, "test_empty.god", """\
BEGIN CREATION
  DEFINE RITE helper()
    REVEAL("no tests here")
  END RITE
END CREATION
""")
    proc = _cli(tmp_path)
    assert proc.returncode == 0
    assert "test_empty.god :: no TEST_ rites found." in proc.stdout
    assert "0 passed, 0 failed." in proc.stdout


def test_parse_failure_is_a_file_level_failure(tmp_path):
    _write(tmp_path, "test_parse.god", """\
BEGIN CREATION
  DEFINE RITE TEST_oops(
END CREATION
""")
    _write(tmp_path, "test_ok.god", PASSING_SCROLL)
    proc = _cli(tmp_path)
    # The runner must not crash: the good file still runs and the summary
    # still prints, but the broken scroll fails the run.
    assert proc.returncode == 1
    assert "FAIL  test_parse.god :: (scroll) ::" in proc.stdout
    assert "PASS  test_ok.god :: TEST_addition" in proc.stdout
    assert "2 passed, 1 failed." in proc.stdout


def test_parameterized_rite_is_skipped(tmp_path):
    _write(tmp_path, "test_params.god", """\
BEGIN CREATION
  DEFINE RITE TEST_needs_input(x)
    TESTIFY x IS 1
  END RITE
END CREATION
""")
    proc = _cli(tmp_path)
    assert proc.returncode == 0
    assert "SKIP  test_params.god :: TEST_needs_input" in proc.stdout
    assert "asks for 1 offering" in proc.stdout
    assert "0 passed, 0 failed, 1 skipped." in proc.stdout


def test_duplicate_test_names_across_files_are_namespaced(tmp_path):
    # The same TEST_ name in two files must run as two independent tests:
    # one passes, one fails. A shared interpreter would blur them.
    _write(tmp_path, "test_one.god", """\
BEGIN CREATION
  DEFINE RITE TEST_same()
    TESTIFY 1 IS 2
  END RITE
END CREATION
""")
    _write(tmp_path, "test_two.god", """\
BEGIN CREATION
  DEFINE RITE TEST_same()
    TESTIFY 1 IS 1
  END RITE
END CREATION
""")
    proc = _cli(tmp_path)
    assert proc.returncode == 1
    assert "FAIL  test_one.god :: TEST_same" in proc.stdout
    assert "PASS  test_two.god :: TEST_same" in proc.stdout
    assert "1 passed, 1 failed." in proc.stdout


def test_state_does_not_leak_between_files(tmp_path):
    _write(tmp_path, "test_a.god", """\
BEGIN CREATION
  DECLARE shared AS 99
  DEFINE RITE TEST_reads_shared()
    TESTIFY shared IS 99
  END RITE
END CREATION
""")
    _write(tmp_path, "test_b.god", """\
BEGIN CREATION
  DEFINE RITE TEST_checks_shared()
    TESTIFY shared IS 99
  END RITE
END CREATION
""")
    proc = _cli(tmp_path)
    assert proc.returncode == 1
    assert "PASS  test_a.god :: TEST_reads_shared" in proc.stdout
    assert "FAIL  test_b.god :: TEST_checks_shared" in proc.stdout


def test_rite_names_are_case_insensitive(tmp_path):
    _write(tmp_path, "test_case.god", """\
begin creation
  define rite test_lower()
    testify 1 is 1
  end rite
end creation
""")
    proc = _cli(tmp_path)
    assert proc.returncode == 0
    assert "PASS  test_case.god :: test_lower" in proc.stdout
    assert "1 passed, 0 failed." in proc.stdout


def test_json_output_shape(tmp_path):
    _write(tmp_path, "test_math.god", PASSING_SCROLL)
    _write(tmp_path, "test_broken.god", """\
BEGIN CREATION
  DEFINE RITE TEST_lie()
    TESTIFY 1 IS 2
  END RITE
  DEFINE RITE TEST_needs(x, y)
    TESTIFY x IS y
  END RITE
END CREATION
""")
    proc = _cli(tmp_path, "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["tool"] == "godcode"
    assert payload["command"] == "test"
    assert payload["dir"] == str(tmp_path)
    by_rite = {(t["file"], t["rite"]): t for t in payload["tests"]}
    assert by_rite[("test_math.god", "TEST_addition")]["ok"] is True
    assert by_rite[("test_broken.god", "TEST_lie")]["ok"] is False
    assert "The testimony has failed" in by_rite[("test_broken.god", "TEST_lie")]["message"]
    assert by_rite[("test_broken.god", "TEST_needs")]["ok"] is None
    assert payload["passed"] == 2
    assert payload["failed"] == 1
    assert payload["skipped"] == 1


def test_missing_directory_is_a_usage_error(tmp_path):
    proc = _run_cli("test", str(tmp_path / "no_such_dir"), cwd=tmp_path)
    assert proc.returncode == 2
    assert "not a directory" in proc.stderr


def test_dir_defaults_to_current_directory(tmp_path):
    _write(tmp_path, "test_math.god", PASSING_SCROLL)
    proc = _run_cli("test", cwd=tmp_path)
    assert proc.returncode == 0
    assert "2 passed, 0 failed." in proc.stdout


# ---------------------------------------------------------------------------
# unit-level: discovery and naming
# ---------------------------------------------------------------------------
def test_is_test_file_names():
    assert tester.is_test_file("test_math.god")
    assert tester.is_test_file("math_test.god")
    assert tester.is_test_file("TEST_MATH.GOD")
    assert not tester.is_test_file("helper.god")
    assert not tester.is_test_file("test_math.txt")
    assert not tester.is_test_file("contest.god")


def test_discover_is_sorted_and_non_recursive(tmp_path):
    _write(tmp_path, "test_b.god", PASSING_SCROLL)
    _write(tmp_path, "test_a.god", PASSING_SCROLL)
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(sub, "test_deep.god", PASSING_SCROLL)
    found = [p.name for p in tester.discover_test_files(tmp_path)]
    assert found == ["test_a.god", "test_b.god"]


def test_collect_test_rites_dedupes_and_keeps_order(tmp_path):
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    program = Parser(Lexer("""\
BEGIN CREATION
  DEFINE RITE TEST_b()
  END RITE
  DEFINE RITE helper()
  END RITE
  DEFINE RITE TEST_a()
  END RITE
  DEFINE RITE TEST_b()
  END RITE
END CREATION
""").lex()).parse()
    rites = tester.collect_test_rites(program)
    assert [r.name for r in rites] == ["TEST_b", "TEST_a"]
