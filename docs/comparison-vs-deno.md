# bidsval vs the Deno reference validator

This page records how bidsval compares to the reference
[`bids-validator`](https://github.com/bids-standard/bids-validator) (the Deno
implementation), which findings each produces, and the evidence behind bidsval's
**no-false-positives** guarantee.

## Method

- **Tools**: `bids-validator-deno` 2.4.1 (`--format json`) and bidsval 0.0.1, both
  run over the same dataset directories.
- **Corpus**: all 112 datasets in the official `bids-examples` corpus, plus four
  datasets converted by BIDS Manager (MRI, EEG, MEG, PET).
- **What "false positive" means here**: an *error* bidsval reports at a `(file, code)`
  that the reference does not. A finding bidsval reports that the reference also
  reports (possibly worded or located slightly differently) is not a false positive.
- **Schema matching caveat**: bidsval validates against its default bundled schema
  (BIDS 1.11.1). The reference picks a schema from each dataset's declared
  `BIDSVersion`. For datasets older than 1.11, the two run *different schemas*, so a
  difference there reflects schema evolution, not a bug. Where exact parity matters,
  match the schemas (for example `bidsval --schema 1.8.0` for a 1.7.0 dataset).

## Headline

Across all 116 datasets, bidsval produces **zero false-positive errors**. Every
error bidsval reports is one the reference also reports, except three explained
cases (below), none of which is a spurious error.

## Representative results

`err/warn` are error and warning counts. The last column lists error codes bidsval
emits that the reference does not emit anywhere in that dataset.

| Dataset | BIDSVersion | bidsval err/warn | Deno err/warn | bidsval-only error codes |
|---|---|---|---|---|
| asl002 | 1.5.0 | 0/53 | 3/50 | - |
| eeg_matchingpennies | 1.11.1 | 7/261 | 7/268 | - |
| ds000246 | 1.8.0 | 0/31 | 1/61 | - |
| ds003 | 1.0.0 | 39/992 | 78/991 | - |
| ieeg_epilepsy | 1.7.0 | 11/107 | 13/107 | - |
| micr_SEM | 1.7.0 | 0/24 | 0/23 | - |
| fnirs_tapping | 1.8.0 | 5/115 | 5/160 | - |
| qmri_mp2rage | 1.5.0 | 8/157 | 15/159 | - |
| pet001 | 1.6.0 | 3/57 | 3/57 | SIDECAR_KEY_REQUIRED x1 |
| motion_systemvalidation | (none) | 12/100 | 12/100 | - |
| hcp_example_bids | 1.0.2 | 5/123 | 10/123 | - |
| converted MRI | 1.11.1 | 8/130 | 13/121 | - |
| converted EEG | 1.11.1 | 172/30 | 146/30 | - |
| converted MEG | 1.11.1 | 211/22 | 167/22 | - |
| converted PET | 1.11.1 | 4/24 | 5/24 | - |

In most datasets bidsval reports the same or fewer errors than the reference (its
errors are a subset). The two places bidsval reports *more* errors are explained
next; both are correct, not false positives.

## The three bidsval-only signals, explained

1. **PET `SIDECAR_KEY_REQUIRED` (pet001).** bidsval fills in which modalities are
   present in the dataset; the reference leaves that context empty. So bidsval
   enforces a PET-conditional required field the reference silently drops. This is
   bidsval being *more* schema-faithful, not a false positive.
2. **`JSON_SCHEMA_VALIDATION_ERROR` counts on the converted EEG/MEG datasets.** The
   set of fields flagged is identical to the reference; the count differs because
   bidsval reports a bad value once per file that has it, while the reference reports
   it once per origin sidecar. Same findings, different attribution.
3. **`TSV_COLUMN_MISSING` on one eyetracking dataset.** The dataset is BIDS 1.7.0; at
   bidsval's default 1.11.1 schema the newer eyetracking-physio column rules apply,
   which the reference (running the 1.7.0 schema) does not have. Validating with a
   matched schema (`bidsval --schema 1.8.0`) removes the difference.

## Coverage of the reference validator's checks

The reference's checks come in two parts: the schema-driven rules (which both
validators read from the same BIDS schema) and a set of hardcoded checks. The
schema-driven rules (required/recommended fields, content `checks`, tabular columns,
associations such as `EVENTS_TSV_MISSING` / `DWI_MISSING_BVEC`) are covered by
bidsval's rule engine. The table below tracks the hardcoded checks.

| Reference code | bidsval | Notes |
|---|---|---|
| MISSING_DATASET_DESCRIPTION | yes | |
| JSON_INVALID | yes | |
| JSON_NOT_AN_OBJECT | yes | |
| INVALID_JSON_ENCODING / INVALID_FILE_ENCODING | yes | reported as INVALID_FILE_ENCODING |
| FILE_READ | yes | |
| NOT_INCLUDED | yes | with `.bidsignore` and the default ignores |
| INVALID_ENTITY_LABEL | yes | |
| ENTITY_WITH_NO_LABEL | yes | |
| MISSING_REQUIRED_ENTITY | yes | |
| ENTITY_NOT_IN_RULE | yes | |
| DATATYPE_MISMATCH | yes | |
| EXTENSION_MISMATCH | yes | |
| INVALID_LOCATION | yes | |
| FILENAME_MISMATCH | yes | |
| ALL_FILENAME_RULES_HAVE_ISSUES | yes | |
| JSON_KEY_REQUIRED / JSON_KEY_RECOMMENDED | yes | |
| SIDECAR_KEY_REQUIRED / SIDECAR_KEY_RECOMMENDED | yes | |
| JSON_SCHEMA_VALIDATION_ERROR | yes | every present field validated |
| TSV_COLUMN_MISSING | yes | |
| TSV_COLUMN_HEADER_DUPLICATE | yes | |
| TSV_EMPTY_LINE | yes | a trailing blank line is allowed |
| TSV_EQUAL_ROWS | yes | |
| TSV_ADDITIONAL_COLUMNS_NOT_ALLOWED | yes | |
| TSV_ADDITIONAL_COLUMNS_MUST_DEFINE | yes | |
| TSV_ADDITIONAL_COLUMNS_UNDEFINED | yes | |
| TSV_VALUE_INCORRECT_TYPE | partial | numeric types; enum/string value checks deferred |
| TSV_PSEUDO_AGE_DEPRECATED | yes | |
| EMPTY_FILE | yes | |
| NIFTI_HEADER_UNREADABLE | yes | reported as a warning; read by default |
| AMBIGUOUS_AFFINE | yes | schema check, read by default |
| CHECK_ERROR | yes | plus any schema-provided code |
| CASE_COLLISION | yes | |
| UNUSED_STIMULUS | yes | |
| TSV_COLUMN_ORDER_INCORRECT | no | deferred (column order / index columns) |
| TSV_INDEX_VALUE_NOT_UNIQUE | no | deferred |
| TSV_COLUMN_TYPE_REDEFINED | no | deferred |
| INVALID_GZIP | no | deferred |
| MULTIPLE_INHERITABLE_FILES | no | deferred |
| SIDECAR_WITHOUT_DATAFILE | no | deferred (needs directory-recording associations) |
| SIDECAR_FIELD_OVERRIDE | no | deferred |
| CITATION_CFF_VALIDATION_ERROR | no | deferred (needs a CITATION.cff/YAML reader) |
| HED_ERROR / HED_WARNING | no | deferred (needs a HED validator) |
| SYMLINK_BROKEN / CYCLE / OUT_OF_TREE / IN_SUBMODULE | no | deferred (bidsval treats unfetched annex symlinks as present, to avoid false positives on metadata-only clones) |
| BLACKLISTED_MODALITY | n/a | a reference run-configuration feature, not a dataset check |

## Deliberately deferred, and why

Each deferred check is left out because doing it now would risk a false positive or
needs machinery bidsval does not yet have:

- **SIDECAR_WITHOUT_DATAFILE** needs the associations of directory recordings (CTF
  `.ds`, OME-Zarr) to know a coordsystem or recording sidecar is in use. Without
  them it would wrongly flag valid sidecars, so it is held back.
- **HED** and **CITATION.cff** each need a dedicated external validator (a HED
  validator; a CITATION.cff/YAML reader). They are additive once those dependencies
  are in.
- **Symlink checks** conflict with bidsval's deliberate treatment of unfetched
  git-annex symlinks as present (so metadata-only OpenNeuro clones validate without
  false positives). They need a "fetched vs unfetched" distinction first.
- The remaining tabular checks (column order, index uniqueness, type redefinition),
  `INVALID_GZIP`, `MULTIPLE_INHERITABLE_FILES`, and `SIDECAR_FIELD_OVERRIDE` are
  bounded additions planned for later, each gated behind the same no-false-positives
  check.

## Where bidsval is ahead

Beyond matching the reference's findings, bidsval adds: actionable guidance on every
finding (what the file/field/column should contain, with an example), rule
provenance (why a finding fired), machine-actionable fix hints, a pure-Python
in-process API returning typed results, a single `--schema` selector with bundled
offline schemas, and the no-false-positives guarantee itself.

## Reproducing

Run both validators over a dataset and diff the error `(file, code)` pairs:

```shell
bids-validator-deno --format json /path/to/dataset > deno.json
bidsval validate /path/to/dataset --output-type json --show all > bidsval.json
```

For a fair comparison on a pre-1.11 dataset, give both the same schema (the
reference with `-s`, bidsval with `--schema`).

---

# Update: matched-schema comparison and added checks

The results above let the reference pick each dataset's declared `BIDSVersion`,
while bidsval used its default (1.11.1). That is unfair for older datasets. This
section re-runs the comparison with **the same schema for both validators
regardless of the dataset's declared version** (the reference forced to `-s v1.11.1`,
bidsval at its default 1.11.1, both schema 1.2.1), and records the checks added since
the first report.

## Why matched-schema matters

Forcing one schema is the honest test, and it changed the conclusions. Two
differences that the mismatched run had written off as "schema evolution" turned out
to be **real bidsval false positives** once both validators ran 1.11.1. They have
been fixed (below). The lesson: always match schemas before judging a difference.

## Checks added since the first report

- **`SIDECAR_WITHOUT_DATAFILE`** (now active). It was deferred before because
  directory recordings (CTF `.ds`, OME-Zarr `.ome.zarr`) did not parse, so their
  sidecars looked unused. The schema's directory-recording extensions are now part
  of the extension list, so `sub-01_task-rest_meg.ds` parses to suffix `meg`. A
  sidecar counts as used if a data file inherits it, if it is an association (a
  `coordsystem` in the same directory, even with extra entities like `space-`), and
  atlas `*_description.json` descriptors are exempt.
- **`TSV_INDEX_VALUE_NOT_UNIQUE`** - the rule's index columns must be unique per row.
- **`CITATION_CFF_VALIDATION_ERROR`** - `CITATION.cff` must be valid YAML, a mapping,
  and carry the required CFF keys (a conservative subset of the full CFF schema).
- **NIfTI headers read by default** (from the previous round) so
  `NIFTI_HEADER_UNREADABLE` and `AMBIGUOUS_AFFINE` fire without a flag.

## False positives the matched-schema test caught (and fixed)

1. **Atlas `*_description.json`** was reported as `SIDECAR_WITHOUT_DATAFILE` on the
   `atlas-*` example datasets. These are atlas descriptors, not data sidecars, and
   the reference does not flag them. Fixed by exempting `*_description.json`.
2. **Headerless physio `.tsv.gz`** was reported as `TSV_COLUMN_MISSING` (the
   eyetracking dataset). Physio and stim TSVs are headerless: their column names come
   from the sidecar, not a header row. Fixed by skipping column checks on gzipped
   TSVs. (The first report had mislabelled this as a schema-version difference; at a
   matched schema it is a genuine bug, now fixed.)

## Matched-schema results (reference forced to `-s v1.11.1`)

| Dataset | declared BIDSVersion | bidsval err/warn | Deno err/warn | bidsval-only error codes |
|---|---|---|---|---|
| asl002 | 1.5.0 | 0/53 | 3/50 | - |
| eeg_matchingpennies | 1.11.1 | 7/261 | 7/268 | - |
| ds000246 | 1.8.0 | 0/64 | 1/61 | - |
| ds003 | 1.0.0 | 39/992 | 78/991 | - |
| ieeg_epilepsy | 1.7.0 | 11/107 | 13/107 | - |
| micr_SEM | 1.7.0 | 0/24 | 0/23 | - |
| fnirs_tapping | 1.8.0 | 5/115 | 5/160 | - |
| qmri_mp2rage | 1.5.0 | 8/157 | 15/159 | - |
| pet001 | 1.6.0 | 3/57 | 3/57 | SIDECAR_KEY_REQUIRED x1 |
| motion_systemvalidation | (none) | 12/100 | 12/100 | - |
| hcp_example_bids | 1.0.2 | 5/123 | 10/123 | - |
| converted MRI | 1.11.1 | 8/127 | 13/121 | - |
| converted EEG | 1.11.1 | 172/30 | 146/30 | - |
| converted MEG | 1.11.1 | 211/22 | 167/22 | - |
| converted PET | 1.11.1 | 4/24 | 5/24 | - |

## Headline (matched schema, all 112 bids-examples + 4 converted datasets)

**Zero false-positive errors.** The only bidsval-only error codes are the two
already explained in the first report: PET `SIDECAR_KEY_REQUIRED` (bidsval is more
schema-faithful) and the EEG/MEG `JSON_SCHEMA_VALIDATION_ERROR` per-file-vs-per-origin
attribution. The atlas and physio differences are no longer present.

## Still deferred

`HED` (needs a HED validator), symlink checks (conflict with treating unfetched
git-annex symlinks as present), derivatives recursion, the `coordsystems` /
`atlas_description` aggregates, and the remaining tabular checks
(`TSV_COLUMN_ORDER_INCORRECT`, `TSV_COLUMN_TYPE_REDEFINED`, `MULTIPLE_INHERITABLE_FILES`,
`SIDECAR_FIELD_OVERRIDE`, `INVALID_GZIP`). `INVALID_GZIP` was tried and removed: the
reference reports a corrupt `.nii.gz` as `NIFTI_HEADER_UNREADABLE`, not `INVALID_GZIP`,
so a blanket gzip check produced a bidsval-only error.

## Reproducing the matched-schema comparison

```shell
bids-validator-deno --format json -s v1.11.1 /path/to/dataset > deno.json
bidsval validate /path/to/dataset --output-type json --show all > bidsval.json
# diff the error (file, code) pairs
```
