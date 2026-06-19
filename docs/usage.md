# Usage

## Install

```shell
pip install -e ".[dev]"        # base + test/lint tooling
pip install -e ".[content]"    # add NIfTI/TSV readers (nibabel, pandas)
pip install -e ".[m-eeg]"      # add EEG/MEG recording readers (mne)
```

`bidsval` (core) depends only on `bidsschematools` and `pydantic`. The `content`
extra enables reading NIfTI headers and TSV columns; without it, those checks are
skipped rather than failing.

## Command line

```shell
bidsval validate <dataset>           # validate a dataset (text summary, exits non-zero on errors)
bidsval validate <dataset> --subject sub-01      # one subject
bidsval validate <dataset> --headers             # also check NIfTI headers (needs nibabel)
bidsval schema                       # show the resolved + bundled schema versions
bidsval eval "<expression>" --context '<json>'   # evaluate one schema expression
```

`bidsval validate` exits 0 when there are no errors, 1 when there are, and 2 on a
usage/IO error, so it drops straight into CI.

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
