# Architecture

## The schema is the engine

The BIDS schema expresses validation as a small expression language: selectors
decide when a rule applies (`suffix == 'T1w'`) and checks must hold
(`nifti_header.dim[0] == 3`). bidsval reads the schema's vocabulary and rules and
evaluates them against a per-file context. No BIDS vocabulary (datatypes,
entities, suffixes, extensions, fields) is hardcoded - it is all read from the
schema, so a different or newer schema changes behaviour with no code change.

## Pipeline

```
selector --> SchemaResolver --> Namespace (the schema)
dataset  --> FileTree --> for each file:
    ContextBuilder.build(file) --> context (entities, datatype, suffix, sidecar,
        associations, columns, json, nifti_header, dataset, schema)
    rules.apply_rules(schema, context) --> [Issue ...]   (+ bespoke + basename checks)
--> ValidationReport --> render(text|json|sarif|html)
```

## Modules

| Module | Responsibility |
|---|---|
| `schema/` | Resolve a selector to one schema; fetch+cache; read vocabulary (`introspect`). |
| `expr/` | Evaluate the schema's expressions (tree-walk over the `bidsschematools` AST; no `eval`). |
| `files/` | Index the dataset (`FileTree`): skips hidden + `sourcedata`/`code`/`derivatives`; treats directory recordings (`.ds`, `.mefd`) as single entries; indexes symlinks as existing. |
| `context/` | Build the per-file context: entities, datatype, inheritance-merged sidecar, associated files, loaded content. |
| `rules/` | `engine` (checks, sidecar fields, dataset_metadata), `values` (field value types), `tables` (TSV columns), `bespoke` (empty file, unreadable NIfTI). |
| `validate.py` | `validate` / `validate_subject` / `validate_file`. |
| `render/` | text / JSON / SARIF / HTML. |
| `issues.py`, `report.py` | Typed findings and results. |
| `cli.py` | The `bidsval` command. |

## What is checked

- File structure and entity-value patterns.
- Sidecar fields: required/recommended presence (with conditional levels and
  derivative exemption) and value-type validation of every present field against
  its schema metadata definition.
- Associated files: events, bval/bvec, channels, ASL, coordsystem, electrodes, ...
- Tabular columns: required columns, undefined/forbidden extra columns, numeric
  value types.
- Empty files (error) and unreadable NIfTI headers (with `--headers`).

## The no-false-positives invariant

A finding is reported only on a determinate failure. When a rule depends on
context bidsval does not populate (currently the `coordsystems` /
`atlas_description` aggregates and gzip/ome/tiff headers), the rule is skipped,
not guessed. A check that evaluates to null is treated as pass. This is verified:
zero false positives against the reference validator across bids-examples, the
converted datasets, and OpenNeuro (metadata-only). The one place bidsval reports
an error the reference does not (`SIDECAR_KEY_REQUIRED` on PET, for a
PET-conditional field) is bidsval being more schema-faithful, not a false positive.

## Remaining gaps (toward full reference parity)

- Filename/path legality against `rules.files` (unknown entities, illegal
  extensions, wrong-datatype placement).
- The `coordsystems` aggregate and a few tabular checks (column type
  redefinition, order); HED; derivatives recursion.
- Ahead-of-market features: requirement-level completeness per subject, reasoned
  waivers, explain mode (rule provenance is already on every `Issue`), one-click
  fixes (fix hints are already on findings).
