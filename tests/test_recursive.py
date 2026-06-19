"""Tests for derivatives recursion."""

from __future__ import annotations

import json

from bidsval import validate
from bidsval.schema import DEFAULT_VERSION


def _dd(path, name, derivative=False) -> None:
    data = {"Name": name, "BIDSVersion": DEFAULT_VERSION}
    if derivative:
        data["GeneratedBy"] = [{"Name": "pipeline"}]
    path.write_text(json.dumps(data))


def test_derivatives_not_validated_without_recursive(tmp_path) -> None:
    _dd(tmp_path / "dataset_description.json", "parent")
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")
    deriv = tmp_path / "derivatives" / "mypipe"
    (deriv / "sub-01" / "anat").mkdir(parents=True)
    _dd(deriv / "dataset_description.json", "deriv", derivative=True)
    (deriv / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")

    report = validate(tmp_path)
    assert report.derivatives == {}


def test_derivatives_validated_with_recursive(tmp_path) -> None:
    _dd(tmp_path / "dataset_description.json", "parent")
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")
    deriv = tmp_path / "derivatives" / "mypipe"
    (deriv / "sub-01" / "anat").mkdir(parents=True)
    _dd(deriv / "dataset_description.json", "deriv", derivative=True)
    (deriv / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")

    report = validate(tmp_path, recursive=True)
    assert "mypipe" in report.derivatives
    # The derivative is itself a ValidationReport.
    assert report.derivatives["mypipe"].bids_version


def test_non_bids_derivative_skipped(tmp_path) -> None:
    _dd(tmp_path / "dataset_description.json", "parent")
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")
    # A derivatives subfolder with no dataset_description.json is not a BIDS dataset.
    nonbids = tmp_path / "derivatives" / "rawoutput"
    nonbids.mkdir(parents=True)
    (nonbids / "notes.txt").write_text("free-form output")

    report = validate(tmp_path, recursive=True)
    assert "rawoutput" not in report.derivatives
