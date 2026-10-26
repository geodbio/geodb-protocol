# Views: showing the user their data in 3D, and handing them the link

What a 3D view is (targets, angle, layers, colour), how to frame "the holes with the new assays" by ids instead of coordinates, a link versus a saved view, and what to tell the user when the scene is still building.

### What a view is

A **view** is what the 3D viewer shows when it opens: the **targets** it is about,
what it does with them (**highlight** them, **isolate** them so only they draw, or
**hide** them), the camera **angle**, which **layers** are on, and what the assays
are **coloured** by. A view is described in words and ids; the viewer does the
drawing. Looking at a view never changes the project's data, its colour ranges or
anyone else's screen.

A view opens in the user's own browser, on the project it names, with the user's
own login. A link to a view grants nothing: a teammate who opens it sees the same
view; someone who cannot see the project sees the normal refusal page and nothing
about what the view was about.

### Targets: name what the view is about, by id

Targets are ids from what you have already read, never a place on the ground:

- a list of drill holes;
- a **certificate**: the holes whose samples it assayed. "The holes with the new
  assays" is the certificate that just came back;
- a **submittal**: the holes of the samples sent in that batch;
- a **logging set** (lithology, alteration, a sampling pass…): the holes logged in
  that pass. "The new logging" is its set, or the list of holes just logged. A
  logging-set target also **draws** that set (next section);
- a **grid filter**: the same filter the user would type on the drill-hole or
  sample grid (a hole-name pattern, a grade range on an element).

A target that is not in the project, was deleted, or never existed gets the same
answer, and it is left out of the view. Check the ids against your own reads and
tell the user what was left out.

### Which logging set the drilling draws

A project can keep several logging sets per kind of interval (a first logging and
a relog, two sampling passes). The viewer draws ONE set per kind: lithology,
alteration, the sampling pass the assays come from, and custom intervals. With no
choice it draws the project's export set (Project Settings), else the default set.
A project whose default set is empty and whose logging sits in another set draws
grey traces with no lithology: that is the set, not the rendering.

Choose the set in the view, never by changing the project's export set (that
moves every export and every connected tool too): a logging-set target draws its
set and frames its holes; to keep the whole project in view and only choose what
draws, name the set as a **set to draw** instead. One per kind; a choice is part
of the view, so a saved view keeps it. In the viewer the user switches it from the
part's style menu, which lists each set with its interval count and says when the
drawn set is empty and which sets hold rows.

### Angle, not coordinates

The camera frames the targets by itself. Name only the angle: **plan** (looking
straight down, north up), **ne30** · **nw30** · **se30** · **sw30** (looking north-east,
north-west, south-east or south-west, 30° down), **section-n** or **section-e** (level,
looking north or east). "Looking north-east" is ne30, which is also the default view,
so a link that looks north-east names no angle at all. An azimuth (the direction the
camera looks toward, degrees clockwise from grid north) and a plunge (degrees below
horizontal) work too. Never compute a camera position.

### Colour and layers

Colour the assays by an element and the viewer uses the project's own colour range
for it. A project without a colour range for that element keeps the default colours;
say so, and that a colour range is set up on the assay colour ranges page. Layers
are switched on or off by name (drilling, terrain, point samples, land holdings,
water, cross sections, structures, surfaces) and the drilling's own parts (traces,
collars, assays, lithology, alteration, custom intervals, pads, planned holes).

### A link, or a saved view

A **link** describes a view without saving anything: hand it to the user and it
opens on that view. A **saved view** is a named view of the project with a short
link of its own: every member who can see the project finds it in the viewer's
Views list. Save one when the user asks to keep or share a view; a saved view can
be removed (to the Trash) and brought back.

### When the scene is still building

A project the viewer has not opened before sets itself up when the view opens:
drill holes with surveys are traced, and terrain is fetched and built. The answer
says what is still building ("traces are building for 15 holes", "terrain is still
building"). Pass that on to the user: the view opens anyway and fills in when the
traces and terrain land, usually within minutes.

### Building a link

`GET /api/v2/projects/{id}/view-link/` builds the link and writes nothing:
`targets` (`holes:12,13;certificate:5;submittal:7;logging_set:lithology:9`, or a
JSON list of target objects, grid filters included), `focus`
(highlight · isolate · hide), `angle`, `color`, `layers`, `hide`, `title`, and
`sets` (the set each kind DRAWS, nothing framed: `lithset:9;altset:4`,
`sampleset:12`, `logging_set:custom_interval:3`; read each one's answer in
`sets`). Hand the
user `url`; `opens_on` says in one sentence what it shows. Read `unresolved` (what was left out, and why) and `notices` (what is
still building) and tell the user both. A project whose company does not have the
3D views yet answers `view_surface_unavailable`: say so, in words.

### Saving a view

A saved view is a `SceneView` record on the records gate (a person's key only):
`create` with `{"project": <id>, "title": "...", "view": {<the view-link
parameters>}}`, dry run first like every write; the row answers the view's
short link as `result.url`. `update` changes its title or what it shows,
`retract` moves it to the Trash (`"confirm": "retract"`), `restore` brings it back,
and Undo reverses any of them.
