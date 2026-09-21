"""Pillar 3 — plugins, SUMMON FFI, and the embedding API."""

import os
import textwrap
from pathlib import Path

import pytest

from godcode import plugins, run_file, run_source
from godcode.errors import GodCodeError, GodRuntimeError
from godcode.interpreter import Interpreter
from godcode.values import Symbol

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_plugin(plugdir: Path, name: str, body: str) -> Path:
    plugdir.mkdir(parents=True, exist_ok=True)
    path = plugdir / f"{name}.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _hermetic_interpreter(monkeypatch) -> Interpreter:
    """An interpreter with auto-loading disabled for hermetic plugin tests."""
    monkeypatch.setenv("GODCODE_NO_PLUGINS", "1")
    return Interpreter()


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def test_discover_loads_plugin_from_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GODCODE_NO_PLUGINS", "1")
    plugdir = tmp_path / "plugins"
    _write_plugin(plugdir, "hello", """
        PLUGIN_API_VERSION = 1
        def register(interpreter):
            interpreter.register_plugin_verb("hello.greet", lambda name: f"hello, {name}", plugin="hello")
    """)
    found = plugins.discover_plugins(dirs=[plugdir])
    assert "hello" in found
    assert hasattr(found["hello"], "register")


def test_discover_ignores_missing_dirs_and_non_python(tmp_path, monkeypatch):
    monkeypatch.setenv("GODCODE_NO_PLUGINS", "1")
    plugdir = tmp_path / "plugins"
    plugdir.mkdir()
    (plugdir / "notes.txt").write_text("not a plugin", encoding="utf-8")
    (plugdir / "_private.py").write_text("x = 1", encoding="utf-8")
    assert plugins.discover_plugins(dirs=[plugdir, tmp_path / "nope"]) == {}


def test_broken_plugin_import_does_not_crash_discovery(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GODCODE_NO_PLUGINS", "1")
    plugdir = tmp_path / "plugins"
    _write_plugin(plugdir, "broken", "raise RuntimeError('boom on import')\n")
    _write_plugin(plugdir, "fine", """
        PLUGIN_API_VERSION = 1
        def register(interpreter): pass
    """)
    found = plugins.discover_plugins(dirs=[plugdir])
    assert "broken" not in found
    assert "fine" in found
    assert "boom on import" in capsys.readouterr().err


def test_load_plugins_survives_bad_register_and_api_mismatch(tmp_path, monkeypatch, capsys):
    interp = _hermetic_interpreter(monkeypatch)
    plugdir = tmp_path / "plugins"
    _write_plugin(plugdir, "exploder", """
        PLUGIN_API_VERSION = 1
        def register(interpreter):
            raise RuntimeError('boom in register')
    """)
    _write_plugin(plugdir, "noregister", "PLUGIN_API_VERSION = 1\nVALUE = 1\n")
    _write_plugin(plugdir, "future", """
        PLUGIN_API_VERSION = 999
        def register(interpreter): pass
    """)
    _write_plugin(plugdir, "good", """
        PLUGIN_API_VERSION = 1
        def register(interpreter):
            interpreter.register_plugin_verb("good.ping", lambda: "pong", plugin="good")
    """)
    loaded = plugins.load_plugins(interp, dirs=[plugdir])
    assert loaded == ["good"]
    err = capsys.readouterr().err
    assert "exploder" in err and "noregister" in err and "future" in err
    assert "good.ping" in interp._plugin_verbs


def test_entry_points_are_best_effort():
    # Must never raise, even with no entry points installed.
    assert isinstance(plugins._entry_point_plugins(), dict)


# ---------------------------------------------------------------------------
# auto-loading at interpreter startup
# ---------------------------------------------------------------------------

def test_plugins_autoload_at_startup(tmp_path, monkeypatch):
    monkeypatch.delenv("GODCODE_NO_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    _write_plugin(tmp_path / "plugins", "auto", """
        PLUGIN_API_VERSION = 1
        def register(interpreter):
            interpreter.register_plugin_verb("auto.ping", lambda: "pong", plugin="auto")
    """)
    interp = Interpreter()
    assert "auto" in interp.loaded_plugins
    assert "auto.ping" in interp._plugin_verbs


def test_godcode_no_plugins_disables_autoload(tmp_path, monkeypatch):
    monkeypatch.setenv("GODCODE_NO_PLUGINS", "1")
    monkeypatch.chdir(tmp_path)
    _write_plugin(tmp_path / "plugins", "auto", """
        PLUGIN_API_VERSION = 1
        def register(interpreter):
            interpreter.register_plugin_verb("auto.ping", lambda: "pong", plugin="auto")
    """)
    interp = Interpreter()
    assert interp.loaded_plugins == []
    assert "auto.ping" not in interp._plugin_verbs
    # SUMMON itself is still a core verb.
    with pytest.raises(GodCodeError):
        interp.run_source('REVEAL(SUMMON("auto.ping"))')


# ---------------------------------------------------------------------------
# SUMMON
# ---------------------------------------------------------------------------

def _maths_plugin(tmp_path: Path) -> Path:
    plugdir = tmp_path / "plugins"
    _write_plugin(plugdir, "maths", """
        PLUGIN_API_VERSION = 1
        def _add(a, b): return a + b
        def _first(items): return items[0]
        def _nothing(): return None
        def _kaboom(): raise ValueError('kaboom')
        def register(interpreter):
            interpreter.register_plugin_verb("maths.add", _add, plugin="maths")
            interpreter.register_plugin_verb("maths.first", _first, plugin="maths")
            interpreter.register_plugin_verb("maths.nothing", _nothing, plugin="maths")
            interpreter.register_plugin_verb("maths.kaboom", _kaboom, plugin="maths")
    """)
    return plugdir


def test_summon_calls_plugin_verb(tmp_path, monkeypatch):
    interp = _hermetic_interpreter(monkeypatch)
    plugins.load_plugins(interp, dirs=[_maths_plugin(tmp_path)])
    interp.run_source('REVEAL(SUMMON("maths.add", 20, 22))')
    assert interp.output == ["42"]


def test_summon_converts_lists_and_void(tmp_path, monkeypatch):
    interp = _hermetic_interpreter(monkeypatch)
    plugins.load_plugins(interp, dirs=[_maths_plugin(tmp_path)])
    interp.run_source('REVEAL(SUMMON("maths.first", [7, 8, 9]))\n'
                      'REVEAL(SUMMON("maths.nothing"))')
    assert interp.output == ["7", "void"]


def test_summon_unknown_verb_is_divine_error(tmp_path, monkeypatch):
    interp = _hermetic_interpreter(monkeypatch)
    plugins.load_plugins(interp, dirs=[_maths_plugin(tmp_path)])
    with pytest.raises(GodRuntimeError) as excinfo:
        interp.run_source('REVEAL("before")\nREVEAL(SUMMON("maths.nope"))')
    assert "SUMMON knows no verb 'maths.nope'" in str(excinfo.value)
    assert excinfo.value.line == 2  # line-numbered


def test_summon_needs_a_name(tmp_path, monkeypatch):
    interp = _hermetic_interpreter(monkeypatch)
    with pytest.raises(GodRuntimeError):
        interp.run_source('REVEAL(SUMMON())')
    with pytest.raises(GodRuntimeError):
        interp.run_source('REVEAL(SUMMON(42))')


def test_plugin_exception_becomes_divine_error(tmp_path, monkeypatch):
    interp = _hermetic_interpreter(monkeypatch)
    plugins.load_plugins(interp, dirs=[_maths_plugin(tmp_path)])
    with pytest.raises(GodRuntimeError) as excinfo:
        interp.run_source('REVEAL(SUMMON("maths.kaboom"))')
    assert "maths.kaboom" in str(excinfo.value) and "kaboom" in str(excinfo.value)
    assert excinfo.value.line == 1


def test_plugin_verbs_are_marked_trusted(tmp_path, monkeypatch):
    interp = _hermetic_interpreter(monkeypatch)
    plugins.load_plugins(interp, dirs=[_maths_plugin(tmp_path)])
    info = interp.plugin_verb_info["maths.add"]
    assert info["trusted"] is True
    assert info["plugin"] == "maths"


def test_plugin_verbs_do_not_shadow_core_verbs(tmp_path, monkeypatch):
    # A plugin verb named like a core verb keeps its exact key; LEN still works.
    interp = _hermetic_interpreter(monkeypatch)
    interp.register_plugin_verb("len", lambda s: "shadowed", plugin="sneaky")
    interp.run_source('REVEAL(LEN("abcd"))')
    assert interp.output == ["4"]


# ---------------------------------------------------------------------------
# value conversion
# ---------------------------------------------------------------------------

def test_value_conversion_round_trips():
    assert plugins.to_python(42) == 42
    assert plugins.to_python(2.5) == 2.5
    assert plugins.to_python("amen") == "amen"
    assert plugins.to_python(True) is True
    assert plugins.to_python(None) is None
    assert plugins.to_python([1, "two", None]) == [1, "two", None]
    sym = Symbol("worthy")
    assert plugins.to_python(sym) is sym  # symbols pass through as-is

    assert plugins.to_godcode((1, 2, (3,))) == [1, 2, [3]]  # tuples become lists
    assert plugins.to_godcode([1, (2,)]) == [1, [2]]
    assert plugins.to_godcode(None) is None
    assert plugins.to_godcode("word") == "word"
    opaque = {"a": 1}
    assert plugins.to_godcode(opaque) is opaque  # no God Code counterpart: opaque


# ---------------------------------------------------------------------------
# clockwork (the exemplary plugin)
# ---------------------------------------------------------------------------

def test_clockwork_plugin(monkeypatch):
    interp = _hermetic_interpreter(monkeypatch)
    loaded = plugins.load_plugins(interp, dirs=[REPO_ROOT / "plugins"])
    assert "clockwork" in loaded
    interp.run_source(
        'DECLARE t AS SUMMON("clockwork.now")\n'
        'REVEAL(TYPE(t))\n'
        'REVEAL(SUMMON("clockwork.sleep_ms", 5))\n'
        'SUMMON("clockwork.mark", "psalm")\n'
        'REVEAL(SUMMON("clockwork.elapsed_ms", "psalm") >= 0)'
    )
    assert interp.output[0] == "string"  # ISO timestamp arrives as a string
    assert interp.output[1] == "5"
    assert interp.output[2] == "true"


def test_clockwork_elapsed_of_unknown_mark_is_divine_error(monkeypatch):
    interp = _hermetic_interpreter(monkeypatch)
    plugins.load_plugins(interp, dirs=[REPO_ROOT / "plugins"])
    with pytest.raises(GodRuntimeError) as excinfo:
        interp.run_source('REVEAL(SUMMON("clockwork.elapsed_ms", "never-marked"))')
    assert "never-marked" in str(excinfo.value)


# ---------------------------------------------------------------------------
# embedding API
# ---------------------------------------------------------------------------

def test_run_source_captures_output():
    result = run_source('REVEAL("hello, creation")\nREVEAL(40 + 2)')
    assert result.ok is True
    assert result.error is None
    assert result.output == "hello, creation\n42"


def test_run_source_error_capture_with_partial_output():
    result = run_source('REVEAL("a")\nREVEAL(1 / 0)\nREVEAL("never")')
    assert result.ok is False
    assert result.output == "a"  # output before the failure is kept
    assert "line 2" in result.error


def test_run_source_return_value_from_top_level_return():
    result = run_source('REVEAL("amen")\nRETURN 42')
    assert result.ok is True
    assert result.return_value == 42
    assert result.output == "amen"


def test_run_file(tmp_path):
    scroll = tmp_path / "psalm.god"
    scroll.write_text('REVEAL("from a file")\n', encoding="utf-8")
    result = run_file(scroll)
    assert result.ok is True
    assert result.output == "from a file"


def test_run_file_missing():
    result = run_file("/nonexistent/psalm.god")
    assert result.ok is False
    assert "cannot read" in result.error


def test_run_source_safe_to_call_repeatedly():
    first = run_source('REVEAL("one")')
    second = run_source('REVEAL("two")')
    assert (first.output, second.output) == ("one", "two")
    assert first.ok and second.ok


def test_run_source_respects_no_plugins(tmp_path, monkeypatch):
    monkeypatch.setenv("GODCODE_NO_PLUGINS", "1")
    monkeypatch.chdir(tmp_path)
    _write_plugin(tmp_path / "plugins", "auto", """
        PLUGIN_API_VERSION = 1
        def register(interpreter):
            interpreter.register_plugin_verb("auto.ping", lambda: "pong", plugin="auto")
    """)
    result = run_source('REVEAL(SUMMON("auto.ping"))')
    assert result.ok is False
    assert "knows no verb" in result.error


def test_emit_hook_captures_without_print(capsys):
    interp = Interpreter(log_path=None)
    captured: list[str] = []
    interp.emit = captured.append
    interp.run_source('REVEAL("silent")')
    assert captured == ["silent"]
    assert capsys.readouterr().out == ""  # nothing reached real stdout
    # ...while the default still prints.
    loud = Interpreter(log_path=None)
    loud.run_source('REVEAL("heard")')
    assert "heard" in capsys.readouterr().out
