# "ODBC troubleshooting: when a modelling or GIS package doesn't show what geoDB holds"

Symptom by symptom, for packages connected through ODBC - a hole that doesn't draw, intervals flagged past the end of a hole, values that differ from the web - what to check in the data first, the usual cause when the data is fine, and what to tell the user. Also the order every table is served in.

### Check the data first, then the package

When a user says a connected modelling or GIS package doesn't show something
geoDB holds, read the record before suggesting anything about their software.
Say what you checked and what you found. If the record is fine, the cause is
almost always the package's own copy of the data, and the fix is on their side;
if the record is not fine, the fix is in geoDB, and the user decides it.

### A drill hole is missing, or doesn't draw

Typical report: the hole's surveys or intervals come through, but the hole is
not in the package's collar list, or nothing draws for it. Check, in order:

1. **The project.** An ODBC login serves the project currently selected for the
   user's account; the database name in the package's connection settings does
   not choose it. The hole must be in that project.
2. **The Trash.** A trashed hole is not served.
3. **Its location.** A collar needs a stored location and its coordinate
   system; a collar without one cannot be drawn. Read the location together
   with its coordinate system, never as bare numbers.
4. **Its purpose.** Underground workings (stopes, levels, raises and other
   workings) are left out of the drill-trace tables by default, so the package
   never draws them as drill holes.
5. **Its children.** The surveys and intervals belong to that collar, and no
   interval or sample runs deeper than the collar's total depth (a package
   flags that, and may drop the intervals).
6. **Its history.** When the location, or anything else the package needs, was
   added or corrected. The record history shows each change and when it was made.

**If all of that is fine, the package is probably holding an older copy.** Most
packages bring ODBC data in again in one of two ways: appending, which adds the
rows the package doesn't have yet and leaves the rows it already holds as they
were; or reloading (a fresh import), which replaces the package's copy with
what geoDB serves now. A hole the package first read before its location was
entered stays without one through every append, while its new surveys and
intervals keep attaching to it. Re-entering the record in geoDB cannot fix
that, because the package never reads that row again. Tell the user to reload
the drill hole data, or import into a fresh project, and then look for the
hole in the package's own error list.

Also tell them where to look: the tables are served sorted by hole name, so a
hole sits beside its neighbours in the package's import grid.

### Intervals flagged past the end of the hole

A package flags an interval whose bottom is deeper than the collar's total
depth. Compare the deepest interval in each logging table, and the deepest
sample, with the collar's total depth, and tell the user both numbers. Either
the total depth or the interval is wrong; the user knows which. Never change
either unasked. A short overrun usually doesn't hide the hole, but the package
may drop or flag the overrunning intervals.

### Values or columns differ from the web

What a package receives is shaped by settings, not only by the records:

- the coordinate frame and length units it is served (see odbc-settings);
- which logging or sampling set each table serves (see sets);
- whether assay values are combined, with below-detection values substituted,
  or raw (see assays);
- table and column names, order and visibility (see column-config).

A change to any of these reaches every connected package on its next refresh.
A change that adds or removes columns can stop a package reading a table it
read before, so ask about recent settings changes first.

### The order every table is served in

Collars come out sorted by hole name. Surveys, intervals and samples come out
in the same hole order, and within each hole from shallow to deep. A package
that sends its own sort gets that instead. If a user can't find a hole in a
long list, have them search for it or scroll on before concluding it is missing.
