# The Scroll Registry — installable God Code scrolls (Pillar 2, v3.0)

God Code v2.0 shipped six stdlib scrolls as loose `.god` files under
`godcode/scrolls/`, loaded only by the `IMPORT "name"` statement. The Scroll
Registry turns scrolls into **installable, versioned packages**:

- a **`scroll.toml` manifest** beside each scroll's entry file,
- a **local registry** at `registry/` (index + versioned sources),
- **`godcode scroll`** commands to publish, install, list, and inspect,
- **IMPORT resolution** that falls back to installed scrolls when a name is
  not in the stdlib.

Stdlib lookup keeps its precedence: if a name exists in `godcode/scrolls/`,
that file wins — registry installs can never shadow the stdlib by accident.

## The manifest: `scroll.toml`

Every scroll is a directory containing a `scroll.toml` manifest and its
entry `.god` file. All six keys are required. The parser is a hand-rolled
TOML subset (requires-python is >=3.10, so `tomllib` is unavailable): one
`key = "value"` per line, `#` comments, double- or single-quoted strings.

```toml
name = "json-tools"                                   # lowercase, digits, hyphens
version = "1.0.0"                                     # semver-ish X.Y.Z
author = "God Code community"
description = "JSON helpers written in pure God Code."
entry = "json-tools.god"                              # plain filename in this dir
godcode = ">=2.0"                                     # engine version requirement
```

| key | rules |
|---|---|
| `name` | lowercase letters, digits, hyphens; must match the scroll's directory name |
| `version` | `X.Y.Z` numeric; publishing the same version twice is refused |
| `author` | free text |
| `description` | free text; shown by `scroll info` and `scroll install` |
| `entry` | plain filename (no directories) that exists beside the manifest |
| `godcode` | requirement like `>=2.0` or `>=2.0, <4`; clauses `>=` `<=` `==` `!=` `>` `<` |

`publish` also verifies the scroll's `godcode` requirement against the
running engine and refuses the publish when it is not satisfied.

## The local registry: `registry/`

```
registry/
  index.json                  # name -> {versions, latest, manifest}
  scrolls/
    <name>/
      <version>/               # the published files, incl. scroll.toml
        scroll.toml
        <name>.god
```

`registry/index.json` is the source of truth for what is published:

```json
{
  "json-tools": {
    "name": "json-tools",
    "versions": ["1.0.0"],
    "latest": "1.0.0",
    "manifest": { "name": "json-tools", "version": "1.0.0", ... }
  }
}
```

## Install locations

| scope | directory | wins? |
|---|---|---|
| project-local | `.godcode/scrolls/<name>/<version>/` (in the cwd) | **yes** — checked first |
| user-global | `~/.godcode/scrolls/<name>/<version>/` | fallback |

Each install carries an `install.json` receipt: name, version, location,
installed-at timestamp, and the manifest snapshot. Within one scope, the
highest installed version is the one IMPORT resolves.

## Flows

**Publish** a scroll you wrote:

```
godcode scroll publish ./my-scroll      # ./my-scroll holds scroll.toml + entry
```

Validates the manifest (required keys, semver, entry exists, name matches
the directory, engine requirement satisfied), refuses when that exact
version is already published, copies into `registry/scrolls/<name>/<version>/`,
and updates `registry/index.json`.

**Install** a published scroll:

```
godcode scroll install json-tools
godcode scroll install json-tools --version 1.0.0
godcode scroll install blessings --project   # project-local instead of ~/
```

With no `--version`, the latest published version is installed ("latest
wins"). Then, in any creation:

```
IMPORT "json-tools"
REVEAL(JSON_ENCODE(["a", 1]))
```

**Inspect:**

```
godcode scroll list          # installed scrolls, versions, locations
godcode scroll info json-tools
```

## Versioning

Versions are semver-ish `X.Y.Z`, compared numerically per component —
`1.10.0` beats `1.9.0`. There is no range resolution on install yet:
`--version` takes an exact published version, otherwise latest wins.
Re-publishing an existing version is refused; bump the version instead.

## The six stdlib scrolls, manifested

The v2.0 stdlib scrolls (`math`, `strings`, `lists`, `time`, `prophecy`,
`covenant`) each carry a `scroll.toml` in `godcode/scrolls/` and are
published at `1.0.0` in the local registry, so the publish/install flow
is real from day one — not just for community scrolls.

## Roadmap: URL registry

The local `registry/` directory is deliberately shaped like a future remote
registry: `index.json` is the catalog, `scrolls/<name>/<version>/` are the
artifacts. The planned next step is a URL-backed registry —
`godcode scroll publish` pushing to, and `install` fetching from, an HTTPS
index — with checksums in the manifest and signature verification on
install. The `ScrollRegistry` class takes its registry root, home, and
project directory as constructor arguments precisely so a remote backend
can slot in beside the local one.
