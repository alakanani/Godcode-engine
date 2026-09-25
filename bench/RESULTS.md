# God Code Benchmark Results

Recorded by running the documented method on this machine:

```bash
python3 bench/bench.py
```

Date: 2026-09-25. Machine: AMD EPYC 9D25 126-Core Processor.
Python 3.12.3 on Linux-7.0.0-38-generic-x86_64-with-glibc2.39.
God Code 4.1.0, branch `feature/bench`.

Mode: full. Seed 20260925. 2 warmup + 5 timed runs per benchmark.
The reported number is the median of the timed runs.

```
benchmark | median_ms | min_ms | max_ms | runs | detail
lex_parse | 220.9 | 205.3 | 243.3 | 5 | 8284 lines, 319.5 KB generated scroll
fib_recursion | 841.3 | 834.6 | 850.1 | 5 | fib(22) by naive double recursion
while_loop | 151.7 | 144.3 | 158.1 | 5 | counting loop of 20000 iterations
string_interp | 28.8 | 28.7 | 29.3 | 5 | 2000 REVEALs with breathed-in expressions
list_ops | 92.6 | 91.9 | 95.0 | 5 | PUSH 5000 items, then FOR-sum them
json_stdlib | 118.0 | 116.7 | 121.4 | 5 | 50 JSON_ENCODE/JSON_DECODE round trips through the registry json-tools scroll
anchor_chain | 8.1 | 8.0 | 8.7 | 5 | 50 ANCHOR seals on a fresh simulated chain
```

Reading the numbers: the tree-walking interpreter executes roughly
130k simple loop iterations per second (`while_loop`), interpolates about
70k strings per second, and lexes/parses about 1.4 MB of God Code per
second. `fib(22)` is the heaviest workload at 0.84 s, dominated by rite
call overhead (roughly 57k rite calls). `ANCHOR` sealing is cheap per seal
(about 0.16 ms) on the local simulated chain.

Rerun on the same machine to compare: medians land within a few percent
run to run. Numbers from other machines are not directly comparable; see
`bench/README.md` for the method and the machine info captured with each
run (`--json` output).
