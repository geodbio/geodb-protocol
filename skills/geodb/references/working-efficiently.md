# Working efficiently: large reads and imports

Read counts first, reference records whole and data records only filtered; check a load with its dry run (one dataset for several record types), never with an export; a worked lab-certificate load.

### Reading efficiently: counts first, references whole, data filtered

A project can hold millions of rows and a page holds at most a few thousand,
so read what answers the question, never a copy of the database.

1. **Counts first.** `record-counts/?project=<id>` answers in one small read
   how many records of each type the project holds (`counts`: `live`, plus
   `in_trash` for a key that acts as a person), which tables are company-wide
   (`company_wide`) and what this key cannot read (`not_readable`). A type at
   0 needs no overlap check; a large one is never paged whole.
2. **Reference records: read them whole.** They are small and every data
   record names them: `laboratories/`, `methods/` (each with its `elements`:
   `element`, `units`, `detection_limit`), `certificates/` (`result_count` is
   how many values a job holds, `alt_certificate_numbers` the other numbers it
   goes by), `standards/`, and the sets and choice lists
   `records/describe/<Model>/` names. Add `include_trashed=true` (a key that
   acts as a person) to see the Trash too: such a row carries `in_trash: true`
   and a `trash` object: the removal that put it there (`audit_batch_id`),
   what that removal took, and the `restore` request that brings it back.
3. **Data records: read them filtered,** never whole: `name=` (several names,
   comma-separated) on the sample and collar lists, on `assays/` and
   `assay-results/` (by sample name) and on every reference list; `bhid=`
   (several holes, comma-separated) on drill samples and every downhole list;
   `certificate=` on `assays/`; `set=` on interval and sample lists. In a
   project with several sampling sets a drill-sample read needs `set=<id>` or
   `set=all`, even by name. A QC sample's `name=` also finds the lab's bare id
   (geoDB stores a laboratory QC name decorated with its job). `compact=1`
   gives flat rows where a list takes it; a page holds 100 rows unless you ask,
   500 at most (2,000 on `assay-results/` and on lean `drill-samples/` pages).
4. **A whole-table export is for ANALYSING the whole table** (statistics, a
   model, a chart over everything): one file (the client's `export()`, or
   `export_link`), never page after page. Never export a table to check an
   import: the write's dry run answers that.

### Writing many records: the dry run decides

- **The dry run is the authority.** It matches every row against what is
  stored (identity, the Trash, the sample each lab value belongs to, lab QC
  names included, the method's units and detection limits) and answers what
  the write would do. Never rebuild the project in your sandbox to predict
  that, and never export a table to check an import.
- **First pass: the framework, not the data.** Before any data row, check that
  the parents exist and agree: laboratories, methods with their elements,
  units and detection limits, certificates, standards, the set. Read data
  records only to settle one specific doubt, by name (a dozen names, never the
  table).
- **Several record types that depend on one another go as ONE dataset**
  (`"model": "Dataset"` on the records endpoint; `records/describe/Dataset/`
  is its contract): upload one CSV per record type, rehearse them together (a
  parent in one file exists when its children are checked), then write after
  the user's yes, under one Undo. ONE file per record type: when the rows of
  one type mix new records with ones already stored (values to add to a loaded
  job beside new jobs), send that file with `"intent": "upsert"` (a create
  skips what exists). Section `assay-load` of this topic walks through one.
- **Order:** parents first. `records/describe/<Model>/` gives `land_order`
  (`parents`, `order`); a dataset orders its files itself.
- **Report the Trash as it is.** A row that meets a trashed record with the
  same identity warns `record_in_trash`: writing it makes a second record
  beside the trashed one. A row whose parent is only in the Trash is refused
  `parent_trashed`, naming the parent. Either way tell the user and ask
  whether to restore it; never restore it, or re-create it, unasked. To
  restore: the record's `trash` (an `include_trashed=true` read, or the
  refusal's parent) holds the `restore` request; dry run it, show the user
  every record it brings back (a restore returns the whole removal, which may
  hold other records), then send it after their yes. A record removed without
  a batch record has no such request: the web Trash restores it.
- **Show the user the answer, not your own tally:** the counts, every
  exception and warning, `before_writing`; then wait for their yes.

### Worked example: loading laboratory certificates

**Who parses.** You do, in your own sandbox: geoDB keeps no parser for each
laboratory's report formats on this surface. Read each report (a spreadsheet
export, a CSV, a PDF) into long-form rows: one per sample, element and method,
the value as the lab reported it (below detection is `-1`, its limit kept on
the method: guide topic `assay-values`), its units and its certificate. If the
user would rather not, geoDB's own assistant on the web reads certificates
itself.

1. **The framework, in a handful of reads.**
   - `certificates/?project=<id>&name=<job>,<job>`: which jobs are loaded
     already (`result_count`, `alt_certificate_numbers`). Read assays only for
     a job already loaded: `assays/?project=<id>&certificate=<job>`.
   - `methods/?project=<id>`: each method's elements, units and detection
     limits, against the reports (a different unit or a missing limit is the
     user's call).
   - `laboratories/` and `standards/` (the reference materials the QC rows
     name), each with `include_trashed=true`.
   - A job billed to another client or project (the report's header says):
     spot-check a dozen of its sample names
     (`drill-samples/?project=<id>&set=all&name=<a>,<b>`, then `point-samples/`
     and `qc-samples/` the same way); if none is in this project, ask the user
     before loading it.
2. **One CSV per record type,** its header the fields
   `records/describe/<Model>/` lists: `Laboratory`, `Method` (one row per
   method and element, with `units` and `detection_limit`), `Certificate`,
   `Standard` and `QCSample` when they are new, and `Assay` (one row per
   value, each certificate's rows together). Upload each as a document (a
   multipart POST to `documents/`: `project`, `document` = the CSV file,
   `category` `OT`) and keep each id.
3. **Rehearse:** POST to the records endpoint `{"model": "Dataset", "intent":
   "create", "project": <id>, "dry_run": true, "dataset": {"members":
   [{"document": <id>, "model": "Method"}, …]}}`, with `qc_mapping` (per
   certificate) when assay rows carry lab QC: a list, one entry per
   certificate, each marker named as its rows name it with its kind (the
   rows' `qc_type`: STD, BLK or DUP), runs and a duplicate's parent;
   `records/describe/Assay/` gives the shape and an example. A laboratory
   reuses its blank and standard names on every job: list them under each
   certificate. Up to 5,000 rows (and 8 MiB of files) answer
   at once; a larger dataset answers 202 with a `dataset.poll` path (absolute,
   on this host): GET it after its `Retry-After` seconds until `status` is
   `done` (the answer is its `result`).
4. **Show the user the answer.** Per file: the counts, and `exceptions` and
   `warnings` by code with each row's file `line`. For the Assay file, its
   `assay` block: values `linked` to samples by kind (drill, point, QC),
   certificates with something to decide (values already loaded, replaced or
   withheld), `unit_mismatches`, `missing_detection_limits` (by method and
   element), `waiting_for_sample` (values whose sample is not in geoDB yet).
   Then `before_writing`; the full list is `detail.download`. Nothing is
   written yet.
5. **After the user's yes,** send the answer's `write` body exactly as it
   came. Each file commits in turn, re-checked against what was approved; a
   file that would land differently stops the write, and the answer names
   what landed and what did not (`stopped`; `rehearse_rest` rehearses the
   rest). One `write_id` undoes the whole dataset.
6. **Attach each certificate's PDF** to its certificate: a document upload
   with `attach_to` `{"model": "Certificate", "id": <id>}`.

**With geodb-client 0.3.5 or later:** `record_counts(project)`;
`plan = validate_dataset(project, {"Method": methods_df, "Certificate":
certs_df, "Assay": assays_df})` uploads the files and rehearses;
`plan.summary()` is the text to show; `done = plan.write()` after the yes;
`done.undo()`; after a stop, `done.rehearse_rest()`; and
`upload_document(path, project, attach_to={"model": "Certificate", "id":
<id>})`. With an older client, make the HTTP calls above from your code with
the session key.
