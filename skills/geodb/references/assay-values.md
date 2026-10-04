# Assay values: below detection, over range, and laboratory statuses

How a below-detection result is stored (the `-1` sentinel) and why it is never a grade, where detection limits live, what over-range values and lab statuses mean, when a substitute has already been applied, and how to spot a unit error.

### Below detection is a state, not a number

A laboratory's "less than the detection limit" result (`<0.005`, ND, BDL) is
stored as the numeric sentinel `-1`: not NULL, and not 0. It means the lab
measured less than the method can resolve, so there is no measured value.
Report it as "below detection", with the detection limit when one is known;
never as a grade, never as zero, never as a negative number, and never
averaged in with real results.

### Where a detection limit comes from

A below-detection value's threshold is resolved in two tiers. Most methods
have a FIXED limit per element, on the method's per-element row (`element`,
`detection_limit`, `upper_limit`, `units`), never on the assay row.
A FLOATING-limit method (`is_floating_dl`, e.g. photon assay) reports the
lab's "<X" threshold per sample instead, in the sample's
`detection_limit_per_sample`. So the limit is the per-sample value when the
method reports one, else the method's per-element limit; a read that carries
`detection_limit` beside each value has already resolved this. Only when
neither exists is the magnitude unknown: say so rather than guessing one.

### Over range is a floor, not a measurement

A result above the method's upper limit (`>10000`) is stored as that number
with `above_det_limit` set. The true value is AT LEAST that much: report it as
"over range (at least …)", and treat any average that includes it as a lower
bound.

### Laboratory statuses are not missing results

A cell reading insufficient sample, listed-not-received or not analysed is a
laboratory STATUS, not a measurement and not a gap: there is no value. The
first two are recorded on the assay as a status code; "not analysed" has no
status code, so it is counted (in the import's report) but never stamped on
the row. Never report those samples as missing results, and never fill them.

### Substitution is a project setting, applied once

The stored value of a below-detection result is always the sentinel, and a
raw (unmerged) read returns it as such. Merged grade tables and exports apply
the project's setting, which can differ per element: a fraction of the
detection limit (half by default; a custom fraction when the project set one),
the full detection limit, zero, or excluded (the value is left out, blank).
When neither a per-sample nor a per-element limit exists, a fraction of the
limit becomes 0: a merged 0 for such a sample is a stand-in, not a
measurement. So a value you read from a merged table or an export has ALREADY
been substituted, and is never substituted again. When you compute statistics
from raw values, use the project's substitute rather than dropping
below-detection samples (dropping them biases the low tail), unless the user
asks to exclude them, and say which you did.

### Read a value against its method before trusting its unit

A unit error does not look like an error: it moves every value by an exact
factor and leaves a tidy table. As units, 1 ppm = 1 g/t = 1000 ppb (so a
value in ppb is a thousand times the same value in ppm) and 1 % = 10 000 ppm.
Before any statistic, read
each element's values beside its method's detection limit and upper limit
(the method's per-element row, in the method's units) and beside the range
that element plausibly takes in rock:

- **The ppb-labelled-ppm signature:** values about a thousand times the
  element's usual range, whose smallest detected values sit near a thousand
  times the method's detection limit, with nothing between the limit and
  there (gold in ordinary drill core reading tens to thousands of "ppm").
  That is a ppb result stored under a ppm label.
- **The reverse, ppm stored as ppb:** most values at or below the detection
  limit and grades a thousand times too low for the rock.
- **Detected values below the method's own detection limit** (or, for a
  floating-limit method, below the sample's own limit): the limit or the unit
  is wrong for those rows.
- **One element on two methods disagreeing by about a thousand times** over
  the same samples: one of the two carries the wrong unit.
- **A percentage above 100, or ppm above a million:** physically impossible;
  a unit or decimal error.

When you see one, REPORT it: the element, the method, how many values, and
the evidence (the ratio to the detection limit, the range you expected).
Never rescale, relabel or drop the values yourself, and never compute a
statistic over the suspect rows as if they were right. The fix belongs to
the user (correct the method's unit, or re-import), because a unit corrected
in one answer is still wrong in every export and every other reader.
