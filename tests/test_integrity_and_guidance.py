"""Tests for the file-integrity checks (malformed JSON, broken TSV structure) and
for the actionable, example-bearing guidance attached to findings."""

from __future__ import annotations

import json

from bidsval import validate
from bidsval.schema import DEFAULT_VERSION


def _dataset(root) -> None:
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": DEFAULT_VERSION})
    )


def _issues(report):
    out = list(report.dataset_issues.issues)
    for verdict in report.files:
        out.extend(verdict.issues)
    return out


def _codes(report):
    return {i.code for i in _issues(report)}


# --- JSON integrity -------------------------------------------------------


def test_malformed_dataset_description_is_reported_and_fields_not_flooded(tmp_path) -> None:
    # Invalid JSON (trailing comma); a sub so the run proceeds.
    (tmp_path / "dataset_description.json").write_text('{"Name": "t",}')
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")
    report = validate(tmp_path)
    codes = _codes(report)
    assert "JSON_INVALID" in codes
    # The malformed file must NOT also be flooded with missing-field findings.
    assert not any(c.startswith("JSON_KEY") for c in codes)
    # And the existing file is not reported missing.
    assert "MISSING_DATASET_DESCRIPTION" not in codes


def test_json_not_an_object(tmp_path) -> None:
    _dataset(tmp_path)
    anat = tmp_path / "sub-01" / "anat"
    anat.mkdir(parents=True)
    (anat / "sub-01_T1w.nii.gz").write_text("x")
    (anat / "sub-01_T1w.json").write_text(json.dumps(["not", "an", "object"]))
    report = validate(tmp_path)
    assert "JSON_NOT_AN_OBJECT" in _codes(report)


def test_valid_json_has_no_integrity_finding(tmp_path) -> None:
    _dataset(tmp_path)
    anat = tmp_path / "sub-01" / "anat"
    anat.mkdir(parents=True)
    (anat / "sub-01_T1w.nii.gz").write_text("x")
    (anat / "sub-01_T1w.json").write_text(json.dumps({"EchoTime": 0.03}))
    codes = _codes(validate(tmp_path))
    assert "JSON_INVALID" not in codes and "JSON_NOT_AN_OBJECT" not in codes


# --- TSV integrity --------------------------------------------------------


def test_tsv_duplicate_header(tmp_path) -> None:
    _dataset(tmp_path)
    (tmp_path / "participants.tsv").write_text("participant_id\tparticipant_id\nsub-01\tsub-01\n")
    assert "TSV_COLUMN_HEADER_DUPLICATE" in _codes(validate(tmp_path))


def test_tsv_ragged_row(tmp_path) -> None:
    _dataset(tmp_path)
    (tmp_path / "samples.tsv").write_text("a\tb\tc\n1\t2\n")
    assert "TSV_EQUAL_ROWS" in _codes(validate(tmp_path))


def test_tsv_empty_line(tmp_path) -> None:
    _dataset(tmp_path)
    (tmp_path / "samples.tsv").write_text("a\tb\n1\t2\n\n3\t4\n")
    assert "TSV_EMPTY_LINE" in _codes(validate(tmp_path))


def test_clean_tsv_has_no_integrity_finding(tmp_path) -> None:
    _dataset(tmp_path)
    (tmp_path / "participants.tsv").write_text("participant_id\nsub-01\n")
    codes = _codes(validate(tmp_path))
    assert not any(c.startswith("TSV_EQUAL") or c == "TSV_EMPTY_LINE" for c in codes)
    assert "TSV_COLUMN_HEADER_DUPLICATE" not in codes


# --- Actionable guidance --------------------------------------------------


def test_missing_required_field_suggestion_has_example(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    # A bold run with no sidecar: the schema requires RepetitionTime / TaskName.
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    required = [i for i in _issues(validate(tmp_path)) if i.code == "SIDECAR_KEY_REQUIRED"]
    assert required, "expected a required sidecar field to be missing"
    sample = required[0]
    assert sample.suggestion, "a missing-field finding must carry guidance"
    # The guidance names the field and shows a concrete JSON example.
    assert sample.sub_code and sample.sub_code in sample.suggestion
    assert "for example" in sample.suggestion and "{" in sample.suggestion


def test_value_error_suggestion_has_example(tmp_path) -> None:
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": DEFAULT_VERSION, "Authors": "a string"})
    )
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")
    value_errors = [
        i for i in _issues(validate(tmp_path)) if i.code == "JSON_SCHEMA_VALIDATION_ERROR"
    ]
    assert value_errors
    suggestion = value_errors[0].suggestion or ""
    assert "Authors" in suggestion and "for example" in suggestion
