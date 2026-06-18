"""Validate a TSV file's columns against the schema's ``rules.tabular_data``.

For a tabular file (events, channels, participants, scans ...) the schema defines
which columns may appear, which are required, whether extra columns are allowed,
and each column's type. This checks the file's actual columns against that, and
is deliberately conservative so it never reports a column problem it cannot be
sure of:

* a required defined column that is absent -> error;
* an extra column that is neither schema-defined nor documented in the sidecar ->
  warning (or error if the rule forbids extra columns);
* a value that cannot be the column's numeric type -> error.

Enum/string value checks are intentionally left out for now (an incomplete schema
enum could otherwise produce a false positive); numeric type coercion is safe.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bidsschematools.types.namespace import Namespace

from ..issues import Fix, Issue, Severity

_NA = {"n/a", "", None}


def eval_columns(
    schema: Namespace,
    rule: Mapping[str, Any],
    context: Mapping[str, Any],
    path: str,
) -> list[Issue]:
    columns = context.get("columns")
    if not isinstance(columns, Mapping) or not columns:
        return []  # not a populated TSV; nothing to check

    location = str(context.get("path", "")).lstrip("/")
    object_columns = schema["objects"].get("columns", {})

    # Map each rule column key to its real name + definition + requirement.
    defined: dict[str, tuple[Mapping[str, Any], Any]] = {}
    for key, requirement in rule.get("columns", {}).items():
        definition = object_columns.get(key, {})
        name = str(definition.get("name", key))
        defined[name] = (definition, requirement)

    issues: list[Issue] = []

    # Required columns must be present.
    for name, (_definition, requirement) in defined.items():
        if _level(requirement) == "required" and name not in columns:
            issues.append(
                Issue(
                    code="TSV_COLUMN_MISSING",
                    sub_code=name,
                    severity=Severity.ERROR,
                    location=location,
                    message=f"required column {name!r} is missing",
                    rule=path,
                    fix=Fix(action="add_column", field=name),
                )
            )

    # Extra columns: must be schema-defined or documented in the sidecar.
    sidecar = context.get("sidecar")
    documented = set(sidecar.keys()) if isinstance(sidecar, Mapping) else set()
    additional = rule.get("additional_columns")
    if additional is not None:
        for name in columns:
            if name in defined or name in documented:
                continue
            if additional == "allowed":
                issues.append(
                    Issue(
                        code="TSV_ADDITIONAL_COLUMNS_UNDEFINED",
                        sub_code=name,
                        severity=Severity.WARNING,
                        location=location,
                        message=f"column {name!r} is not defined by the schema or the sidecar",
                        suggestion="Document this column in the accompanying JSON sidecar.",
                        rule=path,
                    )
                )
            else:  # not allowed
                issues.append(
                    Issue(
                        code="TSV_ADDITIONAL_COLUMNS_NOT_ALLOWED",
                        sub_code=name,
                        severity=Severity.ERROR,
                        location=location,
                        message=f"column {name!r} is not allowed in this file",
                        rule=path,
                    )
                )

    # Numeric value types (safe coercion check only).
    for name, (definition, _requirement) in defined.items():
        if name not in columns:
            continue
        type_name = definition.get("type")
        if type_name in ("number", "integer"):
            issue = _check_numeric_column(name, columns[name], str(type_name), location, path)
            if issue is not None:
                issues.append(issue)

    return issues


def _check_numeric_column(
    name: str, values: list[Any], type_name: str, location: str, path: str
) -> Issue | None:
    for index, value in enumerate(values):
        if value in _NA:
            continue
        try:
            float(value)
        except (TypeError, ValueError):
            return Issue(
                code="TSV_VALUE_INCORRECT_TYPE",
                sub_code=name,
                severity=Severity.ERROR,
                location=location,
                line=index + 2,  # 1-based, plus the header row
                message=f"column {name!r} expects {type_name} values, found {value!r}",
                rule=path,
            )
    return None


def _level(requirement: Any) -> str:
    if isinstance(requirement, str):
        return requirement
    if isinstance(requirement, Mapping):
        return str(requirement.get("level", ""))
    return ""
