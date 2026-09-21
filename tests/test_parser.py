"""Parser tests for God Code v2.0."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from godcode import ast as A
from godcode.errors import LexerError, ParseError
from godcode.lexer import Lexer
from godcode.parser import Parser

REPO = Path(__file__).resolve().parent.parent


def parse_src(src):
    return Parser(Lexer(src).lex()).parse()


def parse_block(src):
    """Parse source wrapped in BEGIN CREATION; return the CreationBlock."""
    prog = parse_src(f"BEGIN CREATION\n{src}\nEND CREATION")
    assert len(prog.statements) == 1
    return prog.statements[0]


def stmt(src):
    block = parse_block(src)
    assert len(block.statements) == 1
    return block.statements[0]


# -- the original sample ------------------------------------------------------

def test_sample_godcode_parses():
    prog = parse_src((REPO / "sample.godcode").read_text())
    assert isinstance(prog, A.Program)
    assert len(prog.statements) == 1
    block = prog.statements[0]
    assert isinstance(block, A.CreationBlock)
    assert len(block.statements) == 4

    d = block.statements[0]
    assert isinstance(d, A.Declare) and d.name == "seeker"
    assert isinstance(d.value, A.Identifier) and d.value.name == "worthy"

    cond = block.statements[1]
    assert isinstance(cond, A.IfStmt)
    assert isinstance(cond.cond, A.BinaryOp) and cond.cond.op == "=="
    assert cond.cond.left.name == "seeker" and cond.cond.right.name == "worthy"
    assert len(cond.then_body) == 1 and len(cond.else_body) == 1
    assert isinstance(cond.then_body[0], A.Reveal)
    assert cond.then_body[0].expr.value == "heaven"
    assert cond.else_body[0].expr.value == "test"

    dp = block.statements[2]
    assert isinstance(dp, A.Declare) and dp.name == "prophets"
    assert isinstance(dp.value, A.ListLiteral)
    assert [i.name for i in dp.value.items] == ["Isaiah", "Elijah", "Jeremiah"]

    loop = block.statements[3]
    assert isinstance(loop, A.ForLoop) and loop.var == "prophet"
    assert isinstance(loop.iterable, A.Identifier)
    # legacy open FOR: body runs to END CREATION, no ENDFOR consumed
    assert len(loop.body) == 2
    assert isinstance(loop.body[0], A.Breathe) and loop.body[0].name == "prophet"
    assert isinstance(loop.body[1], A.Ascend)


# -- declare ------------------------------------------------------------------

def test_declare_single_value_is_not_a_list():
    d = stmt("DECLARE x AS 42")
    assert isinstance(d, A.Declare)
    assert d.name == "x"
    assert isinstance(d.value, A.Literal) and d.value.value == 42


def test_declare_comma_list_becomes_list_literal():
    d = stmt("DECLARE xs AS 1, 2, 3")
    assert isinstance(d.value, A.ListLiteral)
    assert [i.value for i in d.value.items] == [1, 2, 3]


def test_declare_bracket_list_stays_single():
    d = stmt("DECLARE xs AS [1, 2]")
    assert isinstance(d.value, A.ListLiteral)
    assert len(d.value.items) == 2


# -- simple statements --------------------------------------------------------

def test_breathe():
    b = stmt("BREATHE life INTO prophet")
    assert isinstance(b, A.Breathe) and b.name == "prophet"


def test_reveal_requires_parens():
    r = stmt('REVEAL("hi")')
    assert isinstance(r, A.Reveal) and r.expr.value == "hi"
    with pytest.raises(ParseError):
        parse_block('REVEAL "hi"')


def test_prophesy_captures_rest_of_line():
    p = stmt("PROPHESY thus saith the lord of hosts")
    assert isinstance(p, A.Prophesy)
    assert p.text == "thus saith the lord of hosts"


def test_prophesy_empty_line_gives_empty_text():
    p = stmt("PROPHESY")
    assert isinstance(p, A.Prophesy) and p.text == ""


def test_prophesy_stops_at_newline():
    block = parse_block("PROPHESY peace\nREVEAL(1)")
    assert block.statements[0].text == "peace"
    assert isinstance(block.statements[1], A.Reveal)


def test_ascend_reflect_bless_anoint():
    assert isinstance(stmt("ASCEND"), A.Ascend)
    assert isinstance(stmt("REFLECT"), A.Reflect)
    b = stmt("BLESS seeker")
    assert isinstance(b, A.Bless) and b.name == "seeker"
    an = stmt("ANOINT prophet")
    assert isinstance(an, A.Anoint) and an.name == "prophet"


def test_seal_and_testify_take_expressions():
    s = stmt("SEAL covenant")
    assert isinstance(s, A.SealStmt) and s.expr.name == "covenant"
    t = stmt("TESTIFY x == 1")
    assert isinstance(t, A.Testify) and t.expr.op == "=="


def test_import_string_path():
    im = stmt('IMPORT "scrolls/math.god"')
    assert isinstance(im, A.Import) and im.path == "scrolls/math.god"


def test_return_with_and_without_expression():
    r = stmt("RETURN 42")
    assert isinstance(r, A.Return) and r.expr.value == 42
    r2 = stmt("RETURN")
    assert isinstance(r2, A.Return) and r2.expr is None


# -- if -----------------------------------------------------------------------

def test_block_if_else_endif():
    src = ("IF x IS 1 THEN\n"
           "  REVEAL(\"one\")\n"
           "ELSE\n"
           "  REVEAL(\"other\")\n"
           "ENDIF")
    node = stmt(src)
    assert isinstance(node, A.IfStmt)
    assert node.cond.op == "=="
    assert len(node.then_body) == 1 and len(node.else_body) == 1


def test_block_if_without_else():
    node = stmt("IF x THEN\n  REVEAL(1)\nENDIF")
    assert node.else_body == []


def test_inline_if_without_else():
    node = stmt("IF x THEN REVEAL(1)")
    assert len(node.then_body) == 1 and node.else_body == []


def test_nested_block_if():
    src = ("IF a THEN\n"
           "  IF b THEN\n"
           "    REVEAL(1)\n"
           "  ENDIF\n"
           "ENDIF")
    node = stmt(src)
    inner = node.then_body[0]
    assert isinstance(inner, A.IfStmt)


# -- for ----------------------------------------------------------------------

def test_block_for_with_endfor():
    node = stmt("FOR p IN prophets\n  REVEAL(p)\nENDFOR")
    assert isinstance(node, A.ForLoop)
    assert node.var == "p"
    assert len(node.body) == 1


def test_inline_for_single_statement():
    node = stmt("FOR p IN prophets REVEAL(p)")
    assert len(node.body) == 1


def test_legacy_for_inside_rite_runs_to_end_rite():
    src = ("DEFINE RITE walk(xs)\n"
           "  FOR x IN xs\n"
           "  REVEAL(x)\n"
           "END RITE")
    rite = stmt(src)
    loop = rite.body[0]
    assert isinstance(loop, A.ForLoop) and len(loop.body) == 1


# -- while --------------------------------------------------------------------

def test_block_while():
    node = stmt("WHILE x < 10 DO\n  REVEAL(x)\nENDWHILE")
    assert isinstance(node, A.WhileLoop)
    assert node.cond.op == "<"
    assert len(node.body) == 1


def test_inline_while():
    node = stmt("WHILE x DO REVEAL(x)")
    assert len(node.body) == 1


# -- define rite --------------------------------------------------------------

def test_define_rite_with_params():
    node = stmt("DEFINE RITE give(a, b)\n  REVEAL(a)\nEND RITE")
    assert isinstance(node, A.DefineRite)
    assert node.name == "give" and node.params == ["a", "b"]
    assert len(node.body) == 1


def test_define_rite_no_params():
    node = stmt("DEFINE RITE amen()\n  ASCEND\nEND RITE")
    assert node.params == []


def test_define_rite_inline_body():
    node = stmt("DEFINE RITE double(x) RETURN x * 2 END RITE")
    assert len(node.body) == 1
    assert isinstance(node.body[0], A.Return)


# -- invoke / calls ------------------------------------------------------------

def test_invoke_as_expression():
    d = stmt("DECLARE x AS INVOKE double(21)")
    assert isinstance(d.value, A.CallExpr)
    assert d.value.callee == "double"
    assert d.value.args[0].value == 21


def test_invoke_as_statement_wraps_exprstmt():
    node = stmt("INVOKE greet(seeker)")
    assert isinstance(node, A.ExprStmt)
    assert isinstance(node.expr, A.CallExpr)


def test_bare_call_expression_statement():
    node = stmt("greet(seeker, 2)")
    assert isinstance(node.expr, A.CallExpr)
    assert node.expr.callee == "greet"
    assert len(node.expr.args) == 2


def test_call_no_args():
    node = stmt("INVOKE amen()")
    assert node.expr.args == []


# -- expressions ---------------------------------------------------------------

def test_precedence_mul_before_add():
    d = stmt("DECLARE x AS 1 + 2 * 3")
    assert d.value.op == "+"
    assert d.value.right.op == "*"


def test_precedence_parens_override():
    d = stmt("DECLARE x AS (1 + 2) * 3")
    assert d.value.op == "*"
    assert d.value.left.op == "+"


def test_is_and_is_not_map_to_eq_neq():
    a = stmt("DECLARE x AS a IS b").value
    assert (a.op, a.left.name, a.right.name) == ("==", "a", "b")
    b = stmt("DECLARE x AS a IS NOT b").value
    assert b.op == "!="


def test_single_eq_and_double_eq_both_mean_equality():
    assert stmt("DECLARE x AS a = b").value.op == "=="
    assert stmt("DECLARE x AS a == b").value.op == "=="


def test_comparison_operators():
    for src_op, want in [("!=", "!="), ("<", "<"), (">", ">"),
                         ("<=", "<="), (">=", ">=")]:
        node = stmt(f"DECLARE x AS a {src_op} b").value
        assert node.op == want, src_op


def test_boolean_precedence_not_and_or():
    node = stmt("DECLARE x AS NOT a AND b OR c").value
    assert node.op == "or"
    assert node.left.op == "and"
    assert node.left.left.op == "not"


def test_unary_minus_binds_tighter_than_mul():
    node = stmt("DECLARE x AS -a * b").value
    assert node.op == "*"
    assert node.left.op == "-"


def test_not_binds_looser_than_comparison():
    node = stmt("DECLARE x AS NOT a == b").value
    assert node.op == "not"
    assert node.operand.op == "=="


def test_list_literal_and_indexing():
    d = stmt("DECLARE x AS [1, 2, 3][0]")
    assert isinstance(d.value, A.Index)
    assert isinstance(d.value.obj, A.ListLiteral)
    assert d.value.index.value == 0


def test_chained_indexing():
    d = stmt("DECLARE x AS m[0][1]")
    assert isinstance(d.value, A.Index)
    assert isinstance(d.value.obj, A.Index)


def test_true_false_void_literals():
    assert stmt("DECLARE a AS TRUE").value.value is True
    assert stmt("DECLARE b AS FALSE").value.value is False
    assert stmt("DECLARE c AS VOID").value.value is None


def test_string_and_number_literals():
    assert stmt('DECLARE s AS "hi"').value.value == "hi"
    assert stmt("DECLARE n AS 2.5").value.value == 2.5


def test_expression_statement():
    node = stmt("1 + 2")
    assert isinstance(node, A.ExprStmt)
    assert node.expr.op == "+"


# -- programs ------------------------------------------------------------------

def test_bare_statements_without_creation_block():
    prog = parse_src("DECLARE x AS 1\nREVEAL(x)")
    assert isinstance(prog, A.Program)
    assert len(prog.statements) == 2
    assert isinstance(prog.statements[1], A.Reveal)


def test_empty_source_gives_empty_program():
    prog = parse_src("\n  \n")
    assert prog.statements == []


def test_ast_nodes_carry_line_numbers():
    block = parse_block("DECLARE x AS 1\nREVEAL(x)")
    assert block.statements[0].line == 2
    assert block.statements[1].line == 3


# -- errors --------------------------------------------------------------------

def test_missing_endif_reports_line():
    with pytest.raises(ParseError) as ei:
        parse_block("IF x THEN\n  REVEAL(1)")
    assert ei.value.line is not None


def test_missing_end_creation_reports_line():
    with pytest.raises(ParseError) as ei:
        parse_src("BEGIN CREATION\nDECLARE x AS 1\n")
    assert ei.value.line is not None


def test_missing_endwhile_reports_line():
    with pytest.raises(ParseError) as ei:
        parse_block("WHILE x DO\n  REVEAL(x)\n")
    assert ei.value.line == 5  # the END CREATION that arrived instead


def test_bad_expression_reports_line():
    with pytest.raises(ParseError) as ei:
        parse_block("DECLARE x AS +")
    assert ei.value.line == 2


def test_unterminated_string_surfaces_lexer_error_with_line():
    with pytest.raises(LexerError) as ei:
        parse_block('DECLARE x AS "oops')
    assert ei.value.line == 2


def test_bad_character_surfaces_lexer_error():
    with pytest.raises(LexerError):
        parse_block("DECLARE x AS 5 @ 3")


def test_if_without_then():
    with pytest.raises(ParseError) as ei:
        parse_block("IF x REVEAL(1) ENDIF")
    assert ei.value.line == 2


def test_for_without_in():
    with pytest.raises(ParseError):
        parse_block("FOR x OVER y\nENDFOR")


def test_declare_without_name():
    with pytest.raises(ParseError):
        parse_block("DECLARE AS 5")


def test_stray_endfor_is_an_error():
    with pytest.raises(ParseError):
        parse_block("ENDFOR")


def test_trailing_tokens_after_creation_rejected():
    with pytest.raises(ParseError):
        parse_src("BEGIN CREATION\nEND CREATION\nDECLARE x AS 1")


def test_error_message_names_expected_and_found():
    with pytest.raises(ParseError) as ei:
        parse_block("BREATHE INTO x")
    assert "LIFE" in str(ei.value)
