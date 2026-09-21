"""
The harness: a named assertion, a result, and a runner that reports both.

Deliberately hand-rolled rather than pytest-based. A vendor runs this against
their own server to find out whether their implementation is one; asking them
to install and understand a test framework — and to read a pytest tally as a
conformance verdict — puts a tool between them and the answer. What they want
is a table: every claim the protocol makes, and whether their server honours
it.

So the unit here is an ``Assertion``: a name, a one-line ``proves`` sentence
that reads as a contract clause, and a function that either returns (pass),
raises ``Failed`` (the server is wrong), or raises ``Skipped`` (the check could
not run here, and says why). The ``proves`` line is not a docstring for us —
it is the middle column of the report, and it is what makes the markdown output
readable as the contract rather than as a log.

Nothing in this module knows anything about geoDB. That lives in ``checks/``.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional


class Failed(AssertionError):
    """The server did not honour the contract. Carries the evidence."""


class Skipped(Exception):
    """The check could not run here. The message must say WHY, always.

    A skip is a hole in the report, so it is never silent: it prints in the
    table with its reason, and ``--strict`` turns every skip into a failure
    for a run that is meant to be complete.
    """


@dataclass(frozen=True)
class Assertion:
    """One named check.

    name     stable identifier — this is what ``--break`` names, what the
             JUnit testcase is called, and what a bug report cites.
    proves   ONE line, present tense, stating the contract clause this
             establishes. It is the report's middle column.
    fn       callable taking the session; returns None, or raises Failed /
             Skipped.
    profile  'core' (every conforming server) or 'full' (geoDB extensions and
             checks a second implementer is not asked to honour).
    needs    optional capability tags the runner uses to order/skip.
    """

    name: str
    proves: str
    fn: Callable
    profile: str = 'core'
    needs: tuple = ()


@dataclass
class Result:
    assertion: Assertion
    status: str                      # 'pass' | 'fail' | 'skip' | 'error'
    detail: str = ''
    duration_s: float = 0.0
    trace: str = ''

    @property
    def ok(self) -> bool:
        # A skip is not a pass, but it is not a failure of the server either.
        return self.status in ('pass', 'skip')


class Registry:
    """The ordered set of assertions, with the decorator that fills it."""

    def __init__(self):
        self._assertions: list[Assertion] = []

    def add(self, name: str, proves: str, *, profile: str = 'core',
            needs: Iterable[str] = ()):
        def decorate(fn):
            if any(a.name == name for a in self._assertions):
                raise RuntimeError(
                    f'duplicate assertion name {name!r} — names are the '
                    f'--break switch and the JUnit testcase id, so they must '
                    f'be unique')
            self._assertions.append(
                Assertion(name=name, proves=proves, fn=fn, profile=profile,
                          needs=tuple(needs)))
            return fn
        return decorate

    def __iter__(self):
        return iter(self._assertions)

    def __len__(self):
        return len(self._assertions)

    def select(self, profile: str = 'core', only: Optional[Iterable[str]] = None):
        """Assertions for a profile. ``core`` runs core only; ``full`` runs all."""
        only = set(only) if only else None
        out = []
        for a in self._assertions:
            if only is not None and a.name not in only:
                continue
            if profile == 'core' and a.profile != 'core':
                continue
            out.append(a)
        return out

    def names(self):
        return [a.name for a in self._assertions]


#: The one registry. ``checks`` modules import it and decorate onto it.
REGISTRY = Registry()


def run(assertions, session, *, on_result=None) -> list[Result]:
    """Run each assertion against ``session``, never stopping on a failure.

    A conformance run's value is the whole table: stopping at the first red
    tells a vendor one thing to fix and hides the other nine.
    """
    results: list[Result] = []
    for assertion in assertions:
        started = time.time()
        try:
            assertion.fn(session)
        except Skipped as exc:
            result = Result(assertion, 'skip', str(exc), time.time() - started)
        except Failed as exc:
            result = Result(assertion, 'fail', str(exc), time.time() - started)
        except Exception as exc:                      # noqa: BLE001
            # An unexpected exception is reported as 'error' rather than
            # 'fail': the distinction matters, because 'fail' means we
            # measured the server and it was wrong, and 'error' means the
            # check itself fell over and its verdict is unknown.
            result = Result(assertion, 'error',
                            f'{type(exc).__name__}: {exc}',
                            time.time() - started,
                            trace=traceback.format_exc())
        else:
            result = Result(assertion, 'pass', '', time.time() - started)
        results.append(result)
        if on_result is not None:
            on_result(result)
    return results


# ---------------------------------------------------------------------------
# Small assertion helpers — each raises Failed with the evidence in the message
# ---------------------------------------------------------------------------

def require(condition, message):
    if not condition:
        raise Failed(message)


def require_equal(actual, expected, what):
    if actual != expected:
        raise Failed(f'{what}: expected {expected!r}, got {actual!r}')


def require_in(member, container, what):
    if member not in container:
        raise Failed(f'{what}: {member!r} not present in {_brief(container)}')


def _brief(value, limit=300):
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + '…'
