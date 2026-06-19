"""Tests for the dataset-level checks (case collision, unused stimulus) and the
deprecated-age tabular check."""

from __future__ import annotations

import json
from pathlib import Path

from bidsval import validate
from bidsval.files import BIDSFile
from bidsval.rules.dataset_checks import _case_collisions
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


# Case collisions are tested at the function level: a case-insensitive filesystem
# (macOS default) cannot hold both files at once, so we cannot build the dataset.
def test_case_collision_detected() -> None:
    files = [
        BIDSFile("sub-01/anat/sub-01_T1w.nii.gz", Path("/x")),
        BIDSFile("sub-01/anat/sub-01_t1w.nii.gz", Path("/y")),
    ]
    assert {i.code for i in _case_collisions(files)} == {"CASE_COLLISION"}


def test_no_case_collision() -> None:
    files = [BIDSFile("a/b.txt", Path("/x")), BIDSFile("a/c.txt", Path("/y"))]
    assert _case_collisions(files) == []


def test_unused_stimulus(tmp_path) -> None:
    _dataset(tmp_path)
    (tmp_path / "stimuli").mkdir()
    (tmp_path / "stimuli" / "face.png").write_text("x")
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    (func / "sub-01_task-rest_events.tsv").write_text("onset\tduration\n1\t2\n")
    assert "UNUSED_STIMULUS" in _codes(validate(tmp_path))


def test_referenced_stimulus_not_flagged(tmp_path) -> None:
    _dataset(tmp_path)
    (tmp_path / "stimuli").mkdir()
    (tmp_path / "stimuli" / "face.png").write_text("x")
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    (func / "sub-01_task-rest_events.tsv").write_text(
        "onset\tduration\tstim_file\n1\t2\tface.png\n"
    )
    assert "UNUSED_STIMULUS" not in _codes(validate(tmp_path))


def test_pseudo_age_deprecated(tmp_path) -> None:
    _dataset(tmp_path)
    (tmp_path / "participants.tsv").write_text("participant_id\tage\nsub-01\t89+\n")
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")
    assert "TSV_PSEUDO_AGE_DEPRECATED" in _codes(validate(tmp_path))
