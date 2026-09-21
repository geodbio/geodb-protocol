#!/usr/bin/env python3
"""
Emit ``schemas/*.json`` from the core-profile Read components of the spec.

WHY THIS FILE EXISTS
--------------------
The seven schemas in ``schemas/`` were hand-authored at 0.1.0 alongside a
generated ``spec/openapi.yaml``, and the two drifted immediately. The audit
measured it: **six of seven types shared zero or near-zero property names with
the wire**. ``collar.json`` said ``hole_id`` / ``date_drilled`` where the API
sends ``name`` / ``date_completed``. ``interval.json`` described a generic
``interval_type`` + ``code`` record that exists nowhere — downhole logging is
eight separately typed endpoints. ``assay.json`` was flat, one row per element;
the wire is one row per sample with a nested ``elements[]``. A vendor who coded
against ``schemas/`` got a client that could not read a single response.

Ruling R4 settles it in the only way that cannot regress: **the OpenAPI
document is normative for the wire, and these schemas are GENERATED FROM IT.**
They keep their job — the vocabulary, readable one file at a time, without
paging through a 700 KB spec — and lose their ability to disagree.

WHAT IS EMITTED
---------------
One standalone draft-2020-12 schema per **core-profile record resource**, named
after the resource rather than after our serializer class. Membership is read
from the spec's own ``x-protocol-core`` flags, so the profile and the schemas
cannot diverge either.

Each emitted file is self-contained except for references BETWEEN emitted
schemas, which stay as absolute ``$ref``s to their published ``$id`` (a
certificate's laboratory points at ``laboratory.json``). Everything else — the
enums, the nested value objects, the coordinate helpers — is INLINED, because a
reader opening ``collar.json`` should not have to resolve six more files to
learn what ``elevation_source`` can be.

Carried over exactly as the spec states them: ``format``, ``enum``, ``nullable``,
``description``, ``required``, and ``additionalProperties: false`` (every Read
component is closed on the wire — A3 made it so and the drift test keeps it
that way). ``readOnly`` is dropped: on a read-only surface every field is
read-only, and the flag means something different in a write context that Phase
B will define.

The ``cf_*`` custom-field pattern is carried across as ``patternProperties``,
because a schema that closed the object WITHOUT it would reject every real row
from a project that uses custom fields.
"""

import copy
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

VERSION = '0.1.0'
BASE_URI = f'https://spec.geodb.io/exploration/v{VERSION}'
JSON_SCHEMA_DIALECT = 'https://json-schema.org/draft/2020-12/schema'

#: The marker that says a file in ``schemas/`` is not to be hand-edited. It goes
#: in a top-level ``x-generated-by`` AND at the head of the description, because
#: the second is the one a person actually reads.
GENERATED_BY = (
    f'scripts/regenerate.py from spec/openapi.yaml (geoDB Open Exploration '
    f'Protocol v{VERSION})')
GENERATED_NOTE = (
    'GENERATED from the normative OpenAPI document (`spec/openapi.yaml`) — '
    'do not edit by hand; run `python scripts/regenerate.py`. '
    'The OpenAPI document is normative for the wire; this file is the same '
    'contract for one record type, readable on its own.')

#: Emitted schema file name -> the OpenAPI component it is generated from.
#:
#: Keys are RESOURCE names (what the protocol calls the thing), not serializer
#: class names, and they are deliberately the singular of the endpoint.
#: ``interval.json`` is gone: it described one generic interval record, and the
#: protocol has eight typed ones. That is the single biggest correction in this
#: whole task, so it is stated here rather than implied by an absence.
SCHEMA_FOR_COMPONENT = {
    # the hole and the stations that bend it
    'collar':              'DrillCollarRead',
    'survey':              'DrillSurveyRead',
    # the eight typed geological interval families (replacing interval.json)
    'lithology-interval':  'DrillLithologyRead',
    'alteration-interval': 'DrillAlterationRead',
    'structure-interval':  'DrillStructureRead',
    'mineralization-interval': 'DrillMineralizationRead',
    'vein-interval':       'DrillVeinRead',
    'rqd-interval':        'DrillRQDRead',
    'spectral-interval':   'DrillSpectralIntervalRead',
    'custom-interval':     'DrillCustomIntervalRead',
    # the physical samples
    'drill-sample':        'DrillSampleRead',
    'point-sample':        'PointSampleRead',
    # the laboratory half, chain of custody included
    'assay':               'AssayRead',
    'laboratory':          'LaboratoryRead',
    'certificate':         'CertificateRead',
    # quality control
    'qc-sample':           'QCSampleRead',
}

#: component name -> emitted schema name, for cross-references.
COMPONENT_TO_SCHEMA = {v: k for k, v in SCHEMA_FOR_COMPONENT.items()}

#: One sentence per emitted schema, written for somebody meeting the record for
#: the first time. The component's own description (which A5 wrote for a
#: consumer) follows it where there is one.
TITLES = {
    'collar': ('Drill collar',
               'The surface location and orientation of a drillhole — the '
               'anchor every downhole record references.'),
    'survey': ('Downhole survey station',
               'Azimuth and dip measured at a depth down a hole. The stations '
               'are what bend a hole away from its collar orientation.'),
    'lithology-interval': ('Lithology interval',
                           'Rock type logged over a depth interval of a hole.'),
    'alteration-interval': ('Alteration interval',
                            'Alteration logged over a depth interval of a hole.'),
    'structure-interval': ('Downhole structural measurement',
                           'A structural observation at a depth in a hole — '
                           'orientation relative to the core axis, and the '
                           'feature observed.'),
    'mineralization-interval': ('Mineralization interval',
                                'Mineralization logged over a depth interval, '
                                'with the minerals observed and their '
                                'abundances.'),
    'vein-interval': ('Vein interval',
                      'A vein logged over a depth interval — its type, width, '
                      'orientation and mineral contents.'),
    'rqd-interval': ('Geotechnical interval',
                     'Core recovery and rock-mass character over a depth '
                     'interval: RQD, discontinuities, strength and weathering.'),
    'spectral-interval': ('Spectral interval',
                          'A spectral scan over a depth interval, with the '
                          'mineral or geounit abundances it resolved.'),
    'custom-interval': ('Custom interval',
                        'A user-defined downhole interval. THE TYPE IS DATA: '
                        'the row names its own interval type, and carries '
                        'either a categorical value or a numeric measure.'),
    'drill-sample': ('Drill sample',
                     'A sample cut from an interval of core or cuttings, and '
                     'sent to a laboratory.'),
    'point-sample': ('Point sample',
                     'A sample collected at a location on surface — soil, rock '
                     'chip, stream sediment — and sent to a laboratory.'),
    'assay': ('Assay result',
              'One sample\'s laboratory results: a row per sample carrying its '
              'analyte values in `elements[]`, each traceable to the method '
              'and certificate that produced it.'),
    'laboratory': ('Laboratory',
                   'An assaying laboratory — the chain-of-custody endpoint that '
                   'issues certificates.'),
    'certificate': ('Assay certificate',
                    'A laboratory job: the batch of samples one lab analysed '
                    'and reported together, under one certificate number, on '
                    'one date. The chain-of-custody anchor a value traces back '
                    'to.'),
    'qc-sample': ('QC sample',
                  'A quality-control sample inserted into a sample stream — a '
                  'certified reference material, a blank, or a duplicate.'),
}

#: Keys drf-spectacular emits that mean nothing in a standalone JSON Schema.
DROPPED_KEYWORDS = ('readOnly', 'writeOnly', 'discriminator', 'xml',
                    'externalDocs', 'example', 'deprecated')


def _ref_name(node):
    return node['$ref'].rsplit('/', 1)[-1]


def _inline(node, components, seen):
    """Resolve a spec node into standalone JSON Schema.

    - a ``$ref`` to another EMITTED schema becomes an absolute ``$ref`` to its
      published ``$id`` (one hop, resolvable, and it keeps the vocabulary
      joined up);
    - any other ``$ref`` is INLINED, so the file stands alone;
    - ``allOf: [{$ref: SomeEnum}]`` — drf-spectacular's wrapper for a choice
      field carrying its own description — collapses to the enum itself;
    - ``nullable: true`` is carried through as an explicit type union, because
      ``nullable`` is OpenAPI 3.0 and means nothing to a JSON Schema validator.
    """
    if isinstance(node, list):
        return [_inline(v, components, seen) for v in node]
    if not isinstance(node, dict):
        return node

    if '$ref' in node:
        name = _ref_name(node)
        if name in COMPONENT_TO_SCHEMA:
            return {'$ref': f'{BASE_URI}/{COMPONENT_TO_SCHEMA[name]}.json'}
        if name in seen:          # defensive: a cycle would otherwise recurse
            return {'type': 'object'}
        return _inline(components[name], components, seen | {name})

    # allOf wrapping exactly one ref + sibling keywords -> merge them.
    if 'allOf' in node and len(node['allOf']) == 1:
        merged = dict(node)
        inner = _inline(merged.pop('allOf')[0], components, seen)
        if isinstance(inner, dict) and '$ref' not in inner:
            out = dict(inner)
            out.update({k: v for k, v in merged.items()
                        if k not in DROPPED_KEYWORDS})
            node = out
        else:
            node = {**inner, **{k: v for k, v in merged.items()
                                if k not in DROPPED_KEYWORDS}}
        return _nullable_to_union(node)

    out = {}
    for key, value in node.items():
        if key in DROPPED_KEYWORDS:
            continue
        out[key] = _inline(value, components, seen)
    return _nullable_to_union(out)


def _nullable_to_union(node):
    """``nullable: true`` -> a real JSON Schema null branch.

    OpenAPI 3.0's ``nullable`` keyword is not JSON Schema. A validator reading
    one of these files ignores it, and then rejects the null the API really
    sends. So it becomes a type union (or an ``anyOf`` when there is a ``$ref``
    or an ``enum`` in play).
    """
    if not isinstance(node, dict) or not node.pop('nullable', False):
        return node

    # A composition (oneOf/anyOf) — drf-spectacular's shape for a choice field
    # that can also be blank. The null branch has to join the COMPOSITION; a
    # `type` alongside `oneOf` would not admit it, and neither does dropping
    # `nullable` on the floor. ⚠️ This is the case that broke first: four
    # geotechnical fields and two others rejected a real row until the null
    # branch reached the list, and nothing but validating a live row could see
    # it, because the spec itself was correct.
    for keyword in ('oneOf', 'anyOf'):
        if keyword in node:
            branches = list(node[keyword])
            if {'type': 'null'} not in branches:
                branches.append({'type': 'null'})
            node[keyword] = branches
            return node
    if 'enum' in node and None not in node['enum']:
        node['enum'] = list(node['enum']) + [None]
        if isinstance(node.get('type'), str):
            node['type'] = [node['type'], 'null']
        return node
    if '$ref' in node:
        ref = node.pop('$ref')
        rest = {k: v for k, v in node.items()}
        return {'anyOf': [{'$ref': ref}, {'type': 'null'}], **rest}
    if 'type' in node:
        t = node['type']
        node['type'] = ([t, 'null'] if isinstance(t, str)
                        else sorted(set(list(t) + ['null'])))
        return node
    # No type, no enum, no composition: a free-form node that may be null.
    # Saying nothing is correct here — an untyped schema already admits null.
    return node


def core_components(spec):
    """The component names the CORE-PROFILE list operations really return.

    Read from the spec's own ``x-protocol-core`` flags, so this can never
    describe a different profile from the one the document publishes.
    """
    schemas = spec['components']['schemas']
    found = {}
    for path, item in spec.get('paths', {}).items():
        op = item.get('get')
        if not isinstance(op, dict) or not op.get('x-protocol-core'):
            continue
        if not op.get('operationId', '').endswith('_list'):
            continue
        media = ((op.get('responses', {}).get('200', {}) or {})
                 .get('content', {}).get('application/json', {}))
        ref = media.get('schema', {}).get('$ref')
        if not ref:
            continue
        envelope = schemas[_ref_name({'$ref': ref})]
        items = envelope.get('properties', {}).get('results', {}).get('items', {})
        if '$ref' in items:
            found[_ref_name(items)] = path
    return found


def emit(spec, name, component_name):
    """One standalone draft-2020-12 schema for one core record type."""
    components = spec['components']['schemas']
    component = components[component_name]
    title, blurb = TITLES[name]

    # The component's own description is the serializer's class docstring,
    # already written for a consumer by A5.1. It is kept only when it ADDS to
    # the blurb — two sentences saying the same thing in different words is
    # exactly the "two documents describing the same records" the audit named.
    own = (component.get('description') or '').strip()
    first_words = ' '.join(blurb.split()[:4]).lower()
    redundant = (not own or own == blurb
                 or own.lower().startswith(first_words)
                 or own.lower() in blurb.lower())
    description = (f'{blurb}\n\n{GENERATED_NOTE}' if redundant
                   else f'{blurb}\n\n{own}\n\n{GENERATED_NOTE}')

    out = {
        '$schema': JSON_SCHEMA_DIALECT,
        '$id': f'{BASE_URI}/{name}.json',
        'title': title,
        'description': description,
        'x-generated-by': GENERATED_BY,
        'x-openapi-component': component_name,
        'type': 'object',
    }

    resolved = _inline(copy.deepcopy(component), components, {component_name})
    for key in ('properties', 'patternProperties', 'required',
                'additionalProperties'):
        if key in resolved:
            out[key] = resolved[key]
    out.setdefault('additionalProperties', False)
    return out


def write_all(spec, verbose=True):
    """Emit every core schema into ``schemas/``. Returns {name: path}."""
    written = {}
    target = os.path.join(REPO, 'schemas')
    os.makedirs(target, exist_ok=True)
    for name, component_name in sorted(SCHEMA_FOR_COMPONENT.items()):
        path = os.path.join(target, f'{name}.json')
        body = json.dumps(emit(spec, name, component_name),
                          indent=2, ensure_ascii=False) + '\n'
        previous = None
        if os.path.exists(path):
            with open(path, encoding='utf-8') as fh:
                previous = fh.read()
        if previous != body:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(body)
            if verbose:
                print(f'  emitted schemas/{name}.json  <- {component_name}')
        written[name] = path
    return written


def stale_schemas(spec):
    """Names whose committed file differs from what the spec would emit now.

    Also reports files in ``schemas/`` that are no longer generated at all —
    a hand-authored leftover is exactly the drift this task exists to end.
    """
    stale = []
    target = os.path.join(REPO, 'schemas')
    for name, component_name in sorted(SCHEMA_FOR_COMPONENT.items()):
        path = os.path.join(target, f'{name}.json')
        body = json.dumps(emit(spec, name, component_name),
                          indent=2, ensure_ascii=False) + '\n'
        if not os.path.exists(path):
            stale.append(f'schemas/{name}.json (missing)')
            continue
        with open(path, encoding='utf-8') as fh:
            if fh.read() != body:
                stale.append(f'schemas/{name}.json (differs)')
    for existing in sorted(os.listdir(target)):
        if not existing.endswith('.json'):
            continue
        if existing[:-len('.json')] not in SCHEMA_FOR_COMPONENT:
            stale.append(f'schemas/{existing} (not generated from any core '
                         f'component — hand-authored leftover)')
    return stale


def load_spec(path=None):
    import yaml
    path = path or os.path.join(REPO, 'spec', 'openapi.yaml')
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)
