# bidsval

Validate [BIDS](https://bids.neuroimaging.io) datasets in pure Python.

`bidsval` reads the official BIDS schema and checks datasets against the rules it
contains. It runs in-process with no external runtime, returns typed (pydantic)
results, and validates a whole dataset, a single subject, a single file, or a
single expression. Every published BIDS schema version ships inside the package,
so it works offline and you choose the version with one argument.

Because the schema drives everything, `bidsval` covers all of BIDS - anatomical,
functional, diffusion, fieldmaps, perfusion, EEG, MEG, iEEG, behavioural, PET,
microscopy, motion, NIRS, MRS - not a fixed set of modalities. Point it at a
newer schema and the newer rules apply with no code change.

> Working and tested against real MRI, EEG, MEG, and PET datasets and the
> official `bids-examples` corpus, with zero false positives versus the reference
> validator. It checks file structure, sidecar fields (presence and value type),
> associated files (events, bval/bvec, channels, ASL, ...), and tabular columns.
> Full coverage parity with the reference is still in progress; see "Roadmap".

## Install

```shell
pip install -e .                 # bidsval and all required readers (nibabel, pandas, mne)
pip install -e ".[dev]"          # also the test and lint tooling
```

## Validate a dataset

From Python:

```python
import bidsval

report = bidsval.validate("/path/to/dataset")
report.is_valid            # False if there are any errors
report.counts              # {'error': 3, 'warning': 27, 'ignore': 0}
for verdict in report.files:
    for issue in verdict.issues:
        print(issue.severity.value, issue.code, verdict.path, issue.message)

# Narrower granularity:
bidsval.validate_subject("/path/to/dataset", "sub-01")
bidsval.validate_file("/path/to/dataset", "sub-01/anat/sub-01_T1w.nii.gz")
```

From the command line:

```shell
# Text summary to the terminal (exits non-zero on errors, so it drops into CI):
bidsval validate /path/to/dataset

# Validate one subject; also check NIfTI headers:
bidsval validate /path/to/dataset --subject sub-01 --headers

# Pick the output type (independent of where it goes):
bidsval validate /path/to/dataset --output-type json     # JSON to stdout
bidsval validate /path/to/dataset --output-type sarif    # SARIF to stdout (CI / IDE code scanning)

# Write report files: --out-dir holds report.<ext> for each selected type:
bidsval validate /path/to/dataset --output-type html --out-dir reports/   # reports/report.html
bidsval validate /path/to/dataset --output-type all  --out-dir reports/   # report.txt/.json/.sarif/.html

# Show only the severities you care about (does not change pass/fail):
bidsval validate /path/to/dataset --show error           # errors only
```

Flags: `--schema <version|url|path>`, `--subject sub-01`, `--headers`
(also check NIfTI headers, needs nibabel), `--output-type text|json|sarif|html|all`
(default `text`; one type prints to stdout, several need `--out-dir`),
`--out-dir DIR` (write `report.<ext>` per type), `--show error,warning,ignore,all`
(filter displayed findings; default `error,warning`).

## Choose a schema version

Every published BIDS schema is bundled, and any other version or a URL is fetched
and cached. One argument selects the schema; everything downstream is unchanged:

```python
bidsval.validate("/data", schema="1.10.0")               # a bundled version
bidsval.validate("/data", schema="latest")               # the development tip (fetched)
bidsval.validate("/data", schema="https://.../schema.json")  # any URL (fetched + cached)
bidsval.validate("/data", schema="/path/to/schema.json") # a local dereferenced schema.json
bidsval.validate("/data", schema="/path/to/src/schema")  # a YAML schema source directory
bidsval.available_versions()                             # bundled: ['1.8.0', ... '1.11.1']
```

```shell
bidsval validate /data --schema 1.9.0
bidsval validate /data --schema latest
bidsval validate /data --schema https://bids-specification.readthedocs.io/en/v1.10.0/schema.json
bidsval schema --schema 1.10.0      # show the versions a selector resolves to
```

## Evaluate a single expression

The expression engine is usable on its own - handy for understanding a rule or
checking one condition:

```python
from bidsval import evaluate_string

evaluate_string("suffix == 'T1w'", {"suffix": "T1w"})                       # True
evaluate_string("nifti_header.dim[0] == 3", {"nifti_header": {"dim": [4]}}) # False
```

```shell
bidsval eval "suffix == 'T1w'" --context '{"suffix": "T1w"}'
```

## How it works

- The schema is the engine. The BIDS schema expresses validation logic as
  expressions: selectors that decide when a rule applies (`suffix == 'T1w'`) and
  checks that must hold (`nifti_header.dim[0] == 3`). `bidsval` reads the schema's
  vocabulary (datatypes, entities, suffixes, extensions) and rules, builds a
  context for each file, and evaluates the rules against it. No BIDS terms are
  hardcoded.
- Parsing comes from `bidsschematools`; `bidsval` adds the evaluator that walks
  the syntax tree (no `eval`/`exec`), the file/context layers, and the rule loop.
- A finding is reported only when a rule produces a determinate failure. When the
  context cannot determine a rule (for example a check that needs a content layer
  not yet built), the rule is skipped rather than guessed, so the validator does
  not emit false errors.
- Results are pydantic models, ready to serialise to JSON or bind to a GUI.

## Layout

| Module | Responsibility |
|---|---|
| `bidsval.schema` | Resolve a selector to one schema object; read BIDS vocabulary from it. The only version-aware code. |
| `bidsval.files` | Index a dataset's files (`FileTree`). |
| `bidsval.context` | Build the per-file context: entities, datatype, inheritance-merged sidecar, associated files, loaded content. |
| `bidsval.expr` | Evaluate BIDS schema expressions against a context. |
| `bidsval.rules` | Apply the schema's checks, sidecar fields (presence + value type), and tabular-column rules; plus bespoke checks. |
| `bidsval.validate` | `validate` / `validate_subject` / `validate_file`. |
| `bidsval.render` | Render a report as text / JSON / SARIF / HTML. |
| `bidsval.issues` / `bidsval.report` | Typed findings and results. |
| `bidsval.cli` | The `bidsval` command. |

Done: schema engine; file/context/rule layers; dataset/subject/file validation;
JSON sidecar field presence and value-type checks; the associations layer
(events, bval/bvec, channels, ASL, coordsystem, ...); tabular-column checks;
empty-file / unreadable-NIfTI checks; bundled + URL + `latest` schema selection;
text / JSON / SARIF / HTML outputs.

## Roadmap

Filename/path legality, file integrity, the cross-file and tabular checks, inheritance
checks, CITATION.cff, and derivatives recursion are all in (see
[comparison vs the Deno reference validator](docs/comparison-vs-deno.md) for full
coverage). Remaining:

1. Deferred reference checks: HED (needs a HED validator dependency), symlink checks
   (the annex-symlink tension), `TSV_COLUMN_TYPE_REDEFINED`, and the enum/string value
   checks for `TSV_VALUE_INCORRECT_TYPE`.
2. The `coordsystems` / `atlas_description` aggregates (and gzip/ome/tiff headers) the
   engine currently skips.
3. The ahead-of-market features: requirement-level completeness per subject, reasoned
   waivers, explain mode, and one-click fixes (provenance and fix hints are already on
   every finding).

## Documentation

See [`docs/`](docs/index.md):

- [usage](docs/usage.md) - install, the CLI, the Python API.
- [CLI reference](docs/cli-reference.md) - every command and option, with examples and exit codes.
- [schema selection](docs/schema-selection.md) - the single `--schema` selector.
- [output formats](docs/output-formats.md) - `--output-type`, `--out-dir`, `--show`.
- [how it works](docs/internals.md) - the complete technical reference: design, dependencies, every layer, flowcharts, and a glossary.
- [comparison vs the Deno reference validator](docs/comparison-vs-deno.md) - coverage, results, and the no-false-positives evidence.

## Develop

```shell
pytest                                  # unit suite, incl. the schema expression oracle
BIDSVAL_REAL_DATA=1 pytest tests/test_real_data.py   # real-data validation (if datasets present)
ruff check src tests
```

## License

MIT. See [LICENSE](LICENSE).
