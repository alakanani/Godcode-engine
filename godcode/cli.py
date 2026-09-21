"""Command-line interface for the God Code engine.

Subcommands: run, check, repl, fmt, ledger verify.
Sibling modules (lexer, parser, ast, interpreter, ledger, errors) are imported
lazily inside each command so `--help` works even before they land.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    from godcode.errors import GodCodeError
    from godcode.interpreter import Interpreter

    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"godcode: cannot read '{args.file}': {exc.strerror or exc}",
              file=sys.stderr)
        return 1

    kwargs: dict = {}
    if args.log:
        kwargs["log_path"] = args.log
    # Bind the Spirit and the covenant ledger by default; degrade
    # gracefully if either cannot be raised in this environment.
    try:
        from godcode.spirit import SpiritEngine
        kwargs["spirit"] = SpiritEngine()
    except Exception:
        pass
    try:
        from godcode.ledger import CovenantLedger
        kwargs["ledger"] = CovenantLedger()
    except Exception:
        pass
    try:
        Interpreter(**kwargs).run_source(source, source_name=args.file)
    except GodCodeError as err:
        print(str(err), file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------
def cmd_check(args: argparse.Namespace) -> int:
    from godcode.errors import GodCodeError
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"godcode: cannot read '{args.file}': {exc.strerror or exc}",
              file=sys.stderr)
        return 1
    try:
        Parser(Lexer(source).lex()).parse()
    except GodCodeError as err:
        print(str(err), file=sys.stderr)
        return 1
    print(f"✓ {args.file} is pure.")
    return 0


# ---------------------------------------------------------------------------
# repl
# ---------------------------------------------------------------------------
def cmd_repl(args: argparse.Namespace) -> int:  # noqa: ARG001
    from godcode.errors import GodCodeError
    from godcode.interpreter import Interpreter

    try:
        import readline  # noqa: F401  (enables history + line editing)
    except ImportError:
        pass

    print("God Code Live Mode 🕊")
    print("Speak your creation; end each utterance with a blank line. "
          "(:quit to ascend)")
    interp = Interpreter(interactive=True)
    buf: list[str] = []
    while True:
        try:
            line = input("godcode> " if not buf else "...... ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break
        if line.strip() in (":quit", ":q"):
            break
        if not line.strip():
            if buf:
                chunk = "\n".join(buf)
                buf = []
                try:
                    interp.run_source(chunk, source_name="<repl>")
                except GodCodeError as err:
                    print(str(err), file=sys.stderr)
            continue
        buf.append(line)
    print("🕊 The sanctuary rests.")
    return 0


# ---------------------------------------------------------------------------
# fmt — AST -> canonical God Code
# ---------------------------------------------------------------------------
_PRECEDENCE = {
    "or": 1, "and": 2,
    "==": 3, "!=": 3, "<": 3, ">": 3, "<=": 3, ">=": 3,
    "+": 4, "-": 4, "*": 5, "/": 5, "%": 5,
}
_UNARY_PREC = 6
_BLOCK_NODES = {"CreationBlock", "IfStmt", "ForLoop", "WhileLoop", "DefineRite"}


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace('"', '\\"')
                .replace("\n", "\\n").replace("\t", "\\t"))


class CanonicalFormatter:
    """Re-emit an AST as canonical God Code: keywords UPPER, 2-space indent,
    one statement per line, blank line between top-level blocks."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._depth = 0

    # -- driver ---------------------------------------------------------
    def format(self, program) -> str:
        prev_was_block = False
        for i, stmt in enumerate(program.statements):
            is_block = type(stmt).__name__ in _BLOCK_NODES
            if i and (is_block or prev_was_block):
                self._lines.append("")
            self._emit_stmt(stmt)
            prev_was_block = is_block
        return "\n".join(self._lines) + "\n"

    def _emit_stmt(self, node) -> None:
        meth = getattr(self, "_stmt_" + type(node).__name__, None)
        if meth is None:
            raise ValueError(
                f"the formatter knows not this node: {type(node).__name__}")
        meth(node)

    def _line(self, text: str) -> None:
        self._lines.append("  " * self._depth + text)

    def _block(self, stmts) -> None:
        self._depth += 1
        for stmt in stmts:
            self._emit_stmt(stmt)
        self._depth -= 1

    # -- expressions ----------------------------------------------------
    def _expr(self, node, parent_prec: int = 0) -> str:
        kind = type(node).__name__
        if kind == "BinaryOp":
            prec = _PRECEDENCE[node.op]
            op = node.op.upper() if node.op in ("and", "or") else node.op
            text = (f"{self._expr(node.left, prec)} {op} "
                    f"{self._expr(node.right, prec + 1)}")
            return f"({text})" if prec < parent_prec else text
        if kind == "UnaryOp":
            inner = self._expr(node.operand, _UNARY_PREC)
            if type(node.operand).__name__ == "UnaryOp":
                inner = f"({inner})"
            return f"NOT {inner}" if node.op == "not" else f"-{inner}"
        if kind == "Literal":
            return self._literal(node.value)
        if kind == "Identifier":
            return node.name
        if kind == "ListLiteral":
            return "[" + ", ".join(self._expr(i) for i in node.items) + "]"
        if kind == "Index":
            return f"{self._expr(node.obj, _UNARY_PREC)}[{self._expr(node.index)}]"
        if kind == "CallExpr":
            return (f"{node.callee}("
                    + ", ".join(self._expr(a) for a in node.args) + ")")
        raise ValueError(
            f"the formatter knows not this expression: {kind}")

    @staticmethod
    def _literal(value) -> str:
        if isinstance(value, str):
            return f'"{_escape(value)}"'
        if value is True:
            return "true"
        if value is False:
            return "false"
        if value is None:
            return "void"
        return repr(value)

    # -- statements -----------------------------------------------------
    def _stmt_CreationBlock(self, node) -> None:
        self._line("BEGIN CREATION")
        self._block(node.statements)
        self._line("END CREATION")

    def _stmt_Declare(self, node) -> None:
        value = node.value
        if type(value).__name__ == "ListLiteral":
            rhs = ", ".join(self._expr(i) for i in value.items)
        else:
            rhs = self._expr(value)
        self._line(f"DECLARE {node.name} AS {rhs}")

    def _stmt_Breathe(self, node) -> None:
        self._line(f"BREATHE LIFE INTO {node.name}")

    def _stmt_Reveal(self, node) -> None:
        self._line(f"REVEAL({self._expr(node.expr)})")

    def _stmt_Prophesy(self, node) -> None:
        self._line(f"PROPHESY {node.text}".rstrip())

    def _stmt_Ascend(self, node) -> None:
        self._line("ASCEND")

    def _stmt_Reflect(self, node) -> None:
        self._line("REFLECT")

    def _stmt_Bless(self, node) -> None:
        self._line(f"BLESS {node.name}")

    def _stmt_Anoint(self, node) -> None:
        self._line(f"ANOINT {node.name}")

    def _stmt_SealStmt(self, node) -> None:
        self._line(f"SEAL {self._expr(node.expr)}")

    def _stmt_Testify(self, node) -> None:
        self._line(f"TESTIFY {self._expr(node.expr)}")

    def _stmt_IfStmt(self, node) -> None:
        self._line(f"IF {self._expr(node.cond)} THEN")
        self._block(node.then_body)
        if node.else_body:
            self._line("ELSE")
            self._block(node.else_body)
        self._line("ENDIF")

    def _stmt_ForLoop(self, node) -> None:
        self._line(f"FOR {node.var} IN {self._expr(node.iterable)}")
        self._block(node.body)
        self._line("ENDFOR")

    def _stmt_WhileLoop(self, node) -> None:
        self._line(f"WHILE {self._expr(node.cond)} DO")
        self._block(node.body)
        self._line("ENDWHILE")

    def _stmt_DefineRite(self, node) -> None:
        params = ", ".join(node.params)
        self._line(f"DEFINE RITE {node.name}({params})")
        self._block(node.body)
        self._line("END RITE")

    def _stmt_Return(self, node) -> None:
        self._line("RETURN" if node.expr is None
                   else f"RETURN {self._expr(node.expr)}")

    def _stmt_Import(self, node) -> None:
        self._line(f'IMPORT "{_escape(node.path)}"')

    def _stmt_ExprStmt(self, node) -> None:
        expr = node.expr
        if type(expr).__name__ == "CallExpr":
            args = ", ".join(self._expr(a) for a in expr.args)
            self._line(f"INVOKE {expr.callee}({args})")
        else:
            self._line(self._expr(expr))


def cmd_fmt(args: argparse.Namespace) -> int:
    from godcode.errors import GodCodeError
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    src_path = Path(args.file)
    try:
        source = src_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"godcode: cannot read '{args.file}': {exc.strerror or exc}",
              file=sys.stderr)
        return 1
    try:
        program = Parser(Lexer(source).lex()).parse()
    except GodCodeError as err:
        print(str(err), file=sys.stderr)
        return 1

    canonical = CanonicalFormatter().format(program)
    if args.in_place:
        src_path.write_text(canonical, encoding="utf-8")
    else:
        sys.stdout.write(canonical)
    return 0


# ---------------------------------------------------------------------------
# ledger verify
# ---------------------------------------------------------------------------
def cmd_ledger_verify(args: argparse.Namespace) -> int:
    from godcode.ledger import CovenantLedger

    ok, message = CovenantLedger(args.file).verify()
    print(message)
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# parser assembly
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="godcode",
        description="God Code — the language of divine computation 🕊")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Execute a God Code scroll")
    p_run.add_argument("file", help="Path to the .god scroll")
    p_run.add_argument("--log", default=None, metavar="PATH",
                       help="Audit log path (default: logs/godcode.log)")
    p_run.set_defaults(func=cmd_run)

    p_check = sub.add_parser("check",
                             help="Lex and parse a scroll without running it")
    p_check.add_argument("file", help="Path to the .god scroll")
    p_check.set_defaults(func=cmd_check)

    p_repl = sub.add_parser("repl", help="Enter the live sanctuary")
    p_repl.set_defaults(func=cmd_repl)

    p_fmt = sub.add_parser("fmt", help="Re-emit a scroll in canonical form")
    p_fmt.add_argument("file", help="Path to the .god scroll")
    p_fmt.add_argument("--in-place", "-w", dest="in_place",
                       action="store_true",
                       help="Rewrite the file instead of printing")
    p_fmt.set_defaults(func=cmd_fmt)

    p_ledger = sub.add_parser("ledger", help="Covenant ledger commands")
    ledger_sub = p_ledger.add_subparsers(dest="ledger_command", required=True)
    p_verify = ledger_sub.add_parser("verify",
                                     help="Verify the covenant chain")
    p_verify.add_argument("--file", default="covenant.chain", metavar="PATH",
                          help="Chain file (default: covenant.chain)")
    p_verify.set_defaults(func=cmd_ledger_verify)

    return parser


def main(argv=None) -> int:
    """Entry point. Returns 0 on success; raises SystemExit(code) on failure."""
    args = build_parser().parse_args(argv)
    code = args.func(args)
    if code:
        raise SystemExit(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
