# Output formats and filtering

Output type and output destination are independent. You choose the format(s)
with `--out-type`, and where they go with `--out-dir` (or stdout).

## `--out-type`

One format, a comma-separated list, or `all` (`--output-type` is an accepted
alias):

| Value | Format |
|---|---|
| `text` (default) | human-readable summary |
| `json` | flat machine-readable issue list |
| `sarif` | SARIF 2.1.0 (GitHub/GitLab code scanning, IDE Problems panels) |
| `html` | a self-contained styled report |
| `all` | every format above |

## Where output goes

- A single format with no `--out-dir`: printed to stdout, so it composes with
  pipes and redirection.
- `all` or several formats: each one is written to `report.<ext>` (`report.txt`,
  `report.json`, `report.sarif`, `report.html`) inside `--out-dir`, or the current
  directory if `--out-dir` is omitted (several documents cannot stream to stdout).
  The path of each file written is printed to stderr.

```shell
bidsval validate /data                               # text to stdout
bidsval validate /data --out-type json               # JSON to stdout
bidsval validate /data --out-type sarif > out.sarif  # SARIF to a file via redirection
bidsval validate /data --out-type all --out-dir reports/   # writes all four into reports/
bidsval validate /data --out-type all                # writes all four into the current dir
```

## `--show` (which findings to display)

Filter the displayed findings by severity (requirement level). Defaults to `all`.

```shell
bidsval validate /data --show error              # show only errors
bidsval validate /data --show error,warning      # errors and warnings
bidsval validate /data --show all                # everything (default)
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

Empty files and unreadable NIfTI headers are errors (the file exists but has no
usable data), matching the reference validator. An empty `.nii(.gz)` is reported
as both `EMPTY_FILE` and `NIFTI_HEADER_UNREADABLE`, as the reference does.
