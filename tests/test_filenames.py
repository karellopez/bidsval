"""Tests for filename/path legality (ported from the reference validator) and for
.bidsignore handling."""

from __future__ import annotations

import json

from bidsval import validate
from bidsval.schema import DEFAULT_VERSION


def _codes(tmp_path, *files: str, bidsignore: str | None = None) -> set[str]:
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": DEFAULT_VERSION})
    )
    if bidsignore is not None:
        (tmp_path / ".bidsignore").write_text(bidsignore)
    for rel in files:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    report = validate(tmp_path)
    out = {i.code for i in report.dataset_issues.issues}
    for verdict in report.files:
        out.update(i.code for i in verdict.issues)
    return out


def test_unrecognized_file_is_not_included(tmp_path) -> None:
    assert "NOT_INCLUDED" in _codes(tmp_path, "sub-01/anat/sub-01_bogus.nii.gz")


def test_bidsignore_suppresses_not_included(tmp_path) -> None:
    codes = _codes(
        tmp_path, "sub-01/anat/sub-01_bogus.nii.gz", bidsignore="*_bogus.nii.gz\n"
    )
    assert "NOT_INCLUDED" not in codes


def test_container_directory_files_not_checked(tmp_path) -> None:
    # stimuli/ is a schema container directory; its files are not name-checked.
    assert "NOT_INCLUDED" not in _codes(tmp_path, "stimuli/left_hand.png")


def test_datatype_mismatch(tmp_path) -> None:
    # A T1w (anat suffix) placed in a func directory.
    assert "DATATYPE_MISMATCH" in _codes(tmp_path, "sub-01/func/sub-01_T1w.nii.gz")


def test_extension_mismatch(tmp_path) -> None:
    # T1w with a known-but-wrong extension for anat.
    assert "EXTENSION_MISMATCH" in _codes(tmp_path, "sub-01/anat/sub-01_T1w.tsv")


def test_invalid_entity_label(tmp_path) -> None:
    # run must be an index (digits); 'XX' is invalid.
    assert "INVALID_ENTITY_LABEL" in _codes(tmp_path, "sub-01/anat/sub-01_run-XX_T1w.nii.gz")


def test_entity_with_no_label(tmp_path) -> None:
    assert "ENTITY_WITH_NO_LABEL" in _codes(tmp_path, "sub-01/anat/sub-01_acq-_T1w.nii.gz")


def test_entity_not_in_rule(tmp_path) -> None:
    # 'dir' (phase-encoding) is not an anat entity.
    assert "ENTITY_NOT_IN_RULE" in _codes(tmp_path, "sub-01/anat/sub-01_dir-AP_T1w.nii.gz")


def test_filename_mismatch_on_reordered_entities(tmp_path) -> None:
    assert "FILENAME_MISMATCH" in _codes(tmp_path, "sub-01/anat/acq-hi_sub-01_T1w.nii.gz")


def test_valid_file_has_no_filename_findings(tmp_path) -> None:
    codes = _codes(tmp_path, "sub-01/anat/sub-01_T1w.nii.gz")
    for code in (
        "NOT_INCLUDED",
        "DATATYPE_MISMATCH",
        "EXTENSION_MISMATCH",
        "INVALID_ENTITY_LABEL",
        "ENTITY_WITH_NO_LABEL",
        "ENTITY_NOT_IN_RULE",
        "FILENAME_MISMATCH",
        "MISSING_REQUIRED_ENTITY",
    ):
        assert code not in codes, code
