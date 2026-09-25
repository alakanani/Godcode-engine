"""Smoke test for the benchmark suite (bench/bench.py).

Runs the suite in --quick mode and checks that it exits 0 and prints a
parseable results table with one row per benchmark. The full benchmark
is too slow for routine runs, so only --quick is exercised here.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_BENCHMARKS = [
    "lex_parse",
    "fib_recursion",
    "while_loop",
    "string_interp",
    "list_ops",
    "json_stdlib",
    "anchor_chain",
]

HEADER = "benchmark | median_ms | min_ms | max_ms | runs | detail"


def test_bench_quick_produces_parseable_table():
    proc = subprocess.run(
        [sys.executable, "bench/bench.py", "--quick"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        "bench/bench.py --quick failed with exit "
        f"{proc.returncode}:\n{proc.stderr}"
    )
    lines = proc.stdout.splitlines()
    assert HEADER in lines, (
        "results table header missing from bench output:\n" + proc.stdout
    )
    rows = {}
    for line in lines:
        if "|" not in line or line == HEADER:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 6 and parts[0]:
            rows[parts[0]] = parts
    for name in EXPECTED_BENCHMARKS:
        assert name in rows, f"missing results row for benchmark {name!r}"
        median, minimum, maximum = (float(rows[name][i]) for i in (1, 2, 3))
        assert median > 0, f"non-positive median for {name!r}"
        assert minimum <= median <= maximum, (
            f"median out of [min, max] for {name!r}"
        )
        assert int(rows[name][4]) >= 1


def test_bench_only_flag_runs_single_benchmark():
    proc = subprocess.run(
        [sys.executable, "bench/bench.py", "--quick", "--only", "while_loop"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"bench --only failed:\n{proc.stderr}"
    assert "while_loop |" in proc.stdout
    assert "fib_recursion |" not in proc.stdout
