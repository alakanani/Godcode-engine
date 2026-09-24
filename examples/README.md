# Real-world examples

Small scrolls that show God Code doing ordinary work: reading files,
parsing JSON, calling an API, and writing dated reports. Every one of them
runs as-is. Just pick one.

## The four examples

- `examples/file_reporter.god`. Walks a directory, lists every file it finds, and reveals a total. Shows off the file builtins (LIST_DIR, READ_FILE, FILE_EXISTS).
  `godcode run examples/file_reporter.god`
- `examples/sales_summary.god`. Reads a JSON sales ledger from `examples/data/sales.json`, computes totals and averages, and writes a plain-text summary to `examples/data/sales_report.txt`. Shows off JSON parsing, WHILE loops, and file output.
  `godcode run examples/sales_summary.god`
- `examples/rest_client.god`. A REST API client. Fetches the public JSONPlaceholder user directory with HTTP_GET, parses it with JSON_PARSE, and reveals one line per user. If the network is down it degrades gracefully and the scroll still exits 0.
  `godcode run examples/rest_client.god`
- `examples/daily_report.god`. A dated daily report generator. Prints a headline like "Daily summary for September 24, 2026", formats a task list with a rite, and closes with done-vs-pending counts. Shows off rites, WHILE loops, interpolation, and the date builtins.
  `godcode run examples/daily_report.god`

All commands above run from the repo root.

## Notes

- The examples read and write paths relative to wherever you run them, so run them from the repo root. `sales_summary` writes its report to `examples/data/sales_report.txt`.
- `rest_client` needs internet access and plain `godcode run`. Under `godcode run --sandbox` the network is withheld by design, and HTTP_GET raises there.
- Each scroll was verified with `godcode check`, a clean `godcode lint`, and a real `godcode run` before being added.
