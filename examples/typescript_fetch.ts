/**
 * Pull collars and assays with nothing but `fetch` — no dependencies.
 *
 *   export GEODB_TOKEN=<your grant>            # the public sandbox token works
 *   npx tsx examples/typescript_fetch.ts       # or: deno run --allow-net --allow-env
 *
 * Needs a runtime with global fetch (Node 18+, Deno, Bun).
 */

const BASE = (process.env.GEODB_BASE_URL ?? "https://api.geodb.io").replace(/\/$/, "");
const TOKEN = process.env.GEODB_TOKEN;
if (!TOKEN) throw new Error("set GEODB_TOKEN (see AGENTS.md section 2)");
const AUTH = { Authorization: `Grant ${TOKEN}` }; // `Grant`, not `Bearer`

interface Page<T> { count: number; next: string | null; results: T[]; deleted_ids?: number[] }
interface Collar {
  name: string; epsg: number | null; latitude: number | null; longitude: number | null;
  xy_units: string | null;
  source_coordinate: { x: number; y: number; epsg: number } | null;
  geometry_geojson: { type: string; coordinates: number[] } | null;
}
interface Element_ { element: string; value: string; units: string } // value is a STRING
interface Assay { name: string; elements: Element_[] }

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url, { headers: AUTH });
  if (!response.ok) {                              // every 4xx has this shape
    const body = await response.json() as { reason_code: string; detail: string; remedy?: string };
    throw new Error(`${response.status} ${body.reason_code}: ${body.detail}\n  remedy: ${body.remedy}`);
  }
  return response.json() as Promise<T>;
}

/** Every row, following `next` to exhaustion. */
async function pull<T>(resource: string): Promise<T[]> {
  let url: string | null = `${BASE}/api/v2/${resource}/?limit=500`;
  const rows: T[] = [];
  while (url) {
    const page: Page<T> = await get<Page<T>>(url);
    rows.push(...page.results);
    url = page.next;                               // absolute, already carries params
  }
  return rows;
}

async function main() {
  const context = await get<{ project: { id: number; name: string }; protocol_version: string }>(
    `${BASE}/api/v2/grant-context/`);
  console.log(`project : ${context.project.name} (id ${context.project.id})`);
  console.log(`protocol: ${context.protocol_version}`);

  const collars = await pull<Collar>("drill-collars");
  const assays = await pull<Assay>("assays");
  console.log(`\ncollars : ${collars.length} rows\nassays  : ${assays.length} rows`);

  // The CRS is per record, in `epsg`. It decides what the scalars MEAN.
  const epsgs = [...new Set(collars.map((c) => c.epsg).filter((e): e is number => !!e))].sort();
  const projected = !(epsgs.length === 1 && epsgs[0] === 4326);
  console.log(`\nCRS (EPSG): ${epsgs}  ${projected ? "(PROJECTED: easting/northing)" : "(WGS84 degrees)"}`);

  // ⚠️ latitude/longitude are the ORIGINAL coordinate in `epsg`, NOT degrees.
  const c = collars[0];
  console.log(`\n${c.name}`);
  console.log(`  latitude / longitude : ${c.latitude} / ${c.longitude}  <- in EPSG ${c.epsg} (${c.xy_units})`);
  console.log(`  source_coordinate    : ${JSON.stringify(c.source_coordinate)}`);
  console.log(`  geometry_geojson     : ${JSON.stringify(c.geometry_geojson)}`);

  // `value` is a decimal STRING. JS numbers are binary floats, so keep the
  // string (or use a decimal library) for anything that must round-trip.
  const values = assays.flatMap((a) => a.elements ?? []);
  console.log(`\nassay values: ${values.length}`);
  for (const v of values.slice(0, 3)) console.log(`  ${v.element.padEnd(3)} ${v.value} ${v.units}`);
}

// Wrapped in main() rather than using top-level await: that needs an ESM
// context, and a .ts file run through a CJS-defaulting loader will not have one.
main().catch((error) => { console.error(String(error)); process.exit(1); });
