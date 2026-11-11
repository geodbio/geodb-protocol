# Custom columns: a project's own fields on its records

What a custom column is, where its values live, who may add, change or remove one, and why removing a column keeps its values.

### What a custom column is

A project can add its own fields to a record type (drill collars, samples,
lithology intervals, point samples, …) beyond the built-in ones: a permit
number, a core-box id, a "vein style" choice list. Each record type has at most
one set of custom columns per project (a **schema**), and each column has a
key (`field_name`: lowercase letters, digits and `_`), a label, a type (text,
number for whole numbers only, decimal, date, yes/no, choice, **multichoice**
(pick several from the list), link, or **calculated** from other columns), and
optional rules (required, default, minimum / maximum, the allowed choices). A
point-sample column may apply to some sample types only.

A column may carry a **unit** (`unit`: "g", "%", "ppm"). It is a label shown
after the column's name ("Wet Wt (g)"); values are stored as entered and never
converted. A logging sheet's "Wet Wt (g)" is the label `Wet Wt` with the unit
`g`.

A record's value for a column is stored on the record itself under the
column's key, so reading the record returns it beside the built-in fields. A
multichoice value is a list of the chosen values. Sent as text, the values are
separated by `;` ("Pyrite; Galena"); each must be one of the column's choices
(a value that is not is refused, and the list is never widened by a write).
ODBC and the exports give a multichoice value as one text cell, its values
separated by `; `.

### Who may change them

Adding, changing, reordering or removing columns is a project setting: it
needs the project-settings permission (owners, managers and project admins
hold it). Anyone who may add records may fill the columns in.

### What removing a column does

Removing a column takes it off forms, tables, exports and every read, the
API's included. **The values already stored on records are kept** (hidden, not
erased), so restoring the column (or undoing the removal) brings it back
exactly as it was, values included. A column that holds values
cannot be renamed (the values are stored under its key); changing its type
converts the stored values where it can and keeps the rest as they are, and
dropping a choice that records use leaves those records' value in place (or
moves them to a choice you name). Both of those rewrite stored values, so ask
the user first.

Every export carries every live custom column, empty where a record has no
value, and never a removed one.

### Changing custom columns through the API

The model is `CustomFieldSchema` on the records endpoint, with the intents
create, update, retract and restore; read its describe contract first. A
schema is the parent and its columns are its `fields`. On an update each
column carries an `action` (add, change, remove, or restore to bring one
removed column back with its values) and is named by its `field_name` or its
`id`; `order` lists every column once, in the new order. Run every change as
a dry run first, tell the user what it will do, and send it for real only
after they agree. Every write can be undone, but an undo reverses the whole
write: to take back only part of one, send a new update instead.

### Custom drill tables: a downhole table of the project's own

A custom drill table (`CustomIntervalType` on the records endpoint) is a
downhole log the built-in families do not cover: ONE main column, either a
list of values (categorical: an oxidation state, a weathering grade) or a
number with a unit (numeric: a density, a wavelength), plus any extra columns,
which are custom columns scoped to that table alone. A table logs INTERVAL
rows (from / to) or POINT rows (one depth). Its rows may sit in logging sets
of its own (a set belongs to one table, or to none). Every live, active table
is its own ODBC table `ci_<code>` and its own export (POST exports/ with
model `drill_custom_intervals` and `custom_table` = its code or id); the mixed
`drill_custom_intervals` table keeps every table's rows for older readers.

Setting one up: read the describe contract of `CustomIntervalType`, send the create
as a dry run, show the user the table it would make (name, main column,
depths, values, columns, sets, Quick Log tab) and send it for real only after
their yes; then load rows into it as `DrillCustomInterval` records naming the
table (`type`). Renaming keeps the code, so the ODBC table and the Quick Log
tab keep their names. The main column's mode and the depth mode are fixed once
the table holds rows (`config_locked`): a new shape is a new table. A value
rows still carry is never removed, and a table live rows still use is never
retracted (`record_in_use`). Every write has its Undo.

A table's column takes `visible` false to be hidden from its grid, Quick Log
tab, row form, export and ODBC table (never a required one); its label is
its `display_name` and its place the `order`. A table's own logging sets are
made with it (`sets`), and one may be named as its `default_set` in the same
record. To rebuild a customer's whole logging template, see the guide topic
logging-templates.
