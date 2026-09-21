# geodb-conformance

**Point it at your own server and find out whether it implements the geoDB Open
Exploration Protocol.**

```bash
pip install geodb-conformance

python -m geodb_conformance read \
    --base-url https://your-server.example.com \
    --token "$YOUR_GRANT_TOKEN"
```

Exit code `0` means your server honoured the contract, `1` means it did not.
There is no certification and no committee: green here is what "conforming"
means.

## What you get

```
  ✅  auth.header_accepted        A grant token in `Authorization: Grant <token>` is accepted …
  ✅  envelope.paginated_list     Every core list answers the one envelope: `count`, `next` …
  ❌  sync.unparseable_is_refused An unparseable `modified_since` is refused 400 `invalid_parameter` …
        /api/v2/drill-collars/?modified_since=yesterday must be REFUSED, not ignored
```

Every assertion has a **name** and a one-line statement of **what it proves**.
`--markdown report.md` writes those two columns beside each verdict, so the
report reads as the contract with a result against each clause — which is what
you want to paste into a ticket. `--junit report.xml` writes JUnit XML for CI.

| Flag | |
|---|---|
| `--profile core` | the profile a second implementer is asked to serve (default) |
| `--profile full` | plus geoDB extensions, and checks needing outbound network or a populated asset lane |
| `--only NAME` | run one assertion (repeatable) |
| `--strict` | treat a skipped assertion as a failure |
| `--markdown` / `--junit` | write the report |

`python -m geodb_conformance list` prints every assertion and what it proves,
without contacting anything.

## What it checks

Auth and the refusal contract · the one list envelope and its deletion-sync
keys · `limit`/`offset` paging · only `cf_*` extra keys on a row · every row of
every core list validated against the **published JSON Schema** for its record
type · `modified_since` / `deleted_since` semantics, including that an
unparseable date is refused rather than ignored · the coordinate contract ·
STAC 1.1 landing, conformance link and asset redirect · the export create →
status → download round trip · that every 4xx carries a registered
`reason_code` · `X-GeoDB-Protocol-Version`.

Two of those deserve a note:

- **The coordinate check reprojects.** It takes your native coordinate, its
  `epsg`, and reprojects it with `pyproj`, then compares against the WGS84 you
  derived. That is the only way to catch a server that silently reprojected
  into `latitude`/`longitude` and lost its customer's original numbers. Install
  `geodb-conformance[geo]` for it; without `pyproj` it skips and says so.
- **The schemas are ours, not yours.** The suite ships its own copy of
  `spec/openapi.yaml`, `schemas/*.json` and `errors.json` and checks you
  against those. It never asks your server to describe itself — a runner that
  did would pass against any self-consistent server, including one serving a
  completely different protocol.

## Every assertion has been watched to fail

```bash
python -m geodb_conformance selftest
```

Runs each assertion twice: against a mock server serving the protocol
**correctly** (it must pass) and against the same mock broken in **exactly the
one way that assertion exists to catch** (it must fail). An assertion that has
never been observed to go red is a line in a report, not a test.

No credentials and no network, so it is also what CI runs:

```bash
python conformance/run.py --offline
```

You can drive the mock by hand too, which is the quickest way to see what a
given failure looks like before you go hunting for it in your own server:

```bash
python -m geodb_conformance.mock_server --port 8765
python -m geodb_conformance.mock_server --port 8765 --break envelope.paginated_list
```

## If a check is wrong

Tell us — that is the most useful kind of issue. The suite encodes our reading
of our own protocol, and a second implementer hitting a check that is stricter
than the spec, or that bakes in something geoDB happens to do, has found a real
defect in the contract. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md).
