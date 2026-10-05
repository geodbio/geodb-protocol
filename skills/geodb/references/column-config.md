# Column configuration: how a record type's columns are named, ordered and shown

What a column configuration controls (grids, exports, ODBC), who may change it, and what resetting it does.

### What a column configuration controls

For each record type in a project (drill collars, samples, lithology
intervals, …) one configuration says what each column is called, in what
order the columns come, and which are hidden. It applies everywhere the
records are shown or sent out: the grids in the app, every export
(CSV, Excel, GeoPackage, KML) and the ODBC tables external tools read, which
can also take a different table name (some modelling tools expect their own
names, such as "COLLAR"). A record type with no configuration shows its
default columns, all visible. Columns come from the record type itself and
from the project's custom columns; a configuration renames, hides or orders
them, it never invents one. Columns a record cannot be saved without cannot
be hidden.

### Who may change it

Changing the column configuration is a project setting: it needs the
project-settings permission (owners, managers and project admins). Because it
changes what every person, export and connected tool sees, say so before
changing it, and especially before renaming an ODBC table: a tool that read
the old name stops finding it.

### What resetting does

Resetting a configuration returns the record type to its default columns.
The configuration is kept in the Trash, so restoring it (or undoing the
reset) brings back the names, order and hidden columns exactly as they were.

### Changing it through the API

The model is `ColumnConfiguration` on the records endpoint, with the intents
create, update, retract (back to the defaults) and restore; read its describe
contract first. Its columns are its `entries`: each change carries `action`
change with the column's `field_name` and a new `display_name` or `visible`;
`order` lists every column once, in the new order, and `table_display_name`
sets the ODBC table name. Run every change as a dry run first, tell the user
what it will do, and send it for real only after they agree. Every write can
be undone.
