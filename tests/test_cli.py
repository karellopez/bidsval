"""Tests for the command-line interface.

The CLI is driven through ``main`` directly with an explicit argv, so no
subprocess is needed. Output and exit codes are checked.
"""

from __future__ import annotations

from bidsval.cli import main


def test_schema_command_reports_versions(capsys) -> None:
    code = main(["schema"])
    out = capsys.readouterr().out
    assert code == 0
    assert "BIDS version" in out
    assert "1.11.1" in out


def test_eval_command_returns_json_result(capsys) -> None:
    code = main(["eval", "suffix == 'T1w'", "--context", '{"suffix": "T1w"}'])
    assert code == 0
    assert capsys.readouterr().out.strip() == "true"


def test_eval_command_arithmetic(capsys) -> None:
    code = main(["eval", "1 + 2"])
    assert code == 0
    assert capsys.readouterr().out.strip() == "3"


def test_eval_command_rejects_bad_context(capsys) -> None:
    code = main(["eval", "1 + 2", "--context", "not json"])
    assert code == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_eval_command_reports_unparseable_expression(capsys) -> None:
    code = main(["eval", "1 +"])
    assert code == 1
    assert "error" in capsys.readouterr().err


def test_no_command_prints_help(capsys) -> None:
    code = main([])
    assert code == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_validate_command_on_a_dataset(tmp_path, capsys) -> None:
    import json

    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "Test", "BIDSVersion": "1.11.1"})
    )
    anat = tmp_path / "sub-01" / "anat"
    anat.mkdir(parents=True)
    (anat / "sub-01_T1w.nii.gz").write_text("x")
    (anat / "sub-01_T1w.json").write_text("{}")

    code = main(["validate", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0  # valid (only recommended-field warnings)
    assert "VALID" in out
    assert "BIDS 1.11.1" in out


def test_validate_command_reports_missing_description(tmp_path, capsys) -> None:
    code = main(["validate", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1  # invalid
    assert "MISSING_DATASET_DESCRIPTION" in out
    assert "INVALID" in out
