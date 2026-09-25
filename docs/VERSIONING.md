# Versioning in God Code

Two things carry versions in this language: the engine and the scrolls.
Both use the same scheme, and both make the same promise.

## The scheme: `X.Y.Z`

Versions are three plain numbers: major, minor, patch. They are compared
numerically, component by component, so `1.10.0` is newer than `1.9.0`.
Suffixes like `-beta` are not part of the scheme and are rejected by the
registry: a version is either a clean `X.Y.Z` or it does not exist.

| bump | meaning | example |
|---|---|---|
| MAJOR (`X`) | something old can break | a keyword changes meaning, a rite is removed |
| MINOR (`Y`) | new abilities, nothing old breaks | a new builtin, a new stdlib rite |
| PATCH (`Z`) | fixes only | a wrong error message, a crash repaired |

The engine version lives in `godcode/__init__.py` (currently 4.1.0). Each
scroll declares its own version in its `scroll.toml` manifest. A scroll's
`godcode` requirement (for example `>=2.0`) says which engine versions it
runs on; `godcode scroll publish` refuses a scroll whose requirement the
running engine does not satisfy.

## The backward-compatibility promise

- Within a MAJOR version of the engine, every scroll that ran keeps
  running. New MINOR releases may add keywords, builtins, and stdlib rites,
  but they never change the meaning of existing ones and never remove them.
- Within a MAJOR version of a scroll, every rite keeps its name, its
  parameters, and its return shape. New rites may be added in MINOR
  releases; bug fixes land in PATCH releases.
- A MAJOR bump of the engine or of a scroll is the explicit signal that
  something old may break. The breakage is described in `CHANGELOG.md`
  before the bump lands, and the old behavior is kept working for at least
  one full release with a deprecation notice (see below) whenever that is
  practical.

## Deprecation process

Nothing is removed by surprise. When a rite, keyword, or scroll version is
on its way out:

1. It is marked deprecated in `CHANGELOG.md`, with the release it will be
   removed in and what replaces it.
2. Using it keeps working, and the engine says so plainly the first time it
   is seen (a warning, not an error).
3. It is removed no earlier than the next MAJOR release of the engine or
   scroll, or two MINOR releases, whichever comes first.

Published scroll versions are never rewritten or deleted from a registry:
re-publishing an existing version is refused. If a published scroll turns
out to be wrong, publish a PATCH release. The registry keeps every version,
so anyone can pin to the exact release they tested against with
`godcode scroll install <name> --version X.Y.Z`.

## For scroll authors

- Start at `1.0.0`. Reserve `0.x` numbers for experiments you do not want
  strangers to depend on.
- Adding a rite is a MINOR bump. Changing what a rite returns is a MAJOR
  bump. Fixing a wrong result that nobody could have depended on
  intentionally is a PATCH bump.
- Declare the engine you tested against in `godcode`, for example
  `godcode = ">=4.0"`, so `publish` and `install` refuse combinations that
  cannot work.
- Declare what you stand on in `dependencies`, for example
  `dependencies = "json-tools >= 1.0.0, dates"`. Installs resolve the tree
  recursively and record the exact resolved versions in `install.json`, so a
  working set of scrolls can be recreated exactly.
