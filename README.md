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

**In God Code, bare words are symbols**. `worthy` needs no quotes, for every unnamed thing is still a named spirit.

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

## 🕊️ v4.0 — Intent & Chain

The language learns to ask *why*. Every rite can carry a declared intent in plain words, and the Spirit discerns whether its words still walk in it:

```godcode
DECLARE INTENT "bring peace to the household" ON evening_blessing
```

Alignment is blessed. Drift is counseled gently, never punished. Plus **blockchain-anchored seals** (`ANCHOR(x)` returns a tamper-evident receipt map), the **`CONSULT`** oracle (two to three sentences of local counsel), and an **agent tool bridge** (`godcode tools`, `godcode bridge`) with six MCP-compatible tools. Every v1–v3 creation still runs.

Try the new examples:

```bash
godcode run --sandbox examples/intent_demo.god   # declared intent: aligned and drifted
godcode run --sandbox examples/anchor_demo.god   # anchor a covenant, keep the receipt
godcode run --sandbox examples/consult_demo.god  # ask the local oracle
godcode ledger verify                            # attest both chains
```

👉 [Read the v4.0 story](docs/WHAT_IS_NEW_IN_V4.md) — intent and chain in plain, founder-friendly words.

---

## 🌟 v3.0 — Strong Foundations

Four pillars plus a mini-pillar, one promise: **creators can share, protect, extend, and write God Code in comfort. And now AI agents can speak it too.** Every v2 creation still runs.

| Pillar | What it is | In one breath |
|---|---|---|
| 🛡️ **Sandbox** | [`docs/sandbox.md`](docs/sandbox.md) | `godcode run --sandbox file.god` — deny-by-default execution: no files, network, or subprocesses; time + step limits |
| 📜 **Scroll Registry** | [`docs/scroll-registry.md`](docs/scroll-registry.md) | `godcode scroll list` / `install blessings` / `publish ./mine` — share reusable scrolls through the registry |
| ⚙️ **Plugins & FFI** | [`docs/plugins.md`](docs/plugins.md) | `SUMMON("clockwork.now")` calls a plugin verb from God Code; embed the engine in Python with `godcode.run_source()` |
| 💡 **Language Server** | [`docs/lsp.md`](docs/lsp.md) | `godcode lsp` — hover, completions, and live diagnostics in your editor |
| 🤖 **Agentics** | [`docs/agentics.md`](docs/agentics.md) | `godcode check --json` / `run --json` — machine-readable reports so AI agents can generate, validate, and run God Code |

Try the new examples:

```bash
godcode run examples/summon_demo.god            # SUMMON a plugin spirit
godcode run --sandbox examples/sandbox_safe.god # pure creation, guarded
godcode scroll install blessings && godcode run examples/scroll_blessings_demo.god
```

👉 [Read the v3.0 story](docs/WHAT_IS_NEW_IN_V3.md) — the four pillars in plain, founder-friendly words.

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

📜 [Language Reference](docs/LANGUAGE_REFERENCE.md) — the complete v4.0 specification: every statement, operator tables, the Symbol Rule, built-in catalog, scrolls, ledger, Spirit Engine, CLI, SUMMON, the scroll registry, the sandbox, the language server, declared intent, blockchain-anchored seals, the oracle, and the agent tool bridge.

---

## 💻 Write God Code in VS Code

The official extension lives in [`editors/vscode`](editors/vscode): full syntax highlighting for `.god` files, 14 snippets (`creation`, `if`, `for`, `rite`…), and **Run Current File** (`Ctrl+Alt+R`). Copy it to `~/.vscode/extensions/godcode-2.0.0` and reload. Your creations light up like scripture.

---

## 🌍 Community

God Code is alive and growing. Join the movement:

- 💬 [Join our Discord community](https://discord.gg/894FEJhWfZ) — talk with fellow creators, ask questions, share your creations
- 🌐 [Visit getgodcode.com](https://getgodcode.com) — the home of God Code on the web
- 📜 Read [CONTRIBUTING.md](./CONTRIBUTING.md) and our [Code of Conduct](./CODE_OF_CONDUCT.md) before your first contribution
- 🐞 Found a problem or have an idea? [Open an issue](../../issues/new/choose) — the templates will guide you

Whether you write code or not, there is a place for you here. Come build with us.

---

## 🤝 Contribute to the Divine Movement

We welcome contributors with a spirit of purpose. Read [CONTRIBUTING.md](./CONTRIBUTING.md), browse [ISSUES.md](./ISSUES.md) for the v2.1 roadmap, and check [CHANGELOG.md](./CHANGELOG.md) for what v2.0 fulfilled.

---

## 🙏 Credits

**Created by:** Alakanani Itireleng (BitcoinLady) — Visionary Founder, Architect of God Code, Builder of worlds with intention and spirit

**AI Co-Creators:** ChatGPT (OpenAI) — logic assistant, language guide, spirit engine; Muse — v2.0 engine builders

> "Built not alone — but in communion with the machine."

Join us in building more than code. Build prophecy, logic, and purpose into the heart of machines.
