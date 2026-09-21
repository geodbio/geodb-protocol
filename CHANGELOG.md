# Changelog

## [Unreleased]

### Added
- Seven operations the server already served but the committed spec omitted: vector layers (`vector-layers/`, `/{id}/`, `/{id}/features/`), vector features (`vector-features/`, `/{id}/`), `roads/style-spec/`, and project-file raster tiles (`project-files/{id}/tiles/{z}/{x}/{y}.png`). 147 -> 154 paths.
- The `scope` query parameter (`project` | `company`) declared on 24 list operations.
- `docs/` — the GitHub Pages tree that serves every `$id` at `https://spec.geodb.io/...`; `scripts/regenerate.py --check` / `--publish-only` and `scripts/validate.py` fail if a served copy is stale; `scripts/check_ids.py [--live]` proves every published URI resolves.
- `SECURITY.md`, issue templates (ambiguous / missing / wrong / write-semantics), a CI workflow, and a named weekly reader of the issue tracker in `CONTRIBUTING.md`.

### Changed
- **The spec describes the wire exactly** (task A3, with a drift test on the server that fails if it ever diverges again): `extra_data` removed from every Read component (it was declared required and never sent); custom fields declared as `cf_*` pattern properties with types at `/api/v2/model-schemas/`; every Read component closed (`additionalProperties: false`); ONE `PaginatedList` envelope (`count/next/previous/results/deleted_ids/deleted_since_applied/sync_timestamp`); ONE `Error` component (`reason_code`, `detail`, `remedy`, `offending?`) and default 401/403/404/429 on every operation; `modified_since` / `deleted_since` / `scope` / `project_id` declared where they apply, with the DAY-granular `>=` semantics stated; `info.version` is the protocol version (`0.1.0`) and every `/api/v2/` response carries `X-GeoDB-Protocol-Version`; hashed generator enum names replaced.
- **Coordinates (ruling R2):** `latitude` / `longitude` / `epsg` are described exactly (the original as-imported coordinate in the CRS named by `epsg`; degrees only when `epsg == 4326`); NEW read-only `source_coordinate {x, y, epsg}` (the same values under names that cannot be mistaken for degrees) and `geometry_geojson` (WGS84 GeoJSON Point). `geometry` stays EWKT `SRID=4326;POINT Z (...)`.
- **Errors are machine-readable:** an unparseable `modified_since` / `deleted_since` is refused with `invalid_parameter` (it used to be silently ignored, returning everything); a Grant 401 says why (`grant_revoked` / `grant_expired` / `grant_invalid` / `grant_unknown` / `grant_malformed`) with `WWW-Authenticate: Grant`; `/api/v1/` is refused for grants (`use_v2`); an address spraying unknown tokens is throttled (`grant_auth_throttled`).
- ONE schema host: every `$id` and `stac_extensions` URI moved from `schemas.geodb.io` / `stac.geodb.io` (neither ever resolved) to `https://spec.geodb.io/`. Breaking for any consumer that pinned the old URIs; there were none.
- README: the access-log sentence now states exactly what is logged (served requests AND refusals, per endpoint and hour; unattributable tokens per IP-hour) instead of "every pull".

### Fixed
- `stac/xpl/examples/drillhole-package.json` declared a `collection` without the `rel: collection` link STAC 1.1 requires; it failed the core item schema.

All notable changes to the geoDB Open Exploration Protocol are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/); the protocol
uses [semantic versioning](https://semver.org/) (pre-1.0: minor versions may make
breaking changes to field details, never to the auth model or lane structure).

## [0.1.0] — 2026-07-10

Initial public draft.

### Added
- **Records lane** — OpenAPI 3 (`spec/openapi.yaml`) over the read-only,
  project-scoped REST surface; chain-of-custody JSON Schemas (`schemas/`) for
  collar, survey, interval, assay, certificate, laboratory, and qc-sample.
- **Assets lane** — a per-project STAC 1.1 catalog and the `xpl:` exploration
  STAC extension (`stac/xpl/`), the first STAC extension for geophysics /
  drilling / mining. Worked examples for an airborne-magnetics survey item and a
  drillhole-package item.
- **Bulk** — GeoParquet / CSV export via the async export lane.
- **COG** — Cloud-Optimized GeoTIFF assets for grids, served as short-lived
  signed redirects.
- **Auth** — project-pinned, read-only, revocable, access-logged grants
  (`Authorization: Grant <token>`).

### Notes
- The protocol adopts existing standards (STAC 1.1, COG, GeoParquet, OpenAPI 3)
  and contributes only the missing exploration vocabulary.
- v2 backlog (documented, not built): STAC `/search` + stac-geoparquet, OGC
  API-Features conformance, Evo/OMF/geoh5/LAS export dialects, outbound webhooks.
