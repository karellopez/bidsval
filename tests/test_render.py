"""Tests for the JSON, SARIF, and HTML renderers."""

from __future__ import annotations

import json
from pathlib import Path

from bidsval.issues import Issue, Severity
from bidsval.render import to_dict, to_html, to_json, to_sarif
from bidsval.report import FileVerdict, ValidationReport


def _report() -> ValidationReport:
    report = ValidationReport(bids_version="1.11.1", schema_version="1.2.1")
    report.dataset_issues.add(
        Issue(code="MISSING_DATASET_DESCRIPTION", severity=Severity.ERROR, location="x")
    )
    verdict = FileVerdict(path=Path("sub-01/anat/sub-01_T1w.json"))
    verdict.issues.append(
        Issue(
            code="SIDECAR_KEY_RECOMMENDED",
            sub_code="InstitutionName",
            severity=Severity.WARNING,
            location="sub-01/anat/sub-01_T1w.json",
            message="missing recommended field",
        )
    )
    report.files.append(verdict)
    report.recompute()
    return report


def test_json_shape_is_flat_and_complete() -> None:
    data = to_dict(_report())
    assert data["valid"] is False
    assert data["counts"] == {"error": 1, "warning": 1, "ignore": 0}
    assert len(data["issues"]) == 2  # dataset + file findings combined
    assert {i["code"] for i in data["issues"]} == {
        "MISSING_DATASET_DESCRIPTION",
        "SIDECAR_KEY_RECOMMENDED",
    }
    # Round-trips through JSON.
    assert json.loads(to_json(_report()))["bidsVersion"] == "1.11.1"


def test_sarif_is_valid_2_1_0() -> None:
    sarif = json.loads(to_sarif(_report()))
    assert sarif["version"] == "2.1.0"
    driver = sarif["runs"][0]["tool"]["driver"]
    assert driver["name"] == "bidsval"
    results = sarif["runs"][0]["results"]
    assert len(results) == 2
    assert results[0]["level"] in {"error", "warning", "note"}
    assert "physicalLocation" in results[0]["locations"][0]


def test_html_is_self_contained_and_escaped() -> None:
    report = ValidationReport(bids_version="1.11.1", schema_version="1.2.1")
    report.dataset_issues.add(
        Issue(code="X", severity=Severity.ERROR, location="f", message="a <script> & b")
    )
    report.recompute()
    html = to_html(report)
    assert html.startswith("<!doctype html>")
    assert "<style>" in html and "http://" not in html  # no external assets
    assert "INVALID" in html
    # User content is escaped, not injected as markup.
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_clean_dataset_says_no_findings() -> None:
    report = ValidationReport(bids_version="1.11.1", schema_version="1.2.1")
    report.recompute()
    html = to_html(report)
    assert "VALID" in html and "No findings" in html
