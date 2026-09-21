# God Code Plugins 🕊

Drop a Python file here and its verbs become callable from God Code through
`SUMMON`. Each file is a **plugin**: trusted host code that extends the
language without touching the grammar.

## The contract

A plugin is a plain Python module exposing:

```python
PLUGIN_API_VERSION = 1

def register(interpreter):
    interpreter.register_plugin_verb("myns.myverb", myverb, plugin="myns")
```

- `PLUGIN_API_VERSION` — the plugin contract version this file speaks (current: `1`).
- `register(interpreter)` — called once per interpreter at startup. Add verbs with
  `interpreter.register_plugin_verb(name, func, plugin="myns")`.
  - `name` is namespaced by convention: `"myns.myverb"`.
  - `func` is a plain Python callable `func(*args)` — God Code values arrive as
    Python values (see the conversion table below) and whatever `func` returns
    is converted back.
  - Exceptions from `func` become line-numbered divine errors automatically.

From God Code, call it with `SUMMON`:

```
REVEAL(SUMMON("myns.myverb", 40, 2))
```

## Where plugins live

The interpreter scans, in order:

1. `./plugins` — beside where you run `godcode`
2. `~/.godcode/plugins` — your personal plugins

Plus the `godcode_plugins` entry-point group for installed distributions
(best-effort). Files starting with `_` or `.` (and `__init__.py`) are ignored;
later sources shadow earlier ones on name clashes.

A plugin that fails to import, speaks the wrong `PLUGIN_API_VERSION`, lacks
`register()`, or raises inside `register()` is skipped with a warning on
stderr — it never crashes the host run.

Set `GODCODE_NO_PLUGINS=1` to disable plugin loading entirely.

## Value conversion

| God Code  | Python              |
|-----------|---------------------|
| number    | `int` / `float`     |
| string    | `str`               |
| boolean   | `bool`              |
| void      | `None`              |
| list      | `list` (recursive)  |
| symbol    | `Symbol` (a `str` subclass) |
| contract  | `Contract` (opaque) |
| rite      | `RiteFunction` (opaque) |

Anything else a verb returns (tuples become lists recursively; dicts, sets,
custom objects pass through opaquely) is rendered with `str()` by `REVEAL`.

## Trust

Plugins run with the full power of Python and `SUMMON` calls bypass any
sandbox policy **by design**. Every verb is recorded with `trusted=True`
(`interpreter.plugin_verb_info`) so future policy can tell plugin verbs apart.
Only install plugins from sources you trust.

## Testing a plugin

```python
from godcode import plugins
from godcode.interpreter import Interpreter

interp = Interpreter()  # or load explicitly:
plugins.load_plugins(interp, dirs=["/path/to/my/plugins"])
interp.run_source('REVEAL(SUMMON("myns.myverb", 1))')
assert interp.output == ["..."]
```

See `docs/plugins.md` for the full authoring guide and `plugins/clockwork.py`
for a worked example.
