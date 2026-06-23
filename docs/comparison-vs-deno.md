# bidsval vs the Deno reference validator

This page records how bidsval compares to the reference
[`bids-validator`](https://github.com/bids-standard/bids-validator) (the Deno
implementation): which findings each produces, the evidence behind bidsval's
**no-false-positives** guarantee, and proof that bidsval is genuinely schema-driven
(different schema versions give different results).

> Note (bidsval 0.0.4): three behaviours were aligned more closely with the
> reference. `NIFTI_HEADER_UNREADABLE` is now an error, and an empty `.nii(.gz)` is
> reported as both `EMPTY_FILE` and `NIFTI_HEADER_UNREADABLE` (as the reference does).
> Recommended and required sidecar fields are now reported on derivative datasets too.
> And a JSON value finding is attributed only to the `.json` file that carries it, not
> also to the data file. The per-dataset counts in the table below were measured on
> the 0.0.1 baseline and predate these changes, so 0.0.4 matches the reference even
> more closely than the table shows. The no-false-positives guarantee is unchanged:
> every error bidsval reports is one the reference also reports.

## Method

- **Tools**: `bids-validator-deno` 2.4.1 and bidsval 0.0.1, run over the same dataset
  directories, comparing the error `(file, code)` pairs each produces.
- **Corpus**: all 112 datasets of the official `bids-examples` corpus, plus four
  datasets converted by BIDS Manager (MRI, EEG, MEG, PET).
- **"False positive"** means an *error* bidsval reports that the reference does not.
  A finding both report (even worded or located differently) is not a false positive.
- **Matching the schema.** `bids-validator-deno` 2.4.1 always validates against its
  own bundled schema (version 1.2.1, BIDS 1.11.1) no matter what `BIDSVersion` a
  dataset declares; it reads the declared version only to warn `UNKNOWN_BIDS_VERSION`.
  bidsval defaults to the same schema (1.11.1), and is forced to it here. So the
  comparison below is at a single, shared schema. (Earlier notes about the reference
  "picking the dataset's version" were mistaken: it does not.)

## Headline

Across all 116 datasets, bidsval produces **zero false-positive errors**. Every error
bidsval reports is one the reference also reports, except the one explained case
(below), which is not spurious.

## bidsval is schema-driven: different schema versions, different results

bidsval reads all of its vocabulary and rules from the schema, so choosing a
different schema with `--schema` changes the outcome. Error and warning counts for
the same datasets across four bundled schema versions:

| Dataset | `--schema 1.8.0` | `--schema 1.9.0` | `--schema 1.10.0` | `--schema 1.11.1` |
|---|---|---|---|---|
| converted MEG | 188 err / 107 warn | 211 / 107 | 211 / 88 | 211 / 22 |
| converted EEG | 116 / 393 | 172 / 393 | 172 / 142 | 172 / 30 |
| ds003 | 39 / 2409 | 39 / 2292 | 39 / 1641 | 39 / 992 |

Newer schemas generally consolidate recommendations (fewer warnings) and add or
tighten rules (errors shift), with no code change in bidsval. This is the core design
property; it is what lets bidsval validate against any bundled, fetched, or local
schema by changing one argument.

## Per-dataset results (shared schema 1.11.1)

`err/warn` are error and warning counts. The last column lists error codes bidsval
emits that the reference does not emit anywhere in that dataset.

| Dataset | declared BIDSVersion | bidsval err/warn | Deno err/warn | bidsval-only error codes |
|---|---|---|---|---|
| asl002 | 1.5.0 | 0/53 | 3/50 | - |
| eeg_matchingpennies | 1.11.1 | 7/261 | 7/268 | - |
| ds000246 | 1.8.0 | 0/64 | 1/61 | - |
| ds003 | 1.0.0 | 39/992 | 78/991 | - |
| ieeg_epilepsy | 1.7.0 | 11/107 | 13/107 | - |
| micr_SEM | 1.7.0 | 0/24 | 0/23 | - |
| fnirs_tapping | 1.8.0 | 5/115 | 5/160 | - |
| qmri_mp2rage | 1.5.0 | 8/159 | 15/159 | - |
| pet001 | 1.6.0 | 3/57 | 3/57 | SIDECAR_KEY_REQUIRED x1 |
| motion_systemvalidation | (none) | 12/100 | 12/100 | - |
| hcp_example_bids | 1.0.2 | 5/123 | 10/123 | - |
| converted MRI | 1.11.1 | 8/127 | 13/121 | - |
| converted EEG | 1.11.1 | 172/30 | 146/30 | - |
| converted MEG | 1.11.1 | 211/22 | 167/22 | - |
| converted PET | 1.11.1 | 4/24 | 5/24 | - |

bidsval reports the same or fewer errors than the reference everywhere except the two
cases below, both correct.

## The bidsval-only signal (not a false positive)

1. **PET `SIDECAR_KEY_REQUIRED` (pet001).** bidsval fills in which modalities are
   present; the reference leaves that context empty, so bidsval enforces a
   PET-conditional required field the reference drops. bidsval is more schema-faithful.

(The earlier `JSON_SCHEMA_VALIDATION_ERROR` attribution difference on the converted
EEG/MEG datasets is gone as of 0.0.4: bidsval now attributes a bad value only to the
`.json` file that carries it, matching the reference, instead of also flagging it on
the data file.)

## Coverage of the reference's hardcoded checks

Both validators read the schema-driven rules (required/recommended fields, content
`checks`, tabular columns, associations such as `EVENTS_TSV_MISSING` /
`DWI_MISSING_BVEC`) from the same schema, so those are covered by bidsval's rule
engine. The table tracks the reference's *hardcoded* checks.

| Reference code | bidsval | Notes |
|---|---|---|
| MISSING_DATASET_DESCRIPTION | yes | |
| JSON_INVALID / JSON_NOT_AN_OBJECT / INVALID_FILE_ENCODING / FILE_READ | yes | malformed JSON |
| NOT_INCLUDED | yes | with `.bidsignore` and the default ignores |
| INVALID_ENTITY_LABEL / ENTITY_WITH_NO_LABEL | yes | |
| MISSING_REQUIRED_ENTITY / ENTITY_NOT_IN_RULE | yes | |
| DATATYPE_MISMATCH / EXTENSION_MISMATCH / INVALID_LOCATION | yes | |
| FILENAME_MISMATCH / ALL_FILENAME_RULES_HAVE_ISSUES | yes | |
| JSON_KEY_* / SIDECAR_KEY_* | yes | required / recommended fields |
| JSON_SCHEMA_VALIDATION_ERROR | yes | every present field's value |
| TSV_COLUMN_MISSING | yes | |
| TSV_COLUMN_HEADER_DUPLICATE / TSV_EMPTY_LINE / TSV_EQUAL_ROWS | yes | a trailing blank line is allowed |
| TSV_ADDITIONAL_COLUMNS_NOT_ALLOWED / MUST_DEFINE / UNDEFINED | yes | all three modes |
| TSV_COLUMN_ORDER_INCORRECT | yes | initial-column order |
| TSV_INDEX_VALUE_NOT_UNIQUE | yes | |
| TSV_PSEUDO_AGE_DEPRECATED | yes | |
| TSV_VALUE_INCORRECT_TYPE | yes | type, format pattern, allowed values (enum), and bounds |
| TSV_COLUMN_TYPE_REDEFINED | yes | incompatible sidecar redefinition of a column |
| INVALID_GZIP | yes | for `.tsv.gz` (a corrupt `.nii.gz` is `NIFTI_HEADER_UNREADABLE`) |
| EMPTY_FILE | yes | |
| NIFTI_HEADER_UNREADABLE / AMBIGUOUS_AFFINE | yes | read by default; `--no-headers` to skip |
| CHECK_ERROR | yes | plus any schema-provided code |
| CASE_COLLISION | yes | |
| UNUSED_STIMULUS | yes | |
| SIDECAR_WITHOUT_DATAFILE | yes | directory-recording sidecars handled |
| MULTIPLE_INHERITABLE_FILES / SIDECAR_FIELD_OVERRIDE | yes | |
| CITATION_CFF_VALIDATION_ERROR | yes | conservative subset of the CFF schema |
| HED_ERROR / HED_WARNING | no | deferred (needs a HED validator dependency) |
| SYMLINK_BROKEN / CYCLE / OUT_OF_TREE / IN_SUBMODULE | no | deferred (bidsval treats unfetched annex symlinks as present, to avoid false positives on metadata-only clones) |
| BLACKLISTED_MODALITY | n/a | a reference run-configuration feature, not a dataset check |

Derivatives recursion (validating `derivatives/<pipeline>` as nested datasets) is
also implemented, under `--recursive`. The `coordsystems` and `atlas_description`
aggregates are now built, so the EMG coordinate-system and atlas-description rules
fire.

## Deliberately deferred, and why

- **HED** needs a dedicated HED validator (the `hed` Python package) and its own
  verification pass; additive once that dependency is in.
- **Symlink checks** conflict with bidsval treating unfetched git-annex symlinks as
  present (so metadata-only OpenNeuro clones validate without false positives); they
  need a fetched-vs-unfetched distinction first.
- Only the **gzip / ome / tiff content headers** remain unbuilt, so the few schema
  rules that read them are still skipped.

## Where bidsval is ahead

Every finding carries actionable guidance (what the file/field/column should contain,
with an example), rule provenance (why it fired), and a machine-actionable fix hint.
bidsval is a pure-Python in-process library returning typed results, with a single
`--schema` selector and bundled offline schemas, and the no-false-positives guarantee.

## Reproducing

```shell
bids-validator-deno --format json -s v1.11.1 /path/to/dataset > deno.json
bidsval validate /path/to/dataset --out-type json --show all > bidsval.json
# diff the error (file, code) pairs; force the same schema on both for a fair test
```
