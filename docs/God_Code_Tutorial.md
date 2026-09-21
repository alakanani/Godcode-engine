# 🌟 God Code Tutorial: Learn the Language of Divine Computation

> "You are not just coding. You are prophesying."

Welcome to the official tutorial for **God Code v2.0**, the world's first spiritually-inspired programming language. Whether you're a prophet of code or a curious seeker, this guide will walk you from nothing to your first living creation.

For the complete grammar, see [LANGUAGE_REFERENCE.md](LANGUAGE_REFERENCE.md). For runnable programs, explore [`../examples/`](../examples/).

---

## ✨ 1. What is God Code?

**God Code** is a symbolic, intention-driven programming language that blends:
- Artificial intelligence (the **Spirit Engine**)
- Conditional logic and cycles
- A tamper-evident **covenant ledger** (blockchain awareness)
- Spiritual commands and metaphors

Example God Code:
```godcode
BEGIN CREATION
  DECLARE seeker AS worthy
  IF seeker IS worthy THEN REVEAL("heaven") ELSE REVEAL("test")
  ASCEND
END CREATION
```

Notice: `worthy` needs no quotes. **In God Code, bare words are symbols**. Every unnamed thing is still a named spirit.

---

## 🛠️ 2. Setting Up Your Environment

### Step 1: Get the repository
```bash
git clone <your-godcode-repo-url>
cd godcode-engine
```

### Step 2: Install Python (3.10 or above)
God Code is powered by a Python interpreter.
```bash
python --version
```

### Step 3: Install the `godcode` command
```bash
pip install -e .
```

### Step 4: Confirm the heavens respond
```bash
godcode check sample.godcode
# ✓ sample.godcode is pure.
```

---

## 🧠 3. Writing Your First God Code

Create a file called `my_first.god`:

```godcode
BEGIN CREATION
  DECLARE spirit AS humble
  IF spirit IS humble THEN REVEAL("peace") ELSE REVEAL("struggle")
  ASCEND
END CREATION
```

Run it:

```bash
godcode run my_first.god
```

You will see:

```text
peace
🕊 Creation ascended in peace.
```

### What just happened, line by line

| Line | Meaning |
|---|---|
| `BEGIN CREATION` | every program is a creation. This opens it |
| `DECLARE spirit AS humble` | binds the name `spirit` to the **symbol** `humble` (bare words are symbols — no quotes needed) |
| `IF spirit IS humble THEN … ELSE …` | `IS` tests equality; the truthy branch reveals `"peace"` |
| `REVEAL("peace")` | speaks a value aloud (and records it) |
| `ASCEND` | ends the creation in peace |
| `END CREATION` | closes the creation |

Change `humble` to `proud` and run it again. Watch the prophecy change. *You* did that.

---

## 🔤 4. The Commands

| Command | Description |
|---|---|
| `BEGIN CREATION` / `END CREATION` | opens / closes a program |
| `DECLARE name AS value` | binds a name (`DECLARE prophets AS Isaiah, Elijah, Jeremiah` makes a list) |
| `BREATHE LIFE INTO name` | breathes life into a contract |
| `REVEAL(expr)` | speaks a value |
| `PROPHESY words…` | asks the Spirit Engine for a prophecy |
| `ASCEND` | ends the creation in peace |
| `REFLECT` | prints every bound name — a mirror for the program's soul |
| `BLESS name` / `ANOINT name` | marks a name as blessed / anointed |
| `SEAL expr` | writes a value into the tamper-evident covenant chain |
| `TESTIFY expr` | affirms a truth (`[TESTIFY] It is true. ✝`) — halts if it is false |
| `IF … THEN … ELSE … ENDIF` | decisions, inline or in blocks |
| `FOR x IN list` … `ENDFOR` | cycles over lists (or the characters of a string) |
| `WHILE … DO` … `ENDWHILE` | cycles while a condition holds |
| `DEFINE RITE name(params)` … `END RITE` | defines a reusable rite; `RETURN` sends a value back |
| `INVOKE name(args)` | calls a rite as a statement (or call it bare inside an expression) |
| `IMPORT "scroll"` | loads a scroll — `math`, `strings`, `lists`, `time`, `prophecy`, `covenant` |

Full details, operator tables, and the built-in catalog live in [LANGUAGE_REFERENCE.md](LANGUAGE_REFERENCE.md).

---

## 📜 5. Decisions, Cycles, and Rites — a Quick Tour

**Decide:**
```godcode
IF heart IS pure THEN
  REVEAL("the way is open")
ELSE
  REVEAL("wait and be still")
ENDIF
```

**Cycle:**
```godcode
FOR n IN RANGE(1, 6)
  REVEAL(n)
ENDFOR
```

**Bless and reuse:**
```godcode
DEFINE RITE BLESSING(name)
  RETURN "grace upon " + name
END RITE
REVEAL(BLESSING("seeker"))
```

**Borrow wisdom:**
```godcode
IMPORT "math"
REVEAL(SQRT(144))
REVEAL(FACTORIAL(7))
```

---

## 🧰 6. Your Tools

| Command | Does |
|---|---|
| `godcode run <file>` | run a creation |
| `godcode run --sandbox [--sandbox-timeout SECS] <file>` | run guarded — no files, network, or subprocesses ([sandbox](sandbox.md)) |
| `godcode check <file>` | verify a creation is pure (lex + parse, no execution) |
| `godcode repl` | **Live Mode** 🕊 — type God Code, end each block with a blank line, `:quit` to ascend |
| `godcode fmt <file>` | re-emit your code in canonical form (2-space indent, keywords UPPER) |
| `godcode scroll list\|install\|publish\|info` | browse, receive, share, and inspect registry scrolls ([registry](scroll-registry.md)) |
| `godcode lsp` | language server for your editor — hover, completions, live errors ([LSP](lsp.md)) |
| `godcode ledger verify` | verify the covenant chain is intact |

Every run is timestamped, line by line, into `logs/godcode.log` — your divine audit trail.

---

## 📖 7. Where to Go Next

- 📜 [LANGUAGE_REFERENCE.md](LANGUAGE_REFERENCE.md) — the complete v3.0 specification: operators, values, scrolls, ledger, Spirit Engine, CLI
- 🕊 [WHAT_IS_NEW_IN_V3.md](WHAT_IS_NEW_IN_V3.md) — the v3.0 "Strong Foundations" story: what the four pillars mean for you
- 🛡️ [sandbox.md](sandbox.md) — run strangers' creations safely: the deny-by-default sandbox
- 📜 [scroll-registry.md](scroll-registry.md) — publish and receive scrolls: `godcode scroll list|install|publish|info`
- ⚙️ [plugins.md](plugins.md) — extend the engine with plugins, call them with `SUMMON`, embed God Code in Python
- 💡 [lsp.md](lsp.md) — editor intelligence: hover, completions, and live diagnostics
- 🤖 [agentics.md](agentics.md) — for AI agents: machine-readable `--json` reports, the `AGENTS.md` guide, and the road to v4.0 "Intent & Chain"
- 💠 [`../examples/`](../examples/) — fifteen working creations: `seven_seals.god`, `generations.god`, `covenant_demo.god`, `summon_demo.god`, `sandbox_safe.god`, `scroll_blessings_demo.god`, and more
- 🤝 [CONTRIBUTING.md](../CONTRIBUTING.md) — join the movement
- 🛠️ [ISSUES.md](../ISSUES.md) — open tasks and the v2.1 roadmap

With purpose and power,
**Alakanani Itireleng (BitcoinLady)**

> "You are not a coder. You are a creator. You do not write code. You breathe worlds into being."
