# Schema introspection

Validation answers "is this dataset correct?". It needs a dataset to exist first.

There is an earlier question the same schema can answer: **what does BIDS say
about a file of this kind?** Which sidecar fields apply to a `func/bold` run, at
which requirement level, of which type, with which controlled vocabulary. A
metadata form, a conversion template or a table of proposed filenames needs that
answer *before* any file has been written.

`bidsval.schema` exposes it as a small read-only API. It reads the same bundled
schema, through the same expression evaluator, as the validator. That is the
point: a tool that fills metadata and a tool that checks metadata should not hold
two different beliefs about the standard.

```python
from bidsval import schema

for field in schema.sidecar_fields("pet", "pet"):
    if field.is_required:
        print(field.name, field.type, field.description[:60])
```

## `sidecar_fields(datatype, suffix, ...)`

Returns the sidecar fields the schema declares for a file, ordered required,
recommended, optional, deprecated, prohibited, then alphabetically inside each
group. That is the order a form wants to render: the live levels first and the
two dead ones at the bottom.

Where several rules declare the same field at different levels, the stronger
statement wins, and `deprecated` counts as stronger than `optional`. Both permit
the field, but only one of them warns you off it: `AcquisitionDuration` is
optional for MRI at large and deprecated for `func/bold` in particular, and a
form is more use if it says deprecated.

```python
schema.sidecar_fields(
    datatype,                    # "anat", "func", "eeg", "pet", ...
    suffix,                      # "T1w", "bold", "eeg", "pet", ...
    extension=None,              # default: one the schema allows for this file
    schema=None,                 # any --schema selector; None = bundled default
    entities=None,               # {"task": "rest", "ce": "gad"}
    sidecar=None,                # values already known, to resolve conditionals
)  # -> list[FieldSpec]
```

`entities` and `sidecar` are how you narrow the answer. Without them you get the
general answer for that kind of file, with anything that depends on unknown
values reported at its default level and flagged `conditional`. Supply them and
the conditional rules resolve:

```python
# A plain BOLD run: FlipAngle is recommended.
plain = {f.name: f.level for f in schema.sidecar_fields("func", "bold")}
plain["FlipAngle"]                     # "recommended"

# Look-Locker acquisitions must state it.
known = {f.name: f.level for f in schema.sidecar_fields(
    "func", "bold", sidecar={"LookLocker": True})}
known["FlipAngle"]                     # "required"
```

Entities may be given under either spelling. The schema keys its filename rules
by long name (`ceagent`) and writes its selectors with the short one
(`"ce" in entities`), so both are accepted and mean the same thing.

`extension` defaults to one the schema declares legal for the datatype and suffix
(`.edf` for EEG, `.fif` for MEG, `.nii.gz` for MRI and PET). It is worth knowing
that this is not cosmetic: a great many rules select on the extension, so
labelling an EEG recording `.nii.gz` makes every NIfTI-only rule apply to it.

### `FieldSpec`

| Attribute | What it is |
|---|---|
| `name` | The sidecar key, e.g. `RepetitionTime`. |
| `level` | `required`, `recommended`, `optional`, `deprecated` or `prohibited`. Nothing is reported for the last two, but a form should still say which one it is. |
| `type` | The JSON type the schema declares: `number`, `string`, `array`, `object`, `boolean`, `integer`. Drives the widget, and the validator will check it. |
| `description` | The standard's own prose. Ready to use as a tooltip. |
| `display_name` | The human-readable name, e.g. `Repetition Time`. |
| `enum` | The controlled vocabulary as a tuple, empty when the field is free. A non-empty `enum` means the value belongs in a dropdown, not a text box. |
| `unit` | The unit the schema declares, empty when it declares none: `FrameDuration` is in `s`. |
| `conditional` | True when the level or the applicability depends on something not supplied. Render it as "recommended, may become required", not as a hard rule. |
| `rule` | The schema rule the field came from, e.g. `rules.sidecars.mri.MRIHardware`. Useful in a "why am I being asked this?" affordance. |

`is_required` and `is_recommended` are convenience properties.

## `dataset_description_fields(...)`

The same, for `dataset_description.json`, which has no datatype and no suffix.

```python
spec = {f.name: f.level for f in schema.dataset_description_fields()}
spec["Name"]        # "required"
spec["License"]     # "recommended"
spec["Funding"]     # "optional"
spec["Authors"]     # "optional", and conditional: the schema raises it to
                    # recommended when the dataset has no CITATION.cff
```

Pass `dataset_description=` to resolve conditionals.

## `field_applies(field, datatype, suffix, ...)`

The applicability question, answered without building the whole list. Useful for
deciding whether a table column or a form section is relevant at all.

```python
schema.field_applies("EEGReference", "eeg", "eeg")     # True
schema.field_applies("EEGReference", "anat", "T1w")    # False
schema.field_applies("TracerName", "pet", "pet")       # True
```

## Vocabulary helpers

Also exported, for consumers that were re-deriving them. Each takes a resolved
schema namespace from `schema.resolve(selector)`; `resolve(None)` gives the
bundled default.

| Function | Returns |
|---|---|
| `datatypes(ns)` | Every datatype the schema defines. |
| `suffixes(ns)` | Every suffix. |
| `extensions(ns)` | Every extension, longest first so multi-part ones match. |
| `modality_for(ns, datatype)` | The modality a datatype belongs to: `anat` and `func` are both `mri`. |
| `entity_pattern(ns, long_name)` | The regex an entity's value must match. |
| `short_to_long(ns)` | `sub` to `subject`, `ce` to `ceagent`, and so on. |
| `metadata_by_name(ns)` | The raw metadata definitions, keyed by field name. |

## Why this is not a datatype lookup

The obvious implementation is to read `rules.sidecars.<datatype>` and return what
is there. It is also wrong, quietly, in both directions.

BIDS does not file sidecar rules by datatype. It files them by **selector
expression**, and the large MRI groups select on modality:
`rules.sidecars.mri.MRIHardware` (16 fields) and `rules.sidecars.mri.MRISequenceSpecifics`
(24 fields) never mention `anat`. Meanwhile a group that *is* named after a
datatype still holds rules that do not apply to every file in it, so reading the
whole group over-reports.

Measured against the bundled schema:

| datatype/suffix | Reading the datatype key | What the schema declares |
|---|---|---|
| anat/T1w | 6 | 76 |
| func/bold | 14 | 85 |
| dwi/dwi | 3 | 73 |
| fmap/epi | 12 | 74 |
| eeg/eeg | 34 | 40 |
| meg/meg | 43 | 49 |
| pet/pet | 85 | 80 |

So this API evaluates the selectors, the way the validator does, against a
synthetic context built from the datatype, suffix, a legal extension, the
entities the schema declares required for that combination, and whatever the
caller supplied.

## What counts as unsettled

Selectors that cannot be determined without a real file (`nifti_header.*`,
`associations.*`, `dataset.*`) do not veto a rule: the field is reported and
marked `conditional`. That is the correct trade for this question. Over-reporting
a field a form might not need costs the user a glance; under-reporting one hides
a requirement until the validator rejects the dataset.

Two kinds of selector look unsettled and are not, and reading them charitably
leaks one modality's fields into another's form:

- **An entity the file may not carry.** `"ce" in entities` is not an open
  question for a diffusion scan. The schema's own filename rules say `dwi` has no
  `ce` entity, so the test is false for every such file. Left as unsettled, it
  offered contrast-agent metadata for EEG, MEG and PET.
- **A sidecar key no applicable rule could declare.** `rules.sidecars.mri.MTParameters`
  is gated only on `sidecar.MTState == true` and says nothing about modality.
  But every rule that could put `MTState` in a sidecar requires a NIfTI file or
  MRI modality, so an EEG sidecar can never contain it and the gate is
  determinately false. Without this, EEG forms offered magnetisation-transfer
  pulse shape.

Both inferences come from the schema, and both fall back to the charitable
reading when the schema does not say. A derivative-only suffix such as `dseg` has
no raw filename rule and therefore no list of permitted entities; concluding
"then no entity is allowed" would strip it of exactly the fields the derivative
rules exist to add, so an empty list means unknown, not empty.

## Consistency with the validator

Both halves read one schema through one evaluator, and the requirement level is
derived once (`rules.engine.level_of`) and mapped to a finding severity
separately. Before that split the level existed only as a severity, so a consumer
wanting the level had to guess it backwards from how loudly the validator
complained. That mapping is not injective: `optional` and `prohibited` are both
silent, so four optional `dataset_description.json` fields came back looking
required.

The test suite pins the two together, including where the API is
counter-intuitive: `RepetitionTime` is declared for `func/bold` and MRS, not for
anatomical scans, and the API says so.
