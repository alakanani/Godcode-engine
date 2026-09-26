# 🕊 Strong Foundations

> "First the language was born. Then the engine was built. Now, the foundation is made strong."

The vision came first. Then the engine: a real lexer, parser, interpreter, scrolls, and a covenant ledger. **Strong Foundations is the ground an ecosystem is built on.** Four pillars, one purpose: creators should be able to **share** their work, **protect** their world, **extend** the language, and **build in comfort**.

You don't need to be a developer to feel what these mean. Each pillar is a promise:

---

## 🛡️ 1. The Sandbox — *safe hands*

**What it is:** a guarded chamber where creations can run without touching anything they shouldn't.

**Why it matters:** one day people will run code written by strangers — plugins, scrolls from the registry, community creations. The sandbox says *no* by default: no reading or writing files, no network, no subprocesses, no smuggled imports. Each run also gets a **time limit** and a **step budget**, so a runaway creation can never spin forever.

**In plain words:** it's the velvet rope around your computer. You can watch a stranger's creation dance without letting it open your drawers.

```bash
godcode run --sandbox examples/sandbox_safe.god
godcode run --sandbox --sandbox-timeout 5 examples/sandbox_safe.god
```

📖 Full detail: [`docs/sandbox.md`](sandbox.md)

---

## 📜 2. The Scroll Registry — *shared wisdom*

**What it is:** an app store for scrolls — the packages of reusable God Code that creators write and share.

**Why it matters:** today every creator carries their own copy of every helper. The registry changes that: scrolls carry a `scroll.toml` manifest (name, version, description), and four commands rule them all — `godcode scroll list` to browse, `godcode scroll install <name>` to receive, `godcode scroll publish <dir>` to give, and `godcode scroll info <name>` to inspect. Installed scrolls rest in `~/.godcode/scrolls/` (or your project's `.godcode/`) and are reached with plain old `IMPORT`.

**In plain words:** write a blessing once, publish it, and let a thousand creations borrow it.

```bash
godcode scroll install blessings
godcode scroll list
```

📖 Full detail: [`docs/scroll-registry.md`](scroll-registry.md)

---

## ⚙️ 3. Plugins & the FFI — *open doors*

**What it is:** a way for Python developers to give God Code new powers — and for God Code to reach out and use them.

**Why it matters:** the engine's built-in rites are deliberately few. But some things belong to the outside world: clocks, sensors, databases, APIs. A **plugin** is a small Python module placed in `plugins/` with a `register(interpreter)` function; once installed, any creation can call its verbs through the **`SUMMON`** rite:

```godcode
DECLARE the_hour AS SUMMON("clockwork.now")
```

And for developers who want God Code *inside* their own Python programs, the **embedding API** opens the way: `godcode.run_source()` and `godcode.run_file()` execute God Code and return the captured output — no subprocess, no ceremony.

**In plain words:** God Code no longer lives only in its own temple. It can step outside. And Python can step in.

📖 Full detail: [`docs/plugins.md`](plugins.md)

---

## 💡 4. The Language Server (LSP) — *a gentler way to write*

**What it is:** editor intelligence for God Code — hover help, completions, and live error diagnostics, speaking the same protocol as VS Code, Neovim, and the rest.

**Why it matters:** a language people *write* needs to meet them where they write it. Run `godcode lsp` and your editor gains a companion: hover over a rite to see what it does, get suggestions as you type, and see problems underlined before you ever run the file.

**In plain words:** the editor starts to speak God Code too — quietly guiding, never scolding.

```bash
godcode lsp     # speaks JSON-RPC over stdio: initialize, hover, completion, diagnostics
```

📖 Full detail: [`docs/lsp.md`](lsp.md)

---

## 🤖 5. Agentics (mini-pillar) — *the language agents speak*

**What it is:** God Code, made legible to AI agents. `godcode check --json` and `godcode run --json` emit single-document, machine-readable reports — structured diagnostics with line, column, stable error codes, and hints — so a coding agent can generate a creation, validate it, fix it, and run it without ever parsing human prose. A new [`AGENTS.md`](../AGENTS.md) at the repo root tells agents exactly how to work with the language.

**Why it matters:** the founder's corrected vision — not *Argentina*, **agentics**. The next generation of software is written by agents, and a language agents can speak fluently is a language that travels. This mini-pillar is the first step toward [Intent & Chain](INTENT_AND_CHAIN.md), where every agent action becomes a sealed covenant on the ledger.

**In plain words:** God Code learns to talk to the machines that will write it.

```bash
godcode check --json creation.god     # {"ok": true, "diagnostics": []}
godcode run --sandbox --json creation.god  # safe execution, machine-readable
```

📖 Full detail: [`docs/agentics.md`](agentics.md)

---

## 🌱 What this means for the movement

Strong Foundations doesn't change how God Code *feels* to write. Every creation still runs. What changes is what creators can **do together**: publish scrolls for others, run strangers' code in safety, extend the engine with plugins, and write in editors that understand the language.

The language is spoken. The engine is built. **Now the foundation is strong. And the building can begin.**

---

*See also: [CHANGELOG.md](../CHANGELOG.md) · [LANGUAGE_REFERENCE.md](LANGUAGE_REFERENCE.md) · [God_Code_Tutorial.md](God_Code_Tutorial.md)*
