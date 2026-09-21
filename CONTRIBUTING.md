# Contributing to God Code ✨

Welcome to the divine code movement. God Code is the first intentional programming language inspired by spiritual truth, artificial intelligence, and blockchain logic.

We believe that software creation can be sacred, purposeful, and world-changing. If you feel called to build, you are welcome here.

---

## 🏅 Contributor Recognition

Every contributor to God Code receives:

- The official **Divine Coder Badge**
- Shoutouts in the project README
- An eternal mark on the scroll of spiritual computation

---

## Folder Structure (v2.0)

- `godcode/` – the interpreter package: `lexer.py`, `parser.py`, `ast.py`, `interpreter.py`, `environment.py`, `values.py`, `errors.py`, `spirit.py`, `ledger.py`, `cli.py`
- `godcode/scrolls/` – the standard library, written in God Code (`math`, `strings`, `lists`, `time`, `prophecy`, `covenant`)
- `examples/` – twelve working `.god` creations (run with `godcode run examples/<name>.god`)
- `tests/` – pytest suite
- `playground/` – web playground
- `docs/` – tutorial + full language reference
- `archive/` – the honored v1 prototype
- `logs/` – spiritual execution logs (`godcode.log`)
- `main.py` – entry point (no args → runs `sample.godcode`)

---

## How to Contribute

1. Fork the repository
2. Clone your fork
3. Create a new branch (`git checkout -b your-feature`)
4. Install and test:
   ```bash
   pip install -e .
   python -m pytest tests/ -q
   godcode check examples/seven_seals.god
   ```
5. Submit a pull request with a meaningful description

**Please do not commit** build artifacts, `logs/`, or `covenant.chain` — they are per-creation, not per-repo.

---

## Contribution Ideas

- 🌱 See [ISSUES.md](./ISSUES.md) for the v2.1 roadmap: `ELSE IF` chains, string interpolation, dictionaries, `TRY`/`MERCY`, new scrolls, VS Code highlighting
- 📜 Add a new scroll to `godcode/scrolls/` — written in God Code, tested, and documented in `docs/LANGUAGE_REFERENCE.md` §14
- 💠 Add an example to `examples/` — every creation must be valid v2.0 and runnable via `godcode run`

---

## Style Guide

- Code must be clean, readable, and commented
- Use spiritually themed terms when possible
- Errors must be divine-flavored but genuinely helpful, always carrying line numbers — never mocking
- New statements/rites need: grammar in the parser, semantics in the interpreter, tests, and a LANGUAGE_REFERENCE entry

---

## Code of Conduct

We are building a sacred space.
- Be kind and constructive
- Respect all contributors
- No hate or harmful behavior will be tolerated

---

**With love and vision,**
Alakanani Itireleng (BitcoinLady)
