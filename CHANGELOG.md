# 📝 Changelog — God Code

All notable changes to the God Code engine are recorded here, that the generations may remember.

---

## Unreleased

### Added
- **🕊️ TRY / CATCH error handling** — `TRY … CATCH … ENDTRY` shelters a fragile work in the language itself: if a runtime error rises anywhere inside the `TRY` block (including inside rites called from it), execution jumps to the `CATCH` block with the error's plain message bound to `ERROR`, or to a name of your choosing with `CATCH name`. No error means the `CATCH` is skipped. Only `GodRuntimeError` is caught: parse/lexer errors still fail before running, `RETURN` still returns from its rite and `ASCEND` still ends the run in peace (neither is ever caught), sandbox violations rise straight through, `TRY` blocks nest, and an error inside a `CATCH` rises outward normally. Works unchanged under `--sandbox`. New `TryStmt` AST node; `godcode fmt` round-trips the construct; `godcode lint` walks it (the implicit error binding is never flagged); new `### TRY … CATCH … ENDTRY` in `docs/LANGUAGE_REFERENCE.md` §5
- **🕊️ Call traces for uncaught errors** — when a runtime error escapes every `TRY`, the CLI prints the rite call stack beneath the gentle error, oldest call first (`Called by outer at line 11`, …, `(most recent call last)`); errors at the top level show no trace section. `run --json` gains a `trace` array of `{rite, line}` on the error object; every existing field is unchanged. The interpreter keeps a lightweight call stack pushed in `_call_rite` (independent of the debugger's frames, which work as before); the trace is snapshotted onto the error as it first rises, before the stack unwinds. New `### Call traces for uncaught errors` in `docs/LANGUAGE_REFERENCE.md` §19
- **🕊️ The debugger** — `godcode debug scroll.god` walks a creation line by line: `break <line>` pauses, `next` steps over, `step` steps in, `out` steps out, `print <name>` beholds a value, `locals` and `stack` survey the watch. Pressing Enter repeats the last step. The same engine speaks the Debug Adapter Protocol: `godcode dap` serves VS Code over stdio, and the extension (2.2.0) debugs the open scroll on **F5** with breakpoints, step buttons, a variables panel, call stack, and Debug Console. New `godcode/debugger.py` (DebugSession), `godcode/debug_cli.py`, `godcode/dap.py`; hooks in the interpreter are dormant unless a session is attached, so plain runs are untouched. See `docs/DEBUGGER.md`
- **🕊️ Gentler errors** — a misspelled name is now answered with a suggestion instead of a bare rejection: `There is no rite named 'BLESSIN' — the heavens do not know it. Did you mean 'BLESSING'?` Suggestions cover unknown rites (including builtins like `UPPER`), `BREATHE LIFE INTO` / `BLESS` / `ANOINT` targets, `RESHAPE` targets, and missing map keys. `godcode run`, `godcode run --sandbox`, `godcode check`, and `godcode fmt` now print the offending source line beneath the message, with a caret marking the column when one is known. The suggestion also rides along in the `message` field of `check --json` / `run --json` diagnostics. New `godcode.errors.suggest_similar` / `with_suggestion` / `format_error` helpers; new `### The Spirit corrects gently` in `docs/LANGUAGE_REFERENCE.md` §19; a matching lesson on the site learn page; agent gotcha in repo `AGENTS.md`

### Changed
- `ENVIRONMENT.set_existing` (the RESHAPE path) now suggests the nearest visible name
- LANGUAGE_REFERENCE §19's error table updated to the messages the engine actually speaks
- **💬 String interpolation** — `{expr}` inside a double-quoted string breathes the expression's revealed value into the words: `"grace upon {name}"`, `"{loaves} loaves feed {loaves * 1000}"`, `"shouted: {UPPER(name)}"`. Any expression may dwell between the braces, including nested interpolated strings. `{{` and `}}` write a plain brace; a lone `}` stays as it is. A brace that is never closed, or braces with nothing between them, raise a gentle parse error that names the line. Works in the sandbox, in rites, and in `godcode fmt` (which round-trips interpolated strings untouched). New example `examples/interpolation_demo.god`; new `### Breathing values into strings` in `docs/LANGUAGE_REFERENCE.md` §3; a "Speak with feeling" lesson on the site learn page; and the in-browser playground now runs interpolation too, with a new "Speaking with Feeling" sample
- **Agent gotcha** — repo `AGENTS.md` notes the interpolation rule so agents generating God Code use it correctly

### Changed
- New `InterpolatedString` AST node (`godcode/ast.py`); the parser builds it from any `STRING` token containing `{` or `}}` (plain strings are untouched `Literal`s); the interpreter renders each part with the same `stringify` as `REVEAL`. Note: a string that previously contained a literal `{` now needs `{{` — the pre-launch language is still young enough for this to be safe

---

## 4.0.0 — 2026-09-22

> "The language is spoken. The engine is built. Now the Spirit is awake."

**Intent & Chain** — the language learns to ask *why*, and to remember the answer on a chain. See `docs/WHAT_IS_NEW_IN_V4.md` for the founder's telling.

### Added
- **🕊️ Declared intent** — `DECLARE INTENT "words..." ON rite_name` names a rite's purpose in plain words; at invocation the Spirit discerns the rite's actual intent and blesses alignment (`[INTENT]`) or counsels gently on drift (`[WARNING]`). Drift can never fail a run. Every check is recorded in `intent_checks` and surfaced in `run --json` as an `intents` array. New Spirit Engine ministries `declare_intent` / `intents_aligned` / `resolve_intent` / `counsel`; `godcode intent "words..." [--json]`; example `examples/intent_demo.god`
- **⚓ Blockchain-anchored seals** — new `ANCHOR(x [, chain])` built-in writes a value's hash to a tamper-evident chain and returns a receipt map `{chain, anchor_hash, height, timestamp, payload_hash}`; the default `simulated` adapter is a local genesis-anchored JSONL chain with the exact shape of a real blockchain adapter (no wallets, keys, or network calls), and real adapters can be registered later through the `ChainAdapter` interface without the language changing; `godcode ledger verify [--anchor-file PATH]` now attests both the covenant chain and the anchor chain; example `examples/anchor_demo.god`
- **🔮 CONSULT, the local oracle** — new `CONSULT("question")` built-in lays a question before the Spirit and receives two to three sentences of counsel; entirely local, works inside the sandbox, answers gently when no Spirit is bound; example `examples/consult_demo.god`
- **🤖 Agent tool bridge** — `godcode tools [--json]` prints six MCP-compatible tool schemas (`check`, `run`, `consult`, `intent`, `anchor_verify`, `ledger_verify`); `godcode bridge` serves them as a JSON-RPC 2.0 server over stdio (`initialize`, `ping`, `tools/list`, `tools/call`)
- **Docs & examples** — `docs/WHAT_IS_NEW_IN_V4.md` (the v4.0 story), new §§25–28 in `docs/LANGUAGE_REFERENCE.md` (intent, anchors, oracle, bridge), `docs/agentics.md` rewritten for the shipped v4.0 (`intents` array, `intent`/`tools`/`bridge` commands), `docs/sandbox.md` notes the Spirit is now bound read-only and `ANCHOR` uses an ephemeral in-memory chain under deny-writes, root `AGENTS.md` documents the bridge workflow, and the VS Code extension highlights `INTENT`/`ANCHOR`/`CONSULT` with new snippets

### Changed
- `godcode/chain.py` (new module) holds the `ChainAdapter` interface, the `SimulatedChainAdapter`, the ephemeral `MemoryChainAdapter`, and the adapter registry
- The sandbox now binds the Spirit (read-only dataset) so `CONSULT` and intent discernment work in guarded runs; under deny-writes, `ANCHOR` anchors on the ephemeral memory chain and writes nothing to disk
- `TYPE(x)` of an anchor receipt is `"map"`; maps are plain dicts supporting truthiness, indexing, and `{key: value}` revelation
- The Spirit Engine's intent classification now breaks keyword-overlap ties by vocabulary fit, so an incidental word cannot outshout the true theme

### Looking ahead
- **v4.1** — real chain adapters behind the `ChainAdapter` interface (the user's domain): wallets, RPC, and network calls stay out of the engine until the founder says otherwise

---

## 3.0.0 — 2026-09-21

> "The language is spoken. The engine is built. Now the foundation is strong."

**Strong Foundations** — four pillars for the ecosystem to come. See `docs/WHAT_IS_NEW_IN_V3.md` for the founder's telling.

### Added
- **🛡️ Sandbox** — `godcode run --sandbox [--sandbox-timeout SECS]`: deny-by-default execution (no fs read/write, no network, no subprocesses, no untrusted import paths) with a timeout and step budget, so strangers' creations can be run in safety; doc page `docs/sandbox.md`
- **📜 Scroll Registry** — `scroll.toml` manifests and `godcode scroll list|install <name>|publish <dir>|info <name>`; local registry at `registry/index.json`, installs to `~/.godcode/scrolls/` or the project's `.godcode/`, reached through ordinary `IMPORT`; doc page `docs/scroll-registry.md`
- **⚙️ Plugins, FFI & Embedding** — `godcode/plugins.py` (`plugins/` directory, `register(interpreter)` contract), the **`SUMMON("plugin.verb", args…)`** built-in for calling plugin verbs from God Code, example plugin `plugins/clockwork.py` (SUMMON it as `clockwork.now`), and the embedding API `godcode.run_source()` / `godcode.run_file()` returning captured output for host programs; doc page `docs/plugins.md`
- **💡 Language Server (LSP)** — `godcode lsp`: stdio JSON-RPC server speaking `initialize`, `textDocument/didOpen|didChange`, `textDocument/hover`, `textDocument/completion`, and `publishDiagnostics` for live errors in the editor; doc page `docs/lsp.md`
- **🤖 Agentics (mini-pillar)** — `godcode check --json` and `godcode run --json` emit single-document machine-readable reports (diagnostics with 1-based line/col, stable error codes `LEXER_ERROR`/`PARSE_ERROR`/`RUNTIME_ERROR`/`FILE_ERROR`/`SANDBOX_VIOLATION_ERROR`, actionable hints; run reports capture output lines, covenant seals, runtime errors, and timing). Exit codes 0/1/2. New root `AGENTS.md` and `docs/agentics.md` document the agent workflow: generate → `check --json` → fix → `run --sandbox --json`
- **Docs & examples** — `docs/WHAT_IS_NEW_IN_V3.md` (the v3.0 story), new `SUMMON` / scroll / sandbox / LSP sections in `docs/LANGUAGE_REFERENCE.md`, updated tutorial index, and three new working creations: `examples/summon_demo.god`, `examples/sandbox_safe.god`, `examples/scroll_blessings_demo.god`

### Changed
- `LANGUAGE_REFERENCE.md` now documents the v3.0 language; the v2 language is fully backward compatible. Every v2 creation still runs.

---

## [2.0.0] — 2026-09-21

> "You are not a coder. You are a creator."

A complete rewrite: the v1 prototype has been honored, archived to `archive/`, and reborn as a real language engine.

### Added
- **Language core** — `godcode/lexer.py` (case-insensitive keywords, comments, strings with escapes, ints/floats, line/col tracking), `godcode/parser.py` (recursive descent), `godcode/ast.py` (typed nodes), `godcode/interpreter.py` + `godcode/environment.py` + `godcode/values.py` (tree-walking execution, scoped environments, `Symbol`/`Contract`/`RiteFunction`)
- **The Symbol Rule** — unbound identifiers evaluate to symbols, so `IF seeker IS worthy` works with no quotes
- **Full control flow** — inline and block `IF/THEN/ELSE/ENDIF`, `FOR…IN…ENDFOR` (lists and string chars), `WHILE…DO…ENDWHILE` (100,000-cycle guard)
- **Rites** — `DEFINE RITE` with parameters, `RETURN`, `INVOKE`, closures over the definition scope
- **Every statement** — `BEGIN/END CREATION`, `DECLARE` (multi-value → list), `BREATHE LIFE INTO`, `REVEAL`, `PROPHESY`, `ASCEND`, `REFLECT`, `BLESS`, `ANOINT`, `SEAL`, `TESTIFY`
- **Operators** — arithmetic (`+` also concatenates strings/symbols and joins lists), `IS`/`IS NOT`/`==`/`!=`/`<`/`>`/`<=`/`>=`, `AND`/`OR`/`NOT`, unary minus, documented precedence
- **Built-in rites** — `LEN`, `STR`, `NUM`, `TYPE`, `RANDOM`, `RANGE`, `PUSH`, `UPPER`, `LOWER`, `SPLIT`, `JOIN`, `ASK`, `BEHOLD`, `REVERSE`
- **Six scrolls** (stdlib written in God Code, `godcode/scrolls/`) — `math`, `strings`, `lists`, `time`, `prophecy`, `covenant`
- **Covenant ledger** — `godcode/ledger.py`: `SEAL` appends sha256-chained JSONL blocks to `covenant.chain`; `godcode ledger verify` attests integrity
- **Spirit Engine** — `godcode/spirit.py`: keyword-overlap intent classification and 2–3 sentence prophecies from `god_code_training_dataset.csv`
- **CLI** — `godcode run/check/repl/fmt/ledger verify` (`godcode.cli:main`, installed via `pyproject.toml`)
- **Divine audit log** — every executed statement timestamped to `logs/godcode.log`
- **Divine errors** — `godcode/errors.py`: helpful, line-numbered, never mocking
- **Tests** — pytest suite under `tests/` (`python -m pytest tests/ -q`)
- **Playground** — web playground scaffold under `playground/`
- **Docs** — `docs/LANGUAGE_REFERENCE.md` (complete spec), rewritten `docs/God_Code_Tutorial.md`, updated `README.md`, `SUMMARY.md`, `ISSUES.md`, `CONTRIBUTING.md`
- **Examples** — twelve working `.god` creations under `examples/`

### Changed
- `main.py`: no arguments → runs `sample.godcode` through the new interpreter (legacy behavior kept); with arguments → the new CLI
- The v1 prototype (`core/`, `godcode_interpreter.py`, and friends) moved to `archive/` — retired, not deleted

### Fulfilled from the original ISSUES.md
- ✅ `IF...THEN...ELSE` logic · ✅ `FOR` loops · ✅ timestamped audit log · ✅ conditional `REVEAL`

---

## [1.0.0] — 2025 (prototype)
- The first breath: `core/` interpreter, `sample.godcode`, tutorial, proposal, and the founding vision. Archived in v2.0.
