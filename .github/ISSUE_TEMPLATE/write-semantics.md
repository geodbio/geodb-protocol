---
name: "Write semantics proposal"
about: How writing back should work — identity, idempotency, conflicts, refusals, reversibility.
title: "[write] "
labels: write-semantics
assignees: ''
---

The protocol reads today. The write contract is the open problem, and it is the
thing we most want outside constraints on **before** it is written rather than
after. If you would have to implement this side, this is your template.

## The write you need to make

<!-- What records, from what system, how often, and what triggers them. -->

## Identity

<!-- How do you name a record so a retry, a re-run, or a correction six months later
     lands on the same row? What identifier do you own and control? -->

## Idempotency and retries

<!-- What does your side do when a response never arrives? -->

## Conflicts

<!-- The row exists and differs from yours. What is the correct outcome for your
     workflow: refuse, supersede, branch, something else? -->

## Refusal

<!-- What does a refused write have to tell you for your side to do something
     sensible with it — per row, per request, or both? -->

## Reversibility

<!-- Reversibility is our acceptance criterion for the write half. What would undo
     mean in your workflow, and who would press it? -->

## Constraints we would get wrong if you did not tell us

<!-- Regulatory, contractual, instrument, or lab constraints on what you may send. -->

## Context

- **Spec version or commit:** <!-- the `version` from spec/openapi.yaml, a release tag, or a commit sha -->
- **Existing read integration?** <!-- yes/no — and which operations, if yes -->

---

- [ ] This report contains no customer data. Identifiers, coordinates, assay
      values, and file names are either mine to share, or replaced with
      realistically shaped placeholders.
