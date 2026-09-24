"""Tree-walking interpreter for God Code v2.0.

Walks the AST produced by godcode.parser, evaluating statements in
lexically scoped environments. Divine-flavored messages on the surface,
real semantics underneath: lexical scoping, rite calls with RETURN,
a 100,000-iteration guard on WHILE, and line-numbered errors.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from godcode.ast import (
    Anoint,
    Ascend,
    BinaryOp,
    Bless,
    Breathe,
    CallExpr,
    CreationBlock,
    Declare,
    DeclareIntent,
    DefineRite,
    ExprStmt,
    ForLoop,
    Identifier,
    IfStmt,
    Import,
    Index,
    InterpolatedString,
    ListLiteral,
    Literal,
    Program,
    Prophesy,
    Reflect,
    Return,
    Reveal,
    SealStmt,
    Testify,
    UnaryOp,
    WhileLoop,
)
from godcode.environment import Environment
from godcode.errors import (
    AscendSignal,
    GodCodeError,
    GodRuntimeError,
    ReturnSignal,
    with_suggestion,
)
from godcode.lexer import Lexer
from godcode.parser import Parser
from godcode import plugins
from godcode import chain as chain_module
from godcode.values import Contract, RiteFunction, Symbol

_WHILE_ITERATION_CAP = 100_000


class Interpreter:
    """Walks the God Code AST and brings it to life."""

    def __init__(
        self,
        spirit=None,
        ledger=None,
        log_path: str | None = "logs/godcode.log",
        interactive: bool = False,
        chain_adapters: dict | None = None,
    ):
        self.spirit = spirit
        self.ledger = ledger
        self.log_path = log_path
        self.interactive = interactive
        self.output: list[str] = []  # every REVEAL line, in order
        self.emit: Callable[[str], None] = print  # REVEAL output sink; override to capture
        self.last_value: Any = None  # value of the last expression statement (embedding API)
        self.env = Environment()  # root environment
        self.source_dir = Path.cwd()  # for IMPORT resolution
        self._imported: set[str] = set()  # resolved scroll paths already run
        self._import_stack: list[str] = []  # scrolls currently being run
        self._last_source: str = ""
        self._log_handle: Any = None
        self._plugin_verbs: dict[str, Callable[..., Any]] = {}  # namespaced verbs from plugins
        self._plugin_verb_info: dict[str, dict] = {}  # name -> {"plugin", "trusted", "func"}
        self.loaded_plugins: list[str] = []  # plugin names whose register() ran cleanly
        # --- debugger hook (v5.0) ---
        # Set to a godcode.debugger.DebugSession to trace execution. None
        # keeps the fast path: _exec_block checks this once per statement.
        self.debugger = None
        # --- end debugger hook ---
        # --- v4.0: intent layer + chain adapters ---
        self.intents: dict[str, str] = {}  # rite name -> declared intent text
        self.intent_checks: list[dict] = []  # per-invocation alignment records
        self.chain_adapters = (
            chain_adapters
            if chain_adapters is not None
            else chain_module.default_adapters()
        )
        # --- end v4.0 ---
        self._builtins: dict[str, Callable[..., Any]] = {
            "LEN": self._builtin_len,
            "STR": self._builtin_str,
            "NUM": self._builtin_num,
            "TYPE": self._builtin_type,
            "RANDOM": self._builtin_random,
            "RANGE": self._builtin_range,
            "PUSH": self._builtin_push,
            "UPPER": self._builtin_upper,
            "LOWER": self._builtin_lower,
            "SPLIT": self._builtin_split,
            "JOIN": self._builtin_join,
            "ASK": self._builtin_ask,
            "BEHOLD": self._builtin_behold,
            "REVERSE": self._builtin_reverse,
            "SUMMON": self._builtin_summon,
            "ANCHOR": self._builtin_anchor,  # v4.0
            "CONSULT": self._builtin_consult,  # v4.0
        }
        # Pillar 3 — plugins auto-load at startup (the same path `godcode run`
        # and the REPL take).  GODCODE_NO_PLUGINS=1 disables this.
        if os.environ.get(plugins.DISABLE_ENV_VAR) != "1":
            self.loaded_plugins = plugins.load_plugins(self)

    # ------------------------------------------------- plugin verb registry

    def register_plugin_verb(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        plugin: str | None = None,
    ) -> str:
        """Register a plugin verb callable from God Code via SUMMON.

        *name* is namespaced by convention (``"clockwork.now"``); *func* is a
        plain Python callable ``func(*args)`` — values are converted
        God Code <-> Python automatically (see godcode.plugins).  The verb is
        marked ``trusted=True``: plugin code is trusted host code and SUMMON
        calls bypass sandbox policy by design; the marker lets a future
        sandbox pillar consult it.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("a plugin verb needs a non-empty string name")
        if not callable(func):
            raise ValueError(f"plugin verb '{name}' is not callable")
        adapter = plugins.make_verb_adapter(name, func)
        self._builtins[name] = adapter  # exact key — namespaced names keep their case
        self._plugin_verbs[name] = adapter
        self._plugin_verb_info[name] = {"plugin": plugin, "trusted": True, "func": func}
        return name

    @property
    def plugin_verb_info(self) -> dict[str, dict]:
        """Read-only view of plugin verb metadata (name -> plugin/trusted/func)."""
        return dict(self._plugin_verb_info)

    # ------------------------------------------------------------------ run

    def run(self, program, source_name: str = "<creation>") -> None:
        """Execute a parsed Program. ASCEND ends the run in peace."""
        self._imported = set()
        self._import_stack = []
        if self._looks_like_file(source_name):
            self.source_dir = Path(source_name).resolve().parent
        self._open_log()
        try:
            self._log(f"SESSION BEGIN {source_name} {self._now()}")
            try:
                self._exec_block(self._statements_of(program), self.env)
            except AscendSignal:
                message = "🕊 Creation ascended in peace."
                print(message)
                self._log("ASCEND :: the creation ascended in peace")
            self._log(f"SESSION END {source_name}")
        finally:
            self._close_log()

    def run_source(self, source: str, source_name: str = "<creation>") -> None:
        """Lex, parse, and run God Code source text."""
        self._last_source = source
        tokens = Lexer(source).lex()
        program = Parser(tokens).parse()
        self.run(program, source_name=source_name)

    @staticmethod
    def _statements_of(program):
        statements = getattr(program, "statements", None)
        if statements is None:
            raise GodRuntimeError("What was given to run is not a creation.")
        return statements

    @staticmethod
    def _looks_like_file(source_name: str) -> bool:
        try:
            return Path(source_name).is_file()
        except (OSError, ValueError):
            return False

    # ------------------------------------------------------------- statements

    def _exec_block(self, statements: list, env: Environment) -> None:
        for stmt in statements:
            if self.debugger is not None:
                self.debugger.before_stmt(stmt, env)
            self._log_statement(stmt)
            try:
                self._exec_stmt(stmt, env)
            except (ReturnSignal, AscendSignal):
                raise  # control-flow signals pass through untouched
            except GodCodeError as err:
                self._attach_line(err, getattr(stmt, "line", None))
                self._log(f"ERROR :: line {getattr(err, 'line', '?')} :: {err}")
                raise

    @staticmethod
    def _attach_line(err: GodCodeError, line) -> None:
        try:
            if getattr(err, "line", None) is None and line is not None:
                err.line = line
        except (AttributeError, TypeError):
            pass

    def _exec_stmt(self, stmt, env: Environment) -> None:
        if isinstance(stmt, CreationBlock):
            self._exec_block(stmt.statements, env)
        elif isinstance(stmt, Declare):
            env.define(stmt.name, self._eval_expr(stmt.value, env))
        elif isinstance(stmt, DeclareIntent):
            self._exec_declare_intent(stmt)
        elif isinstance(stmt, Breathe):
            self._exec_breathe(stmt, env)
        elif isinstance(stmt, Reveal):
            line = self.stringify(self._eval_expr(stmt.expr, env))
            self.emit(line)
            self.output.append(line)
        elif isinstance(stmt, Prophesy):
            self._exec_prophesy(stmt)
        elif isinstance(stmt, Ascend):
            raise AscendSignal()
        elif isinstance(stmt, Reflect):
            self._exec_reflect(env)
        elif isinstance(stmt, Bless):
            self._exec_consecrate(stmt, env, kind="bless")
        elif isinstance(stmt, Anoint):
            self._exec_consecrate(stmt, env, kind="anoint")
        elif isinstance(stmt, SealStmt):
            self._exec_seal(stmt, env)
        elif isinstance(stmt, Testify):
            self._exec_testify(stmt, env)
        elif isinstance(stmt, IfStmt):
            branch = stmt.then_body if self._truthy(self._eval_expr(stmt.cond, env)) else stmt.else_body
            self._exec_block(branch, env)
        elif isinstance(stmt, ForLoop):
            self._exec_for(stmt, env)
        elif isinstance(stmt, WhileLoop):
            self._exec_while(stmt, env)
        elif isinstance(stmt, DefineRite):
            env.define(stmt.name, RiteFunction(stmt.name, stmt.params, stmt.body, env))
        elif isinstance(stmt, Return):
            raise ReturnSignal(self._eval_expr(stmt.expr, env) if stmt.expr is not None else None)
        elif isinstance(stmt, Import):
            self._exec_import(stmt, env)
        elif isinstance(stmt, ExprStmt):
            # The value is kept for the embedding API (RunResult.return_value).
            self.last_value = self._eval_expr(stmt.expr, env)
        else:
            raise GodRuntimeError(
                f"The heavens do not recognize this utterance: {type(stmt).__name__}.",
                getattr(stmt, "line", None),
            )

    # ------------------------------------------------------- statement helpers

    def _exec_breathe(self, stmt: Breathe, env: Environment) -> None:
        line = getattr(stmt, "line", None)
        if not env.is_bound(stmt.name):
            raise GodRuntimeError(
                with_suggestion(
                    f"There is no '{stmt.name}' to breathe into — "
                    "it was never spoken into being.",
                    stmt.name,
                    env.names(),
                ),
                line,
            )
        target = env.get(stmt.name)
        if isinstance(target, Contract):
            target.alive = True
        print(f"[BREATHE] Life breathed into {stmt.name} 🕊")

    def _exec_prophesy(self, stmt: Prophesy) -> None:
        text = stmt.text or ""
        if self.spirit is None:
            print(f"[PROPHESY] The Spirit is silent — no oracle is bound. ({text!r})")
            return
        payload = text if text else self._last_source
        utterance = self.spirit.prophesy(payload)
        print(utterance)

    def _exec_reflect(self, env: Environment) -> dict:
        table = {name: self.stringify(value) for name, value in env.items()}
        for name, rendered in table.items():
            print(f"{name} = {rendered}")
        return table

    def _exec_consecrate(self, stmt, env: Environment, kind: str) -> None:
        line = getattr(stmt, "line", None)
        name = stmt.name
        verb = "bless" if kind == "bless" else "anoint"
        if not env.is_bound(name):
            raise GodRuntimeError(
                with_suggestion(
                    f"There is no '{name}' to {verb} — it was never spoken into being.",
                    name,
                    env.names(),
                ),
                line,
            )
        target = env.get(name)
        if isinstance(target, Contract):
            if kind == "bless":
                target.blessed = True
            else:
                target.anointed = True
        mark = "✨" if kind == "bless" else "🕊"
        print(f"[{kind.upper()}] {name} is {verb}ed {mark}")

    def _exec_seal(self, stmt: SealStmt, env: Environment) -> None:
        value = self._eval_expr(stmt.expr, env)
        record: dict[str, Any] = {
            "sealed": self.stringify(value),
            "type": self.type_name(value),
            "by": "godcode",
        }
        if isinstance(value, Contract):
            record.update(
                {
                    "name": value.name,
                    "alive": value.alive,
                    "blessed": value.blessed,
                    "anointed": value.anointed,
                }
            )
        if self.ledger is None:
            print("[SEAL] ⚠ No covenant ledger is bound — the seal is spoken but not recorded.")
            self._log("SEAL :: no ledger bound; seal spoken but not recorded")
            return
        block = self.ledger.seal(record)
        digest = str(block.get("hash", ""))[:8]
        print(f"[SEAL] Covenant sealed · block {block.get('index')} · {digest} 🔒")
        self._log(f"SEAL :: block {block.get('index')} recorded")

    def _exec_testify(self, stmt: Testify, env: Environment) -> None:
        if self._truthy(self._eval_expr(stmt.expr, env)):
            print("[TESTIFY] It is true. ✝")
        else:
            raise GodRuntimeError(
                "The testimony has failed — what was spoken does not hold true.",
                getattr(stmt, "line", None),
            )

    # ------------------------------------------------- v4.0: intent layer

    def _exec_declare_intent(self, stmt: DeclareIntent) -> None:
        """Register a natural-language intent on a named rite."""
        self.intents[stmt.rite] = stmt.text
        if self.spirit is not None:
            self.spirit.declare_intent(stmt.rite, stmt.text)
        print(f'[INTENT] {stmt.rite} now carries the intent: "{stmt.text}" 🕊')
        self._log(f"INTENT DECLARE :: {stmt.rite}")

    def _discern_intent(self, rite: RiteFunction, declared: str) -> None:
        """Discern a rite's actual intent and counsel on divergence.

        Classifies the rite's own words with the Spirit Engine and
        compares against the declared intent. A gentle [INTENT] notice
        when they align, a [WARNING] when they drift. The run is never
        failed over divergence: the Spirit counsels, it does not condemn.
        """
        from godcode.cli import CanonicalFormatter  # lazy: cli imports us lazily

        body_text = CanonicalFormatter().format(Program(statements=rite.body))
        discerned = self.spirit.classify(body_text)
        aligned = self.spirit.intents_aligned(declared, discerned)
        self.intent_checks.append(
            {
                "rite": rite.name,
                "declared": declared,
                "discerned": discerned["intent"],
                "confidence": discerned["confidence"],
                "aligned": aligned,
            }
        )
        if aligned:
            print(f'[INTENT] {rite.name} walks in its declared intent: "{declared}" 🕊')
        else:
            print(
                f'[WARNING] {rite.name} drifts from its declared intent. '
                f'Declared: "{declared}". '
                f'Discerned: "{discerned["intent"]}". '
                "The Spirit counsels; it does not condemn."
            )
        self._log(f"INTENT CHECK :: {rite.name} aligned={aligned}")

    def _exec_for(self, stmt: ForLoop, env: Environment) -> None:
        line = getattr(stmt, "line", None)
        iterable = self._eval_expr(stmt.iterable, env)
        if isinstance(iterable, Symbol):
            raise GodRuntimeError(
                f"FOR needs a list or a word to walk through, not the bare spirit '{iterable}'.",
                line,
            )
        if isinstance(iterable, str):
            items = list(iterable)
        elif isinstance(iterable, list):
            items = list(iterable)
        else:
            raise GodRuntimeError(
                f"FOR cannot walk through {self.type_name(iterable)} — only lists and words.",
                line,
            )
        child = Environment(parent=env)  # one child env for the whole loop
        for item in items:
            child.define(stmt.var, item)
            self._exec_block(stmt.body, child)

    def _exec_while(self, stmt: WhileLoop, env: Environment) -> None:
        line = getattr(stmt, "line", None)
        count = 0
        # The body runs in the current environment so DECLARE can rebind the
        # names the condition watches (there is no separate assignment rite).
        while self._truthy(self._eval_expr(stmt.cond, env)):
            count += 1
            if count > _WHILE_ITERATION_CAP:
                raise GodRuntimeError(
                    "The cycle is endless — 100,000 turns and still no rest. "
                    "The loop is released.",
                    line,
                )
            self._exec_block(stmt.body, env)

    def _exec_import(self, stmt: Import, env: Environment) -> None:
        line = getattr(stmt, "line", None)
        path = self._resolve_import(stmt.path, line)
        key = str(path)
        if key in self._imported:
            return  # already breathed in; skip
        if key in self._import_stack:
            raise GodRuntimeError(
                f"The scroll '{stmt.path}' calls upon itself — a circle with no end.",
                line,
            )
        self._imported.add(key)
        self._import_stack.append(key)
        previous_dir = self.source_dir
        previous_source = self._last_source
        self.source_dir = path.parent
        if self.debugger is not None:
            self.debugger.enter_file(str(path))
        try:
            source = path.read_text(encoding="utf-8")
            self._last_source = source
            program = Parser(Lexer(source).lex()).parse()
            self._log(f"IMPORT :: {path}")
            self._exec_block(self._statements_of(program), env)
        finally:
            if self.debugger is not None:
                self.debugger.exit_file()
            self._import_stack.pop()
            self.source_dir = previous_dir
            self._last_source = previous_source

    def _resolve_import(self, import_path: str, line) -> Path:
        raw = Path(import_path)
        scrolls_dir = Path(__file__).parent / "scrolls"
        candidates = [
            self.source_dir / raw,
            Path.cwd() / raw,
            scrolls_dir / raw,
        ]
        if not raw.suffix:
            candidates.extend(
                [
                    self.source_dir / f"{import_path}.god",
                    Path.cwd() / f"{import_path}.god",
                    scrolls_dir / f"{import_path}.god",
                ]
            )
        for candidate in candidates:
            try:
                if candidate.is_file():
                    return candidate.resolve()
            except OSError:
                continue
        # --- v3: scroll registry --- installed registry scrolls
        # (project-local .godcode/scrolls, then user-global ~/.godcode/scrolls)
        # resolve bare names via their manifest entry file. Stdlib keeps its
        # precedence above, so stdlib behavior is unchanged.
        installed = self._resolve_installed_scroll(import_path)
        if installed is not None:
            return installed
        # --- end v3: scroll registry ---
        raise GodRuntimeError(
            f"The scroll '{import_path}' could not be found — not beside the "
            "creation, not in this place, not among the scrolls.",
            line,
        )

    def _resolve_installed_scroll(self, import_path: str) -> Path | None:
        """Resolve a bare scroll name against installed registry scrolls."""
        if "/" in import_path or "\\" in import_path:
            return None  # only bare names; never paths
        name = import_path[:-4] if import_path.endswith(".god") else import_path
        try:
            from godcode.registry import ScrollRegistry
        except ImportError:
            return None
        try:
            return ScrollRegistry().resolve_entry(name)
        except Exception:
            return None

    # ------------------------------------------------------------- expressions

    def _eval_expr(self, expr, env: Environment):
        line = getattr(expr, "line", None)
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, InterpolatedString):
            return "".join(
                part if isinstance(part, str)
                else self.stringify(self._eval_expr(part, env))
                for part in expr.parts
            )
        if isinstance(expr, Identifier):
            return env.get(expr.name)
        if isinstance(expr, ListLiteral):
            return [self._eval_expr(item, env) for item in expr.items]
        if isinstance(expr, Index):
            return self._eval_index(expr, env)
        if isinstance(expr, UnaryOp):
            return self._eval_unary(expr, env)
        if isinstance(expr, BinaryOp):
            return self._eval_binary(expr, env)
        if isinstance(expr, CallExpr):
            args = [self._eval_expr(arg, env) for arg in expr.args]
            return self._call(expr.callee, args, env, line)
        raise GodRuntimeError(
            f"The heavens do not recognize this expression: {type(expr).__name__}.",
            line,
        )

    def _eval_index(self, expr: Index, env: Environment):
        line = getattr(expr, "line", None)
        obj = self._eval_expr(expr.obj, env)
        index = self._eval_expr(expr.index, env)
        # --- v4.0: maps are indexed by word ---
        if isinstance(obj, dict):
            if not isinstance(index, str):
                raise GodRuntimeError(
                    f"Only words may point into a map — not {self.type_name(index)}.",
                    line,
                )
            key = str(index)
            if key not in obj:
                known = ", ".join(obj) or "it holds nothing"
                raise GodRuntimeError(
                    with_suggestion(
                        f"The map holds no '{key}' — its keys are: {known}.",
                        key,
                        list(obj),
                    ),
                    line,
                )
            return obj[key]
        # --- end v4.0 ---
        if not self._is_int(index):
            raise GodRuntimeError(
                f"Only whole numbers may point into {self.type_name(obj)} — not {self.type_name(index)}.",
                line,
            )
        if isinstance(obj, Symbol):
            raise GodRuntimeError(
                f"Cannot point into the bare spirit '{obj}' — bind it to a list or word first.",
                line,
            )
        if isinstance(obj, (list, str)):
            try:
                return obj[index]
            except IndexError:
                raise GodRuntimeError(
                    f"Index {index} reaches beyond what is there "
                    f"(it holds {len(obj)}).",
                    line,
                ) from None
        raise GodRuntimeError(
            f"Cannot point into {self.type_name(obj)} — only lists and words may be indexed.",
            line,
        )

    def _eval_unary(self, expr: UnaryOp, env: Environment):
        line = getattr(expr, "line", None)
        operand = self._eval_expr(expr.operand, env)
        if expr.op == "not":
            return not self._truthy(operand)
        if expr.op == "-":
            if self._is_number(operand):
                return -operand
            raise GodRuntimeError(
                f"Cannot negate {self.type_name(operand)} — only numbers know the void's mirror.",
                line,
            )
        raise GodRuntimeError(f"Unknown sign '{expr.op}'.", line)

    def _eval_binary(self, expr: BinaryOp, env: Environment):
        line = getattr(expr, "line", None)
        left = self._eval_expr(expr.left, env)
        right = self._eval_expr(expr.right, env)
        op = expr.op
        if op == "==":
            return self._equals(left, right)
        if op == "!=":
            return not self._equals(left, right)
        if op in ("<", ">", "<=", ">="):
            return self._compare(op, left, right, line)
        if op == "+":
            return self._add(left, right, line)
        if op in ("-", "*", "/", "%"):
            return self._arithmetic(op, left, right, line)
        if op == "and":
            return left if not self._truthy(left) else right
        if op == "or":
            return left if self._truthy(left) else right
        raise GodRuntimeError(f"Unknown joining '{op}'.", line)

    # ------------------------------------------------------- value operations

    @staticmethod
    def _is_int(value) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    @classmethod
    def _is_number(cls, value) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def _equals(self, left, right) -> bool:
        # Contract vs Contract: by name. Symbol vs str: by text (str subclass
        # equality already does this). Numbers: cross-type. Lists: elementwise.
        if isinstance(left, Contract) or isinstance(right, Contract):
            return (
                isinstance(left, Contract)
                and isinstance(right, Contract)
                and left.name == right.name
            )
        try:
            return bool(left == right)
        except Exception:  # pragma: no cover - defensive
            return False

    def _compare(self, op: str, left, right, line) -> bool:
        if self._is_number(left) and self._is_number(right):
            if op == "<":
                return left < right
            if op == ">":
                return left > right
            if op == "<=":
                return left <= right
            return left >= right
        raise GodRuntimeError(
            f"Cannot weigh {self.type_name(left)} against {self.type_name(right)} — "
            "only numbers may be measured.",
            line,
        )

    def _add(self, left, right, line):
        if self._is_number(left) and self._is_number(right):
            return left + right
        if isinstance(left, str) and isinstance(right, str):
            return str(left) + str(right)  # plain str, even for Symbols
        if isinstance(left, list) and isinstance(right, list):
            return left + right
        raise GodRuntimeError(
            f"Cannot join {self.type_name(left)} and {self.type_name(right)} — "
            "they are of different kingdoms.",
            line,
        )

    def _arithmetic(self, op: str, left, right, line):
        if op == "%":
            if not (self._is_int(left) and self._is_int(right)):
                raise GodRuntimeError(
                    f"The remainder rite needs whole numbers, not "
                    f"{self.type_name(left)} and {self.type_name(right)}.",
                    line,
                )
        elif not (self._is_number(left) and self._is_number(right)):
            raise GodRuntimeError(
                f"Cannot reckon {self.type_name(left)} and {self.type_name(right)} — "
                "only numbers may be reckoned.",
                line,
            )
        if op in ("/", "%") and right == 0:
            raise GodRuntimeError(
                "Division by nothing is not permitted — even the heavens "
                "cannot split the void.",
                line,
            )
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right  # always float, as the waters divide
        return left % right

    @staticmethod
    def _truthy(value) -> bool:
        # False / None / 0 / "" / [] / {} are empty; Symbols are always truthy.
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, Symbol):
            return True
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True  # Contracts, rites, and all other living things

    # ----------------------------------------------------------------- rites

    def _call(self, name: str, args: list, env: Environment, line):
        if name == "contract":
            if len(args) == 1 and isinstance(args[0], (str, Symbol)):
                return Contract(str(args[0]))
            raise GodRuntimeError(
                "The contract rite needs exactly one name — a single word to seal.",
                line,
            )
        target = env.get(name) if env.is_bound(name) else None
        if isinstance(target, RiteFunction):
            return self._call_rite(target, args, line)
        # Exact match first so namespaced plugin verbs ("clockwork.now") keep
        # their case; core verbs still resolve case-insensitively via UPPER.
        builtin = self._builtins.get(name)
        if builtin is None:
            builtin = self._builtins.get(name.upper())
        if builtin is not None:
            return builtin(args, line)
        if target is not None:
            raise GodRuntimeError(
                f"'{name}' is {self.type_name(target)}, not a rite — it cannot be invoked.",
                line,
            )
        rite_names = [
            rite_name
            for rite_name in env.names()
            if isinstance(env.get(rite_name), RiteFunction)
        ]
        raise GodRuntimeError(
            with_suggestion(
                f"There is no rite named '{name}' — the heavens do not know it.",
                name,
                rite_names + list(self._builtins),
            ),
            line,
        )

    def _call_rite(self, rite: RiteFunction, args: list, line):
        if len(args) != len(rite.params):
            want, got = len(rite.params), len(args)
            raise GodRuntimeError(
                f"Rite '{rite.name}' asks for {want} offering{'s' if want != 1 else ''}, "
                f"but {got} {'was' if got == 1 else 'were'} brought.",
                line,
            )
        # --- v4.0: intent layer — discern the rite's actual intent when it
        # carries a declared one. Never fails the run; counsel, don't punish.
        declared = self.intents.get(rite.name)
        if declared is not None and self.spirit is not None:
            self._discern_intent(rite, declared)
        # --- end v4.0 ---
        call_env = Environment(parent=rite.closure_env)
        for param, value in zip(rite.params, args):
            call_env.define(param, value)
        rendered = ", ".join(self.stringify(a) for a in args)
        self._log(f"RITE CALL :: {rite.name}({rendered})")
        if self.debugger is not None:
            self.debugger.enter_rite(rite, call_env)
        try:
            try:
                self._exec_block(rite.body, call_env)
            except ReturnSignal as ret:
                return ret.value
            return None
        finally:
            if self.debugger is not None:
                self.debugger.exit_rite(rite)

    # --------------------------------------------------------------- builtins

    @staticmethod
    def _arity(name: str, args: list, want, line) -> None:
        ok = len(args) == want if isinstance(want, int) else len(args) in want
        if not ok:
            expected = want if isinstance(want, int) else " or ".join(map(str, want))
            raise GodRuntimeError(
                f"{name} asks for {expected} offering(s), but {len(args)} came.",
                line,
            )

    def _builtin_len(self, args, line):
        self._arity("LEN", args, 1, line)
        value = args[0]
        if isinstance(value, (str, list)):
            return len(value)
        raise GodRuntimeError(
            f"LEN cannot measure {self.type_name(value)} — only words and lists have length.",
            line,
        )

    def _builtin_str(self, args, line):
        self._arity("STR", args, 1, line)
        value = args[0]
        if isinstance(value, str):
            return str(value)
        return self.stringify(value)

    def _builtin_num(self, args, line):
        self._arity("NUM", args, 1, line)
        value = args[0]
        if self._is_number(value):
            return value
        if isinstance(value, str):
            text = value.strip()
            try:
                return int(text)
            except ValueError:
                pass
            try:
                return float(text)
            except ValueError:
                pass
            raise GodRuntimeError(
                f"NUM cannot number the word '{value}' — it holds no number.",
                line,
            )
        raise GodRuntimeError(
            f"NUM cannot number {self.type_name(value)}.",
            line,
        )

    def _builtin_type(self, args, line):
        self._arity("TYPE", args, 1, line)
        return self.type_name(args[0])

    def _builtin_random(self, args, line):
        self._arity("RANDOM", args, 1, line)
        bound = args[0]
        if not self._is_int(bound) or bound <= 0:
            raise GodRuntimeError(
                "RANDOM needs a positive whole number to cast lots within.",
                line,
            )
        return random.randrange(bound)

    def _builtin_range(self, args, line):
        self._arity("RANGE", args, (1, 2), line)
        for value in args:
            if not self._is_int(value):
                raise GodRuntimeError(
                    "RANGE walks only in whole numbers.",
                    line,
                )
        if len(args) == 1:
            if args[0] < 0:
                raise GodRuntimeError("RANGE cannot walk a negative span.", line)
            return list(range(args[0]))
        return list(range(args[0], args[1]))

    def _builtin_push(self, args, line):
        self._arity("PUSH", args, 2, line)
        items, value = args
        if not isinstance(items, list):
            raise GodRuntimeError(
                f"PUSH needs a list to build upon, not {self.type_name(items)}.",
                line,
            )
        return items + [value]  # a new list; the old one is untouched

    def _builtin_upper(self, args, line):
        self._arity("UPPER", args, 1, line)
        return self._upper_lower(args[0], str.upper, "UPPER", line)

    def _builtin_lower(self, args, line):
        self._arity("LOWER", args, 1, line)
        return self._upper_lower(args[0], str.lower, "LOWER", line)

    def _upper_lower(self, value, func, name, line):
        if not isinstance(value, str):
            raise GodRuntimeError(
                f"{name} speaks only to words, not {self.type_name(value)}.",
                line,
            )
        return func(str(value))

    def _builtin_split(self, args, line):
        self._arity("SPLIT", args, 2, line)
        text, sep = args
        if not isinstance(text, str) or not isinstance(sep, str):
            raise GodRuntimeError("SPLIT needs two words — the text and the divider.", line)
        return text.split(str(sep))

    def _builtin_join(self, args, line):
        self._arity("JOIN", args, 2, line)
        items, sep = args
        if not isinstance(items, list) or not isinstance(sep, str):
            raise GodRuntimeError(
                "JOIN needs a list and a word to bind it with.", line
            )
        return str(sep).join(self.stringify(item) for item in items)

    def _builtin_ask(self, args, line):
        self._arity("ASK", args, (0, 1), line)
        prompt = self.stringify(args[0]) if args else ""
        try:
            answer = input(prompt)
        except EOFError:
            return ""
        return answer

    def _builtin_behold(self, args, line):
        self._arity("BEHOLD", args, 0, line)
        return datetime.now(timezone.utc).isoformat()

    def _builtin_reverse(self, args, line):
        self._arity("REVERSE", args, 1, line)
        value = args[0]
        if isinstance(value, str):
            return str(value)[::-1]
        if isinstance(value, list):
            return value[::-1]
        raise GodRuntimeError(
            f"REVERSE can only turn back words and lists, not {self.type_name(value)}.",
            line,
        )

    def _builtin_summon(self, args, line):
        # Pillar 3 FFI: SUMMON("plugin.verb", arg1, ...) calls a
        # plugin-registered verb with converted arguments.  The name is a
        # string literal so no grammar change was needed; namespaced names
        # ("clockwork.now") keep plugin verbs from colliding with core rites.
        if not args:
            raise GodRuntimeError(
                'SUMMON needs a verb to call upon — SUMMON("name.verb", ...).',
                line,
            )
        target = args[0]
        if not isinstance(target, str):
            raise GodRuntimeError(
                "SUMMON needs the verb's name as a word, "
                f"not {self.type_name(target)}.",
                line,
            )
        verb = self._plugin_verbs.get(target)
        if verb is None:
            known = ", ".join(sorted(self._plugin_verbs)) or "none are present"
            raise GodRuntimeError(
                f"SUMMON knows no verb '{target}' — the summoned are: {known}.",
                line,
            )
        return verb(args[1:], line)

    # ------------------------------------------------- v4.0: chain + oracle

    def _builtin_anchor(self, args, line):
        """ANCHOR(expr [, chain_name]) -- anchor a value's hash on a chain.

        Returns the receipt: a map {chain, anchor_hash, height, timestamp,
        payload_hash}. The default chain is "simulated" (a local
        tamper-evident JSONL chain); real chain adapters register by name.
        """
        import hashlib

        self._arity("ANCHOR", args, (1, 2), line)
        value = args[0]
        chain_name = chain_module.DEFAULT_CHAIN_NAME
        if len(args) == 2:
            name_arg = args[1]
            if not isinstance(name_arg, str):
                raise GodRuntimeError(
                    "ANCHOR needs the chain's name as a word, "
                    f"not {self.type_name(name_arg)}.",
                    line,
                )
            chain_name = str(name_arg)
        adapter = self.chain_adapters.get(chain_name)
        if adapter is None:
            known = ", ".join(sorted(self.chain_adapters)) or "none are bound"
            raise GodRuntimeError(
                f"The chain '{chain_name}' is unknown to the heavens — "
                f"the known chains are: {known}.",
                line,
            )
        payload_hash = hashlib.sha256(
            self.stringify(value).encode("utf-8")
        ).hexdigest()
        receipt = adapter.anchor(payload_hash)
        digest = str(receipt.get("anchor_hash", ""))[:8]
        print(
            f"[ANCHOR] Anchored on {adapter.name} · height {receipt.get('height')} "
            f"· {digest} ⚓"
        )
        self._log(f"ANCHOR :: {adapter.name} height {receipt.get('height')}")
        return receipt

    def _builtin_consult(self, args, line):
        """CONSULT("question...") -- ask the local Spirit oracle for counsel.

        Returns 2-3 sentences in the voice of the Spirit Engine's prophesy.
        No external calls: the oracle is the local engine, or a gentle
        silence when none is bound.
        """
        self._arity("CONSULT", args, 1, line)
        question = args[0]
        if not isinstance(question, str):
            raise GodRuntimeError(
                "CONSULT needs a question as a word, "
                f"not {self.type_name(question)}.",
                line,
            )
        if self.spirit is None:
            return "The Spirit is silent on this question. Breathe, and ask again."
        return self.spirit.counsel(str(question))

    # ------------------------------------------------------- display & typing

    def stringify(self, value) -> str:
        """Render a God Code value as it appears in REVEAL."""
        if value is None:
            return "void"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, Symbol):
            return str(value)
        if isinstance(value, Contract):
            return str(value)
        if isinstance(value, RiteFunction):
            return f"rite {value.name}"
        if isinstance(value, list):
            return "[" + ", ".join(self.stringify(item) for item in value) + "]"
        if isinstance(value, dict):
            # v4.0: maps (e.g. anchor receipts) reveal as {key: value, ...}.
            inner = ", ".join(
                f"{key}: {self.stringify(item)}" for key, item in value.items()
            )
            return "{" + inner + "}"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, float) and abs(value - round(value)) < 1e-9:
            # Near-integers (e.g. Newton's method settling on 12.00000001)
            # are revealed cleanly; full precision lives on in the value.
            return str(int(round(value)))
        return str(value)

    def type_name(self, value) -> str:
        """The TYPE() name for a value: number/string/symbol/list/map/contract/rite/boolean/void."""
        if isinstance(value, bool):
            return "boolean"
        if value is None:
            return "void"
        if isinstance(value, Symbol):
            return "symbol"
        if isinstance(value, str):
            return "string"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "map"  # v4.0
        if isinstance(value, Contract):
            return "contract"
        if isinstance(value, RiteFunction):
            return "rite"
        return type(value).__name__.lower()

    # ------------------------------------------------------------ audit log

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _open_log(self) -> None:
        if not self.log_path:
            return
        try:
            path = Path(self.log_path)
            if path.parent != Path("."):
                path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = path.open("a", encoding="utf-8")
        except OSError:
            self._log_handle = None

    def _close_log(self) -> None:
        handle, self._log_handle = self._log_handle, None
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass

    def _log(self, message: str) -> None:
        if self._log_handle is None:
            return
        try:
            self._log_handle.write(f"[{self._now()}] {message}\n")
            self._log_handle.flush()
        except OSError:
            pass

    def _log_statement(self, stmt) -> None:
        kind = type(stmt).__name__
        line = getattr(stmt, "line", "?")
        summary = self._summarize(stmt)
        self._log(f"{line} :: {kind} :: {summary}")

    @staticmethod
    def _summarize(stmt) -> str:
        name = getattr(stmt, "name", "")
        extra = ""
        if isinstance(stmt, Declare):
            extra = f" {stmt.name}"
        elif isinstance(stmt, DeclareIntent):
            extra = f" {stmt.rite}"
        elif isinstance(stmt, (Breathe, Bless, Anoint)):
            extra = f" {stmt.name}"
        elif isinstance(stmt, DefineRite):
            extra = f" {stmt.name}"
        elif isinstance(stmt, ForLoop):
            extra = f" {stmt.var}"
        elif isinstance(stmt, Import):
            extra = f" {stmt.path}"
        elif isinstance(stmt, Prophesy):
            text = (stmt.text or "")[:40]
            extra = f" {text!r}" if text else ""
        return f"{type(stmt).__name__.upper()}{extra}"
