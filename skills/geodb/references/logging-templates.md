# Logging templates: recreating a customer's own logging sheets in a project

How a multi-tab logging template (tables, columns, pick lists, units, required fields) maps onto a project's built-in tables, custom columns and custom drill tables, and how to carry it over with nothing lost or invented.

### What a logging template holds

A logging template is a spreadsheet a team logs core into: usually one tab per
table (collars, lithology, alteration, structure, a density or redox log …),
each tab's header row naming its columns. Everything that defines the table
can sit outside the data rows, so read the WHOLE file before deciding
anything:

- every tab, hidden ones included: pick lists usually live on a hidden
  "Lists" or "Lookups" tab and reach a column through a drop-down (data
  validation) rule;
- every header row: a second header row, or the header text itself, often
  carries the unit ("Wet Wt (g)", "Recovery %") or a required marker (`*`,
  bold, "required");
- cell notes and comments, which often say what a code means;
- validation rules (allowed range, whole numbers only) and number formats;
- formulas: a computed column ("SG = Dry / (Dry - Wet)") is a definition, not
  data.

### Mapping each tab onto the project

**A tab that matches a built-in table** (collars, surveys, lithology,
alteration, mineralization, veins, structures, RQD, samples, QC samples) goes
to that table. Its columns that the built-in table already has map onto them;
every other column becomes a custom column on that record type. The built-in
columns' labels, order and visibility are a column configuration. A built-in
column fed by a pick list (lithology codes, alteration types, minerals,
textures) takes its values from the project's own lists: add the template's
codes there, exactly as spelt, with what each means as its description.

**Any other tab** (specific gravity, redox, weathering, magnetic
susceptibility, point load, a vein log the built-in table does not fit …) is a
custom drill table of its own. Decide, per tab:

- **Interval or point.** From / To columns make an interval table; a single
  depth column ("Depth", "At (m)") makes a point table. The hole, from, to and
  depth columns are the table's own fixed columns, never extra columns.
- **The main column.** Every table has ONE main column: the value the log is
  about, drawn on the strip log and in 3D. A pick list of states (oxide /
  transition / fresh) is a categorical main column with those values; one
  measured number is a numeric main column with its unit. When a tab measures
  several numbers to produce one result (dry and wet weights giving a density),
  the main column is the RESULT the geologist reads, and the inputs are extra
  columns. Never pick a column only because it comes first. A `*` on the main
  column ("Redox state*") makes it required: `main_required` true.
- **Its extra columns**, each with the settings below.

**Every column, carried over exactly:**

- its label as the template shows it, the unit apart: "Wet Wt (g)" is the
  label `display_name` "Wet Wt" with `unit` "g" (a unit is a label only;
  values are never converted); and a short lowercase key (`field_name`)
  made from it;
- its type: text, whole number, decimal, date, yes/no, a pick list (choice),
  a pick-SEVERAL list (multi-choice: a cell holding "quartz; pyrite") or a
  link — a drop-down that accepts several values is never flattened to one;
- the pick list's values, spelt and ordered as in the template;
- required or not, its default, its minimum and maximum, its help text (the
  header note);
- its place in the column order, and whether it is shown: a column the
  template hides is a hidden column, never a dropped one.

If the template keeps separate passes or loggers apart (a second pass, a
re-log), each is a logging set of that table.

### Carrying it over with nothing lost or invented

1. Propose the WHOLE structure first, as one table the user can read: each
   tab and where it goes (a built-in table, or a new custom drill table with
   its main column and depth kind), then every column with its label, type,
   unit, pick list, required flag, default, range, order and visibility. Ask
   once; build only after the user agrees.
2. Build it as few changes as possible, each shown as a dry run first: the
   pick-list entries, the custom drill tables (several in one change), the
   custom columns, then the column configurations.
3. Read back what the project now holds and compare it with the template,
   column by column. Report every difference, and everything that could not be
   carried exactly, in plain words. Nothing is silently renamed, merged,
   dropped or re-typed.
4. **Formulas are asked about, never invented.** For a computed column, ask
   the user what it means and how it is worked out; record it as they answer,
   or keep its inputs as columns and say the result is not computed yet.
   Never guess a formula from a column's name or its numbers.
5. A label or code the template spells oddly stays as spelt: ask before
   correcting it.

### Setting a template up through the API

Read the describe contract of `CustomIntervalType`, `CustomFieldSchema`,
`ColumnConfiguration` and each pick-list catalog (e.g. `Lithology`) first.
Then, after the user has agreed the proposed structure, write through the
records endpoint:

- **Pick lists of built-in columns:** `create` on the catalog (e.g.
  `Lithology`), one record per entry with its key and description. An entry
  the project already has answers "unchanged" and is left as it is.
- **Custom drill tables:** `create` on `CustomIntervalType`, one record per
  table (several tables in one request): its name, `mode` (the main column:
  categorical with its `values`, or numeric with its `unit`), `depth_mode`,
  `main_required`,
  and its `columns` (each with `field_name`, `display_name`, `unit`,
  `field_type` (`multichoice` for a pick-several column), `required`,
  `choices`, `default_value`, `min_value`, `max_value`, `help_text`, and
  `visible` false for a hidden one), in the template's column order. Its logging sets go in `sets`, and one of them may be named as its
  `default_set` in the same record.
- **Extra columns on built-in tables:** `create` (or `update` with
  `"action": "add"`) on `CustomFieldSchema`, one record per record type.
- **Labels, order and visibility of built-in columns:** `ColumnConfiguration`.

A configuration request carries at most 20 records (more is refused
`batch_too_large`: split the setup into several requests); a catalog request
carries up to 500 entries. Send each request as a dry run, show the user what
it will make, then send it for real. Each written row's `result` is the
record as stored (a custom drill table's result lists every column with its
settings and whether it is shown): compare it with the template and report
the differences. Every write can be undone as a whole.
