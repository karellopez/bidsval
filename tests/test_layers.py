"""Tests for the content layers: JSON value validation, associations, tabular
columns, the empty-file check, sourcedata exclusion, and schema URL helpers."""

from __future__ import annotations

import json
import os

import pytest

from bidsval import validate
from bidsval.schema import DEFAULT_VERSION, cache


def _dataset(root) -> None:
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": DEFAULT_VERSION})
    )


def _codes(report, *, severity=None):
    out = []
    for issue in report.dataset_issues.issues:
        out.append((issue.severity.value, issue.code, issue.sub_code))
    for verdict in report.files:
        for issue in verdict.issues:
            out.append((issue.severity.value, issue.code, issue.sub_code))
    if severity:
        out = [c for c in out if c[0] == severity]
    return out


def test_json_value_type_validation(tmp_path) -> None:
    # Authors must be an array; a string is an error (matches the reference).
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": DEFAULT_VERSION, "Authors": "just a string"})
    )
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")
    report = validate(tmp_path)
    assert ("error", "JSON_SCHEMA_VALIDATION_ERROR", "Authors") in _codes(report)


def test_associations_dwi_bvec_bval(tmp_path) -> None:
    _dataset(tmp_path)
    dwi = tmp_path / "sub-01" / "dwi"
    dwi.mkdir(parents=True)
    (dwi / "sub-01_dwi.nii.gz").write_text("x")
    # Without .bval/.bvec the schema flags them missing.
    report = validate(tmp_path)
    codes = {c for _s, c, _ in _codes(report)}
    assert "DWI_MISSING_BVEC" in codes and "DWI_MISSING_BVAL" in codes
    # Add them and the errors go away (the finder resolves them).
    (dwi / "sub-01_dwi.bval").write_text("0 1000 1000\n")
    (dwi / "sub-01_dwi.bvec").write_text("0 1 0\n0 0 1\n0 0 0\n")
    codes = {c for _s, c, _ in _codes(validate(tmp_path))}
    assert "DWI_MISSING_BVEC" not in codes and "DWI_MISSING_BVAL" not in codes


def test_events_tsv_missing(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-go_bold.nii.gz").write_text("x")  # task data, no events.tsv
    report = validate(tmp_path)
    assert "EVENTS_TSV_MISSING" in {c for _s, c, _ in _codes(report)}


def test_tabular_additional_column_and_bad_value(tmp_path) -> None:
    _dataset(tmp_path)
    (tmp_path / "participants.tsv").write_text("participant_id\tundocumented\nsub-01\thi\n")
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    (func / "sub-01_task-rest_events.tsv").write_text("onset\tduration\nNOTNUM\t1\n")
    report = validate(tmp_path)
    codes = {(c, sub) for _s, c, sub in _codes(report)}
    assert ("TSV_ADDITIONAL_COLUMNS_UNDEFINED", "undocumented") in codes
    assert ("TSV_VALUE_INCORRECT_TYPE", "onset") in codes


def test_empty_file_is_a_warning_with_explanation(tmp_path) -> None:
    _dataset(tmp_path)
    anat = tmp_path / "sub-01" / "anat"
    anat.mkdir(parents=True)
    (anat / "sub-01_T1w.nii.gz").write_text("")  # 0 bytes
    report = validate(tmp_path)
    empty = [i for f in report.files for i in f.issues if i.code == "EMPTY_FILE"]
    assert empty and empty[0].severity.value == "warning"
    assert empty[0].suggestion and "placeholder" in empty[0].suggestion
    assert empty[0].fix is not None


def test_sourcedata_and_code_are_not_validated(tmp_path) -> None:
    _dataset(tmp_path)
    anat = tmp_path / "sub-01" / "anat"
    anat.mkdir(parents=True)
    (anat / "sub-01_T1w.nii.gz").write_text("x")
    src = tmp_path / "sourcedata" / "sub-01"
    src.mkdir(parents=True)
    (src / "raw.xyz").write_text("")  # would be flagged if validated
    report = validate(tmp_path)
    locations = [i.location for f in report.files for i in f.issues]
    assert not any("sourcedata" in (loc or "") for loc in locations)


def test_schema_url_helpers() -> None:
    assert cache.is_url("https://example.org/schema.json")
    assert not cache.is_url("1.11.1")
    assert cache.published_url("latest", ).endswith("/en/latest/schema.json")
    assert cache.published_url("1.10.0").endswith("/en/v1.10.0/schema.json")
    assert cache.published_url("/local/path") is None


@pytest.mark.skipif(
    os.environ.get("BIDSVAL_NETWORK_TESTS") != "1",
    reason="set BIDSVAL_NETWORK_TESTS=1 to run network fetch",
)
def test_resolve_latest_over_network() -> None:
    from bidsval.schema import bids_version, resolve

    schema = resolve("latest")
    assert bids_version(schema)  # fetched a real schema
