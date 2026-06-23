"""Tests for the command-line interface.

The CLI is driven through ``main`` directly with an explicit argv, so no
subprocess is needed. Output and exit codes are checked.
"""

from __future__ import annotations

import json

from bidsval.cli import main


def _write_nifti(path) -> None:
    """Write a small, readable NIfTI so it is not flagged NIFTI_HEADER_UNREADABLE."""
    import nibabel as nib
    import numpy as np

    nib.save(nib.Nifti1Image(np.zeros((2, 2, 2), dtype=np.int16), np.eye(4)), str(path))


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
    _write_nifti(anat / "sub-01_T1w.nii.gz")
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


def _valid_dataset(root) -> None:
    import json

    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.11.1"})
    )
    anat = root / "sub-01" / "anat"
    anat.mkdir(parents=True)
    _write_nifti(anat / "sub-01_T1w.nii.gz")
    (anat / "sub-01_T1w.json").write_text("{}")


def test_output_type_json_to_stdout(tmp_path, capsys) -> None:
    import json

    _valid_dataset(tmp_path)
    code = main(["validate", str(tmp_path), "--output-type", "json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["valid"] is True


def test_output_type_all_writes_every_format(tmp_path) -> None:
    _valid_dataset(tmp_path)
    out = tmp_path / "reports"
    main(["validate", str(tmp_path), "--output-type", "all", "--out-dir", str(out)])
    names = {p.name for p in out.iterdir()}
    assert names == {"report.txt", "report.json", "report.sarif", "report.html"}


def test_multiple_output_types_default_to_cwd(tmp_path, monkeypatch) -> None:
    # Several formats with no --out-dir write into the current directory.
    _valid_dataset(tmp_path)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    main(["validate", str(tmp_path), "--out-type", "json,html"])
    names = {p.name for p in workdir.iterdir()}
    assert names == {"report.json", "report.html"}


def test_show_filter_hides_warnings(tmp_path, capsys) -> None:
    # Missing dataset_description.json is an error; recommended fields are warnings.
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    _write_nifti(tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz")
    main(["validate", str(tmp_path), "--show", "error"])
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "WARNING" not in out  # warnings filtered from the display


def test_bad_output_type_errors(tmp_path, capsys) -> None:
    _valid_dataset(tmp_path)
    code = main(["validate", str(tmp_path), "--output-type", "pdf"])
    assert code == 2
    assert "unknown --output-type" in capsys.readouterr().err


def test_out_type_alias_and_list_schemas(tmp_path, capsys) -> None:
    # --out-type is the pv-style alias of --output-type.
    _valid_dataset(tmp_path)
    code = main(["validate", str(tmp_path), "--out-type", "json"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True


def test_validate_list_schemas_flag(tmp_path, capsys) -> None:
    code = main(["validate", str(tmp_path), "--list-schemas"])
    assert code == 0
    out = capsys.readouterr().out
    assert "default:" in out and "bundled:" in out and "1.11.1" in out


def test_max_rows_accepted(tmp_path) -> None:
    _valid_dataset(tmp_path)
    assert main(["validate", str(tmp_path), "--max-rows", "500"]) == 0


def test_filenames_only_hides_content_findings(tmp_path, capsys) -> None:
    # A dataset with a stray (not-included) file and a missing recommended field:
    # --filenames-only shows the filename finding but not the content warning.
    import json as _json

    (tmp_path / "dataset_description.json").write_text(
        _json.dumps({"Name": "t", "BIDSVersion": "1.11.1"})
    )
    anat = tmp_path / "sub-01" / "anat"
    anat.mkdir(parents=True)
    _write_nifti(anat / "sub-01_T1w.nii.gz")
    (anat / "sub-01_T1w.json").write_text("{}")
    (tmp_path / "sub-01" / "anat" / "stray_file.foo").write_text("x")
    main(["validate", str(tmp_path), "--filenames-only", "--show", "all"])
    out = capsys.readouterr().out
    assert "NOT_INCLUDED" in out
    assert "SIDECAR_KEY_RECOMMENDED" not in out
