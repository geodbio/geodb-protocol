# the geoDB Open Exploration Protocol

**An open, machine-readable contract for pulling QA/QC'd mineral-exploration data
out of a geoDB project — drill collars, samples, assays, surveys, geophysics,
rasters, and documents — over a standard, authenticated REST + STAC surface.**

Mineral exploration data is trapped in bespoke databases with no public API. A
junior's data lives in one system, their consultant works in another, and every
AI-targeting or resource-modelling vendor re-solves the same
collect-standardize-clean problem from scratch. This protocol makes a geoDB
project's data **pullable as a feed**: adopt the standards the geospatial world
already agreed on (STAC 1.1, COG, GeoParquet, OpenAPI 3), and contribute only the
missing *exploration* vocabulary.

- **Spec + docs:** CC-BY-4.0 · **Schemas + code:** Apache-2.0
- **Version:** `0.1.0` (pre-1.0 — the shape is stable, field details may still move)
- **Reference implementation:** the geoDB API itself (this is not a paper standard)
- **Python client:** [`geodb-client`](https://pypi.org/project/geodb-client/) — `pip install geodb-client`

## Two lanes

| Lane | What | Transport |
|---|---|---|
| **Records** | Relational, chain-of-custody data (collar / survey / interval / assay / QC / certificate / laboratory) — the first-in-category part | Read-only REST (OpenAPI 3), bulk as **GeoParquet** / CSV |
| **Assets** | Surveys, rasters, documents as catalog items with footprints + checksums; grids also as **COG** | A per-project **STAC 1.1** catalog + the `xpl:` exploration extension |

## Auth model (read this first)

Every endpoint is **authenticated and project-scoped**. There is no anonymous
access to customer data. A project owner mints a **project-pinned, read-only,
revocable access grant** (Project Settings → API Access Grants) and hands the
token to a vendor:

```
Authorization: Grant gdbg_<token>
```

- The grant is pinned to exactly **one project** — it can never read another.
- It is **read-only**. The single exception is `POST /api/v2/exports/`, which
  creates an export *job* (it mutates no customer data).
- Every pull lands in a **customer-visible access log** — the owner sees exactly
  what the vendor pulled, and when. Revoke or rotate at any time.
- Asset downloads are **short-lived signed redirects** (302 → a ~5-minute URL);
  no long-lived links are ever embedded in the catalog JSON.

Existing first-party clients (mobile, QGIS, Blender) keep using Knox tokens
(`Authorization: Token …`) — unchanged.

## What's in this repo

```
spec/openapi.yaml          OpenAPI 3 for the read surface (generated; regen script below)
schemas/                   Chain-of-custody JSON Schemas (collar, survey, interval,
                           assay, certificate, laboratory, qc-sample) — the vocabulary
                           Evo/OMF don't define
stac/xpl/schema.json       The xpl: STAC extension JSON Schema (generated)
stac/xpl/README.md         The xpl: extension — fields, profiles, item examples
stac/xpl/examples/         Worked STAC items (airborne-mag survey, drillhole package)
scripts/regenerate.py      Re-emit openapi.yaml + xpl/schema.json from a geoDB checkout
scripts/validate.py        Validate schemas, spec, and examples offline (no checkout needed)
CHANGELOG.md               Version history
CONTRIBUTING.md            How to file a useful issue; how decisions get made
SECURITY.md                How to report a vulnerability; scope; disclosure window
LICENSE (Apache-2.0)       Code + schemas
LICENSE-docs (CC-BY-4.0)   Spec + documentation
```

## Quickstart (20 lines to DataFrames)

```python
import geodb

gx = geodb.Client(token="gdbg_...", base_url="https://api.geodb.io")

collars = gx.collars().to_dataframe()        # every drill collar → pandas
assays  = gx.assays().to_dataframe()         # merged assay values → pandas
surveys = gx.surveys().to_dataframe()        # geophysical surveys + footprints

# Walk the STAC catalog and pull a Cloud-Optimized GeoTIFF
for item in gx.stac().items("rasters"):
    cog = item.asset("cog")
    if cog:
        cog.download("grid.tif")             # short-SAS redirect, streamed
        break

# Trigger a GeoParquet bulk export and get the file
job = gx.export("drill_samples", format="geoparquet")
path = job.wait().download("samples.parquet")
```

## The `xpl:` STAC extension

STAC 1.1 has ~89 extensions and **zero** for geophysics, drilling, or mining.
`xpl:` is the first — the exploration vocabulary for STAC items (geophysical
surveys today; drillhole-package and assay-certificate profiles defined for
adopters). See [`stac/xpl/README.md`](stac/xpl/README.md).

## Changes feed (sync without webhooks)

There is no webhook fan-out in v1. Clients poll with the existing sync semantics:
list endpoints accept `?modified_since=<iso8601>` for incremental pulls, and a
`deleted_since` companion surfaces soft-deletes so a mirror stays consistent.
(Outbound webhooks are a documented v2 item.)

## Non-goals (v1)

STAC `/search` + stac-geoparquet; OGC API-Features conformance formalities;
Evo/OMF/geoh5/LAS export dialects; outbound webhooks. These are tracked, not
built. This protocol adopts existing standards and adds the one missing
vocabulary — it is deliberately small.

## Contributing and security

If something here is ambiguous, missing, or wrong, that is the thing we most want to
hear about — [`CONTRIBUTING.md`](CONTRIBUTING.md) says what makes a useful issue, who
reads the tracker, and how decisions get made. You do not need permission, an NDA, or
a partnership to implement, fork, or criticise this specification.

Security problems go to **security@geodb.io**, not the issue tracker —
[`SECURITY.md`](SECURITY.md) has scope, what to include, and our disclosure window.

**How to validate locally:** `python scripts/validate.py` checks every schema, the
`xpl:` extension, the OpenAPI document, and the worked STAC examples — offline, with
no geoDB checkout and no credentials. It needs `jsonschema` and `pyyaml`.

## Governance

A public repo with issues open. Nothing heavier until adoption forces it —
explicitly **not** a consortium or a standards-body submission. Validation
tooling, never certification.
