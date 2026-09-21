# Examples

Four flavours of the same thing: pull the collars and the assays, and report
the coordinate reference system. Each runs as-is against the public sandbox —
no signup, no account.

```bash
export GEODB_TOKEN=<sandbox token from AGENTS.md section 2>
export GEODB_BASE_URL=https://api.geodb.io      # optional; this is the default

bash    examples/curl.sh                 # curl + python3, no libraries at all
python  examples/python_client.py        # the geodb-client library -> DataFrames
python  examples/python_requests.py      # bare `requests` — port this to any language
npx tsx examples/typescript_fetch.ts     # global fetch, no dependencies
```

`python examples/run_all.py` runs whichever of them the machine can run, and is
what CI calls. Without `GEODB_TOKEN` it skips — an example that needs a
credential is not a failure on a machine that has none.

**Every one of them prints the CRS**, because that is the thing this domain
gets wrong most often: `latitude` and `longitude` hold the *original* imported
coordinate in the CRS named by `epsg`, which is easting/northing unless `epsg`
is 4326. See [AGENTS.md](../AGENTS.md) section 3.1.
