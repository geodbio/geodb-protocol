# Drilling: the programme, drill intercepts, and sampling passes

Daily shift reports, rigs and contractors; how drill intercepts are chosen and length-weighted (never a grade cutoff); why a hole can carry two samples over one interval.

**DSR = Daily Shift Report** — ONE row per drill per shift (`DailyShiftReport`).
NOT "Drill Site Record", NOT permitting, NOT a LandHolding. The subsystem:
- `DrillingContractor` — a drilling company hired by this operator (company-scoped).
- `Drill` — one rig asset of a contractor (`rig_number`, `drill_type`; company-scoped).
- `DailyShiftReport` — the DSR: project, drill, contractor, `shift_date`, `shift`
  (day/night), hole (`hole_id` text + optional `hole_collar` link), crew
  (`driller_name` / `helper_name` / `supervisor_name`), `start_depth_m` /
  `end_depth_m`, `status` (draft/submitted/approved).
- `DSRActivity` — line items inside a DSR: `activity_type` (drill/trip/casing/
  survey/maintenance/standby/move/safety/other; project-custom types via
  `activity_type_custom`), `duration_hours`, `depth_from_m`/`depth_to_m`, notes.
- `Consumable` + `DSRConsumableUsage` — the project catalog of materials + the
  per-DSR usage rows (`quantity`).
A "cutsheet" in the drilling-management sense is the RC cutsheet document — a
different thing from an import file that happens to be called a cutsheet.

- DSRs are created RIG-SIDE: a driller fills the shift form on the drilling web
  pages, or a photo of the paper form is scanned into a DRAFT DSR from the
  import page. **There is NO contract→DSR path.** A drilling CONTRACT governs
  the engagement — it maps to a DrillingContractor + Drill setup, done on the
  drilling web pages — never to DSR rows.
- **Contractor isolation is a real permission boundary.** Drill-only users are
  scoped to ONE DrillingContractor and the server scopes every drilling read to
  it. Never offer a cross-contractor comparison to a contractor-scoped user —
  a read that comes back narrower than expected is the isolation working, not
  missing data.

Meters drilled = end depth − start depth per DSR; depths may be empty. A
negative meters value is a data-entry flag worth surfacing, not clipping.

Merged grade reads return `depth_from` / `depth_to` / the hole name / one column
per element. Below-detection values in a MERGED read are **ALREADY substituted**
per the project's `AssayMergeSettings` (half the detection limit by default) —
do NOT substitute them again, and do not treat the substituted value as a real
measurement.

**Choosing boundaries is THE JUDGEMENT CALL, and never a grade cutoff.**
Real intercepts routinely OPEN AND CLOSE BELOW their own internal average and
swallow internal waste: a validated intercept can open on a sample barely above
its own average, close on one below it, and carry a below-detection sample in
the middle. **No threshold reproduces that.** A cutoff produces a
fluent table that is wrong in a way the reader cannot see — and these tables
go into public disclosure. Look at more than one scale: the broad envelope AND
the tight high-grade cores inside it; one scale alone reliably misses the other.
PROPOSE boundaries and say why you drew each one; the geologist rules. If the
user gives you boundaries, use theirs exactly.

**Length-weight with one tested implementation — never hand-rolled
arithmetic**, which gets a different answer every session. **ALWAYS read the
coverage and say so when it is below 1.0** — it is how you tell a real
intercept from a little assay stretched across a long span. Coverage ABOVE 1.0
means overlapping sample support; say that too, do not round it to "100%".

**The conventional nested shape.** Whole-hole row first, then `incl.`
(a sub-range of its parent) and `and` (a further separate interval in the same
hole), re-weighted over the narrower span. Report every element the user asked
for — dropping silver from a silver-bearing table is a silent omission, not a
simplification.

**Reading intercepts without re-deriving them.** geoDB serves the two halves
of an intercept table as reads, so your numbers match the ones geoDB reports:
(1) a hole's merged grades for ONE sampling pass — the project's export pass
unless you name another — with below-detection values already substituted
per the project's merge settings; (2) length-weighted intervals over the
boundaries you send, each with its coverage, in the nested order you give
(the hole row, then `incl.` / `and`). **There is no cutoff parameter, and a
request that names one is refused**: read the grades, propose boundaries the
way a geologist draws them, say why, and let the geologist rule. Report every
element asked for, state coverage below 1.0, and never call downhole length
true width.

**Where a depth is in space.** A hole's desurveyed trace (from its collar and
survey stations, minimum curvature by default) and the position at any depth
down it are served by geoDB, on the PROJECT LOCAL GRID in metres — not degrees,
and not the hole's own `epsg`. Interval records carry the same local-grid
positions at their from/to depths. Read these instead of desurveying yourself;
a hole with no survey stations has no trace to read, and you say so rather
than assuming it is vertical.

⛔ Do NOT convert grade units in prose (g/t ↔ oz/ton) — an arithmetic slip in a
press-release sentence is the same class of error as a hand-rolled composite.
⛔ Do NOT state true widths unless the user gives you the zone orientation:
downhole length is not true width, and dip alone does not determine it.

A sampling PASS is one physical sampling of a hole. A second pass over the same
ground is normal cost-control design: Au on every 5-ft bag (gold is nuggety) AND a
48-element ICP suite on 10-ft composites of the pulps (that signal varies slowly, and
it halves the bill). Both are REAL samples — their own lab IDs, their own certificates,
often a different lab a week later. A composite is NOT a duplicate, NOT QC, and NEVER
derivable from its members (the average of two Au values is not an ICP result). ⛔ Never
"clean up" a second pass by deleting rows — that destroys assay values. Every drill
sample belongs to exactly one pass (the project's `default` pass unless told
otherwise); a pass carries a kind — primary / composite / metallurgical (bulk) /
resample (re-split) / historic / other.

**THE RULE, one sentence:** within one pass, in one hole, intervals must not overlap
(1 mm); across passes anything goes; sample NAMES stay unique per project regardless
(a lab ID names one physical bag).

**Three reads — say which one the user is looking at:**

| Surface | Reads |
|---|---|
| ONE sequence — Leapfrog / the ODBC interval table, the 3D viewer + grade shells, map drill traces, compositing / intercept tables, Quick Log start-depth auto-fill | ONE pass: the project's EXPORT pass (Project settings → Data Export & ODBC → "Drill Sample Set"), else the default pass — NEVER passes merged. A 3D or map drill layer can pick a different pass of its own. |
| Listers — the DrillSample grid (its "Pass" column), CSV/XLSX (a `sample_set` column), the Quick Log roster (badged), the API list, strip-log sample tracks (a pass filter) | EVERY pass, named. |
| Putting EXISTING rows into a pass | a staff-reviewed PROPOSAL, never a direct write. |

So "my ODBC table has fewer rows than the grid" is these two reads disagreeing ON
PURPOSE: the table serves the export pass, the grid lists every pass. Which pass is
"primary" for export is the CUSTOMER's call — offer the settings page, never pick it
for them silently. Length-weighting refuses overlapping input, so scope to ONE pass
before compositing.

The export pass is set in ONE place: **Project settings → Data Export & ODBC →
"Drill Sample Set"**, the customer's own choice (it decides what Leapfrog, the 3D
viewer, the map and every composite READ). It is NOT on Assay Merge Settings: that
page governs how assay VALUES merge, not which sampling pass exports. When a user
says *"just pick the primary one"*, describe what each pass holds so the choice is
easy, and send them to that setting.

A drill-sample import that would overlap the target pass — or re-use an existing
interval under a NEW name (a re-split? a re-import with renamed IDs?) — is refused
as a QUESTION with nothing written: counts per hole, the conflict classes, sample
pairs. The passing paths: a NEW pass (named, with its kind — a guessed kind is a
wrong label forever), an EXISTING non-default pass, or fix the file. An unknown pass
name is refused, never created silently. Ask the user what the pass IS before naming
it. ⛔ Never answer the ask by dropping rows into the default pass.

**Moving EXISTING rows into their own pass** ("put my composites in a Composites
pass") is a staff-run PROPOSAL: a dry run sweeps the default pass for rows that
CONTAIN ≥2 others in the same hole, reports each with the NAME convention that matched
(joined ids, a range, a stripped suffix …), writes a CSV a human reads, and only then
applies — with a snapshot and a revert. It proposes, never classifies silently; a
name pattern is never proof, and containers with NO naming signal (`geometry_only`)
are EXCLUDED — a single container spanning hundreds of metres over dozens of rows is a
logging error, not a composite. ⛔ Never invent a threshold for "this looks like a composite".

**"My validator says thousands of overlaps."** Before calling it a data error, ask whether the
project's composites still sit in the DEFAULT pass — overlaps are counted PER PASS, so
an unclassified composite pass reads as thousands of containment pairs; once the
composites move, the residual is a handful of exact duplicates, which ARE a data
question.
