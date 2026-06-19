# CLI reference

The `bidsval` command has three subcommands:

| Command | Purpose |
|---|---|
| [`bidsval validate`](#bidsval-validate) | validate a dataset, a subject, or a file |
| [`bidsval schema`](#bidsval-schema) | show the resolved schema and the bundled versions |
| [`bidsval eval`](#bidsval-eval) | evaluate one BIDS schema expression |

Top-level options:

| Option | Effect |
|---|---|
| `-h`, `--help` | show help and exit (works on every subcommand too) |
| `--version` | print the bidsval version and exit |

Every command prints `-h` help with examples. Run `bidsval <command> -h` for the
command you want.

## Exit codes

`bidsval` is built to drop into CI: the exit code is the result.

| Code | Meaning |
|---|---|
| `0` | the dataset is valid (no errors); warnings may still be present |
| `1` | validation found errors, or an expression failed to evaluate |
| `2` | usage error, file/IO error, schema not available, or invalid JSON input |

`--show` (below) changes only what is displayed; it never changes the exit code.
Validity always depends on whether there are error-level findings.

---

## `bidsval validate`

Validate a BIDS dataset against the schema and report errors and warnings.

```
bidsval validate PATH [--schema SELECTOR] [--subject SUB] [--no-headers] [--recursive]
                      [--output-type TYPES] [--out-dir DIR] [--show LEVELS]
```

A dataset is valid when it has no errors. Errors are rule violations (a misplaced
or misnamed file, a required field that is missing, a value of the wrong type).
Warnings flag recommended-but-missing metadata and do not affect validity.

### Argument

| Argument | Meaning |
|---|---|
| `PATH` | path to the dataset root, the folder that holds `dataset_description.json` and the `sub-*` folders |

### Options

| Option | Default | Meaning |
|---|---|---|
| `--schema SELECTOR` | bundled latest | which schema to validate against. A BIDS version (e.g. `1.11.1`), `latest`, a URL, a local `schema.json`, or a YAML schema source directory. Run `bidsval schema` to list bundled versions. See [schema selection](schema-selection.md). |
| `--subject SUB` | all subjects | validate only this subject. Accepts `sub-01` or just `01` (the `sub-` prefix is added if missing). Files outside that subject are skipped. |
| `--no-headers` | (headers on) | skip NIfTI header checks. Headers are read by default (needs `nibabel`; skipped automatically if it is not installed). Pass this to validate faster on large datasets. |
| `--recursive` | off | also validate every BIDS dataset under `derivatives/` (each on its own); results are attached to the report's `derivatives`. |
| `--output-type TYPES` | `text` | comma-separated output formats: `text`, `json`, `sarif`, `html`, or `all`. Selecting more than one requires `--out-dir`. See [output formats](output-formats.md). |
| `--out-dir DIR` | (stdout) | write reports into this directory (created if needed), one `report.<ext>` per format. Required when more than one format is selected; a single format prints to stdout. |
| `--show LEVELS` | `error,warning` | severities to display: any of `error`, `warning`, `ignore`, or `all` (comma-separated). Filters the output only; it does not change validity or the exit code. |

### Output behaviour

`--output-type` chooses the format(s); `--out-dir` chooses where they go. They are
independent:

- **One format, no `--out-dir`**: the report prints to stdout (the default is the
  `text` summary). You can redirect it: `bidsval validate /data --output-type sarif > out.sarif`.
- **More than one format**: `--out-dir` is required. Each selected format is written
  to `DIR/report.<ext>` (`report.txt`, `report.json`, `report.sarif`, `report.html`),
  and the path of each file written is printed to stderr.
- `--output-type all` is shorthand for `text,json,sarif,html` and therefore also
  needs `--out-dir`.

In the **text** report, the run header is one line (`bidsval <version>  schema
<X>  BIDS <Y>`), then the dataset path, then one line per finding:

```
SEVERITY CODE [field] file - message
```

`field` (in brackets) is the specific JSON key or column the finding is about, when
applicable. The report ends with a count line (`N error(s), M warning(s)`) and a
`VALID` / `INVALID` verdict.

### Examples

```shell
# quick check (text summary; exits non-zero on errors, so it fits CI)
bidsval validate /data/my_study

# show everything, including warnings and suppressed notes
bidsval validate /data/my_study --show all

# show only errors
bidsval validate /data/my_study --show error

# check a single subject (the sub- prefix is optional)
bidsval validate /data/my_study --subject 01

# pin a schema version for reproducible results
bidsval validate /data/my_study --schema 1.10.0

# validate against the development tip of the schema (fetched and cached)
bidsval validate /data/my_study --schema latest

# skip NIfTI header reading (faster on large datasets)
bidsval validate /data/my_study --no-headers

# machine-readable JSON to stdout (for scripting)
bidsval validate /data/my_study --output-type json

# SARIF to a file by redirection (for code scanning)
bidsval validate /data/my_study --output-type sarif > my_study.sarif

# write JSON and HTML reports into ./reports/
bidsval validate /data/my_study --output-type json,html --out-dir ./reports

# write every format into ./reports/
bidsval validate /data/my_study --output-type all --out-dir ./reports
```

---

## `bidsval schema`

Show the schema bidsval would use and the versions bundled with this install.

```
bidsval schema [--schema SELECTOR]
```

Prints the BIDS version and the schema version a selector resolves to, plus the
list of bundled versions you can pass to `--schema` (here or on `validate`). Useful
to confirm what you are validating against, or to discover the available versions
before pinning one.

### Options

| Option | Default | Meaning |
|---|---|---|
| `--schema SELECTOR` | bundled latest | which schema to inspect. Same selector forms as `validate --schema`: a BIDS version, `latest`, a URL, a local `schema.json`, or a YAML schema source directory. |

### Output

```
BIDS version  : 1.11.1
schema version: 1.2.1
bundled       : 1.8.0, 1.9.0, 1.10.0, 1.11.1
```

`BIDS version` is the BIDS specification version; `schema version` is the schema's
own structural version. They travel together inside one schema artifact, so you
never choose them separately. See [schema selection](schema-selection.md).

### Examples

```shell
# the default (bundled latest) schema
bidsval schema

# a specific bundled version
bidsval schema --schema 1.10.0

# the development tip, fetched from the spec and cached
bidsval schema --schema latest

# a custom or forked schema from a local source directory
bidsval schema --schema /path/to/bids-specification/src/schema
```

---

## `bidsval eval`

Evaluate one BIDS schema expression against a context and print the result as JSON.

```
bidsval eval EXPR [--context JSON]
```

This exposes the same expression engine the validator uses, which is handy for
understanding a rule or testing a single condition. The result is printed as JSON
(`true`, `false`, a number, a string, `null`, ...). Undefined names evaluate to
`null`.

### Argument

| Argument | Meaning |
|---|---|
| `EXPR` | the expression to evaluate, e.g. `"suffix == 'T1w'"` |

### Options

| Option | Default | Meaning |
|---|---|---|
| `--context JSON` | `{}` | a JSON object providing the variables the expression can reference. Must be a JSON object, not an array or a scalar. |

### Operators

| Group | Operators |
|---|---|
| comparison | `==`  `!=`  `<`  `<=`  `>`  `>=` |
| logical | `&&`  `\|\|`  `!` |
| arithmetic | `+`  `-`  `*`  `/`  `%` |
| membership | `in` (key membership on an object, e.g. `"FlipAngle" in sidecar`) |

`&&` and `||` short-circuit and return the operand value (as in JavaScript), not a
coerced boolean. Equality treats `null` specially: `null` equals only `null`.

### Functions

The expression language has a fixed set of built-ins, all read by the validator
from the schema's rules:

`type`, `intersects`, `match`, `substr`, `min`, `max`, `length`, `unique`,
`count`, `index`, `allequal`, `sorted`, `exists`.

An unknown function (for example one introduced by a newer schema than this engine
knows) is reported as unknown rather than crashing.

### Examples

```shell
# a simple comparison
bidsval eval "suffix == 'T1w'" --context '{"suffix": "T1w"}'

# combine conditions with && and ||
bidsval eval "x > 0 && x < 10" --context '{"x": 5}'

# arithmetic and the modulo operator
bidsval eval "n % 2 == 0" --context '{"n": 4}'

# a built-in function
bidsval eval "length(channels) == 3" --context '{"channels": ["a", "b", "c"]}'

# undefined names are null (so this prints false)
bidsval eval "suffix == 'T1w'"
```

Exit code `1` means the expression failed to evaluate (a syntax error or an
unsupported construct). Exit code `2` means `--context` was not valid JSON or was
not a JSON object.

---

## Python API

Everything the CLI does is available in-process. See [usage](usage.md#python-api)
for `bidsval.validate`, `bidsval.validate_subject`, `bidsval.validate_file`, and
`bidsval.evaluate_string`, all of which return typed (pydantic) results.
