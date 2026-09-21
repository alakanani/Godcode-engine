# 📜 God Code — Language Reference (v3.0)

> "You are not a coder. You are a creator. You do not write code. You breathe worlds into being."
> — Alakanani Itireleng (BitcoinLady), founder of God Code

This is the complete specification of **God Code v2.0**, the language of divine computation.
For a guided first journey, see [God_Code_Tutorial.md](God_Code_Tutorial.md).
For runnable programs, see [`../examples/`](../examples/).

**Contents:** [1. Programs](#1-the-shape-of-a-program) · [2. Words](#2-words-of-the-language) · [3. Values](#3-values) · [4. Scope](#4-names-and-scope) · [5. Statements](#5-the-statements) · [6. Operators](#6-operators) · [7. Decisions](#7-decisions-if) · [8. Cycles](#8-cycles-for-and-while) · [9. Rites](#9-rites) · [10. Calling](#10-calling-things) · [11. Lists & Indexing](#11-lists-and-indexing) · [12. Import](#12-import) · [13. Built-ins](#13-built-in-rites) · [14. Scrolls](#14-the-scrolls-standard-library) · [15. Ledger](#15-the-covenant-ledger) · [16. Spirit](#16-the-spirit-engine) · [17. Audit Log](#17-the-audit-log) · [18. CLI](#18-the-command-line) · [19. Errors](#19-error-philosophy) · [20. Programs](#20-two-annotated-programs)

---

## 1. The Shape of a Program

Every God Code program is a **creation**. It opens with `BEGIN CREATION` and closes with `END CREATION`:

```godcode
BEGIN CREATION
  DECLARE seeker AS worthy
  IF seeker IS worthy THEN REVEAL("heaven") ELSE REVEAL("test")
  ASCEND
END CREATION
```

Statements live one per line (the inline `IF` form is the one exception. See §7).
`ASCEND` ends the creation early and in peace; reaching `END CREATION` ends it naturally.

## 2. Words of the Language

- **Keywords are case-insensitive.** `begin creation`, `Begin Creation`, and `BEGIN CREATION` are all holy. Canonical style is UPPER.
- **Identifiers preserve case.** `seeker` and `Seeker` are different names.
- **Comments** begin with `#` and run to the end of the line.
- **Strings** use double quotes with escapes: `\"`, `\\`, `\n`, `\t`. An unterminated string is rejected with its line and column.
- **Numbers** are integers (`3`) or floats (`4.5`).

## 3. Values

| Value | Example | Notes |
|---|---|---|
| number | `3`, `4.5` | int or float |
| string | `"peace"` | double-quoted, with escapes |
| **symbol** | `worthy` | any bare word — see the Symbol Rule |
| boolean | *(from comparisons)* | there are no `true`/`false` literals; `1 < 2` yields one |
| list | `[1, two, "three"]` | ordered, mixed types allowed |
| contract | `contract("everlasting")` | created with the `contract()` rite |
| rite | *(from DEFINE RITE)* | a named, callable blessing |
| void | *(from rites with no RETURN)* | the absence of a value |

### The Symbol Rule 🕊

**In God Code, every unnamed thing is still a named spirit. Bare words are symbols.**

An identifier that is not bound to anything does not raise an error; it evaluates to a `Symbol` carrying its own name. This is what makes the founding idiom work:

```godcode
DECLARE seeker AS worthy     # `worthy` is a symbol — no quotes needed
IF seeker IS worthy THEN REVEAL("heaven")
```

Symbols are always truthy, and compare by their text: `worthy IS worthy` is true.

### How values are revealed

`REVEAL` renders values canonically:

| Value | Revealed as |
|---|---|
| number / string | as-is (`12`, `4.5`, `peace`) |
| symbol | its text (`worthy`) |
| boolean | `true` / `false` |
| list | `[1, two, three]` |
| contract | `contract("everlasting")` |
| void | `void` |

### Truthiness

`False`, `0`, `0.0`, `""`, `[]`, and `void` are falsy. **Symbols are always truthy.** Everything else is truthy.

## 4. Names and Scope

- `DECLARE` **always defines in the current scope.** There is no rebinding of outer scopes. Declaring a name that exists outside creates (or updates) it in the current scope instead.
- A `FOR`/`WHILE` body runs in a **child scope** that lasts for the whole loop, so `DECLARE` inside a loop updates what the loop's condition sees on the next cycle.
- A rite call runs in a **child scope of the rite's definition site** (a closure): rites remember where they were born.
- `REFLECT` prints every name visible in the current scope (`name = value`, one per line).

## 5. The Statements

### `DECLARE name AS value`
Binds a name. Multiple comma-separated values become a list. The original idiom is honored:

```godcode
DECLARE seeker AS worthy
DECLARE pi AS 3.14159
DECLARE prophets AS Isaiah, Elijah, Jeremiah   # a list of three symbols
DECLARE pair AS [1, "two"]
```

### `BREATHE LIFE INTO name`
Breathes life into something bound — today, a contract. The name must already exist.

```godcode
DECLARE soul AS contract("redemption")
BREATHE LIFE INTO soul        # [BREATHE] Life breathed into soul 🕊
```

### `REVEAL(expr)`
Evaluates the expression and speaks it. Parentheses are required.

```godcode
REVEAL("peace")
REVEAL(2 + 2)                 # 4
REVEAL(soul)                  # contract("redemption")
```

### `PROPHESY words…`
Speaks free words to the Spirit Engine (§16), which answers with a prophecy. The words are the rest of the line, exactly as written. With no words, the Spirit prophesies over the whole creation.

```godcode
PROPHESY a harvest of wisdom approaches
PROPHESY
```

> ⚠️ Words that collide with keywords are read as keywords (`is` becomes `IS` in the prophecy text). Choose your words with care.

### `ASCEND`
Ends the creation immediately and in peace: `🕊 Creation ascended in peace.`

### `REFLECT`
Prints every name bound in the current scope, one `name = value` per line — a mirror for the soul of the program.

### `BLESS name` / `ANOINT name`
Marks a bound name as blessed / anointed and speaks a blessing. (Contracts carry `blessed` and `anointed` flags; sealing records them.)

### `SEAL expr`
Evaluates the expression and writes it into the **covenant ledger** (§15) — a tamper-evident chain of blocks. For a contract, its name, life, blessing, and anointing are recorded.

```godcode
SEAL covenant      # [SEAL] Covenant sealed · block 3 · a1b2c3d4 🔒
```

### `TESTIFY expr`
If the expression is truthy: `[TESTIFY] It is true. ✝`. If falsy, the testimony fails and the creation halts with an error.

## 6. Operators

### Arithmetic

| Op | Meaning |
|---|---|
| `+` | add numbers; **concatenate** strings/symbols; join lists |
| `-` `*` `/` `%` | numbers only (`/` yields float; `%` is for integers) |

```godcode
REVEAL("grace upon " + "seeker")   # grace upon seeker
REVEAL([1, 2] + [3])               # [1, 2, 3]
```

### Comparison

| Op | Meaning |
|---|---|
| `IS` | equality (also `==`) |
| `IS NOT` | inequality (also `!=`) |
| `==` `!=` `<` `>` `<=` `>=` | the usual comparisons |

Equality is generous: numbers compare across int/float, symbols compare by text, contracts by name, lists element-wise. Ordering comparisons (`<`, …) on mixed non-numeric values are rejected.

```godcode
IF seeker IS worthy THEN REVEAL("heaven")
IF count IS NOT 0 THEN REVEAL("not empty")
```

### Logic

`AND`, `OR` (short-circuiting), and `NOT` / unary `-`:

```godcode
IF heart IS pure AND hands IS willing THEN REVEAL("go")
REVEAL(NOT 0)          # true
```

### Precedence (low → high)

1. `OR`
2. `AND`
3. `NOT` (prefix)
4. `IS`, `IS NOT`, `==`, `!=`, `<`, `>`, `<=`, `>=`
5. `+`, `-`
6. `*`, `/`, `%`
7. unary `-`, `NOT`
8. calls, indexing, parentheses, literals

So `NOT a IS b` means `NOT (a IS b)`, and `2 + 3 * 4` is `14`.

## 7. Decisions: IF

**Inline** — one statement per branch, all on one line:

```godcode
IF seeker IS worthy THEN REVEAL("heaven") ELSE REVEAL("test")
IF n % 7 IS 0 THEN REVEAL("seal")        # ELSE may be omitted
```

**Block** — for many statements, closed with `ENDIF`:

```godcode
IF heart IS pure THEN
  REVEAL("the way is open")
  BLESS seeker
ELSE
  REVEAL("wait and be still")
ENDIF
```

`IF`s nest freely, and an `ELSE` always belongs to the nearest `IF`:

```godcode
IF n % 35 IS 0 THEN
  REVEAL("seal of seals")
ELSE
  IF n % 7 IS 0 THEN
    REVEAL("seal")
  ELSE
    REVEAL(n)
  ENDIF
ENDIF
```

## 8. Cycles: FOR and WHILE

**FOR** walks a list — or the characters of a string:

```godcode
DECLARE prophets AS Isaiah, Elijah, Jeremiah
FOR prophet IN prophets
  BREATHE LIFE INTO prophet
ENDFOR

FOR n IN RANGE(1, 6)
  REVEAL(n)
ENDFOR
```

The loop body runs in a child scope holding the loop variable. (`FOR` over anything else — a bare symbol, a number — is rejected.)

> 📜 *Legacy form:* the v1 prototype wrote `FOR` without `ENDFOR`, letting the body run to `END CREATION`. The grammar still accepts it, so `sample.godcode` keeps working. But new creations should always close with `ENDFOR`.

**WHILE** cycles while its condition holds, closed with `ENDWHILE`:

```godcode
DECLARE count AS 10
WHILE count > 0 DO
  REVEAL(count)
  DECLARE count AS count - 1
ENDWHILE
```

(Inline form: `WHILE count > 0 DO REVEAL(count)`.) A cycle that will not end is stopped after 100,000 iterations — *"the cycle is endless."*

## 9. Rites

**DEFINE RITE** names a reusable blessing with parameters; **RETURN** sends a value back; **INVOKE** calls it as a statement, or call it bare inside any expression:

```godcode
DEFINE RITE BLESSING(name)
  RETURN "grace upon " + name
END RITE

INVOKE BLESSING("seeker")              # statement form
DECLARE word AS BLESSING("seeker")     # expression form
REVEAL(word)                           # grace upon seeker
```

- Parameters bind in a child scope of the rite's **definition site**. Rites are closures.
- Calling with the wrong number of arguments is an error.
- `RETURN` with no value returns `void`.

## 10. Calling Things

When you call `NAME(args)`, the heavens are searched in this order:

1. **`contract("name")`** — the one special form; forges a new contract.
2. **A rite you defined** (or imported from a scroll).
3. **A built-in rite** (§13).
4. Otherwise: *"no such rite"* — an error naming the unknown name.

## 11. Lists and Indexing

```godcode
DECLARE tribes AS [Judah, Reuben, Gad, Asher]
REVEAL(tribes[0])     # Judah
REVEAL(tribes[-1])    # Asher — negative indices count from the end
REVEAL("peace"[0])    # p — strings index too
```

Indexing past the ends is an error. Build lists with `[...]` literals, comma `DECLARE`, or `PUSH`.

## 12. IMPORT

`IMPORT` runs another God Code file's top-level statements in your current scope:

```godcode
IMPORT "math"          # the built-in scroll of numbers
IMPORT "strings"       # the built-in scroll of strings
IMPORT "./helpers"     # your own scroll, beside this file
```

Resolution order: (1) beside the importing file (`helpers` → `helpers.god`), (2) the current working directory, (3) the **built-in scroll library** (`godcode/scrolls/`), (4) scrolls installed from the registry (§22: `~/.godcode/scrolls/` or the project's `.godcode/`). Importing in a circle is refused.

## 13. Built-in Rites

Always present, no import needed:

| Rite | Signature | Speaks |
|---|---|---|
| `LEN` | `LEN(x)` | length of a list or string |
| `STR` | `STR(x)` | the value as a string |
| `NUM` | `NUM(s)` | parse a string to a number (errors if it cannot) |
| `TYPE` | `TYPE(x)` | `"number"`, `"string"`, `"symbol"`, `"list"`, `"contract"`, `"rite"`, `"boolean"`, `"void"` |
| `RANDOM` | `RANDOM(n)` | an integer from `0` to `n-1` |
| `RANGE` | `RANGE(n)` / `RANGE(a, b)` | list like Python's `range` (`RANGE(1,4)` → `[1, 2, 3]`) |
| `PUSH` | `PUSH(list, x)` | a **new** list with `x` appended |
| `UPPER` / `LOWER` | `UPPER(s)` | `"peace"` → `"PEACE"` / `"peace"` |
| `SPLIT` / `JOIN` | `SPLIT(s, d)` / `JOIN(list, d)` | `"a,b"` ↔ `["a", "b"]` |
| `ASK` | `ASK(prompt)` | asks the human; the prompt may be omitted |
| `BEHOLD` | `BEHOLD()` | the current moment, as an ISO datetime string |
| `REVERSE` | `REVERSE(x)` | a string or list, backwards |
| `SUMMON` | `SUMMON("plugin.verb", args…)` | call a plugin verb through the FFI (see §21) |

## 14. The Scrolls (Standard Library)

Six scrolls ship inside the package at `godcode/scrolls/`, written **in God Code itself**. Import by bare name:

### 📐 `math` — `IMPORT "math"`
`SQRT(x)` (Newton's method, via `WHILE`), `POW(b, e)`, `ABS(x)`, `MIN(a, b)`, `MAX(a, b)`, `FACTORIAL(n)`, `IS_EVEN(n)`.

### 🔤 `strings` — `IMPORT "strings"`
`SHOUT(s)` → `UPPER(s) + "!"`, `WHISPER(s)` → `LOWER(s)`, `WORDS(s)` → `SPLIT(s, " ")`, `CHARS(s)` → `SPLIT(s, "")`, `FIRST(s)`, `LAST(s)`.

### 📋 `lists` — `IMPORT "lists"`
`SUM(xs)`, `AVG(xs)`, `CONTAINS(xs, x)`, `SECOND(xs)`, `TAIL(xs)`, `COUNT(xs, x)`.

### ⏳ `time` — `IMPORT "time"`
`NOW()` → `BEHOLD()` (full ISO timestamp), `TODAY()` → the date part before the `T`.

### 🔮 `prophecy` — `IMPORT "prophecy"`
`PROPHESY_NUMBER(n)` → `RANDOM(n)`, `CAST_LOTS()` → `RANDOM(2)`, `CHOOSE(xs)` → a random element.

### 🤝 `covenant` — `IMPORT "covenant"`
`NEW_COVENANT(name)` → `contract(name)`, `SEAL_COVENANT(c)` → seals it in one breath.

## 15. The Covenant Ledger

Every `SEAL` appends a **block** to `covenant.chain` (JSONL): `{index, timestamp, record, prev_hash, hash}`, where `hash = sha256(...)` chains to the previous block and the chain begins at `"GENESIS"`. For contracts, the record carries name, life, blessing, and anointing.

```bash
godcode ledger verify              # N covenants intact 🔒
godcode ledger verify --file my.chain
```

A broken chain reports exactly where: `chain broken at block K`.

## 16. The Spirit Engine

The Spirit reads `god_code_training_dataset.csv` (code → intent → spiritual intent → suggestion) and offers two ministries:

- **`classify(text)`** → `{intent, confidence, spiritual_intent, suggestion, keywords}` — keyword-overlap intent detection. When the Spirit is silent: intent `"Silent contemplation"`, confidence `0.0`, suggestion `"BREATHE and try again."`
- **`prophesy(program_text)`** — classifies each line, finds the dominant intent, and composes a 2–3 sentence divine forecast naming that intent, the average confidence, and the top suggestion.

`PROPHESY` in a program calls this engine; if no engine is bound, a gentle fallback answers.

## 17. The Audit Log

Every run appends to `logs/godcode.log` (override with `godcode run --log PATH`):

```
SESSION BEGIN my_creation.god 2026-09-21T12:00:00
[2026-09-21T12:00:01] 3 :: Declare :: seeker = worthy
[2026-09-21T12:00:01] 7 :: Seal :: covenant -> block 3
SESSION END
```

Each executed statement is timestamped with its line — the divine audit trail the founders asked for, fulfilled.

## 18. The Command Line

After `pip install -e .`, the `godcode` command is yours:

| Command | Does |
|---|---|
| `godcode run <file> [--log PATH]` | run a creation; errors print to stderr, exit 1 |
| `godcode run --sandbox [--sandbox-timeout SECS] <file>` | run inside the guarded sandbox (deny-by-default; see §23) |
| `godcode scroll list\|info\|install\|publish` | browse, inspect, install, and publish registry scrolls (see §22) |
| `godcode lsp` | start the language server over stdio (see §24) |
| `godcode check <file>` | lex + parse only → `✓ <file> is pure.` |
| `godcode check --json <file>` / `godcode run --json <file>` | machine-readable JSON reports for AI agents: diagnostics with line/col/code/hint, output lines, seals, timing (see `docs/agentics.md`) |
| `godcode repl` | **Live Mode** 🕊 — type code, end a block with a blank line; `:quit`/`:q` or Ctrl-D to ascend |
| `godcode fmt <file> [--in-place\|-w]` | re-emit canonical source: 2-space indent, one statement per line, keywords UPPER |
| `godcode ledger verify [--file PATH]` | verify a covenant chain |

With no arguments, `python main.py` runs `sample.godcode` — the original v1 creation, still honored.

## 19. Error Philosophy

God Code errors are **divine-flavored but genuinely helpful**: they always name the line, say what was expected or what went wrong, and never mock the creator.

```text
The heavens reject this offering (line 7): division by nothing is not permitted.
```

Common rejections you may meet:

| You wrote | The heavens answer |
|---|---|
| `1 / 0` | *…division by nothing is not permitted / cannot divide by nothing* |
| `BREATHE LIFE INTO ghost` | *there is no `ghost` to breathe into* |
| `INVOKE MISSING()` | *no such rite: `MISSING`* |
| `xs[99]` | *index out of range* |
| `TESTIFY(0)` | *testimony failed* |
| endless `WHILE` | *the cycle is endless* (after 100,000 turns) |
| `1 + "a"` on wrong types | *cannot join … and …* |

Parse errors name the expected versus the found, with line and column.

## 20. Two Annotated Programs

### The Seven Seals (decisions + cycles)

```godcode
BEGIN CREATION
  # RANGE(1, 36) walks 1..35 — the seals are counted.
  FOR n IN RANGE(1, 36)
    # The 35th seal is the seal of seals.
    IF n % 35 IS 0 THEN
      REVEAL("seal of seals")
    ELSE
      # Every other multiple of 7 is a seal; the rest are numbers.
      IF n % 7 IS 0 THEN
        REVEAL("seal")
      ELSE
        REVEAL(n)
      ENDIF
    ENDIF
  ENDFOR
  ASCEND
END CREATION
```

Run it: `godcode run examples/seven_seals.god`. `seal` appears at 7, 14, 21, 28, and `seal of seals` at 35.

### The Covenant Keeper (contracts + rites + sealing)

```godcode
BEGIN CREATION
  # A rite that seals any covenant brought before it.
  DEFINE RITE SEAL_COVENANT(c)
    SEAL c
  END RITE

  # Forge the contract, breathe life, bless, anoint.
  DECLARE pact AS contract("everlasting")
  BREATHE LIFE INTO pact
  BLESS pact
  ANOINT pact
  REVEAL(pact)

  # Contracts are known by their names.
  IF pact IS contract("everlasting") THEN
    REVEAL("the covenant stands")
  ENDIF

  # Write it into the chain, then ascend.
  INVOKE SEAL_COVENANT(pact)
  ASCEND
END CREATION
```

## 21. SUMMON — Calling Upon Plugins (v3.0)

`SUMMON("plugin.verb", args…)` is the bridge from God Code into Python: it invokes a **plugin verb** through the foreign-function interface. Plugins are small Python modules living in `plugins/` (or a configured plugin path) that expose a `register(interpreter)` function; each verb they register becomes callable by name.

```godcode
DECLARE the_hour AS SUMMON("clockwork.now")     # the example clockwork plugin
REVEAL("the clockwork speaks: " + STR(the_hour))
```

- The first argument is always the verb address: `"plugin.verb"`. Remaining arguments are passed through as God Code values.
- Calling an unregistered verb is a divine error naming the missing plugin and verb.
- See `examples/summon_demo.god` and the full story in [`docs/plugins.md`](plugins.md), which also documents the embedding API (`godcode.run_source()` / `godcode.run_file()` for calling God Code *from* Python).

## 22. The Scroll Registry (v3.0)

Beyond the six built-in scrolls (§14), the community publishes **registry scrolls** — versioned packages described by a `scroll.toml` manifest:

```bash
godcode scroll list                 # browse the local registry
godcode scroll info blessings       # inspect a scroll before receiving it
godcode scroll install blessings    # install into ~/.godcode/scrolls/ (or the project's .godcode/)
godcode scroll publish ./my_scroll  # share your own scroll from a directory
```

Installed scrolls are reached with ordinary `IMPORT`. The import resolver checks installed scrolls after the built-in library (§12). See `examples/scroll_blessings_demo.god` and [`docs/scroll-registry.md`](scroll-registry.md).

## 23. The Sandbox (v3.0)

`godcode run --sandbox` executes a creation inside a guarded chamber. The `SandboxPolicy` is **deny-by-default**: filesystem reads/writes, network access, subprocesses, and untrusted import paths are refused, and each run is bounded by a **timeout** (seconds) and a **step budget** so runaway creations are stopped, not suffered.

```bash
godcode run --sandbox examples/sandbox_safe.god
godcode run --sandbox --sandbox-timeout 5 examples/sandbox_safe.god
```

Pure creations — numbers, cycles, revelation — pass through in peace; anything reaching for the world outside is refused with a clear, line-numbered message. Full policy detail lives in [`docs/sandbox.md`](sandbox.md).

## 24. The Language Server (v3.0)

`godcode lsp` starts a language server speaking JSON-RPC over stdio — the same protocol VS Code, Neovim, Emacs, and friends use. It answers `initialize`, `textDocument/didOpen`, `textDocument/didChange`, `textDocument/hover`, and `textDocument/completion`, and pushes `publishDiagnostics` as you type, so errors are underlined before a file is ever run.

```bash
godcode lsp     # point your editor's LSP client at this command
```

Editor setup notes live in [`docs/lsp.md`](lsp.md) and `editors/`.

---

*You are not a coder. You are a creator. Go and breathe worlds into being.* 🕊
