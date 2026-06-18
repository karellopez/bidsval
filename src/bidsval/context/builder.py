"""Assemble the evaluation context for each file in a dataset.

The builder is created once per run with a resolved schema and a file tree. It
computes the dataset-level context (subjects, ``dataset_description``, the
datatypes and modalities present) a single time, then produces a per-file
context on demand. The per-file context is a plain dict so the evaluator can read
it directly, and its keys follow the schema's ``meta.context`` definition.
"""

from __future__ import annotations

from typing import Any

from bidsschematools.types.namespace import Namespace

from ..expr.functions import EXISTS_RESOLVER_KEY
from ..files import BIDSFile, FileTree
from ..schema import introspect
from .associations import build_associations
from .entities import parse_filename
from .inheritance import merged_sidecar
from .loaders import load_columns, load_json, load_nifti_header


class ContextBuilder:
    """Build per-file contexts for a dataset against a schema."""

    def __init__(
        self,
        schema: Namespace,
        tree: FileTree,
        *,
        read_headers: bool = False,
        max_rows: int = 1000,
    ) -> None:
        self.schema = schema
        self.tree = tree
        self.read_headers = read_headers
        self.max_rows = max_rows
        self._datatypes = introspect.datatypes(schema)
        self._dataset = self._build_dataset_context()

    # -- dataset-level (built once) ---------------------------------------

    def _build_dataset_context(self) -> dict[str, Any]:
        dd_file = self.tree.get("dataset_description.json")
        dataset_description = load_json(dd_file) if dd_file else {}
        if "DatasetType" not in dataset_description:
            dataset_description["DatasetType"] = (
                "derivative" if dataset_description.get("GeneratedBy") else "raw"
            )

        participants = self.tree.get("participants.tsv")
        participant_id: list[str] = []
        if participants:
            # Read in full (not capped): this feeds a full-set-equality check.
            participant_id = load_columns(participants, max_rows=-1).get("participant_id", [])

        datatypes_present = sorted(
            {dt for f in self.tree.files() if (dt := self._datatype_of(f.relpath))}
        )
        modalities_present = sorted(
            {m for dt in datatypes_present if (m := introspect.modality_for(self.schema, dt))}
        )

        return {
            "dataset_description": dataset_description,
            "datatypes": datatypes_present,
            "modalities": modalities_present,
            "subjects": {
                "sub_dirs": self.tree.subjects(),
                "participant_id": participant_id,
            },
            "tree": self.tree,
        }

    @property
    def dataset_description(self) -> dict[str, Any]:
        return self._dataset["dataset_description"]

    # -- per-file ----------------------------------------------------------

    def build(self, bids_file: BIDSFile) -> dict[str, Any]:
        """Return the evaluation context for one file."""
        short_entities, suffix, extension = parse_filename(self.schema, bids_file.name)
        datatype = self._datatype_of(bids_file.relpath)
        is_json = extension == ".json"
        is_tsv = extension in (".tsv", ".tsv.gz")

        context: dict[str, Any] = {
            "path": "/" + bids_file.relpath,
            "size": bids_file.size(),
            "entities": short_entities,
            "datatype": datatype,
            "suffix": suffix,
            "extension": extension,
            "modality": introspect.modality_for(self.schema, datatype),
            "sidecar": merged_sidecar(self.schema, self.tree, bids_file),
            "json": load_json(bids_file) if is_json else {},
            "columns": self._load_columns(bids_file, extension) if is_tsv else {},
            "nifti_header": (
                load_nifti_header(bids_file)
                if self.read_headers and extension.startswith(".nii")
                else None
            ),
            "associations": build_associations(
                self.schema, self.tree, bids_file, short_entities, suffix, extension
            ),
            "subject": {},
            "dataset": self._dataset,
            # The schema is part of the context: some checks reference
            # ``schema.meta.versions`` / ``schema.objects.*``.
            "schema": self.schema,
            EXISTS_RESOLVER_KEY: self._make_exists_resolver(bids_file, short_entities),
        }
        return context

    def _datatype_of(self, relpath: str) -> str:
        """The file's datatype: its immediate parent directory, if that is a
        BIDS datatype (mirrors the reference; a deeper nesting is not a datatype)."""
        parts = relpath.split("/")
        parent = parts[-2] if len(parts) >= 2 else ""
        return parent if parent in self._datatypes else ""

    def _load_columns(self, bids_file: BIDSFile, extension: str) -> dict[str, list[str]]:
        """Read a TSV's columns, in full for the small tables that feed
        full-set-equality checks (participants / scans), capped otherwise."""
        name = bids_file.name
        uncapped = name == "participants.tsv" or name.endswith("_scans.tsv")
        return load_columns(bids_file, -1 if uncapped else self.max_rows)

    def _make_exists_resolver(self, bids_file: BIDSFile, short_entities: dict[str, str]):
        """A callable ``(item, rule) -> bool`` the ``exists`` function uses.

        Resolves a referenced path relative to the dataset root, the subject, the
        stimuli directory, or the file's own directory, per the ``rule`` mode.
        """
        sub = short_entities.get("sub", "")
        parent = bids_file.parent

        def resolver(item: Any, rule: str = "dataset") -> bool:
            if not isinstance(item, str):
                return False
            if rule == "bids-uri":
                return item.startswith("bids:")
            if rule == "file":
                target = f"{parent}/{item}" if parent else item
            elif rule == "subject":
                target = f"sub-{sub}/{item}" if sub else item
            elif rule == "stimuli":
                target = f"stimuli/{item}"
            else:  # dataset
                target = item
            return self.tree.exists(target.lstrip("/"))

        return resolver
