# Assays: merged or raw, how geoDB combines them, and when to trust a number

Read this first for any assay question. Which reads give the laboratory's own numbers and which give geoDB's combined ones, how to tell them apart, which merge settings combined them (strategy, units, below-detection substitute, over range), values outside their method's limits, results whose sample is gone, a sample number two certificates share (re-assay or reused tag), the traps of lab file layouts, and how QC verdicts are reached.

### Two kinds of assay number: raw and combined

geoDB keeps every laboratory result as it was reported: one value per
sample, element and method, with its own unit, its method's detection and
upper limits, the certificate that reported it, and its flags (below
detection, over range). That is the RAW table, and it is the only place a
repeat assay, a second laboratory or an ore-grade re-run is visible as its
own row.

A plain sample read is raw too: each sample names its assay (`assay_id`),
and `expand=assay` returns that laboratory record (every value per method,
the below-detection sentinel `-1`, the flags). A sample read that names
merge settings (`merge_settings_id`, `assay_config_id` or `merge_assays=true`)
shows a COMBINED value instead: one number per sample and element, produced
by those merge settings. Exports and ODBC tables follow the settings'
`merge_mode`: one combined column per element (merged), one column per method
as reported (unmerged; below detection is still substituted there), or both.
A combined value has already been through four decisions: which of several
results wins (the strategy), what unit it is converted to, what a
below-detection result becomes, and what an over-range result becomes; a
result from a laboratory job its QAQC review rejected never enters it. It
carries none of the raw flags.

So before quoting a number, know which kind it is. A combined value answers
"what grade does the project use"; a raw value answers "what did the
laboratory report". When two results for one sample disagree, or when a
value sits exactly at a method's limit, go to the raw rows before you
conclude anything.

### Which settings combined a value

A project holds one or more sets of merge settings; one is the project
default, which exports and ODBC use. A combined read uses the default unless
it names other settings (directly, or through a colour scheme that names
them), and every combined answer STATES the settings it applied: which ones,
the strategy, the units, what below detection became and what over range
became. Each set of settings says:

- **strategy**, per element or for all: `high` (the highest result wins),
  `low` (the lowest) or `average` (the mean of the results). The strategy is
  the only thing that decides between two laboratories, two methods or a
  repeat: there is no method ranking, no "which method wins" order and no
  preference for the newer certificate.
- **units**, per element or for all: every result is converted to this unit
  before the strategy compares them (ppm, ppb, % or oz/t).
- **below detection**: when on, a below-detection result becomes a fraction
  of its detection limit (half by default); when off, it is left out.
- **per-element overrides**, which change the strategy or unit for one
  element (for example the highest gold but the average copper), and can
  restrict which results count for that element to one digestion or finish
  (for example only fire-assay gold); results by other methods are then left
  out of that element's combined value.

A value's `source_type` says laboratory (`lab`) or field (portable) XRF
(`field_xrf`), and a combined value never blends the two: merge settings
combine results within one source. Reads that can carry field XRF return it
beside laboratory values, labelled, and take `source_type` to read one
source; the sample-table exports and the ODBC tables still combine
laboratory results only. A result
whose unit cannot be converted to the target unit is left out of every
combined value.

Combined values are labelled in the units they were converted to, element
by element (an override's units where it has one). When you report a
combined value, say which settings produced it and, where there were several
results, which rule picked the one shown.

### Repeat results: when the strategy changes the answer

A sample assayed twice (a second laboratory, an umpire check, a re-assay, a
fire assay and an ore-grade finish) has several raw results for one element.
The combined value depends on the strategy: with results of 2.45 and 1.62,
`high` gives 2.45, `average` 2.035 and `low` 1.62, and a hole's best interval
can change with it. When a question turns on such a sample, give the raw
results, the laboratories and certificates that reported them, the rule the
project applies, and what the other rules would give. Never pick one result
yourself and present it as geoDB's.

### One sample number, two samples: re-assay or reused tag

geoDB keeps one assay record per sample name in a project, and a result
reaches its sample by that name. Sample numbers get reused: one tag book
serves a drill hole's intervals and a surface program, a book is restarted
years later, a laboratory QC insert takes a numbered slot inside a drill
sequence. A later certificate carrying a reused number lands on the earlier
sample's record, so one record holds two rocks, and the name links it to
every sample that carries it.

A second certificate on one sample is often right (a re-assay, an umpire or
second laboratory). To tell which it is, compare:

- **The values both certificates hold.** A re-assay of the same material
  tracks: most shared elements agree within tens of percent. Two different
  rocks rarely do.
- **The dates.** A surface sample collected after the first certificate was
  issued cannot be its re-assay.
- **The kind of sample.** A drill interval and a surface sample, or a QC
  insert and a routine sample, sharing one number are two samples.
- **The weights.** Two samples rarely weigh the same.

When geoDB reports a result landing on another certificate's sample, or a
sample name carried by more than one kind of sample, stop: show the user the
evidence and ask which it is. Never decide it yourself, in either direction.
A reused number is fixed by telling the two samples apart (usually renaming
one program's samples and results), never by merging them.

### Lab file layouts: the traps when reading a report

Read each laboratory file into one row per sample, element and method, and
watch for these layouts:

- **Trailing metadata columns are not elements.** A flat export often ends
  in columns such as certificate, comments, date finalized or lab name.
- **Lab duplicates are QC.** A row like `S-101-X` or `S-101 DUP` is the
  laboratory's duplicate of sample `S-101`: map it as lab QC with that parent.
- **A gravimetric over-limit column is its own method.** A column like
  "Ag (G)" is a separate method from the column it re-runs.
- **A limit printed in another unit is converted, never copied.** A
  detection limit in oz/t beside values in ppm must be converted first.
- **A re-run column labelled by grade, not by method** (for example "ORE
  GRADE"): ask the user which of the laboratory's method codes it is.
- **A status code in the weight column means no weight.** SNR there means
  the sample was not received.
- **Dates:** parse ISO dates (YYYY-MM-DD) as they are, never day-first, then
  read your own table back against the report before you write.

### Over range survives only in the raw rows

An over-range result is stored as the method's upper limit with the
over-range flag, and is a floor: the true value is at least that much. A
combined value does not carry the flag, so a combined value that equals a
method's upper limit may be a floor. Check the raw row, report it as "at
least …", treat any average that includes it as a lower bound, and say
whether an ore-grade or gravimetric re-assay exists. When none does, the
sample needs one before the grade is used.

### "N.D." can mean two things: ask

`ND`, `BDL`, "not detected" and a "less than" (`<0.005`) are below detection
and are stored as the below-detection sentinel. `N.D.` or `N/D` is different:
laboratories use it both for "not detected" and for "not determined" (not
analysed). Before you send or import a file that uses it, ask the user which
the laboratory means. Not detected: send it as BDL. Not determined: leave the
value out (it is not a result). Never guess either way, and never send 0 or a
fraction of the detection limit for it. A write that sends "N.D." as it is
is refused, per row, as ambiguous (`ambiguous_nd`).

### Every value against its method's limits

Each raw value carries its method's detection limit and upper limit, and
geoDB flags a value outside them when it is read: a plain number above the
upper limit (not marked over range), or a detected value below the detection
limit. Either is outside what the method can measure: the result, the unit or
the limits are wrong. Report it with the limit it breaks, and prefer an
ore-grade result for the same sample when one exists. A method with no limits
on file cannot be checked: say so rather than assume the value is fine. When
below-detection results have no detection limit at all, combined reads and
exports name those method and element pairs: ask the user for the
laboratory's limits, never guess them.

### Results whose sample is gone or not there yet

An assay is kept when its sample is moved to the Trash (it links again if the
sample is restored), but it no longer belongs to any hole: geoDB leaves it
out of what reads return by default and counts it as withheld, and a reader
that asks for it sees it marked. Never put such a result in a statistic or
an intercept. A result whose sample name matches no sample at all (one
waiting for its sample to be imported) has no hole and no depth: report it
as unlinked, never place it in a hole.

### QC verdicts are geoDB's, judged against the project's own rules

Whether a standard, blank or duplicate passed is geoDB's verdict, reached
against the project's QC configuration (certified values for standards,
warning limits for blanks, precision limits for duplicates). A QC sample is
typed by its QC type, never by its sample type. A blank is judged per
element against that element's warning limit. With no limit, a blank the
laboratory reported below detection passes (it is clean), while a blank with
a detected value cannot be judged and its verdict is unknown. Quote the
verdicts, say which
elements could not be judged and why, and when a failure has another
explanation in the data (a unit error on the same certificate, a swapped
bag), say so beside the verdict rather than changing it.

### Raw and combined reads on the API

- **Raw:** `assay-results/` (one row per sample, element and method: `value`
  as a decimal string, `units`, `detection_limit`, `upper_limit`,
  `below_detection`, `above_det_limit`, the method, certificate and
  laboratory ids, `sample_status`, `data_warnings` such as
  `above_upper_limit_as_value` / `below_detection_limit_as_value`; `element=`
  filters), or the `assay_results` export for a whole project. The
  below-detection sentinel `-1` is kept. Assays whose sample is in the Trash
  are withheld (`withheld.sample_trashed`); `include_trashed_samples=true`
  returns them marked.
- **Combined:** `drill-samples/` and `point-samples/` merged by
  `merge_settings_id` (the settings by id), `assay_config_id` (a colour
  scheme's settings) or `merge_assays=true` (the project default): each
  element marked `merged`, one value per element (a JSON number) in its true
  units, and the answer's `merge_settings` stating what was applied (with
  `no_detection_limit` when below-detection results had no limit);
  `drill-samples/composited/` (each composite's `coverage`), the
  `drill_samples` / `point_samples` exports (their column headers name each
  element's units and strategy; the settings' `merge_mode` shapes the columns)
  and the ODBC tables.
- **Settings:** `assay-merge-settings/` lists each set (strategy, units,
  below-detection handling, `merge_mode`, `is_project_default`, per-element
  overrides, `assay_configs`: the colour schemes that use it).
- **Limits:** `methods/` and `detection-limits/`.
- **QC:** `qaqc-verdicts/` (never recompute a verdict).
