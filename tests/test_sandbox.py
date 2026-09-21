"""Tests for the God Code v3.0 sandbox (godcode/sandbox.py, Pillar 1).

Policy unit tests plus end-to-end sandboxed runs. Everything stays
inside tmp_path fixtures; the sandbox is never allowed to touch the
real filesystem outside them.
"""

import os

import pytest

from godcode import cli
from godcode.errors import GodCodeError, SandboxViolation
from godcode.interpreter import Interpreter
from godcode.sandbox import (
    Sandbox,
    SandboxPolicy,
    apply_policy,
    run_sandboxed,
)


PURE = """\
BEGIN CREATION
  DECLARE answer AS 40 + 2
  REVEAL(answer)
END CREATION
"""

ASK_SCROLL = """\
BEGIN CREATION
  DECLARE name AS ASK("Who goes there? ")
  REVEAL(name)
END CREATION
"""

LOOP_FOREVER = """\
DECLARE x AS 0
WHILE x < 99999999 DO
  DECLARE x AS x + 1
ENDWHILE
"""

RECURSE = """\
DEFINE RITE deep(n)
  INVOKE deep(n + 1)
END RITE
INVOKE deep(0)
"""


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------ policy


class TestPolicy:
    def test_defaults_deny_everything(self):
        policy = SandboxPolicy()
        assert policy.allow_read_paths is None
        assert policy.allow_write is False
        assert policy.allow_network is False
        assert policy.allow_subprocess is False
        assert policy.allow_stdin is False
        assert policy.allowed_import_paths == ()

    def test_strict_allows_stdlib_scrolls(self):
        policy = SandboxPolicy.strict()
        scrolls = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "..", "godcode", "scrolls")
        )
        assert scrolls in [os.path.realpath(p)
                           for p in policy.allowed_import_paths]
        # ...but still denies the dangerous powers
        assert policy.allow_write is False
        assert policy.allow_network is False
        assert policy.allow_subprocess is False
        assert policy.allow_stdin is False

    def test_strict_adds_source_dir_and_timeout(self):
        policy = SandboxPolicy.strict(source_dir="/tmp/creation",
                                      timeout_seconds=2.5)
        assert "/tmp/creation" in policy.allowed_import_paths
        assert policy.timeout_seconds == 2.5

    def test_defaults_time_and_step_budgets(self):
        policy = SandboxPolicy()
        assert policy.timeout_seconds == 5.0
        assert policy.max_steps == 100_000


# ------------------------------------------------------------ end-to-end


class TestRunSandboxed:
    def test_pure_program_succeeds(self):
        assert run_sandboxed(PURE) == ["42"]

    def test_matches_unsandboxed_output(self):
        interp = Interpreter(log_path=None)
        interp.run_source(PURE)
        assert run_sandboxed(PURE) == list(interp.output)

    def test_stdlib_scroll_import_allowed_under_strict(self):
        source = 'IMPORT "math"\nREVEAL(POW(2, 10))\n'
        assert run_sandboxed(source) == ["1024"]

    def test_explicit_import_dir_allows_scroll(self, tmp_path):
        _write(tmp_path, "helper.god",
               "DEFINE RITE BLESSING()\nRETURN 7\nEND RITE\n")
        policy = SandboxPolicy(allowed_import_paths=(str(tmp_path),))
        main = _write(tmp_path, "main.god",
                      'IMPORT "helper"\nREVEAL(BLESSING())\n')
        assert run_sandboxed(main.read_text(encoding="utf-8"), policy,
                             source_name=str(main)) == ["7"]

    def test_import_outside_approved_paths_denied(self, tmp_path):
        _write(tmp_path, "helper.god", "REVEAL(1)\n")
        main = _write(tmp_path, "main.god", 'IMPORT "helper"\n')
        policy = SandboxPolicy()  # no import paths approved
        with pytest.raises(SandboxViolation) as exc:
            run_sandboxed(main.read_text(encoding="utf-8"), policy,
                          source_name=str(main))
        assert exc.value.line == 1
        assert "line 1" in str(exc.value)

    def test_import_traversal_denied_even_with_source_dir(self, tmp_path):
        outer = tmp_path / "outer"
        outer.mkdir()
        _write(outer, "secret.god", "REVEAL(1)\n")
        inner = tmp_path / "inner"
        inner.mkdir()
        main = _write(inner, "main.god", 'IMPORT "../outer/secret"\n')
        policy = SandboxPolicy.strict(source_dir=str(inner))
        with pytest.raises(SandboxViolation) as exc:
            run_sandboxed(main.read_text(encoding="utf-8"), policy,
                          source_name=str(main))
        assert exc.value.line == 1
        assert "outside the consecrated paths" in str(exc.value)

    def test_ask_denied_by_default(self):
        with pytest.raises(SandboxViolation) as exc:
            run_sandboxed(ASK_SCROLL)
        assert exc.value.line == 2
        assert "line 2" in str(exc.value)
        assert "ASK" in str(exc.value)

    def test_ask_allowed_when_granted(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt="": "Moses")
        policy = SandboxPolicy(allow_stdin=True)
        assert run_sandboxed(ASK_SCROLL, policy) == ["Moses"]

    def test_infinite_loop_exceeds_step_budget(self):
        policy = SandboxPolicy(max_steps=500)
        with pytest.raises(SandboxViolation) as exc:
            run_sandboxed(LOOP_FOREVER, policy)
        assert "step" in str(exc.value).lower()
        assert exc.value.line is not None
        assert f"line {exc.value.line}" in str(exc.value)

    def test_long_run_exceeds_time_grant(self):
        policy = SandboxPolicy(timeout_seconds=0.05, max_steps=10 ** 9)
        with pytest.raises(SandboxViolation) as exc:
            run_sandboxed(LOOP_FOREVER, policy)
        assert "time" in str(exc.value).lower()
        assert exc.value.line is not None

    def test_unbounded_recursion_is_a_divine_error(self):
        with pytest.raises(SandboxViolation) as exc:
            run_sandboxed(RECURSE)
        assert exc.value.line is not None

    def test_violation_is_a_god_code_error(self):
        with pytest.raises(GodCodeError):
            run_sandboxed(ASK_SCROLL)

    def test_sandbox_writes_no_log_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        run_sandboxed(PURE)
        assert list(tmp_path.iterdir()) == []

    def test_sandbox_disables_plugin_autoload(self, monkeypatch):
        import godcode.plugins as plugins

        calls = []
        monkeypatch.setattr(
            plugins, "load_plugins",
            lambda interpreter, dirs=None: calls.append(1) or [],
        )
        run_sandboxed(PURE)
        assert calls == []


# ------------------------------------------------------------ apply_policy


class TestApplyPolicy:
    def test_install_and_uninstall(self):
        interp = Interpreter(log_path=None)
        original = interp._exec_stmt
        guard = apply_policy(interp, SandboxPolicy())
        assert isinstance(guard, Sandbox)
        assert guard._originals["_exec_stmt"] == original
        assert interp._exec_stmt.__name__ == "exec_stmt"  # the wrapper
        guard.uninstall()
        assert interp._exec_stmt == original

    def test_guard_counts_steps(self):
        interp = Interpreter(log_path=None)
        guard = apply_policy(interp, SandboxPolicy())
        interp.run_source(PURE)
        assert guard.steps > 0
        guard.uninstall()

    def test_uninstalled_interpreter_runs_free(self):
        interp = Interpreter(log_path=None)
        guard = apply_policy(interp, SandboxPolicy(max_steps=1))
        guard.uninstall()
        interp.run_source(PURE)  # would have blown a 1-step budget
        assert interp.output == ["42"]


# --------------------------------------------------------------------- CLI


class TestSandboxCLI:
    def test_run_sandbox_success(self, tmp_path, capsys):
        scroll = _write(tmp_path, "pure.god", PURE)
        rc = cli.main(["run", "--sandbox", str(scroll)])
        assert rc == 0
        assert "42" in capsys.readouterr().out

    def test_run_sandbox_denied_rite_fails(self, tmp_path, capsys):
        scroll = _write(tmp_path, "asking.god", ASK_SCROLL)
        with pytest.raises(SystemExit) as exc:
            cli.main(["run", "--sandbox", str(scroll)])
        assert exc.value.code == 1
        assert "sandbox" in capsys.readouterr().err.lower()

    def test_run_sandbox_timeout_flag(self, tmp_path, capsys):
        scroll = _write(tmp_path, "pure.god", PURE)
        rc = cli.main(["run", "--sandbox", "--sandbox-timeout", "10",
                       str(scroll)])
        assert rc == 0
        assert "42" in capsys.readouterr().out

    def test_run_sandbox_import_limited_to_scroll_dir(self, tmp_path):
        _write(tmp_path, "helper.god", "REVEAL(1)\n")
        scroll = _write(tmp_path, "main.god", 'IMPORT "helper"\n')
        rc = cli.main(["run", "--sandbox", str(scroll)])
        assert rc == 0

    def test_run_sandbox_stdlib_example(self, capsys):
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        example = os.path.join(repo, "examples", "sandbox_safe.god")
        rc = cli.main(["run", "--sandbox", example])
        assert rc == 0
        assert "fibonacci" in capsys.readouterr().out
