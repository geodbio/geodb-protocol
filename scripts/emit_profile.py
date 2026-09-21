#!/usr/bin/env python3
"""
Emit ``PROFILE.md`` from the spec's own ``x-protocol-core`` flags.

``PROFILE.md`` answers the one question that makes "any vendor can implement
this" a finite statement: **which operations are the protocol, and which are
geoDB's own?** Written by hand it would be a fourth document to keep in step
with three others, and the audit's whole finding B1 is that documents kept in
step by hand are not kept in step. So it is generated, and
``regenerate.py --check`` fails if the committed copy has fallen behind.

The prose that is NOT generated — what the split means, why a record is in or
out — lives in the constants below, beside the thing it explains.
"""

import collections
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

PROFILE_PATH = os.path.join(REPO, 'PROFILE.md')

#: Why each core family is in the profile. One sentence, aimed at somebody
#: deciding whether to implement it.
FAMILY_RATIONALE = {
    'Grant': 'What the credential in your hand can see. The cheapest first '
             'call an integration can make, and the one that tells a client '
             'which project it is bound to.',
    'Discovery': 'What this project actually contains, field by field — '
                 'including its user-defined `cf_*` fields, which vary by '
                 'project and by record type and cannot be discovered any '
                 'other way. Read this before assuming a fixed schema.',
    'Drill Holes': 'The hole and the stations that bend it. Everything logged '
                   'downhole references a collar, and any position computed '
                   'down a hole is an interpolation between survey stations, '
                   'so a server that serves intervals without these serves '
                   'data nobody can place in space.',
    'Drill Intervals': 'The eight typed geological interval families. A '
                       'conforming server implements the families it has '
                       'data for and returns an empty list for the rest; what '
                       'it must not do is invent a ninth generic one.',
    'Samples': 'The physical things that were sent to a laboratory — cut from '
               'core, or collected at a point on surface. The join between '
               'the geology and the results.',
    'Assays': 'The results and the chain of custody behind them: the values, '
              'the certificate (lab job) each one came from, and the '
              'laboratory that ran it. This is the first-in-category half of '
              'this protocol — a value with no route back to the job that '
              'produced it is what everything else here exists to stop '
              'shipping.',
    'Quality Control': 'The evidence the assays can be trusted: the standards, '
                       'blanks and duplicates inserted into the sample stream.',
    'STAC Catalog': 'The assets lane. Large binary data — imagery, grids, '
                    'geophysical volumes — travels as STAC 1.1 items with '
                    'footprints and checksums, not as JSON rows. The asset '
                    'endpoint answers with a short-lived signed redirect.',
    'Bulk Export': 'Whole tables, built in the background, as GeoParquet / '
                   'Parquet / CSV. One POST instead of paging a large list. '
                   'This is the only non-GET operation in the entire read '
                   'profile.',
}

#: What each extension family is, in a few words. These are real, supported and
#: ours — the label is about the CONTRACT, not about quality.
EXTENSION_NOTE = {
    'Surface Geology': 'Geology mapped at surface, plus the lookup vocabulary '
                       'behind it (lithologies, alterations, minerals, '
                       'formations, textures, vein types, field notes).',
    'Drill Intervals': 'The `*-sets` logging-run groupings and the interval-'
                       'type lookups — a geoDB organisational concept, not a '
                       'measurement.',
    'Drill Holes': 'Pads, computed traces and their GeoJSON form.',
    'Quality Control': 'Certified reference materials, QC type lookups, and a '
                       "project's QA/QC protocol and its status.",
    'Assays': 'Analytical method definitions and the per-project rules for '
              'merging several results for one sample and element.',
    'Samples': 'Fixed-length compositing of drill samples, and the '
               'assigned-to-a-user work queue.',
    'Discovery': 'Custom-field definitions in their own right, and '
                 'client-shaped rearrangements of the schema response.',
    'Map Layers': 'Vector layers, their features, and roads.',
    'Files': 'Project files, their raster map tiles, and elevation data.',
    'Photos': 'Core photography and general project photographs.',
    'Land Holdings': 'Mineral claims and other land holdings. A project '
                     'chooses how much of this a grant may read.',
    'Water': 'Water monitoring sites and the samples taken at them.',
    'Geophysics': 'Geophysical survey acquisition metadata. The bulk data '
                  'itself travels as STAC assets, which ARE core.',
}

HEADER = '''# The core profile

**A conforming server implements the core profile; everything else is optional
and labelled `x-geodb-extension`.**

This file answers one question: of the operations this API serves, which ones
are *the protocol* and which are *geoDB's own*? Without that line, "any vendor
can implement this" is not a finite statement — it is an invitation to
reimplement somebody else's application.

The split is machine-readable. **Every operation in [`spec/openapi.yaml`](spec/openapi.yaml)
carries exactly one of:**

| Flag | Meaning |
|---|---|
| `x-protocol-core: true` | A second implementer MUST serve this for a client written against this protocol to work against their server. |
| `x-geodb-extension: true` | Real, supported, and ours. Useful, and **not** part of the contract anyone else is asked to implement. |

⚠️ `x-geodb-extension` does not mean second-class, unstable or deprecated. Our
own clients read those endpoints every day. It means: not in the contract.

**This file is generated** from those flags by `scripts/regenerate.py`, so it
cannot describe a different profile from the one the spec publishes.
`scripts/regenerate.py --check` fails if it has fallen behind.

## What a conforming server owes

1. **The operations below**, at the paths below, with the response shapes the
   OpenAPI document declares. You may serve an empty list for a family you hold
   no data for; you may not serve a different shape.
2. **The envelope.** Every list answers `count` / `next` / `previous` /
   `results`, plus the deletion-sync keys `deleted_ids` /
   `deleted_since_applied` / `sync_timestamp`.
3. **The error contract.** Every 4xx carries a machine-readable `reason_code`
   with a `detail` and a `remedy`.
4. **The coordinate rule.** `latitude` / `longitude` are the ORIGINAL imported
   coordinate in the CRS named by `epsg` — easting and northing for a projected
   import, degrees only when `epsg` is 4326. The derived WGS84 is `geometry`.
   A server that silently reprojects into those two fields is not conforming;
   it is losing the customer's numbers.
5. **Nothing else.** The extension list below is explicitly NOT owed.

The per-record vocabulary, one readable file each, is in
[`schemas/`](schemas/) — also generated from the same components, for the same
reason.

'''

FOOTER = '''
## Notes on membership

**Why the eight interval families and not one generic interval.** Version 0.1.0
shipped a `schemas/interval.json` describing a generic record with an
`interval_type` discriminator and a `code`. No such record exists, here or in
any logging system we know of: lithology carries a rock type, RQD carries
recovery and fracture counts, a vein carries a width and its mineral contents.
Collapsing them loses every field that made them worth logging. That schema has
been removed rather than corrected.

**Why lookups are not core.** Methods, standards, QC types and the surface-
geology vocabulary are real, and a conforming server does not have to reproduce
our lookup model to be conforming: the values that matter travel inline on the
record — an assay value carries its own units and detection limit, an interval
carries its own length units.

**Why `certificates` is core.** The chain of custody is the part of this
protocol that does not exist elsewhere. A result you cannot trace to the job
that produced it, the lab that ran it, and the state that job was in
(preliminary, final, or a record reconstructed because the source named no
certificate) is a number without provenance.

**Why the two collar computations are core.** Desurveying is the one
calculation every consumer needs and everyone implements slightly differently.
Two clients that re-derive it independently will disagree about where a sample
is in space, and neither will know.

**Why `my-tasks`-style actions are not core.** "You" in those endpoints is a
geoDB user account. A grant does not have one, and a second implementer has no
reason to model ours.
'''


def build(spec):
    """PROFILE.md as a string, from the spec's own flags."""
    core = collections.defaultdict(list)
    extension = collections.defaultdict(list)

    for path, item in sorted(spec.get('paths', {}).items()):
        for method, op in item.items():
            if not isinstance(op, dict) or method == 'parameters':
                continue
            family = (op.get('tags') or ['Other'])[0]
            row = (op.get('operationId', ''), method.upper(), path,
                   (op.get('summary') or '').strip())
            if op.get('x-protocol-core'):
                core[family].append(row)
            else:
                extension[family].append(row)

    n_core = sum(len(v) for v in core.values())
    n_ext = sum(len(v) for v in extension.values())

    out = [HEADER]
    out.append(f'## The core profile — {n_core} operations\n')

    # Deliberate reading order: what am I allowed to see, what is here, then
    # the data, then the two lanes that are shaped differently.
    order = ['Grant', 'Discovery', 'Drill Holes', 'Drill Intervals', 'Samples',
             'Assays', 'Quality Control', 'STAC Catalog', 'Bulk Export']
    for family in order + sorted(set(core) - set(order)):
        rows = core.get(family)
        if not rows:
            continue
        out.append(f'### {family}\n')
        note = FAMILY_RATIONALE.get(family)
        if note:
            out.append(f'{note}\n')
        out.append('| operationId | | Purpose |')
        out.append('|---|---|---|')
        for op_id, method, path, summary in rows:
            out.append(f'| `{op_id}` | `{method} {path}` | {summary} |')
        out.append('')

    out.append(f'## geoDB extensions — {n_ext} operations\n')
    out.append(
        'Supported, project-scoped, and outside the contract. Read them '
        'freely against geoDB; do not expect them from another '
        'implementation.\n')
    out.append('| Family | Operations | What it is |')
    out.append('|---|---|---|')
    for family in sorted(extension):
        note = EXTENSION_NOTE.get(family, '')
        out.append(f'| {family} | {len(extension[family])} | {note} |')
    out.append(FOOTER)
    return '\n'.join(out)


def write(spec, verbose=True):
    body = build(spec)
    previous = None
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, encoding='utf-8') as fh:
            previous = fh.read()
    if previous == body:
        return False
    with open(PROFILE_PATH, 'w', encoding='utf-8') as fh:
        fh.write(body)
    if verbose:
        print('  emitted PROFILE.md')
    return True


def is_stale(spec):
    if not os.path.exists(PROFILE_PATH):
        return True
    with open(PROFILE_PATH, encoding='utf-8') as fh:
        return fh.read() != build(spec)
