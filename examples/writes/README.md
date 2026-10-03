# Write examples — one per intent

> **Staff only for now.** geoDB's production servers serve the write half to
> geoDB staff connections only while API writing opens (any other key is
> refused `writes_staff_only` — the public demo write key too, until then);
> these run against a server that accepts your key's writes.

**Read [AGENTS.md](../../AGENTS.md), "Managing data", first** — these examples
show the calls; the rules they follow are stated there. Three you must not
skip:

- **Sets.** Every interval or sample row belongs to a set. When the user has
  not said which, ASK — a write that names none is refused `set_required`, and
  the answer lists the project's sets. Create a new set only when the user
  asked for one (or for a derived interpretation).
- **Ask before changing what exists.** `upsert`, `update`, `retract`,
  `restore` and `make_default_set` change the user's data: dry-run, show the
  user what will change, send it only after their yes.
- **Coordinates carry their `epsg`.** Never pre-convert.

```bash
export GEODB_BASE_URL=https://api.geodb.io
export GEODB_WRITE_TOKEN=<a key that may write records>
python examples/writes/run_writes.py          # or one: python examples/writes/retract.py
```

| Example | Intent | Shows |
|---|---|---|
| `create.py` | `create` | describe → dry run → write; a retry replays (`Idempotency-Key`); a re-sent `external_id` is `unchanged`; a conflicting create is `skipped` with both values |
| `upsert.py` | `upsert` | new rows created, existing ones changed only in the fields sent — after a dry run the user has seen |
| `update.py` | `update` | change a record by its geoDB `id`; nothing else moves |
| `retract.py` | `retract` | the dry run's `cascade`; refused without `"confirm": "retract"`; then sent |
| `restore.py` | `restore` | a retract brought back by its `write_id` |
| `undo.py` | `undo` | `undo_stale` on a row changed since, the write log, undo newest-first, `already_undone` |
| `make_default_set.py` | `make_default_set` | the person-key-only rule (a vendor key is refused) and the dry-run `confirm` |

Every example names its rows `<INTENT>-<run>` and undoes what it wrote,
newest first. The rules they follow are in [AGENTS.md](../../AGENTS.md),
"Managing data".
