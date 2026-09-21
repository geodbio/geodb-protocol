# Contributing

This protocol exists to be implemented by people who do not work here. If you are
building a logging app, a modelling package, a lab system, or an internal pipeline
and something in this spec is wrong, ambiguous, or missing — that is the thing we
most want to hear about.

**You do not need permission, an NDA, or a partnership to use, implement, fork, or
criticise this specification.**

## The fastest useful thing you can do

Open an issue. Three kinds are all welcome:

- **"This is ambiguous."** Two implementers could read a field two ways. These are
  the highest-value reports — ambiguity in a spec becomes divergence in the wild.
- **"This is missing."** Your data does not fit the vocabulary. Tell us the shape
  you actually have, with a real (or realistically shaped) example.
- **"This is wrong."** The spec says one thing and the reference implementation
  does another, or the modelling is simply bad.

A good issue names the file and field, says what you expected, says what you got or
what you could not express, and — where it helps — includes a small worked example.
You do not need to propose a fix.

There is a template for each of those three, plus one for proposals about the write
half — see the "New issue" chooser. The templates are prompts, not a form to satisfy:
skip anything that does not apply.

One thing we do ask. **Do not paste anyone's data into a public issue.** Strip or
replace identifiers, coordinates, and assay values that are not yours to share; a
realistically shaped placeholder tells us everything a real row would. Each template
carries a checkbox for this.

## Who reads this

Issues are triaged **weekly** by Joshua ([@joswhite1](https://github.com/joswhite1)).
Not instantly, and not by a rota — one person, once a week, reading all of them. If
something has sat for more than a couple of weeks, a nudge on the thread is welcome
and will not annoy anyone.

**Security problems do not go here.** They go to the address in
[`SECURITY.md`](SECURITY.md), which also gives our disclosure window and what to
include. The dividing line is in that file and repeated at the bottom of this one.

## How decisions get made

Plainly, because "open" is often heard as "design by committee" and this is not that:

- **Issues are open to everyone.** Anyone can argue any part of this spec.
- **We curate.** geoDB maintains the specification and the reference implementation,
  and we make the final call on what merges. Coherence is our responsibility.
- **Disagreement resolves by fork, not by veto.** The spec is CC-BY-4.0 and the
  schemas and code are Apache-2.0. If we steer this badly, you can take it and go.
  Nobody is trapped — that is the actual guarantee here, and it is deliberate.
- **No consortium, no standards body, no certification programme.** Validation
  tooling, never certification. If adoption ever demands heavier governance, that
  will be decided in public, in this repo.

We would rather change the spec early because an implementer told us it was wrong
than defend a mistake because it shipped.

## What we are actively looking for

**The write contract is the open problem.** This protocol reads today. Writing back
is harder and unfinished, because the rules that make the data trustworthy have to
travel with the write and be enforced on arrival — coordinates keeping their source
CRS, existing rows not being silently overwritten, provenance recorded per row,
every external write reversible.

If you would have to implement that side, your constraints should shape it before it
is written rather than after. Issues about write semantics — identity and
idempotency, conflict handling, what "the write was refused" should look like on the
wire — are the ones we most want right now.

## Compatibility and versioning

Semantic versioning. Additive fields are minor; anything that could break an existing
client is major and gets a changelog entry explaining the migration. Pre-1.0 the
shape is stable but field details may still move — [`CHANGELOG.md`](CHANGELOG.md) is
the record.

## Issues are the main road; pull requests are the side road

**We build the implementation. What we need from you is the specification.** The most
valuable contribution is not code — it is telling us what your data actually looks
like and where this contract would fail it. If your imaging data does not fit the
interval model, or your lab returns a shape the assay schema cannot express, that is
the report we cannot write ourselves.

Pull requests are welcome for documentation, examples, and clarifications. For
anything that changes the *meaning* of a field or endpoint, open an issue first — a
discussed change lands; an unannounced PR against the semantics usually does not.

**Generated files cannot be hand-edited.** `spec/openapi.yaml` and
`stac/xpl/schema.json` are emitted from the geoDB implementation, and
`schemas/*.json` and [`PROFILE.md`](PROFILE.md) are emitted in turn from the spec, by
[`scripts/regenerate.py`](scripts/regenerate.py). Edits are overwritten on the next
regeneration, and `scripts/regenerate.py --check` fails in CI if a committed copy has
fallen behind. If one of them is wrong, the bug is upstream — file the issue against the
behaviour and we will fix it at the source.

## Which document is right

**[`spec/openapi.yaml`](spec/openapi.yaml) is normative for the wire.** If any other
file in this repo disagrees with it about a field name, a type, or whether something
can be null, the OpenAPI document is right and the other file is a bug.

That sentence used to be load-bearing and is now mostly historical, because the other
files can no longer disagree: `schemas/` and `PROFILE.md` are generated from the
spec's own components and flags. It is stated anyway, because "which one is normative"
is the first question a serious implementer asks, and a repo that cannot answer it is
asking them to guess.

**[`PROFILE.md`](PROFILE.md) is normative for scope** — which operations a conforming
server owes. An issue arguing that something should move between the core profile and
the extensions is a good issue; it is a decision about the contract, not a detail.

## Licensing of contributions

By contributing you agree your contribution is licensed under this repo's terms —
Apache-2.0 for schemas and code, CC-BY-4.0 for spec text and documentation. No CLA,
no copyright assignment.

## Security

**Do not open a public issue for a security problem in the geoDB implementation.**
Email **security@geodb.io** (or **support@geodb.io** as a fallback).
[`SECURITY.md`](SECURITY.md) has what to include, what is in scope, and our
disclosure window.

Issues about the *specification's* security properties — a design that cannot be
implemented safely, an access-control model with a hole in it, a scoping rule that
does not compose — are ordinary public issues and are very welcome.
