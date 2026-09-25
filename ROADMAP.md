# God Code Roadmap

Where the language is headed, in plain words. This is a living document: it changes as the language grows.

## Just landed

- The linter (`godcode lint`): six gentle rules that catch unused names, undefined names, shadowing, empty blocks, unreachable code, and duplicate declarations.
- A bigger standard library: JSON, file reading and writing, directory listing, dates and times, and fetching pages from the web.
- The test runner (`godcode test`): write rites named `TEST_*` and the runner finds them, runs them, and reports pass or fail.
- `BREAK` and `CONTINUE` for loops.
- `TRY` / `CATCH` error handling, plus stack traces that show the path through your rites when something fails.
- The formal language specification (`docs/LANGUAGE_SPEC.md`) and the EBNF grammar (`docs/GRAMMAR.ebnf`).
- The remote scroll registry: `godcode scroll search` queries the public
  catalog over HTTPS, `install` falls back to the remote registry when the
  local index has no answer (`--remote` prefers it), `publish --remote`
  pushes with a publish token (`GODCODE_PUBLISH_TOKEN`), `update` moves
  installed scrolls to the newest known version, `uninstall` removes them,
  manifests declare `dependencies` resolved recursively with cycle
  detection, and sha256 checksums are recorded on publish and verified on
  install. The versioning scheme, compatibility promise, and deprecation
  process are written down in `docs/VERSIONING.md`.

## What is next

- Performance benchmarks: reproducible numbers, published with the method, so improvements can be measured honestly.
- More of the standard library: cryptography, concurrency, and the everyday builtins a working language needs.
- Editor tooling polish: the VS Code extension, the language server, and the playground keeping pace with the language.
- 1.0 readiness: the versioning promise, the compatibility policy, and the governance documents a language needs before strangers trust it with real work.

## Deliberately not planned

- A compiler to native machine code. God Code is interpreted, and that is a choice, not a gap.
- Mobile targets. The language runs where Python runs.

No hype: items move from "next" to "landed" when they are built, tested, documented, and green.
