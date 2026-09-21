# 📝 Changelog — God Code

All notable changes to the God Code engine are recorded here, that the generations may remember.

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

### Looking ahead
- **v4.0 — Intent & Chain: the language agents speak.** The agentics mini-pillar made God Code legible to agents; v4.0 will make agents legible to God Code. Every agent action — a generated scroll, a fix applied from a diagnostic, an execution — becomes a sealed covenant on the ledger, hash-chained and timestamped, so an agent's *intent* is auditable end to end. The covenant chain graduates from a local JSONL file to a blockchain-anchored record: each sealed block carries a proof that can be verified without trusting the machine that ran it. Agents will not just run God Code. They will testify in it, and the ledger will remember what they meant.

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
