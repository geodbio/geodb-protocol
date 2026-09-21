"""
The session: the HTTP transport, plus the contract the runner carries with it.

⭐ The suite ships its OWN copy of the contract. ``spec/openapi.yaml``,
``schemas/*.json`` and ``errors.json`` are packaged as package data and read
from the installed package — never fetched from the server under test, and
never read out of whatever repo happens to be the working directory.

That is the whole point of a conformance runner. A suite that asked the server
for its own spec and then checked the server against it would pass against any
self-consistent server, including one that serves a completely different
protocol. What a vendor needs to know is whether their server matches OUR
published contract, so the published contract travels with the runner.

The session also records every exchange, so a failure can print the request
that produced it rather than an assertion message alone.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Optional

import requests

from .harness import Failed, Skipped

#: Read by the CLI's ``--base-url`` default, so an environment already set up
#: for the examples works without repeating itself.
DEFAULT_BASE_URL = os.environ.get('GEODB_BASE_URL', 'https://api.geodb.io')


# ---------------------------------------------------------------------------
# The packaged contract
# ---------------------------------------------------------------------------

def _package_file(*parts) -> str:
    """Read one packaged contract file as text."""
    root = resources.files('geodb_conformance') / 'contract'
    handle = root
    for part in parts:
        handle = handle / part
    return handle.read_text(encoding='utf-8')


class Contract:
    """The published protocol, as the runner carries it.

    Loaded lazily: ``--offline`` mock runs and ``--list`` should not pay for
    parsing a 735 KB OpenAPI document.
    """

    def __init__(self):
        self._spec = None
        self._errors = None
        self._schemas: dict[str, Any] = {}

    # -- the normative document ------------------------------------------
    @property
    def spec(self) -> dict:
        if self._spec is None:
            import yaml
            self._spec = yaml.safe_load(_package_file('openapi.yaml'))
        return self._spec

    @property
    def version(self) -> str:
        return self.spec['info']['version']

    def core_operations(self) -> list[tuple]:
        """``(method, path, operationId)`` for every ``x-protocol-core`` op.

        The core profile is read from the spec's own flags rather than from a
        list maintained here, so adding an operation to the profile adds it to
        the suite in the same commit.
        """
        out = []
        for path, item in self.spec['paths'].items():
            for method, op in item.items():
                if method not in ('get', 'post', 'put', 'patch', 'delete'):
                    continue
                if op.get('x-protocol-core'):
                    out.append((method.upper(), path, op.get('operationId')))
        return sorted(out, key=lambda row: (row[1], row[0]))

    def operation(self, method: str, path: str) -> dict:
        return self.spec['paths'][path][method.lower()]

    def component(self, name: str) -> dict:
        return self.spec['components']['schemas'][name]

    # -- the error register ----------------------------------------------
    @property
    def errors(self) -> dict:
        if self._errors is None:
            self._errors = json.loads(_package_file('errors.json'))
        return self._errors

    @property
    def reason_codes(self) -> dict:
        return self.errors['reason_codes']

    # -- the per-record schemas ------------------------------------------
    def schema(self, name: str) -> dict:
        if name not in self._schemas:
            self._schemas[name] = json.loads(
                _package_file('schemas', f'{name}.json'))
        return self._schemas[name]

    def schema_names(self) -> list[str]:
        root = resources.files('geodb_conformance') / 'contract' / 'schemas'
        return sorted(p.name[:-len('.json')] for p in root.iterdir()
                      if p.name.endswith('.json'))


@dataclass
class Exchange:
    """One request/response pair, kept for the report."""
    method: str
    url: str
    status: int
    elapsed_s: float
    note: str = ''


class Session:
    """HTTP against the server under test, plus the packaged contract.

    Every check takes one of these. It deliberately does NOT wrap responses in
    anything clever: a check that wants the raw body should see the raw body,
    because the thing being tested is the wire.
    """

    def __init__(self, base_url: str, token: Optional[str], *,
                 timeout: float = 60.0, profile: str = 'core',
                 transport=None, network: bool = True):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout
        self.profile = profile
        self.network = network
        self.contract = Contract()
        self.exchanges: list[Exchange] = []
        #: Scratch space for checks that hand a value to a later check (the
        #: export job id, the row sample). Keyed by assertion name to keep the
        #: coupling visible.
        self.shared: dict[str, Any] = {}
        self._http = transport if transport is not None else requests.Session()

    # -- requests ---------------------------------------------------------
    @property
    def auth_header(self) -> dict:
        if not self.token:
            raise Skipped('no token supplied (--token / GEODB_TOKEN)')
        return {'Authorization': f'Grant {self.token}'}

    def request(self, method: str, path: str, *, auth: bool = True,
                allow_redirects: bool = False, note: str = '', **kwargs):
        """One request. ``path`` may be absolute (a ``next`` URL) or relative.

        ``allow_redirects`` defaults to FALSE, which is the opposite of
        requests' default and deliberate: trap 3.6 is that an asset download
        is a 302 whose Location must be fetched WITHOUT the grant header. A
        suite that auto-followed could not see the redirect it exists to check.
        """
        url = path if path.startswith('http') else f'{self.base_url}{path}'
        headers = dict(kwargs.pop('headers', {}))
        if auth:
            headers.update(self.auth_header)
        started = __import__('time').time()
        response = self._http.request(
            method, url, headers=headers, timeout=self.timeout,
            allow_redirects=allow_redirects, **kwargs)
        self.exchanges.append(Exchange(method, url, response.status_code,
                                       __import__('time').time() - started,
                                       note))
        return response

    def get(self, path, **kwargs):
        return self.request('GET', path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('POST', path, **kwargs)

    # -- convenience ------------------------------------------------------
    def json(self, response, what: str = 'response'):
        """Parse a JSON body, failing with the status and a body excerpt."""
        try:
            return response.json()
        except ValueError:
            raise Failed(
                f'{what}: expected JSON, got {response.status_code} '
                f'{response.headers.get("Content-Type")!r}: '
                f'{response.text[:200]!r}')

    def get_json(self, path, *, expect=200, what=None, **kwargs):
        what = what or f'GET {path}'
        response = self.get(path, **kwargs)
        if expect is not None and response.status_code != expect:
            raise Failed(f'{what}: expected HTTP {expect}, got '
                         f'{response.status_code}: {response.text[:300]!r}')
        return self.json(response, what)

    def list_path_for(self, operation_path: str) -> str:
        """A core LIST path with no ``{param}`` in it, as-is."""
        return operation_path
