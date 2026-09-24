# The Sandbox — Pillar 1 of God Code v3.0

`godcode run --sandbox scroll.god` executes a creation under a
**deny-by-default policy**: everything that touches the world outside the
program is withheld unless the policy explicitly grants it. The default
strict policy grants almost nothing. Pure creations (numbers, cycles,
rites, REVEAL) pass through in peace; anything reaching for the host is
refused with a divine, line-numbered error.

## CLI usage

```sh
godcode run --sandbox scroll.god
godcode run --sandbox --sandbox-timeout 10 scroll.god
```

The bundled example is made for this:

```sh
godcode run --sandbox examples/sandbox_safe.god
```

A violation fails the run (exit 1) and names the line:

```
The sandbox withholds this power: the rite ASK would speak with the outer world — it is not granted. (line 3)
```

## Policy reference (`godcode.sandbox.SandboxPolicy`)

| Field | Default | Meaning |
|---|---|---|
| `allow_read_paths` | `None` (deny all) | Directories the creation may read files from. No file-reading rites exist in v2.0; enforced if any are added. |
| `allow_write` | `False` | Filesystem writes. No file-writing rites exist in v2.0; enforced if any are added. |
| `allow_network` | `False` | Network access. The `HTTP_GET` rite (see §13) is the one network rite: when network is denied it is withheld and raises instead of reaching out. |
| `allow_subprocess` | `False` | Spawning subprocesses. No subprocess rites exist in v2.0; enforced if any are added. |
| `allow_stdin` | `False` | Whether the `ASK` rite may read from stdin. |
| `allowed_import_paths` | `()` (deny all) | Directories `IMPORT` may draw scrolls from. A scroll is allowed when its real (symlink-resolved) path lies under one of these directories. |
| `timeout_seconds` | `5.0` | Wall-clock grant for the whole run. |
| `max_steps` | `100_000` | Step budget: one step per statement dispatch and per expression evaluation, bounding runaway loops and rite recursion. |

`SandboxPolicy.strict(source_dir=..., timeout_seconds=...)` builds the
CLI's policy: imports allowed from the bundled stdlib scrolls
(`godcode/scrolls/`) plus the creation's own directory, everything else
denied, with the given time grant.

Python API:

```python
from godcode.sandbox import SandboxPolicy, run_sandboxed, apply_policy

output = run_sandboxed(source, SandboxPolicy.strict(), source_name="psalm.god")
# output: list of REVEAL lines

guard = apply_policy(interpreter, policy)  # hooks onto an existing Interpreter
```

## What is enforced

- **Scroll imports** — `IMPORT` of any scroll whose resolved path falls
  outside `allowed_import_paths` is refused, including `..` traversals
  and symlinks (paths are resolved before the check).
- **The ASK rite** — reading from stdin is refused unless
  `allow_stdin=True`. (The only v2.0 rite with a host side effect.)
- **Step budget** — every statement dispatch and every expression
  evaluation counts one step; exceeding `max_steps` ends the run. This
  catches infinite `WHILE` cycles before the interpreter's own
  100,000-iteration guard, and converts unbounded rite recursion into a
  divine error instead of a bare `RecursionError`.
- **Time grant** — a POSIX alarm (`setitimer`) raises the violation when
  the grant expires; a wall-clock check inside the step counter is the
  fallback on platforms without `setitimer` or outside the main thread.
- **Host-side witnesses** — the covenant ledger and the audit log are
  left unbound in sandboxed runs, because they write to the host world.
  Since v4.0 the **Spirit is bound read-only** (the training dataset is
  only ever read), so `CONSULT` and intent discernment work in guarded
  runs, and `ANCHOR` is served by an **ephemeral in-memory chain**: it is
  never refused under the deny-writes policy, but nothing it anchors is
  written to disk. Host plugin auto-loading is likewise disabled:
  plugin verbs are trusted host code that runs outside any policy
  (SUMMON of a loaded plugin verb bypasses the sandbox by the plugin
  system's design), so `run_sandboxed` does not breathe them in.
  `apply_policy` on an interpreter that already loaded plugins cannot
  untrust them. Start from a fresh interpreter (or disable plugins)
  for a true sandbox.

All violations raise `godcode.errors.SandboxViolation`, a `GodCodeError`
with a line number, so existing `except GodCodeError` handling (including
the CLI's) treats them like any other divine error.

## Honest limitations

This is an **in-process sandbox**: a cooperative audit of the
tree-walking interpreter, not OS-level isolation.

- It cannot contain a program that escapes the interpreter itself
  (there is no known escape in the v2.0 walker, but in-process
  sandboxing can never prove the absence of one).
- It does not cap **memory**: a creation can still build enormous lists
  or strings within its step and time budgets.
- It does not cap **output**: REVEAL lines print as usual.
- `RANDOM` and `BEHOLD` (the clock) remain available. They are
  non-deterministic but touch nothing.
- The POSIX alarm only works in the main thread; elsewhere the
  wall-clock fallback applies, which checks once per interpreter step.
- A creation that never yields to the interpreter (impossible in the
  pure tree-walker, but possible if a future builtin blocks in C) would
  not be interrupted by the fallback check.

Treat the sandbox as a strong guardrail for running untrusted or
experimental scrolls — not as a security boundary for truly adversarial
code. For that, run the process itself inside a container or a
restricted user account.
