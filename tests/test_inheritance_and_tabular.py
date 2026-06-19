"""Tests for the inheritance findings (multiple inheritable files, field override)
and the remaining tabular checks (column order, invalid gzip)."""

from __future__ import annotations

import gzip
import json

from bidsval import validate
from bidsval.rules.tables import _initial_columns_order
from bidsval.schema import DEFAULT_VERSION


def _dataset(root) -> None:
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": DEFAULT_VERSION})
    )


def _codes(report):
    out = {i.code for i in report.dataset_issues.issues}
    for verdict in report.files:
        out.update(i.code for i in verdict.issues)
    return out


# --- column order (unit; mirrors the schema's initial_columns) -------------


def test_column_order_incorrect() -> None:
    rule = {"initial_columns": ["onset", "duration"], "columns": {"onset": "required"}}
    object_columns = {"onset": {"name": "onset"}, "duration": {"name": "duration"}}
    out_of_order = _initial_columns_order(
        rule, object_columns, {"duration": ["1"], "onset": ["2"]}, "f.tsv", "p"
    )
    assert any(i.code == "TSV_COLUMN_ORDER_INCORRECT" for i in out_of_order)
    in_order = _initial_columns_order(
        rule, object_columns, {"onset": ["1"], "duration": ["2"]}, "f.tsv", "p"
    )
    assert in_order == []


# --- invalid gzip ----------------------------------------------------------


def test_invalid_gzip(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_physio.tsv.gz").write_bytes(b"this is not gzip")
    assert "INVALID_GZIP" in _codes(validate(tmp_path))


def test_valid_gzip_not_flagged(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    with gzip.open(func / "sub-01_task-rest_physio.tsv.gz", "wb") as handle:
        handle.write(b"1\t2\t3\n")
    assert "INVALID_GZIP" not in _codes(validate(tmp_path))


# --- inheritance -----------------------------------------------------------


def test_multiple_inheritable_files(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    # Two sidecars in the same directory both apply, neither exactly.
    (func / "sub-01_bold.json").write_text(json.dumps({"EchoTime": 0.03}))
    (func / "task-rest_bold.json").write_text(json.dumps({"RepetitionTime": 2.0}))
    assert "MULTIPLE_INHERITABLE_FILES" in _codes(validate(tmp_path))


def test_sidecar_field_override(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    # A less specific (root) sidecar and a more specific one disagree on a field.
    (tmp_path / "task-rest_bold.json").write_text(json.dumps({"RepetitionTime": 2.0}))
    (func / "sub-01_task-rest_bold.json").write_text(json.dumps({"RepetitionTime": 3.0}))
    assert "SIDECAR_FIELD_OVERRIDE" in _codes(validate(tmp_path))


def test_consistent_sidecars_no_override(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    (tmp_path / "task-rest_bold.json").write_text(json.dumps({"RepetitionTime": 2.0}))
    (func / "sub-01_task-rest_bold.json").write_text(json.dumps({"TaskName": "rest"}))
    assert "SIDECAR_FIELD_OVERRIDE" not in _codes(validate(tmp_path))
