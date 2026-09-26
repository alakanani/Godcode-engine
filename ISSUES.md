# God Code Contributor Tasks – GitHub Issues

Welcome to the contributor space for God Code! The original tasks are fulfilled. What remains is the road ahead.

---

## ✅ Fulfilled (2026-09-21)

### ~~1. Add IF...THEN...ELSE logic to interpreter~~ — ✅ DONE
Inline and block forms, nesting, `ELSE` binding to the nearest `IF`. See `docs/LANGUAGE_REFERENCE.md` §7.

### ~~2. Implement FOR loop logic~~ — ✅ DONE
`FOR x IN list … ENDFOR` over lists and string characters, with child scoping. See §8.

### ~~3. Add timestamp to each audit log entry~~ — ✅ DONE
Every executed statement is timestamped to `logs/godcode.log` (`[ts] line :: Kind :: summary`). See §17.

### ~~4. Expand REVEAL to support conditions~~ — ✅ DONE
`IF seeker IS prophet THEN REVEAL("vision") ELSE REVEAL("cloud")` — decisions and revelation are fully joined.

### 5. Build syntax highlighter or online demo — 🚧 IN PROGRESS
`playground/` is scaffolded. Remaining: live in-browser execution, shareable creation links, and editor syntax highlighting for `.god` files.

**Labels**: `frontend`, `demo`, `project-help`

---

## 🌱 Ideas — the road ahead

### 6. `ELSE IF` chains
Flatten nested decisions: `IF … THEN … ELSE IF … THEN … ELSE … ENDIF`.
**Labels**: `feature`, `logic`

### 7. String interpolation
`"grace upon {name}"` — breathe values directly into strings.
**Labels**: `feature`, `expression`

### 8. Dictionaries (tables of testimony)
`DECLARE record AS {name: "seeker", seals: 7}` with `record["seals"]` access.
**Labels**: `feature`, `values`

### 9. `TRY` / `MERCY` error handling
Catch a failing testimony with grace instead of halting the creation.
**Labels**: `feature`, `errors`

### 10. More scrolls
`files` (read/write scrolls on disk), `http` (call upon distant APIs), `json` (parse and emit).
**Labels**: `scrolls`, `stdlib`

### 11. VS Code syntax highlighting
A TextMate grammar for `.god` files — keywords, symbols, strings, and comments in their proper colors.
**Labels**: `frontend`, `tooling`

### 12. A debugger for the divine
Step through creations line by line: `godcode debug <file>` with breakpoints and `REFLECT` at each pause.
**Labels**: `tooling`, `cli`

### 13. Scroll registry
Publish and share scrolls: `godcode scroll publish my_scroll.god`, `IMPORT "seeker/my_scroll"`.
**Labels**: `ecosystem`, `scrolls`

### 14. Fuzz the heavens
Property-based tests over the lexer/parser (Hypothesis) — let randomness testify to the grammar's soundness.
**Labels**: `tests`, `good-first-issue`

---

*Have another vision? Open an issue. Prophecy favors the bold.*
