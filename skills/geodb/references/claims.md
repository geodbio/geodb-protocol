# Mining claims: corners, block layout, and stake status

What a claim's corner monuments are, why a lode-claim block is shaped the way it is, and why a crew's stake status is not the claim's approval or legal status.

Each claim's corners are marked by **location monuments (LMs)**: the physical
posts or markers a staker sets, and the reference points a filing map cites.

Lode claims are packed as rectangles wound clockwise; a block follows the
source ground and the packing rules.

A crew's STAKE workflow status on a corner post (Planned / Assigned / Staked /
Skipped) is a different object from a claim's layout, its approval status and
its legal status: changing it never touches the layout or the approval.

### Reading a claim's stakes

`claim-stakes/` lists the posts of a project's claims: one row per physical
post, its `claim_links` naming every claim it serves with the corner number it
holds there (`claim-stakes/by-claim/<land-holding id>/` for one claim). The
PLANNED position is `target_easting` / `target_northing` in `target_epsg`; the
STAKED position, when one was recorded, is `latitude` / `longitude` in `epsg`
(a staked stake without one was staked before positions were recorded). To
hand the user one consolidated file of corners and monuments, read the stakes
and the claims (`landholdings/`) and build it yourself.

### Landing a claim's stakes

Landing stakes is a claim-manager task, from the person's own connection: it
needs the Contracting Manager role (or a company owner or manager) PLUS the
right to add data on the project. In order:

1. Land the claims (`LandHolding`, each with its `state`).
2. Create the group's package (a `ClaimPackage` create): ONE package
   per group of claims staked together, i.e. per lead file or staking batch,
   never one per stake. It lands as a Draft.
3. Land the group's posts as `ClaimStake` rows, each naming that package in
   `claim_package` (its name or CP-number): one row per physical post, so a
   corner shared by four claims is ONE stake naming all four in
   `land_holdings` (`"AB 12:2, AB 13:1"`: claim name, then the corner number).

A dataset (several files rehearsed together) may carry `LandHolding` or
`ClaimStake` members but never a `ClaimPackage`, which is always its own
request; since the package needs its claims stored and every stake names the
package, a new block is these three writes in this order, never its claims and
stakes in one dataset.

- **Which corner is Corner 1**, in this order of authority: the location
  notice's description, then the claim map, then the first vertex of the
  claim's polygon. Say which you used for each claim; the vertex order is the
  weakest, so flag it.
- **Idaho and New Mexico**: the location monument IS Corner 1, a corner (WP)
  stake, never a separate LM stake (refused). Elsewhere an LM is its own
  stake with no corner number.
- **Positions**: the planned position always (the original numbers and their
  `target_epsg`); the staked position only when you know it, e.g. read from GPS
  tracks of the staking day. Never copy the planned position into the staked
  one.
- **Status**: Planned, or Staked with its `date_staked` (a historical post
  staked without a recorded position lands Staked; the planned position
  stands). Later changes: see the next section; choosing a crew's staker is
  the web's.
- A stake is identified by its name WITHIN its package: a name already in
  that package is skipped, never a second stake, while another group's
  package may reuse it ("WP 1" in two packages is two stakes). A corner
  already held by any stake, in any package, is refused.

### After the stakes land

A landed stake is never re-sent as a `ClaimStake` to change it. Its workflow
changes through `ClaimStakeStatus` (intent `update`), one record per existing
stake, named by `id` or by `sequence_number` with `claim_package`:

- **Status** Planned / Assigned / Staked / Skipped. Planned releases the
  assignee (any crew can pick it up); Assigned keeps the staker already
  assigned on the web and is refused for a stake nobody is assigned to.
- **A staked position** (`latitude` + `longitude`, with `epsg` when
  projected; `date_staked` = when the work happened). Filling one onto a stake
  that has none needs no reason and means Staked. A different position on a
  stake that already has one is a MOVE and needs a `reason`.
- **Reopening a Staked stake** needs a `reason`. Nothing is erased: the
  closed staking round keeps its date, staker, position and photos.
- The status note (`status_notes`) and links to the project's own photos
  (`photo_ids`, additive).

Ask the user for every reason; never invent one. One refused row refuses the
whole request. A status change is not undoable: to reverse one, send the
opposite change. To move a stake, or a whole package with its stakes, to the
Trash use `retract` with `"confirm": "retract"`; bring it back with `restore`
and that write's `audit_batch_id` (or its Undo). All of it needs the same
claim-manager right as landing; the Trash also needs the right to edit all
data.
