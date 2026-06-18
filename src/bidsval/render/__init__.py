"""Render a validation report in different formats.

Each renderer turns a :class:`~bidsval.report.ValidationReport` into text a
consumer wants:

* :func:`~bidsval.render.json.to_json` - machine-readable JSON (a flat issue list).
* :func:`~bidsval.render.sarif.to_sarif` - SARIF 2.1.0, for code-scanning tools.
* :func:`~bidsval.render.html.to_html` - a self-contained HTML report.

The renderers are pure functions of the report, so the same result can be
emitted to stdout or written to any number of files.
"""

from __future__ import annotations

from .html import to_html
from .json import to_dict, to_json
from .sarif import to_sarif

__all__ = ["to_dict", "to_json", "to_sarif", "to_html"]
