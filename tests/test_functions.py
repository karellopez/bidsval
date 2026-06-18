"""Unit tests for the expression helper functions and value coercions.

These complement the schema oracle by pinning the behaviours that are easy to
get subtly wrong: JavaScript truthiness, NaN handling in numeric sorts, and
first-seen de-duplication where ``1`` and ``1.0`` collapse.
"""

from __future__ import annotations

import math

from bidsval.expr import functions as fn


def test_truthy_matches_javascript() -> None:
    # Falsy in JS:
    assert fn.truthy(None) is False
    assert fn.truthy(False) is False
    assert fn.truthy(0) is False
    assert fn.truthy("") is False
    assert fn.truthy(math.nan) is False
    # Truthy in JS - note empty containers are truthy, unlike Python:
    assert fn.truthy([]) is True
    assert fn.truthy({}) is True
    assert fn.truthy("x") is True
    assert fn.truthy(1) is True


def test_js_string_coercion() -> None:
    assert fn.js_string(None) == "null"
    assert fn.js_string(True) == "true"
    assert fn.js_string(False) == "false"
    assert fn.js_string(1.0) == "1"  # integral floats print without a decimal
    assert fn.js_string(1.5) == "1.5"


def test_to_number_handles_na() -> None:
    assert fn.to_number("1.5") == 1.5
    assert fn.to_number("") == 0.0
    assert fn.to_number(True) == 1.0
    assert math.isnan(fn.to_number("n/a"))


def test_unique_collapses_equal_numbers_keeping_first() -> None:
    assert fn.unique([1, 1.0]) == [1]
    assert fn.unique([1.0, 1]) == [1.0]
    assert fn.unique([52, -4, 3, 8, -4, 52, 9]) == [52, -4, 3, 8, 9]
    assert fn.unique(None) is None


def test_sorted_numeric_leaves_non_numbers_in_place() -> None:
    assert fn.sorted_(["1", "2", "n/a"], "numeric") == ["1", "2", "n/a"]
    assert fn.sorted_(["n/a", "2", "1"], "numeric") == ["n/a", "1", "2"]
    assert fn.sorted_([3, 2, 1]) == [1, 2, 3]
    assert fn.sorted_([1, 2, 5, 10], "lexical") == [1, 10, 2, 5]


def test_intersects_returns_intersection_or_false() -> None:
    assert fn.intersects([1], [1, 2]) == [1]
    assert fn.intersects([1], []) is False
    assert fn.intersects([], None) is False


def test_min_max_ignore_non_numeric() -> None:
    assert fn.min_([-1, "n/a", 1]) == -1
    assert fn.max_([-1, "n/a", 1]) == 1
    assert fn.min_(None) is None


def test_exists_without_resolver_reports_zero() -> None:
    assert fn.exists(None, "bids-uri") == 0
    assert fn.exists([], None) == 0
    assert fn.exists(["sub-01/anat/sub-01_T1w.nii.gz"], "dataset") == 0


def test_exists_uses_installed_resolver() -> None:
    # The host installs a resolver on the context; exists counts the hits.
    present = {"a", "b"}
    context = {fn.EXISTS_RESOLVER_KEY: lambda item, rule: item in present}
    assert fn.exists(["a", "b", "c"], "dataset", context) == 2


def test_unique_preserves_element_type_not_just_value() -> None:
    # Plain list equality treats [1] == [1.0], so assert the type too: a wrong
    # implementation that collapsed to the second occurrence would slip past ==.
    first = fn.unique([1, 1.0])
    assert first == [1] and isinstance(first[0], int)
    second = fn.unique([1.0, 1])
    assert second == [1.0] and isinstance(second[0], float)


def test_type_of_tags() -> None:
    assert fn.type_of([]) == "array"
    assert fn.type_of({}) == "object"
    assert fn.type_of(True) == "boolean"
    assert fn.type_of(1) == "number"
    assert fn.type_of("s") == "string"
    assert fn.type_of(None) == "null"


def test_length_count_index_allequal() -> None:
    assert fn.length([1, 2, 3]) == 3
    assert fn.length("abc") == 3
    assert fn.length(None) is None
    assert fn.count([1, 2, 1, 3], 1) == 2
    assert fn.index(["i", "j", "k"], "j") == 1
    assert fn.index(["i", "j"], "x") is None
    assert fn.allequal([1, 2], [1, 2]) is True
    assert fn.allequal([1, 2], [1, 3]) is False
    assert fn.allequal([1], None) is False


def test_substr_and_match_basic_and_guarded() -> None:
    assert fn.substr("string", 1, 4) == "tri"
    assert fn.substr("string", None, 4) is None
    assert fn.substr("string", "x", 4) is None  # non-integer bound degrades
    assert fn.match("string", ".*") is True
    assert fn.match(None, "p") is None
    assert fn.match("string", "(unclosed") is None  # invalid regex degrades


def test_sorted_non_list_degrades_to_null() -> None:
    assert fn.sorted_(None) is None
    assert fn.sorted_("scalar") is None


def test_js_string_special_floats() -> None:
    assert fn.js_string(float("nan")) == "NaN"
    assert fn.js_string(float("inf")) == "Infinity"
    assert fn.js_string(float("-inf")) == "-Infinity"
