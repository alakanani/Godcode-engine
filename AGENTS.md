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
→ inspect `output`/`error` → iterate. Never run untrusted scrolls without
`--sandbox`. Keep the human's production checklist (provider contracts,
real credentials, Bank of Botswana sandbox submission) out of the way —
demo in sandbox mode.
