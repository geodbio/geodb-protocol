# Water results: non-detects, the detected and over-range flags, and units

How a non-detect water result is sent and stored, how a read says whether a water result was detected and whether it is over range (the same meaning as on an assay), and the units each field-measurement column is stored in.

### A non-detect is sent as a word or a "less than", never as a number

A laboratory's "not detected" water result is sent exactly as the lab
reported it: `ND`, `BDL`, or a "less than" such as `<0.5`. geoDB stores it as
a non-detect for you: the value becomes the sentinel `-1` and the
`qualifier` becomes `ND`. Never send `0` for a non-detect: it is stored as a
detected zero. A negative concentration is stored as a non-detect too; only a
signed parameter (ORP, Eh, temperature, an ion balance) keeps a real
negative. "N.D." or "N/D" can mean not detected or not determined: ask the
user which before sending (not detected: send ND; not determined: leave the
value out). A non-detect is never a
concentration: report it as "not detected", with the method's detection
limit when it is known, and never average it in with detected results.

The number inside a "less than" is not kept as the sample's own reporting
limit: the threshold geoDB knows is the method's detection limit. Keep the
laboratory's file when a diluted sample's own limit matters.

### Detected, not detected, over range

Each water result a read returns says whether the laboratory detected the
parameter (`detected`: false for a non-detect, whose value is the sentinel
`-1`) and whether it is over the calibration range (`above_det_limit`, the
same meaning as on an assay value: the laboratory qualified it `E`, so the
true value is at least the stored number). Its `value` is a decimal string:
parse it as a decimal, never as a float. A detected water value that is not
over range is a measurement.

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
