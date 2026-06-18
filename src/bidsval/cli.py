"""Command-line entry point for bidsval.

* ``bidsval validate PATH`` - validate a dataset; print a text/JSON/SARIF summary
  and optionally write JSON, SARIF, and HTML report files.
* ``bidsval schema`` - print the resolved schema version and the bundled versions.
* ``bidsval eval EXPR`` - evaluate a BIDS schema expression against a context.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .expr import EvaluationError, evaluate_string
from .render import to_html, to_json, to_sarif
from .report import ValidationReport
from .schema import SchemaNotAvailable, available_versions, bids_version, resolve, schema_version
from .validate import validate as run_validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidsval",
        description="A schema-driven, pydantic-typed, in-process BIDS validator.",
    )
    parser.add_argument("--version", action="version", version=f"bidsval {__version__}")
    subcommands = parser.add_subparsers(dest="command", metavar="<command>")

    schema_cmd = subcommands.add_parser("schema", help="show the resolved schema version")
    schema_cmd.add_argument(
        "--schema",
        default=None,
        metavar="SELECTOR",
        help="bundled version (e.g. 1.11.1) or a path to a local schema.json",
    )
    schema_cmd.set_defaults(func=_run_schema)

    eval_cmd = subcommands.add_parser("eval", help="evaluate a BIDS schema expression")
    eval_cmd.add_argument("expression", help="the expression, e.g. \"suffix == 'T1w'\"")
    eval_cmd.add_argument(
        "--context",
        default="{}",
        metavar="JSON",
        help="JSON object of context variables (default: {})",
    )
    eval_cmd.set_defaults(func=_run_eval)

    validate_cmd = subcommands.add_parser("validate", help="validate a BIDS dataset")
    validate_cmd.add_argument("dataset", help="path to the dataset root")
    validate_cmd.add_argument(
        "--schema",
        default=None,
        metavar="SELECTOR",
        help="bundled version (e.g. 1.11.1) or a path to a local schema.json",
    )
    validate_cmd.add_argument(
        "--subject", default=None, metavar="SUB", help="validate only this subject (e.g. sub-01)"
    )
    validate_cmd.add_argument(
        "--headers", action="store_true", help="also check NIfTI headers (needs nibabel)"
    )
    validate_cmd.add_argument(
        "--format",
        choices=["text", "json", "sarif"],
        default="text",
        help="format printed to stdout (default: text)",
    )
    validate_cmd.add_argument("--json", metavar="PATH", help="also write a JSON report to PATH")
    validate_cmd.add_argument("--sarif", metavar="PATH", help="also write a SARIF report to PATH")
    validate_cmd.add_argument("--html", metavar="PATH", help="also write an HTML report to PATH")
    validate_cmd.add_argument(
        "--out-dir",
        metavar="DIR",
        help="write all report formats (report.json, report.sarif, report.html) to DIR",
    )
    validate_cmd.set_defaults(func=_run_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


def _run_schema(args: argparse.Namespace) -> int:
    try:
        schema = resolve(args.schema)
    except SchemaNotAvailable as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"BIDS version  : {bids_version(schema)}")
    print(f"schema version: {schema_version(schema)}")
    print(f"bundled       : {', '.join(available_versions())}")
    return 0


def _run_eval(args: argparse.Namespace) -> int:
    try:
        context = json.loads(args.context)
    except json.JSONDecodeError as error:
        print(f"error: --context is not valid JSON: {error}", file=sys.stderr)
        return 2
    if not isinstance(context, dict):
        print("error: --context must be a JSON object", file=sys.stderr)
        return 2
    try:
        result = evaluate_string(args.expression, context)
    except EvaluationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    subjects = None
    if args.subject:
        sub = args.subject if args.subject.startswith("sub-") else f"sub-{args.subject}"
        subjects = [sub]
    try:
        report = run_validate(
            args.dataset, schema=args.schema, read_headers=args.headers, subjects=subjects
        )
    except SchemaNotAvailable as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    # What goes to stdout.
    if args.format == "json":
        print(to_json(report))
    elif args.format == "sarif":
        print(to_sarif(report))
    else:
        _print_report(report)

    # Optional report files (any combination).
    outputs = [(args.json, to_json), (args.sarif, to_sarif), (args.html, to_html)]
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        outputs += [
            (str(out_dir / "report.json"), to_json),
            (str(out_dir / "report.sarif"), to_sarif),
            (str(out_dir / "report.html"), to_html),
        ]
    for path, render in outputs:
        if path:
            Path(path).write_text(render(report), encoding="utf-8")
            print(f"wrote {path}", file=sys.stderr)

    return 0 if report.is_valid else 1


def _print_report(report: ValidationReport) -> None:
    print(f"bidsval {__version__}  schema {report.schema_version}  BIDS {report.bids_version}")
    print(f"{report.dataset_root}")
    findings = list(report.dataset_issues.issues)
    for verdict in report.files:
        findings.extend(verdict.issues)
    for issue in findings:
        where = issue.location or ""
        field = f" [{issue.sub_code}]" if issue.sub_code else ""
        message = f" - {issue.message}" if issue.message else ""
        print(f"  {issue.severity.value.upper():7s} {issue.code}{field}  {where}{message}")
    counts = report.counts
    print(f"\n{counts['error']} error(s), {counts['warning']} warning(s)")
    print("VALID" if report.is_valid else "INVALID")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
