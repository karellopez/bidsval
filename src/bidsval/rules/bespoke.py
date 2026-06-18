"""Per-file checks that are not expressed in the schema as rules.

These mirror what the reference validator hard-codes (empty files, unreadable
NIfTI headers), but bidsval reports them more usefully: as warnings (not hard
errors), with an explanation of what the finding does and does not mean, and a
machine-actionable fix. The point is to be clear when something is a content or
readability issue rather than a BIDS structure violation - for example, the
empty placeholder files that example datasets deliberately ship.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..files import BIDSFile
from ..issues import Fix, Issue, Severity


def bespoke_checks(
    bids_file: BIDSFile, context: Mapping[str, Any], *, read_headers: bool
) -> list[Issue]:
    """Run the non-schema per-file checks."""
    issues: list[Issue] = []
    location = bids_file.relpath

    if bids_file.size() == 0:
        issues.append(
            Issue(
                code="EMPTY_FILE",
                severity=Severity.WARNING,
                location=location,
                message="file is empty (0 bytes): it exists but contains no data",
                suggestion=(
                    "An empty file is often an intentional placeholder (example datasets ship "
                    "these). This is a content issue, not a filename or structure violation - the "
                    "name and location are valid, but there is no data. Replace it with real data "
                    "if it should not be empty."
                ),
                fix=Fix(action="replace_empty_file", label="Provide real data for this file"),
            )
        )
        return issues  # nothing else to check on an empty file

    extension = str(context.get("extension", ""))
    if read_headers and extension.startswith(".nii") and context.get("nifti_header") is None:
        issues.append(
            Issue(
                code="NIFTI_HEADER_UNREADABLE",
                severity=Severity.WARNING,
                location=location,
                message="the NIfTI header could not be read",
                suggestion=(
                    "This is a file-readability issue, not necessarily a BIDS structure violation: "
                    "the file may be truncated, compressed oddly, or not a valid NIfTI. Verify it "
                    "opens in a NIfTI reader."
                ),
                fix=Fix(action="inspect_file", label="Check that the file is a valid NIfTI"),
            )
        )
    return issues
