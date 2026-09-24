"""End-to-end tests for the four real-world example scrolls.

Each test copies the whole examples/ tree into tmp_path (so file writes
stay hermetic), runs the scroll with cwd=tmp_path the way a user would,
and asserts the scroll exits 0 with its expected output.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _run_cli(*argv, cwd):
    """Run `python3 -m godcode ...` as a user would; return CompletedProcess."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "godcode", *argv],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture()
def examples_tree(tmp_path):
    """Copy the whole examples/ tree into tmp_path; return tmp_path."""
    shutil.copytree(REPO / "examples", tmp_path / "examples")
    return tmp_path


def _run_example(cwd, name):
    return _run_cli("run", f"examples/{name}.god", cwd=cwd)


def test_file_reporter(examples_tree):
    proc = _run_example(examples_tree, "file_reporter")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "notes.txt" in out
    assert re.search(r"total\s+files.*\d+", out, re.IGNORECASE)


def test_sales_summary(examples_tree):
    proc = _run_example(examples_tree, "sales_summary")
    assert proc.returncode == 0, proc.stderr
    report = (examples_tree / "examples" / "data" / "sales_report.txt").read_text(
        encoding="utf-8"
    )
    sales = json.loads(
        (examples_tree / "examples" / "data" / "sales.json").read_text(encoding="utf-8")
    )
    # Records carry qty and price; each sale's value is qty * price.
    values = [float(record["qty"]) * float(record["price"]) for record in sales]
    total = sum(values)
    average = total / len(values)
    peak = max(values)
    for value in (total, average, peak):
        candidates = {f"{value}", f"{value:.2f}"}
        assert any(candidate in report for candidate in candidates), (
            f"expected {value!r} in sales_report.txt"
        )


def test_rest_client(examples_tree):
    proc = _run_example(examples_tree, "rest_client")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    live = "@" in out  # a user email from the live API
    offline = "offline" in out.lower() and "peace" in out.lower()
    assert live or offline, (
        "expected either live user lines (an email) or the graceful offline message"
    )


def test_daily_report(examples_tree):
    proc = _run_example(examples_tree, "daily_report")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    today = datetime.date.today()
    human = today.strftime("%B %d, %Y")
    assert str(today) in out or human in out
    assert "tasks done" in out.lower()
