"""Recursive-descent parser for God Code v2.0.

``Parser(tokens).parse()`` returns a ``Program``. A program is either a
``BEGIN CREATION ... END CREATION`` block (wrapped in a Program) or a
bare sequence of statements (for scrolls / fragments).

Statement forms (spec §4):
- DECLARE name AS expr (, expr)*      -> Declare (multi-expr -> ListLiteral)
- BREATHE LIFE INTO name              -> Breathe
- REVEAL(expr)                        -> Reveal
- PROPHESY <rest of line>             -> Prophesy
- ASCEND / REFLECT                    -> Ascend / Reflect
- BLESS name / ANOINT name            -> Bless / Anoint
- SEAL expr / TESTIFY expr            -> SealStmt / Testify
- IF expr THEN ... (block: ENDIF / inline)          -> IfStmt
- FOR name IN expr ... (block: ENDFOR / legacy open / inline) -> ForLoop
- WHILE expr DO ... (block: ENDWHILE / inline)      -> WhileLoop
- DEFINE RITE name(params) ... END RITE (block or inline) -> DefineRite
- RETURN expr?                        -> Return
- IMPORT "path"                       -> Import
- INVOKE name(args) | any expression   -> CallExpr / ExprStmt

Expression precedence (low -> high):
  or -> and -> not -> comparison (IS [NOT], =, ==, !=, <, >, <=, >=)
  -> additive (+ -) -> multiplicative (* / %) -> unary (-, NOT) -> primary
``IS``/``IS NOT`` become ``==``/``!=`` BinaryOps.
"""

from __future__ import annotations

from . import ast as A
from .errors import ParseError
from .lexer import Lexer
from .tokens import Token, TokenType

TT = TokenType

_EXPR_STARTS = {
    TT.NUMBER, TT.STRING, TT.IDENT, TT.LPAREN, TT.LBRACKET,
    TT.MINUS, TT.NOT, TT.TRUE, TT.FALSE, TT.VOID, TT.INVOKE,
}

# Tokens after which RETURN takes no expression.
_RETURN_TERMINATORS = {
    TT.NEWLINE, TT.EOF, TT.END, TT.ENDIF, TT.ELSE, TT.ENDFOR, TT.ENDWHILE,
}


class Parser:
    def __init__(self, tokens: list[Token]):
        if not tokens:
            raise ParseError("The scroll is empty; there is nothing to reveal")
        self.tokens = tokens
        self.pos = 0
        # Tracks lexically enclosing FOR/WHILE loops so BREAK and CONTINUE
        # can be rejected at parse time when no loop holds them. A rite
        # body resets this to 0: loop signals never cross a rite boundary.
        self._loop_depth = 0

    # -- public ------------------------------------------------------------

    def parse(self) -> A.Program:
        self._skip_newlines()
        first = self._peek()
        if self._check(TT.BEGIN):
            block = self._parse_creation_block()
            self._skip_newlines()
            t = self._peek()
            if t.type is not TT.EOF:
                raise ParseError(
                    f"The creation is sealed, yet {self._describe(t)} remains; "
                    "a scroll holds only one creation",
                    line=t.line, col=t.col,
                )
            return A.Program(statements=[block], line=block.line, col=block.col)
        stmts = self._parse_body(
            end={TT.EOF},
            missing="the end of the scroll",
            opening=None,
        )
        return A.Program(statements=stmts, line=first.line, col=first.col)

    # -- cursor helpers ----------------------------------------------------

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _peek_next(self) -> Token:
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1]
        return self.tokens[-1]

    def _advance(self) -> Token:
        t = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return t

    def _check(self, tt: TokenType) -> bool:
        return self._peek().type is tt

    def _expect(self, tt: TokenType, what: str | None = None) -> Token:
        t = self._peek()
        if t.type is not tt:
            raise ParseError(
                f"Expected {what or tt.name} but found {self._describe(t)}",
                line=t.line, col=t.col,
            )
        return self._advance()

    def _skip_newlines(self) -> None:
        while self._check(TT.NEWLINE):
            self._advance()

    @staticmethod
    def _describe(t: Token) -> str:
        if t.type is TT.EOF:
            return "the end of the scroll"
        if t.type is TT.NEWLINE:
            return "the end of the line"
        if t.type is TT.IDENT:
            return f"the name '{t.value}'"
        if t.type is TT.NUMBER:
            return f"the number {t.value!r}"
        if t.type is TT.STRING:
            return f"the text {t.value!r}"
        return f"'{t.value}'"

    # -- statement lists ---------------------------------------------------

    def _parse_body(self, *, end: set[TokenType], missing: str,
                    opening: Token | None, legacy_for: bool = False) -> list:
        """Parse statements until a token in ``end`` (left unconsumed).

        With ``legacy_for``, END CREATION / END RITE / EOF also end the body
        without being consumed (the original sample.godcode's open FOR).
        Otherwise hitting them raises ParseError naming what was missing.
        """
        stmts: list = []
        while True:
            self._skip_newlines()
            t = self._peek()
            if t.type in end:
                return stmts
            if t.type is TT.EOF:
                if legacy_for:
                    return stmts
                raise ParseError(
                    f"The scroll ends before {missing}; "
                    + (f"the {opening.value} opened on line {opening.line} "
                       "was never closed" if opening else
                       "every opened block must be closed"),
                    line=t.line, col=t.col,
                )
            if t.type is TT.END and self._peek_next().type in (TT.CREATION, TT.RITE):
                if legacy_for:
                    return stmts
                raise ParseError(
                    f"Found {t.value} {self._peek_next().value} before {missing}; "
                    "every opened block must be closed in its own time",
                    line=t.line, col=t.col,
                )
            stmts.append(self._parse_statement())

    # -- top level ---------------------------------------------------------

    def _parse_creation_block(self) -> A.CreationBlock:
        b = self._expect(TT.BEGIN)
        self._expect(TT.CREATION)
        self._skip_newlines()
        stmts = self._parse_body(end={TT.END}, missing="END CREATION", opening=b)
        self._expect(TT.END)
        self._expect(TT.CREATION)
        return A.CreationBlock(statements=stmts, line=b.line, col=b.col)

    # -- statements --------------------------------------------------------

    def _parse_statement(self):
        t = self._peek()
        tt = t.type
        if tt is TT.DECLARE:
            return self._parse_declare()
        if tt is TT.BREATHE:
            return self._parse_breathe()
        if tt is TT.REVEAL:
            return self._parse_reveal()
        if tt is TT.PROPHESY:
            return self._parse_prophesy()
        if tt is TT.ASCEND:
            self._advance()
            return A.Ascend(line=t.line, col=t.col)
        if tt is TT.REFLECT:
            self._advance()
            return A.Reflect(line=t.line, col=t.col)
        if tt is TT.BLESS:
            return self._parse_named_single(TT.BLESS, A.Bless)
        if tt is TT.ANOINT:
            return self._parse_named_single(TT.ANOINT, A.Anoint)
        if tt is TT.SEAL:
            self._advance()
            return A.SealStmt(expr=self._parse_expr(), line=t.line, col=t.col)
        if tt is TT.TESTIFY:
            self._advance()
            return A.Testify(expr=self._parse_expr(), line=t.line, col=t.col)
        if tt is TT.IF:
            return self._parse_if()
        if tt is TT.FOR:
            return self._parse_for()
        if tt is TT.WHILE:
            return self._parse_while()
        if tt is TT.BREAK:
            return self._parse_break()
        if tt is TT.CONTINUE:
            return self._parse_continue()
        if tt is TT.DEFINE:
            return self._parse_define_rite()
        if tt is TT.RETURN:
            return self._parse_return()
        if tt is TT.IMPORT:
            return self._parse_import()
        if tt in _EXPR_STARTS:
            expr = self._parse_expr()
            return A.ExprStmt(expr=expr, line=t.line, col=t.col)
        raise ParseError(
            f"Unexpected {self._describe(t)}; a decree must begin with "
            "a holy word (DECLARE, IF, FOR, REVEAL, ...)",
            line=t.line, col=t.col,
        )

    def _parse_named_single(self, tt: TokenType, node_cls):
        kw = self._expect(tt)
        name = self._expect(TT.IDENT, "a name").value
        return node_cls(name=name, line=kw.line, col=kw.col)

    def _parse_declare(self) -> A.Declare:
        d = self._expect(TT.DECLARE)
        # --- v4.0: DECLARE INTENT "words..." ON rite_name ---
        # INTENT and ON are soft keywords (plain identifiers by text), so
        # `DECLARE intent AS x` keeps working: only DECLARE followed by the
        # word INTENT and then a quoted string takes the intent path.
        nxt, nxt2 = self._peek(), self._peek_next()
        if (nxt.type is TT.IDENT and nxt.value.upper() == "INTENT"
                and nxt2.type is TT.STRING):
            self._advance()  # the word INTENT
            text = self._expect(TT.STRING, "the intent in quotes").value
            on = self._peek()
            if not (on.type is TT.IDENT and on.value.upper() == "ON"):
                raise ParseError(
                    'DECLARE INTENT needs ON and a rite name, as in '
                    'DECLARE INTENT "bring peace" ON evening_blessing',
                    line=on.line, col=on.col,
                )
            self._advance()  # the word ON
            rite = self._expect(TT.IDENT, "a rite name").value
            return A.DeclareIntent(text=text, rite=rite, line=d.line, col=d.col)
        # --- end v4.0 ---
        name = self._expect(TT.IDENT, "a name to declare").value
        self._expect(TT.AS)
        items = [self._parse_expr()]
        while self._check(TT.COMMA):
            self._advance()
            items.append(self._parse_expr())
        if len(items) == 1:
            value = items[0]
        else:
            value = A.ListLiteral(items=items, line=items[0].line, col=items[0].col)
        return A.Declare(name=name, value=value, line=d.line, col=d.col)

    def _parse_breathe(self) -> A.Breathe:
        b = self._expect(TT.BREATHE)
        self._expect(TT.LIFE)
        self._expect(TT.INTO)
        name = self._expect(TT.IDENT, "a name to breathe into").value
        return A.Breathe(name=name, line=b.line, col=b.col)

    def _parse_reveal(self) -> A.Reveal:
        r = self._expect(TT.REVEAL)
        self._expect(TT.LPAREN)
        expr = self._parse_expr()
        self._expect(TT.RPAREN)
        return A.Reveal(expr=expr, line=r.line, col=r.col)

    def _parse_prophesy(self) -> A.Prophesy:
        p = self._expect(TT.PROPHESY)
        line_no = p.line
        parts: list[str] = []
        while True:
            t = self._peek()
            if t.type in (TT.NEWLINE, TT.EOF) or t.line != line_no:
                break
            parts.append(str(t.value))
            self._advance()
        return A.Prophesy(text=" ".join(parts), line=p.line, col=p.col)

    def _parse_if(self) -> A.IfStmt:
        i = self._expect(TT.IF)
        cond = self._parse_expr()
        self._expect(TT.THEN)
        if self._check(TT.NEWLINE):
            self._skip_newlines()
            then_body = self._parse_body(end={TT.ENDIF, TT.ELSE},
                                        missing="ENDIF", opening=i)
            else_body: list = []
            has_else = False
            if self._check(TT.ELSE):
                self._advance()
                has_else = True
                self._skip_newlines()
                else_body = self._parse_body(end={TT.ENDIF},
                                            missing="ENDIF", opening=i)
            self._expect(TT.ENDIF)
        else:
            then_body = [self._parse_statement()]
            else_body = []
            has_else = False
            if self._check(TT.ELSE):
                self._advance()
                has_else = True
                else_body = [self._parse_statement()]
        return A.IfStmt(cond=cond, then_body=then_body, else_body=else_body,
                        has_else=has_else, line=i.line, col=i.col)

    def _parse_for(self) -> A.ForLoop:
        f = self._expect(TT.FOR)
        var = self._expect(TT.IDENT, "a name for the traveler").value
        self._expect(TT.IN)
        iterable = self._parse_expr()
        self._loop_depth += 1
        try:
            if self._check(TT.NEWLINE):
                body = self._parse_body(end={TT.ENDFOR}, missing="ENDFOR",
                                        opening=f, legacy_for=True)
                if self._check(TT.ENDFOR):
                    self._advance()
            else:
                body = [self._parse_statement()]
        finally:
            self._loop_depth -= 1
        return A.ForLoop(var=var, iterable=iterable, body=body,
                         line=f.line, col=f.col)

    def _parse_while(self) -> A.WhileLoop:
        w = self._expect(TT.WHILE)
        cond = self._parse_expr()
        self._expect(TT.DO)
        self._loop_depth += 1
        try:
            if self._check(TT.NEWLINE):
                body = self._parse_body(end={TT.ENDWHILE}, missing="ENDWHILE",
                                        opening=w)
                self._expect(TT.ENDWHILE)
            else:
                body = [self._parse_statement()]
        finally:
            self._loop_depth -= 1
        return A.WhileLoop(cond=cond, body=body, line=w.line, col=w.col)

    def _parse_break(self) -> A.Break:
        b = self._advance()
        if self._loop_depth == 0:
            raise ParseError(
                "BREAK can only be used inside a loop. It was spoken with "
                "no cycle to release. Place it within a FOR or a WHILE.",
                line=b.line, col=b.col,
            )
        return A.Break(line=b.line, col=b.col)

    def _parse_continue(self) -> A.Continue:
        c = self._advance()
        if self._loop_depth == 0:
            raise ParseError(
                "CONTINUE can only be used inside a loop. It was spoken with "
                "no cycle to turn. Place it within a FOR or a WHILE.",
                line=c.line, col=c.col,
            )
        return A.Continue(line=c.line, col=c.col)

    def _parse_define_rite(self) -> A.DefineRite:
        d = self._expect(TT.DEFINE)
        self._expect(TT.RITE)
        name = self._expect(TT.IDENT, "a name for the rite").value
        self._expect(TT.LPAREN)
        params: list[str] = []
        if not self._check(TT.RPAREN):
            params.append(self._expect(TT.IDENT, "a parameter name").value)
            while self._check(TT.COMMA):
                self._advance()
                params.append(self._expect(TT.IDENT, "a parameter name").value)
        self._expect(TT.RPAREN)
        # A rite body is a fresh boundary: BREAK/CONTINUE inside it may only
        # answer to loops within the rite, never to a caller's loop.
        saved_depth, self._loop_depth = self._loop_depth, 0
        try:
            if self._check(TT.NEWLINE):
                self._skip_newlines()
                body = self._parse_body(end={TT.END}, missing="END RITE", opening=d)
            else:
                # inline single-statement body, e.g. DEFINE RITE f(x) SEAL x END RITE
                body = [self._parse_statement()]
                self._skip_newlines()
        finally:
            self._loop_depth = saved_depth
        self._expect(TT.END)
        self._expect(TT.RITE)
        return A.DefineRite(name=name, params=params, body=body,
                            line=d.line, col=d.col)

    def _parse_return(self) -> A.Return:
        r = self._expect(TT.RETURN)
        if self._peek().type in _RETURN_TERMINATORS:
            return A.Return(expr=None, line=r.line, col=r.col)
        return A.Return(expr=self._parse_expr(), line=r.line, col=r.col)

    def _parse_import(self) -> A.Import:
        im = self._expect(TT.IMPORT)
        path = self._expect(TT.STRING, "a scroll path in quotes").value
        return A.Import(path=path, line=im.line, col=im.col)

    # -- expressions -------------------------------------------------------

    def _parse_expr(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self._check(TT.OR):
            op = self._advance()
            right = self._parse_and()
            left = A.BinaryOp(op="or", left=left, right=right,
                              line=op.line, col=op.col)
        return left

    def _parse_and(self):
        left = self._parse_not_low()
        while self._check(TT.AND):
            op = self._advance()
            right = self._parse_not_low()
            left = A.BinaryOp(op="and", left=left, right=right,
                              line=op.line, col=op.col)
        return left

    def _parse_not_low(self):
        if self._check(TT.NOT):
            op = self._advance()
            return A.UnaryOp(op="not", operand=self._parse_not_low(),
                             line=op.line, col=op.col)
        return self._parse_comparison()

    _COMPARISON_OPS = {
        TT.EQ: "==", TT.NEQ: "!=", TT.LT: "<",
        TT.GT: ">", TT.LTE: "<=", TT.GTE: ">=",
    }

    def _parse_comparison(self):
        left = self._parse_additive()
        while True:
            t = self._peek()
            if t.type is TT.IS:
                self._advance()
                if self._check(TT.NOT):
                    self._advance()
                    op = "!="
                else:
                    op = "=="
            elif t.type in self._COMPARISON_OPS:
                self._advance()
                op = self._COMPARISON_OPS[t.type]
            else:
                break
            right = self._parse_additive()
            left = A.BinaryOp(op=op, left=left, right=right,
                              line=t.line, col=t.col)
        return left

    def _parse_additive(self):
        left = self._parse_multiplicative()
        while self._peek().type in (TT.PLUS, TT.MINUS):
            op = self._advance()
            right = self._parse_multiplicative()
            left = A.BinaryOp(op=op.value, left=left, right=right,
                              line=op.line, col=op.col)
        return left

    def _parse_multiplicative(self):
        left = self._parse_unary()
        while self._peek().type in (TT.STAR, TT.SLASH, TT.PERCENT):
            op = self._advance()
            right = self._parse_unary()
            left = A.BinaryOp(op=op.value, left=left, right=right,
                              line=op.line, col=op.col)
        return left

    def _parse_unary(self):
        t = self._peek()
        if t.type is TT.MINUS:
            self._advance()
            return A.UnaryOp(op="-", operand=self._parse_unary(),
                             line=t.line, col=t.col)
        if t.type is TT.NOT:
            self._advance()
            return A.UnaryOp(op="not", operand=self._parse_unary(),
                             line=t.line, col=t.col)
        return self._parse_postfix()

    def _parse_postfix(self):
        obj = self._parse_primary()
        while self._check(TT.LBRACKET):
            lb = self._advance()
            index = self._parse_expr()
            self._expect(TT.RBRACKET)
            obj = A.Index(obj=obj, index=index, line=lb.line, col=lb.col)
        return obj

    def _parse_primary(self):
        t = self._peek()
        tt = t.type
        if tt is TT.NUMBER:
            self._advance()
            return A.Literal(value=t.value, line=t.line, col=t.col)
        if tt is TT.STRING:
            self._advance()
            if "{" in t.value or "}}" in t.value:
                return self._parse_interpolated(t)
            return A.Literal(value=t.value, line=t.line, col=t.col)
        if tt is TT.TRUE:
            self._advance()
            return A.Literal(value=True, line=t.line, col=t.col)
        if tt is TT.FALSE:
            self._advance()
            return A.Literal(value=False, line=t.line, col=t.col)
        if tt is TT.VOID:
            self._advance()
            return A.Literal(value=None, line=t.line, col=t.col)
        if tt is TT.IDENT:
            self._advance()
            if self._check(TT.LPAREN):
                self._advance()
                args = self._parse_args()
                self._expect(TT.RPAREN)
                return A.CallExpr(callee=t.value, args=args,
                                  line=t.line, col=t.col)
            return A.Identifier(name=t.value, line=t.line, col=t.col)
        if tt is TT.INVOKE:
            self._advance()
            name = self._expect(TT.IDENT, "a rite name").value
            self._expect(TT.LPAREN)
            args = self._parse_args()
            self._expect(TT.RPAREN)
            return A.CallExpr(callee=name, args=args, line=t.line, col=t.col)
        if tt is TT.LPAREN:
            self._advance()
            expr = self._parse_expr()
            self._expect(TT.RPAREN)
            return expr
        if tt is TT.LBRACKET:
            self._advance()
            items = []
            if not self._check(TT.RBRACKET):
                items.append(self._parse_expr())
                while self._check(TT.COMMA):
                    self._advance()
                    items.append(self._parse_expr())
            self._expect(TT.RBRACKET)
            return A.ListLiteral(items=items, line=t.line, col=t.col)
        raise ParseError(
            f"Expected a value or name but found {self._describe(t)}",
            line=t.line, col=t.col,
        )

    # -- string interpolation: "grace upon {name}" ----------------------------

    def _parse_interpolated(self, tok):
        """Build an InterpolatedString from a STRING token's value.

        ``{expr}`` breathes the expression's revealed value into the string;
        ``{{`` and ``}}`` write a plain brace; a lone ``}`` stays a plain brace.
        """
        src = tok.value
        parts: list = []
        buf: list[str] = []
        i, n = 0, len(src)
        while i < n:
            ch = src[i]
            if ch == "{" and src[i + 1 : i + 2] == "{":
                buf.append("{")
                i += 2
                continue
            if ch == "}" and src[i + 1 : i + 2] == "}":
                buf.append("}")
                i += 2
                continue
            if ch == "{":
                end = self._find_interpolation_end(src, i, tok)
                inner = src[i + 1 : end]
                if not inner.strip():
                    raise ParseError(
                        "empty braces breathe nothing into the string; "
                        "place a name or an expression between '{' and '}', "
                        "or write '{{}}' for plain braces",
                        line=tok.line, col=tok.col + i,
                    )
                if buf:
                    parts.append("".join(buf))
                    buf = []
                parts.append(self._parse_braced_expr(inner, tok, i))
                i = end + 1
                continue
            buf.append(ch)
            i += 1
        if buf:
            parts.append("".join(buf))
        return A.InterpolatedString(parts=parts, source=src,
                                    line=tok.line, col=tok.col)

    @staticmethod
    def _find_interpolation_end(src: str, start: int, tok) -> int:
        """Index of the ``}`` closing the ``{`` at ``start``.

        Nested braces count toward the depth, and braces inside a quoted
        string are skipped, so ``"{greet("hi {name}")}"`` seals correctly.
        """
        depth = 0
        in_string = False
        i, n = start, len(src)
        while i < n:
            c = src[i]
            if in_string:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    in_string = False
            elif c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        raise ParseError(
            "an opening '{' breathes a blessing that was never sealed; "
            "close it with '}' or write '{{' for a plain brace",
            line=tok.line, col=tok.col + start,
        )

    def _parse_braced_expr(self, inner: str, tok, offset: int):
        """Parse the text between one pair of braces as a single expression."""
        tokens = [t for t in Lexer(inner).lex()
                  if t.type not in (TT.NEWLINE, TT.EOF)]
        tokens.append(Token(TT.EOF, "", tok.line, tok.col + offset))
        sub = Parser(tokens)
        expr = sub._parse_expr()
        if not sub._check(TT.EOF):
            raise ParseError(
                "the blessing between '{' and '}' could not be understood; "
                "only one expression may dwell there",
                line=tok.line, col=tok.col + offset,
            )
        return expr

    def _parse_args(self) -> list:
        args = []
        if not self._check(TT.RPAREN):
            args.append(self._parse_expr())
            while self._check(TT.COMMA):
                self._advance()
                args.append(self._parse_expr())
        return args
