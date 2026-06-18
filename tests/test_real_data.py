"""Real-data validation, gated on an environment variable.

Run with ``BIDSVAL_REAL_DATA=1 pytest`` to validate the real MRI/EEG/MEG/PET
datasets. These confirm the validator runs to completion on genuine datasets
without internal errors, and that a known true finding is caught.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bidsval import validate

_ENABLED = os.environ.get("BIDSVAL_REAL_DATA") == "1"
_ROOT = Path(
    os.environ.get(
        "BIDSVAL_REAL_DATA_DIR",
        "/Users/karelo/Development/datasets/BIDS_Manager/bids_manager_outputs/testing",
    )
)

pytestmark = pytest.mark.skipif(not _ENABLED, reason="set BIDSVAL_REAL_DATA=1 to run")


@pytest.mark.parametrize("name", ["ds_mri", "ds_eeg", "ds_meg", "ds_pet"])
def test_real_dataset_runs_without_internal_errors(name: str) -> None:
    root = _ROOT / name
    if not root.is_dir():
        pytest.skip(f"{root} not present")
    report = validate(root)
    assert report.files, "expected per-file verdicts"
    internal = [
        i.location
        for f in report.files
        for i in f.issues
        if i.code == "bidsval.internal_error"
    ]
    assert not internal, f"internal errors on: {internal}"


def test_real_meg_flags_unresolved_empty_room() -> None:
    root = _ROOT / "ds_meg"
    if not root.is_dir():
        pytest.skip("ds_meg not present")
    report = validate(root)
    codes = {i.code for f in report.files for i in f.issues}
    # The MEG sidecars carry AssociatedEmptyRoom = "TODO", which does not resolve.
    assert "ASSOCIATED_EMPTY_ROOM" in codes
