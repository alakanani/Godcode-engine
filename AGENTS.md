# AGENTS.md — God Code, for AI agents

God Code is a small divine-flavored programming language ("scrolls", `.god`
files). This file tells an AI agent how to generate, validate, and run it
safely. Prefer these commands over scraping prose output.

## Validate first, always

```bash
godcode check --json scroll.god
```

Returns one JSON document: `{"tool":"godcode","command":"check","file":…,
"ok":true|false,"diagnostics":[{line,col,code,severity,message,hint}]}`.
Exit 0 = pure, 1 = diagnostics, 2 = usage error. Fix every diagnostic
before running. `line`/`col` are 1-based; `col` may be null.

## Execute safely

```bash
godcode run --sandbox --json scroll.god
```

Same exit-code convention. JSON shape: `{"tool","command","file","ok",
"output":[…],"seals":[{block,hash}],"error":{…}|null,"stats":{"ms":…}}`.
`output` = every line printed during the run (REVEAL lines plus engine
notices like `[SEAL]`); on runtime error it holds lines revealed *before*
the error, and `error` carries `line`/`col`/`code`/`message`. `--sandbox`
confines execution; `--json` composes with plain `run`/`check` too.

## Share scrolls

```bash
godcode scroll …          # install / publish / verify scrolls in the registry
godcode ledger verify     # verify the covenant chain
```

## Language gotchas (check these before "fixing" generated code)

- Every program needs `BEGIN CREATION` … `END CREATION`. Nothing runs outside it.
- Comments start with `#` and run to end of line.
- Comparisons use `IS` / `IS NOT` (`==`/`!=` also work). Assignment is `DECLARE x AS …`.
- Keywords are case-insensitive; canonical style is UPPER.
- Output: `REVEAL(expr)`. Input-free; there is no stdin.
- Blocks close explicitly: `ENDIF`, `ENDFOR`, `ENDWHILE`, `END RITE`.
- `SEAL(expr)` appends a tamper-evident covenant block to the ledger.
- `ANCHOR(expr [, chain])` anchors a value's hash on a chain (default
  `simulated`, a local genesis-anchored chain) and returns a receipt map
  `{chain, anchor_hash, height, timestamp, payload_hash}` — index it like
  `receipt["anchor_hash"]`; `TYPE(receipt)` is `"map"`.
- `CONSULT("question")` asks the local Spirit oracle; answers in 2-3
  sentences, works in the sandbox, never fails the run.
- `DECLARE INTENT "words..." ON rite_name` names a rite's purpose; at
  invocation the Spirit checks alignment and counsels gently on drift.
  Drift can never fail a run.
- `ASCEND` ends the run peacefully (not an error).
- An unbound name evaluates to a Symbol, it does not raise — `BREATHE LIFE INTO`
  an undeclared name *does* raise at runtime.
- Division by zero is rejected: "division by nothing is not permitted".

## Error codes (`--json`)

| Code | Meaning | Typical fix |
|---|---|---|
| `LEXER_ERROR` | bad characters / unterminated string | check quotes on the reported line |
| `PARSE_ERROR` | grammar violation | missing BEGIN/END CREATION or block closer |
| `RUNTIME_ERROR` | failed while running | DECLARE names before use; re-read the line |
| `FILE_ERROR` | scroll unreadable | check the path |

## Agent workflow

generate → `check --json` → fix from diagnostics → `run --sandbox --json`
→ inspect `output`/`error`/`intents` → iterate. Never run untrusted scrolls without
`--sandbox`. Keep the human's production checklist (provider contracts,
real credentials, Bank of Botswana sandbox submission) out of the way —
demo in sandbox mode.

## Agent tool bridge (v4.0)

Six MCP-compatible tool schemas for agent frameworks, plus a JSON-RPC
bridge over stdio:

```bash
godcode tools --json     # check, run, consult, intent, anchor_verify, ledger_verify
godcode bridge           # serve the tools to an agent host over stdio
godcode intent "words"   # resolve the intent behind words with the Spirit
godcode ledger verify    # attest the covenant chain AND the anchor chain
```

`run --json` reports now carry an `intents` array: one entry per invoked
rite carrying a `DECLARE INTENT`, with `declared`, `discerned`,
`confidence`, and `aligned`. Declare the intent of generated rites and
check `intents` for drift after each run.
