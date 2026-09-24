"""Abstract syntax tree nodes for God Code v2.0.

Every node carries 1-based ``line``/``col`` of the token that opened it.
Expression fields are annotated with the ``Expr`` alias (a union of all
expression node types).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

# Filled in below once the classes exist; string form keeps runtime cheap.
Expr = Union[
    "BinaryOp", "UnaryOp", "Literal", "Identifier",
    "ListLiteral", "Index", "CallExpr",
]


# -- program structure -------------------------------------------------------

@dataclass
class Program:
    statements: list = field(default_factory=list)
    line: int = 1
    col: int = 1


@dataclass
class CreationBlock:
    statements: list = field(default_factory=list)
    line: int = 1
    col: int = 1


# -- statements --------------------------------------------------------------

@dataclass
class Declare:
    name: str
    value: Expr
    line: int = 1
    col: int = 1


@dataclass
class DeclareIntent:
    """DECLARE INTENT "words..." ON rite_name -- the v4.0 intent layer."""
    text: str
    rite: str
    line: int = 1
    col: int = 1


@dataclass
class Breathe:
    name: str
    line: int = 1
    col: int = 1


@dataclass
class Reveal:
    expr: Expr
    line: int = 1
    col: int = 1


@dataclass
class Prophesy:
    text: str
    line: int = 1
    col: int = 1


@dataclass
class Ascend:
    line: int = 1
    col: int = 1


@dataclass
class Reflect:
    line: int = 1
    col: int = 1


@dataclass
class Bless:
    name: str
    line: int = 1
    col: int = 1


@dataclass
class Anoint:
    name: str
    line: int = 1
    col: int = 1


@dataclass
class SealStmt:
    expr: Expr
    line: int = 1
    col: int = 1


@dataclass
class Testify:
    expr: Expr
    line: int = 1
    col: int = 1


@dataclass
class IfStmt:
    cond: Expr
    then_body: list = field(default_factory=list)
    else_body: list = field(default_factory=list)
    has_else: bool = False  # True when an ELSE keyword was actually written
    line: int = 1
    col: int = 1


@dataclass
class ForLoop:
    var: str
    iterable: Expr
    body: list = field(default_factory=list)
    line: int = 1
    col: int = 1


@dataclass
class WhileLoop:
    cond: Expr
    body: list = field(default_factory=list)
    line: int = 1
    col: int = 1


@dataclass
class Break:
    """BREAK: release the innermost enclosing loop at once."""
    line: int = 1
    col: int = 1


@dataclass
class Continue:
    """CONTINUE: skip to the next turn of the innermost enclosing loop."""
    line: int = 1
    col: int = 1


@dataclass
class TryStmt:
    """TRY ... CATCH [name] ... ENDTRY: in-language error handling.

    The TRY block runs first; if a runtime error (GodRuntimeError) rises,
    the error's plain message is bound to ``error_name`` and the CATCH
    block runs. ``error_name`` defaults to "ERROR" when the CATCH carries
    no name. Control-flow signals (RETURN, ASCEND) are never caught.
    """
    try_body: list = field(default_factory=list)
    catch_body: list = field(default_factory=list)
    error_name: str = "ERROR"
    line: int = 1
    col: int = 1


@dataclass
class DefineRite:
    name: str
    params: list = field(default_factory=list)  # list[str]
    body: list = field(default_factory=list)
    line: int = 1
    col: int = 1


@dataclass
class Return:
    expr: Expr | None = None
    line: int = 1
    col: int = 1


@dataclass
class Import:
    path: str
    line: int = 1
    col: int = 1


@dataclass
class ExprStmt:
    expr: Expr
    line: int = 1
    col: int = 1


# -- expressions -------------------------------------------------------------

@dataclass
class BinaryOp:
    # op: '+','-','*','/','%', '==','!=','<','>','<=','>=', 'and','or'
    op: str
    left: Expr
    right: Expr
    line: int = 1
    col: int = 1


@dataclass
class UnaryOp:
    # op: 'not', '-'
    op: str
    operand: Expr
    line: int = 1
    col: int = 1


@dataclass
class Literal:
    value: object  # int | float | str | bool | None
    line: int = 1
    col: int = 1


@dataclass
class InterpolatedString:
    """A string holding ``{expr}`` blessings: parts are literal text (str)
    or expression nodes whose revealed value is breathed into the string.
    ``source`` keeps the original string content so formatters can re-emit it.
    """

    parts: list = field(default_factory=list)  # list[str | Expr]
    source: str = ""
    line: int = 1
    col: int = 1


@dataclass
class Identifier:
    name: str
    line: int = 1
    col: int = 1


@dataclass
class ListLiteral:
    items: list = field(default_factory=list)  # list[Expr]
    line: int = 1
    col: int = 1


@dataclass
class Index:
    obj: Expr
    index: Expr
    line: int = 1
    col: int = 1


@dataclass
class CallExpr:
    callee: str
    args: list = field(default_factory=list)  # list[Expr]
    line: int = 1
    col: int = 1
