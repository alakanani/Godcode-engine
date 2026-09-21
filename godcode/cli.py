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
# --- v3: agentics --json ---
def _make_interpreter(log_path):
    """Build an Interpreter the way `godcode run` always has, shared by the
    plain and --json run paths so they can never drift apart."""
    from godcode.interpreter import Interpreter

    kwargs: dict = {}
    if log_path:
        kwargs["log_path"] = log_path
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
    return Interpreter(**kwargs)
# --- end v3: agentics --json ---


def cmd_run(args: argparse.Namespace) -> int:
    from godcode.errors import GodCodeError

    # --- v3: sandbox commands ---
    if getattr(args, "sandbox", False):
        return _cmd_run_sandboxed(args)
    # --- end v3: sandbox commands ---

    # --- v3: agentics --json ---
    if getattr(args, "json", False):
        from godcode import agentics
        return agentics.cmd_run_json(args)
    # --- end v3: agentics --json ---

    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"godcode: cannot read '{args.file}': {exc.strerror or exc}",
              file=sys.stderr)
        return 1

    try:
        _make_interpreter(args.log).run_source(source, source_name=args.file)
    except GodCodeError as err:
        print(str(err), file=sys.stderr)
        return 1
    return 0


# --- v3: sandbox commands ---
def _cmd_run_sandboxed(args: argparse.Namespace) -> int:
    """Run a scroll under the strict sandbox policy.

    Spirit, covenant ledger, and the audit log stay unbound: they write
    to the host world, which the sandbox does not permit. The CLI itself
    reads the scroll file before the sandbox is entered — that read is
    the invoker's own act, not the creation's.
    """
    from godcode.errors import GodCodeError
    from godcode.sandbox import SandboxPolicy, run_sandboxed

    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        if getattr(args, "json", False):
            from godcode import agentics
            agentics.emit(agentics.run_payload(
                args.file, False, [], [],
                agentics._file_error_diagnostic(args.file, exc), 0))
        else:
            print(f"godcode: cannot read '{args.file}': {exc.strerror or exc}",
                  file=sys.stderr)
        return 1

    source_dir = str(Path(args.file).resolve().parent)
    policy = SandboxPolicy.strict(
        source_dir=source_dir,
        timeout_seconds=args.sandbox_timeout,
    )
    if getattr(args, "json", False):
        # Machine-readable report; stdout carries exactly one JSON document.
        import contextlib
        import io
        import time as _time

        from godcode import agentics

        error = None
        output: list[str] = []
        start = _time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                output = run_sandboxed(source, policy, source_name=args.file)
            except GodCodeError as err:
                error = agentics.diagnostic(err)
        ms = int((_time.perf_counter() - start) * 1000)
        agentics.emit(agentics.run_payload(
            args.file, error is None, output, [], error, ms))
        return 0 if error is None else 1
    try:
        run_sandboxed(source, policy, source_name=args.file)
    except GodCodeError as err:
        print(str(err), file=sys.stderr)
        return 1
    return 0
# --- end v3: sandbox commands ---


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------
def cmd_check(args: argparse.Namespace) -> int:
    from godcode.errors import GodCodeError
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    # --- v3: agentics --json ---
    if getattr(args, "json", False):
        from godcode import agentics
        return agentics.cmd_check_json(args)
    # --- end v3: agentics --json ---

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


# --- v3: scroll commands ---
# Pillar 2 — Scroll Registry: publish/install/info/list installable scrolls.


def _scroll_registry():
    from godcode.registry import ScrollRegistry

    return ScrollRegistry()


def cmd_scroll_list(args: argparse.Namespace) -> int:  # noqa: ARG001
    from godcode.registry import ScrollError

    try:
        rows = _scroll_registry().list_installed()
    except ScrollError as exc:
        print(f"godcode: {exc}", file=sys.stderr)
        return 1
    if not rows:
        print("No scrolls installed. "
              "Publish one with `godcode scroll publish <dir>`, "
              "then `godcode scroll install <name>`.")
        return 0
    for row in rows:
        loc = ",".join(row["locations"])
        vers = ", ".join(row["versions"])
        print(f"{row['name']} {vers} [{loc}]")
    return 0


def cmd_scroll_install(args: argparse.Namespace) -> int:
    from godcode.registry import ScrollError

    try:
        receipt = _scroll_registry().install(
            args.name, version=args.version, project=args.project)
    except ScrollError as exc:
        print(f"godcode: {exc}", file=sys.stderr)
        return 1
    where = "project-local" if args.project else "user-global"
    print(f"Installed {receipt['name']} {receipt['version']} "
          f"({where}: {receipt['manifest']['description'][:60]}...)")
    return 0


def cmd_scroll_publish(args: argparse.Namespace) -> int:
    from godcode.registry import ScrollError

    try:
        manifest = _scroll_registry().publish(args.dir)
    except ScrollError as exc:
        print(f"godcode: {exc}", file=sys.stderr)
        return 1
    print(f"Published {manifest['name']} {manifest['version']} "
          f"to the local registry.")
    return 0


def cmd_scroll_info(args: argparse.Namespace) -> int:
    from godcode.registry import ScrollError

    try:
        info = _scroll_registry().info(args.name)
    except ScrollError as exc:
        print(f"godcode: {exc}", file=sys.stderr)
        return 1
    print(f"name:        {info['name']}")
    if info["manifest"]:
        manifest = info["manifest"]
        print(f"version:     {info['latest']} (latest published)")
        print(f"author:      {manifest['author']}")
        print(f"entry:       {manifest['entry']}")
        print(f"godcode:     {manifest['godcode']}")
        print(f"description: {manifest['description']}")
    else:
        print("published:   (not in the local registry)")
    if info["published"]:
        print(f"published:   {', '.join(info['published'])}")
    if info["installed"]:
        print(f"installed:   {', '.join(info['installed'])} "
              f"(project: {', '.join(info['installed_project']) or '--'}; "
              f"user: {', '.join(info['installed_user']) or '--'})")
    else:
        print(f"installed:   (nowhere -- `godcode scroll install "
              f"{info['name']}` to receive it)")
    return 0


def _add_scroll_commands(sub) -> None:
    p_scroll = sub.add_parser("scroll", help="Scroll Registry commands")
    scroll_sub = p_scroll.add_subparsers(dest="scroll_command", required=True)

    p_list = scroll_sub.add_parser("list", help="List installed scrolls")
    p_list.set_defaults(func=cmd_scroll_list)

    p_install = scroll_sub.add_parser("install",
                                      help="Install a scroll from the registry")
    p_install.add_argument("name", help="Scroll name, e.g. json-tools")
    p_install.add_argument("--version", default=None, metavar="X.Y.Z",
                           help="Exact version (default: latest published)")
    p_install.add_argument("--project", action="store_true",
                           help="Install project-local (.godcode/scrolls/) "
                                "instead of user-global (~/.godcode/scrolls/)")
    p_install.set_defaults(func=cmd_scroll_install)

    p_publish = scroll_sub.add_parser("publish",
                                      help="Publish a scroll dir to the registry")
    p_publish.add_argument("dir", help="Directory holding scroll.toml")
    p_publish.set_defaults(func=cmd_scroll_publish)

    p_info = scroll_sub.add_parser("info",
                                   help="Show a scroll's manifest and state")
    p_info.add_argument("name", help="Scroll name")
    p_info.set_defaults(func=cmd_scroll_info)


# --- end v3: scroll commands ---

# --- v3: lsp commands ---
def cmd_lsp(args: argparse.Namespace) -> int:  # noqa: ARG001
    from godcode.lsp import serve

    return serve()
# --- end v3: lsp commands ---

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
    # --- v3: sandbox commands ---
    p_run.add_argument("--sandbox", action="store_true",
                       help="Run under the strict sandbox policy "
                            "(deny fs writes, network, subprocesses, "
                            "stdin; scroll imports limited to the "
                            "scroll's own directory and the stdlib "
                            "scrolls; time and step budgets enforced)")
    p_run.add_argument("--sandbox-timeout", type=float, default=5.0,
                       metavar="SECS",
                       help="Wall-clock grant for --sandbox runs "
                            "(default: 5.0 seconds)")
    # --- end v3: sandbox commands ---
    # --- v3: agentics --json ---
    p_run.add_argument("--json", action="store_true",
                       help="Emit a machine-readable JSON report on stdout")
    # --- end v3: agentics --json ---
    p_run.set_defaults(func=cmd_run)

    p_check = sub.add_parser("check",
                             help="Lex and parse a scroll without running it")
    p_check.add_argument("file", help="Path to the .god scroll")
    # --- v3: agentics --json ---
    p_check.add_argument("--json", action="store_true",
                         help="Emit a machine-readable JSON report on stdout")
    # --- end v3: agentics --json ---
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

    # --- v3: scroll commands ---
    _add_scroll_commands(sub)
    # --- end v3: scroll commands ---

    # --- v3: lsp commands ---
    p_lsp = sub.add_parser("lsp",
                           help="Start the language server over stdio")
    p_lsp.set_defaults(func=cmd_lsp)
    # --- end v3: lsp commands ---

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
