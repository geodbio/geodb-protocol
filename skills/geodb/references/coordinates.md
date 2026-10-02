# Coordinates: the native numbers, their CRS, and the derived WGS84

Why `latitude`/`longitude` are usually NOT degrees, where WGS84 lives, how to measure and compare positions, and the one rule for writing a coordinate.

The `latitude`/`longitude` fields are a **misnomer**: they hold the **original
as-imported coordinate in the CRS named by that record's `epsg`**. For a UTM
import that is **easting in `longitude`, northing in `latitude`**. They are
true degrees **only** when `epsg == 4326`, and one file (or one project) can
carry **several** EPSGs at once. Reading them as degrees puts the point on the
wrong continent.

Stored `geometry` is always **WGS84 (EPSG:4326)**. That is the one frame you
can rely on across projects.

⛔ **Never write the reprojected numbers back into a record's `latitude`/`longitude`.**
The original numbers plus their `epsg` are the record; the import derives
WGS84 itself. Reprojecting for a join is fine; storing reprojected coordinates
(or degrees under a projected `epsg`) destroys the provenance the whole design
protects.

Measure a distance in a **projected** CRS (metres), never in degrees: a degree
is not a distance.

⚠ `LandHolding` has **no** `latitude`/`longitude` fields at all: a claim is
its polygon (a `geometry` WKT column, already WGS84).

⛔ **Never author a ring from memory.** A boundary you invent draws exactly
like a surveyed one and there is nothing on screen that says which it is:
never approximate a claim.

**Say which CRS you read.** When you report or use a position, state its CRS
without being asked: "easting and northing in the project's UTM zone (the
records' `epsg`)", or "WGS84 longitude and latitude from `geometry`". That
holds for every answer that carries a position (one hole, a table of collars,
an extent), even when the question was about something else. Each
project keeps its own CRS, so compare positions between projects through
`geometry`, never through the native `latitude`/`longitude`. A coordinate
quoted without its CRS is the commonest way a correct number turns into a
point on the wrong continent.
