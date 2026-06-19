# Schema selection

bidsval validates against one BIDS schema, chosen with a single selector. There
is exactly one knob - `--schema` (CLI) / `schema=` (API) - so the schema and its
versions are always consistent.

## One selector, no conflicting versions

A BIDS schema carries two version numbers: the **BIDS specification version**
(e.g. `1.11.1`) and the schema's own **structural version** (e.g. `1.2.1`). These
are different counters, but they travel together inside one schema artifact.

bidsval never lets you set them independently. You choose the schema by BIDS
version (or a URL/path), and the structural version is whatever that schema
contains. So it is impossible to ask for, say, an old schema with a newer BIDS
version - there is only one thing to choose, and it determines everything.

```python
bidsval.bids_version(bidsval.resolve("1.11.1"))    # '1.11.1'
bidsval.schema_version(bidsval.resolve("1.11.1"))  # '1.2.1'  (derived, not chosen separately)
```

## Selector forms

| Selector | Meaning |
|---|---|
| omitted / `None` | the bundled latest (default) |
| a BIDS version, e.g. `"1.10.0"` | a bundled version (offline) |
| `"latest"` | the development tip, fetched from the spec and cached |
| a not-yet-bundled version, e.g. `"1.7.0"` | fetched from the spec and cached (errors clearly if unavailable) |
| a URL, e.g. `"https://.../schema.json"` | fetched and cached |
| a path to `schema.json` | a local dereferenced schema |
| a path to a YAML source directory (e.g. `bids-specification/src/schema`) | a local/forked schema in authoring form (dereferenced on load) |

```shell
bidsval validate /data --schema 1.9.0
bidsval validate /data --schema latest
bidsval validate /data --schema https://bids-specification.readthedocs.io/en/v1.10.0/schema.json
bidsval validate /data --schema /path/to/bids-specification/src/schema
bidsval schema --schema 1.10.0      # show what a selector resolves to
```

```python
bidsval.available_versions()   # bundled versions, e.g. ['1.8.0', ..., '1.11.1']
```

## Why bundling a single JSON is complete

The schema is authored as a directory of YAML files, but is compiled into one
dereferenced `schema.json` - the form `bidsschematools`, the reference validator,
and the published per-version artifacts all consume. bidsval bundles that JSON
per version (fully dereferenced, every `objects`/`rules`/`meta` section present)
and can also load the YAML source directory directly, dereferencing it on the
fly.

Fetched schemas are cached under `~/.cache/bidsval/schemas/` (honours
`XDG_CACHE_HOME`), so repeated and offline use is free.
