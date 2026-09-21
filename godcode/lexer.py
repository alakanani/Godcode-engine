"""Lexer for God Code v2.0.

``Lexer(source).lex()`` turns source text into a list of Tokens with
1-based line/column positions, NEWLINE tokens for each physical line
break, and a final EOF token. ``#`` starts a comment to end of line.
Keywords are matched case-insensitively (canonical value = UPPER);
identifiers preserve their casing.
"""

from __future__ import annotations

from .errors import LexerError
from .tokens import Token, TokenType

# Every alphabetic TokenType name that is not a literal/structural/operator
# token is a keyword. New keyword TokenTypes are picked up automatically.
_NON_KEYWORD_NAMES = {
    "NUMBER", "STRING", "IDENT", "NEWLINE", "EOF",
    "PLUS", "MINUS", "STAR", "SLASH", "PERCENT",
    "EQ", "NEQ", "LT", "GT", "LTE", "GTE",
    "LPAREN", "RPAREN", "LBRACKET", "RBRACKET", "COMMA",
}
KEYWORDS: dict[str, TokenType] = {
    tt.name: tt for tt in TokenType if tt.name not in _NON_KEYWORD_NAMES
}

_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}

_SINGLE_CHAR_TOKENS = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    "=": TokenType.EQ,
    "<": TokenType.LT,
    ">": TokenType.GT,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ",": TokenType.COMMA,
}

_MULTI_CHAR_TOKENS = {
    "!=": TokenType.NEQ,
    "<=": TokenType.LTE,
    ">=": TokenType.GTE,
    "==": TokenType.EQ,  # both = and == spell equality
}


class Lexer:
    def __init__(self, source: str):
        self.source = source

    def lex(self) -> list[Token]:
        src = self.source
        n = len(src)
        tokens: list[Token] = []
        i = 0
        line = 1
        col = 1

        def here() -> tuple[int, int]:
            return line, col

        while i < n:
            c = src[i]

            # whitespace (but not newlines)
            if c == " " or c == "\t":
                i += 1
                col += 1
                continue

            # line breaks: collapse \r\n, tolerate lone \r
            if c == "\r" or c == "\n":
                ln, cl = here()
                if c == "\r" and i + 1 < n and src[i + 1] == "\n":
                    i += 2
                else:
                    i += 1
                tokens.append(Token(TokenType.NEWLINE, "\n", ln, cl))
                line += 1
                col = 1
                continue

            # comments run to end of line (the newline itself is still lexed)
            if c == "#":
                while i < n and src[i] != "\n" and src[i] != "\r":
                    i += 1
                continue

            # strings
            if c == '"':
                tok, i, col = self._lex_string(src, i, line, col)
                tokens.append(tok)
                continue

            # numbers
            if c.isdigit():
                tok, i, col = self._lex_number(src, i, line, col)
                tokens.append(tok)
                continue

            # words: keywords (case-insensitive) or identifiers
            if c.isalpha() or c == "_":
                start = i
                ln, cl = here()
                while i < n and (src[i].isalnum() or src[i] == "_"):
                    i += 1
                word = src[start:i]
                col += i - start
                upper = word.upper()
                if upper in KEYWORDS:
                    tokens.append(Token(KEYWORDS[upper], upper, ln, cl))
                else:
                    tokens.append(Token(TokenType.IDENT, word, ln, cl))
                continue

            # operators: multi-char first, then single-char
            two = src[i : i + 2]
            if two in _MULTI_CHAR_TOKENS:
                ln, cl = here()
                tokens.append(Token(_MULTI_CHAR_TOKENS[two], two, ln, cl))
                i += 2
                col += 2
                continue
            if c in _SINGLE_CHAR_TOKENS:
                ln, cl = here()
                tokens.append(Token(_SINGLE_CHAR_TOKENS[c], c, ln, cl))
                i += 1
                col += 1
                continue

            raise LexerError(
                f"The heavens do not recognize the character {c!r}; "
                "it has no place in the holy tongue",
                line=line,
                col=col,
            )

        tokens.append(Token(TokenType.EOF, "", line, col))
        return tokens

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _lex_string(src: str, i: int, line: int, col: int):
        """Lex a string starting at the opening quote. Returns (token, i, col)."""
        n = len(src)
        open_line, open_col = line, col
        i += 1  # opening quote
        col += 1
        buf: list[str] = []
        while i < n and src[i] != '"':
            ch = src[i]
            if ch == "\n" or ch == "\r":
                raise LexerError(
                    "The utterance was never finished: string runs past the "
                    "end of the line without a closing quote",
                    line=open_line,
                    col=open_col,
                )
            if ch == "\\":
                if i + 1 >= n:
                    break
                esc = src[i + 1]
                if esc not in _ESCAPES:
                    raise LexerError(
                        f"Unknown escape '\\{esc}'; the holy escapes are "
                        '\\\\ \\" \\n \\t',
                        line=line,
                        col=col,
                    )
                buf.append(_ESCAPES[esc])
                i += 2
                col += 2
            else:
                buf.append(ch)
                i += 1
                col += 1
        if i >= n:
            raise LexerError(
                "The utterance was never finished: unterminated string",
                line=open_line,
                col=open_col,
            )
        i += 1  # closing quote
        col += 1
        return Token(TokenType.STRING, "".join(buf), open_line, open_col), i, col

    @staticmethod
    def _lex_number(src: str, i: int, line: int, col: int):
        """Lex an int or float starting at a digit. Returns (token, i, col)."""
        n = len(src)
        start = i
        while i < n and src[i].isdigit():
            i += 1
        is_float = False
        if i < n and src[i] == ".":
            if i + 1 < n and src[i + 1].isdigit():
                is_float = True
                i += 1
                while i < n and src[i].isdigit():
                    i += 1
            else:
                raise LexerError(
                    f"Malformed number {src[start:i+1]!r}; a decimal point "
                    "must be followed by digits",
                    line=line,
                    col=col,
                )
        text = src[start:i]
        value: int | float = float(text) if is_float else int(text)
        tok = Token(TokenType.NUMBER, value, line, col)
        return tok, i, col + (i - start)
