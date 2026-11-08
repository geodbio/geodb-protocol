# Data rooms and vendor keys: sharing a project with an outside party

A data room is a curated, published set of a project's maps, 3D views, figures, documents, photos, reports, QA/QC approvals and data tables; a vendor key is a read-only API key for one outside party, optionally limited to one published room. Curate the room, the person publishes it and creates the key in the browser, then read what the party pulled.

### What they are

A **data room** is a named set of one project's items curated for people
outside the company (an investor, a partner, a consultant, a targeting or
modelling firm). It has an Overview text and sections of panes: maps, 3D
views, figures, documents, photos, published reports, QA/QC approvals and
live data tables. A project may have several rooms. Nothing in a room is seen
by anyone outside until the room is **published**, and publishing can make
items that are private today visible to the room's guests.

A **vendor key** is a read-only API key a company gives ONE outside party for
ONE project. It never writes. It may be **pinned to one data room**: it then
reads only what that room shares, and only while the room is published. Each
key has a pull log: what the party read, when, and what was refused.

A vendor key is not the user's own AI connection or agent key: those act AS
the person, with the person's rights. Never suggest giving one of those to an
outside party.

### Reading them

- `datarooms/?project=<id>` lists a project's rooms; `datarooms/<id>/` is
  one room with its panes and the preflight (what its guests would see, and
  which private items publishing would make visible).
- `datarooms/candidates/?project=<id>` lists what the project could put in
  a room, before any room exists, by section (maps, threed, figures,
  documents, photos, reports, qaqc; add `&section=<section>` for one);
  `datarooms/<id>/candidates/?section=<section>` is the same list marked with
  what that room already holds. Maps, 3D views, figures, documents, photos
  and reports are listed there, not among the project's data records: a
  project with no drilling can still have maps to share.
- `vendor-keys/?project=<id>` lists a project's vendor keys (label, the first
  characters of the key, its state, its room, its request totals);
  `vendor-keys/<id>/pull-log/` is one key's log, by hour.
- These reads need the person to manage the project: data rooms need a company
  owner or manager; vendor keys need an owner, a manager or the project's admin.

### Curating a room

1. Read `datarooms/?project=<id>` (reuse a room if one fits) and the
   candidates for each section the user named, and match their words to the
   items' labels.
2. Create the room (`DataRoom` create: `name`, `overview`). It starts empty.
   Write the short Overview yourself from what the user said and what the
   project holds; the dry run shows it to them before anything is saved.
3. Add the panes (`DataRoomItem` create: `dataroom`, `section`, `artifact`
   from the candidates read, `caption`). Order them with `position`; remove
   one with a retract. Every write is a dry run first and waits for the
   user's yes, as always: once they say yes, carry the plan through.
4. Read `datarooms/<id>/` and walk the user through the preflight, the
   private items above all: publishing makes them visible to the room's
   guests.

### Publishing: the person's own click

A `DataRoom` publish never publishes. Its dry run answers
`publish_approval_required` with `offending.preflight` and a one-time link in
`offending.approval.url`. Show the preflight, give the user the link, and say
that nothing is shared until they press Publish on that page (it asks them for
a sign-in code first). `GET approvals/<id>/` says what became of it.

Guests (invites and share links) and keys pinned to a room see it only while
it is published. To take a room down, send a `DataRoom` unpublish (`id`): a
dry run first, then the user's yes. Nothing is deleted, and publishing it
again brings every guest back. An unpublish is not undone: putting the room
back up is a publish, which the person approves.

Once a room is published, its guests see every change at once, so you may
only reorder or remove its panes. Anything that adds to or rewrites what they
see (a pane, the Overview, the name, a caption, a 3D view shown in it) is
refused `dataroom_published`: tell the user what you would change, and that
they can make it on the room's page or unpublish first. A data table pane is
live: its guests see the project's rows as they change.

### Giving an outside party a key

You never create a key and never see one: the key is shown once, in the
user's browser. `GET vendor-keys/new-key-link/?project=<id>&dataroom=<id>
&label=<who it is for>&expires_days=<n>` returns the page with the form
filled in, and the steps to give the user:

1. Open the link and press Create. Copy the key: it is shown only once.
2. Send it to the outside party privately (never by a shared document or a
   group chat), with the API's address.
3. Set an expiry that matches the work, and revoke the key when it ends.

A key pinned to a room works only while the room is published. Afterwards,
read the pull log to tell the user what the party read, and revoke a key
(`VendorKey` retract, `"confirm": "retract"`) when the user asks: the party
is refused from their next request. A revoke cannot be undone; a new key can
always be made.
