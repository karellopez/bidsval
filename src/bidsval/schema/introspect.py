"""Read BIDS vocabulary out of a schema.

Everything the validator needs to know about BIDS terms - the datatypes, the
entity short/long names and their value patterns, the suffixes, the file
extensions, and which modality a datatype belongs to - is read from the schema
here. Nothing in the validator hardcodes these; point it at a different schema
and the vocabulary changes with it.

Each function takes a ``bidsschematools`` ``Namespace`` and returns plain Python
data. Results are memoized per schema object so repeated calls during a run are
free.
"""

from __future__ import annotations

from typing import Any

from bidsschematools.types.namespace import Namespace

# Memo keyed by the id() of the schema object. Schema objects are cached for the
# life of the process by ``schema.resolve``, so their ids are stable.
_MEMO: dict[int, dict[str, Any]] = {}


def _vocab(schema: Namespace) -> dict[str, Any]:
    cached = _MEMO.get(id(schema))
    if cached is not None:
        return cached

    objects = schema["objects"]

    # Entities: long name -> short name (e.g. "subject" -> "sub"), and the value
    # pattern each entity's value must match (via its named format).
    formats = objects.get("formats", {})
    short_to_long: dict[str, str] = {}
    entity_pattern: dict[str, str] = {}
    for long_name, info in objects["entities"].items():
        short = str(info.get("name", long_name))
        short_to_long[short] = long_name
        fmt = info.get("format")
        pattern = formats.get(fmt, {}).get("pattern") if fmt else None
        if pattern:
            entity_pattern[long_name] = str(pattern)

    # Suffix and extension *values* (the objects are keyed by display name; the
    # real token is in ``.value``).
    suffixes = {str(v.get("value", k)) for k, v in objects["suffixes"].items()}
    extensions = sorted(
        {str(v.get("value", k)) for k, v in objects["extensions"].items()},
        key=len,
        reverse=True,  # longest first so ".nii.gz" wins over ".gz"/".nii"
    )

    datatypes = set(objects["datatypes"].keys())

    # Datatype -> modality, from rules.modalities[*].datatypes.
    datatype_modality: dict[str, str] = {}
    for modality, info in schema.get("rules", {}).get("modalities", {}).items():
        for datatype in info.get("datatypes", []):
            datatype_modality[datatype] = modality

    vocab = {
        "short_to_long": short_to_long,
        "entity_pattern": entity_pattern,
        "suffixes": suffixes,
        "extensions": extensions,
        "datatypes": datatypes,
        "datatype_modality": datatype_modality,
    }
    _MEMO[id(schema)] = vocab
    return vocab


def datatypes(schema: Namespace) -> set[str]:
    """The set of BIDS datatype directory names (anat, func, eeg, ...)."""
    return _vocab(schema)["datatypes"]


def suffixes(schema: Namespace) -> set[str]:
    """The set of valid suffix tokens (T1w, bold, ...)."""
    return _vocab(schema)["suffixes"]


def extensions(schema: Namespace) -> list[str]:
    """Known file extensions, longest first (so multi-part extensions match)."""
    return _vocab(schema)["extensions"]


def short_to_long(schema: Namespace) -> dict[str, str]:
    """Map an entity short name (``sub``) to its long name (``subject``)."""
    return _vocab(schema)["short_to_long"]


def entity_pattern(schema: Namespace, long_name: str) -> str | None:
    """The regex an entity's value must match, or ``None`` if unconstrained."""
    return _vocab(schema)["entity_pattern"].get(long_name)


def modality_for(schema: Namespace, datatype: str) -> str:
    """The modality a datatype belongs to (``anat`` -> ``mri``), or ``""``."""
    return _vocab(schema)["datatype_modality"].get(datatype, "")


def split_extension(schema: Namespace, name: str) -> tuple[str, str]:
    """Split a filename into (stem, extension) using the schema's extension list.

    Falls back to no extension if none match, so unknown files still parse.
    """
    for ext in extensions(schema):
        if ext and name.endswith(ext):
            return name[: -len(ext)], ext
    return name, ""
