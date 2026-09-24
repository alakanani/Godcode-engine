"""Static lint pass over the God Code AST (rules GC001-GC006).

``lint_source(source, source_name)`` lexes, parses, and walks a scroll,
returning a list of ``Finding`` records. The scope model mirrors the
interpreter's real behavior:

- IF and WHILE bodies run in the *current* environment (no new scope).
- FOR bodies run in one child environment; the loop variable lives there.
- DEFINE RITE bodies run in a child environment whose parent is the
  closure environment (lexical scope at the point of definition); the
  rite name is bound in the enclosing scope, params in the child.
- DECLARE binds in the current environment, shadowing any outer binding.

Rules (stable ids, plain language):
- GC001 unused variable: a name DECLAREd (or a FOR loop variable) that is
  never referenced anywhere else. A reference inside a nested rite body
  counts as used, since closures capture; a loop variable used in its
  body counts as used.
- GC002 undefined name: an Identifier or rite call naming something never
  declared, defined, imported, or provided by a builtin.
- GC003 shadowing: a DECLARE, rite param, or FOR loop variable that reuses
  a name already visible from an outer scope.
- GC004 empty block: IF/FOR/WHILE/DEFINE RITE with zero statements in a
  body (both the IF and ELSE bodies are checked).
- GC005 unreachable code: any statement after RETURN, BREAK, or CONTINUE
  in the same block.
- GC006 re-DECLARE: the same name DECLAREd twice in the same scope. A
  re-DECLARE whose value uses the old value (the update idiom, e.g.
  DECLARE count AS count + 1) is not flagged, since that is the language's
  only way to update a variable.

Unknown AST node types are traversed generically and never raise.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import ast as A
from .lexer import Lexer
from .parser import Parser


# ---------------------------------------------------------------------------
# public records
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    line: int
    col: int
    rule: str
    message: str


# ---------------------------------------------------------------------------
# scope model
# ---------------------------------------------------------------------------

# Declaration kinds.
_DECLARE = "declare"      # DECLARE name AS ...
_RITE = "rite"           # DEFINE RITE name(...)
_PARAM = "param"          # rite parameter
_LOOP = "loop"           # FOR loop variable

# GC001 tracks these kinds (DECLAREd names and loop variables).
_GC001_KINDS = (_DECLARE, _LOOP)


@dataclass
class _Decl:
    name: str
    kind: str
    line: int
    col: int
    used: bool = False


@dataclass
class _Ref:
    """A use of a name. kind "read" may raise GC002; kind "intent" only
    marks a declaration as used (DECLARE INTENT names a rite's purpose
    without requiring the rite to exist)."""
    name: str
    line: int
    col: int
    kind: str  # "read" | "intent"


class _Scope:
    def __init__(self, parent: "_Scope | None" = None):
        self.parent = parent
        self.decls: dict[str, list[_Decl]] = {}
        self.children: list[_Scope] = []


def _interpreter():
    """Build an Interpreter the way the engine builds it, with plugins off
    so the builtin names are deterministic. This is the same source the
    task names for reading ``_builtins`` without duplicating the list."""
    from . import plugins
    from .interpreter import Interpreter

    os.environ.setdefault(plugins.DISABLE_ENV_VAR, "1")
    return Interpreter(spirit=None, ledger=None)


def _builtin_names() -> set[str]:
    """Exact builtin names (all UPPER) plus the special ``contract`` name
    the interpreter handles before builtin lookup."""
    interp = _interpreter()
    names = set(interp._builtins.keys())
    names.add("contract")
    return names


# ---------------------------------------------------------------------------
# the pass
# ---------------------------------------------------------------------------

class _Linter:
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.findings: list[Finding] = []
        self.root = _Scope()
        self.refs: list[tuple[_Scope, _Ref]] = []
        self.builtins = _builtin_names()
        self.interp = _interpreter()
        self.imported_names: set[str] = set()
        self.imports_unknown = False
        self._import_seen: set[str] = set()
        # source_dir mirrors Interpreter.run: the linted file's own dir.
        try:
            if Path(source_name).is_file():
                self.source_dir = Path(source_name).resolve().parent
            else:
                self.source_dir = Path.cwd()
        except (OSError, ValueError):
            self.source_dir = Path.cwd()
        # Import resolution mirrors Interpreter.run: relative to the
        # linted scroll's own directory.
        self.interp.source_dir = self.source_dir

    # -- scope helpers ---------------------------------------------------

    def _visible_in_outer(self, scope: _Scope, name: str) -> bool:
        env = scope.parent
        while env is not None:
            if name in env.decls:
                return True
            env = env.parent
        return False

    def _declare(self, scope: _Scope, name: str, kind: str,
                 line: int, col: int, value=None) -> _Decl:
        decl = _Decl(name=name, kind=kind, line=line, col=col)
        bucket = scope.decls.setdefault(name, [])
        if kind == _DECLARE and any(d.kind == _DECLARE for d in bucket):
            # The update idiom (DECLARE x AS <expr using x>) is the only
            # way to change a variable, so it is not a re-declaration.
            if value is None or not self._expr_mentions(value, name):
                self._finding(line, col, "GC006",
                              f"'{name}' is declared more than once in the same scope")
        elif kind in (_DECLARE, _PARAM, _LOOP) and self._visible_in_outer(scope, name):
            self._finding(line, col, "GC003",
                          f"'{name}' shadows a name already visible from an outer scope")
        bucket.append(decl)
        return decl

    def _ref(self, scope: _Scope, name: str, line: int, col: int,
             kind: str = "read") -> None:
        self.refs.append((scope, _Ref(name=name, line=line, col=col, kind=kind)))

    def _finding(self, line: int, col: int, rule: str, message: str) -> None:
        self.findings.append(Finding(line=line, col=col, rule=rule,
                                     message=message))

    # -- driver ----------------------------------------------------------

    def lint(self, program) -> list[Finding]:
        self._walk_block(program.statements, self.root)
        self._resolve_imports(program)
        self._resolve_refs()
        self._check_unused(self.root)
        self.findings.sort(key=lambda f: (f.line, f.col, f.rule))
        return self.findings

    # -- statement walking -----------------------------------------------

    def _walk_block(self, stmts: list, scope: _Scope) -> None:
        terminated_by = None  # the word that ended this block's flow
        for stmt in stmts:
            if terminated_by is not None:
                self._finding(getattr(stmt, "line", 1), getattr(stmt, "col", 1),
                              "GC005",
                              f"unreachable code after {terminated_by}")
            kind = type(stmt).__name__
            if kind in ("Return", "Break", "Continue"):
                terminated_by = {"Return": "RETURN", "Break": "BREAK",
                                 "Continue": "CONTINUE"}[kind]
            self._walk_stmt(stmt, scope)

    def _walk_stmt(self, stmt, scope: _Scope) -> None:
        kind = type(stmt).__name__
        meth = getattr(self, "_stmt_" + kind, None)
        if meth is not None:
            meth(stmt, scope)
            return
        # Unknown node: walk any statement lists and expressions it holds,
        # in the current scope. Never raise.
        self._walk_unknown(stmt, scope)

    def _walk_unknown(self, node, scope: _Scope) -> None:
        try:
            fields = vars(node)
        except TypeError:
            return
        for value in fields.values():
            if isinstance(value, str):
                continue
            if isinstance(value, list):
                for item in value:
                    if self._looks_like_stmt(item):
                        self._walk_stmt(item, scope)
                    elif self._looks_like_expr(item):
                        self._walk_expr(item, scope)
                    elif isinstance(item, list):
                        for sub in item:
                            if self._looks_like_stmt(sub):
                                self._walk_stmt(sub, scope)
                            elif self._looks_like_expr(sub):
                                self._walk_expr(sub, scope)
            elif self._looks_like_stmt(value):
                self._walk_stmt(value, scope)
            elif self._looks_like_expr(value):
                self._walk_expr(value, scope)

    @staticmethod
    def _looks_like_stmt(node) -> bool:
        return hasattr(node, "line") and hasattr(node, "col") and not isinstance(
            node, (str, bytes, int, float, bool, type(None)))

    @staticmethod
    def _looks_like_expr(node) -> bool:
        return _Linter._looks_like_stmt(node)

    # -- known statements ------------------------------------------------

    def _stmt_Program(self, node, scope: _Scope) -> None:
        self._walk_block(node.statements, scope)

    def _stmt_CreationBlock(self, node, scope: _Scope) -> None:
        # The creation block runs in the same environment: no new scope.
        self._walk_block(node.statements, scope)

    def _stmt_Declare(self, node, scope: _Scope) -> None:
        # The value is breathed in the enclosing scope, before the name
        # itself is bound (mirrors env.define(name, eval(value, env))).
        self._walk_expr(node.value, scope)
        self._declare(scope, node.name, _DECLARE, node.line, node.col,
                      value=node.value)

    def _expr_mentions(self, expr, name: str) -> bool:
        """True when the expression reads the given name anywhere inside."""
        if expr is None or isinstance(expr, str):
            return False
        kind = type(expr).__name__
        if kind == "Identifier":
            return expr.name == name
        if kind == "CallExpr":
            return expr.callee == name or any(
                self._expr_mentions(a, name) for a in expr.args)
        if kind == "BinaryOp":
            return (self._expr_mentions(expr.left, name)
                    or self._expr_mentions(expr.right, name))
        if kind == "UnaryOp":
            return self._expr_mentions(expr.operand, name)
        if kind == "InterpolatedString":
            return any(not isinstance(p, str) and self._expr_mentions(p, name)
                       for p in expr.parts)
        if kind == "ListLiteral":
            return any(self._expr_mentions(i, name) for i in expr.items)
        if kind == "Index":
            return (self._expr_mentions(expr.obj, name)
                    or self._expr_mentions(expr.index, name))
        # Unknown node types: walk their fields generically.
        try:
            fields = vars(expr)
        except TypeError:
            return False
        for v in fields.values():
            if isinstance(v, list):
                if any(self._expr_mentions(i, name) for i in v):
                    return True
            elif self._expr_mentions(v, name):
                return True
        return False

    def _stmt_DeclareIntent(self, node, scope: _Scope) -> None:
        # Names a rite's purpose; marks the rite used but never flags GC002.
        self._ref(scope, node.rite, node.line, node.col, kind="intent")

    def _stmt_Breathe(self, node, scope: _Scope) -> None:
        self._ref(scope, node.name, node.line, node.col)

    def _stmt_Reveal(self, node, scope: _Scope) -> None:
        self._walk_expr(node.expr, scope)

    def _stmt_Prophesy(self, node, scope: _Scope) -> None:  # noqa: ARG002
        return

    def _stmt_Ascend(self, node, scope: _Scope) -> None:  # noqa: ARG002
        return

    def _stmt_Reflect(self, node, scope: _Scope) -> None:  # noqa: ARG002
        return

    def _stmt_Bless(self, node, scope: _Scope) -> None:
        self._ref(scope, node.name, node.line, node.col)

    def _stmt_Anoint(self, node, scope: _Scope) -> None:
        self._ref(scope, node.name, node.line, node.col)

    def _stmt_SealStmt(self, node, scope: _Scope) -> None:
        self._walk_expr(node.expr, scope)

    def _stmt_Testify(self, node, scope: _Scope) -> None:
        self._walk_expr(node.expr, scope)

    def _stmt_IfStmt(self, node, scope: _Scope) -> None:
        self._walk_expr(node.cond, scope)
        # IF bodies run in the current environment: no new scope.
        if not node.then_body:
            self._finding(node.line, node.col, "GC004", "empty IF body")
        self._walk_block(node.then_body, scope)
        if node.has_else and not node.else_body:
            self._finding(node.line, node.col, "GC004", "empty ELSE body")
        self._walk_block(node.else_body, scope)

    def _stmt_ForLoop(self, node, scope: _Scope) -> None:
        # The iterable is breathed in the enclosing scope; the body runs in
        # one child environment holding the loop variable.
        self._walk_expr(node.iterable, scope)
        child = _Scope(parent=scope)
        scope.children.append(child)
        self._declare(child, node.var, _LOOP, node.line, node.col)
        if not node.body:
            self._finding(node.line, node.col, "GC004", "empty FOR body")
        self._walk_block(node.body, child)

    def _stmt_WhileLoop(self, node, scope: _Scope) -> None:
        self._walk_expr(node.cond, scope)
        # The body runs in the current environment: no new scope.
        if not node.body:
            self._finding(node.line, node.col, "GC004", "empty WHILE body")
        self._walk_block(node.body, scope)

    def _stmt_TryStmt(self, node, scope: _Scope) -> None:
        # TRY/CATCH bodies run in the current environment: no new scope.
        # The CATCH's error name is an implicit binding, marked used so a
        # CATCH that never reads it is not flagged as an unused variable.
        if not node.try_body:
            self._finding(node.line, node.col, "GC004", "empty TRY body")
        self._walk_block(node.try_body, scope)
        decl = self._declare(scope, node.error_name, _DECLARE,
                             node.line, node.col)
        decl.used = True
        if not node.catch_body:
            self._finding(node.line, node.col, "GC004", "empty CATCH body")
        self._walk_block(node.catch_body, scope)

    def _stmt_DefineRite(self, node, scope: _Scope) -> None:
        # The rite name is bound in the enclosing scope (so rites may call
        # themselves); the body runs in a child environment whose parent is
        # the lexical closure, holding the params.
        self._declare(scope, node.name, _RITE, node.line, node.col)
        child = _Scope(parent=scope)
        scope.children.append(child)
        for param in node.params:
            self._declare(child, param, _PARAM, node.line, node.col)
        if not node.body:
            self._finding(node.line, node.col, "GC004",
                          f"empty rite body for '{node.name}'")
        self._walk_block(node.body, child)

    def _stmt_Return(self, node, scope: _Scope) -> None:
        if node.expr is not None:
            self._walk_expr(node.expr, scope)

    def _stmt_Break(self, node, scope: _Scope) -> None:  # noqa: ARG002
        # No names are read or bound; control passes to the enclosing loop.
        return

    def _stmt_Continue(self, node, scope: _Scope) -> None:  # noqa: ARG002
        # No names are read or bound; control passes to the enclosing loop.
        return

    def _stmt_Import(self, node, scope: _Scope) -> None:  # noqa: ARG002
        # Imports are resolved after the walk (see _resolve_imports).
        return

    def _stmt_ExprStmt(self, node, scope: _Scope) -> None:
        self._walk_expr(node.expr, scope)

    # -- expression walking ----------------------------------------------

    def _walk_expr(self, expr, scope: _Scope) -> None:
        if expr is None:
            return
        kind = type(expr).__name__
        if kind == "Identifier":
            self._ref(scope, expr.name, expr.line, expr.col)
        elif kind == "CallExpr":
            self._ref(scope, expr.callee, expr.line, expr.col)
            for arg in expr.args:
                self._walk_expr(arg, scope)
        elif kind == "BinaryOp":
            self._walk_expr(expr.left, scope)
            self._walk_expr(expr.right, scope)
        elif kind == "UnaryOp":
            self._walk_expr(expr.operand, scope)
        elif kind == "Literal":
            return
        elif kind == "InterpolatedString":
            for part in expr.parts:
                if isinstance(part, str):
                    continue
                self._walk_expr(part, scope)
        elif kind == "ListLiteral":
            for item in expr.items:
                self._walk_expr(item, scope)
        elif kind == "Index":
            self._walk_expr(expr.obj, scope)
            self._walk_expr(expr.index, scope)
        else:
            # Unknown expression: walk any nested nodes generically.
            self._walk_unknown(expr, scope)

    # -- imports ----------------------------------------------------------

    def _collect_imports(self, node) -> list:
        """Every Import statement in the tree, in source order."""
        found: list = []

        def visit(n):
            if n is None or isinstance(n, str):
                return
            if type(n).__name__ == "Import":
                found.append(n)
                return
            try:
                fields = vars(n)
            except TypeError:
                return
            for value in fields.values():
                if isinstance(value, list):
                    for item in value:
                        visit(item)
                else:
                    visit(value)

        visit(node)
        return found

    def _resolve_imports(self, program) -> None:
        for stmt in self._collect_imports(program):
            path = self._resolve_one_import(stmt.path)
            if path is None:
                # Cannot resolve: skip GC002 for names rather than guessing.
                self.imports_unknown = True
                continue
            self._harvest_import(path)

    def _resolve_one_import(self, import_path: str) -> "Path | None":
        """Resolve the way Interpreter._resolve_import does."""
        try:
            return self.interp._resolve_import(import_path, None)
        except Exception:
            return None

    def _harvest_import(self, path: Path) -> None:
        """Harvest top-level (importer-visible) rite and DECLAREd names from
        an imported scroll: names bound in its root scope, since the
        interpreter runs imports in the importer's own environment."""
        key = str(path)
        if key in self._import_seen:
            return
        self._import_seen.add(key)
        try:
            source = path.read_text(encoding="utf-8")
            program = Parser(Lexer(source).lex()).parse()
        except Exception:
            self.imports_unknown = True
            return
        saved_root = self.root
        saved_refs = self.refs
        saved_findings = self.findings
        try:
            self.root = _Scope()
            self.refs = []
            self.findings = []
            self._walk_block(program.statements, self.root)
            for name, bucket in self.root.decls.items():
                if any(d.kind in (_DECLARE, _RITE) for d in bucket):
                    self.imported_names.add(name)
            # Recurse into the import's own imports, guarded by _import_seen.
            self._resolve_imports(program)
        finally:
            self.root = saved_root
            self.refs = saved_refs
            self.findings = saved_findings

    # -- reference resolution ---------------------------------------------

    def _resolve_refs(self) -> None:
        for scope, ref in self.refs:
            bucket = self._resolve(scope, ref.name)
            if bucket is not None:
                # Mark every declaration in the bucket used: a re-declared
                # name's value reads the older binding (DECLARE x AS x + 1),
                # so all of them take part in the program's life.
                for decl in bucket:
                    decl.used = True
                continue
            if ref.kind != "read":
                continue
            if ref.name in self.imported_names:
                continue
            if ref.name.upper() in self.builtins or ref.name in self.builtins:
                continue
            if self.imports_unknown:
                continue
            self._finding(ref.line, ref.col, "GC002",
                          f"undefined name '{ref.name}'")

    @staticmethod
    def _resolve(scope: _Scope, name: str) -> "list | None":
        env: "_Scope | None" = scope
        while env is not None:
            bucket = env.decls.get(name)
            if bucket:
                # The runtime's env.define overwrites, so the last
                # declaration in the innermost scope is the live one.
                return bucket
            env = env.parent
        return None

    # -- GC001 -------------------------------------------------------------

    def _check_unused(self, scope: _Scope) -> None:
        for bucket in scope.decls.values():
            for decl in bucket:
                if decl.kind in _GC001_KINDS and not decl.used:
                    self._finding(decl.line, decl.col, "GC001",
                                  f"unused variable '{decl.name}'")
        for child in scope.children:
            self._check_unused(child)


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------

def lint_source(source: str, source_name: str = "<scroll>") -> list[Finding]:
    """Lex, parse, and lint a God Code scroll.

    Raises the usual lexer/parser errors on bad source, so callers can
    report them the way ``godcode check`` does.
    """
    program = Parser(Lexer(source).lex()).parse()
    return _Linter(source_name).lint(program)


__all__ = ["Finding", "lint_source"]
