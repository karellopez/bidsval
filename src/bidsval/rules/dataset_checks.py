"""Dataset-level checks that look across files, ported from the reference validator.

Unlike the per-file checks, these need the whole dataset at once:

* ``CASE_COLLISION`` - two files whose paths differ only by letter case (a hazard on
  case-insensitive filesystems);
* ``UNUSED_STIMULUS`` - a file in ``stimuli/`` referenced by no ``events.tsv``.

``UNUSED_STIMULUS`` relies on a "viewed" set gathered while the per-file contexts are
built (which stimuli an events table referenced), so a stimulus counts as used
exactly when an events table points at it.

Note: ``SIDECAR_WITHOUT_DATAFILE`` is intentionally not implemented yet. Determining
that a sidecar applies to no data file needs the associations of directory recordings
(CTF ``.ds``, OME-Zarr), which bidsval does not yet resolve; without them, coordsystem
and recording sidecars would be wrongly reported. It is deferred to keep the
no-false-positives guarantee.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..files import BIDSFile, FileTree
from ..issues import Issue, Severity


def dataset_checks(
    tree: FileTree, files: list[BIDSFile], viewed_stimuli: set[str]
) -> list[Issue]:
    """Run the dataset-wide checks over the validated ``files``."""
    issues: list[Issue] = []
    issues += _case_collisions(files)
    issues += _unused_stimulus(tree, viewed_stimuli)
    return issues


def _case_collisions(files: list[BIDSFile]) -> list[Issue]:
    by_lower: dict[str, list[str]] = {}
    for bids_file in files:
        by_lower.setdefault(bids_file.relpath.lower(), []).append(bids_file.relpath)
    issues: list[Issue] = []
    for collisions in by_lower.values():
        if len(collisions) > 1:
            for relpath in sorted(collisions):
                others = ", ".join(sorted(set(collisions) - {relpath}))
                issues.append(
                    Issue(
                        code="CASE_COLLISION",
                        severity=Severity.ERROR,
                        location=relpath,
                        message=f"another file has the same name but a different case: {others}",
                        suggestion=(
                            "On a case-insensitive filesystem these files clash. Rename so the "
                            "paths differ by more than letter case."
                        ),
                    )
                )
    return issues


def _unused_stimulus(tree: FileTree, viewed_stimuli: set[str]) -> list[Issue]:
    stimuli = [f.relpath for f in tree.files() if f.relpath.split("/", 1)[0] == "stimuli"]
    unused = sorted(relpath for relpath in stimuli if relpath not in viewed_stimuli)
    if not unused:
        return []
    return [
        Issue(
            code="UNUSED_STIMULUS",
            severity=Severity.WARNING,
            location="stimuli",
            message=f"{len(unused)} file(s) in stimuli/ are not referenced by any events.tsv",
            suggestion=(
                "Reference each stimulus from an events.tsv 'stim_file' column, or remove the "
                "unused files. First few: " + ", ".join(unused[:5])
            ),
            affects=unused,
        )
    ]


def collect_viewed(
    bids_file: BIDSFile,
    context: Mapping[str, object],
    viewed_stimuli: set[str],
) -> None:
    """Record, from one data file's context, which stimuli it references."""
    columns = context.get("columns") or {}
    if isinstance(columns, Mapping):
        for value in columns.get("stim_file", []):
            if value and value not in ("n/a", ""):
                viewed_stimuli.add("stimuli/" + str(value).lstrip("/"))
