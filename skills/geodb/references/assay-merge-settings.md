# Assay merge settings: how several assays of one element become one value

What merge settings control (merged values, units, below-detection handling, export columns), the project default, who may change them, and what removing them does.

### What merge settings control

A sample is often assayed for the same element more than once (two methods,
a re-assay, an over-limit finish). Merge settings decide which single value a
merged read, an export or an ODBC table shows: the highest, the lowest or the
average; the units it is converted to; what a below-detection result becomes
(a fraction of the detection limit, or left out); and whether exports carry
one column per element, one per method, or both. Per-element overrides change
the strategy or units for one element (for example, the highest gold but the
average copper). A project can hold several sets of merge settings; ONE is the
project default, used by exports and ODBC unless a read names another.

### Who may change them

Creating merge settings needs the permission to add data; changing or removing
them needs the permission to edit all data, or to have created them. The
project default is different: making settings the default, or changing the
default's own settings, changes every export and ODBC read for everyone, so it
needs the company-settings permission (owners, and managers given it).

### What removing them does

Removed merge settings go to the Trash and can be restored. The project's
built-in "Default Merge Settings" are never removed, and settings an assay
range configuration uses cannot be removed until that configuration points at
other settings.

### Changing them through the API

On the records endpoint these settings are the merge-settings model that
grant-context lists under `writes.config_models`, with the intents create,
update, retract and restore; read its describe contract first. Its
per-element overrides are its `element_overrides` — the same key a read
returns them under: on an update each carries an `action` (add, change or
remove) and is named by its `id` or its `element`, so a read override can be
sent back with an action. A digestion or finish filter is accepted by id or by
code; reads give both (`digestion_filter` and `digestion_filter_code`). Making settings the project default
is an update with `is_project_default` true. Each read row lists, under
`assay_configs`, the range configurations that use the settings; their ids are
what a merged sample read takes as `assay_config_id`. Run every change as a dry
run first, tell the user what it will change, and send it for real only after
they agree. Every write can be undone.
