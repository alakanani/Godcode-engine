# Agentics — machine-readable God Code (Mini-Pillar 5)

God Code speaks JSON as fluently as it speaks in tongues. The `--json`
flag on `run` and `check` emits a single machine-readable document on
stdout — no prose to scrape, no emoji to parse. It is the contract between
the engine and AI agents that generate, validate, and execute scrolls.

Implementation: `godcode/agentics.py` (payload builders, error-code
mapping, `--json` command bodies). The `run`/`check` wiring in
`godcode/cli.py` is marked `# --- agentics --json ---`.

## `godcode check --json FILE`

Lexes and parses without executing.

```jsonc
{"tool":"godcode","command":"check","file":"scroll.god","ok":false,
 "diagnostics":[{"line":3,"col":5,"code":"PARSE_ERROR","severity":"error",
                 "message":"Expected a name to declare but found 'AS'",
                 "hint":"Every scroll needs BEGIN CREATION ... END CREATION; …"}]}
```

| Field | Type | Meaning |
|---|---|---|
| `tool` | string | Always `"godcode"` |
| `command` | string | `"check"` |
| `file` | string | Path as passed on the command line |
| `ok` | boolean | `true` when the scroll is pure (no diagnostics) |
| `diagnostics` | array | Zero or more diagnostic objects |
| `diagnostics[].line` | int \| null | 1-based line of the fault, `null` if unknown |
| `diagnostics[].col` | int \| null | 1-based column, `null` when not tracked |
| `diagnostics[].code` | string | Stable machine code (see below) |
| `diagnostics[].severity` | string | `"error"` (errors only) |
| `diagnostics[].message` | string | Human-readable message, no location suffix |
| `diagnostics[].hint` | string \| null | One-line actionable suggestion, `null` if none |

Exit codes: **0** if `ok`, **1** if any diagnostic, **2** on usage errors
(argparse). Nothing but the JSON document is written to stdout; warnings
and human prose go to stderr.

## `godcode run --json FILE`

Executes the scroll, capturing everything it prints via
`contextlib.redirect_stdout` into a buffer (no dependency on capture
hooks from other pillars).

```jsonc
{"tool":"godcode","command":"run","file":"scroll.god","ok":true,
 "output":["42"],"seals":[{"block":0,"hash":"b9637bbd…"}],
 "intents":[{"rite":"evening_blessing","declared":"bring peace",
             "discerned":"Blessing of peace","confidence":0.27,"aligned":true}],
 "error":null,"stats":{"ms":1}}
```

| Field | Type | Meaning |
|---|---|---|
| `tool` | string | Always `"godcode"` |
| `command` | string | `"run"` |
| `file` | string | Path as passed on the command line |
| `ok` | boolean | `true` when the run completed without a God Code error |
| `output` | string[] | Every line printed during the run, in order — REVEAL lines plus engine notices such as `[SEAL]` and the ascension message |
| `seals` | array | Covenant blocks sealed during this run: `{"block": <index>, "hash": <sha256 hex>}` |
| `intents` | array | Intent checks recorded during this run: `{"rite", "declared", "discerned", "confidence", "aligned"}` — one entry per invocation of a rite carrying a `DECLARE INTENT` |
| `error` | object \| null | On runtime failure: `{line, col, code, severity, message, hint}` (same shape as a diagnostic, minus `hint` when none); `null` on success |
| `stats.ms` | int | Wall-clock milliseconds for lex + parse + run |

On runtime error `ok` is `false`, `output` holds the lines revealed
*before* the error, `seals` holds blocks sealed before the error, and
`error` is populated. Exit codes: **0** on success, **1** on failure,
**2** on usage errors.

`seals` is best-effort: it diffs the interpreter's bound ledger before
and after the run. If no ledger is bound or it cannot be read, `seals`
is `[]` — never an error.

`--json` composes with plain `run`/`check` and does not interfere with
other flags (e.g. the sandbox flag from the sibling pillar).

## Error codes

Chosen as a small, stable, language-agnostic vocabulary derived from the
error hierarchy in `godcode/errors.py` (which has no `GodCodeSyntaxError`
class, so the mapping is explicit rather than mechanical):

| Code | Source | Meaning |
|---|---|---|
| `LEXER_ERROR` | `LexerError` | Source could not be tokenized |
| `PARSE_ERROR` | `ParseError` | Tokens did not form a holy grammar |
| `RUNTIME_ERROR` | `GodRuntimeError` | Creation failed while being brought to life |
| `FILE_ERROR` | — | Scroll file unreadable (not an exception class) |

Any other `GodCodeError` subclass falls back to a CamelCase → UPPER_SNAKE
conversion of its class name (e.g. `FooBarError` → `FOO_BAR_ERROR`).

## The agent workflow

```
generate → check --json → fix from diagnostics → run --sandbox --json
         → inspect output / error → iterate
```

1. **Generate** a scroll.
2. **Declare the intent** of each rite with `DECLARE INTENT "words..." ON rite_name`
   (intent): say what the work is for, in plain words.
3. **Validate** with `godcode check --json`; repair every diagnostic
   (the `hint` field suggests the fix).
4. **Execute** with `godcode run --sandbox --json`; never run untrusted
   scrolls without `--sandbox`.
5. **Inspect** `output`, `error`, `seals`, and `intents`; iterate until `ok`
   is true and every intent is aligned.

## Intent & Chain: the language agents speak (shipped)

Mini-Pillar 5 made God Code legible to agents; declared intent makes agents legible
to God Code. The `run --json` report now carries an **`intents` array** —
every rite's declared intent, the intent the Spirit discerned, the
confidence, and whether they aligned — so an agent's *intent* is auditable
end to end. Three new commands complete the picture:

- **`godcode intent "words..." [--json]`** — resolve the intent behind any
  words through the Spirit Engine.
- **`godcode tools [--json]`** — six MCP-compatible tool schemas (`check`,
  `run`, `consult`, `intent`, `anchor_verify`, `ledger_verify`) for any
  agent framework that speaks the Model Context Protocol.
- **`godcode bridge`** — a JSON-RPC 2.0 server over stdio
  (`initialize`, `ping`, `tools/list`, `tools/call`) exposing those tools
  to an agent host.

Anchor receipts from `ANCHOR` can be verified after the fact with the
`anchor_verify` tool or `godcode ledger verify`, which now attests both
the covenant chain and the anchor chain. Agents do not just run God Code.
They testify in it, and the ledger remembers what they meant.
