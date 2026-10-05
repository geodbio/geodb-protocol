# Projects: creating one, its coordinate system, its states, and the Trash

Which company a new project belongs to (always ask), setting up the project's coordinate system, what Active, Holding and Frozen each stop, and why deleting a project is reversible.

A project belongs to exactly one **company**, and a person may belong to
several. The company decides who sees the project, what it costs and whose
records it can share (laboratories, methods, standards). **Never pick the
company for the user**, even when only one is offered: ask which company, and
say the company again when you show what the project will be. Creating a
project can raise what the company pays, so only the company's owner, a
company manager with purchase authority, or geoDB staff may create one; a
member without it is told the fix (the owner turns on purchasing for them).

A project's **coordinate system** is its working frame: a **projected** CRS
(a UTM zone or a State Plane, in metres or feet), optionally with a local
origin and a rotation. It is what drill traces are computed in, and every
point record's project-frame copy (`crs_easting`/`crs_northing`) is derived in
it on read. Degrees are not a frame: a geographic CRS (EPSG:4326) can be the
project's *reference* CRS but never its working frame. Setting it never
changes a record's own numbers (its native coordinate and `epsg` stay exactly
as entered). Changing a frame that is already set re-derives every
project-frame copy and recomputes every drill trace, so it is a decision for
the user, made once and on purpose. A project with no coordinate system
cannot compute traces or positions down a hole; the remedy is to set one,
never to guess positions.

A project is in one of three **states**. **Active**: everything works.
**Holding**: the project can be read, exported and its claims maintained, but
no geology data is added, edited or deleted (imports, logging, field sync and
connected-AI writes are refused). **Frozen**: sealed; nobody can open, read or
export it until it is unfrozen. A state can change what the company pays:
moving down takes effect from the next billing cycle; moving up is the
person's own decision, made in the browser.

**Deleting a project is reversible.** It moves to the Trash with everything
in it and can be restored for the retention window; nothing is purged by an
AI. Before a deletion, say what goes with it (every record in the project)
and that it can be restored.

**Managing projects from outside geoDB** goes through the same records
endpoint as every write, with the model Project, one project per request:
create, update (its name or description), set the coordinate system, set the
state, retract (to the Trash) and restore. Read its contract first. Every one
is a dry run first: the dry run returns what will change and a confirm value;
show the user what will change, wait for their yes, then send the same request
for real with that confirm value. A create that names no company is refused
and lists the companies the person may use: ask the user which one, every
time, even when only one is listed, and name the company again when you show
the dry run. Changing a coordinate system that is already set also needs the
user's explicit acknowledgement (change_project_crs). A change that raises
what the company pays is never yours to make: it is refused with the page
where the person does it themselves. Every write returns its Undo handle and
the project's web address; say both when you report it.
