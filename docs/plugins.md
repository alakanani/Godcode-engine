# Plugins, SUMMON, and the Embedding API 🕊

Pillar 3 lets Python extend God Code — and lets Python *host* God Code.

- **Plugins** add new built-in verbs without touching the grammar.
- **SUMMON** is the foreign-function interface: `SUMMON("name.verb", args...)`.
- The **embedding API** runs scrolls from Python and captures the outcome.

## Authoring a plugin

A plugin is one Python file in a plugins directory. The interpreter scans, in
order, `./plugins`, `~/.godcode/plugins`, and the `godcode_plugins`
entry-point group (best-effort). Set `GODCODE_NO_PLUGINS=1` to skip loading.

```python
# plugins/myns.py
PLUGIN_API_VERSION = 1

def shout(text):
    return str(text).upper() + "!"

def register(interpreter):
    interpreter.register_plugin_verb("myns.shout", shout, plugin="myns")
```

The contract:

1. `PLUGIN_API_VERSION = 1` — the plugin contract version (current: `1`).
   A mismatch skips the plugin with a stderr warning.
2. `register(interpreter)` — called once per interpreter at startup. Register
   verbs with `interpreter.register_plugin_verb(name, func, plugin="myns")`:
   - `name` is namespaced by convention (`"myns.shout"`), keeping plugin verbs
     from colliding with core rites or each other.
   - `func` is plain Python, `func(*args)`. God Code values arrive already
     converted (table below); the return value is converted back.
   - A Python exception inside `func` becomes a line-numbered divine error
     automatically; divine errors you raise yourself pass through untouched.

A plugin that fails to import, lacks `register()`, or raises inside it is
skipped with a warning on stderr — it never crashes the host run.

### Value conversion

| God Code | Python | Notes |
|----------|--------|-------|
| number   | `int` / `float` | identity |
| string   | `str` | identity |
| boolean  | `bool` | identity |
| void     | `None` | identity |
| list     | `list` | recursive |
| symbol   | `Symbol` | a `str` subclass; identity |
| contract | `Contract` | opaque; identity |
| rite     | `RiteFunction` | opaque; identity |

Anything else a verb returns passes through opaquely — except tuples, which
become lists recursively. `REVEAL` renders opaque values with `str()`.

### Trust

Plugins are **trusted host code**: they run with the full power of Python, and
`SUMMON` calls into them bypass any sandbox policy *by design*. Every verb is
recorded with `trusted=True` in `interpreter.plugin_verb_info` so a future
sandbox pillar can tell plugin verbs apart from core ones. Only install plugins
from sources you trust; set `GODCODE_NO_PLUGINS=1` when running untrusted
scrolls in a locked-down environment.

### Testing a plugin

```python
from godcode import plugins
from godcode.interpreter import Interpreter

interp = Interpreter()
plugins.load_plugins(interp, dirs=["/path/to/my/plugins"])  # explicit, hermetic
interp.run_source('REVEAL(SUMMON("myns.shout", "amen"))')
assert interp.output == ["AMEN!"]
```

See `plugins/clockwork.py` for a worked example (time verbs + stopwatches).

## SUMMON reference

```
SUMMON("name.verb", arg1, arg2, ...)
```

- The first argument is the verb's namespaced name as a string. Using a string
  literal means no grammar change was needed — the parser never sees the dot.
- Remaining arguments are ordinary God Code expressions, converted to Python
  before the call; the result is converted back to a God Code value.
- Calling an unknown verb is a divine, line-numbered error listing the verbs
  that *are* available:
  `SUMMON knows no verb 'nope.nope' — the summoned are: clockwork.now, ... (line 1)`
- Wrong argument types/counts surface as divine errors naming the verb.
- `SUMMON` resolves **plugin verbs only**. Core rites (`LEN`, `REVEAL`, ...)
  are called directly; they don't need summoning.

Example with the bundled `clockwork` plugin:

```
REVEAL(SUMMON("clockwork.now"))
SUMMON("clockwork.mark", "psalm")
SUMMON("clockwork.sleep_ms", 100)
REVEAL(SUMMON("clockwork.elapsed_ms", "psalm"))
```

## Embedding API reference

```python
from godcode import run_source, run_file, RunResult

result: RunResult = run_source('REVEAL("hello, creation")\nREVEAL(40 + 2)')
assert result.ok
print(result.output)        # hello, creation\n42

result = run_file("psalms/seven_seals.god")
if not result.ok:
    print("the heavens objected:", result.error)

bad = run_source('REVEAL(1 / 0)')
print(bad.ok, bad.error)
# False  Division by nothing is not permitted — even the heavens cannot split the void. (line 1)
```

`RunResult` fields:

| Field | Meaning |
|-------|---------|
| `output: str` | Captured `REVEAL` output, lines joined with `\n` |
| `return_value` | Value of a top-level `RETURN`, else the last expression statement's value, else `None` |
| `error: str \| None` | Divine error message (with line number) when the run failed |
| `ok: bool` | Whether the run completed |

Notes:

- Output is captured per-interpreter through the interpreter's `emit` hook
  (default: `print`), so `run_source` is safe to call many times in one
  process — no global stdout redirection.
- A top-level `RETURN value` ends the run peacefully with `ok=True` and
  `return_value` set.
- Unexpected host/plugin failures outside the divine error hierarchy are also
  captured into `error` (never raised), prefixed `the outer world faltered:`.
- Embedding runs do not write the audit log; plugin auto-loading still
  applies unless `GODCODE_NO_PLUGINS=1` is set.
- To capture output with a live `Interpreter` instead, override `emit`:
  `interp.emit = my_list.append` before `interp.run_source(...)`.
