# Changelog

## [0.2.0] — prepared 2026-10-03 (published at the maintainer's go)

Protocol **0.2.0** (`info.version`, the `X-GeoDB-Protocol-Version` header and
`grant-context.protocol_version` all say `0.2.0`). ⚠️ **Breaking for grant
callers** (ruling R-G); geoDB's first-party (Knox) clients are unchanged. The
exploration schemas publish at a new `$id`, `https://spec.geodb.io/exploration/v0.2.0/…`;
the `v0.1.0` copies stay served as they were.

### ⚠️ Changed — scope: no current project, one company per read (R-A, R-B, R-F)
- **A read names its project.** geoDB keeps no current project between calls. A
  project-level read (everything carrying a project) that names none while the
  credential reads several is refused **`400 project_required`** with `choices`
  (the readable projects, grouped by company). A credential that reads one
  project needs to name nothing. `company=<id>` alone narrows the question, or
  answers when that company has one readable project.
- **Company-level tables name their company:** laboratories, methods, standards,
  QC types answer `company=<id>` (or a `project`'s company, or the credential's
  only company); else **`400 company_required`** (new code).
- **`scope=company` reads ONE company** (`company=<id>` when the credential reads
  several companies, else `company_required`). No request returns rows of two
  companies.
- **Every grant row says where it is:** top-level rows carry `project_id`
  (company-level rows `company_id`). A record by id is found anywhere in the
  readable set.
- **`grant-context/`** lists `companies` → `projects` (and the same projects flat
  in `projects`, each with its company and its per-family set counts in `sets`);
  `default_project`, `project` and `company` are set only when the credential
  reads exactly one; `choosing_a_project` states the rule. The connector's
  consent screen no longer offers a "default project".
- `scope` (and `company`) are declared on every project-level list (the spec
  used to declare `scope` only on some, with a description that said "the
  active company").
- This supersedes the "default project" rule described under *connector scope
  fixes* below.

### ⚠️ Changed — lean shapes (R-D)
- **An assay names its relations by id:** `certificate_id`, `laboratory_id` on the
  assay row; `method_id` (and `certificate_id`) on each value. The nested objects
  come back only with **`expand=certificate,method,laboratory`**; an `expand` a
  read does not offer is refused `invalid_parameter`. A sample's nested assay
  record follows the same shape.
- **`detection_limit` / `upper_limit` are JSON numbers** on every grant route.
- **Point LIST rows drop the per-row `coordinate_system_metadata`** (collar lists
  also `images` / `documents`); a record by id keeps them. The block's one home is
  new **`GET /api/v2/projects/{id}/coordinate-system/`**.
- New **`GET /api/v2/assay-results/`**: the flat, dataframe-ready table — one row
  per sample × element × method (sample, hole + depths, value as a decimal
  string, units, numeric limits, flags, method / certificate / laboratory ids) —
  exactly the assays `assays/` answers for the same request.

### ⚠️ Changed — sets first (R-E)
- **`set=<id|name|all>`** on every interval and sample list (the per-model set
  fields stay as aliases). An interval list over a project holding more than one
  set of that kind, naming none, is refused **`400 set_choice_required`** (new
  code) with `sets`: each set's id, name, description, rows, holes, depth range,
  default flag, created + the creator's role (never an email), source,
  `writable_by_this_key`. `set=all` reads every set; every grant interval row
  carries **`set_id` / `set_name`** (a row with no stored set reads as its
  project's default set). A record by id is never asked.
- `writable_by_this_key` is false on a key that cannot write.

### ⚠️ Changed — exports
- `POST /api/v2/exports/` takes the list's parameters in the query or the body:
  `project`, `company`, `scope=company` (only when it answers one project — an
  export is one project's table; several are refused `invalid_parameter` with the
  `choices`), and `set` (the list's set rule; a table whose export ships only the
  project's export set refuses `set=all` / another set). Never an empty file for a
  parameter it cannot honour. The connector's `export_link` takes the same
  `filters` (`project`, `company`, `scope`, `set`).

### Changed — client/server version pairing
- The install line geoDB serves (the connector's `session_key` result, the
  teaching) is pinned to the protocol's minor: `pip install "geodb-client>=0.2,<0.3"`,
  derived from the protocol version so it moves with it. `geodb-client` 0.2.0
  sends `X-GeoDB-Protocol-Version` and raises `ProtocolVersionMismatch` (naming
  the install line) when the server speaks another major.minor.

### Changed — help text and labels
- `qaqc-verdicts/` accepts **`offset`** (and answers `next_offset`); its
  per-certificate pass rates honour `element`.
- The `-1.0000` below-detection sentinel is compared numerically; `xyz_*` are
  described as project-local-grid metres (not a CRS, not WGS84; the `_wgs84`
  twins are EPSG:4326). `POST exports/` is documented as the one read-POST.

### Added — the write chapter (R-I, R22)
- **The write half is published:** `POST /api/v2/records/` (create · upsert ·
  update · retract · restore · make_default_set · qaqc_verdict · qc_reconnect ·
  undo), its describe contract, the write log, and the feedback lane. The write
  profile (`conformance/geodb_conformance/contract/write-profile.json`) is
  `published`, and its codes are in `errors.json`. AGENTS.md "Managing data" and
  the Skill's Writing section teach it, including: every write names its project
  and set; dry run → write → report the Undo handle; corrections are updates;
  moving an interval's depths is retract + create.
- ⚠️ **While API writing opens, geoDB's servers accept writes only from geoDB
  staff connections**: any other key is refused **`403 writes_staff_only`** (new
  code), whatever write access it was given. A compliance report is started in
  the web app (**`compliance_create_staff_only`**, new). A row the server wrote
  but stored differently is reported written with the warning
  **`stored_differently`** (new) and `conflicts` (`stored` vs `sent`).

### Earlier unreleased changes, folded into 0.2.0

### Changed — protocol v0.2, phase 1: one seam per concern (geoDB `feature/protocol-v0-2`)
- **No read answers differently.** Scope, exports, the response projection, the interval set filter and the teaching each moved to ONE seam in the reference implementation, pinned response-for-response against the previous server. The only wire change is additive and grant-only:
- **Every refusal a grant meets carries a `reason_code` and a `remedy`.** The app endpoints' hand-written 4xx bodies (`{"error": …}`) gain the two keys for a grant caller — the status's registered code (`validation_error`, `authentication_failed`, `permission_denied`, `not_found`, `method_not_allowed`, `conflict`, `throttled`) unless the endpoint names a more specific one. First-party (Knox) bodies are unchanged. New reason code **`conflict`** (409). 27 codes.

### Changed — connector scope fixes (geoDB `feature/connector-scope-fixes`)
- **One rule for which projects a read answers.** A credential that can read several projects (a connected AI over the projects a person ticked, or a regional key) reads its DEFAULT project unless the call names another: `project=<id>` (or its exact name) selects any project it can read, on every list and every pin-scoped detail read; `scope=company` reads all of them. Lists that used to answer every readable project without being asked (certificates, assays, the `*-sets` lists, photos, the vocabularies) now answer the default project — ⚠️ a regional key that pulled one of those without a project parameter now gets its default project; add `scope=company` for all. A pin-scoped list that refused `project=<another readable project>` (400) now answers it.
- ⚠️ **A project parameter on a single-record read is judged too.** `project` / `project_id` on a `…/{id}/` read now resolves within the projects the credential can read like it does on a list: an unreadable or unknown project is refused `400 invalid_parameter` (it used to be ignored on a record read and answer the default project's record).
- **The "use an operation…" remedies in `errors.json` describe a server whose operation map is served** (`GET /api/v2/`, i.e. the connector is on — as on api.geodb.io). A server running without the map answers those refusals (`permission_denied`, `grant_surface_forbidden`, `grant_no_read_capability`, `use_v2`) with the previous wording, pointing at this repository's spec; match on `reason_code`, never on `remedy` text.
- **`GET /api/v2/grant-context/` always lists `projects`** (`[{id, name, code, company {id, name}}]`), names **`default_project`** and says how to choose (**`choosing_a_project`**). Additive: no key removed or retyped (`projects` items keep `id` + `name`). The spec intro and the grant-context description no longer say a grant is pinned to one project.
- **Refusal remedies name the operation map.** `grant_surface_forbidden`, `grant_no_read_capability`, `permission_denied` and `use_v2` point at `GET /api/v2/` (the operation map; on a connector, `api_read` path `''`) and `grant-context/`, not the GitHub repository.
- New reason codes: **`connector_staff_only`** (401: AI connections are open to geoDB staff accounts only for now) and **`overlapping_samples`** is now registered for every caller (the composite read answers it instead of a 500, naming the sampling passes in `sets`). 26 codes.
- Summaries: every STAC operation has its own summary (was "Get one of the STAC catalog" ×4). `DrillPadRead.elevation` (and the pad's local-grid shape) is a nullable number, not a string. The land-holdings list/retrieve 200 now says its schema is the OUTLINE shape and that a project shared at `detailed` adds the claim-maintenance fields named in the operation description (the published components stay outline-only by design).
- **Reads never refuse stored data; `data_warnings` marks a bad row.** Whatever is stored is returned (an upside-down interval, a dip past 90°, coordinates with no CRS, an invalid outline — 200, every row). A row the server recognises as wrong carries the optional `data_warnings: [{code, field, detail}]` (new `DataWarning` component; codes `interval_upside_down`, `negative_value`, `depth_past_hole`, `dip_out_of_range`, `azimuth_out_of_range`, `missing_epsg`, `coordinate_outside_crs`, `invalid_geometry`), declared on the 23 components that carry a depth, dip, azimuth, coordinate or geometry; absent when the row has none. Additive: optional in every schema.
- Teaching (Skill, AGENTS.md domain region): the coordinates trap names the DERIVED `crs_*` copy (project CRS, `crs_epsg`) beside the native `latitude`/`longitude` (= `source_coordinate`); the Sets summary's write etiquette is taught only beside the write rows (writes are dark); the water topic says `time_collected` reads back as `HH:MM:SS`.

### Added
- **A read-side model sweep: every list filter the server honours is declared, and a filter value it cannot apply is refused `invalid_parameter`, never answered with an empty list.** Set filters on the downhole families (`drill_lithology_set`, `drill_alteration_set`, `drill_mineralization_set`, `drill_vein_set`, `drill_rqd_set`, `drill_spectral_set`, `custom_interval_set`, `drill_sample_set`: by id or exact name, case-insensitive; an unknown set is refused `invalid_parameter`, never an empty list); QC samples `category` (`sample_type` is its legacy twin), `qc_type` (id or name) and `lab_status`; point samples `status`; drill and point samples `assay_config_id` and the legacy `merge_assays`; water samples `site_id` (the site's id or its name), `sample_type`, `start_date` / `end_date`; water sites `site_type` and `status`. Structures, field notes and land holdings gain the sync parameters (`modified_since`, `deleted_since`, `compact`, `skip_count`) and the deletion-sync keys (`deleted_ids`, `deleted_since_applied`, `sync_timestamp`, `withheld`) on their list envelopes.
- New read fields: `dry_weight` / `wet_weight` on drill samples (grams; the two inputs of a submerged specific gravity, null when not measured); `formation` on lithology intervals (`{id, name, description}` or null); `lithology`, `alteration`, `alteration_grade` (ISRM A1–A5), `fracture_count` and `run_length` on RQD intervals; `source_geometry` (`{wkt, epsg}`, the original line or polygon exactly as sent, never reprojected) on roads; the nested assay on a sample carries `excluded`, `excluded_reason` and `excluded_by_certificate` like a top-level assay row. These are new REQUIRED properties in `drill-sample.json`, `lithology-interval.json` and `rqd-interval.json` (each nullable), so a server must send the key even when it has no value.
- **Catalog references resolved by `*_display`:** a method's `digestion_display` / `finish_display` / `type_display` and a certified value's `method_display` each carry `{id, code, name}`, the only resolution of a catalog id the protocol has no endpoint for. A certified value's `method` is an analytical-method id, a different table from an assay value's laboratory `method`; the description now says so. (These are kept by name; the formatted `*_display` twins of stored values stay out of the projection.)
- Reason code **`land_holdings_not_shared`** (403): the project owner has not shared land holdings with API keys on this project. 24 codes.
- Domain-guide topic **`water`** (AGENTS.md domain-knowledge region, `skills/geodb/references/water.md`): water non-detects, the stored units of each field measurement, and why `above_det_limit` on a water result means detected, the opposite of its meaning on an assay value.
- **Unread list parameters are refused, not ignored.** A list query parameter the list does not read (`page_size`, a misspelt or guessed filter) now answers `400 invalid_parameter` naming the parameters that list honours; AGENTS.md's paging trap and the Skill say so. Assays declare **`certificate`** (id or exact name, case-insensitive; a name shared by several certificates you can read matches each — send **`certificate_id`** to pick one) and `certificate_id`; the drill-hole filter's text now says a shared hole name matches each project's hole. No reason code added (`invalid_parameter` already existed). The assay `above_det_limit` flag on the public demo data now means over the method's upper range, matching §3.4.
- **The write profile + `geodb-conformance write` (dark — geoDB's production servers do not serve the write half yet).** The write half's contract as its own versioned document, `conformance/geodb_conformance/contract/write-profile.json` (`profile_version` 0.1.0, `status: dark`), generated from the reference implementation by `manage.py export_write_profile` and checked by `scripts/regenerate.py --check` and `scripts/validate.py` (its reason codes partition the registry with `errors.json`). It lives only inside the conformance package until the write half ships; it is not in `spec/`, `docs/`, `PROFILE.md` or `AGENTS.md`. `python -m geodb_conformance write --base-url … --token …` runs 20 named assertions against a key that may write, then undoes every write it made; `examples/writes/` — one runnable example per intent (`create`, `upsert`, `update`, `retract`, `restore`, `undo`, `make_default_set`), bare `requests`, each undoing what it wrote; not run by CI. A throttled key SKIPS the run (with the wait) instead of failing the server. `selftest` runs a write break matrix beside the read one (write 22/22 breakages over 20 assertions + read 40/40).
- Set provenance gains the value **`external`** (`source` on interval/sample sets): a set written through a key — a connected AI, an agent or a vendor app. Additive.
- **[`skills/geodb/`](skills/geodb/) — a Claude Skill** (`SKILL.md` + references: the core profile, coordinates, assay values, sets, QAQC, drilling, geochem, reports, claims), and an AGENTS.md **domain-knowledge region**, both GENERATED from the same source as geoDB's connector instructions (`manage.py export_protocol_guide`; `--check` fails when the committed files drift). Sections that describe dark (unreleased) surfaces are omitted until those surfaces ship.
- **AGENTS.md §3.7–3.8: two new traps** — withheld rows (rejected or superseded certificates and soft-deleted rows are left out, and every list's `withheld` object counts them on the first page; certificates carry `qaqc_status` / `superseded_by` / `supersedes`) and below-detection values (`-1.0000` with `below_detection: true` and the value's `detection_limit`). The spec gains these fields on assays, QC samples and certificates (`excluded`, `excluded_reason`, `excluded_by_certificate`, `certificate_id`, `below_detection`, `source_type`, the review fields) and declares every list filter the server honours (`project`, `project_id`, `compact`, `skip_count`, `deleted_since`, …), which it previously accepted undeclared; an unknown project is refused `invalid_parameter`, never an empty list.
- **The interval set on lithology, RQD and spectral reads: `drill_lithology_set`, `drill_rqd_set`, `drill_spectral_set`** — each `null` or `{id, name, description}`, on list and detail. The server has sent them since geoDB moved to DRF 3.17.2 (2026-10-01); the published schemas (`additionalProperties: false`) did not declare them, so a strict validator, and `geodb-conformance`, rejected live rows. Additive: nothing removed or reshaped. Regenerated from the reference implementation (`spec/openapi.yaml` +63 lines; the three interval schemas, their `docs/` copies and the conformance contract copies follow).
- **[`AGENTS.md`](AGENTS.md) — the entry point an AI coding agent reads first.** What this is, how to get a token, **the six domain traps that produce silently wrong answers** (native-CRS `latitude`/`longitude`; per-project `cf_*` fields and where their types live; DAY-granular `modified_since` and its same-day over-inclusion; decimal-STRING assay values; EWKT `geometry`; the asset 302 that must not carry `Authorization`), the core profile, pagination and the sync loop as runnable code, every `reason_code` with its remedy, and the retry policy. The core-profile and reason-code tables are GENERATED (`scripts/emit_agents.py`) from the spec's `x-protocol-core` flags and from `errors.json`, so neither can fall behind what the server does.
- **[`errors.json`](errors.json) — the reason-code registry.** Every code the server can emit, with `http`, `meaning`, `remedy` and `retry` (`no` / `after` / `maybe`). Generated from the reference implementation by `manage.py export_reason_codes`; `scripts/regenerate.py --check --geodb <dir>` fails when the committed file differs from what the server registers. The spec's `Error` component links to it. **21 codes.**
- **[`examples/`](examples/) — four runnable integrations**, each under 60 lines and each against the public sandbox with no signup: `curl.sh` (curl + python3, no libraries), `python_client.py` (the `geodb-client` library, straight to DataFrames), `python_requests.py` (bare `requests` — the whole protocol in one file, to port), `typescript_fetch.ts` (global `fetch`, no dependencies). `examples/run_all.py` runs whichever the machine can run and **fails an example that stops reporting the CRS**, which is the one thing they all exist to demonstrate.
- **[`conformance/`](conformance/) — `geodb-conformance`, the runner you point at your OWN server.** `python -m geodb_conformance read --base-url URL --token TOKEN [--profile core|full] [--junit FILE] [--markdown FILE]`, exit 0/1. **43 named assertions**, each carrying a one-line statement of the contract clause it establishes, so the markdown report reads as the contract with a verdict beside each clause: auth and the refusal codes, the one envelope and its deletion-sync keys, `limit`/`offset` paging, `cf_*`-only extra keys, **every row of every core list validated against the published JSON Schema**, `modified_since` / `deleted_since` semantics (including that an unparseable date is refused, not ignored), the coordinate contract, STAC 1.1 landing + conformance link + asset redirect, the export round trip, every 4xx carrying a registered `reason_code`, and `X-GeoDB-Protocol-Version`. **The suite ships its own copy of the spec, the schemas and the error register and checks you against those** — a runner that asked the server under test to describe itself would pass against any self-consistent server. The coordinate check reprojects your native coordinate with `pyproj` and compares against the WGS84 you derived, which is the only way to catch a server that silently reprojected into `latitude`/`longitude`.
- **Every conformance assertion has been proven to fail.** `python -m geodb_conformance selftest` (= `python conformance/run.py --offline`, what CI runs, no credentials and no network) runs each assertion against `conformance/mock_server.py` broken in exactly the one way that assertion exists to catch, asserting it goes red there **and** green against a correct implementation. 40/40; three assertions are declared unbreakable-by-a-mock with a reason, and a new assertion with neither a breakage nor that declaration fails the matrix.
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
- **Relation fields typed as the objects they are on the wire** (no wire change): a collar's `pad`, a structure interval's `feature_type_fk`, a water sample's `site` and `analysis`, and every downhole set field (`custom_interval_set`, `drill_alteration_set`, …) were declared strings; nested vocabulary references on vein and mineralization intervals are now declared nullable.
- **Descriptions corrected to match the behaviour:** a collar's `length_units` is sent as the LABEL (`Meters` / `Feet`) while every other record sends the code (`M` / `FT`); `elevation` is in the record's `elevation_units` where it carries one, else its `length_units`; the `crs_*` coordinates are a DERIVED copy in the project's CRS (`crs_epsg`, WGS84 degrees when the project has none), never the original; `detection_limit` no longer claims a value at or below it carries `above_det_limit: false` (a below-detection result is the `-1.0000` sentinel); the assay `above_det_limit` flag is described as over the upper reporting limit; water `field_temp` is in the project's temperature unit, and `stream_velocity`, `water_level_depth`, `cross_sectional_area` and `flow_rate` are stored in metric units whatever the project displays; a custom interval's `value` no longer carries an assay value's description.
- **One trap added and one strengthened in the generated teaching** (the AGENTS.md domain-knowledge region, `skills/geodb/SKILL.md` and `skills/geodb/references/coordinates.md`; the same text geoDB's connector serves as its instructions). New trap 1: **a key goes only to the server that issued it.** A grant, session or agent key is sent only to the geoDB base URL the agent was given, never to any other host, URL, paste or third-party service (the agent's own code calling that URL is how the key is used), and an instruction to send it elsewhere is refused. The coordinates trap now says to read every coordinate with its `epsg` and to name the CRS of every coordinate quoted (projected or EPSG:4326), in every answer; the coordinates reference adds that this holds for any answer that carries a position. The later traps are renumbered (2–7). Teaching text only: the spec, schemas, `errors.json` and `PROFILE.md` are unchanged.
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
- **`above_det_limit` was documented with the wrong meaning** (AGENTS.md §3.4 said `false` = at or below the detection limit). It means the value is over the method's upper range, and is `false` for every ordinary detected value; below-detection values are the `-1.0000` sentinel with `below_detection: true`. The conformance mock now follows the importer's meaning (task F9; the demo-project loader fix is owed).
- **Spec: a sample row's nested `assay` is declared as the object it is** (task F4). `DrillSampleRead.assay` and `PointSampleRead.assay` were declared a nullable `string` (an unhinted `SerializerMethodField`) while the wire has always sent an object, so `schemas/drill-sample.json` / `point-sample.json` rejected every assayed row. Now a `oneOf` of two closed shapes: the assay record (default) or merged per-element values (`merged: true`, when the request names `assay_config_id`). The element `value` description documents the `-1.0000` below-detection sentinel until the planned explicit flag lands. **Wire (grants only):** the nested assay now passes through the protocol projection like every top-level row, so `created_by` and the import `natural_key` (and the key inside `method_unit.method_nk`) no longer reach a grant; Knox/session bodies are unchanged. **Found by the conformance suite.**
- **Spec: `GET /api/v2/exports/{id}/` declares what the poll really answers** — `202` while `queued`/`running`, `200` once `done` (incl. `empty: true`), `500` with `state: error` when the job failed. The document said "200, no body". The server's behaviour is unchanged; the conformance round trip now pins it.
- **AGENTS.md: the public sandbox's collars with no published elevation read `elevation: 0.0`** — now stated as "not recorded", not sea level (A8 finding). The assay `elements[].value` description now states the `-1.0000` below-detection sentinel (the explicit flag is planned).
- **Conformance: `envelope.only_cf_extra_keys` honours the schema's own `patternProperties`.** A metal-equivalent key (`AuEq ppm`, whose NAME is data) is declared by pattern in the drill/point/QC sample schemas; the check accepted only `cf_*` and failed a conforming server. `schema.every_row_validates` already accepted it.
- **Breaking (spec): `schemas/assay.json` rejected every real assay row, on the highest-traffic endpoint of the whole surface.** Five properties were declared `string` and are objects or nullable numbers on the wire: `certificate`, `elements[].certificate`, `elements[].method` (objects), `elements[].detection_limit`, `elements[].upper_limit` (nullable numbers). Cause: unhinted `SerializerMethodField`s, which drf-spectacular defaults to a non-nullable `string` — the same defect fixed for `project` in the previous task and not swept beyond it. The drift test could not see them because its fixture's assay had no certificate and no elements, so every one serialised to `null`, and a null is only checked for nullability. The fixture now carries both, and a new assertion sweeps types INSIDE nested arrays of objects — where an assay keeps all of its values. **Found by the conformance suite validating real rows against the published schemas.**
- **Breaking (wire): `POST /api/v2/exports/` refusals now carry the error envelope.** An unsupported model or format answered `{"detail": "...", "allowed_models": [...]}` with no `reason_code`, while the spec declared `Error` for that 400 — so the one refusal a client is most likely to hit on the export lane was the one it could not branch on. Five refusal sites now raise the shared error type (`validation_error`, `invalid_parameter`, `permission_denied`, `grant_room_pinned_refused`, `not_found`). `allowed_models` / `allowed_formats` are kept, additively and inside `offending.allowed`.
- `stac/xpl/examples/drillhole-package.json` declared a `collection` without the `rel: collection` link STAC 1.1 requires; it failed the core item schema.

### Known gaps
- **22 list operations declare the deletion-sync keys (`deleted_ids`, `deleted_since_applied`, `sync_timestamp`) and do not send them**, including three core-profile ones: `/api/v2/assays/`, `/api/v2/qc-samples/`, `/api/v2/laboratories/`. A mirror built from the document keeps deleted rows forever and is never told. Found by the conformance suite; pinned by a server-side test carrying a ledger that only ever shrinks. Closing it is a per-family wire change and is scoped to the next task, not this release.

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
