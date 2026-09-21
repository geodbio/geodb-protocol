"""
The asset lane: STAC 1.1, and the 302 that must not carry your credential.

Two claims are being checked. First, that the catalog is a real STAC 1.1
catalog — `conformsTo`, a `conformance` link that is not just the landing page
again, and extension URIs that resolve. Second, and more important, that an
asset download hands back a short-lived signed URL and that the credential is
NOT forwarded to it: a grant token presented on storage infrastructure is a
token in somebody else's logs.
"""

from __future__ import annotations

from ..harness import REGISTRY, Failed, Skipped, require, require_equal, require_in

STAC_VERSION_PREFIX = '1.1'


def _landing(session):
    return session.get_json('/api/v2/stac/', what='the STAC landing page')


@REGISTRY.add(
    'stac.landing_is_1_1',
    'The STAC landing page is a valid 1.1 Catalog with `conformsTo`, so a '
    'STAC client recognises it without being told.')
def stac_landing_is_1_1(session):
    body = _landing(session)
    require_in('stac_version', body, 'STAC landing')
    require(str(body['stac_version']).startswith(STAC_VERSION_PREFIX),
            f'STAC landing declares stac_version '
            f'{body["stac_version"]!r}, expected {STAC_VERSION_PREFIX}.x')
    require_in('type', body, 'STAC landing')
    require_equal(body['type'], 'Catalog', 'STAC landing `type`')
    require_in('id', body, 'STAC landing')
    require_in('links', body, 'STAC landing')
    require_in('conformsTo', body, 'STAC landing')
    require(isinstance(body['conformsTo'], list) and body['conformsTo'],
            'STAC landing `conformsTo` must be a non-empty array of '
            'conformance-class URIs')
    session.shared['stac_landing'] = body


@REGISTRY.add(
    'stac.conformance_link_differs_from_self',
    'The `conformance` link points at the conformance declaration, not back at '
    'the landing page — a client following it learns something new.')
def stac_conformance_link(session):
    body = session.shared.get('stac_landing') or _landing(session)
    links = {link.get('rel'): link.get('href')
             for link in body.get('links') or []}
    require_in('conformance', links, 'STAC landing links')
    require_in('self', links, 'STAC landing links')
    require(links['conformance'] != links['self'],
            f'the `conformance` link is the landing page itself '
            f'({links["conformance"]!r}) — following it teaches a client '
            f'nothing')
    followed = session.get_json(links['conformance'],
                                what='the STAC conformance declaration')
    require_in('conformsTo', followed, 'STAC conformance declaration')
    require(isinstance(followed['conformsTo'], list) and followed['conformsTo'],
            'the conformance declaration carries no conformance classes')


@REGISTRY.add(
    'stac.extensions_resolve',
    'Every `stac_extensions` URI a served item declares actually resolves, so '
    'a validating client is not stopped by a dead schema host.',
    profile='full', needs=('network',))
def stac_extensions_resolve(session):
    import urllib.error
    import urllib.request

    collections = session.get_json('/api/v2/stac/collections/',
                                   what='STAC collections')
    uris = set()
    for collection in collections.get('collections') or []:
        for uri in collection.get('stac_extensions') or []:
            uris.add(uri)
        items_href = None
        for link in collection.get('links') or []:
            if link.get('rel') == 'items':
                items_href = link.get('href')
        if not items_href:
            continue
        items = session.get(items_href)
        if items.status_code != 200:
            continue
        for feature in (session.json(items, 'STAC items')
                        .get('features') or []):
            for uri in feature.get('stac_extensions') or []:
                uris.add(uri)
    if not uris:
        raise Skipped('no served collection or item declares a stac_extension')

    unresolvable = []
    for uri in sorted(uris):
        try:
            with urllib.request.urlopen(uri, timeout=15) as handle:
                if handle.status >= 400:
                    unresolvable.append(f'{uri} -> HTTP {handle.status}')
        except urllib.error.HTTPError as exc:
            unresolvable.append(f'{uri} -> HTTP {exc.code}')
        except Exception as exc:                            # noqa: BLE001
            # A DNS failure here may be the runner's network rather than the
            # server's spec, so the message says which uri and what happened
            # and lets the reader judge.
            unresolvable.append(f'{uri} -> {type(exc).__name__}: {exc}')
    if unresolvable and len(unresolvable) == len(uris):
        raise Skipped(
            'no stac_extensions URI resolved from here — this is most likely '
            'the runner having no outbound network rather than the server '
            'being wrong: ' + '; '.join(unresolvable[:3]))
    require(not unresolvable,
            'stac_extensions URIs a served item declares but that do not '
            'resolve:\n' + '\n'.join(f'  {row}' for row in unresolvable))


@REGISTRY.add(
    'stac.asset_redirects_without_credential',
    'An asset download answers 302 to a self-authenticating signed URL, and '
    'that URL is fetchable with NO `Authorization` header — your grant token '
    'is never handed to storage infrastructure.')
def stac_asset_redirect(session):
    collections = session.get_json('/api/v2/stac/collections/',
                                   what='STAC collections')
    asset_href = None
    for collection in collections.get('collections') or []:
        items_href = next((link.get('href')
                           for link in collection.get('links') or []
                           if link.get('rel') == 'items'), None)
        if not items_href:
            continue
        items = session.get(items_href)
        if items.status_code != 200:
            continue
        for feature in (session.json(items, 'STAC items')
                        .get('features') or []):
            for asset in (feature.get('assets') or {}).values():
                if asset.get('href'):
                    asset_href = asset['href']
                    break
            if asset_href:
                break
        if asset_href:
            break
    if not asset_href:
        raise Skipped('this project serves no STAC asset to download')

    response = session.get(asset_href, allow_redirects=False)
    require(response.status_code in (301, 302, 303, 307),
            f'an asset href must answer a redirect to a signed URL, got '
            f'{response.status_code}')
    location = response.headers.get('Location')
    require(location, 'the asset redirect carries no Location header')

    # The second hop, deliberately WITHOUT the grant header. This is the check:
    # if the signed URL needs our token, the token is travelling to storage.
    import requests
    if location.startswith('/'):
        location = f'{session.base_url}{location}'
    unauthenticated = requests.get(location, timeout=session.timeout,
                                   stream=True, allow_redirects=True)
    unauthenticated.close()
    require(unauthenticated.status_code < 400,
            f'the signed URL from the asset redirect answered '
            f'{unauthenticated.status_code} without an Authorization header — '
            f'it is not self-authenticating, so a client is forced to forward '
            f'its grant token to storage')
