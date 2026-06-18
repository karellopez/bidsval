"""Tests for the schema resolver.

These confirm the bundled default loads and exposes both version axes, that a
bundled version tag and a local path both resolve, and that an unsupported
selector fails clearly rather than silently substituting a different schema.
"""

from __future__ import annotations

import pytest
from bidsschematools.types.namespace import Namespace

from bidsval.schema import (
    DEFAULT_VERSION,
    SchemaNotAvailable,
    available_versions,
    bids_version,
    resolve,
    schema_version,
)


def test_default_resolves_to_bundled_schema() -> None:
    schema = resolve()
    assert isinstance(schema, Namespace)
    # The default is the bundled version, and both version axes are present.
    assert bids_version(schema) == DEFAULT_VERSION
    assert schema_version(schema)  # the schema's own version, e.g. "1.2.2"


def test_bundled_version_tag_resolves() -> None:
    assert DEFAULT_VERSION in available_versions()
    schema = resolve(DEFAULT_VERSION)
    assert bids_version(schema) == DEFAULT_VERSION


def test_default_and_version_tag_share_one_cached_load() -> None:
    # None defaults to DEFAULT_VERSION, so both go through the same cache entry.
    assert resolve() is resolve(DEFAULT_VERSION)


def test_resolve_local_path(tmp_path) -> None:
    # A dereferenced schema.json on disk loads via the same entry point.
    import json

    from bidsschematools import data

    schema_json = data.load.readable("schema.json").read_text()
    local = tmp_path / "schema.json"
    local.write_text(schema_json)

    loaded = resolve(local)
    assert isinstance(loaded, Namespace)
    assert str(loaded.bids_version) == json.loads(schema_json)["bids_version"]


def test_unbundled_version_or_url_raises_clearly() -> None:
    with pytest.raises(SchemaNotAvailable):
        resolve("9.9.9")  # not bundled, and fetching is not implemented yet
    with pytest.raises(SchemaNotAvailable):
        resolve("https://example.org/schema.json")
