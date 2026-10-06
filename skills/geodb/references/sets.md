# Sets: several versions of the same downhole data, side by side

What a set is, the one overlap rule, default vs active sets, and why an assistant must ask which set before it writes an interval or a sample.

### What a set is

A **set** is a named version of one kind of downhole data in a project: one
logging pass, one interpretation, or one sampling pass. Eight families have
sets: lithology, alteration, mineralization, veins, RQD, spectral, custom
intervals, and **sample sets**. A sample set is a sampling PASS (for example
10-ft lab composites sitting over the 5-ft bags, with their own sample ids and
certificates), not a list of members. Structures have no sets.

Every interval and every sample belongs to exactly one set of its family. A
row that names no set belongs to the project's default set.

### The one rule

**Within one set, in one hole, intervals may not overlap. Across sets, anything
goes.** So two geologists' logs of the same hole, or a geologist's log and an
interpretation derived from pXRF, live side by side as two sets over the same
depths, and neither changes the other. Two sets overlapping is normal; two
intervals overlapping inside one set is an error the data will refuse.

### Default and active

Each project has a **default set** per family: what maps, sections and
people see unless they choose otherwise. Each person has an **active set** per
family that they view and log into; it starts at the project default. Samples
and the logging families can also have a project **export set**: an API export
reads the export set, else the default set; the ODBC sample table reads the
export set, else the default; the ODBC logging tables (lithology, alteration,
mineralization, veins, RQD) read the export set, else EVERY set. Making a set
the project default changes what EVERYONE on the project sees.

### Who owns a set, and how it was made

Every set has a creator. People edit their own sets; the project's default set
is managed by the project's managers. A set is `active` or `archived`.
Lithology, alteration, custom-interval and sample sets record in `source` how
they were made (hand-logged or software-derived); elsewhere the NAME must say it.

### Reading sets

Every interval and sample you read names its set. When a project holds
several sets of a kind, ask which one the user means, or whether they want
all; **never merge them**: report per set, and say which set every answer came
from.

### Before any interval or sample write: establish the set, and ASK if the user hasn't said

Offer the real choices, listing the project's sets with their creator, row and
hole counts, date, and whether each is the default:

1. **add to an existing set** (which one?);
2. **create a new set** (what to call it?), which changes nothing anyone else
   sees until it is promoted;
3. **correct rows in an existing set** (an update: audited, but with no
   one-step restore today — say so first).

For a derived interpretation (pXRF → lithology, a re-log, a model's output),
suggest option 2. A new set is nobody's active set nor the default until chosen:
each person picks their active set; a project manager sets the default (what
everyone sees) — never without the user's explicit yes.

⛔ **Never** pick a set on the user's behalf, merge sets, or write a derived
interpretation into someone's logged set.

**Sets.** Downhole intervals and samples live in named sets (one logging pass,
interpretation or sampling pass each; eight families; structures have none).
Within one set in one hole intervals may not overlap; across sets anything
goes. Each project has a default set per family (what everyone sees); each
person an active set. When a project holds several sets of a kind, ask which
one (or all); never merge sets; say which set every answer came from.

Before any interval or sample write, ask which set if the user hasn't
said, offering: add to an existing set · create a new one · correct rows in
one. Derived interpretations go in a new set. Making a set the default needs
the user's explicit yes.

An EMPTY set the user no longer wants can be retracted, by its id or name,
after a dry run they have seen; Undo brings it back. A set that still holds
rows is never removed or merged (the refusal gives the count), the project's
default set never goes, and a person removes only a set they created. Rows in
the Trash still belong to their set: the set reads count `rows_live` and
`rows_in_trash`, and a set whose rows are ALL in the Trash is removed only
after they are purged on the web (the refusal says so).
