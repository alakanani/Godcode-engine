"""Token types and the Token dataclass for God Code v2.0.

Keyword tokens carry their canonical UPPER name as ``value``;
identifiers preserve the author's casing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # --- keywords -----------------------------------------------------------
    BEGIN = auto()
    CREATION = auto()
    END = auto()
    DECLARE = auto()
    AS = auto()
    BREATHE = auto()
    LIFE = auto()
    INTO = auto()
    REVEAL = auto()
    PROPHESY = auto()
    ASCEND = auto()
    IF = auto()
    THEN = auto()
    ELSE = auto()
    ENDIF = auto()
    FOR = auto()
    IN = auto()
    ENDFOR = auto()
    WHILE = auto()
    DO = auto()
    ENDWHILE = auto()
    DEFINE = auto()
    RITE = auto()
    INVOKE = auto()
    RETURN = auto()
    IMPORT = auto()
    IS = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    # §4 additions (missed in §1's list)
    REFLECT = auto()
    BLESS = auto()
    ANOINT = auto()
    SEAL = auto()
    TESTIFY = auto()
    # boolean / void literals (added for fmt <-> parse round-trip fidelity)
    TRUE = auto()
    FALSE = auto()
    VOID = auto()
    # --- literals -----------------------------------------------------------
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()
    # --- operators ----------------------------------------------------------
    PLUS = auto()      # +
    MINUS = auto()     # -
    STAR = auto()      # *
    SLASH = auto()     # /
    PERCENT = auto()   # %
    EQ = auto()        # = or ==
    NEQ = auto()       # !=
    LT = auto()        # <
    GT = auto()        # >
    LTE = auto()       # <=
    GTE = auto()       # >=
    # --- punctuation --------------------------------------------------------
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    # --- structural ---------------------------------------------------------
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: object  # NUMBER -> int|float, STRING -> str (unescaped),
                   # IDENT/keywords -> str, operators/punct -> the lexeme
    line: int      # 1-based
    col: int       # 1-based

    def __repr__(self) -> str:  # compact, readable in test failures
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"
