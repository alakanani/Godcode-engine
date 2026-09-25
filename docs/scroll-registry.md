# The Scroll Registry — installable God Code scrolls (Pillar 2, v3.0)

God Code v2.0 shipped six stdlib scrolls as loose `.god` files under
`godcode/scrolls/`, loaded only by the `IMPORT "name"` statement. The Scroll
Registry turns scrolls into **installable, versioned packages**:

- a **`scroll.toml` manifest** beside each scroll's entry file, with
  optional **dependency declarations**,
- a **local registry** at `registry/` (index + versioned sources),
- a **remote registry** over HTTPS (`api.getgodcode.com` by default),
- **`godcode scroll`** commands to publish, install, search, update,
  uninstall, list, and inspect,
- **IMPORT resolution** that falls back to installed scrolls when a name is
  not in the stdlib,
- **sha256 checksums** recorded on publish and verified on install.

Stdlib lookup keeps its precedence: if a name exists in `godcode/scrolls/`,
that file wins. Registry installs can never shadow the stdlib by accident.

## The manifest: `scroll.toml`

Every scroll is a directory containing a `scroll.toml` manifest and its
entry `.god` file. Six keys are required; `dependencies` is optional. The
parser is a hand-rolled TOML subset (requires-python is >=3.10, so `tomllib`
is unavailable): one `key = "value"` per line, `#` comments, double- or
single-quoted strings.

```toml
name = "json-tools"                                   # lowercase, digits, hyphens
version = "1.0.0"                                     # semver-ish X.Y.Z
author = "God Code community"
description = "JSON helpers written in pure God Code."
entry = "json-tools.god"                              # plain filename in this dir
godcode = ">=2.0"                                     # engine version requirement
dependencies = "dates >= 1.0.0, prophecy"             # optional: other scrolls
```

| key | rules |
|---|---|
| `name` | lowercase letters, digits, hyphens; must match the scroll's directory name |
| `version` | `X.Y.Z` numeric; publishing the same version twice is refused |
| `author` | free text |
| `description` | free text; shown by `scroll info` and `scroll install` |
| `entry` | plain filename (no directories) that exists beside the manifest |
| `godcode` | requirement like `>=2.0` or `>=2.0, <4`; clauses `>=` `<=` `==` `!=` `>` `<` |
| `dependencies` | optional; comma-separated `name` or `name <requirement>` clauses, e.g. `"json-tools >= 1.0.0, dates"` |

`publish` also verifies the scroll's `godcode` requirement against the
running engine and refuses the publish when it is not satisfied.

## Dependencies

A scroll may stand on other scrolls. Each clause names a scroll and
optionally one version requirement (`==`, `>=`, `>`, `<=`, `<`, `!=`).
Clauses are separated by commas, so each dependency carries a single
requirement clause.

On install, the tree is resolved recursively: the local index first, then
the remote registry, choosing the highest version that satisfies each
requirement. Cycles (scroll A needs B needs A) are refused with an error
that names the circle. Two branches demanding incompatible versions of the
same scroll are refused as a version conflict. The exact resolved tree is
recorded in the scroll's `install.json` receipt under `dependencies`, so a
working set can be recreated exactly.

## The local registry: `registry/`

```
registry/
  index.json                  # name -> {versions, latest, manifest, checksums}
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
    "manifest": { "name": "json-tools", "version": "1.0.0", ... },
    "checksums": { "1.0.0": { "scroll.toml": "sha256…", "json-tools.god": "sha256…" } }
  }
}
```

Publish records the sha256 of every published file in the index; install
verifies each file against its recorded checksum and refuses a copy that
changed after publish, naming the file and both digests.

## Install locations

| scope | directory | wins? |
|---|---|---|
| project-local | `.godcode/scrolls/<name>/<version>/` (in the cwd) | **yes** — checked first |
| user-global | `~/.godcode/scrolls/<name>/<version>/` | fallback |

Each install carries an `install.json` receipt: name, version, source
(`local` or `remote`), location, installed-at timestamp, checksums, the
resolved dependency tree, and the manifest snapshot. Within one scope, the
highest installed version is the one IMPORT resolves.

## The remote registry

The public registry lives at `https://api.getgodcode.com` and speaks
plain REST:

- `GET /v1/scrolls?q=&limit=&offset=`. Search the catalog.
- `GET /v1/scrolls/:name`. One scroll: versions, latest, description.
- `GET /v1/scrolls/:name/download`. The latest entry `.god` source.
- `GET /v1/scrolls/:name/versions/:version`. One version's source.
- `POST /v1/scrolls`. Publish (needs `Authorization: Bearer <token>`).

The base URL can be pointed elsewhere with the `GODCODE_REGISTRY_URL`
environment variable (used by the test suite to aim at a fake server).
Publishing to the remote registry needs the `GODCODE_PUBLISH_TOKEN`
environment variable; the CLI refuses without it and says so plainly.

A remote install downloads the entry `.god` and synthesizes a `scroll.toml`
from the catalog record (name, version, author, description, permissive
engine requirement). The downloaded bytes' checksum is recorded in the
install receipt.

## Flows

**Publish** a scroll you wrote:

```
godcode scroll publish ./my-scroll              # to the local registry
godcode scroll publish ./my-scroll --remote     # to the remote registry
```

No scroll yet? `godcode new my-scroll` raises one with a ready manifest.

Local publish validates the manifest (required keys, semver, entry exists,
name matches the directory, engine requirement satisfied), refuses when
that exact version is already published, records sha256 checksums of the
published files, copies into `registry/scrolls/<name>/<version>/`, and
updates `registry/index.json`. Remote publish posts the manifest and entry
source to the registry with your publish token.

**Install** a published scroll:

```
godcode scroll install json-tools
godcode scroll install json-tools --version 1.0.0
godcode scroll install blessings --project   # project-local instead of ~/
godcode scroll install sky-scroll --remote   # prefer the remote registry
```

With no `--version`, the latest published version is installed ("latest
wins"). The local index is consulted first; when the scroll is not there,
install falls back to the remote registry automatically. Dependencies are
resolved recursively along the way. Then, in any creation:

```
IMPORT "json-tools"
REVEAL(JSON_ENCODE(["a", 1]))
```

**Search** the remote catalog:

```
godcode scroll search sky
```

**Update** installed scrolls to the newest version known to the local
index or the remote registry:

```
godcode scroll update               # every installed scroll
godcode scroll update greet         # just one
godcode scroll update --remote      # prefer remote versions
```

**Uninstall** removes installed copies:

```
godcode scroll uninstall greet               # every installed version
godcode scroll uninstall greet --version 1.0.0
```

**Inspect:**

```
godcode scroll list          # installed scrolls, versions, locations
godcode scroll info json-tools
```

## Versioning

Versions are semver-ish `X.Y.Z`, compared numerically per component.
`1.10.0` beats `1.9.0`. Dependency clauses reuse the requirement machinery
(`>= 1.0.0`, `== 2.3.4`, `!= 1.2.0`, ...). Re-publishing an existing
version is refused; bump the version instead. The full scheme, the
backward-compatibility promise, and the deprecation process live in
`docs/VERSIONING.md`.

## The six stdlib scrolls, manifested

The v2.0 stdlib scrolls (`math`, `strings`, `lists`, `time`, `prophecy`,
`covenant`) each carry a `scroll.toml` in `godcode/scrolls/` and are
published at `1.0.0` in the local registry, so the publish/install flow
is real from day one — not just for community scrolls.

## Roadmap: signed publishes

The remote catalog is shaped so a signature field can join each version
later: `publish` already records checksums, and installs already verify
them. The next step is cryptographic signatures on publishes, verified on
install.
