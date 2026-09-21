---
name: "This is wrong"
about: The spec says one thing and the implementation does another, or the modelling is simply bad.
title: "[wrong] "
labels: wrong
assignees: ''
---

Two kinds both belong here: the spec and the running API disagree, or the spec is
internally coherent and still models the world badly.

## What you called

- **operationId, path, or schema file:** <!-- e.g. operationId `api_v2_assays_list`, GET /api/v2/assays/ -->
- **Spec version or commit:** <!-- the `version` from spec/openapi.yaml, a release tag, or a commit sha -->
- **Client:** <!-- geodb-client x.y.z, curl, generated from the OpenAPI document, other -->

## What you expected

<!-- Quote the line of the spec you were reading, if the spec is the source of your expectation. -->

## What you got

```
```

<!-- Status code and response body. Redact any access token. -->

## Why you think this is the spec's fault rather than yours

<!-- Optional. "I am not sure which end is wrong" is a legitimate issue. -->

---

- [ ] This report contains no customer data. Identifiers, coordinates, assay
      values, and file names are either mine to share, or replaced with
      realistically shaped placeholders.
