# God Code Language Server (`godcode lsp`)

The language server brings the sanctuary into your editor: divine errors
as you type, hover scripture for every keyword, and completions — all
through the [Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
over stdio. Hand-rolled JSON-RPC with `Content-Length` framing, stdlib only
(`godcode/lsp.py`); no third-party dependencies.

## Running it

```bash
godcode lsp
```

The server reads JSON-RPC messages on stdin and writes responses and
notifications on stdout. **Never write to stdout from anything else** —
it is the protocol channel. All server logging goes to stderr
(`[godcode-lsp] ...`).

A minimal manual session:

```
Content-Length: 82\r\n\r\n{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
```

→ responds with capabilities, then accepts `initialized`, document
notifications, and the `shutdown` / `exit` lifecycle.

## Protocol coverage

| Method | Kind | Support |
|---|---|---|
| `initialize` | request | ✅ Responds with `textDocumentSync: 1` (full), `hoverProvider: true`, `completionProvider: {triggerCharacters: []}`, plus `serverInfo` |
| `initialized` | notification | ✅ No-op |
| `shutdown` | request | ✅ Responds `null`; sets the shutdown flag |
| `exit` | notification | ✅ Stops the server (exit 0 after `shutdown`, else 1) |
| `textDocument/didOpen` | notification | ✅ Stores the document, re-parses, publishes diagnostics |
| `textDocument/didChange` | notification | ✅ Full-document sync; re-parses, publishes diagnostics |
| `textDocument/publishDiagnostics` | → notification | ✅ `[{range, severity: 1, message}]`; empty list when the scroll is pure |
| `textDocument/hover` | request | ✅ Markdown doc for the word (or multi-word phrase) under the cursor; `null` when unknown |
| `textDocument/completion` | request | ✅ Keywords + built-ins (kind 14) and snippet items (kind 15, `insertTextFormat: 2`) |
| `$/cancelRequest`, `workspace/*`, other methods | — | ❌ Not implemented; unknown requests answer JSON-RPC `-32601` (Method not found) |

### Diagnostics

`didOpen`/`didChange` run the **real lexer + parser** — the same pipeline
as `godcode check` — and map the divine error's 1-based line to 0-based
LSP ranges. `severity: 1` (Error), `source: "godcode"`, and the full
divine message (e.g. `Expected AS but found the end of the line
(line 3, col 12)`). A pure scroll publishes an empty diagnostic list.

### Hover

The word under the cursor is looked up in the `LSP_DOCS` table in
`godcode/lsp.py`: every keyword (`BEGIN`, `CREATION`, `DECLARE`, `IF`,
`FOR`, `WHILE`, `DEFINE`, `RITE`, `INVOKE`, `RETURN`, `IMPORT`, `REVEAL`,
`BREATHE`, `PROPHESY`, `ASCEND`, `SEAL`, `TESTIFY`, `BLESS`, `ANOINT`,
`REFLECT`, …) and every built-in (`LEN`, `STR`, `NUM`, `TYPE`, `RANDOM`,
`RANGE`, `PUSH`, `UPPER`, `LOWER`, `SPLIT`, `JOIN`, `ASK`, `BEHOLD`,
`REVERSE`) carries a 1–2 sentence divine-voiced description plus a tiny
usage snippet, returned as markdown. Multi-word phrases are matched as
units: `BEGIN CREATION`, `END CREATION`, `DEFINE RITE`, `END RITE`,
`BREATHE LIFE INTO`.

### Robustness

- Unknown methods → JSON-RPC error `-32601` (notifications are ignored).
- Malformed frames (bad `Content-Length`, truncated body, invalid JSON)
  are logged to stderr and skipped; the server keeps serving.
- A handler that raises answers `-32603` (Internal error) instead of
  killing the server.

## Editor integration

Any LSP client can spawn the server:

```jsonc
// example client configuration
{
  "command": ["godcode", "lsp"],
  "filetypes": ["godcode"],
  "rootPatterns": [".git"]
}
```

Neovim (`nvim-lspconfig`-style):

```lua
vim.api.nvim_create_autocmd("FileType", {
  pattern = "godcode",
  callback = function()
    vim.lsp.start({ name = "godcode-lsp", cmd = { "godcode", "lsp" } })
  end,
})
```

Sublime Text (LSP package), Emacs (`eglot`), Helix, and Zed all accept the
same `["godcode", "lsp"]` stdio command. Associate the server with
`*.god` / `*.godcode` files.

## VS Code adoption plan

The bundled extension (`editors/vscode/`) currently ships TextMate
grammar, snippets, and run commands only. In a future release it will
adopt `godcode lsp` as its language server:

1. Add a `client/` contribution that spawns `godcode lsp` via
   `vscode-languageclient/node` for `godcode` language files.
2. Route the existing "check scroll" command through
   `textDocument/publishDiagnostics` instead of parsing CLI output.
3. Surface hover docs and completions from the server, replacing the
   static snippet list where they overlap.
4. Keep the TextMate grammar for syntax highlighting. The server does
   not provide semantic tokens (yet).

Until then, VS Code users can already point any generic LSP client
extension at `godcode lsp` (see "Editor integration" above) for live
diagnostics.
