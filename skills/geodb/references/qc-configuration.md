# "QC configuration: blank limits, duplicate limits, excluded elements and approval"

The project's QC judging settings beside its protocol: per-element blank warning limits, per-element duplicate RPD limits, the elements left out of pass rates, and whether results wait for a QAQC review before anything serves them; who may change each, and what a change does.

### What the QC configuration controls

Beside its protocol, every project has one set of QC judging settings:

- **Blank warning limits**, per element (optionally per method, in the units
  of that element's results): a blank above its limit fails. A limit is
  either set by hand or derived from the blank material's background
  (background times a multiplier, five by default); changing the background
  or multiplier re-derives a derived limit, while a hand-set limit changes
  only when a new limit is given. With no limit for an element, a blank the
  laboratory reported below detection passes (it is clean), while a blank
  with a detected value cannot be judged: its verdict is unknown, which is
  missing configuration, not a clean blank.
- **Duplicate RPD limits**, per element, replacing the default relative
  difference a duplicate pair may show.
- **Elements left out of pass rates**: their QC results are still recorded
  and shown, but do not count towards a certificate's pass rate.
- **Results wait for QAQC approval**: when on, a certificate's results are
  held back from reads, maps and connected tools until a person has reviewed
  the certificate. Exports and the ODBC tables follow the merge settings' QAQC
  export mode instead: exclude (the held-back results stay out), include with
  status (every result, with a column saying its QC status) or include all
  (every result, no status column) — so an export can carry results still
  awaiting review.

### Who may change it

Each part needs the permission of its area, as on the web: blank warning
limits need the QAQC approval permission; duplicate limits and excluded
elements need the permission to run QAQC; whether results wait for approval
needs the permission to manage the project's settings.

### What a change does

Every one of these settings moves verdicts or what is served: a new or
changed blank limit re-judges blanks, an excluded element changes pass
rates, and turning approval on holds back results that were being served.
The change is shown before it is made, with the certificates already
reviewed that it reaches; review decisions are never changed by it. A
removed blank limit is kept in the Trash and can be put back.

### Changing it through the API

On the records endpoint the QC configuration is a settings model
grant-context lists under `writes.settings_models`, with the intent update
only: one per project, named by the project. Blank warning limits are its
parts, each with an `action` (add, change or remove) and named by its id or
element. Read its describe contract first. The dry run answers `verdicts`
and a `confirm` value: show the user both and send the update with that
`confirm` only after their yes. Every write can be undone. The settings in
force are read at `qc-configuration/`.
