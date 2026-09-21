"""Tests for the God Code tree-walking interpreter (spec §§5-6).

Tests that need sibling modules (lexer/parser/ast/errors) skip gracefully
when those modules are not yet present; values tests always run.
"""

import pytest

from godcode.values import Contract, RiteFunction, Symbol

try:
    from godcode.environment import Environment
    from godcode.errors import AscendSignal, GodCodeError, GodRuntimeError, ReturnSignal
    from godcode.interpreter import Interpreter

    _SIBLINGS_OK = True
    _SIBLING_ERROR = ""
except ImportError as _exc:  # sibling module not yet built
    _SIBLINGS_OK = False
    _SIBLING_ERROR = str(_exc)

needs_siblings = pytest.mark.skipif(
    not _SIBLINGS_OK, reason=f"blocked on missing sibling module: {_SIBLING_ERROR}"
)


# ------------------------------------------------------------------ values


class TestSymbol:
    def test_is_str_subclass_with_text(self):
        s = Symbol("worthy")
        assert isinstance(s, str)
        assert s == "worthy"
        assert str(s) == "worthy"

    def test_compares_by_text(self):
        assert Symbol("a") == Symbol("a")
        assert Symbol("a") != Symbol("b")
        assert Symbol("a") == "a"


class TestContract:
    def test_defaults(self):
        c = Contract("abraham")
        assert c.name == "abraham"
        assert c.alive is False
        assert c.blessed is False
        assert c.anointed is False

    def test_str(self):
        assert str(Contract("abraham")) == 'contract("abraham")'


class TestRiteFunction:
    def test_fields(self):
        rite = RiteFunction("add", ["a", "b"], [], None)
        assert rite.name == "add"
        assert rite.params == ["a", "b"]
        assert rite.body == []
        assert rite.closure_env is None


# -------------------------------------------------------------- environment


@needs_siblings
class TestEnvironment:
    def test_define_and_get(self):
        env = Environment()
        env.define("x", 42)
        assert env.get("x") == 42

    def test_unbound_returns_symbol(self):
        env = Environment()
        value = env.get("worthy")
        assert isinstance(value, Symbol)
        assert value == "worthy"

    def test_child_shadows_parent(self):
        parent = Environment()
        parent.define("x", "outer")
        child = Environment(parent=parent)
        assert child.get("x") == "outer"
        child.define("x", "inner")
        assert child.get("x") == "inner"
        assert parent.get("x") == "outer"

    def test_deep_walk(self):
        root = Environment()
        root.define("a", 1)
        mid = Environment(parent=root)
        leaf = Environment(parent=mid)
        assert leaf.get("a") == 1

    def test_set_existing_updates_where_bound(self):
        root = Environment()
        root.define("x", 1)
        child = Environment(parent=root)
        child.set_existing("x", 2)
        assert root.get("x") == 2

    def test_set_existing_unbound_raises(self):
        env = Environment()
        with pytest.raises(GodRuntimeError):
            env.set_existing("ghost", 1)

    def test_names_innermost_first_no_dupes(self):
        root = Environment()
        root.define("a", 1)
        root.define("b", 2)
        child = Environment(parent=root)
        child.define("b", 3)
        assert env_names(child) == ["b", "a"]


def env_names(env):
    return env.names()


# -------------------------------------------------------------- interpreter


@pytest.fixture
def interp(tmp_path):
    if not _SIBLINGS_OK:
        pytest.skip(f"blocked on missing sibling module: {_SIBLING_ERROR}")
    return Interpreter(log_path=str(tmp_path / "godcode.log"))


def run(interp, source):
    del interp.output[:]  # each run starts with a clean slate
    interp.run_source(source)
    return interp.output


@needs_siblings
class TestDeclareReveal:
    def test_declare_and_reveal_number(self, interp):
        assert run(interp, 'DECLARE x AS 40 + 2\nREVEAL(x)') == ["42"]

    def test_reveal_string_literal(self, interp):
        assert run(interp, 'REVEAL("heaven")') == ["heaven"]

    def test_output_accumulates_in_order(self, interp):
        assert run(interp, 'REVEAL("a")\nREVEAL("b")') == ["a", "b"]

    def test_declare_does_not_rebind_outer(self, interp):
        src = (
            "DECLARE x AS \"outer\"\n"
            "DEFINE RITE shadow()\n"
            "DECLARE x AS \"inner\"\n"
            "END RITE\n"
            "INVOKE shadow()\n"
            "REVEAL(x)"
        )
        assert run(interp, src) == ["outer"]


@needs_siblings
class TestArithmetic:
    def test_precedence(self, interp):
        assert run(interp, "REVEAL(2 + 3 * 4)") == ["14"]

    def test_parens(self, interp):
        assert run(interp, "REVEAL((2 + 3) * 4)") == ["20"]

    def test_sub_mul_mod(self, interp):
        assert run(interp, "REVEAL(10 - 4)\nREVEAL(3 * 7)\nREVEAL(10 % 3)") == ["6", "21", "1"]

    def test_division_is_float(self, interp):
        assert run(interp, "REVEAL(7 / 2)") == ["3.5"]

    def test_unary_minus(self, interp):
        assert run(interp, "REVEAL(-5 + 2)") == ["-3"]

    def test_string_concat(self, interp):
        assert run(interp, 'REVEAL("alpha" + "bet")') == ["alphabet"]

    def test_symbol_concat_yields_plain_str(self, interp):
        out = run(interp, "DECLARE a AS hello\nREVEAL(a + \" world\")")
        assert out == ["hello world"]
        assert type(interp.env.get("a")) is Symbol

    def test_list_concat(self, interp):
        assert run(interp, "REVEAL([1, 2] + [3])") == ["[1, 2, 3]"]

    def test_mixed_addition_errors(self, interp):
        with pytest.raises(GodRuntimeError):
            run(interp, 'REVEAL(1 + "a")')

    def test_division_by_zero(self, interp):
        with pytest.raises(GodRuntimeError) as exc:
            run(interp, "DECLARE x AS 1\nREVEAL(x / 0)")
        assert exc.value.line == 2

    def test_modulo_by_zero(self, interp):
        with pytest.raises(GodRuntimeError):
            run(interp, "REVEAL(5 % 0)")


@needs_siblings
class TestComparisons:
    def test_numeric_comparisons(self, interp):
        src = "REVEAL(1 < 2)\nREVEAL(2 > 3)\nREVEAL(2 <= 2)\nREVEAL(3 >= 4)\nREVEAL(1 != 2)"
        assert run(interp, src) == ["true", "false", "true", "false", "true"]

    def test_is_and_is_not(self, interp):
        src = (
            "DECLARE seeker AS worthy\n"
            "REVEAL(seeker IS worthy)\n"
            "REVEAL(seeker IS NOT worthy)\n"
            "REVEAL(seeker IS unworthy)"
        )
        assert run(interp, src) == ["true", "false", "false"]

    def test_equality_cross_type_numbers(self, interp):
        assert run(interp, "REVEAL(2 = 2.0)") == ["true"]

    def test_list_equality_elementwise(self, interp):
        assert run(interp, "REVEAL([1, 2] = [1, 2])") == ["true"]
        assert run(interp, "REVEAL([1, 2] = [1, 3])") == ["false"]

    def test_mixed_ordering_errors(self, interp):
        with pytest.raises(GodRuntimeError):
            run(interp, 'REVEAL("a" < 1)')


@needs_siblings
class TestLogic:
    def test_and_or_not(self, interp):
        src = "REVEAL(1 < 2 AND 3 < 4)\nREVEAL(1 > 2 OR 3 < 4)\nREVEAL(NOT 1 < 2)"
        assert run(interp, src) == ["true", "true", "false"]

    def test_symbol_is_truthy(self, interp):
        assert run(interp, "DECLARE s AS anything\nREVEAL(NOT s)") == ["false"]

    def test_falsy_values(self, interp):
        src = 'REVEAL(NOT 0)\nREVEAL(NOT "")\nREVEAL(NOT [])\nREVEAL(NOT 1)'
        assert run(interp, src) == ["true", "true", "true", "false"]


@needs_siblings
class TestListsIndexing:
    def test_list_literal_and_index(self, interp):
        assert run(interp, "DECLARE xs AS [10, 20, 30]\nREVEAL(xs[1])") == ["20"]

    def test_negative_index(self, interp):
        assert run(interp, 'REVEAL(["a", "b"][0 - 1])') == ["b"]

    def test_string_index(self, interp):
        assert run(interp, 'REVEAL("word"[2])') == ["r"]

    def test_index_out_of_range(self, interp):
        with pytest.raises(GodRuntimeError) as exc:
            run(interp, "DECLARE xs AS [1]\nREVEAL(xs[5])")
        assert exc.value.line == 2

    def test_declare_comma_list(self, interp):
        src = "DECLARE prophets AS Isaiah,Elijah,Jeremiah\nREVEAL(LEN(prophets))"
        assert run(interp, src) == ["3"]


@needs_siblings
class TestIf:
    def test_inline_true_branch(self, interp):
        src = 'DECLARE seeker AS worthy\nIF seeker IS worthy THEN REVEAL("heaven") ELSE REVEAL("test")'
        assert run(interp, src) == ["heaven"]

    def test_inline_false_branch(self, interp):
        src = 'DECLARE seeker AS lowly\nIF seeker IS worthy THEN REVEAL("heaven") ELSE REVEAL("test")'
        assert run(interp, src) == ["test"]

    def test_block_form(self, interp):
        src = (
            "DECLARE n AS 5\n"
            "IF n > 10 THEN\n"
            'REVEAL("big")\n'
            "ELSE\n"
            'REVEAL("small")\n'
            "ENDIF"
        )
        assert run(interp, src) == ["small"]

    def test_no_else(self, interp):
        assert run(interp, 'IF 1 > 2 THEN REVEAL("nope")') == []


@needs_siblings
class TestFor:
    def test_for_over_list(self, interp):
        src = "FOR x IN [1, 2, 3]\nREVEAL(x)\nENDFOR"
        assert run(interp, src) == ["1", "2", "3"]

    def test_for_over_string(self, interp):
        src = 'FOR c IN "ab"\nREVEAL(c)\nENDFOR'
        assert run(interp, src) == ["a", "b"]

    def test_loop_var_scoped_to_loop(self, interp):
        src = "FOR x IN [1]\nREVEAL(x)\nENDFOR\nREVEAL(x)"
        # x is unbound after the loop -> Symbol fallback
        assert run(interp, src) == ["1", "x"]

    def test_for_over_non_iterable_errors(self, interp):
        with pytest.raises(GodRuntimeError):
            run(interp, "FOR x IN 42\nREVEAL(x)\nENDFOR")

    def test_legacy_open_for(self, interp):
        # No ENDFOR: body runs to END CREATION (original sample shape)
        src = (
            "BEGIN CREATION\n"
            "DECLARE xs AS [1, 2]\n"
            "FOR x IN xs\n"
            "REVEAL(x)\n"
            "END CREATION"
        )
        assert run(interp, src) == ["1", "2"]


@needs_siblings
class TestWhile:
    def test_while_counts(self, interp):
        src = (
            "DECLARE i AS 0\n"
            "WHILE i < 3 DO\n"
            "REVEAL(i)\n"
            "DECLARE i AS i + 1\n"
            "ENDWHILE"
        )
        assert run(interp, src) == ["0", "1", "2"]

    def test_endless_cycle_released(self, interp):
        with pytest.raises(GodRuntimeError) as exc:
            run(interp, 'WHILE 1 < 2 DO REVEAL("round")')
        assert "endless" in str(exc.value).lower()


@needs_siblings
class TestRites:
    def test_params_and_return(self, interp):
        src = (
            "DEFINE RITE add(a, b)\n"
            "RETURN a + b\n"
            "END RITE\n"
            "REVEAL(INVOKE add(2, 3))"
        )
        assert run(interp, src) == ["5"]

    def test_no_return_gives_void(self, interp):
        src = (
            "DEFINE RITE quiet()\n"
            'REVEAL("inside")\n'
            "END RITE\n"
            "REVEAL(INVOKE quiet())"
        )
        assert run(interp, src) == ["inside", "void"]

    def test_recursion(self, interp):
        src = (
            "DEFINE RITE fact(n)\n"
            "IF n < 2 THEN RETURN 1 ELSE RETURN n * INVOKE fact(n - 0 - 1)\n"
            "END RITE\n"
            "REVEAL(INVOKE fact(5))"
        )
        assert run(interp, src) == ["120"]

    def test_closure_sees_definition_env(self, interp):
        src = (
            'DECLARE word AS "manna"\n'
            "DEFINE RITE speak()\n"
            "REVEAL(word)\n"
            "END RITE\n"
            "INVOKE speak()"
        )
        assert run(interp, src) == ["manna"]

    def test_arity_mismatch(self, interp):
        src = "DEFINE RITE one(a)\nRETURN a\nEND RITE\nREVEAL(INVOKE one(1, 2))"
        with pytest.raises(GodRuntimeError):
            run(interp, src)

    def test_unknown_rite(self, interp):
        with pytest.raises(GodRuntimeError) as exc:
            run(interp, "INVOKE nosuchrite()")
        assert "nosuchrite" in str(exc.value)

    def test_calling_non_rite_errors(self, interp):
        with pytest.raises(GodRuntimeError):
            run(interp, "DECLARE x AS 5\nINVOKE x()")


@needs_siblings
class TestContracts:
    def test_contract_rite(self, interp):
        src = 'DECLARE c AS INVOKE contract("abraham")\nREVEAL(c)'
        assert run(interp, src) == ['contract("abraham")']

    def test_breathe_bless_anoint(self, interp, capsys):
        src = (
            'DECLARE c AS INVOKE contract("abraham")\n'
            "BREATHE life INTO c\n"
            "BLESS c\n"
            "ANOINT c\n"
        )
        run(interp, src)
        out = capsys.readouterr().out
        assert "Life breathed into c" in out
        c = interp.env.get("c")
        assert isinstance(c, Contract)
        assert c.alive and c.blessed and c.anointed

    def test_breathe_unbound_errors(self, interp):
        with pytest.raises(GodRuntimeError):
            run(interp, "BREATHE life INTO ghost")

    def test_contract_equality_by_name(self, interp):
        src = (
            'DECLARE a AS INVOKE contract("x")\n'
            'DECLARE b AS INVOKE contract("x")\n'
            'DECLARE c AS INVOKE contract("y")\n'
            "REVEAL(a = b)\n"
            "REVEAL(a = c)"
        )
        assert run(interp, src) == ["true", "false"]


@needs_siblings
class TestBuiltins:
    def test_len(self, interp):
        assert run(interp, 'REVEAL(LEN("abcd"))\nREVEAL(LEN([1, 2]))') == ["4", "2"]

    def test_str(self, interp):
        assert run(interp, "REVEAL(STR(42))\nREVEAL(TYPE(STR(42)))") == ["42", "string"]

    def test_num(self, interp):
        assert run(interp, 'REVEAL(NUM("42") + 1)\nREVEAL(NUM("4.5"))') == ["43", "4.5"]

    def test_num_bad_word(self, interp):
        with pytest.raises(GodRuntimeError):
            run(interp, 'REVEAL(NUM("manna"))')

    def test_type(self, interp):
        src = (
            "REVEAL(TYPE(1))\n"
            'REVEAL(TYPE("s"))\n'
            "REVEAL(TYPE(sym))\n"
            "REVEAL(TYPE([1]))\n"
            "REVEAL(TYPE(INVOKE contract(\"c\")))\n"
            "REVEAL(TYPE(1 < 2))\n"
        )
        assert run(interp, src) == [
            "number", "string", "symbol", "list", "contract", "boolean",
        ]

    def test_random_in_range(self, interp):
        for _ in range(20):
            interp2_out = run(Interpreter(log_path=None), "REVEAL(RANDOM(6))")
            assert interp2_out[0] in {"0", "1", "2", "3", "4", "5"}

    def test_range(self, interp):
        assert run(interp, "REVEAL(RANGE(3))\nREVEAL(RANGE(2, 5))") == [
            "[0, 1, 2]", "[2, 3, 4]",
        ]

    def test_push_returns_new_list(self, interp):
        src = "DECLARE xs AS [1]\nDECLARE ys AS PUSH(xs, 2)\nREVEAL(xs)\nREVEAL(ys)"
        assert run(interp, src) == ["[1]", "[1, 2]"]

    def test_upper_lower(self, interp):
        assert run(interp, 'REVEAL(UPPER("amen"))\nREVEAL(LOWER("AMEN"))') == ["AMEN", "amen"]

    def test_split_join(self, interp):
        src = 'REVEAL(SPLIT("a,b", ","))\nREVEAL(JOIN(["a", "b"], "-"))'
        assert run(interp, src) == ["[a, b]", "a-b"]

    def test_ask(self, interp, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt="": "Moses")
        assert run(interp, 'DECLARE name AS ASK("Who? ")\nREVEAL(name)') == ["Moses"]

    def test_behold(self, interp):
        out = run(interp, "REVEAL(BEHOLD())")
        assert len(out) == 1 and "T" in out[0]

    def test_reverse(self, interp):
        assert run(interp, 'REVEAL(REVERSE("abc"))\nREVEAL(REVERSE([1, 2]))') == [
            "cba", "[2, 1]",
        ]

    def test_unknown_name_is_not_builtin(self, interp):
        with pytest.raises(GodRuntimeError):
            run(interp, "REVEAL(FROBNICATE(1))")


@needs_siblings
class TestTestify:
    def test_passing_testimony(self, interp, capsys):
        run(interp, "TESTIFY(1 < 2)")
        assert "It is true" in capsys.readouterr().out

    def test_failing_testimony(self, interp):
        with pytest.raises(GodRuntimeError) as exc:
            run(interp, "DECLARE x AS 1\nTESTIFY(x > 5)")
        assert exc.value.line == 2


@needs_siblings
class TestAscend:
    def test_ascend_ends_run_in_peace(self, interp, capsys):
        src = 'REVEAL("before")\nASCEND\nREVEAL("after")'
        interp.run_source(src)
        assert interp.output == ["before"]
        assert "ascended in peace" in capsys.readouterr().out


@needs_siblings
class TestSymbolFallback:
    def test_bare_words_are_symbols(self, interp):
        assert run(interp, "REVEAL(undeclared)") == ["undeclared"]

    def test_symbol_compares_with_identifier(self, interp):
        assert run(interp, "REVEAL(manna = manna)") == ["true"]


@needs_siblings
class TestErrorsCarryLines:
    def test_error_line_numbers(self, interp):
        with pytest.raises(GodRuntimeError) as exc:
            run(interp, 'REVEAL("ok")\nREVEAL(1 + "x")')
        assert exc.value.line == 2

    def test_undefined_rite_line(self, interp):
        with pytest.raises(GodCodeError) as exc:
            run(interp, "DECLARE a AS 1\nINVOKE ghost()")
        assert exc.value.line == 2


@needs_siblings
class TestReflectProphesySeal:
    def test_reflect_prints_table(self, interp, capsys):
        run(interp, 'DECLARE alpha AS 1\nREFLECT')
        out = capsys.readouterr().out
        assert "alpha = 1" in out

    def test_prophesy_without_spirit(self, interp, capsys):
        run(interp, "PROPHESY the rains will come")
        assert "PROPHESY" in capsys.readouterr().out

    def test_prophesy_with_spirit(self, interp, capsys):
        class FakeSpirit:
            def prophesy(self, text):
                return f"oracle says: {text}"

        spirit_interp = Interpreter(spirit=FakeSpirit(), log_path=None)
        spirit_interp.run_source("PROPHESY the rains will come")
        assert "oracle says: the rains will come" in capsys.readouterr().out

    def test_seal_without_ledger_warns(self, interp, capsys):
        run(interp, 'SEAL "covenant"')
        assert "No covenant ledger" in capsys.readouterr().out

    def test_seal_with_ledger(self, interp, capsys):
        class FakeLedger:
            def __init__(self):
                self.records = []

            def seal(self, record):
                self.records.append(record)
                return {"index": len(self.records) - 1, "hash": "deadbeefcafe1234"}

        ledger = FakeLedger()
        ledger_interp = Interpreter(ledger=ledger, log_path=None)
        ledger_interp.run_source('SEAL "covenant"')
        out = capsys.readouterr().out
        assert "block 0" in out and "deadbeef" in out
        assert ledger.records[0]["sealed"] == "covenant"
        assert ledger.records[0]["type"] == "string"


@needs_siblings
class TestAuditLog:
    def test_session_logged(self, interp, tmp_path):
        log = tmp_path / "godcode.log"
        fresh = Interpreter(log_path=str(log))
        fresh.run_source('REVEAL("amen")', source_name="psalm")
        text = log.read_text(encoding="utf-8")
        assert "SESSION BEGIN psalm" in text
        assert "SESSION END psalm" in text
        assert "Reveal" in text

    def test_errors_logged(self, interp, tmp_path):
        log = tmp_path / "godcode.log"
        fresh = Interpreter(log_path=str(log))
        with pytest.raises(GodRuntimeError):
            fresh.run_source('REVEAL(1 / 0)')
        assert "ERROR" in log.read_text(encoding="utf-8")


@needs_siblings
class TestSampleEndToEnd:
    def test_sample_godcode(self, tmp_path):
        import pathlib

        sample = pathlib.Path(__file__).resolve().parent.parent / "sample.godcode"
        source = sample.read_text(encoding="utf-8")
        interp = Interpreter(log_path=str(tmp_path / "godcode.log"))
        interp.run_source(source, source_name=str(sample))
        assert interp.output == ["heaven"]
