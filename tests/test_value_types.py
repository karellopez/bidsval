"""Tests for column value-type checking and sidecar type redefinition."""

from __future__ import annotations

import json

from bidsval import validate
from bidsval.rules.column_types import (
    Signature,
    check_value,
    compile_spec,
    is_trivial,
    value_signature,
)
from bidsval.schema import DEFAULT_VERSION, resolve


def _dataset(root) -> None:
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": DEFAULT_VERSION})
    )


def _codes(report):
    out = {i.code for i in report.dataset_issues.issues}
    for verdict in report.files:
        out.update(i.code for i in verdict.issues)
    return out


# --- unit: signature + value checking --------------------------------------


def test_sidecar_redefinition_conflict() -> None:
    schema = resolve()
    onset = schema["objects"]["columns"]["onset"]  # type: number
    _sig, error = value_signature(onset, {"Format": "string"})
    assert error is not None  # number column cannot be redefined as a string


def test_sidecar_refinement_ok() -> None:
    schema = resolve()
    onset = schema["objects"]["columns"]["onset"]
    _sig, error = value_signature(onset, {"Format": "number", "Units": "s"})
    assert error is None  # a compatible refinement is fine


def test_check_value_number() -> None:
    schema = resolve()
    spec = compile_spec(Signature(formats=["number"]), schema["objects"]["formats"])
    assert check_value("3.5", spec)
    assert check_value("n/a", spec)
    assert not check_value("abc", spec)


def test_string_column_is_trivial() -> None:
    assert is_trivial(Signature(formats=["string"]))
    assert not is_trivial(Signature(formats=["number"]))
    assert not is_trivial(Signature(formats=["string"], levels=["a", "b"]))


# --- validate: end to end --------------------------------------------------


def test_tsv_value_incorrect_type(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    # onset is a number; 'abc' is not.
    (func / "sub-01_task-rest_events.tsv").write_text("onset\tduration\nabc\t2\n")
    assert "TSV_VALUE_INCORRECT_TYPE" in _codes(validate(tmp_path))


def test_tsv_value_correct_type_not_flagged(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    (func / "sub-01_task-rest_events.tsv").write_text("onset\tduration\n1.0\t2.0\n")
    assert "TSV_VALUE_INCORRECT_TYPE" not in _codes(validate(tmp_path))


def test_tsv_column_type_redefined(tmp_path) -> None:
    _dataset(tmp_path)
    func = tmp_path / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_text("x")
    (func / "sub-01_task-rest_events.tsv").write_text("onset\tduration\n1\t2\n")
    # The sidecar redefines the numeric 'onset' column as a string: incompatible.
    (func / "sub-01_task-rest_events.json").write_text(json.dumps({"onset": {"Format": "string"}}))
    assert "TSV_COLUMN_TYPE_REDEFINED" in _codes(validate(tmp_path))
