"""Which metadata fields the standard declares for a file, and at what level.

This is the introspection half of the schema layer. The validator asks "is this
dataset correct"; this module answers the prior question "what does BIDS say
about a file of this kind", which is what an editor, a form or a metadata
template needs before any file exists.

The two are deliberately different in one important way. The validator skips a
rule whose applicability it cannot determine, because guessing would produce a
false positive. Introspection does the opposite: when a selector depends on
something unknowable in the abstract (the contents of a sidecar, which
modalities a dataset happens to contain, whether an optional entity is
present), the field is reported as **potentially applicable**. Hiding a field
that does apply is worse for a form than showing one that might not, and the
caller can see which ones were conditional.

Everything here is read-only and derives from the schema alone.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from typing import Any

from ..expr import EvaluationError, evaluate_string
from ..expr.functions import truthy
from ..rules.engine import level_of
from . import introspect
from .resolve import SchemaSelector, resolve

__all__ = [
    "FieldSpec",
    "dataset_description_fields",
    "field_applies",
    "sidecar_fields",
]


# Context names nothing but a concrete file or dataset can settle. A selector
# mentioning one of these is never grounds for exclusion; the rule is reported
# as conditionally applicable instead.
_UNKNOWABLE_RE = re.compile(r"\b(dataset|nifti_header|associations)\b")

# `sidecar` is deliberately NOT in that list. Sidecar selectors are evaluated
# against the sidecar the caller supplied, or against an empty one, which is
# what makes the DEFAULT case come out right: `sidecar.LookLocker != true`
# holds for a file that says nothing about LookLocker, so FlipAngle is
# recommended rather than required. Treating these as merely unknowable made
# every conditional variant apply at once and the strictest of them won, which
# is how a plain BOLD run ended up being told FlipAngle was required.
# The rule is still marked conditional, so a caller knows the answer could
# change once a real sidecar exists.
_SIDECAR_RE = re.compile(r"\bsidecar\b")

# Entities are different. The synthetic context carries the entities the schema
# declares REQUIRED for the datatype/suffix, so a selector like
# `"task" in entities` evaluates truthfully for MEG. When such a selector is
# false it means the rule needs an OPTIONAL entity the caller did not mention,
# which makes the rule conditional rather than inapplicable.
_ENTITIES_RE = re.compile(r"\bentities\b")

# The two idiomatic ways the schema tests for an entity's presence. An entity
# the schema does not permit for this datatype/suffix can never be present, so
# such a test is determinately false rather than merely unsettled.
_ENTITY_PRESENCE_RE = re.compile(r'"(\w+)"\s+in\s+entities|\bentities\.(\w+)\b')

# A selector reading a specific sidecar key, e.g. `sidecar.MTState == true`.
_SIDECAR_FIELD_RE = re.compile(r"\bsidecar\.(\w+)\b")


@dataclass(frozen=True)
class FieldSpec:
    """One metadata field the standard declares for a given kind of file.

    ``level`` is the BIDS requirement level (``required`` / ``recommended`` /
    ``optional`` / ``deprecated`` / ``prohibited``).

    Two flags say how firm that level is, and they are not the same question.
    ``conditional`` is the broad one: True when either the level or the rule's
    applicability depends on something only a concrete file can settle, so the
    caller should present the field as possible rather than certain.
    ``speculative`` is the sharp one: True when the RULE ITSELF may not describe
    this file at all.

    The difference decides whether a field may be DEMANDED. ``RepetitionTime``
    on a ``func/bold`` run is conditional but not speculative: its rule
    certainly applies and the condition is about an alternative field
    (``VolumeTiming``), so a missing value is a real violation.
    ``SkullStripped`` is both: it is required of derivatives, and nothing about
    a datatype and suffix says whether this dataset is one, so demanding it of
    an ordinary raw scan reports a violation that is not one. Show both; demand
    only the non-speculative.
    """

    name: str
    level: str
    type: str = ""
    item_type: str = ""
    description: str = ""
    display_name: str = ""
    enum: tuple[Any, ...] = ()
    unit: str = ""
    conditional: bool = False
    speculative: bool = False
    rule: str = ""

    @property
    def is_required(self) -> bool:
        return self.level == "required"

    @property
    def is_recommended(self) -> bool:
        return self.level == "recommended"


# ----------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------


def sidecar_fields(
    datatype: str,
    suffix: str,
    *,
    extension: str | None = None,
    schema: SchemaSelector | None = None,
    entities: Mapping[str, str] | None = None,
    sidecar: Mapping[str, Any] | None = None,
) -> list[FieldSpec]:
    """Every sidecar metadata field BIDS declares for ``datatype``/``suffix``.

    The result is ordered required, then recommended, then optional, and
    alphabetically within each level, which is the order a form wants.

    ``entities`` and ``sidecar`` are optional. Supplying them resolves
    conditional rules concretely (a field that is "required if `MTState` is
    `true`" comes back as required); omitting them returns the unconditional
    level with ``conditional=True`` so the caller can mark it.

    ``extension`` defaults to one the schema declares legal for this
    datatype/suffix, because many rules select on it. Forcing ``.nii.gz`` on an
    EEG recording is not a harmless placeholder: it makes NIfTI-only rules apply
    to it.

    Note this reads far more than ``rules.sidecars.<datatype>``: the schema
    groups most MRI metadata under selectors on ``modality``, so ``anat`` gets
    its fields from ``rules.sidecars.mri``. Reading only the datatype key is
    the mistake this function exists to prevent.
    """
    _SEEN.clear()
    ns = resolve(schema)
    entities_supplied = entities is not None
    if entities is None:
        # Represent a minimally VALID file of this kind rather than a bare one.
        # Many rules gate on an entity the schema itself declares required, and
        # `"task" in entities` gates every MEG rule; evaluating that against an
        # empty dict would hide 61 of MEG's 63 fields behind "conditional".
        entities = _required_entities(ns, datatype, suffix)
    if extension is None:
        extension = _default_extension(ns, datatype, suffix)
    context = _context_for(ns, datatype, suffix, extension, entities, sidecar)
    known_concrete = sidecar is not None
    allowed = _allowed_entities(ns, datatype, suffix)

    # Which sidecar keys could this kind of file carry at all. Computed first,
    # because a rule gated on `sidecar.MTState` is unreachable when no rule
    # that applies here can declare MTState in the first place.
    reachable = _reachable_fields(
        ns, context, entities_supplied=entities_supplied,
        sidecar_supplied=known_concrete, allowed_entities=allowed,
    )

    out: dict[str, FieldSpec] = {}
    for rule_path, rule in _sidecar_rules(ns):
        applicability = _rule_applies(
            rule,
            context,
            entities_supplied=entities_supplied,
            sidecar_supplied=known_concrete,
            allowed_entities=allowed,
            reachable=reachable,
        )
        if applicability == "never":
            continue
        for spec, state in _fields_of(ns, rule, rule_path, context, applicability):
            _merge(out, spec, state)
    return _ordered(out.values())


def dataset_description_fields(
    *,
    schema: SchemaSelector | None = None,
    dataset_description: Mapping[str, Any] | None = None,
) -> list[FieldSpec]:
    """Every field BIDS declares for ``dataset_description.json``.

    Separate from :func:`sidecar_fields` because a top-level dataset file has
    no datatype and no suffix, so it cannot be addressed the same way. Callers
    that guess a level for these fields get them wrong: ``Name`` and
    ``BIDSVersion`` are required, ``License`` and ``DatasetType`` recommended,
    and ``Authors``, ``Funding``, ``EthicsApprovals`` and ``ReferencesAndLinks``
    are all merely optional.
    """
    _SEEN.clear()
    ns = resolve(schema)
    supplied = dataset_description is not None
    context: dict[str, Any] = {
        # Selectors identify the file by path, and several sibling rules under
        # rules.dataset_metadata describe OTHER files (genetic_info.json, an
        # atlas description). Without a path they all match, which is how
        # License came back required: that is the atlas rule's answer.
        "path": "/dataset_description.json",
        "suffix": "description",
        "extension": ".json",
        "json": dict(dataset_description or {}),
        "sidecar": {},
        "entities": {},
        "dataset": {},
        "schema": ns,
    }

    rules = _namespace_get(ns, "rules", "dataset_metadata")
    out: dict[str, FieldSpec] = {}
    for rule_name in _keys(rules):
        rule = _as_mapping(_get(rules, rule_name))
        if "fields" not in rule:
            continue
        state = _rule_applies(rule, context, sidecar_supplied=supplied)
        if state == "never":
            continue
        for spec, spec_state in _fields_of(
            ns, rule, f"rules.dataset_metadata.{rule_name}", context, state
        ):
            _merge(out, spec, spec_state)
    return _ordered(out.values())


def field_applies(
    field: str,
    datatype: str,
    suffix: str,
    *,
    extension: str | None = None,
    schema: SchemaSelector | None = None,
) -> bool:
    """True if BIDS declares ``field`` for this kind of file.

    The question a table or a form asks before showing a column: does
    ``PowerLineFrequency`` mean anything for an anatomical scan (no), or
    ``TracerName`` for a MEG recording (no).
    """
    return any(
        spec.name == field
        for spec in sidecar_fields(datatype, suffix, extension=extension, schema=schema)
    )


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


def _context_for(
    ns: Any,
    datatype: str,
    suffix: str,
    extension: str,
    entities: Mapping[str, str] | None,
    sidecar: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """A synthetic evaluation context describing a file of this kind."""
    # Accept either spelling from the caller and evaluate against both, the
    # same way the required entities are carried.
    expanded: dict[str, Any] = {}
    for key, value in (entities or {}).items():
        for name in _both_names(ns, str(key)):
            expanded[name] = value

    return {
        "datatype": datatype,
        "suffix": suffix,
        "extension": extension,
        "modality": introspect.modality_for(ns, datatype),
        "entities": expanded,
        "sidecar": dict(sidecar or {}),
        "dataset": {},
        # The schema itself: selectors reach into it for controlled vocabularies,
        # e.g. `intersects(schema.objects.enums._StandardTemplateCoordSys.enum,
        # [entities.space])`. Omitting it makes every such lookup empty, which
        # silently inverts the test and applied the non-standard-template rule
        # to standard spaces.
        "schema": ns,
        "path": f"/sub-01/{datatype}/sub-01_{suffix}{extension}",
        "size": 1,
    }


def _file_rules(ns: Any, datatype: str, suffix: str) -> Iterator[Mapping[str, Any]]:
    """The ``rules.files.raw`` entries that describe this datatype/suffix.

    These are the schema's own statement of what such a file may be named: which
    entities it may carry and which extensions it may have.
    """
    raw = _namespace_get(ns, "rules", "files", "raw")
    for group in _keys(raw):
        container = _get(raw, group)
        for rule_name in _keys(container):
            rule = _as_mapping(_get(container, rule_name))
            suffixes = rule.get("suffixes") or []
            datatypes = rule.get("datatypes") or []
            if suffix not in suffixes:
                continue
            if datatypes and datatype not in datatypes and group != datatype:
                continue
            yield rule


def _both_names(ns: Any, entity: str) -> set[str]:
    """An entity under both the names a selector might use for it.

    The schema's filename rules key entities by LONG name (``ceagent``) while
    selectors overwhelmingly use the SHORT one (``"ce" in entities``), with a
    handful going the other way (``entities.density``). Carrying both is what
    makes either form evaluate, and costs nothing: the two namespaces do not
    collide, and most entities spell the same in each.
    """
    short_to_long = introspect.short_to_long(ns)
    names = {entity}
    for short, long in short_to_long.items():
        if entity in (short, long):
            names.update((short, long))
    return names


def _required_entities(ns: Any, datatype: str, suffix: str) -> dict[str, str]:
    """Entity names the schema declares REQUIRED for this datatype/suffix.

    Values are placeholders: only presence is ever tested by a selector.
    """
    out: dict[str, str] = {}
    for rule in _file_rules(ns, datatype, suffix):
        for ent, level in _as_mapping(rule.get("entities", {})).items():
            if str(level) == "required":
                for name in _both_names(ns, str(ent)):
                    out[name] = "x"
    return out


def _allowed_entities(ns: Any, datatype: str, suffix: str) -> set[str]:
    """Every entity this kind of file may carry, at any requirement level.

    An empty result means the schema does not describe this datatype/suffix at
    all (a derivative-only suffix such as ``dseg`` has no raw filename rule),
    and callers must fall back rather than conclude that nothing is allowed.
    """
    out: set[str] = set()
    for rule in _file_rules(ns, datatype, suffix):
        for ent in _as_mapping(rule.get("entities", {})):
            out.update(_both_names(ns, str(ent)))
    return out


def _default_extension(ns: Any, datatype: str, suffix: str) -> str:
    """A file extension the schema declares legal for this datatype/suffix.

    Any legal one will do: the extension exists in the context so that rules
    selecting on it can be settled, and the schema's NIfTI-only rules only ever
    need to know that an EEG recording is not a NIfTI. Sidecar extensions are
    skipped because every datatype allows ``.json`` and it would settle nothing.
    A real extension is preferred over the schema's directory forms (``.ds/``,
    ``.mefd/``, and the bare ``/`` MEG uses), which are legal but make a poor
    stand-in for a filename.
    """
    fallback = ""
    for rule in _file_rules(ns, datatype, suffix):
        for ext in rule.get("extensions") or []:
            text = str(ext)
            if text in (".json", ".tsv"):
                continue
            if text.startswith(".") and not text.endswith("/"):
                return text
            fallback = fallback or text
    return fallback or ".nii.gz"


def _reachable_fields(
    ns: Any,
    context: Mapping[str, Any],
    *,
    entities_supplied: bool,
    sidecar_supplied: bool,
    allowed_entities: set[str],
) -> set[str]:
    """Sidecar keys this kind of file could carry, ignoring sidecar gates.

    A first pass, needed because some rules are gated only on the value of
    another metadata field: ``sidecars.mri.MTParameters`` applies when
    ``sidecar.MTState == true`` and says nothing about modality. Read literally
    that gate is merely unsettled for an EEG recording, so magnetisation-transfer
    parameters were offered for EEG and PET. They are not unsettled: every rule
    that could put ``MTState`` in a sidecar requires a NIfTI file or MRI
    modality, so an EEG sidecar can never contain it and the gate is
    determinately false.
    """
    out: set[str] = set()
    for _path, rule in _sidecar_rules(ns):
        state = _rule_applies(
            rule,
            context,
            entities_supplied=entities_supplied,
            sidecar_supplied=sidecar_supplied,
            allowed_entities=allowed_entities,
        )
        if state != "never":
            out.update(_as_mapping(rule.get("fields", {})).keys())
    return out


def _sidecar_rules(ns: Any) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """Every rule under ``rules.sidecars`` that declares fields, at any depth.

    The nesting is not uniform: most groups are two levels
    (``sidecars.mri.MRIHardware``) but the derivative rules are three
    (``sidecars.derivatives.common_derivatives.SegmentationCommon``). Walking a
    fixed depth silently drops the deeper ones, which is how ``dseg`` and
    ``probseg`` lost ``SpatialReference`` and ``Description``.
    """
    yield from _walk_rules(_namespace_get(ns, "rules", "sidecars"), "rules.sidecars")


def _walk_rules(node: Any, path: str) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for name in _keys(node):
        child = _get(node, name)
        mapping = _as_mapping(child)
        if "fields" in mapping:
            yield f"{path}.{name}", mapping
        elif _keys(child):
            yield from _walk_rules(child, f"{path}.{name}")


def _rule_applies(
    rule: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    entities_supplied: bool = False,
    sidecar_supplied: bool = False,
    allowed_entities: set[str] | None = None,
    reachable: set[str] | None = None,
) -> str:
    """How surely does this rule apply to the kind of file being described?

    Returns one of:

    ``"certain"``
        Every selector is settled by facts the caller supplied. The rule
        applies, full stop.
    ``"default"``
        Some selector rests on something invented for the query (an empty
        sidecar, only the required entities, an unknown dataset) and it holds.
        The rule applies to the file as described, but a real file could
        change that.
    ``"possible"``
        Such a selector does not hold. The rule is not describing this file,
        so it must not set the field's level; it only means the level could
        change for some other file.
    ``"never"``
        A selector settled by the caller's own facts is false.

    A selector is only "invented" if the caller did not supply the thing it
    rests on. Passing ``entities`` or ``sidecar`` makes the corresponding
    selectors authoritative, which is what lets a caller ask a precise
    question and get the validator's own answer.

    Two kinds of selector look invented but are not, and treating them as such
    leaks another modality's fields into the answer. A test for an entity the
    schema does not permit here, and a test on a sidecar key no applicable rule
    could ever declare, are both determinately false. ``allowed_entities`` and
    ``reachable`` supply what is needed to tell the difference; both are read
    from the schema, and both fall back to the unsettled reading when absent.

    Every selector is evaluated: returning early on the first unevaluable one
    would skip the checks after it. That is how a ``dseg`` in a standard
    template space was told ``SpatialReference`` is required, when the rule
    demanding it applies only to NON-standard spaces and its test sat behind an
    unevaluable ``DatasetType`` selector.
    """
    state = "certain"
    for selector in rule.get("selectors", []) or []:
        text = str(selector)
        invented = bool(
            _UNKNOWABLE_RE.search(text)
            or (
                _SIDECAR_RE.search(text)
                and not sidecar_supplied
                and _gate_is_reachable(text, reachable)
            )
            or (
                _ENTITIES_RE.search(text)
                and not entities_supplied
                and _entity_test_is_possible(text, allowed_entities)
            )
        )
        try:
            passes = truthy(evaluate_string(text, context))
        except EvaluationError:
            # Unevaluable here. If it rests on something a real file settles,
            # the rule stays possible; otherwise the schema uses a construct we
            # do not implement, and dropping the rule would silently lose
            # fields, so keep it possible as well.
            state = "possible"
            continue
        if not passes:
            if invented:
                state = "possible"
                continue
            return "never"
        if invented and state == "certain":
            state = "default"
    return state


def _item_type(meta: Mapping[str, Any]) -> str:
    """The JSON type of an array field's ELEMENTS, empty when not an array.

    Needed because "array" alone does not say what may go in it, and the schema
    is specific: ``Authors`` holds strings, ``FrameDuration`` numbers,
    ``SourceDatasets`` objects. A consumer building a widget, or writing a
    placeholder, gets it wrong without this.
    """
    items = meta.get("items")
    if items is None:
        return ""
    return str(_as_mapping(items).get("type", "") or "")


def _entity_test_is_possible(text: str, allowed: set[str] | None) -> bool:
    """False when a selector tests for an entity this file may not carry.

    ``"ce" in entities`` is not an open question for an EEG recording: the
    schema's own filename rules say EEG has no ``ce`` entity, so the test is
    false for every such file and the rule genuinely does not apply. Left as
    merely unsettled, it put contrast-agent metadata on EEG and PET forms.

    Only presence tests are read this way. A selector that merely reads an
    entity's value inside a larger expression is not asserting it is there.
    """
    if not allowed:
        return True
    names = {a or b for a, b in _ENTITY_PRESENCE_RE.findall(text)}
    if not names:
        return True
    return any(name in allowed for name in names)


def _gate_is_reachable(text: str, reachable: set[str] | None) -> bool:
    """False when a selector reads a sidecar key this file could never carry.

    See :func:`_reachable_fields`. Note this only decides whether the selector's
    result is authoritative, not what that result is: a NEGATIVE gate such as
    ``sidecar.LookLocker != true`` is then determinately TRUE, which is equally
    correct and equally useful.
    """
    if reachable is None:
        return True
    names = set(_SIDECAR_FIELD_RE.findall(text))
    if not names:
        return True
    return all(name in reachable for name in names)


def _fields_of(
    ns: Any,
    rule: Mapping[str, Any],
    rule_path: str,
    context: Mapping[str, Any],
    applicability: str,
) -> Iterator[tuple[FieldSpec, str]]:
    metadata = _namespace_get(ns, "objects", "metadata")
    for key, requirement in _as_mapping(rule.get("fields", {})).items():
        meta = _as_mapping(_get(metadata, key)) or {}
        level = level_of(requirement, context)
        # A conditional level (level_addendum) is itself a reason to mark the
        # field conditional when no concrete sidecar settled it.
        has_addendum = isinstance(requirement, Mapping) and bool(
            requirement.get("level_addendum")
        )
        yield (
            FieldSpec(
                name=str(meta.get("name", key)),
                level=level,
                type=str(meta.get("type", "") or ""),
                item_type=_item_type(meta),
                description=str(meta.get("description", "") or "").strip(),
                display_name=str(meta.get("display_name", "") or ""),
                enum=tuple(meta.get("enum", ()) or ()),
                unit=str(meta.get("unit", "") or ""),
                # Public flag: the level or the applicability is not settled
                # here, whichever of the two it is.
                conditional=applicability != "certain"
                or (has_addendum and not context.get("sidecar")),
                # The narrower flag: this rule may not describe this file at
                # all, so its level must not be enforced. "default" does
                # describe the file as the caller described it, and only
                # "possible" means the rule failed against invented context.
                speculative=applicability == "possible",
                rule=rule_path,
            ),
            applicability,
        )


# How strong a statement each level is, used when several rules declare the same
# field and one of them has to win. Deprecated outranks optional deliberately:
# both permit the field, but only one of them warns you off it, and that is the
# more informative thing to tell a curator. `AcquisitionDuration` is optional for
# MRI at large and deprecated for func/bold specifically; the form should say
# deprecated.
_LEVEL_RANK = {
    "required": 4,
    "recommended": 3,
    "deprecated": 2,
    "optional": 1,
    "prohibited": 0,
}

# Where each level belongs in a form, which is a different question: deprecated
# and prohibited sink to the bottom however strong a statement they are.
_ORDER_RANK = {
    "required": 0,
    "recommended": 1,
    "optional": 2,
    "deprecated": 3,
    "prohibited": 4,
}

# Rule-certainty of the spec currently kept per field name, for the duration of
# one query. Not part of FieldSpec because it is a merge detail, not something
# a caller needs: the public `conditional` flag already carries the outcome.
_SEEN: dict[str, str] = {}


_APPLIES_RANK = {"certain": 2, "default": 1, "possible": 0}


def _merge(out: dict[str, FieldSpec], spec: FieldSpec, applicability: str) -> None:
    """Combine the several rules that can declare the same field.

    A CERTAIN rule beats a conditional one, and only then does the stronger
    level win. Getting this backwards is subtly wrong in a way that matters:
    ``NonlinearGradientCorrection`` is recommended for MRI by
    ``MRISequenceSpecifics`` (which always applies) and required by
    ``PETMRISequenceSpecifics`` (which applies only when the dataset also
    contains PET). Taking the stronger level unconditionally would tell every
    plain anatomical dataset the field is required, which the validator rightly
    disagrees with.

    When a conditional rule is the stricter one, its level is not adopted but
    its conditionality is: the field keeps the level that certainly applies and
    is marked ``conditional`` so a caller can say "may be required here".
    """
    current = out.get(spec.name)
    if current is None:
        _SEEN[spec.name] = applicability
        out[spec.name] = spec
        return

    here = _APPLIES_RANK.get(applicability, 0)
    there = _APPLIES_RANK.get(_SEEN.get(spec.name, "possible"), 0)

    if here != there:
        # The rule that describes THIS file decides the level. A rule that only
        # might apply contributes nothing but the warning that the level could
        # change, which is what `conditional` carries.
        winner, other = (spec, current) if here > there else (current, spec)
        if here > there:
            _SEEN[spec.name] = applicability
        raises = _LEVEL_RANK.get(other.level, 0) > _LEVEL_RANK.get(winner.level, 0)
        out[spec.name] = replace(winner, conditional=True) if raises else winner
        return

    if _LEVEL_RANK.get(spec.level, 0) > _LEVEL_RANK.get(current.level, 0):
        out[spec.name] = spec


def _ordered(specs: Any) -> list[FieldSpec]:
    return sorted(specs, key=lambda s: (_ORDER_RANK.get(s.level, len(_ORDER_RANK)), s.name))


# -- Namespace / Mapping access -----------------------------------------
# The schema object is a Namespace in some code paths and a plain dict in
# others; these keep the rest of the module free of that distinction.


def _keys(node: Any) -> list[str]:
    if node is None:
        return []
    if hasattr(node, "keys"):
        return list(node.keys())
    return []


def _get(node: Any, key: str) -> Any:
    if node is None:
        return None
    if isinstance(node, Mapping):
        return node.get(key)
    return getattr(node, key, None)


def _namespace_get(ns: Any, *path: str) -> Any:
    node = ns
    for part in path:
        node = _get(node, part)
        if node is None:
            return None
    return node


def _as_mapping(node: Any) -> Mapping[str, Any]:
    if isinstance(node, Mapping):
        return node
    if node is None:
        return {}
    if hasattr(node, "keys"):
        return {k: _get(node, k) for k in node.keys()}
    return {}
