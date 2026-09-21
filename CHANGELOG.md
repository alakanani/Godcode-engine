# 📝 Changelog — God Code

All notable changes to the God Code engine are recorded here, that the generations may remember.

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
