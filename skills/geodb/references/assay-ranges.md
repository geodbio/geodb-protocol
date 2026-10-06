# Assay range configurations: colouring and compositing one element's values

What a range configuration controls (colours and sizes on maps, sections and 3D; optional compositing), who may change it, and what removing it does.

### What a range configuration controls

A range configuration colours one element's values on maps, cross-sections
and the 3D viewer: a list of value ranges, each with a colour, a marker size
and a label, plus a colour for values outside every range. It reads values
through one set of merge settings (so units and the duplicate-assay rule are
set there), and it can composite samples to a fixed length first. Ranges in
one configuration may not overlap. Its id is also how a merged or composited
sample read names the configuration to apply.

### Who may change it

Creating a configuration needs the permission to add data; changing or
removing one needs the permission to edit all data, or to have created it.

### What removing it does

A removed configuration goes to the Trash with its ranges and comes back
whole with a restore. Removing one range from a configuration also keeps that
range restorable.

### Changing it through the API

The model is `AssayRangeConfiguration` on the records endpoint, with the
intents create, update, retract and restore; read its describe contract first.
Its ranges are its `ranges` — the same key a read returns them under: on a
create a list; on an update each carries an `action` (add, change or remove),
and change or remove name the range by its `id`, so a read range can be sent
back with an action. Run every change as a dry run first, tell the user what it will change,
and send it for real only after they agree. Every write can be undone.
