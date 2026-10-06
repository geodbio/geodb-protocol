# Custom columns: a project's own fields on its records

What a custom column is, where its values live, who may add, change or remove one, and why removing a column keeps its values.

### What a custom column is

A project can add its own fields to a record type (drill collars, samples,
lithology intervals, point samples, …) beyond the built-in ones: a permit
number, a core-box id, a "vein style" choice list. Each record type has at most
one set of custom columns per project (a **schema**), and each column has a
key (`field_name`: lowercase letters, digits and `_`), a label, a type (text,
number for whole numbers only, decimal, date, yes/no, choice, link, or
**calculated** from other columns), and optional rules (required, default,
minimum / maximum, the allowed choices). A point-sample column may apply to some sample types only.

A record's value for a column is stored on the record itself under the
column's key, so reading the record returns it beside the built-in fields.

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
