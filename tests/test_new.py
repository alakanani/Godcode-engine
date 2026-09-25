"""Tests for `godcode new` — the project scaffold (godcode/scaffold.py).

Conventions:
  * Plugins are disabled (GODCODE_NO_PLUGINS=1) so runs are deterministic.
  * The scaffolded project is exercised through the real CLI, the way a
    newcomer would meet it: `new`, then `run`, `check`, `lint`, `fmt`,
    and `test` on the raised files.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ["GODCODE_NO_PLUGINS"] = "1"

import pytest

from godcode.scaffold import ScaffoldError, create_project, validate_name

REPO = Path(__file__).resolve().parents[1]


def _run_cli(*argv, cwd=None):
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


# ---------------------------------------------------------------------------
# name validation
# ---------------------------------------------------------------------------

def test_validate_name_accepts_good_names():
    assert validate_name("greeting") == "greeting"
    assert validate_name("my-scroll") == "my-scroll"
    assert validate_name("scroll2") == "scroll2"


def test_validate_name_cleans_whitespace_and_case():
    assert validate_name("  Greeting ") == "greeting"


@pytest.mark.parametrize("bad", ["", "Bad Name", "9lives", "-lead",
                                 "under_score", "way-too-" + "long-" * 20])
def test_validate_name_refuses_bad_names(bad):
    with pytest.raises(ScaffoldError):
        validate_name(bad)


# ---------------------------------------------------------------------------
# create_project
# ---------------------------------------------------------------------------

def test_create_project_writes_four_files(tmp_path):
    result = create_project("greeting", dest=tmp_path, author="Ada")
    assert result.name == "greeting"
    assert result.directory == tmp_path / "greeting"
    assert sorted(result.files) == [
        "README.md", "main.god", "scroll.toml", "test_main.god"]
    for filename in result.files:
        assert (result.directory / filename).is_file()


def test_create_project_refuses_occupied_ground(tmp_path):
    (tmp_path / "greeting").mkdir()
    with pytest.raises(ScaffoldError):
        create_project("greeting", dest=tmp_path)


def test_scaffold_manifest_is_publishable(tmp_path):
    from godcode.registry import ScrollRegistry

    result = create_project("greeting", dest=tmp_path)
    registry = ScrollRegistry(registry_root=tmp_path / "registry")
    manifest = registry.publish(result.directory)
    assert manifest["name"] == "greeting"
    assert manifest["entry"] == "main.god"


# ---------------------------------------------------------------------------
# the raised project must be a healthy, runnable creation
# ---------------------------------------------------------------------------

@pytest.fixture()
def raised(tmp_path):
    result = create_project("greeting", dest=tmp_path)
    return result.directory


def test_raised_project_runs_pure(raised):
    proc = _run_cli("check", "main.god", cwd=raised)
    assert proc.returncode == 0, proc.stderr
    proc = _run_cli("run", "main.god", cwd=raised)
    assert proc.returncode == 0, proc.stderr
    assert "Peace be upon this house." in proc.stdout


def test_raised_project_passes_lint_and_fmt(raised):
    proc = _run_cli("lint", "main.god", cwd=raised)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = _run_cli("fmt", "main.god", cwd=raised)
    assert proc.returncode == 0, proc.stderr


def test_raised_project_tests_pass(raised):
    proc = _run_cli("test", ".", cwd=raised)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "2 passed, 0 failed" in proc.stdout


# ---------------------------------------------------------------------------
# the CLI itself
# ---------------------------------------------------------------------------

def test_cli_new_happy_path(tmp_path):
    proc = _run_cli("new", "greeting", "--author", "Ada", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "A new scroll rises" in proc.stdout
    assert (tmp_path / "greeting" / "main.god").is_file()


def test_cli_new_json(tmp_path):
    proc = _run_cli("new", "greeting", "--json", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "new"
    assert payload["name"] == "greeting"
    assert sorted(payload["files"]) == [
        "README.md", "main.god", "scroll.toml", "test_main.god"]


def test_cli_new_refuses_bad_name(tmp_path):
    proc = _run_cli("new", "Bad Name", cwd=tmp_path)
    assert proc.returncode == 1
    assert "fitting scroll name" in proc.stderr


def test_cli_new_refuses_occupied_ground(tmp_path):
    _run_cli("new", "greeting", cwd=tmp_path)
    proc = _run_cli("new", "greeting", cwd=tmp_path)
    assert proc.returncode == 1
    assert "already stands" in proc.stderr


def test_cli_new_json_error_shape(tmp_path):
    proc = _run_cli("new", "Bad Name", "--json", cwd=tmp_path)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "new"
    assert payload["error"]
