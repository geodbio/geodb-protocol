# Public land: who holds claims here, what PLSS division it is, and what is withdrawn

Reading geoDB's mirror of the public land layers before staking or plotting — claims keyed by serial with an aliquot footprint, the PLSS division and aliquot at a point, withdrawals and surface ownership — and why an empty answer is never open ground.

### An empty answer is not open ground

geoDB keeps a **mirror** of the public land layers: BLM's mining claims, the Public
Land Survey System (PLSS), designated wilderness, wilderness study areas, mineral
withdrawals and surface management. It is a convenience copy with a **sync date**,
never the agency's own record and never a title search.

So "no claims here" means only "none in the mirror as of its last sync". A claim
staked since then is not in it; a withdrawal from a layer the mirror does not carry
is not in it; ground the PLSS mirror has not loaded has no section. Say the sync
date, say what the layer does not cover, and never tell the user ground is open,
clear or available to stake on the strength of an empty answer. Checking the
agency's own record before staking is the user's step, and saying so is part of
the answer.

### A claim's polygon is a footprint, not its boundary

BLM publishes a mining claim's shape as the **aliquot parts** (the quarter-sections,
or quarter-quarters) it touches. A standard 20-acre lode claim can show as a
160-acre rectangle. So:

- never present the polygon as the claim's boundary, and never measure a claim
  from it — the recorded acres are the claim's size;
- "claims touching this area" is over-inclusive by up to a whole aliquot part: a
  claim listed may not actually reach the ground in question;
- a claim BLM publishes with no polygon is still located by its legal description
  (the sections it names).

### Key a claim by its serial

A claim is identified by its **BLM serial** (the case number, e.g. two state
letters and digits). BLM's internal row numbers change whenever it republishes a
layer, so never carry one. Claims filed together share a **lead file** serial.
The claimant, location date and fee dates come from BLM's own case records:
its serial register (`serial_register_read_at` says when it was read for this
claim), its case page (`case_read_at`), or its bulk serial-number index, which
is how a claim can name a claimant while both stamps are empty. An empty
claimant means none of them has published one yet, or BLM redacted it (closed
cases), never "nobody holds it".
A closed claim is history, not a holding.

### PLSS: state, meridian, township, range, section, aliquot

A PLSS location is only unique with its **state and principal meridian**: the same
township, range and section label exists in several states. Name all of them.
Where two surveys overlap (near some state lines) a point lies in two divisions,
and both are real.

A section numbered **above 36** is a **protraction block**: BLM numbers unsurveyed
ground 37 and up. It is not a typo and not an error. An **aliquot** (NE¼ NW¼ and
so on) is only placed on a regular surveyed section; on an irregular, fractional or
unsurveyed section, name the section and let the user confirm the aliquot from the
survey — never guess a quarter.

### Withdrawals, designations and surface ownership

A **designation** sits on ground whoever manages it: designated wilderness
(mineral entry is withdrawn), a wilderness study area (managed to preserve
wilderness character until Congress decides — not wilderness), or a mineral
withdrawal. A withdrawal is not always a flat bar: its **purpose** says whether
special rules apply (a powerline corridor is not a wilderness). An empty expiry
means none is published, not that it never expires.

**Surface ownership** says which agency manages the surface (or, in Alaska, the
state land category). Ground with no ownership piece is neither federal nor state
land in the mirror: usually private or other. Mineral and surface rights can
differ; this is not a title search.

### Reading the land layers

Every land read names the project it is for (`project_id`) and is served only
for a project whose company pays for geoDB (its first free month counts);
otherwise `land_data_needs_paid_plan` names the remedy. The reads are bounded: one
area of interest per read (except `land-recent-filings/`, below) (`bbox` as west, south, east, north; or `lat` and `lon`
with `radius_m`; or a GeoJSON `polygon`; all WGS84 degrees, at most 260 km²), pages
of at most 200 claims, lookups by serial or by township and section. There is no
whole-layer read and no file export of these layers.

- `land-claims/` — claims in the area (`status`: active, closed or all), each
  with its serial, name, type, claimants, lead file, dates and footprint;
  `land-claims/<serial>/` — one claim. To find a block's claims, narrow the
  area by `name` (the start of the claim name) or `claimant`, or read one lead
  file's whole group with `lead_file`, which needs no area.
- `land-plss/` with `lat` and `lon` — the divisions a point is in, with the
  aliquot where it can be placed; `land-townships/` and `land-sections/`
  (`state`, `township`, `range`, `section`, optional `meridian`) — an outline.
- `land-status/` — designations and ownership clipped to the area, each with its
  acres in the area and whether it covers the whole area.
- `land-recent-filings/` — the one read bounded by a state and a window instead
  of an area: new claim blocks (claims filed under one lead file) in `state`
  over the last `days` (at most 366) or `since`/`until`, with `min_claims` and
  `order`. It needs a company that pays (its free month does not count) and
  holds a Field or Drilling project, otherwise
  `recent_filings_need_field_project` names the remedy. `date_basis=appeared`
  (the default) is when BLM's records first showed the claims, never the day
  they were staked: say "newly appeared in BLM's records". `date_basis=located`
  is the legal staking date, and its latest weeks are incomplete because a
  claimant has 90 days to file. `ungrouped` counts new claims BLM's serial index
  has not been read for yet: say how many. Read a block's claims with
  `land-claims/?lead_file=`.

Every answer carries `mirror` (each layer's last sync and what it does not cover)
and `not_a_clearance`; pass both on in plain words.
