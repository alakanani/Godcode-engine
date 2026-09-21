# 🌟 God Code: The Language of Divine Computation

> "You are not a coder. You are a creator. You do not write code. You breathe worlds into being."
> — Alakanani Itireleng (BitcoinLady)

---

God Code is the **first spiritually-inspired programming language** — a complete v2.0 engine with a real lexer, parser, interpreter, standard library of scrolls, a tamper-evident covenant ledger, and an AI Spirit Engine. It reimagines programming with purpose, intention, and sacred design at the center.

---

## ✨ What Is God Code?

A symbolic, prophetic programming language:

```godcode
BEGIN CREATION
  DECLARE soul AS contract("redemption")
  BREATHE LIFE INTO soul
  IF seeker IS worthy THEN REVEAL("truth") ELSE REVEAL("trial")
  ASCEND
END CREATION
```

**In God Code, bare words are symbols** — `worthy` needs no quotes, for every unnamed thing is still a named spirit.

---

## 🚀 Quickstart

```bash
pip install -e .
godcode run examples/seven_seals.god
```

```text
1
2
3
...
seal        # 7, 14, 21, 28
...
seal of seals   # 35
🕊 Creation ascended in peace.
```

Verify before you run, or enter **Live Mode** 🕊:

```bash
godcode check my_creation.god   # ✓ my_creation.god is pure.
godcode repl                    # interactive — blank line executes, :quit ascends
```

---

## 🔥 v2.0 — What the Engine Holds

- 📖 **Real language core** — lexer, recursive-descent parser, AST, and tree-walking interpreter (Python 3.10+, stdlib only)
- 🕊 **The Symbol Rule** — unbound words evaluate to symbols; `IF seeker IS worthy` just works
- 🧭 **Control flow** — inline & block `IF/THEN/ELSE`, `FOR…ENDFOR`, `WHILE…DO…ENDWHILE`
- 🙏 **Rites** — `DEFINE RITE` with parameters, `RETURN`, `INVOKE`, and closures
- 📜 **Six scrolls** (stdlib, written in God Code): `math`, `strings`, `lists`, `time`, `prophecy`, `covenant`
- 🔒 **Covenant ledger** — `SEAL` writes tamper-evident hash-chained blocks (`godcode ledger verify`)
- 🧠 **Spirit Engine** — intent classification & prophecy from `god_code_training_dataset.csv`
- 📝 **Divine audit log** — every statement timestamped to `logs/godcode.log`
- 🛠️ **CLI** — `run`, `check`, `repl`, `fmt`, `ledger verify`
- 🧪 **Pytest suite** — `python -m pytest tests/ -q`

---

## 🗂️ Folder Structure

```
godcode-engine/
├── godcode/              # the interpreter package
│   ├── lexer.py          # tokens
│   ├── parser.py         # recursive descent → AST
│   ├── ast.py            # node definitions
│   ├── interpreter.py    # tree-walking execution
│   ├── environment.py    # scopes
│   ├── values.py         # Symbol, Contract, RiteFunction
│   ├── errors.py         # divine, line-numbered errors
│   ├── spirit.py         # Spirit Engine (intent + prophecy)
│   ├── ledger.py         # covenant chain
│   ├── cli.py            # the `godcode` command
│   └── scrolls/          # standard library, written in God Code
│       ├── math.god strings.god lists.god
│       └── time.god prophecy.god covenant.god
├── tests/                # pytest suite
├── examples/             # twelve working .god creations
├── playground/           # web playground
├── editors/vscode/       # VS Code extension — highlighting, snippets, run
├── docs/                 # tutorial + full language reference
├── archive/              # the v1 prototype, honored and retired
├── sample.godcode        # the original v1 creation — still runs
├── main.py               # entry point (no args → runs sample.godcode)
└── pyproject.toml        # pip install -e .  →  the `godcode` command
```

---

## 📖 Learn God Code

👉 [Start with the God Code Tutorial](docs/God_Code_Tutorial.md) — setup, your first creation, the commands.

📜 [Language Reference](docs/LANGUAGE_REFERENCE.md) — the complete v2.0 specification: every statement, operator tables, the Symbol Rule, built-in catalog, scrolls, ledger, Spirit Engine, and CLI.

---

## 💻 Write God Code in VS Code

The official extension lives in [`editors/vscode`](editors/vscode): full syntax highlighting for `.god` files, 14 snippets (`creation`, `if`, `for`, `rite`…), and **Run Current File** (`Ctrl+Alt+R`). Copy it to `~/.vscode/extensions/godcode-2.0.0` and reload — your creations light up like scripture.

---

## 🤝 Contribute to the Divine Movement

We welcome contributors with a spirit of purpose. Read [CONTRIBUTING.md](./CONTRIBUTING.md), browse [ISSUES.md](./ISSUES.md) for the v2.1 roadmap, and check [CHANGELOG.md](./CHANGELOG.md) for what v2.0 fulfilled.

---

## 🙏 Credits

**Created by:** Alakanani Itireleng (BitcoinLady) — Visionary Founder, Architect of God Code, Builder of worlds with intention and spirit

**AI Co-Creators:** ChatGPT (OpenAI) — logic assistant, language guide, spirit engine; Muse — v2.0 engine builders

> "Built not alone — but in communion with the machine."

Join us in building more than code — build prophecy, logic, and purpose into the heart of machines.
