# Water results: non-detects, units, and a flag that means the opposite of the assay flag

How a non-detect water result is sent and stored, why `above_det_limit` on a water result means DETECTED (not over range), and the units each field-measurement column is stored in.

### A non-detect is sent as a word or a "less than", never as a number

A laboratory's "not detected" water result is sent exactly as the lab
reported it: `ND`, `BDL`, or a "less than" such as `<0.5`. geoDB stores it as
a non-detect for you: the value becomes the sentinel `-1` and the
`qualifier` becomes `ND`. Never send `0` or `-1` yourself for a non-detect:
`0` is stored as a detected zero, and a bare `-1` is stored as a detected
negative number, so both read later as measurements. A non-detect is never a
concentration: report it as "not detected", with the method's detection
limit when it is known, and never average it in with detected results.

The number inside a "less than" is not kept as the sample's own reporting
limit: the threshold geoDB knows is the method's detection limit. Keep the
laboratory's file when a diluted sample's own limit matters.

### On a water result, `above_det_limit` means DETECTED

On a water result, `above_det_limit` is true when the parameter was detected
and false for a non-detect. That is the opposite reading from an assay value,
where the same name marks an OVER-RANGE result (the true value is at least
the stored number). Never read a water result through the assay meaning: a
detected water value is a measurement, not a floor.

### Units: each value in its method's unit; field readings in metres

A water result's `value` is in its method's unit for that parameter; send
the unit the method reports, and convert before sending rather than after.
The field measurements on a water sample are stored in metres:
`stream_depth`, `stream_width` and `water_level_depth` in metres,
`stream_velocity` in metres per second, `cross_sectional_area` in square
metres and `flow_rate` in cubic metres per second. Every read returns them
in those units whatever unit the project displays. Through the API a
record is taken in the same units, so convert feet before sending; a file
import converts for you, from the unit the import states (the project's
unless another is chosen). Leave `cross_sectional_area`
and `flow_rate` out and they are filled in when the sample is created:
depth × width, and velocity × depth × width × the correction factor
(0.80 unless sent). `field_temp` is stored as sent, in the project's
temperature unit (`temperature_units`: Celsius or Fahrenheit), and
`purge_volume` as sent, in litres on a metres project and gallons on a
feet project; read the project's units before reporting either.
`time_collected` is stored as a 24-hour clock time and read back as
`HH:MM:SS` (`14:21:00`); send `14:21` or `14:21:00` — "2:21 PM" is accepted
too, but send the 24-hour form.
