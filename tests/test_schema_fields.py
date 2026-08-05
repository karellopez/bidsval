"""The public schema-introspection API.

These answer "what does BIDS say about a file of this kind", which is the
question an editor, a metadata form or a conversion template asks before any
file exists. The validator answers the later question "is this dataset
correct", and the two must not drift, so several tests here pin the API against
the validator's own interpretation.

Most of this file exists because of bugs found while building it. Each of those
has a named regression test: the failure modes were all silent, producing a
plausible-looking but wrong answer rather than an error.
"""

from __future__ import annotations

import pytest

from bidsval import schema as S
from bidsval.issues import Severity
from bidsval.rules.engine import _LEVEL_TO_SEVERITY, field_severity, level_of

# ---------------------------------------------------------------------------
# level_of: the split that lets a level survive being turned into a severity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "requirement, expected",
    [
        ("required", "required"),
        ("recommended", "recommended"),
        ("optional", "optional"),
        ("prohibited", "prohibited"),
        ("something the schema never says", "optional"),
        (None, "optional"),
        (42, "optional"),
    ],
)
def test_level_of_plain_requirements(requirement, expected) -> None:
    assert level_of(requirement, {}) == expected


def test_level_of_honours_a_conditional_addendum() -> None:
    """The schema raises some levels conditionally, e.g. MTState."""
    requirement = {
        "level": "optional",
        "level_addendum": "required if `MTState` is `true`",
    }
    assert level_of(requirement, {"sidecar": {"MTState": "true"}}) == "required"
    assert level_of(requirement, {"sidecar": {"MTState": "false"}}) == "optional"


def test_level_of_without_a_context_gives_the_unconditional_level() -> None:
    """Asking "what does the standard say in general" must not need a file."""
    requirement = {
        "level": "optional",
        "level_addendum": "required if `MTState` is `true`",
    }
    assert level_of(requirement) == "optional"


def test_severity_still_derives_from_level() -> None:
    """REGRESSION: the split must not change what the validator reports."""
    for level, severity in _LEVEL_TO_SEVERITY.items():
        assert field_severity(level, {}) is severity


def test_an_unknown_level_is_ignored_not_reported() -> None:
    assert field_severity("nonsense", {}) is Severity.IGNORE


# ---------------------------------------------------------------------------
# sidecar_fields
# ---------------------------------------------------------------------------


def test_anat_is_not_empty() -> None:
    """THE headline regression.

    A consumer reading only ``rules.sidecars.anat`` sees nothing, because the
    schema files most MRI metadata under selectors on ``modality == "mri"``.
    An anatomical scan getting zero fields is the defect this API exists to
    prevent, so assert generously rather than exactly.
    """
    fields = S.sidecar_fields("anat", "T1w")
    assert len(fields) > 60
    names = {f.name for f in fields}
    assert {"Manufacturer", "MagneticFieldStrength", "EchoTime"} <= names


@pytest.mark.parametrize(
    "datatype, suffix, floor",
    [
        ("anat", "T1w", 60),
        ("anat", "T2w", 60),
        ("func", "bold", 60),
        ("dwi", "dwi", 55),
        ("fmap", "epi", 55),
        ("eeg", "eeg", 30),
        ("meg", "meg", 30),
        ("ieeg", "ieeg", 30),
        ("pet", "pet", 70),
    ],
)
def test_every_datatype_reports_fields(datatype, suffix, floor) -> None:
    assert len(S.sidecar_fields(datatype, suffix)) >= floor


def test_results_are_ordered_required_first() -> None:
    """The order a form wants: required first, the two dead levels last."""
    rank = {"required": 0, "recommended": 1, "optional": 2, "deprecated": 3, "prohibited": 4}
    for datatype, suffix in (("pet", "pet"), ("func", "bold"), ("anat", "T1w")):
        levels = [f.level for f in S.sidecar_fields(datatype, suffix)]
        assert levels == sorted(levels, key=lambda x: rank[x]), f"{datatype}/{suffix}"


def test_a_deprecated_field_says_so() -> None:
    """REGRESSION 9: the schema marks a few fields deprecated, but that level
    was not in the severity map, so it collapsed to `optional` and an editor
    could not tell a curator to stop using the field. Nothing is REPORTED for
    them either way, so the validator is unaffected."""
    spec = {f.name: f.level for f in S.sidecar_fields("pet", "pet")}
    assert spec["ScanDate"] == "deprecated"
    assert {f.name: f.level for f in S.sidecar_fields("ieeg", "ieeg")}[
        "DCOffsetCorrection"
    ] == "deprecated"


def test_deprecation_beats_a_more_permissive_general_rule() -> None:
    """`AcquisitionDuration` is optional for MRI at large and deprecated for
    func/bold in particular. Both rules apply; the form should say deprecated,
    because that is the one that tells the curator something."""
    spec = {f.name: f.level for f in S.sidecar_fields("func", "bold")}
    assert spec["AcquisitionDuration"] == "deprecated"


def test_fields_carry_their_type_and_description() -> None:
    """A form needs more than a name: the type drives the widget."""
    spec = {f.name: f for f in S.sidecar_fields("pet", "pet")}
    assert spec["FrameDuration"].type == "array"
    assert spec["TracerName"].description


def test_pet_requires_what_pet_requires() -> None:
    spec = {f.name: f.level for f in S.sidecar_fields("pet", "pet")}
    for name in ("TracerName", "TracerRadionuclide", "Units", "ModeOfAdministration"):
        assert spec[name] == "required", name


def test_eeg_reference_is_eeg_only() -> None:
    """The applicability question a table column asks."""
    assert S.field_applies("EEGReference", "eeg", "eeg")
    assert not S.field_applies("EEGReference", "anat", "T1w")
    assert not S.field_applies("EEGReference", "pet", "pet")


def test_tracer_is_pet_only() -> None:
    assert S.field_applies("TracerName", "pet", "pet")
    assert not S.field_applies("TracerName", "meg", "meg")
    assert not S.field_applies("TracerName", "anat", "T1w")


def test_repetition_time_is_func_only() -> None:
    """Worth pinning because it is counter-intuitive: the schema declares
    RepetitionTime for func/bold and MRS, not for anatomical scans. An API that
    returned it for anat would be over-reporting, which is how a form ends up
    asking for metadata the standard never wanted."""
    assert S.field_applies("RepetitionTime", "func", "bold")
    assert not S.field_applies("RepetitionTime", "anat", "T1w")


def test_power_line_frequency_is_electrophysiology_only() -> None:
    for datatype, suffix in (("eeg", "eeg"), ("meg", "meg"), ("ieeg", "ieeg")):
        assert S.field_applies("PowerLineFrequency", datatype, suffix)
    for datatype, suffix in (("anat", "T1w"), ("func", "bold"), ("pet", "pet")):
        assert not S.field_applies("PowerLineFrequency", datatype, suffix)


# ---------------------------------------------------------------------------
# Regressions: five silent bugs found while building this
# ---------------------------------------------------------------------------


def test_meg_rules_gated_on_a_task_entity_are_not_lost() -> None:
    """REGRESSION 1: every MEG rule is gated on `"task" in entities`.

    Matching unknowable context names by prefix missed that form (no dot), so
    the selector evaluated false against an empty entities dict and MEG lost
    most of its fields. The synthetic context now carries the entities the
    schema declares REQUIRED for the datatype/suffix.
    """
    names = {f.name for f in S.sidecar_fields("meg", "meg")}
    assert {"SamplingFrequency", "PowerLineFrequency", "DewarPosition"} <= names


def test_a_plain_bold_run_is_not_told_flip_angle_is_required() -> None:
    """REGRESSION 2: several conditional rules applied at once and the
    strictest won. FlipAngle is required only when the `flip` entity is present
    or LookLocker is true; by default it is recommended."""
    spec = {f.name: f for f in S.sidecar_fields("func", "bold")}
    assert spec["FlipAngle"].level == "recommended"
    assert spec["FlipAngle"].conditional, "the caller should know it can change"


def test_conditional_and_speculative_are_different_questions() -> None:
    """REGRESSION 10: one flag conflated "the level might change" with "this
    rule might not describe this file", and a consumer cannot enforce anything
    without telling those apart.

    RepetitionTime on a bold run is conditional (the schema excuses it when
    VolumeTiming is present) but its rule certainly applies, so a missing value
    is a real violation. SkullStripped is required of DERIVATIVES, and nothing
    in a datatype and suffix says whether this dataset is one, so demanding it
    of a raw scan invents a violation. BIDS Manager reported exactly that on
    every raw dwi until this split existed.
    """
    spec = {f.name: f for f in S.sidecar_fields("func", "bold")}
    assert spec["RepetitionTime"].level == "required"
    assert spec["RepetitionTime"].conditional
    assert not spec["RepetitionTime"].speculative

    assert spec["SkullStripped"].level == "required"
    assert spec["SkullStripped"].speculative


def test_raw_scans_have_no_speculative_hard_requirements() -> None:
    """What a raw dataset may actually be held to. dwi and anat genuinely
    declare no required sidecar field; if either ever reports one, a
    derivative-only rule has leaked back in."""
    for datatype, suffix in (("dwi", "dwi"), ("anat", "T1w")):
        hard = [
            f.name
            for f in S.sidecar_fields(datatype, suffix)
            if f.level == "required" and not f.speculative
        ]
        assert hard == [], f"{datatype}/{suffix}: {hard}"
    pet = [
        f.name for f in S.sidecar_fields("pet", "pet")
        if f.level == "required" and not f.speculative
    ]
    assert "TracerName" in pet and len(pet) > 20


def test_a_supplied_sidecar_resolves_the_conditional() -> None:
    spec = {f.name: f.level for f in S.sidecar_fields(
        "func", "bold", sidecar={"LookLocker": True})}
    assert spec["FlipAngle"] == "required"


def test_derivative_rules_nested_three_deep_are_found() -> None:
    """REGRESSION 3: most rule groups are two levels
    (sidecars.mri.MRIHardware) but derivatives are three
    (sidecars.derivatives.common_derivatives.SegmentationCommon). A fixed-depth
    walk silently dropped them, and dseg lost SpatialReference entirely."""
    names = {f.name for f in S.sidecar_fields("anat", "dseg")}
    assert {"SpatialReference", "Description"} <= names


def test_a_standard_template_space_does_not_require_spatial_reference() -> None:
    """REGRESSION 4, two causes at once.

    The rule demanding SpatialReference applies only to NON-standard spaces,
    and its test sat behind an unevaluable DatasetType selector that used to
    short-circuit. The check also needs `schema` in the context, because it
    reads a controlled vocabulary out of it; without that the lookup came back
    empty and inverted the result.
    """
    standard = {f.name: f.level for f in S.sidecar_fields(
        "anat", "dseg", entities={"subject": "x", "space": "MNI152NLin2009cAsym"})}
    custom = {f.name: f.level for f in S.sidecar_fields(
        "anat", "dseg", entities={"subject": "x", "space": "myCustomSpace"})}
    assert standard["SpatialReference"] == "recommended"
    assert custom["SpatialReference"] == "required"


def test_dataset_description_does_not_borrow_the_atlas_rules() -> None:
    """REGRESSION 5: rules.dataset_metadata also describes genetic_info.json
    and atlas description files. Ignoring selectors merged them in, and
    required-License is the atlas rule's answer, not dataset_description's."""
    spec = {f.name: f.level for f in S.dataset_description_fields()}
    assert spec["License"] == "recommended"


# ---------------------------------------------------------------------------
# Regressions: another modality's fields leaking in
#
# Three separate causes, all producing the same visible nonsense: an EEG form
# asking for magnetisation-transfer pulse shape.
# ---------------------------------------------------------------------------


MRI_SEQUENCE_FIELDS = ("MTPulseShape", "MTState", "SpoilingType", "EchoTime", "FlipAngle")


@pytest.mark.parametrize("datatype, suffix", [("eeg", "eeg"), ("meg", "meg"), ("ieeg", "ieeg")])
@pytest.mark.parametrize("field", MRI_SEQUENCE_FIELDS)
def test_mri_sequence_fields_do_not_reach_electrophysiology(field, datatype, suffix) -> None:
    assert not S.field_applies(field, datatype, suffix)


@pytest.mark.parametrize("field", MRI_SEQUENCE_FIELDS)
def test_the_same_fields_still_reach_mri(field) -> None:
    """The other half of the guard: suppressing the leak must not suppress the
    fields where they belong."""
    assert S.field_applies(field, "anat", "T1w")


def test_a_gate_on_an_unreachable_sidecar_key_is_not_an_open_question() -> None:
    """REGRESSION 6: `sidecars.mri.MTParameters` is gated only on
    `sidecar.MTState == true` and says nothing about modality. Read literally
    the gate is unsettled for an EEG recording, so MT parameters were offered
    for EEG, MEG and PET. Every rule that could put MTState in a sidecar needs a
    NIfTI file or MRI modality, so an EEG sidecar can never carry it."""
    assert not S.field_applies("MTPulseShape", "pet", "pet")
    assert S.field_applies("MTPulseShape", "func", "bold")


def test_the_default_extension_is_one_the_datatype_allows() -> None:
    """REGRESSION 7: the default was a hardcoded `.nii.gz`, which is not a
    harmless placeholder. It made every NIfTI-only rule apply to EEG and MEG."""
    for datatype, suffix in (("eeg", "eeg"), ("meg", "meg"), ("nirs", "nirs")):
        assert not S.field_applies("EchoTime", datatype, suffix)
    # An explicit extension is still honoured.
    assert S.sidecar_fields("anat", "T1w", extension=".nii.gz")


def test_an_entity_the_datatype_cannot_carry_settles_the_rule() -> None:
    """REGRESSION 8: `"ce" in entities` was treated as merely unsettled, so
    contrast-agent metadata was offered for every datatype. An anatomical scan
    may carry `ce`; a diffusion scan may not, and the schema says so."""
    assert S.field_applies("ContrastBolusIngredient", "anat", "T1w")
    assert not S.field_applies("ContrastBolusIngredient", "dwi", "dwi")
    assert not S.field_applies("ContrastBolusIngredient", "eeg", "eeg")


def test_a_suffix_with_no_raw_filename_rule_keeps_its_fields() -> None:
    """The necessary escape hatch. `dseg` is derivative-only, so the schema
    lists no raw entities for it; concluding "no entity is allowed" would strip
    it of exactly the fields the derivative rules exist to add."""
    names = {f.name for f in S.sidecar_fields("anat", "dseg")}
    assert {"SpatialReference", "Description"} <= names


def test_entities_are_accepted_under_either_spelling() -> None:
    """The schema keys filename rules by long name (`ceagent`) and writes
    selectors with the short one (`"ce" in entities`), so the API has to answer
    to both or it silently ignores what the caller passed."""
    def levels(entities):
        return [(f.name, f.level) for f in S.sidecar_fields("anat", "T1w", entities=entities)]

    short = levels({"ce": "gad"})
    assert short == levels({"ceagent": "gad"})
    assert ("ContrastBolusIngredient", "optional") in short


def test_units_belongs_to_pet_not_eeg() -> None:
    """`Units` reads like a universal field. The schema declares it for PET, for
    fieldmaps and for phase images, and not for electrophysiology."""
    assert S.field_applies("Units", "pet", "pet")
    assert not S.field_applies("Units", "eeg", "eeg")


# ---------------------------------------------------------------------------
# dataset_description
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, level",
    [
        ("Name", "required"),
        ("BIDSVersion", "required"),
        ("License", "recommended"),
        ("DatasetType", "recommended"),
        ("GeneratedBy", "recommended"),
        ("SourceDatasets", "recommended"),
        ("Funding", "optional"),
        ("EthicsApprovals", "optional"),
        ("ReferencesAndLinks", "optional"),
        ("Acknowledgements", "optional"),
        ("HowToAcknowledge", "optional"),
        ("DatasetDOI", "optional"),
    ],
)
def test_dataset_description_levels(field, level) -> None:
    """Ground truth for a top-level file that has no datatype and no suffix.

    A consumer that guesses these from finding severity gets them wrong, and
    paints four optional fields as required.
    """
    spec = {f.name: f.level for f in S.dataset_description_fields()}
    assert spec[field] == level


def test_authors_is_not_required() -> None:
    """The specific badge that was wrong downstream."""
    spec = {f.name: f.level for f in S.dataset_description_fields()}
    assert spec["Authors"] != "required"


# ---------------------------------------------------------------------------
# Shape and robustness
# ---------------------------------------------------------------------------


def test_unknown_datatype_returns_something_sane() -> None:
    """A caller passing a folder name that is not a datatype must not crash."""
    assert isinstance(S.sidecar_fields("notadatatype", "T1w"), list)


def test_conditional_flag_marks_the_uncertain_ones() -> None:
    fields = S.sidecar_fields("anat", "T1w")
    assert any(f.conditional for f in fields)
    assert any(not f.conditional for f in fields)


def test_field_spec_convenience_properties() -> None:
    spec = {f.name: f for f in S.dataset_description_fields()}
    assert spec["Name"].is_required
    assert not spec["Name"].is_recommended
    assert spec["License"].is_recommended


def test_the_public_namespace_is_exported() -> None:
    for name in (
        "FieldSpec", "sidecar_fields", "dataset_description_fields",
        "field_applies", "datatypes", "suffixes", "modality_for",
    ):
        assert name in S.__all__, name
        assert hasattr(S, name), name


def test_modality_for_is_the_mapping_consumers_kept_re_deriving() -> None:
    ns = S.resolve(None)
    assert S.modality_for(ns, "anat") == "mri"
    assert S.modality_for(ns, "func") == "mri"
    assert S.modality_for(ns, "eeg") == "eeg"
