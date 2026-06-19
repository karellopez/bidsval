# Usage

## Install

```shell
pip install -e .               # bidsval and all required readers (nibabel, pandas, mne)
pip install -e ".[dev]"        # also the test and lint tooling
```

bidsval requires `bidsschematools` and `pydantic` (the schema engine and the typed
result model) plus the content readers `nibabel`, `pandas`, and `mne`, so a default
install can read NIfTI headers, TSV columns, and EEG/MEG recordings out of the box.
If a reader is ever missing, or a file is malformed, the affected check is skipped
rather than failing. See [how it works: dependencies](internals.md#5-dependencies-and-why-they-are-what-they-are).

## Command line

```shell
bidsval validate <dataset>           # validate a dataset (text summary, exits non-zero on errors)
bidsval validate <dataset> --subject sub-01      # one subject
bidsval validate <dataset> --no-headers          # skip NIfTI header checks (read by default)
bidsval schema                       # show the resolved + bundled schema versions
bidsval eval "<expression>" --context '<json>'   # evaluate one schema expression
```

`bidsval validate` exits 0 when there are no errors, 1 when there are, and 2 on a
usage/IO error, so it drops straight into CI.

The [CLI reference](cli-reference.md) documents every command and option in full.
Selecting output and which findings to show is covered in
[output formats](output-formats.md); selecting a schema in
[schema selection](schema-selection.md).

## Python API

```python
import bidsval

report = bidsval.validate("/path/to/dataset")     # ValidationReport
report.is_valid                                    # False if any errors
report.counts                                      # {'error': N, 'warning': M, 'ignore': K}
for verdict in report.files:
    for issue in verdict.issues:
        print(issue.severity.value, issue.code, verdict.path, issue.message)

bidsval.validate_subject("/path/to/dataset", "sub-01")
bidsval.validate_file("/path/to/dataset", "sub-01/anat/sub-01_T1w.nii.gz")
```

`validate`, `validate_subject`, and `validate_file` accept `schema=`,
`read_headers=`, and (for `validate`) `subjects=` and `max_rows=`.

Results are pydantic models, so `report.model_dump()` /
`bidsval.render.to_json(report)` give plain serialisable data.

## The expression engine on its own

```python
from bidsval import evaluate_string

evaluate_string("suffix == 'T1w'", {"suffix": "T1w"})                        # True
evaluate_string("nifti_header.dim[0] == 3", {"nifti_header": {"dim": [4]}})  # False
```
