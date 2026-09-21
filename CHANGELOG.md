# Changelog

## [Unreleased]

### Added
- **[`AGENTS.md`](AGENTS.md) — the entry point an AI coding agent reads first.** What this is, how to get a token, **the six domain traps that produce silently wrong answers** (native-CRS `latitude`/`longitude`; per-project `cf_*` fields and where their types live; DAY-granular `modified_since` and its same-day over-inclusion; decimal-STRING assay values; EWKT `geometry`; the asset 302 that must not carry `Authorization`), the core profile, pagination and the sync loop as runnable code, every `reason_code` with its remedy, and the retry policy. The core-profile and reason-code tables are GENERATED (`scripts/emit_agents.py`) from the spec's `x-protocol-core` flags and from `errors.json`, so neither can fall behind what the server does.
- **[`errors.json`](errors.json) — the reason-code registry.** Every code the server can emit, with `http`, `meaning`, `remedy` and `retry` (`no` / `after` / `maybe`). Generated from the reference implementation by `manage.py export_reason_codes`; `scripts/regenerate.py --check --geodb <dir>` fails when the committed file differs from what the server registers. The spec's `Error` component links to it. **21 codes.**
- **[`examples/`](examples/) — four runnable integrations**, each under 60 lines and each against the public sandbox with no signup: `curl.sh` (curl + python3, no libraries), `python_client.py` (the `geodb-client` library, straight to DataFrames), `python_requests.py` (bare `requests` — the whole protocol in one file, to port), `typescript_fetch.ts` (global `fetch`, no dependencies). `examples/run_all.py` runs whichever the machine can run and **fails an example that stops reporting the CRS**, which is the one thing they all exist to demonstrate.
- **[`conformance/agent_smoke.py`](conformance/agent_smoke.py)** — extracts the quickstart OUT of `AGENTS.md` and executes it, so a quickstart that has rotted fails CI instead of failing somebody's first five minutes. `--offline` compiles it without credentials.
- **[`llms.txt`](llms.txt)** and [`sandbox.env.example`](sandbox.env.example) — a one-line index of every file in the repo, ranked below `AGENTS.md`, and the two environment variables every example reads.
- **The in-app Access Grants page now links `AGENTS.md` and the live API reference**, so the person minting a token can tell the recipient where to read (audit E10: issuance worked and was documented nowhere the issuer could see).
- Two `reason_code`s that reached the wire but were never registered, found by a source walk over every refusal site rather than a hand-written list: **`use_v2`** (a grant is refused on `/api/v1/`) and **`grant_auth_throttled`** (an address presenting too many unknown credentials). The server test now walks `ProtocolError(` / `_grant_deny(` call sites and the two lookup tables, so an unregistered code fails the build rather than reaching a vendor as an undocumented string.
- **`GET /api/v2/certificates/` and `/certificates/{id}/`** — the chain-of-custody anchor finally has a URL. `schemas/certificate.json` has shipped since 0.1.0 describing a record the API had no endpoint for; a certificate could only be glimpsed as a nested object on an assay row, never listed, paged or synced. Read-only, project-pinned, `modified_since` / `deleted_since` like every other list. Carries `status` (`preliminary` / `finalized` / `unverified`), `alt_certificate_numbers` for a lab job split across several certificate numbers, the methods reported, and `result_count`.
- **[`PROFILE.md`](PROFILE.md) — the core profile.** 47 operations a second implementer must serve, by `operationId`, with the reasoning for each family's membership; the 87 geoDB extensions listed by family. Generated from the spec.
- **Every operation carries `x-protocol-core: true` or `x-geodb-extension: true`** (exactly one). `x-geodb-extension` means "supported, ours, not in the contract" — not second-class.
- Seven operations the server already served but the committed spec omitted: vector layers (`vector-layers/`, `/{id}/`, `/{id}/features/`), vector features (`vector-features/`, `/{id}/`), `roads/style-spec/`, and project-file raster tiles (`project-files/{id}/tiles/{z}/{x}/{y}.png`). 147 -> 154 paths.
- The `scope` query parameter (`project` | `company`) declared on 24 list operations.
- `docs/` — the GitHub Pages tree that serves every `$id` at `https://spec.geodb.io/...`; `scripts/regenerate.py --check` / `--publish-only` and `scripts/validate.py` fail if a served copy is stale; `scripts/check_ids.py [--live]` proves every published URI resolves.
- `SECURITY.md`, issue templates (ambiguous / missing / wrong / write-semantics), a CI workflow, and a named weekly reader of the issue tracker in `CONTRIBUTING.md`.

### Changed
- **Breaking (spec): `NullEnum` removed.** Nullable choice fields now express null only as `nullable: true` on the property. Clients generated before this release did not compile (`class NullEnum(, Enum):`) — regenerate.
- **Breaking (wire): `GET /api/v2/drill-photos/` is now paginated**, returning `count`/`next`/`previous` like every other list. It previously returned only `results` plus the deletion-sync keys. (3 requests from 1 grant all-time.)
- **Breaking (wire): audit, tenancy and UI fields no longer appear in protocol responses** — `created_by`, `last_edited_by`, `mark_deleted`, `date_marked_deleted`, `deleted_at`, `company`, `natural_key`, `color`, `display_order`, and the `*_display` formatted twins. Deletions have always been reported through `deleted_ids`; stored values and their units are unchanged.
- Every operation now carries a summary and a consumer-facing description; tags reduced from 61 to 16 resource families. Six always-empty UI families left the grant surface (spec 154 → 132 paths); `/api/v1/` is refused for grants.
- Declared types now match the wire on every core resource (nullable computed values, nested objects, read-only choice fields that send `""`); a generated client validates a real row of all nine core lists.
- `POST /api/v2/exports/` documents its 202 (idempotent on re-POST) and both 429 causes (`throttled`, `export_concurrency`); the `reused` field is declared.
- **One normative artifact (ruling R4).** `spec/openapi.yaml` is NORMATIVE for the wire, stated in the README and in `CONTRIBUTING.md`. `schemas/*.json` and `PROFILE.md` are now GENERATED from it — the schemas from the core-profile Read components, the profile from the `x-protocol-core` flags — so they cannot contradict it again. `scripts/regenerate.py --check` and `scripts/validate.py` both fail if a committed copy has drifted.
- **Breaking (schemas): every schema in `schemas/` was replaced by its generated equivalent, and the set changed.** The hand-authored seven described a vocabulary the API never emitted (six of seven shared almost no property names with the wire): `collar.json` said `hole_id` / `date_drilled` where the wire sends `name` / `date_completed`; `assay.json` was one row per element where the wire sends one row per sample with a nested `elements[]`; `qc-sample.json` declared a `qc_type` string enum where the wire sends an integer reference. There are now **16** schemas, one per core record type, each carrying real `format` / `enum` / null branches, `additionalProperties: false`, and the `cf_*` custom-field pattern.
- **Breaking (schemas): `interval.json` is REMOVED.** It described a generic `interval_type` + `code` record that exists nowhere; downhole logging is eight separately typed families, and they are now eight schemas (`lithology-interval.json`, `alteration-interval.json`, `structure-interval.json`, `mineralization-interval.json`, `vein-interval.json`, `rqd-interval.json`, `spectral-interval.json`, `custom-interval.json`).
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
