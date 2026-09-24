# Changelog

## 2.2.0 — 2026-09-24
- F5 debugging: new `godcode.debugFile` command ("God Code: Debug Current File"), editor title-bar button, and F5 keybinding for .god files
- Debug adapter wired to `godcode dap`: breakpoints, stepping, variables, and `stopOnEntry` via the Debug Adapter Protocol over stdio
- New "God Code: Launch scroll" launch.json configuration snippet with `program` and `stopOnEntry` settings

## 2.1.0 — 2026-09-22
- God Code v4.0 support: `INTENT` and `ON` highlighted as declaration keywords; `ANCHOR` and `CONSULT` highlighted as built-ins
- New snippets: `intent` (DECLARE INTENT), `anchor` (ANCHOR receipt), `consult` (CONSULT oracle)

## 2.0.0 — 2026-09-21
- Initial release alongside God Code v2.0
- TextMate grammar: full v2 syntax highlighting (blocks, spirit commands, control flow, built-ins, strings, numbers, comments)
- 14 snippets covering every major construct
- Run / check-syntax commands with output panel (`Ctrl+Alt+R`)
- Smart indentation and `#` comment support for `.god` / `.godcode` files
