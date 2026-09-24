"""The God Code test runner, behind `godcode test`.

Convention: a *test scroll* is any `.god` file named `test_*.god` or
`*_test.god`. Inside it, every rite named `TEST_*` (case-insensitive) is
one test case. The scroll is parsed once; then each `TEST_*` rite runs in
a FRESH `Interpreter`, so tests cannot leak state into each other. A
`TESTIFY` failure fails that test, and any runtime error fails it too,
with the error message carried in the report.

Discovery reads only the given directory itself; subfolders are not
entered. The runner binds no Spirit, no covenant ledger, and no audit log
(`log_path=None`), and it runs scrolls the same way `godcode run` does
(not sandboxed): only test scrolls you wrote or trust.
"""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path

from godcode.ast import CreationBlock, DefineRite
from godcode.errors import GodCodeError
from godcode.interpreter import Interpreter
from godcode.lexer import Lexer
from godcode.parser import Parser
from godcode.values import RiteFunction

#: Rite label used when the failure belongs to the scroll itself (it could
#: not be read or parsed), not to any single rite.
SCROLL_LEVEL = "(scroll)"


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    """One test's outcome. `ok` is True (passed), False (failed), or None
    (skipped, e.g. the rite asks for offerings)."""

    file: str
    rite: str
    ok: bool | None
    message: str = ""


@dataclass
class TestReport:
    results: list[TestResult] = field(default_factory=list)
    #: Names of test scrolls that held no TEST_ rites at all.
    empty_files: list[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.ok is True)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.ok is False)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.ok is None)

    def text_lines(self) -> list[str]:
        """Human report: one line per test, then the summary line."""
        lines = []
        for r in self.results:
            status = "PASS" if r.ok is True else ("SKIP" if r.ok is None else "FAIL")
            line = f"{status}  {r.file} :: {r.rite}"
            if r.message:
                line += f" :: {r.message}"
            lines.append(line)
        for name in self.empty_files:
            lines.append(f"{name} :: no TEST_ rites found.")
        parts = [f"{self.passed} passed", f"{self.failed} failed"]
        if self.skipped:
            parts.append(f"{self.skipped} skipped")
        lines.append(", ".join(parts) + ".")
        return lines

    def payload(self, dir_label: str) -> dict:
        """Machine report for `godcode test --json`."""
        return {
            "tool": "godcode",
            "command": "test",
            "dir": dir_label,
            "tests": [
                {"file": r.file, "rite": r.rite, "ok": r.ok, "message": r.message}
                for r in self.results
            ],
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
        }


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------
def is_test_file(name: str) -> bool:
    """True for `test_*.god` and `*_test.god` (case-insensitive)."""
    lowered = name.lower()
    return lowered.endswith(".god") and (
        lowered.startswith("test_") or lowered[:-4].endswith("_test")
    )


def discover_test_files(directory: Path) -> list[Path]:
    """Test scrolls in `directory`, sorted by name. Non-recursive: only the
    directory itself is read, subfolders are not entered."""
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and is_test_file(p.name)),
        key=lambda p: p.name,
    )


# ---------------------------------------------------------------------------
# collection
# ---------------------------------------------------------------------------
def _top_level_statements(program) -> list:
    stmts = getattr(program, "statements", None) or []
    if len(stmts) == 1 and isinstance(stmts[0], CreationBlock):
        return stmts[0].statements
    return stmts


def collect_test_rites(program) -> list[DefineRite]:
    """The `TEST_*` rites defined at the scroll's top level, in definition
    order. A repeated name keeps its first position but the last definition
    wins when the rite runs (as `DECLARE` would)."""
    found: dict[str, DefineRite] = {}
    for stmt in _top_level_statements(program):
        if isinstance(stmt, DefineRite) and stmt.name.upper().startswith("TEST_"):
            found[stmt.name] = stmt
    return list(found.values())


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
def _parse_scroll(path: Path):
    source = path.read_text(encoding="utf-8")
    return Parser(Lexer(source).lex()).parse()


def _run_rite(program, rite_node: DefineRite, file_label: str) -> TestResult:
    """Run one TEST_ rite in a fresh interpreter and report the outcome."""
    interp = Interpreter(log_path=None)
    buf = io.StringIO()
    # The runner's own report must stay one line per test: swallow REVEAL
    # lines, [TESTIFY] notices, and any other chatter the scroll makes.
    with contextlib.redirect_stdout(buf):
        try:
            interp.run(program, source_name=file_label)
        except GodCodeError as err:
            return TestResult(file_label, rite_node.name, False,
                              f"the scroll could not be prepared: {err}")
        except Exception as exc:  # an engine fault, not a test failure
            return TestResult(file_label, rite_node.name, False,
                              f"the scroll could not be prepared: "
                              f"{type(exc).__name__}: {exc}")
        target = interp.env.get(rite_node.name) \
            if interp.env.is_bound(rite_node.name) else None
        if not isinstance(target, RiteFunction):
            return TestResult(
                file_label, rite_node.name, False,
                f"the rite {rite_node.name} was not found "
                f"after the scroll ran.")
        if target.params:
            n = len(target.params)
            return TestResult(
                file_label, rite_node.name, None,
                f"the rite asks for {n} offering{'s' if n != 1 else ''}, "
                f"so it was not called.")
        try:
            interp._call_rite(target, [], rite_node.line)
        except GodCodeError as err:
            return TestResult(file_label, rite_node.name, False, str(err))
        except Exception as exc:  # an engine fault, not a test failure
            return TestResult(file_label, rite_node.name, False,
                              f"{type(exc).__name__}: {exc}")
    return TestResult(file_label, rite_node.name, True, "")


def run_test_file(path: Path) -> tuple[list[TestResult], bool]:
    """Parse `path` once, then run each TEST_ rite in isolation.

    Returns (results, is_empty). A scroll that cannot be read or parsed
    yields one file-level failure and never crashes the runner.
    """
    label = path.name
    try:
        program = _parse_scroll(path)
    except GodCodeError as err:
        return [TestResult(label, SCROLL_LEVEL, False, str(err))], False
    except OSError as exc:
        return [TestResult(
            label, SCROLL_LEVEL, False,
            f"the scroll could not be read: {exc.strerror or exc}")], False
    rites = collect_test_rites(program)
    if not rites:
        return [], True
    return [_run_rite(program, rite, label) for rite in rites], False


def run_tests(directory: Path) -> TestReport:
    """Discover test scrolls in `directory` and run them all."""
    report = TestReport()
    for path in discover_test_files(directory):
        results, is_empty = run_test_file(path)
        report.results.extend(results)
        if is_empty:
            report.empty_files.append(path.name)
    return report
