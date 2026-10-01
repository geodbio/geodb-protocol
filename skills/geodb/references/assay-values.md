# Assay values: below detection, over range, and laboratory statuses

How a below-detection result is stored (the `-1` sentinel) and why it is never a grade, where detection limits live, what over-range values and lab statuses mean, and when a substitute has already been applied.

### Below detection is a state, not a number

A laboratory's "less than the detection limit" result (`<0.005`, ND, BDL) is
stored as the numeric sentinel `-1`: not NULL, and not 0. It means the lab
measured less than the method can resolve, so there is no measured value.
Report it as "below detection", with the detection limit when one is known;
never as a grade, never as zero, never as a negative number, and never
averaged in with real results.

### Where a detection limit comes from

A below-detection value's threshold is resolved in two tiers. Most methods
have a FIXED limit per element, on the method's per-element row (`MethodUnit`:
`element`, `detection_limit`, `upper_limit`, `units`), never on the assay row.
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
