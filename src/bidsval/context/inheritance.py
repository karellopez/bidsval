"""Apply the BIDS inheritance principle to assemble a file's sidecar.

A JSON metadata file applies to a data file when it sits in the same directory or
an ancestor, its entities are a subset of the data file's (with matching values),
and its suffix matches. More specific sidecars (deeper directory, more entities)
override less specific ones.
"""

from __future__ import annotations

from bidsschematools.types.namespace import Namespace

from ..files import BIDSFile, FileTree
from .entities import parse_filename
from .loaders import load_json


def merged_sidecar(schema: Namespace, tree: FileTree, data_file: BIDSFile) -> dict[str, object]:
    """Return the inheritance-merged JSON sidecar for ``data_file``.

    Returns an empty dict for a file that is itself JSON (JSON files have no
    sidecar) or that has no suffix.
    """
    name = data_file.name
    if name.endswith(".json"):
        return {}
    source_entities, source_suffix, _ = parse_filename(schema, name)
    if not source_suffix:
        return {}

    # The inheritance principle applies AT MOST ONE sidecar per directory level
    # (the most specific subset match), then merges across levels with the
    # closest level winning. Picking one-per-level avoids pulling fields from a
    # less specific sidecar that the spec would not apply.
    merged: dict[str, object] = {}
    for dir_relpath in tree.ancestor_dirs(data_file.relpath):  # closest first
        chosen = _best_sidecar(schema, tree, dir_relpath, source_entities, source_suffix)
        if chosen is None:
            continue
        data = load_json(chosen)
        if isinstance(data, dict):
            for key, value in data.items():
                merged.setdefault(key, value)  # closest level (seen first) wins
    return merged


def applicable_sidecar_files(schema: Namespace, tree: FileTree, data_file: BIDSFile) -> list[str]:
    """The relpaths of the JSON sidecars that apply to ``data_file`` (one per level).

    Used to mark sidecars as "in use", so a sidecar that applies to no data file can
    be reported. Empty for a JSON file or a file with no suffix.
    """
    name = data_file.name
    if name.endswith(".json"):
        return []
    source_entities, source_suffix, _ = parse_filename(schema, name)
    if not source_suffix:
        return []
    out: list[str] = []
    for dir_relpath in tree.ancestor_dirs(data_file.relpath):
        chosen = _best_sidecar(schema, tree, dir_relpath, source_entities, source_suffix)
        if chosen is not None:
            out.append(chosen.relpath)
    return out


def _best_sidecar(
    schema: Namespace,
    tree: FileTree,
    dir_relpath: str,
    source_entities: dict[str, str],
    source_suffix: str,
) -> BIDSFile | None:
    """The single most-specific sidecar in one directory that applies, or None.

    Prefers a sidecar whose entities exactly match the data file's; otherwise the
    one with the most entities (deterministic by path on a tie).
    """
    candidates: list[tuple[dict[str, str], BIDSFile]] = []
    for candidate in tree.json_sidecars_in(dir_relpath):
        cand_entities, cand_suffix, _ = parse_filename(schema, candidate.name)
        if cand_suffix != source_suffix:
            continue
        if not _is_subset(cand_entities, source_entities):
            continue
        if cand_entities == source_entities:  # exact match: use it directly
            return candidate
        candidates.append((cand_entities, candidate))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (len(item[0]), item[1].relpath))
    return candidates[-1][1]


def _is_subset(candidate: dict[str, str], source: dict[str, str]) -> bool:
    """True if every entity in ``candidate`` is present in ``source`` with the same value."""
    return all(source.get(key) == value for key, value in candidate.items())
