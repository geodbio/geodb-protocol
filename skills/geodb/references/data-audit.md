# Auditing a project's data: what to read, in what order, and whose each problem is

How to audit a project: geoDB's own findings first, then the QC verdicts, then name collisions, then tables; the raw-data signatures of the common problems (feet stored as metres, half-detection-limit values, capped values, lab status behind its results, empty holes); and how to say who should fix each one.

### How to audit a project

Asked to audit a project ("what's wrong with our data?", "anything that
doesn't add up?"), read in this order and report what geoDB says before
analysing anything yourself:

1. **geoDB's project-health findings.** geoDB checks the project's stored data
   itself and returns findings, never repairs: each has a severity, a count,
   up to ten examples (record ids and the customer's own names and numbers),
   who made the affected rows and whose the fix is. A check that could not run
   is named; its silence is not a clean result.
2. **The QC verdicts and the reference materials.** The findings do not judge
   QC, so every audit report carries its own QC section.
3. **Sample names held by more than one kind of sample** (drill, surface, QC).
4. **Only then pull whole tables**, for what the findings do not already
   answer: one table per question, never everything at once.

Report each finding with its evidence (the count and a few examples) and its
owner. Name the coordinate system of every coordinate you quote. geoDB stores
a below-detection result as `-1`: report it as below detection with its
detection limit, never as a number.

### Whose problem is it? Attribute before you recommend

Every finding carries `owner` and `origin`.

- `origin` counts who made the affected rows, as a ROLE: `geodb_staff` (a
  geoDB staff load), `member` (the customer's own people, field app
  included), `connector` (a connected AI or client) or `unknown`. It never
  names a person, and neither do you: never guess who did it.
- Rows carry `origin` too, not only findings: each collar, survey, sample and
  logging row says who made it, in the same words.
- `owner` `geodb`: a known geoDB product gap, or rows that mostly came from a
  geoDB staff load. Report it as **geoDB's to fix: tell geoDB support**. Never
  hand it to the user as their to-do, and never ask the user about it (whether
  a staff-loaded hole exists, say): geoDB checks its own load.
- `owner` `customer`: a data-entry shape on rows the customer's side made.
  Theirs to correct, with the remedy the finding names.
- `owner` `ask`: it could be either. Ask before calling it an error. Value
  signatures (half-detection-limit values, a pile at the upper limit) are
  always `ask`, even from a geoDB staff load: the customer's file carried them.

When you spot a problem in raw data yourself, ask the same question: did a
geoDB import or a staff load make it? If you cannot tell, say so and ask.

### Collars

- **Dip** lies in −90..90 degrees (negative points down, positive is an
  overhead hole) and **azimuth** in 0..360. geoDB refuses a new value outside
  those ranges, but older rows can hold one: a dip of −91 or −92 is a typo or
  an inclination written where a dip belongs.
- **A positive collar dip on a hole whose surveys dip negative** is a sign
  convention question, not an error: ask which convention the collar used.
- **Empty holes**: no location, no total depth and nothing logged. Ask whether
  they exist, unless a geoDB staff load made them: then they are geoDB's to
  clean up.
- **Placeholder holes**: no location and no total depth, but rows hang off
  them (each example lists what: spectral intervals, photos, samples). Give
  each a location and depth, or, when its name is a second spelling of a real
  hole, move its rows onto that hole.
- A collar coordinate is the original as surveyed, in the record's own
  coordinate system (usually easting and northing): quote it with that system.

### Surveys

Survey dips and azimuths share the collar's ranges. Some survey tools write an
overhead hole's dip on a 0–360 scale (327.5 meaning −32.5); geoDB folds that on
import, so a stored survey dip outside −90..90 is a data-entry error, often an
azimuth in the dip column or a slipped decimal. A hole with neither surveys nor
a collar dip and azimuth cannot be traced; one traced straight from its collar
is fine until surveys exist. Stations far apart (over 50 m) are interpolated
across the gap.

### Depths and units: one hole in feet, stored as metres

geoDB stores every depth in metres. A file in feet loaded as metres has one
signature: **a hole whose intervals run about 3.28 times its total depth**
(logging to 1140 m in a hole drilled to 366 m, which is 1200 ft). It happens
**per hole**, not per set: one hole of a set can be wrong while the rest are
right, so name the hole. The reverse, intervals stopping near 0.3048 times the
total depth while other logging goes deeper, suggests metres entered as feet,
but a partly logged hole looks the same: ask. When several kinds of interval
all run past the same total depth, the data cannot say which is wrong: the
total depth, or every interval of the hole entered in feet (likelier near
3.28 times). Ask, with both fixes. Never convert on a guess: convert that
hole's rows from the original file.

### Intervals

Within one set, in one hole, intervals must not overlap; across sets anything
goes, and alteration, vein and mineralization rows overlap by design (one
mineral or type per row). Two sampling passes over the same core (composites
over bags) belong in separate sample sets, not one. A gap is usually unlogged
or unsampled core: ask before calling it missing data. An interval deeper than
the hole's total depth means one of the two is wrong.

### Lab status behind the results

A sample with a linked result has been analysed. **Samples holding results
but not marked Analyzed** (still Collected or Submitted) are a geoDB import
gap, not something the customer forgot: report them as geoDB's to fix. Count
QC samples as well as drill and surface samples. The reverse, samples marked
Analyzed with no result linked, is worth one question: were the results never
loaded, unlinked by a rejected certificate, or deleted?

### Sample names

A sample number names one bag. **One number on drill samples of more than one
hole** means a result loaded under it cannot tell the holes apart: ask which
hole each belongs to. One name on more than one kind of sample (a drill sample
and a QC sample, say) is reported on its own, with the names and counts.

### Assay values that are not measurements

- **Values exactly half the method's detection limit**, across a certificate,
  are a substitution done before the data reached geoDB: below-detection
  results stored as numbers. Report them by element and say when gold is among
  them (it moves an average most). Treat them as below detection, and never
  substitute them a second time.
- **A pile of values exactly on the method's upper limit, without the
  over-range flag**, are capped results: each is a floor (at least the limit),
  usually re-assayed by an ore-grade method. Never average them as grades.
- `-1` is geoDB's below-detection marker, never a value: report it as below
  detection, with the detection limit.
- A merged (combined) table converts each element to one unit: read the
  `units` beside each value before calling a unit mislabelled.

### QC is a section of every audit

The project findings check QC integrity only: standards with no reference
material, duplicates with no original (or sharing the original's result), QC
samples with no type or no result. They do **not** judge QC. Read geoDB's
verdicts (standards, blanks and duplicates: pass, warn and fail, per
certificate and per reference material) and report them in their own section,
naming any certificate a review rejected or superseded. Quote the verdicts'
own counts of fails, warns and duplicates; never recount them yourself. An audit without a QC
section is incomplete, even when the findings say nothing about QC.

### Sets

Name the sets that are empty, or whose rows are all in the Trash: an empty set
is usually left over from a load, and a set whose rows wait in the Trash cannot
be removed until they are restored or purged on the web. Say which set every
finding came from.

**The audit reads, in order.** 1. `project-health/`, narrowed by `owner`,
`severity` or `code` when it is long; each finding's `see_guide` names the
section of this topic that explains it. 2. `qaqc-verdicts/` (grouped by
standard: one row per reference material) and `qaqc-standards/`. 3.
`sample-name-collisions/`, and `sets/` for the sets. 4. Exports, only for what
is left: at most two building at once. While an export answers pending, read
its status at `exports/<job_id>/` (progress, rows done) every Retry-After
seconds, never the download link.
