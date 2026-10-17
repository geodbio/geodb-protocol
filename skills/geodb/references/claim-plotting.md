# Claim plotting: turning a location notice into claims on the project map

How a mining claim is plotted from its lead file — you read the notice and quote it, geoDB walks the courses and checks your quotes, the user confirms the reference point on the map, and only then are the claims recorded, private to the project.

### You read the notice; geoDB walks it

A location notice (a lead file) describes each claim in words: a tie from a
reference point to the first corner, then the courses around the claim — bearing
and distance, corner to corner, back to the start. You read the notice and write
each claim down as it is written: its name, its type, every course, its stated
acres. With every course you carry the notice's own words for it, verbatim — the
citation is how the user, and geoDB, can see where each number came from.

geoDB does the geometry. It walks the courses from the reference point on the
ground (bearing basis, declination, units, closure) and draws each claim; you
never compute a corner or a polygon yourself. A claim it cannot place honestly
comes back refused, by name, with what it needs — that is an answer, not a
failure. Report it plainly.

Transcribe each claim from its OWN words. Never copy a course from a sibling
claim, and never infer a course from a dimension the notice did not state: claims
in one block are often different sizes, and some lie long side north-south while
their neighbours lie east-west. A claim's orientation is a fact of that claim.

### The reference point and its frame are the user's

Every claim hangs from a point on the ground: a monument, a section corner, a
stated coordinate. The notice states it; you propose it, with its numbers exactly
as written and the coordinate system they are written in. That coordinate system
is the riskiest number you send — the same numbers in a neighbouring zone or
another datum land kilometres away, and the claims still look perfect, because
they all move together.

So the user confirms it. They see your proposed point on the project map and
either accept it, click where the point really is, or type its numbers in the
frame THEY pick. Nothing is recorded until they have answered, and you have
looked again at where the claims land from their point.

### Citations are checked against the document

geoDB checks every quoted call against the text the lead file itself carries.
The check ignores spacing, line breaks and punctuation, but every letter and
digit must be there in order: a near miss is a miss, so "N 12 W" never matches a
notice that says "N 21 W". A quote must also state the course it is attached to:
when it states a bearing or a distance, the course must carry the same numbers,
or the claim cannot read as verified. A quote that is not found, or that disagrees
with its course, does not stop the plot — it tells you to read that call again
(never edit the quote to fit), and the user should hear about it.

A scanned notice has no text layer, so nothing can be checked. Its claims carry
an `unverified_citation` flag on the record, and the user's confirmation of the
reference point on the map is required before anything is recorded. Say plainly
that the quotes could not be checked.

### What else is on that ground

With the claims drawn, geoDB lists the live federal mining claims and the land
withdrawals or designations they meet, from its mirror of the public land layers.
A live claim is listed when its published footprint (the quarter-sections it
touches) meets yours, so it may not truly overlap. An empty list is not open
ground: the mirror has a sync date and gaps, so pass on `not_a_clearance`.

### Previewing claims

`claim-plots/preview/` with `project`, `document` (the lead file the claims were
read from, a document of that project) and `plot`: ONE JSON object, sent as a
string, holding `claims` (each claim's courses with their `narrative_citation`),
ONE `reference_point` (`x` and `y`, or latitude and longitude, plus `epsg` and the
notice's words for it in `citation`) and an optional `block_name`. A claim tied
to a sibling's corner names it with `tie_to` and its `own_corner`; every other
claim hangs from the reference point. At most twenty claims a preview: preview a
bigger block in parts, one reference point each.

It writes nothing. It answers each claim's polygon (WGS84), tier, acres and
findings; the claims it could not place and why; the citation check; the live
claims and withdrawals nearby; `map.url`, a link the user opens to see the claims
drawn and to confirm the reference point; and a `preview_id`. Nothing records
until the user has confirmed that point and you have previewed again at it. Only a person's
own connection may preview, on a project where they may add data and whose
company pays for geoDB (`plotting_needs_paid_plan` otherwise), after they have
accepted the plotting terms on the web (`plotting_tos_required` otherwise).

### Recording claims

The rhythm: preview, give the user `map.url`, wait while they confirm the
reference point there, preview AGAIN with the same body (it now walks from their
point), show them where the claims land, and record only after they say yes:
`records/` with model `PlottedClaim`, intent create, the project, and ONE record
naming the preview — `preview` set to its `preview_id`. Send it as a dry run
first; it answers what the write will record, then the same with the dry run
off.

A record waits for the user: `reference_point_unconfirmed` until they answer on
the map, `plot_preview_stale` when they answered after your preview (preview
again), `plot_preview_required` when the preview was replaced or already
recorded. A claim that already has a current plot in the project is refused
`plot_already_recorded`: correcting a recorded claim is done on the map, not
here. Recorded claims are private to their project, and every write is undoable:
undo its `write_id` and the claims go to the project's Trash.

Recording files the notice as the claims' lead file, and geoDB then holds a lead
file back from connected AIs until it has reviewed it — even after an undo. So a
later preview from the same file answers not found: tell the user, and plot it
again on the project map if they want it now.
