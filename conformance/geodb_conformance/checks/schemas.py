"""
Every row of every core list validates against the packaged schema.

This is the check a vendor cares about most and the one a hand-written test
suite never quite gets to: not "the endpoint answered 200" but "the thing it
answered is the record the protocol describes, field by field, for every row
it served."

The schemas travel with the package (``contract/schemas/``) so the runner is
checking the server against the PUBLISHED vocabulary rather than against
whatever the server would describe itself as.
"""

from __future__ import annotations

from ..harness import REGISTRY, Failed, Skipped, require

#: list path -> packaged schema name. Derived from the spec's own component
#: reference where possible (below); this map is the fallback for the handful
#: of names that do not transform mechanically.
_SCHEMA_BY_COMPONENT = {
    'DrillCollarRead': 'collar',
    'DrillSurveyRead': 'survey',
    'DrillLithologyRead': 'lithology-interval',
    'DrillAlterationRead': 'alteration-interval',
    'DrillStructureRead': 'structure-interval',
    'DrillMineralizationRead': 'mineralization-interval',
    'DrillVeinRead': 'vein-interval',
    'DrillRQDRead': 'rqd-interval',
    'DrillSpectralIntervalRead': 'spectral-interval',
    'DrillCustomIntervalRead': 'custom-interval',
    'DrillSampleRead': 'drill-sample',
    'PointSampleRead': 'point-sample',
    'AssayRead': 'assay',
    'LaboratoryRead': 'laboratory',
    'CertificateRead': 'certificate',
    'QCSampleRead': 'qc-sample',
}


def component_for_list_path(session, path):
    """The Read component a list operation's 200 declares, via its envelope."""
    try:
        operation = session.contract.operation('get', path)
    except KeyError:
        return None
    schema = (operation.get('responses', {}).get('200', {})
              .get('content', {}).get('application/json', {})
              .get('schema', {}))
    ref = schema.get('$ref')
    if not ref:
        return None
    envelope = session.contract.component(ref.rsplit('/', 1)[-1])
    items = (envelope.get('properties', {}).get('results', {})
             .get('items', {}).get('$ref'))
    return items.rsplit('/', 1)[-1] if items else None


def schema_for_list_path(session, path):
    """The packaged schema name for a list path, or None if it has none."""
    component = component_for_list_path(session, path)
    return _SCHEMA_BY_COMPONENT.get(component)


def _validator(schema):
    from jsonschema.validators import Draft202012Validator
    return Draft202012Validator(schema)


@REGISTRY.add(
    'schema.every_row_validates',
    'Every row of every core list validates against the published JSON Schema '
    'for its record type — the schemas a vendor downloads accept the data '
    'this server actually serves.')
def schema_every_row_validates(session):
    from .envelope import core_list_paths

    failures = []
    validated = 0
    covered = []
    for path in core_list_paths(session):
        name = schema_for_list_path(session, path)
        if name is None:
            continue
        try:
            schema = session.contract.schema(name)
        except FileNotFoundError:
            failures.append(f'{path}: no packaged schema named {name!r}')
            continue
        validator = _validator(schema)
        body = session.get_json(path, params={'limit': 25})
        rows = body.get('results') or []
        if rows:
            covered.append(f'{name}×{len(rows)}')
        for index, row in enumerate(rows):
            errors = sorted(validator.iter_errors(row),
                            key=lambda e: list(e.absolute_path))
            validated += 1
            for error in errors[:3]:
                location = '.'.join(str(p) for p in error.absolute_path) or '(root)'
                failures.append(
                    f'{path}[{index}] {location}: {error.message}'
                    f'  (schema {name}.json)')
    require(validated,
            'no core list returned a row, so no schema was exercised — this '
            'is not a pass, it is an empty project')
    require(not failures,
            f'rows that do not validate against their published schema '
            f'({validated} rows checked, {len(covered)} types):\n'
            + '\n'.join(f'  {row}' for row in failures[:25]))
    session.shared['schema_coverage'] = covered


@REGISTRY.add(
    'schema.declared_types_hold',
    'A field the spec declares as a string is a string on the wire — in '
    'particular an assay value, which is a decimal STRING so that a lab '
    'number is never silently rounded by a JSON float.')
def schema_declared_types_hold(session):
    body = session.get_json('/api/v2/assays/', params={'limit': 10})
    rows = body.get('results') or []
    if not rows:
        raise Skipped('this project holds no assays')
    problems = []
    seen = 0
    for row in rows:
        for element in row.get('elements') or []:
            seen += 1
            value = element.get('value')
            if value is None:
                continue
            if not isinstance(value, str):
                problems.append(
                    f'assay {row.get("id")} element '
                    f'{element.get("element")!r}: `value` is '
                    f'{type(value).__name__} {value!r}, must be a string')
            if 'units' not in element:
                problems.append(
                    f'assay {row.get("id")} element '
                    f'{element.get("element")!r}: no `units` beside the value')
    if not seen:
        raise Skipped('assays present but none carries an element value')
    require(not problems,
            'assay values that are not decimal strings with their units:\n'
            + '\n'.join(f'  {row}' for row in problems[:15]))
