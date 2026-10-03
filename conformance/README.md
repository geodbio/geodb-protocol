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

## The write profile

> **Published with protocol 0.2.0.** The write profile's `status` is
> `published`. geoDB's production servers accept writes from geoDB staff
> connections only while API writing opens (other keys — the public demo write
> key included — are refused `writes_staff_only`), so point the suite at your
> own server.

```bash
python -m geodb_conformance write \
    --base-url https://your-server.example.com \
    --token "$A_KEY_THAT_MAY_WRITE_RECORDS"
```

The write half's contract is its own versioned document,
`contract/write-profile.json` (generated from the reference implementation,
like `errors.json`): the endpoints, the body keys, the intents and whether an
agent must confirm each with its user, the row statuses, the batch cap, and
every reason code a write can answer. 20 named assertions check a server
against it — validate is the dry run · the coordinate system is never assumed
(`missing_crs`) · an `external_id` re-sent is a no-op · an `Idempotency-Key`
replays · a create never overwrites · `set_required` / `set_not_owned` · an
update changes only what it names · undo restores field for field, refuses a
row changed since (`undo_stale`), never runs twice (`already_undone`) and
removes what a create made · a retract needs its confirm, cascades, and undo
brings everything back · restore · a resource-path write names the one
endpoint · a record read and written back is `unchanged` · every refusal is
registered · the key's write log lists writes and undos.

**Every assertion writes.** It refuses (exit 2, before writing anything) unless
the key's project is a declared write twin (`grant-context` →
`writes.write_twin: true`, a demo project reset nightly); pass
`--allow-non-twin` for a staging project you may write test data into. Each row it writes is named `CONF-<run>-…`, and the run ends by undoing
every write it made, newest first (`--keep` leaves them). The write break
matrix runs with the read one in `selftest`: 20/20, each assertion red under
its own breakage of the mock and green against a correct one.

## If a check is wrong

Tell us — that is the most useful kind of issue. The suite encodes our reading
of our own protocol, and a second implementer hitting a check that is stricter
than the spec, or that bakes in something geoDB happens to do, has found a real
defect in the contract. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md).
