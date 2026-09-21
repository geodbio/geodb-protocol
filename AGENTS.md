# AGENTS.md — read this first

You are integrating with a geoDB project over the geoDB Open Exploration
Protocol. This file is written for you: it is the shortest path from a token to
correct data, and it names the handful of things about this domain that will
silently give you wrong answers if nobody tells you. Read it before the
OpenAPI document — then trust
[`spec/openapi.yaml`](spec/openapi.yaml), which is normative for the wire.

**Everything here is verifiable by running it.** If a statement in this file
and the server disagree, the server is right and the file is a bug: please
[open an issue](CONTRIBUTING.md).

---

## 1. What this is

A geoDB project holds a mineral-exploration dataset — drill holes and what was
logged down them, the samples cut from them, the assay results with the
laboratory chain of custody behind each value, and large binary assets like
grids and imagery. This protocol is a read-only, project-scoped, authenticated
REST + STAC surface over that data, described by an OpenAPI 3 document that is
generated from the running server rather than written beside it.

A project owner issues you a **grant**: one token, pinned to exactly one
project, read-only, revocable at any moment, and logged — the owner sees every
call you make. You cannot reach another project with it, and you cannot write.

Two lanes: **records** (relational rows, JSON, paged) and **assets** (large
files as STAC 1.1 items with footprints and checksums, fetched through
short-lived signed redirects).

---

## 2. Get a token

**If you have a project owner:** they mint one in the geoDB web app under
**Project Settings → API Access Grants → New grant**. The token is shown once,
at creation, and never again. They hand it to you; you keep it out of source
control.

**If you just want to try it:** use the public sandbox grant. It is read-only,
pinned to one open-data demonstration project, throttled, and rotated
periodically. No signup, no account.

```bash
export GEODB_TOKEN=<SANDBOX_TOKEN>
export GEODB_BASE_URL=https://api.geodb.io      # the default; override for a self-hosted server
```

See [`sandbox.env.example`](sandbox.env.example). Every example in
[`examples/`](examples/) runs as-is against it.

**Every request carries the token in one header:**

```
Authorization: Grant <token>
```

Not `Bearer`. A 401 from this API answers `WWW-Authenticate: Grant`.

**The cheapest first call**, and the one that tells you what you are holding:

```bash
curl -s -H "Authorization: Grant $GEODB_TOKEN" "$GEODB_BASE_URL/api/v2/grant-context/"
```

It returns the project the grant is pinned to, whether it is read-only, its
throttle rate, its expiry, and the protocol version. Call it before assuming
anything.

---

## 3. Six traps

These are the things that produce confidently wrong answers. They are not edge
cases; the first one will affect nearly every project you touch.

### 3.1 `latitude` and `longitude` are NOT degrees

On every record that has a location, `latitude` and `longitude` hold the
**original coordinate exactly as it was imported, in the coordinate reference
system named by the sibling `epsg` field.** For a projected CRS — UTM, State
Plane, anything that is not 4326 — that means:

```
longitude  =  EASTING        latitude  =  NORTHING
```

They are true WGS84 degrees **only when `epsg == 4326`.**

This is deliberate. The customer's numbers are kept byte-for-byte as they
supplied them, beside the CRS they were supplied in, so that nothing is ever
lossily reprojected on write. The field names are historical and are kept for
continuity with existing clients. A conforming server does the same; one that
silently reprojects into those two fields is losing its customer's data.

**What to read instead:**

| You want | Read |
|---|---|
| The original coordinate, unambiguously named | `source_coordinate` → `{x, y, epsg}` |
| WGS84, as a parsed object | `geometry_geojson` → GeoJSON `Point`, `[lon, lat, elev]` |
| WGS84, as a string | `geometry` → EWKT, `SRID=4326;POINT Z (lon lat elev)` |
| What units the originals are in | `xy_units` → `degrees` \| `meters` \| `feet` \| `us-feet` |

A real row from a project imported in UTM zone 15N:

```json
{
  "name": "SB-26-001",
  "latitude": 4189978.52,
  "longitude": 712671.53,
  "epsg": 26915,
  "xy_units": "meters",
  "source_coordinate": {"x": 712671.53, "y": 4189978.52, "epsg": 26915},
  "geometry": "SRID=4326;POINT Z (-90.5833663 37.8324627 332.137)",
  "geometry_geojson": {"type": "Point", "coordinates": [-90.5833663, 37.8324627, 332.137]}
}
```

If you plotted `latitude`/`longitude` on a map here you would place the hole
somewhere off the coast of Antarctica, and every guard would pass.

**Rule:** decide by `epsg`, never by the field name. If `xy_units` is anything
other than `degrees`, the scalars are easting/northing.

**The same rule applies to the other two coordinate blocks on the record, and
they are the reason the rule is worth stating twice.** Beside the fields above,
a point record also carries:

| Block | What it is |
|---|---|
| `crs_easting` / `crs_northing` / `crs_epsg` / `crs_xy_units` | The record **reprojected into the project's own working CRS** — whatever the project is configured to work in, which is *not* necessarily the CRS the record was imported in. |
| `proj4_easting` / `proj4_northing` / `proj4_string` | The record on the project's **local grid**, when one is defined. Null when it is not. |

⚠️ **`crs_easting` and `crs_northing` are named for the usual case, not for
every case.** They mean "X" and "Y" in `crs_epsg`. When a project's working CRS
is itself geographic — 4326, say — then `crs_epsg` reads `4326`,
`crs_xy_units` reads `degrees`, and the field called `crs_easting` contains a
**longitude**. That is not a bug and the values are not swapped; it is the same
naming compromise as `latitude`/`longitude`, one level along. A row can
therefore advertise `epsg: 26915` and `crs_epsg: 4326` at once, and both are
true: the first is what the customer imported, the second is what the project
works in.

**For an integration, prefer `epsg` + `source_coordinate` (the original, always
present) and `geometry_geojson` (WGS84, always present).** Read the `crs_*`
block only when you specifically want the customer's working grid, and read
`crs_xy_units` before you interpret it. Neither `crs_*` nor `proj4_*` is in the
core profile.

### 3.2 `cf_*` keys are per-project custom fields — discover them

Any record may carry extra keys matching `cf_[a-z0-9_]+`. These are
user-defined fields; they vary by project **and** by record type, and no fixed
schema will ever list them. The spec declares them as a pattern, not as named
properties, so a generated client will not invent them for you.

Their names, types and whether they are required live at:

```
GET /api/v2/model-schemas/          # every record type this project exposes
GET /api/v2/model-schemas/{id}/     # one type, with its full field list
```

⚠️ **`{id}` is the `model_type` value, not the URL path segment.**
`/api/v2/model-schemas/DrillCollar/` works; `/api/v2/model-schemas/drill-collars/`
is a 404. Each entry in the list response carries both — `model_type` is the
key you look a type up by, `api_endpoint` is where its rows live. Join on those
two fields rather than transforming one name into the other.

Read this before assuming a fixed schema, and do not drop unknown keys.

### 3.3 `modified_since` is DAY-granular — expect same-day repeats

Incremental sync works like this:

```
GET /api/v2/drill-collars/?modified_since=2026-03-14
```

The server answers rows changed on or after that date, plus `deleted_ids` for
rows soft-deleted since, plus a `sync_timestamp` to use as the next cursor.

**The comparison is by DAY, not by instant.** Records carry a modification
*date*, so passing a full ISO timestamp does not narrow within the day: a pull
at 14:00 with `modified_since` set to this morning's cursor returns everything
touched today, including rows you already have. That is over-inclusion, never
under-inclusion — you will not miss a change, but you must **upsert by `id`**
rather than append. A loop that appends will duplicate rows on every same-day
poll.

An unparseable value is **refused with 400 `invalid_parameter`**, not silently
ignored. `?modified_since=yesterday` is an error, not a full table scan.

### 3.4 Assay values are decimal STRINGS

```json
{"element": "Au", "value": "5.5575", "units": "ppm", "detection_limit": 0.005}
```

`value` is a JSON string on purpose: it preserves exactly what the laboratory
reported, and parsing it as a float will silently round it. **Parse it with a
decimal type** (`decimal.Decimal`, `BigDecimal`, `pandas` with `dtype=object`
or an explicit conversion). Do not let a JSON library coerce it.

`units` are **per value**, not per sample and not per element — one sample can
carry results from two laboratories at different units. Always read `units`
beside the value it belongs to. Assays nest their results under `elements`:

```
assay.elements[] = {element, value, units, detection_limit, upper_limit,
                    above_det_limit, method, certificate}
```

`above_det_limit: false` means the value is at or below the detection limit;
treat it as a censored observation, not as a measurement.

### 3.5 `geometry` is EWKT, not GeoJSON

The `geometry` field is a **string** in EWKT form:

```
SRID=4326;POINT Z (-90.5833663 37.8324627 332.137)
```

Longitude first, then latitude, then elevation in metres. It is always EPSG
4326 whatever `epsg` says, because it is the derived value. A `POINT` without
`Z` means no elevation was recorded.

If you want a parsed object, read `geometry_geojson` — the same location as an
RFC 7946 GeoJSON `Point`. `geometry` stays a string because existing clients
parse it that way; the GeoJSON is a separate, additive key.

### 3.6 Asset downloads are 302 redirects — do NOT forward `Authorization`

STAC asset endpoints and finished exports answer with a **302 to a short-lived
signed URL** (about five minutes). That URL authenticates itself. You must:

1. request the asset endpoint **with** your grant header, and **not** follow
   the redirect automatically;
2. read `Location`;
3. fetch it **without any `Authorization` header**.

Most HTTP clients auto-follow redirects and re-send headers, which will fail:
the signed URL is on different infrastructure, and the grant gate rejects a
grant token presented anywhere outside the API surface. Set
`allow_redirects=False` (requests), `redirect: "manual"` (fetch), or `-L`'s
absence (curl) and do the second hop yourself.

```python
r = session.get(asset_url, headers=auth, allow_redirects=False)
blob = session.get(r.headers["Location"])          # NO auth header here
```

The `geodb-client` library does this for you.

### Bonus trap: paging is `limit`/`offset`

Lists page with **`limit`** (default 100, maximum 500) and **`offset`**. A
`page_size` parameter is **silently ignored** — you will get the default page
and may conclude the project is small. Follow the `next` URL instead of
building your own, and see §5.

---

## 4. The core profile

<!-- BEGIN:core-profile (generated by scripts/emit_agents.py — do not edit) -->

**47 operations.** Everything else the server answers is a geoDB extension: real and supported, but not part of the contract another implementation is asked to serve. Which is which is machine-readable — each operation in the spec carries `x-protocol-core: true` or `x-geodb-extension: true`.

**Grant**

| operationId | | Purpose |
|---|---|---|
| `grant_context_retrieve` | `GET /api/v2/grant-context/` | Get what this credential can see |

**Discovery**

| operationId | | Purpose |
|---|---|---|
| `model_schemas_retrieve` | `GET /api/v2/model-schemas/` | Get field definitions |
| `model_schemas_retrieve_2` | `GET /api/v2/model-schemas/{id}/` | Get one of the field definitions |

**Drill Holes**

| operationId | | Purpose |
|---|---|---|
| `drill_collars_list` | `GET /api/v2/drill-collars/` | List drill holes |
| `drill_collars_retrieve` | `GET /api/v2/drill-collars/{id}/` | Get one of the drill holes |
| `drill_collars_trace_retrieve` | `GET /api/v2/drill-collars/{id}/trace/` | Get a hole's computed trace |
| `drill_collars_xyz_at_depth_retrieve` | `GET /api/v2/drill-collars/{id}/xyz_at_depth/` | Position at a depth down a hole |
| `drill_surveys_list` | `GET /api/v2/drill-surveys/` | List downhole survey stations |
| `drill_surveys_retrieve` | `GET /api/v2/drill-surveys/{id}/` | Get one of the downhole survey stations |

**Drill Intervals**

| operationId | | Purpose |
|---|---|---|
| `drill_alterations_list` | `GET /api/v2/drill-alterations/` | List logged alteration intervals |
| `drill_alterations_retrieve` | `GET /api/v2/drill-alterations/{id}/` | Get one of the logged alteration intervals |
| `drill_custom_intervals_list` | `GET /api/v2/drill-custom-intervals/` | List logged custom intervals |
| `drill_custom_intervals_retrieve` | `GET /api/v2/drill-custom-intervals/{id}/` | Get one of the logged custom intervals |
| `drill_lithologies_list` | `GET /api/v2/drill-lithologies/` | List logged lithology intervals |
| `drill_lithologies_retrieve` | `GET /api/v2/drill-lithologies/{id}/` | Get one of the logged lithology intervals |
| `drill_mineralizations_list` | `GET /api/v2/drill-mineralizations/` | List logged mineralization intervals |
| `drill_mineralizations_retrieve` | `GET /api/v2/drill-mineralizations/{id}/` | Get one of the logged mineralization intervals |
| `drill_rqds_list` | `GET /api/v2/drill-rqds/` | List logged RQD and geotechnical intervals |
| `drill_rqds_retrieve` | `GET /api/v2/drill-rqds/{id}/` | Get one of the logged RQD and geotechnical intervals |
| `drill_spectral_intervals_list` | `GET /api/v2/drill-spectral-intervals/` | List logged spectral intervals |
| `drill_spectral_intervals_retrieve` | `GET /api/v2/drill-spectral-intervals/{id}/` | Get one of the logged spectral intervals |
| `drill_structures_list` | `GET /api/v2/drill-structures/` | List logged structural measurements |
| `drill_structures_retrieve` | `GET /api/v2/drill-structures/{id}/` | Get one of the logged structural measurements |
| `drill_veins_list` | `GET /api/v2/drill-veins/` | List logged vein intervals |
| `drill_veins_retrieve` | `GET /api/v2/drill-veins/{id}/` | Get one of the logged vein intervals |

**Samples**

| operationId | | Purpose |
|---|---|---|
| `drill_samples_list` | `GET /api/v2/drill-samples/` | List drill samples |
| `drill_samples_retrieve` | `GET /api/v2/drill-samples/{id}/` | Get one of the drill samples |
| `point_samples_list` | `GET /api/v2/point-samples/` | List surface samples |
| `point_samples_retrieve` | `GET /api/v2/point-samples/{id}/` | Get one of the surface samples |

**Assays**

| operationId | | Purpose |
|---|---|---|
| `assays_list` | `GET /api/v2/assays/` | List assay results |
| `assays_retrieve` | `GET /api/v2/assays/{id}/` | Get one of the assay results |
| `certificates_list` | `GET /api/v2/certificates/` | List laboratory certificates |
| `certificates_retrieve` | `GET /api/v2/certificates/{id}/` | Get one of the laboratory certificates |
| `laboratories_list` | `GET /api/v2/laboratories/` | List laboratories |
| `laboratories_retrieve` | `GET /api/v2/laboratories/{id}/` | Get one of the laboratories |

**Quality Control**

| operationId | | Purpose |
|---|---|---|
| `qc_samples_list` | `GET /api/v2/qc-samples/` | List QC samples |
| `qc_samples_retrieve` | `GET /api/v2/qc-samples/{id}/` | Get one of the QC samples |

**STAC Catalog**

| operationId | | Purpose |
|---|---|---|
| `stac_assets_retrieve` | `GET /api/v2/stac/assets/{kind}/{id}/` | Get one of the STAC catalog |
| `stac_collections_items_retrieve` | `GET /api/v2/stac/collections/{collection_id}/items/` | Get one of the STAC catalog |
| `stac_collections_items_retrieve_2` | `GET /api/v2/stac/collections/{collection_id}/items/{item_id}/` | Get one of the STAC catalog |
| `stac_collections_retrieve` | `GET /api/v2/stac/collections/` | Get STAC catalog |
| `stac_collections_retrieve_2` | `GET /api/v2/stac/collections/{collection_id}/` | Get one of the STAC catalog |
| `stac_conformance_retrieve` | `GET /api/v2/stac/conformance/` | Get STAC catalog |
| `stac_retrieve` | `GET /api/v2/stac/` | Get STAC catalog |

**Bulk Export**

| operationId | | Purpose |
|---|---|---|
| `exports_create` | `POST /api/v2/exports/` | Create a bulk export job |
| `exports_download_retrieve` | `GET /api/v2/exports/{job_id}/download/` | Download a finished export |
| `exports_retrieve` | `GET /api/v2/exports/{job_id}/` | Get one of the bulk export |

<!-- END:core-profile -->

Full detail, including why each family is in or out:
[`PROFILE.md`](PROFILE.md). Per-record vocabulary, one readable file each:
[`schemas/`](schemas/).

---

## 5. Pagination and the sync loop

Every list answers one envelope:

```json
{
  "count": 2417,
  "next": "https://api.geodb.io/api/v2/drill-collars/?limit=500&offset=500",
  "previous": null,
  "results": [ ... ],
  "deleted_ids": [],
  "deleted_since_applied": false,
  "sync_timestamp": "2026-03-14T09:15:22.180411+00:00"
}
```

`count` is the total matching rows. `deleted_ids` and `sync_timestamp` are how
a mirror stays consistent — **do not drop them.** A client that yields only
`results` loses the deletion feed and its mirror grows stale rows forever.

**Pull everything:**

```python
import os, requests

BASE = os.environ.get("GEODB_BASE_URL", "https://api.geodb.io")
AUTH = {"Authorization": f"Grant {os.environ['GEODB_TOKEN']}"}


def pull(path, **params):
    """Every row from a list endpoint, following `next` to exhaustion."""
    url, params = f"{BASE}/api/v2/{path}/", {"limit": 500, **params}
    rows = []
    while url:
        page = requests.get(url, params=params, headers=AUTH, timeout=60)
        page.raise_for_status()
        body = page.json()
        rows.extend(body["results"])
        url, params = body.get("next"), None      # `next` already carries them
    return rows
```

**Stay in sync** — incremental, upsert by `id`, honour deletions:

```python
def sync(path, cursor, store):
    """One incremental pull. Returns the next cursor to persist."""
    url = f"{BASE}/api/v2/{path}/"
    params = {"limit": 500}
    if cursor:
        params["modified_since"] = cursor          # DAY-granular: see trap 3.3
    stamp = None
    while url:
        body = requests.get(url, params=params, headers=AUTH, timeout=60).json()
        for row in body["results"]:
            store[row["id"]] = row                 # UPSERT — same-day repeats are normal
        for dead in body.get("deleted_ids") or []:
            store.pop(dead, None)
        stamp = body.get("sync_timestamp") or stamp
        url, params = body.get("next"), None
    return stamp                                   # persist; feed back next time
```

Persist `sync_timestamp` only after the whole page set succeeds. A partial run
that saves the cursor will skip the rows it never read.

---

## 6. Every refusal, and what to do about it

Every 4xx carries the same shape:

```json
{
  "reason_code": "grant_revoked",
  "detail": "The grant was revoked by the project owner.",
  "remedy": "Do not retry; ask the owner for a new grant.",
  "offending": {"parameter": "modified_since", "value": "yesterday"}
}
```

`reason_code` is stable and machine-readable. `remedy` is one sentence of what
to do. `offending` names the thing at fault when there is one. Branch on
`reason_code`; never pattern-match `detail`.

<!-- BEGIN:reason-codes (generated by scripts/emit_agents.py — do not edit) -->

**21 codes.** Generated from [`errors.json`](errors.json), which is itself generated from the server, so this table cannot fall behind what you will actually be refused with. Match on `reason_code`, never on `detail` prose.

`retry` — **no**: retrying the identical request cannot succeed. **after**: retry once `Retry-After` has elapsed. **maybe**: transient or state-dependent, safe to retry later.

| `reason_code` | HTTP | retry | What it means | What you do |
|---|---|---|---|---|
| `invalid_parameter` | 400 | no | A query parameter was present but could not be understood. | Correct the parameter named in `offending` and resend. Dates are ISO 8601 (YYYY-MM-DD or a full timestamp). |
| `parse_error` | 400 | no | The request body was not valid for its Content-Type. | Send well-formed JSON with Content-Type: application/json. |
| `validation_error` | 400 | no | The request body or parameters failed validation. | Correct the fields named in the response and resend. |
| `authentication_failed` | 401 | no | No usable credential was presented. | Send `Authorization: Grant <token>` with a current grant. |
| `grant_expired` | 401 | no | The grant passed its expiry date. | Ask the project owner to rotate or reissue it. |
| `grant_invalid` | 401 | maybe | The grant cannot be used in its current project or data-room state. | Contact the project owner. |
| `grant_malformed` | 401 | no | The Authorization header is not a well-formed Grant header. | Send exactly 'Authorization: Grant <token>'. |
| `grant_revoked` | 401 | no | The grant was revoked by the project owner. | Do not retry; ask the owner for a new grant. |
| `grant_unknown` | 401 | no | The token does not resolve to any grant. | Check the credential. If it was never issued, ask the project owner for an access grant. Do not retry as-is. |
| `grant_no_read_capability` | 403 | no | The view declares no read capability, so no grant may reach it. | Use an operation listed in the published OpenAPI spec (/api/schema/). |
| `grant_room_pinned_refused` | 403 | no | The grant is pinned to a data room that does not expose this endpoint. | Use an operation the room exposes, or ask the owner for a project-wide key. |
| `grant_room_pinned_unclassified` | 403 | no | The endpoint has no room-scope classification, so a room-pinned grant is refused rather than guessed at. | Use an operation the room exposes, or ask the owner for a project-wide key. |
| `grant_surface_forbidden` | 403 | no | The endpoint is not part of the grant-readable surface. | Use an operation listed in the published OpenAPI spec (/api/schema/). |
| `grant_write_forbidden` | 403 | no | A write method was attempted with a read-only grant. | Use a read operation. The one write a grant may make is creating an export job (POST /api/v2/exports/). |
| `permission_denied` | 403 | no | The credential is valid but not permitted this operation. | Use an operation listed in the published OpenAPI spec (/api/schema/), within the grant's project scope. |
| `use_v2` | 403 | no | Access grants read the /api/v2/ surface only. The /api/v1/ tree is not part of the protocol. | Request the same path under /api/v2/. Every operation a grant may call is listed in the published OpenAPI spec (/api/schema/). |
| `not_found` | 404 | no | No such resource inside this credential's scope. A row that exists in another project is indistinguishable from one that does not exist — by design. | Check the id, and that it belongs to the project this grant is pinned to (GET /api/v2/grant-context/). |
| `method_not_allowed` | 405 | no | The HTTP method is not supported on this endpoint. | Use a method the spec declares for this path. The read surface is GET-only apart from POST /api/v2/exports/. |
| `export_concurrency` | 429 | after | This grant already holds the maximum number of export jobs that have not finished. | Do NOT resend the same export. Poll the status_url of the jobs you already started; when one reaches a terminal state a slot frees. `offending` carries in_flight and limit. |
| `grant_auth_throttled` | 429 | after | Too many credentials that resolve to no grant have been presented from this address within the hour. | Stop retrying with a credential that is not working. Obtain a current grant from the project owner, then resend after the interval in Retry-After. |
| `throttled` | 429 | after | The grant's request rate was exceeded. | Wait for the interval given in the Retry-After header, then resend. Prefer ?modified_since= incremental pulls over repeated full pulls. |

<!-- END:reason-codes -->

---

## 7. Retry policy

**Three different refusals answer `429`, and they need opposite reactions.**

| Code | Meaning | What to do |
|---|---|---|
| `throttled` | You are calling too often | Sleep for `Retry-After`, then resend. Prefer `?modified_since=` over repeated full pulls. |
| `export_concurrency` | You are holding too many unfinished export jobs | **Do not resend the export.** Poll the `status_url` of jobs you already started; a slot frees when one finishes. |
| `grant_auth_throttled` | Too many unknown credentials from your address | Stop retrying. Get a working grant first. |

All three send `Retry-After` in seconds. Honour it; do not invent a backoff
shorter than it.

**401 — do not retry.** `grant_revoked`, `grant_expired`, `grant_unknown` and
`grant_malformed` are all permanent until a human does something. Retrying a
revoked token is visible to the project owner in their access log and is the
fastest way to look broken. Stop, surface the `remedy`, ask for a new token.

**403 — do not retry.** You asked for something outside the grant's surface
(`grant_surface_forbidden`), tried to write (`grant_write_forbidden`), or used
the `/api/v1/` tree (`use_v2`). Fix the request.

**404 — do not retry.** A row in another project is indistinguishable from one
that does not exist. That is deliberate. Check `grant-context` for which
project you are pinned to.

**400 — do not retry as-is.** Read `offending`, fix the parameter, resend.

**5xx — retry with exponential backoff**, a few times, then give up and report.

Sane defaults: one request at a time per grant unless the owner says otherwise,
`limit=500`, and a timeout of 60 s (exports and large pages are slow).

---

## 8. If you are implementing the server

You are writing a second implementation of this protocol, not a client. Two
documents are for you:

- **[`PROFILE.md`](PROFILE.md)** — the operations a conforming server must
  serve, what the envelope must contain, the error contract, and the coordinate
  rule. It is generated from the spec's own flags, so it cannot describe a
  different profile from the one published.
- **[`conformance/`](conformance/)** — the runner you point at your own base
  URL with your own token. It checks the envelope, the auth codes, the sync
  semantics, the coordinate contract, the STAC landing page, the export flow,
  and that every 4xx you emit carries a registered `reason_code`. Green there
  is what "conforming" means; there is no certification and no committee.

  ```bash
  pip install geodb-conformance          # or: pip install -e conformance/
  python -m geodb_conformance read \
      --base-url https://your-server.example.com \
      --token "$YOUR_GRANT_TOKEN" \
      --profile core \
      --markdown conformance-report.md
  ```

  It exits 0 when your server honoured the contract and 1 when it did not, so
  it drops straight into CI; `--junit` writes JUnit XML beside the markdown.
  Every assertion is named and carries a one-line statement of what it proves,
  and the markdown report puts that line beside each verdict — so the output
  reads as the contract with a result against each clause, which is what you
  want in a ticket. `--profile core` is the profile you are asked to
  implement; `--profile full` adds our own extensions and the checks that need
  outbound network or a populated asset lane. `python -m geodb_conformance
  list` prints every assertion without contacting anything.

  The suite carries its own copy of the spec, the schemas and the error
  register, and checks you against **those** — it never asks your server to
  describe itself, because a runner that did would pass against any
  self-consistent server. It validates real rows out of your lists against the
  published JSON Schemas, and it reprojects a coordinate with `pyproj` to check
  your derived WGS84 really is your native coordinate reprojected (install
  `geodb-conformance[geo]` for that one; without it that check skips and says
  so).

  **Every assertion in it has been watched to fail.** `python -m
  geodb_conformance selftest` runs each one against a mock server broken in
  exactly the one way that assertion exists to catch, and asserts it goes red
  there and green against a correct one. That needs no credentials and no
  network, and it is what our own CI runs on every push.

Start from [`spec/openapi.yaml`](spec/openapi.yaml) (normative for the wire)
and [`schemas/`](schemas/) (the vocabulary, one record type per file). The
coordinate rule in §3.1 is not optional: a server that writes reprojected
degrees into `latitude`/`longitude` is not conforming, it is discarding its
customer's data.

If something here is ambiguous, missing or wrong, that is the thing we most
want to hear about — [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Quickstart

Runnable as-is once `GEODB_TOKEN` is set. `conformance/agent_smoke.py`
executes this exact block in CI, so it cannot rot.

```python
import os
import requests

BASE = os.environ.get("GEODB_BASE_URL", "https://api.geodb.io")
AUTH = {"Authorization": f"Grant {os.environ['GEODB_TOKEN']}"}


def pull(path, **params):
    url, params = f"{BASE}/api/v2/{path}/", {"limit": 500, **params}
    rows = []
    while url:
        body = requests.get(url, params=params, headers=AUTH, timeout=60).json()
        rows.extend(body["results"])
        url, params = body.get("next"), None
    return rows


context = requests.get(f"{BASE}/api/v2/grant-context/", headers=AUTH,
                       timeout=60).json()
collars = pull("drill-collars")
assays = pull("assays")

print(f"project: {context['project']['name']}")
print(f"collars: {len(collars)}   assays: {len(assays)}")

# The CRS is per record, in `epsg`. latitude/longitude are the ORIGINAL
# coordinate in THAT system — easting/northing unless epsg is 4326.
epsgs = {c.get("epsg") for c in collars if c.get("epsg")}
print(f"collar CRS (EPSG): {sorted(epsgs)}")
for collar in collars[:1]:
    print(f"  native   : {collar['source_coordinate']}  ({collar['xy_units']})")
    print(f"  WGS84    : {collar['geometry_geojson']}")

# Assay values are decimal STRINGS — parse with Decimal, never float.
from decimal import Decimal
values = [(e["element"], Decimal(e["value"]), e["units"])
          for a in assays for e in a.get("elements", [])]
print(f"assay values: {len(values)}   e.g. {values[:2]}")
```

---

## Where everything is

| File | What |
|---|---|
| [`spec/openapi.yaml`](spec/openapi.yaml) | **Normative for the wire.** Generated from the reference implementation. |
| [`PROFILE.md`](PROFILE.md) | Which operations are the protocol and which are geoDB's own. |
| [`schemas/`](schemas/) | One JSON Schema per core record type. |
| [`errors.json`](errors.json) | Every `reason_code`, with meaning, remedy and retry safety. |
| [`examples/`](examples/) | Runnable: curl, geodb-client, bare requests, TypeScript. |
| [`conformance/`](conformance/) | The runner a second implementation points at itself. |
| [`stac/xpl/`](stac/xpl/) | The `xpl:` STAC extension for exploration assets. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to file a useful issue. |
| [`SECURITY.md`](SECURITY.md) | How to report a vulnerability. |

**Python client:** `pip install geodb-client` —
[source](https://github.com/geodbio/geodb-client).
