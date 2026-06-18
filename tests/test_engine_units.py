"""Unit tests for the schema-driven building blocks: introspection, filename
parsing, and the file tree."""

from __future__ import annotations

from bidsval.context.entities import parse_filename
from bidsval.files import FileTree
from bidsval.schema import introspect, resolve


def test_introspect_reads_vocabulary_from_schema() -> None:
    schema = resolve()
    assert "anat" in introspect.datatypes(schema)
    assert "eeg" in introspect.datatypes(schema)
    assert "T1w" in introspect.suffixes(schema)
    # Extensions are listed longest-first so multi-part extensions win.
    exts = introspect.extensions(schema)
    assert ".nii.gz" in exts
    assert exts.index(".nii.gz") < exts.index(".nii")
    # Short -> long entity mapping.
    assert introspect.short_to_long(schema)["sub"] == "subject"
    assert introspect.modality_for(schema, "anat") == "mri"


def test_split_extension_prefers_longest() -> None:
    schema = resolve()
    assert introspect.split_extension(schema, "x_bold.nii.gz") == ("x_bold", ".nii.gz")
    assert introspect.split_extension(schema, "x_T1w.json") == ("x_T1w", ".json")


def test_parse_filename_entities_suffix_extension() -> None:
    schema = resolve()
    entities, suffix, ext = parse_filename(schema, "sub-01_ses-pre_acq-hi_T1w.nii.gz")
    assert entities == {"sub": "01", "ses": "pre", "acq": "hi"}
    assert suffix == "T1w"
    assert ext == ".nii.gz"


def test_parse_filename_no_suffix_when_last_token_is_an_entity() -> None:
    schema = resolve()
    entities, suffix, _ = parse_filename(schema, "sub-01_ses-pre")
    assert entities == {"sub": "01", "ses": "pre"}
    assert suffix == ""


def test_entities_are_keyed_by_short_name(tmp_path) -> None:
    # The context keys entities by short name (matching the reference validator).
    schema = resolve()
    entities, _, _ = parse_filename(schema, "sub-01_acq-hi_T1w.nii.gz")
    assert entities == {"sub": "01", "acq": "hi"}
    assert "subject" not in entities and "acquisition" not in entities


def test_filetree_indexes_and_skips_hidden(tmp_path) -> None:
    (tmp_path / "dataset_description.json").write_text("{}")
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_text("x")
    (tmp_path / "sub-01" / "anat" / "sub-01_T1w.json").write_text("{}")
    (tmp_path / ".bidsval").mkdir()
    (tmp_path / ".bidsval" / "ignore.json").write_text("{}")

    tree = FileTree(tmp_path)
    paths = {f.relpath for f in tree.files()}
    assert "dataset_description.json" in paths
    assert "sub-01/anat/sub-01_T1w.nii.gz" in paths
    assert not any(".bidsval" in p for p in paths)  # hidden dir skipped
    assert tree.subjects() == ["sub-01"]
    assert tree.exists("sub-01/anat/sub-01_T1w.json")
    # Sidecars in a directory, and the ancestor chain for inheritance.
    sidecars = {f.name for f in tree.json_sidecars_in("sub-01/anat")}
    assert sidecars == {"sub-01_T1w.json"}
    assert tree.ancestor_dirs("sub-01/anat/sub-01_T1w.nii.gz") == ["sub-01/anat", "sub-01", ""]


def test_filetree_treats_directory_recordings_as_existing(tmp_path) -> None:
    # A directory-based recording (CTF .ds) must resolve as existing, so the
    # scans-table existence check does not false-positive on it.
    rec = tmp_path / "sub-01" / "meg" / "sub-01_task-rest_meg.ds"
    rec.mkdir(parents=True)
    (rec / "data.meg4").write_text("x")
    tree = FileTree(tmp_path)
    assert tree.exists("sub-01/meg/sub-01_task-rest_meg.ds")   # the directory itself
    assert not tree.exists("sub-01/meg/missing.ds")
    assert not tree.exists("../escape")                         # no traversal
