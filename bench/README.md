# God Code Benchmarks

A performance benchmark suite for the God Code interpreter. It drives the
real interpreter (direct import of the `godcode` package, no subprocess)
over representative workloads and reports the median of several timed runs.

## How to run it

From the repo root:

```bash
python3 bench/bench.py                 # full run (about 20-30 seconds)
python3 bench/bench.py --quick         # short smoke run (a few seconds)
python3 bench/bench.py --json out.json # also write machine-readable results
python3 bench/bench.py --only fib_recursion
python3 bench/bench.py --runs 7 --warmups 3
```

Flags:

| Flag | Meaning |
|---|---|
| `--quick` | smaller workloads, 1 warmup + 3 timed runs |
| `--json PATH` | write machine-readable results (JSON) to PATH |
| `--runs N` | timed runs per benchmark (default 5, 3 with `--quick`) |
| `--warmups N` | warmup runs per benchmark (default 2, 1 with `--quick`) |
| `--only NAME` | run a single benchmark by name |

The workload scrolls are generated deterministically into `bench/scrolls/`
(fixed seed `20260925`) and are gitignored. Every scroll is validated with
`python -m godcode check` before any timing begins; a scroll that fails
validation aborts the run.

## What each benchmark measures

| Benchmark | Measures |
|---|---|
| `lex_parse` | Lexing + parsing of a large generated scroll (DECLAREs, interpolated REVEALs, IF blocks, rite definitions and invocations). Front-end cost only. |
| `fib_recursion` | Deep rite recursion: naive double-recursive `fib(22)` (depth 22, well inside the call stack). Exercises rite calls, environments, and RETURN unwinding. |
| `while_loop` | A tight counting WHILE loop (20,000 iterations of integer addition). |
| `string_interp` | String interpolation: REVEAL of strings breathing in several expressions each, including a builtin call (`UPPER`). |
| `list_ops` | List work: `PUSH` 5,000 items onto a list, then `FOR`-iterate and sum it. |
| `json_stdlib` | JSON encode/decode round trips through the real registry scroll `registry/scrolls/json-tools/1.0.0/json-tools.god`, imported for real with `IMPORT`. |
| `anchor_chain` | `ANCHOR` chain sealing: hashing plus the tamper-evident JSONL chain append per seal, on a fresh simulated chain in a temp dir. |

## Methodology

1. **Deterministic generation.** Workload scrolls are generated with a fixed
   random seed (`20260925`), so the same scrolls are produced on every run.
2. **Validate first.** Each scroll passes `godcode check` before timing.
3. **Warmup, then median.** Each benchmark runs `warmups` untimed warmup runs
   followed by `runs` timed runs; the reported number is the **median** of the
   timed runs (min and max are shown too).
4. **Isolated interpreter.** Every timed run builds a fresh `Interpreter`
   with `log_path=None` (the per-statement session log is disabled so the
   numbers measure the interpreter, not disk logging), REVEAL output captured
   to a null sink, and plugins disabled (`GODCODE_NO_PLUGINS=1`).
5. **Execution only.** Run benchmarks parse once up front and time execution
   only; the `lex_parse` benchmark covers front-end cost separately.
6. **Machine info.** Platform, Python version, and CPU are captured and
   printed with every run, and stored in `--json` output.

## How to reproduce the numbers

```bash
git checkout <commit>          # the commit the numbers were recorded on
python3 bench/bench.py         # full run; compare the medians
```

The absolute numbers depend on the machine (see `bench/RESULTS.md` for the
reference machine). On the same machine, reruns land within a few percent of
each other; compare medians, not single runs. For quick iteration use
`--quick`, but note its smaller workloads are not comparable to full-run
numbers.

## A note on the json-tools scroll

The registry scroll `registry/scrolls/json-tools/1.0.0/json-tools.god` could
not be parsed as shipped: line 174 compared with the literal string `"{"`,
which the parser reads as an unsealed interpolation. It is fixed on this
branch to `"{{"` (which evaluates to the same single `{`). Without the fix
the scroll cannot be imported at all, so the `json_stdlib` benchmark could
not run through the real scroll.
