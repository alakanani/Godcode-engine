# God Code for VS Code

Language support for **God Code** — the spiritually-inspired programming language.
Syntax highlighting, smart indentation, snippets, and one-key running of `.god` / `.godcode` files.

## Features

- 🌈 Full syntax highlighting for God Code v2 (creation blocks, spirit commands, control flow, built-ins)
- ✍️ Snippets: `creation`, `declare`, `reveal`, `breathe`, `if`, `for`, `while`, `rite`, `invoke`, `testify`, `seal`, `import`, `bless`, `prophesy`
- ▶️ **God Code: Run Current File** (`Ctrl+Alt+R` / `Cmd+Alt+R`) — runs the open file and shows output in the God Code panel
- ✔️ **God Code: Check Syntax of Current File** — parses without executing
- 💬 `#` line comments, auto-closing brackets and quotes, smart indent/dedent

## Requirements

The God Code interpreter (Python 3.10+):

```bash
git clone https://github.com/alakanani/Godcode-engine
cd Godcode-engine
pip install -e .
```

## Install this extension

**Option A — from source (today):**
1. Copy the `editors/vscode` folder to `~/.vscode/extensions/godcode-2.0.0`
2. Reload VS Code. `.god` files light up immediately

**Option B — package it:**
```bash
npm install -g @vscode/vsce
cd editors/vscode && vsce package
# then: code --install-extension godcode-2.0.0.vsix
```

**Option C — marketplace:** coming soon 🕊

## Try it

Create `hello.god`:

```godcode
BEGIN CREATION
  DECLARE seeker AS "world"
  BREATHE life INTO seeker
  REVEAL("Hello, " + seeker)
  ASCEND
END CREATION
```

Press `Ctrl+Alt+R` and watch it ascend.

---

## Language server (coming next) 🕊

God Code now ships a **language server**: `godcode lsp` serves the
[Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
over stdio — live diagnostics from the real parser, hover scripture for
every keyword and built-in, and completions. See [`docs/lsp.md`](../../docs/lsp.md)
for the protocol coverage table and editor setup.

**Adoption plan for this extension:** in a future release the extension
will spawn `godcode lsp` as its language server (via
`vscode-languageclient`), routing diagnostics, hover, and completions
through it while keeping the TextMate grammar for highlighting. Until
then, you can point any generic LSP client extension at the
`godcode lsp` command today.

---

*"You are not a coder. You are a creator."* — Alakanani Itireleng
