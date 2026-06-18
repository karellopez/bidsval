"""Validator tests against small synthetic datasets.

A handful of files written to a temp directory exercise the end-to-end path
(walk -> context -> rules -> report) deterministically, plus the inheritance
principle and the three granularities.
"""

from __future__ import annotations

import json

import pytest

from bidsval import validate, validate_file, validate_subject
from bidsval.context.inheritance import merged_sidecar
from bidsval.files import FileTree
from bidsval.schema import DEFAULT_VERSION, resolve


def _minimal_dataset(root, *, with_description=True) -> None:
    if with_description:
        (root / "dataset_description.json").write_text(
            json.dumps({"Name": "Test", "BIDSVersion": DEFAULT_VERSION})
        )
    anat = root / "sub-01" / "anat"
    anat.mkdir(parents=True)
    (anat / "sub-01_T1w.nii.gz").write_text("not a real nifti")
    (anat / "sub-01_T1w.json").write_text(json.dumps({"InstitutionName": "Somewhere"}))


def test_minimal_dataset_has_no_errors(tmp_path) -> None:
    _minimal_dataset(tmp_path)
    report = validate(tmp_path)
    errors = [i.code for f in report.files for i in f.issues if i.severity.value == "error"]
    assert report.is_valid, errors
    assert report.bids_version == DEFAULT_VERSION
    assert report.schema_version  # recorded


def test_missing_dataset_description_is_an_error(tmp_path) -> None:
    _minimal_dataset(tmp_path, with_description=False)
    report = validate(tmp_path)
    codes = {i.code for i in report.dataset_issues.issues}
    assert "MISSING_DATASET_DESCRIPTION" in codes
    assert not report.is_valid


def test_dataset_description_missing_required_field(tmp_path) -> None:
    # A missing required field is flagged by the schema's dataset_metadata rules
    # (no hardcoding), as an error on dataset_description.json.
    _minimal_dataset(tmp_path, with_description=False)
    (tmp_path / "dataset_description.json").write_text(json.dumps({"Name": "No version"}))
    report = validate(tmp_path)
    errors = [
        i
        for f in report.files
        for i in f.issues
        if i.severity.value == "error" and i.sub_code == "BIDSVersion"
    ]
    assert errors, "expected a required-field error for BIDSVersion"
    assert not report.is_valid


def test_no_subjects_warns(tmp_path) -> None:
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "Empty", "BIDSVersion": DEFAULT_VERSION})
    )
    report = validate(tmp_path)
    assert any(i.code == "NO_SUBJECTS" for i in report.dataset_issues.issues)


def test_validate_file_granularity(tmp_path) -> None:
    _minimal_dataset(tmp_path)
    verdict = validate_file(tmp_path, "sub-01/anat/sub-01_T1w.nii.gz")
    assert str(verdict.path) == "sub-01/anat/sub-01_T1w.nii.gz"
    assert verdict.severity is None or verdict.severity.value != "error"


def test_validate_file_not_found(tmp_path) -> None:
    _minimal_dataset(tmp_path)
    verdict = validate_file(tmp_path, "sub-99/anat/sub-99_T1w.nii.gz")
    assert any(i.code == "FILE_NOT_FOUND" for i in verdict.issues)


def test_validate_subject_filters(tmp_path) -> None:
    _minimal_dataset(tmp_path)
    (tmp_path / "sub-02" / "anat").mkdir(parents=True)
    (tmp_path / "sub-02" / "anat" / "sub-02_T1w.nii.gz").write_text("x")
    report = validate_subject(tmp_path, "01")
    subjects_seen = {str(f.path).split("/", 1)[0] for f in report.files if "/" in str(f.path)}
    assert subjects_seen == {"sub-01"}


def test_schema_version_selection_changes_report(tmp_path) -> None:
    _minimal_dataset(tmp_path)
    report = validate(tmp_path, schema="1.10.0")
    assert report.bids_version == "1.10.0"


def test_inheritance_merges_sidecars_most_specific_wins(tmp_path) -> None:
    root = tmp_path
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "X", "BIDSVersion": DEFAULT_VERSION})
    )
    func = root / "sub-01" / "func"
    func.mkdir(parents=True)
    data = func / "sub-01_task-rest_bold.nii.gz"
    data.write_text("x")
    # Top-level applies to all rest-bold; subject-level overrides one field.
    (root / "task-rest_bold.json").write_text(json.dumps({"RepetitionTime": 2.0, "EchoTime": 0.03}))
    (func / "sub-01_task-rest_bold.json").write_text(json.dumps({"EchoTime": 0.05}))

    tree = FileTree(root)
    merged = merged_sidecar(resolve(), tree, tree.get("sub-01/func/sub-01_task-rest_bold.nii.gz"))
    assert merged["RepetitionTime"] == 2.0   # inherited from the root sidecar
    assert merged["EchoTime"] == 0.05        # most specific (subject-level) wins


def test_inheritance_picks_one_sidecar_per_directory(tmp_path) -> None:
    # Within one directory, only the most specific applicable sidecar is used -
    # not the union of all subset matches.
    root = tmp_path
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "X", "BIDSVersion": DEFAULT_VERSION})
    )
    func = root / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    # Two same-directory candidates both subset-match the data file.
    (func / "sub-01_bold.json").write_text(json.dumps({"EchoTime": 0.03}))
    (func / "sub-01_task-rest_bold.json").write_text(json.dumps({"RepetitionTime": 2.0}))

    tree = FileTree(root)
    merged = merged_sidecar(resolve(), tree, tree.get("sub-01/func/sub-01_task-rest_bold.nii.gz"))
    assert merged.get("RepetitionTime") == 2.0   # the exact-match sidecar is used
    assert "EchoTime" not in merged              # the less-specific one is NOT merged in


def test_validator_never_raises_on_garbage(tmp_path) -> None:
    # Odd files must not crash the run.
    (tmp_path / "dataset_description.json").write_text("{ this is not valid json")
    weird = tmp_path / "sub-01" / "anat"
    weird.mkdir(parents=True)
    (weird / "sub-01_T1w.json").write_text("also not json")
    (weird / "not-a-bids-file.xyz").write_text("\x00\x01binary")
    report = validate(tmp_path)  # must return, not raise
    assert report is not None


@pytest.mark.parametrize("version", ["1.8.0", "1.9.0", "1.10.0", "1.10.1", "1.11.0", "1.11.1"])
def test_all_bundled_schema_versions_validate(tmp_path, version) -> None:
    _minimal_dataset(tmp_path)
    report = validate(tmp_path, schema=version)
    assert report.bids_version == version  # every bundled schema is usable
