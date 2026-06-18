"""Robustness tests for the evaluator.

The rule engine will evaluate every schema selector and check against every file
in a dataset. A single malformed input must never crash the run. The centrepiece
here evaluates *every* real selector/check expression in the schema (hundreds of
them) against deliberately sparse contexts and asserts that nothing raises - the
evaluator must always return a value, degrading to null where an operation does
not make sense.
"""

from __future__ import annotations

import json

import pytest
from bidsschematools import data

from bidsval.expr import EvaluationError, evaluate_string


def _all_schema_expressions() -> list[str]:
    """Every selector/check expression the validator would evaluate."""
    schema = json.loads(data.load.readable("schema.json").read_text())
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key in ("selectors", "checks"):
                value = node.get(key)
                if isinstance(value, list):
                    found.extend(item for item in value if isinstance(item, str))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema["rules"])
    return list(dict.fromkeys(found))  # dedupe, preserve order


SCHEMA_EXPRESSIONS = _all_schema_expressions()

# A few representative contexts. The empty one is the harshest (everything is
# null); the others exercise the populated paths. None should ever raise.
_CONTEXTS = [
    {},
    {"sidecar": {}, "entities": {}, "columns": {}, "associations": {}},
    {
        "suffix": "T1w",
        "datatype": "anat",
        "extension": ".nii.gz",
        "modality": "mri",
        "size": 1024,
        "path": "/sub-01/anat/sub-01_T1w.nii.gz",
        "sidecar": {"RepetitionTime": 2.0},
        "entities": {"sub": "01"},
        "columns": {"onset": ["0", "1", "2"]},
        "nifti_header": {"dim": [3, 64, 64, 30], "pixdim": [1, 1, 1, 2]},
    },
]


def test_schema_expressions_are_non_trivial() -> None:
    assert len(SCHEMA_EXPRESSIONS) >= 100


@pytest.mark.parametrize("expression", SCHEMA_EXPRESSIONS)
def test_every_schema_expression_evaluates_without_crashing(expression: str) -> None:
    for context in _CONTEXTS:
        try:
            result = evaluate_string(expression, context)
        except EvaluationError:
            # A controlled signal (e.g. an unknown function in the schema) is
            # acceptable: the rule engine catches these and reports them as
            # unsupported constructs. What must never happen is an *uncontrolled*
            # Python exception (TypeError, ZeroDivisionError, ...), which would
            # propagate from here as something other than EvaluationError.
            continue
        # The result must be a JSON-ish value, never a stray object.
        assert result is None or isinstance(result, (bool, int, float, str, list, dict))


def test_unknown_schema_function_is_a_controlled_signal() -> None:
    # The schema contains one expression that calls ``len(...)`` (a typo for
    # ``length``) in ``rules.checks.anat.PDT2Echos``. ``len`` is not a defined
    # expression function (the reference validator does not define it either), so
    # bidsval surfaces it as a controlled EvaluationError. The rule engine will
    # skip the check and report the unsupported construct, rather than crashing or
    # emitting a false error.
    with pytest.raises(EvaluationError):
        evaluate_string("len(sidecar.EchoTime) == 2", {"sidecar": {"EchoTime": [1, 2]}})


# --- targeted error-path behaviour ---------------------------------------


def test_division_and_modulo_by_zero_degrade_to_null() -> None:
    assert evaluate_string("3 / 0", {}) is None
    assert evaluate_string("3 % 0", {}) is None


def test_ordering_coerces_numeric_strings_and_degrades_on_non_numbers() -> None:
    assert evaluate_string("x < 5", {"x": "3"}) is True       # numeric string coerces
    assert evaluate_string("x < 5", {"x": "abc"}) is None     # not a number -> null
    assert evaluate_string("x < 5", {"x": None}) is None      # null propagation


def test_plus_concatenates_when_either_side_is_text() -> None:
    assert evaluate_string("1 + 'a'", {}) == "1a"


def test_function_arity_mismatch_degrades_to_null() -> None:
    assert evaluate_string("length()", {}) is None


def test_in_operator_is_object_key_membership() -> None:
    ctx = {"x": {"a": 1}}
    assert evaluate_string("'a' in x", ctx) is True
    assert evaluate_string("'b' in x", ctx) is False
    assert evaluate_string("'a' in x", {}) is None  # null right operand


def test_index_out_of_range_or_bad_index_is_null() -> None:
    ctx = {"x": [1, 2]}
    assert evaluate_string("x[5]", ctx) is None
    assert evaluate_string("x[-1]", ctx) is None
    assert evaluate_string("x['a']", ctx) is None


def test_unparseable_expression_raises_evaluation_error() -> None:
    with pytest.raises(EvaluationError):
        evaluate_string("1 +", {})
