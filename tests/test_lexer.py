"""Lexer tests for God Code v2.0."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from godcode.errors import LexerError
from godcode.lexer import Lexer
from godcode.tokens import TokenType as TT


def lex(src):
    return Lexer(src).lex()


def types(src):
    return [t.type for t in lex(src)]


# -- keywords ---------------------------------------------------------------

def test_keywords_case_insensitive_canonical_upper():
    toks = lex("begin creation DECLARE Seeker as WORTHY")
    assert [(t.type, t.value) for t in toks[:5]] == [
        (TT.BEGIN, "BEGIN"),
        (TT.CREATION, "CREATION"),
        (TT.DECLARE, "DECLARE"),
        (TT.IDENT, "Seeker"),
        (TT.AS, "AS"),
    ]


def test_identifiers_preserve_case():
    toks = lex("myVar _hidden x1")
    assert [t.value for t in toks if t.type is TT.IDENT] == ["myVar", "_hidden", "x1"]


def test_all_spec_keywords_recognized():
    words = ("begin creation end declare as breathe life into reveal prophesy "
             "ascend if then else endif for in endfor while do endwhile "
             "define rite invoke return import is not and or "
             "reflect bless anoint seal testify true false void")
    toks = lex(words)
    idents = [t for t in toks if t.type is TT.IDENT]
    assert idents == [], f"unrecognized keywords lexed as IDENT: {idents}"
    assert toks[-2].type is TT.VOID  # last word before EOF


def test_extra_keywords_have_distinct_types():
    toks = {t.value: t.type for t in lex("REFLECT BLESS ANOINT SEAL TESTIFY")
            if t.type not in (TT.NEWLINE, TT.EOF)}
    assert toks == {
        "REFLECT": TT.REFLECT, "BLESS": TT.BLESS, "ANOINT": TT.ANOINT,
        "SEAL": TT.SEAL, "TESTIFY": TT.TESTIFY,
    }


# -- positions --------------------------------------------------------------

def test_line_and_col_tracking():
    toks = lex("DECLARE x AS 5\n  REVEAL(x)")
    by_type = {}
    for t in toks:
        by_type.setdefault(t.type, []).append(t)
    d = by_type[TT.DECLARE][0]
    assert (d.line, d.col) == (1, 1)
    x = by_type[TT.IDENT][0]
    assert (x.line, x.col) == (1, 9) and x.value == "x"
    r = by_type[TT.REVEAL][0]
    assert (r.line, r.col) == (2, 3)
    eof = by_type[TT.EOF][0]
    assert (eof.line, eof.col) == (2, 12)


def test_newline_tokens_and_final_eof():
    toks = lex("a\n\nb")
    assert [t.type for t in toks] == [TT.IDENT, TT.NEWLINE, TT.NEWLINE, TT.IDENT, TT.EOF]


def test_crlf_collapses_to_single_newline():
    toks = lex("a\r\nb")
    assert [t.type for t in toks] == [TT.IDENT, TT.NEWLINE, TT.IDENT, TT.EOF]
    assert toks[2].line == 2


# -- literals ---------------------------------------------------------------

def test_int_and_float_numbers():
    toks = lex("3 4.5 0 100.25")
    nums = [t for t in toks if t.type is TT.NUMBER]
    assert [(t.value, type(t.value)) for t in nums] == [
        (3, int), (4.5, float), (0, int), (100.25, float),
    ]


def test_strings_with_escapes():
    toks = lex(r'"heaven" "a\"b" "c\\d" "e\nf" "g\th"')
    strs = [t for t in toks if t.type is TT.STRING]
    assert [t.value for t in strs] == ["heaven", 'a"b', "c\\d", "e\nf", "g\th"]


def test_empty_string():
    toks = lex('""')
    assert toks[0].type is TT.STRING and toks[0].value == ""


# -- comments ---------------------------------------------------------------

def test_comment_to_end_of_line_emits_no_token():
    toks = lex("DECLARE x AS 5 # a comment\nREVEAL(x) # trailing")
    kinds = [t.type for t in toks]
    assert kinds == [TT.DECLARE, TT.IDENT, TT.AS, TT.NUMBER, TT.NEWLINE,
                    TT.REVEAL, TT.LPAREN, TT.IDENT, TT.RPAREN, TT.EOF]


def test_comment_only_line_still_breaks_line():
    toks = lex("# just a comment\nDECLARE")
    assert toks[0].type is TT.NEWLINE
    assert toks[1].type is TT.DECLARE
    assert toks[1].line == 2


# -- operators ----------------------------------------------------------------

def test_multi_char_operators_lexed_first():
    toks = lex("!= <= >= ==")
    assert [(t.type, t.value) for t in toks[:4]] == [
        (TT.NEQ, "!="), (TT.LTE, "<="), (TT.GTE, ">="), (TT.EQ, "=="),
    ]


def test_single_char_operators_and_punctuation():
    toks = lex("= < > + - * / % ( ) [ ] ,")
    assert [t.type for t in toks[:13]] == [
        TT.EQ, TT.LT, TT.GT, TT.PLUS, TT.MINUS, TT.STAR, TT.SLASH,
        TT.PERCENT, TT.LPAREN, TT.RPAREN, TT.LBRACKET, TT.RBRACKET, TT.COMMA,
    ]
    assert toks[0].value == "="  # single = is EQ too


def test_double_eq_and_single_eq_are_both_eq():
    assert lex("==")[0].type is TT.EQ
    assert lex("=")[0].type is TT.EQ


# -- errors -------------------------------------------------------------------

def test_unterminated_string_raises_with_line():
    with pytest.raises(LexerError) as ei:
        lex('DECLARE x AS "never ends\nREVEAL(x)')
    assert ei.value.line == 1


def test_string_ending_at_eof_raises():
    with pytest.raises(LexerError) as ei:
        lex('"abc')
    assert ei.value.line == 1
    assert "nterminated" in str(ei.value)


def test_illegal_character_names_it_with_position():
    with pytest.raises(LexerError) as ei:
        lex("DECLARE x AS 5 @\n")
    err = ei.value
    assert "@" in str(err)
    assert err.line == 1 and err.col == 16


def test_lone_bang_is_illegal():
    with pytest.raises(LexerError):
        lex("x ! y")


def test_malformed_number_raises():
    with pytest.raises(LexerError) as ei:
        lex("4.")
    assert ei.value.line == 1
    assert "alformed" in str(ei.value)


def test_unknown_escape_raises():
    with pytest.raises(LexerError) as ei:
        lex(r'"bad \q escape"')
    assert ei.value.line == 1
