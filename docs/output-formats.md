# Output formats and filtering

Output type and output destination are independent. You choose the format(s)
with `--output-type`, and where they go with `--out-dir` (or stdout).

## `--output-type`

A comma-separated list of formats, or `all`:

| Value | Format |
|---|---|
| `text` (default) | human-readable summary |
| `json` | flat machine-readable issue list |
| `sarif` | SARIF 2.1.0 (GitHub/GitLab code scanning, IDE Problems panels) |
| `html` | a self-contained styled report |
| `all` | every format above |

## Where output goes

- Without `--out-dir`: the single selected type is printed to stdout
  (`--output-type` must name exactly one type in this case).
- With `--out-dir DIR`: each selected type is written to `DIR/report.<ext>`
  (`report.txt`, `report.json`, `report.sarif`, `report.html`).

```shell
bidsval validate /data                                  # text to stdout
bidsval validate /data --output-type json               # JSON to stdout
bidsval validate /data --output-type sarif > out.sarif  # SARIF to a file via redirection
bidsval validate /data --output-type html --out-dir reports/      # writes reports/report.html
bidsval validate /data --output-type all  --out-dir reports/      # writes all four files
```

## `--show` (which findings to display)

Filter the displayed findings by severity (requirement level). Defaults to
`error,warning`.

```shell
bidsval validate /data --show error              # show only errors
bidsval validate /data --show error,warning      # default
bidsval validate /data --show all                # include ignored/suppressed findings
```

`--show` only changes what is displayed or written; it never changes the
pass/fail result. The exit code and validity always depend on whether there are
errors, regardless of the filter.

## Severities and BIDS requirement levels

| Finding severity | BIDS requirement level |
|---|---|
| `error` | a REQUIRED rule is violated (the dataset is invalid) |
| `warning` | a RECOMMENDED practice is not met |
| `ignore` | an explicitly silenced finding (kept for transparency) |

Empty files are errors (the file exists but has no data), matching the reference
validator.
