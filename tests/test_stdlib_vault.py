"""Tests for the vault stdlib: JSON and filesystem builtins (godcode.stdlib_vault).

Every test runs real God Code source through the real pipeline
(Lexer -> Parser -> Interpreter) and asserts on revealed output, in the
style of tests/test_scrolls.py. Filesystem tests stay inside tmp_path.
"""

import pytest

from godcode.errors import GodRuntimeError, SandboxViolation
from godcode.interpreter import Interpreter
from godcode.lexer import Lexer
from godcode.parser import Parser
from godcode.sandbox import SandboxPolicy, apply_policy
from godcode import stdlib_vault


def fresh_interpreter():
    """An Interpreter with the vault builtins registered."""
    interp = Interpreter()
    stdlib_vault.register(interp)
    return interp


def run(src, interp=None):
    """Parse src, run it, return the revealed lines."""
    prog = Parser(Lexer(src).lex()).parse()
    interp = interp if interp is not None else fresh_interpreter()
    interp.run(prog)
    return interp.output


def god_word(raw):
    """Quote raw text as a God Code word literal.

    Braces are doubled so they survive string interpolation, and the
    holy escapes are honored, so JSON text can be embedded in sources.
    """
    return (
        '"'
        + raw.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("{", "{{")
        .replace("}", "}}")
        + '"'
    )


# ------------------------------------------------------------------- JSON


def test_json_round_trip():
    src = f"REVEAL(JSON_STRING(JSON_PARSE({god_word('{"a": 1, "b": [1, 2]}')})))"
    assert run(src) == ['{"a":1,"b":[1,2]}']


def test_json_nested_maps_and_lists():
    raw = (
        '{"users": [{"name": "Amina", "tags": ["grace", "peace"]}],'
        ' "n": 3, "ok": true, "nothing": null}'
    )
    src = (
        f"DECLARE d AS JSON_PARSE({god_word(raw)})\n"
        "REVEAL(TYPE(d))\n"
        'REVEAL(d["users"][0]["name"])\n'
        'REVEAL(d["users"][0]["tags"][1])\n'
        'REVEAL(d["n"])\n'
        'REVEAL(d["ok"])\n'
        'REVEAL(TYPE(d["nothing"]))\n'
    )
    assert run(src) == ["map", "Amina", "peace", "3", "true", "void"]


def test_map_indexing_on_parsed_json():
    src = (
        f"DECLARE d AS JSON_PARSE({god_word('{"name": "Bakang"}')})\n"
        'REVEAL(d["name"])\n'
    )
    assert run(src) == ["Bakang"]


def test_json_parse_top_level_values():
    assert run(f"REVEAL(JSON_PARSE({god_word('[1, 2]')}))") == ["[1, 2]"]
    assert run(f"REVEAL(JSON_PARSE({god_word('42')}))") == ["42"]
    assert run(f"REVEAL(JSON_PARSE({god_word('true')}))") == ["true"]
    assert run(f"REVEAL(JSON_PARSE({god_word('null')}))") == ["void"]


def test_json_string_compact_shapes():
    assert run('REVEAL(JSON_STRING([1, "two", true]))') == ['[1,"two",true]']
    assert run('REVEAL(JSON_STRING("hi"))') == ['"hi"']
    assert run("REVEAL(JSON_STRING(2.5))") == ["2.5"]


def test_json_parse_invalid_raises():
    with pytest.raises(GodRuntimeError) as excinfo:
        run(f"REVEAL(JSON_PARSE({god_word('{oops')}))")
    message = str(excinfo.value)
    assert "JSON_PARSE could not read that word as JSON" in message
    assert "\u2014" not in message  # plain words, no em dashes


def test_json_parse_needs_a_word():
    with pytest.raises(GodRuntimeError) as excinfo:
        run("REVEAL(JSON_PARSE(42))")
    assert "JSON_PARSE needs a word" in str(excinfo.value)


def test_json_string_rejects_rite():
    src = "DEFINE RITE r()\nEND RITE\nREVEAL(JSON_STRING(r))"
    with pytest.raises(GodRuntimeError) as excinfo:
        run(src)
    assert "cannot carry a rite" in str(excinfo.value)


def test_json_string_rejects_symbol():
    with pytest.raises(GodRuntimeError) as excinfo:
        run("REVEAL(JSON_STRING(some_unbound_name))")
    assert "cannot carry a symbol" in str(excinfo.value)


def test_json_string_rejects_contract():
    with pytest.raises(GodRuntimeError) as excinfo:
        run('REVEAL(JSON_STRING(contract("noah")))')
    assert "cannot carry a contract" in str(excinfo.value)


def test_json_string_arity():
    with pytest.raises(GodRuntimeError):
        run('REVEAL(JSON_STRING("a", "b"))')


# -------------------------------------------------------------- filesystem


def test_file_write_read_round_trip(tmp_path):
    path = (tmp_path / "psalm.txt").as_posix()
    src = (
        f'DECLARE n AS WRITE_FILE("{path}", "grace upon grace")\n'
        "REVEAL(n)\n"
        f'REVEAL(READ_FILE("{path}"))\n'
    )
    assert run(src) == ["16", "grace upon grace"]


def test_file_exists_true_and_false(tmp_path):
    present = (tmp_path / "here.txt").as_posix()
    missing = (tmp_path / "gone.txt").as_posix()
    (tmp_path / "here.txt").write_text("x", encoding="utf-8")
    src = f'REVEAL(FILE_EXISTS("{present}"))\nREVEAL(FILE_EXISTS("{missing}"))\n'
    assert run(src) == ["true", "false"]


def test_list_dir_sorted(tmp_path):
    for name in ("b.txt", "c.txt", "a.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    src = f'REVEAL(LIST_DIR("{tmp_path.as_posix()}"))\n'
    assert run(src) == ["[a.txt, b.txt, c.txt]"]


def test_read_file_missing_raises(tmp_path):
    path = (tmp_path / "missing.txt").as_posix()
    with pytest.raises(GodRuntimeError) as excinfo:
        run(f'REVEAL(READ_FILE("{path}"))')
    assert "READ_FILE could not read" in str(excinfo.value)


def test_list_dir_on_file_raises(tmp_path):
    path = (tmp_path / "plain.txt").as_posix()
    (tmp_path / "plain.txt").write_text("x", encoding="utf-8")
    with pytest.raises(GodRuntimeError) as excinfo:
        run(f'REVEAL(LIST_DIR("{path}"))')
    assert "LIST_DIR needs a directory" in str(excinfo.value)


def test_write_file_arity():
    with pytest.raises(GodRuntimeError):
        run('REVEAL(WRITE_FILE("only-one"))')


# ----------------------------------------------------------------- sandbox


def sandboxed(policy):
    interp = fresh_interpreter()
    apply_policy(interp, policy)
    return interp


def test_sandbox_refuses_write_file(tmp_path):
    interp = sandboxed(SandboxPolicy.strict())
    path = (tmp_path / "nope.txt").as_posix()
    with pytest.raises(SandboxViolation):
        interp.run_source(f'REVEAL(WRITE_FILE("{path}", "no"))')
    assert not (tmp_path / "nope.txt").exists()


def test_sandbox_refuses_read_file(tmp_path):
    interp = sandboxed(SandboxPolicy.strict())
    target = tmp_path / "secret.txt"
    target.write_text("hidden", encoding="utf-8")
    with pytest.raises(SandboxViolation):
        interp.run_source(f'REVEAL(READ_FILE("{target.as_posix()}"))')


def test_sandbox_refuses_list_dir(tmp_path):
    interp = sandboxed(SandboxPolicy.strict())
    with pytest.raises(SandboxViolation):
        interp.run_source(f'REVEAL(LIST_DIR("{tmp_path.as_posix()}"))')


def test_sandbox_scoped_read_grant(tmp_path):
    inner = tmp_path / "inner.txt"
    inner.write_text("manna", encoding="utf-8")
    interp = sandboxed(SandboxPolicy(allow_read_paths=(tmp_path.as_posix(),)))
    interp.run_source(f'REVEAL(READ_FILE("{inner.as_posix()}"))')
    assert interp.output == ["manna"]
    # Outside the granted directory, the read is still withheld.
    outside = tmp_path.parent / "outside_probe_godcode.txt"
    outside.write_text("x", encoding="utf-8")
    try:
        with pytest.raises(SandboxViolation):
            interp.run_source(f'REVEAL(READ_FILE("{outside.as_posix()}"))')
    finally:
        outside.unlink(missing_ok=True)


def test_sandbox_write_grant_allows_write(tmp_path):
    interp = sandboxed(SandboxPolicy(allow_write=True))
    path = (tmp_path / "allowed.txt").as_posix()
    interp.run_source(f'REVEAL(WRITE_FILE("{path}", "yes"))')
    assert interp.output == ["3"]
    assert (tmp_path / "allowed.txt").read_text(encoding="utf-8") == "yes"


def test_json_needs_no_grant_under_sandbox():
    interp = sandboxed(SandboxPolicy.strict())
    src = f"REVEAL(JSON_STRING(JSON_PARSE({god_word('{"a": [1]}')})))"
    interp.run_source(src)
    assert interp.output == ['{"a":[1]}']
