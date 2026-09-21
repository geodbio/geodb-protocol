# The `xpl:` STAC extension — exploration vocabulary

- **Title:** Exploration (`xpl`)
- **Identifier:** `https://spec.geodb.io/xpl/v0.1.0/schema.json`
- **Field name prefix:** `xpl`
- **Scope:** Item (properties), Asset
- **Extension maturity:** Proposal (0.1.0)

STAC 1.1 has ~89 extensions and **none** for geophysics, drilling, or mining.
`xpl:` fills that gap: the vocabulary for describing exploration STAC items. All
fields are OPTIONAL and only meaningful on the item *profile(s)* they belong to.
The machine-readable schema is [`schema.json`](schema.json) (generated from the
geoDB reference implementation — a drift test keeps the emitter and schema in
lock-step, so they can never disagree).

## Item profiles

| Profile | `collection` | Geometry | Key fields |
|---|---|---|---|
| **geophysical-survey** | `geophysical-surveys` | survey footprint (Polygon) | `xpl:method`, `xpl:acquisition_type`, `xpl:contractor`, `xpl:instrument`, `xpl:line_spacing_m`, `xpl:footprint_source`, `xpl:specs` |
| **drillhole-package** | `drillhole-packages` | collar (Point) | `xpl:hole_id`, `xpl:hole_type`, `xpl:total_depth_m`, `xpl:azimuth_deg`, `xpl:dip_deg`, `xpl:sample_count` |
| **assay-certificate** | (asset-level) | — | `xpl:laboratory`, `xpl:certificate_number`, `xpl:elements` |

## Fields

### geophysical-survey
| Field | Type | Description |
|---|---|---|
| `xpl:method` | string enum | `magnetics`, `gravity`, `em`, `ip`, `resistivity`, `radiometrics`, `mt`, `seismic`, `gpr`, `other` |
| `xpl:acquisition_type` | string enum | `ground`, `airborne`, `downhole` |
| `xpl:contractor` | string | Survey / acquisition company |
| `xpl:instrument` | string | Sensor / instrument |
| `xpl:line_spacing_m` | number | Nominal line spacing (metres) |
| `xpl:survey_date_start` / `xpl:survey_date_end` | date | Acquisition window (also mirrored to STAC `start_datetime`/`end_datetime`) |
| `xpl:footprint_source` | string enum | How the footprint was derived: `grid`, `vector`, `lines_hull`, `declared`, `drawn` |
| `xpl:specs` | object | Free-form method-specific parameters (tie-line spacing, terrain clearance, …) |

### drillhole-package
| Field | Type | Description |
|---|---|---|
| `xpl:hole_id` | string | Collar / hole identifier |
| `xpl:hole_type` | string | Drilling method (DD, RC, …) |
| `xpl:total_depth_m` | number | Final drilled depth (metres) |
| `xpl:azimuth_deg` / `xpl:dip_deg` | number | Collar orientation |
| `xpl:sample_count` | integer | Samples in the package |

### assay-certificate (asset-level)
| Field | Type | Description |
|---|---|---|
| `xpl:laboratory` | string | Issuing laboratory |
| `xpl:certificate_number` | string | Lab certificate / job number |
| `xpl:elements` | array | Element symbols reported |

## Enums come from the reference implementation

`xpl:method`, `xpl:acquisition_type`, and `xpl:footprint_source` enumerations are
generated from the geoDB model choices — the same values a survey is stored
against — so the extension and the platform never drift.

## Examples

- [`examples/airborne-mag-survey.json`](examples/airborne-mag-survey.json) — an
  airborne-magnetics survey item (geophysical-survey profile) with a COG grid asset.
- [`examples/drillhole-package.json`](examples/drillhole-package.json) — a
  drillhole package item (drillhole-package profile) with GeoParquet + certificate assets.

Both validate against `schema.json` and STAC 1.1 (offline; see the reference
implementation's `api/stac/validation.py`).
