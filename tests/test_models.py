"""Tests for the pydantic result models (issues and report rollup)."""

from __future__ import annotations

from pathlib import Path

from bidsval.issues import DatasetIssues, Issue, Severity
from bidsval.report import FileVerdict, ValidationReport


def test_severity_ordering() -> None:
    assert Severity.IGNORE.rank < Severity.WARNING.rank < Severity.ERROR.rank


def test_dataset_issues_highest_severity() -> None:
    issues = DatasetIssues()
    assert issues.highest_severity() is None
    issues.add(Issue(code="A", severity=Severity.WARNING))
    issues.add(Issue(code="B", severity=Severity.ERROR))
    issues.add(Issue(code="C", severity=Severity.IGNORE))
    assert issues.highest_severity() is Severity.ERROR
    assert len(issues) == 3
    assert [i.code for i in issues.by_severity(Severity.WARNING)] == ["A"]


def test_file_verdict_recompute_severity() -> None:
    verdict = FileVerdict(path=Path("sub-01/anat/sub-01_T1w.json"))
    assert verdict.severity is None
    verdict.issues.append(Issue(code="X", severity=Severity.WARNING))
    verdict.recompute_severity()
    assert verdict.severity is Severity.WARNING


def test_report_rollup_and_counts() -> None:
    report = ValidationReport(bids_version="1.11.1", schema_version="1.2.2")
    report.dataset_issues.add(Issue(code="DS", severity=Severity.WARNING))

    verdict = FileVerdict(path=Path("sub-01/anat/sub-01_T1w.nii.gz"))
    verdict.issues.append(Issue(code="DIM", severity=Severity.ERROR))
    report.files.append(verdict)

    report.recompute()
    assert report.severity is Severity.ERROR
    assert report.counts == {"error": 1, "warning": 1, "ignore": 0}
    assert report.is_valid is False


def test_clean_report_is_valid() -> None:
    report = ValidationReport()
    report.recompute()
    assert report.severity is None
    assert report.is_valid is True


def test_issue_carries_provenance_and_fix() -> None:
    issue = Issue(
        code="SIDECAR_KEY_REQUIRED",
        sub_code="RepetitionTime",
        severity=Severity.ERROR,
        fix={"action": "add_field", "field": "RepetitionTime"},
        provenance={"rule_path": "rules.sidecars.mri.func", "checks": []},
    )
    assert issue.fix is not None and issue.fix.action == "add_field"
    assert issue.provenance is not None and issue.provenance.rule_path.endswith("func")


def test_report_with_only_ignored_findings_is_valid() -> None:
    report = ValidationReport()
    report.dataset_issues.add(Issue(code="SILENCED", severity=Severity.IGNORE))
    report.recompute()
    assert report.severity is Severity.IGNORE  # rollup reflects what is present
    assert report.is_valid is True             # ...but ignored findings are not errors
    assert report.counts == {"error": 0, "warning": 0, "ignore": 1}


def test_report_serialises_to_plain_data() -> None:
    # The report is pure data: model_dump must work (and not depend on any
    # custom container iteration).
    report = ValidationReport(bids_version="1.11.1")
    report.dataset_issues.add(Issue(code="X", severity=Severity.WARNING))
    report.recompute()
    dumped = report.model_dump()
    assert dumped["counts"]["warning"] == 1
    assert dumped["dataset_issues"]["issues"][0]["code"] == "X"
