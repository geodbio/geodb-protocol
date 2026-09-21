---
name: "This is ambiguous"
about: Two implementers could read the same field or endpoint two different ways.
title: "[ambiguous] "
labels: ambiguous
assignees: ''
---

Ambiguity in a spec becomes divergence in the wild, so these are the highest-value
reports we get. Tell us where two readings are both defensible.

## Where

- **File and field, or operationId:** <!-- e.g. schemas/collar.json -> `epsg`, or operationId `api_v2_drill_collars_list` -->
- **Spec version or commit:** <!-- the `version` from spec/openapi.yaml, a release tag, or a commit sha -->

## The two readings

1. <!-- What one implementer would build -->
2. <!-- What another would build, equally justified by the current text -->

## Which one you implemented, and why

<!-- Including "we guessed" is a fine answer and a useful data point. -->

## What it would cost to get it wrong

<!-- Silent bad data, a failed import, a wrong number in a report — whatever applies. -->

## Anything else

<!-- A small worked example helps. You do not need to propose a fix. -->

---

- [ ] This report contains no customer data. Identifiers, coordinates, assay
      values, and file names are either mine to share, or replaced with
      realistically shaped placeholders.
