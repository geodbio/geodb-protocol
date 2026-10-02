# The core profile

Every operation a conforming geoDB protocol server answers (the spec flags them `x-protocol-core`); everything else is a geoDB extension. Paths are under the base URL.

## Grant

- `GET /api/v2/grant-context/` — Get what this credential can see

## Discovery

- `GET /api/v2/model-schemas/` — Get field definitions
- `GET /api/v2/model-schemas/{id}/` — Get one of the field definitions

## Drill Holes

- `GET /api/v2/drill-collars/` — List drill holes
- `GET /api/v2/drill-collars/{id}/` — Get one of the drill holes
- `GET /api/v2/drill-collars/{id}/trace/` — Get a hole's computed trace
- `GET /api/v2/drill-collars/{id}/xyz_at_depth/` — Position at a depth down a hole
- `GET /api/v2/drill-surveys/` — List downhole survey stations
- `GET /api/v2/drill-surveys/{id}/` — Get one of the downhole survey stations

## Drill Intervals

- `GET /api/v2/drill-alterations/` — List logged alteration intervals
- `GET /api/v2/drill-alterations/{id}/` — Get one of the logged alteration intervals
- `GET /api/v2/drill-custom-intervals/` — List logged custom intervals
- `GET /api/v2/drill-custom-intervals/{id}/` — Get one of the logged custom intervals
- `GET /api/v2/drill-lithologies/` — List logged lithology intervals
- `GET /api/v2/drill-lithologies/{id}/` — Get one of the logged lithology intervals
- `GET /api/v2/drill-mineralizations/` — List logged mineralization intervals
- `GET /api/v2/drill-mineralizations/{id}/` — Get one of the logged mineralization intervals
- `GET /api/v2/drill-rqds/` — List logged RQD and geotechnical intervals
- `GET /api/v2/drill-rqds/{id}/` — Get one of the logged RQD and geotechnical intervals
- `GET /api/v2/drill-spectral-intervals/` — List logged spectral intervals
- `GET /api/v2/drill-spectral-intervals/{id}/` — Get one of the logged spectral intervals
- `GET /api/v2/drill-structures/` — List logged structural measurements
- `GET /api/v2/drill-structures/{id}/` — Get one of the logged structural measurements
- `GET /api/v2/drill-veins/` — List logged vein intervals
- `GET /api/v2/drill-veins/{id}/` — Get one of the logged vein intervals

## Samples

- `GET /api/v2/drill-samples/` — List drill samples
- `GET /api/v2/drill-samples/{id}/` — Get one of the drill samples
- `GET /api/v2/point-samples/` — List surface samples
- `GET /api/v2/point-samples/{id}/` — Get one of the surface samples

## Assays

- `GET /api/v2/assays/` — List assay results
- `GET /api/v2/assays/{id}/` — Get one of the assay results
- `GET /api/v2/certificates/` — List laboratory certificates
- `GET /api/v2/certificates/{id}/` — Get one of the laboratory certificates
- `GET /api/v2/laboratories/` — List laboratories
- `GET /api/v2/laboratories/{id}/` — Get one of the laboratories

## Quality Control

- `GET /api/v2/qc-samples/` — List QC samples
- `GET /api/v2/qc-samples/{id}/` — Get one of the QC samples

## STAC Catalog

- `GET /api/v2/stac/` — Get the STAC catalog root
- `GET /api/v2/stac/assets/{kind}/{id}/` — Download one STAC asset
- `GET /api/v2/stac/collections/` — List STAC collections
- `GET /api/v2/stac/collections/{collection_id}/` — Get one STAC collection
- `GET /api/v2/stac/collections/{collection_id}/items/` — List the items of a STAC collection
- `GET /api/v2/stac/collections/{collection_id}/items/{item_id}/` — Get one STAC item
- `GET /api/v2/stac/conformance/` — STAC conformance classes

## Bulk Export

- `POST /api/v2/exports/` — Create a bulk export job
- `GET /api/v2/exports/{job_id}/` — Poll an export job
- `GET /api/v2/exports/{job_id}/download/` — Download a finished export
