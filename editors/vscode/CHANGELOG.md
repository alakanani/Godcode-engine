# Changelog

## 2026-09-24: Debugging arrives
- F5 debugging: new `godcode.debugFile` command ("God Code: Debug Current File"), editor title-bar button, and F5 keybinding for .god files
- Debug adapter wired to `godcode dap`: breakpoints, stepping, variables, and `stopOnEntry` via the Debug Adapter Protocol over stdio
- New "God Code: Launch scroll" launch.json configuration snippet with `program` and `stopOnEntry` settings

## 2026-09-22: Intent & Chain support
- Declared intent support: `INTENT` and `ON` highlighted as declaration keywords; `ANCHOR` and `CONSULT` highlighted as built-ins
- New snippets: `intent` (DECLARE INTENT), `anchor` (ANCHOR receipt), `consult` (CONSULT oracle)

## 2026-09-21: First light
- Initial release
- TextMate grammar: full syntax highlighting (blocks, spirit commands, control flow, built-ins, strings, numbers, comments)
- 14 snippets covering every major construct
- Run / check-syntax commands with output panel (`Ctrl+Alt+R`)
- Smart indentation and `#` comment support for `.god` / `.godcode` files
