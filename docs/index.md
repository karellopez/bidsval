# bidsval documentation

A schema-driven, pydantic-typed, in-process BIDS validator in pure Python.

bidsval reads the official BIDS schema and checks datasets against the rules it
contains. It runs with no external runtime, returns typed results, and validates
a whole dataset, a single subject, a single file, or a single expression.

- [Usage](usage.md) - install, the CLI, the Python API.
- [CLI reference](cli-reference.md) - every command and option, with examples and exit codes.
- [Schema selection](schema-selection.md) - choosing a schema (the single `--schema` selector).
- [Output formats](output-formats.md) - `--output-type`, `--out-dir`, `--show`.
- [How it works](internals.md) - the complete technical reference: design, dependencies, every layer, flowcharts, and a glossary.

## Design in one paragraph

The schema is the engine. The BIDS schema expresses validation as expressions
(selectors that decide when a rule applies, checks that must hold). bidsval reads
the schema's vocabulary and rules and evaluates them against a per-file context.
No BIDS terms are hardcoded, so a different or newer schema changes behaviour with
no code change. A finding is reported only when a rule produces a determinate
failure; rules whose inputs cannot be determined are skipped, so bidsval does not
emit false errors (verified: zero false positives against the reference validator
across bids-examples, converted datasets, and OpenNeuro).
