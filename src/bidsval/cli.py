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
from .issues import Severity
from .render import EXTENSIONS, RENDERERS
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
        metavar="VERSION",
        help="the schema to use, chosen by BIDS version (e.g. 1.11.1), 'latest', a "
        "URL, or a local schema.json / source directory (default: the bundled latest)",
    )
    validate_cmd.add_argument(
        "--subject", default=None, metavar="SUB", help="validate only this subject (e.g. sub-01)"
    )
    validate_cmd.add_argument(
        "--headers", action="store_true", help="also check NIfTI headers (needs nibabel)"
    )
    validate_cmd.add_argument(
        "--output-type",
        default="text",
        metavar="TYPES",
        help="comma-separated output formats: text, json, sarif, html, or all (default: text)",
    )
    validate_cmd.add_argument(
        "--out-dir",
        metavar="DIR",
        help="write each --output-type to DIR/report.<ext> (required for html or multiple types)",
    )
    validate_cmd.add_argument(
        "--show",
        default="error,warning",
        metavar="LEVELS",
        help="which severities to display: any of error, warning, ignore, or all "
        "(default: error,warning). Does not change the pass/fail result.",
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

    try:
        types = _parse_output_types(args.output_type)
        severities = _parse_severities(args.show)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    # Findings are filtered for display only; validity always depends on errors.
    display = report.filtered(severities)

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for output_type in sorted(types):
            destination = out_dir / f"report.{EXTENSIONS[output_type]}"
            destination.write_text(RENDERERS[output_type](display), encoding="utf-8")
            print(f"wrote {destination}", file=sys.stderr)
    elif len(types) > 1:
        print("error: --out-dir is required when --output-type selects more than one format",
              file=sys.stderr)
        return 2
    else:
        print(RENDERERS[next(iter(types))](display))

    return 0 if report.is_valid else 1


def _parse_output_types(value: str) -> set[str]:
    requested = [t.strip().lower() for t in value.split(",") if t.strip()]
    if "all" in requested:
        return set(RENDERERS)
    unknown = [t for t in requested if t not in RENDERERS]
    if unknown:
        raise ValueError(
            f"unknown --output-type {unknown}; choose from {sorted(RENDERERS)} or 'all'"
        )
    return set(requested) or {"text"}


def _parse_severities(value: str) -> set[Severity]:
    requested = [s.strip().lower() for s in value.split(",") if s.strip()]
    if "all" in requested:
        return set(Severity)
    out: set[Severity] = set()
    for name in requested:
        try:
            out.add(Severity(name))
        except ValueError as error:
            raise ValueError(
                f"unknown --show level {name!r}; choose from error, warning, ignore, or 'all'"
            ) from error
    return out or {Severity.ERROR, Severity.WARNING}


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
