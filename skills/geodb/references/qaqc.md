# QAQC: reading geoDB's QC verdicts honestly

How geoDB judges standards, blanks and duplicates, what a rejection or a deleted certificate hides, and the traps that make a capable model get QC wrong.

geoDB judges every QC reading (each standard, blank and duplicate) with ONE
verdict engine; the project's QC dashboard and each certificate's QAQC page
show its verdicts. **Read those verdicts; never compute your own and present it
as the answer** — a pass rate that differs from the page is a trust failure,
however competent the arithmetic. If the evidence makes you think a verdict is
wrong (a certified value that looks mistyped, a mistagged CRM, a unit
mismatch), **say so, show why, and leave the call to the geologist**: geoDB's
verdict stays the verdict of record until the data or configuration it was
judged on changes.

⭐ **The certificate page already draws the charts and EXPORTS them — send
people there before plotting by hand.** A **Value / Z-score toggle** (the
reader's choice is remembered); in Z mode the standards tab draws ONE
**overlay** per element with every CRM on shared ±2/±3 bands — the answer to
"all my standards on one chart". Its **XLSX / PDF export** carries **real Excel
charts, not pictures** — restylable, pasteable into a report.

⚠️ **"Z-score plot" in a QC context means CRM performance against certified
values** — what the page draws. If the ask could mean routine SAMPLE GRADES
standardised, ASK which; only one of them has an acceptance band.

⛔ **Never invent a threshold.** Every number you assert must come from the
industry QAQC guidance, a certificate's own fields (certified value, its SDs,
the method's detection limit) or the project's configured limits — otherwise
say plainly that the guidance doesn't give one. The recorded failure: a
competent hand-rolled Z-score analysis that **invented a ±10% bias threshold**
for CRMs with no certified SD, narrated as authoritative while the verdict
engine already owned those rules.

**A QC row the user cannot find is far more often HIDDEN than missing.**
`Assay` and `QCSample` carry `qaqc_excluded` — set when the parent
certificate's QAQC review is rejected — and the web grids hide those
rows by default (the QC Samples page's "Show Rejected" is the user's switch).
Whether a data read returns them depends on how it asks.
**Quick Log does not filter on it**, so one project legitimately shows more QC
rows in Quick Log than under Assay Data → QC Samples. ⛔ *"Those samples
aren't in the database"* is the wrong answer and the one you will reach for:
before ANY absence claim about QC rows, read them again with rejected rows
included.

**A count mismatch between two screens is a SIGNAL to check this flag, not a
bug to report.** Then name *which certificate was rejected and when*, so the
number they are staring at has a cause.

**What a read withholds, and how it says so.** Four kinds of row are held
back from results by default, and a good answer names them instead of
treating the gap as missing data:

1. **Results from a REJECTED certificate** — the lab job failed QAQC review.
2. **Results from a SUPERSEDED certificate** — the job was replaced by a
   re-assay; the newer certificate carries the live values, and each
   certificate names the one it replaced or was replaced by.
3. **Soft-deleted records** — deleted on the server, recoverable there; a list
   reports them by id and by count, never as rows.
4. **Below-detection values** are NOT withheld but are not grades either: the
   laboratory's "<DL" is stored as the sentinel `-1` with an explicit
   below-detection flag beside it, and the value's detection limit is the
   threshold. A merged read has already substituted it once (half the
   detection limit by default) — never substitute it again, and never average
   the sentinel.

Every list states what its default left out as counts. Ask for the
QAQC-withheld rows to be included and each one comes back flagged as excluded,
with the reason and the certificate behind it. So when a user asks *"why are
these samples missing from the pass rate?"*, read the withheld rows and the
certificates' review state, then answer with the cause: **which certificate
was rejected or superseded**, and what replaced it. Never report a flagged
row's value as a result — it is shown so you can explain its absence — and
never treat a rejection as something to overturn: report the state, and leave
the review decision to the geologist.

**geoDB's verdicts are a read, row by row.** Each QC reading (standard,
blank, duplicate) comes back judged exactly as its certificate's QAQC page
judges it: `pass` / `warn` / `fail`, or `unknown` when no acceptance
criterion resolved (neither a pass nor a fail — say how many), with the
measured and expected values, the Z-score and bias for standards, and the
threshold that judged it. Each certificate carries its pass rates, how many
readings could be judged, and the stored review decision. A project-wide read
leaves out certificates a review rejected or superseded and LISTS them, so a
pass rate is over the certificates in use — name them when you report it. A
per-CRM summary answers "how is this standard performing". Quote these
numbers; never recompute a pass rate, and if you disagree, say why.

**Working through a project's QAQC, from geoDB's reads.** Read in this order,
and report what the reads say before anything of your own:

1. **The QC rules in force** (`qc-configuration/`) — the thresholds, the blank limits per element,
   the duplicate criteria, the elements left out of pass rates. A blank with
   no limit for an element is judged `unknown` there: missing configuration,
   not a clean blank.
2. **The verdicts per insertion**, per certificate. Each standards row says
   the method's detection limit, whether the reading was below it, and
   whether the CRM is certified at or below that limit — such a reading reads
   `unknown`, correctly: the method cannot resolve that element on that
   standard, so it never gets an accuracy verdict (a DETECTED value on such a
   CRM is still judged). A standards reading with no CRM linked, or linked to
   a CRM holding no certified value, gets NO verdict row; the read lists it as
   withheld with the reason — name it, never count it as a pass or a fail.
3. **The CRM library as the project uses it** — certified values per method
   (value, units, SD) beside the detection limit each assay method has here,
   with two named states: `no_certified_values` and
   `certified_below_method_dl`. A state explains readings that are never
   judged; it is not a laboratory failure. ⚠️ A CRM's certified method and
   an assay's method are DIFFERENT records (the CRM certificate's chemistry vs
   the laboratory's method): match them on digestion and finish, never on
   their ids — differing ids are not a mismatch.
4. **The planned sequence beside the field record** — each hole's cut-sheet
   lists the planned slots in order and, beside each, what is recorded today
   (the QC type, the CRM tag, the certificate its result came from, whether a
   review withholds it). Where the plan, the record and the result's
   chemistry disagree, suspect a swapped or mistyped bag before a lab problem.
5. **Duplicate pairs** are verdict rows with their parent sample, both values
   and the test that judged them; **name collisions** (one name held by two
   kinds of sample) and **withheld rows** (rejected or superseded
   certificates) each have their own read.

Then tell the user what needs attention, each finding with the evidence (the
rows, the chemistry, the state), and what they could do about it. Changing
anything is their call.

**Changing QAQC data: only when the user asks, and never a verdict on your
own initiative.** What can change, each on the user's explicit request, each
shown to them first as a dry run, each undoable:

- **Retype a QC sample** — an update to its `qc_type` (the QC field; never
  `sample_type`). **Retag a standard's CRM** — an update to its `standard`.
  A field duplicate's parent is `ds_duplicate`.
- **Reconnect a QC sample to its withdrawn result** — when a deleted
  certificate left the QC sample standing with no visible result. A
  rejected certificate's QC is not a reconnect: its result is withheld by
  the review, which is a verdict question.
- **A certificate's verdict** — approve, conditionally approve, reject, set
  back to pending, or link the certificate that re-assayed it. This is the
  geologist's decision, made through their own key: never propose one, never
  infer one from your own analysis, never fold one into another change. When
  the user explicitly asks, run it as a dry run, show them each certificate's
  verdict now and after and how many results that withholds or brings back,
  wait for their yes, then send it with the confirm value the dry run
  returned. A field that records the review decision (a row's
  withheld-by-review flag) is never written as a field. Un-rejecting a
  certificate whose sample names another certificate now holds is refused,
  naming the samples: ask the user which certificate is right.

The verdict write is one record per certificate on the certificate record
type: `"certificate"` (its name or id), `"status"` (`approved`,
`conditional`, `rejected` or `pending`), optionally `"notes"` and
`"reassay_certificate"` (the name or id of the certificate that re-assayed
it, or null to unlink). Its dry run returns the `"confirm"` value the real
write sends.

If you disagree with a verdict, say so and show why; the verdict stays
geoDB's until the user changes it. Every change can be undone by its write
id; say so when you report it.

⚠️ **Deleting a certificate DOES take its assays — and leaves its QC samples
standing.** A certificate delete cascades to its assays, its QAQC approval and
its saved QC charts. `QCSample` is deliberately NOT in it: the
QC sample is the PARENT of the QC chain (a bag of material actually inserted in
the field) and the assay is only one lab's result for it, so deleting the bag
because a result was withdrawn would destroy the record that QC *was* inserted
and corrupt the insertion rate. Net effect the user sees: the QC sample
survives with **no visible result**, because its result went with the
certificate. Report it that way — the values are recoverable from the Trash,
not lost, and the result can be reconnected.

⛔ **Two ERAS of this, and a row can be in either — check, don't assume.**
An earlier web-grid delete soft-deleted the certificate ALONE, orphaning live
`Assay` rows under a deleted parent: the user saw results but could not find
the certificate, and a re-import was refused as a duplicate against rows they
could not trace. That is fixed and the orphans were repaired — so say "was",
not "is", and resolve the actual row (deleted rows included) before
explaining. Never say the record is gone.

⭐ **An INVENTORY that mentions deleted rows must COUNT them, per model.** A
default read returns live rows only. So when the user says *"include
soft-deleted"* (a cleanup ask — they are deciding what to restore or purge),
count each model twice, live and with deleted rows included, and report the
pair. ⛔ **NEVER infer a deleted count**, and never attribute one to a
"trash ledger" or any other source you did not read — there is no such readable
source, and a confident wrong zero is worse than "I did not check". If a
model's deleted rows genuinely cannot be reached, say which model and stop. (The recorded
failure: an inventory that reported no deleted QC when several had been — exactly
the rows the cleanup was about.)

⛔ **Read the type from `qc_type`, NEVER `sample_type`.** `qc_type` (the QC
type: `.name`, `.category`) is what every verdict reads. `sample_type` is a
frozen legacy column, used only as a fallback when
`qc_type` is empty — and its enum has **no Field
Duplicate code**, so a correctly-typed row reads EMPTY there. Reporting
"N untyped QC rows" off `sample_type` invents a cleanup the user cannot do.

⚠️ **A LAB duplicate has no client-side parent — correct, not a gap.**
`ds_duplicate`/`ps_duplicate` name the field sample a duplicate was split from;
a lab re-running its own pulp (type `DLB`) has none, and its RPD comes from the
lab's paired values. Only a FIELD duplicate with a NULL parent is a finding.
Split field from lab before reporting on linkage.

⭐ **Compare the PLANNED sequence with the FIELD sequence.** A generated
cutsheet plans which QC type is due at which slot in a hole's sample sequence
(one standard every N samples, and so on); its rows are
*Planned* until collected and are never QC data — never counted, never judged.
What the field crew actually bagged is the field record. They can differ, and
when they do the field record is the truth about what was inserted — but a slot
where the plan, the recorded `qc_type` and the result's chemistry disagree is
the strongest evidence of a swapped bag or a mistyped row. Check that before
calling a QC reading a lab failure.

⚠️ **Hunting misplaced QC (a blank or standard swapped with a sample): never one
element, never one direction.** A blank has a chemistry SIGNATURE — take it
from this project's PASSING blanks across several majors (a carbonate blank:
very high Ca, very low Al and Fe) — and a standard's is its certified values.
Then test BOTH ways: registered QC whose result reads like rock, AND drill
samples whose result reads like the blank or a standard (the dangerous half — a
standard there reads as grade). Report per hole, from that check only; never
extrapolate a count.

⛔ **Rejected is a STATE, not a verdict to re-litigate.** Report it and stop:
never imply the data is bad, never propose clearing the flag, never re-judge
the certificate.

#### Rejection is judged PER VALUE, not per row

⭐ **A rejection has a ROW half and a VALUE half.** A sample row is
keyed `(name, project)` and ACCUMULATES values across lab jobs; every value
carries its OWN certificate — **the job that PRODUCED it**, which is NOT
always the row's certificate (the job that CREATED the row). They differ on any
row a second lab landed onto. ⛔ Never "fix" one to match the other.

So *"is this showing?"* has two answers, and you must give the right one:

* **The ROW** flips `qaqc_excluded` only when EVERY value on it is from a
  rejected job. A row that still holds one live value STAYS VISIBLE.
* **The VALUE** from a rejected job is hidden on that surviving row — in QAQC,
  merged reads, exports, map, 3D and cert-scoped dataroom views.

⇒ Rejecting lab A's certificate does not take lab B's values down with it,
and rejecting lab B is not a no-op.

**What this changes in your answers.** A user who says *"I rejected that cert
and my other lab's numbers vanished"* is describing OLD behaviour — say it was
fixed, not that they are mistaken. A user who says *"I rejected it and the row
is still there"* is seeing the rule work: the row survived because another job's
value on it is live. Name **which job** is still live, from each value's OWN
certificate — never the row header; quoting the header as the source of a value
is the exact wrong answer that column exists to prevent.

⚠️ **Older values can carry the ROW's certificate**: values landed before
per-value provenance existed were back-filled from the row. On such a merged
row a second lab's values therefore still read as the first lab's job until
that job is re-landed. Say so plainly when provenance looks wrong on old data — it is a
known limit of the back-fill, not a bug and not the user misremembering.

⭐ **A cert-scoped view keeps its OWN values even when rejected** — a rejected
certificate's page must still show why it was rejected. That is deliberate;
do not report it as a leak.

#### One QC name, several certificates — the collision you WILL be asked about

Labs reuse house QC names (a granite blank, a standard blank, a CRM code) on
**every** certificate, often twice on one. `Assay` allows one ACTIVE row per
`(name, project)`, so those names collide.

**This is handled — the certificate imports.** A repeating QC name is stored
tagged with its certificate number (`<cert>_<QC name>`, then `…_2`), by ONE rule
shared by every import path. Both certificates keep their own specimen; nothing
is dropped or overwritten. Say the names were tagged — never that anything was
refused.

⛔ **A repeated ROUTINE sample name DOES still refuse the file, and should.**
The same field sample on two certificates is a re-assay decision only the
customer can make. Rejecting the superseded certificate frees the name — but
ONLY when it truly is superseded. If both jobs are wanted, do not reject: that
excludes data they need (it can mean excluding a whole live certificate). Never advise it for a QC-name collision.

### REJECTION — what it changes, where rows go, and what the user still holds

**Mechanics, per model (one rejection, three different effects):**
- `Assay` rows on the cert → `qaqc_excluded=True`. Values hidden per LAB JOB
  where a row carries a second lab's value (the row stays live).
- `DrillSample` / `PointSample` (primaries) → `assay` link set to **NULL** and
  `lab_status` stepped back **AN → SU** ("Submitted — awaiting results"). A
  rejected primary with no assay and `lab_status='SU'` is the EXPECTED state,
  not a sync failure. The re-assay's certificate re-links it by name through
  the ordinary import path and the status returns to AN on its own.
- `QCSample` → `qaqc_excluded=True` and it **KEEPS** its link to the assay (the audit
  chain back to the failed cert). Un-rejecting clears the flags but never
  re-links a primary. A re-imported QC keeps its lab name — rejected names are
  reclaimable (a rejected row does not hold the name) — so after a re-assay one name
  can legitimately be TWO rows: one rejected, one live.

**Where rejected rows are HIDDEN vs SHOWN — say which, never "gone":**
- HIDDEN by default: the Assay and QC Samples grids (**"Show Rejected (N)"** —
  the button carries the number; if it reads a plain "Show Rejected", nothing
  is hidden on that page), every export (ODBC / XLSX / CSV — no toggle exists
  there), the sample inventory, QC Health /
  unlinked-QC lists, the QC data-issues scan, project QAQC aggregates, and the
  report's "N QC samples" line.
- SHOWN: the Quick Log roster (full working roster by design; the row wears a
  **REJECTED CERT** badge), the certificate's OWN QAQC page (its rejected rows
  are the point), Trash, backups, billing counts.
- COUNTED as nothing: both insertion-rate counters skip rejected QC. A
  "Standard is DUE" prompt appearing right after a rejection is CORRECT — the
  rejected standard is no longer credit — not a bug to report.

**What the user physically holds — ask, never assume.** A rejection is about
the LAB RESULT, not the sample. Whether the company still has the **reject**
(the 1–3 kg not selected for assay) or the **pulp** (ground, unused) is NOT
recorded anywhere; labs return them sometimes, and it differs by lab and
contract. Two re-assay routes both end in a new certificate import: the lab
re-runs the pulps it holds, or the company ships returned rejects/pulps (to
the same lab or another). Standards, blanks and lab QC are consumables — a
re-run inserts fresh ones, so their rejected rows are audit-chain and are
never re-shipped. A **field duplicate is the one QC that is a company bag**;
it follows its parent primary in every respect.

**The reply shape for "where did my QC go":** name the certificate and the
rejection date, point at the grid's "Show Rejected (N)" button, say what the
counters now do, and stop. Two related behaviours are by design — describe
them, never call them gaps. The mobile pack scan answers a rejected QC
bag's barcode with *"matches QC sample X from a rejected certificate —
not active inventory"* and counts only LIVE rows as duplicates (a re-assay's
live twin is not a duplicate of its rejected twin). The classic cert-import
QC step RECLAIMS a name held only by a rejected certificate's QC row: the
confirm page flags the row and names that certificate before anything is
written, the checkbox stays the user's, and the result lists every skipped
(live-duplicate) and every reclaimed name. Nothing is skipped silently.

- **The verdict engine.** Standards: |z|≤2 pass / ≤3 warn / >3 fail; a bias
  fallback (10%/15%) only when no SD is usable; a |bias|>50% ceiling fails a
  row even at low z (a per-project QC setting) but is
  only consulted where z said pass. ⭐ **A CRM certified at or below the
  method's detection limit cannot get an accuracy verdict from that method:**
  the method cannot resolve that element on that standard, so a
  below-detection reading is the CORRECT result and the row reads `'unknown'`
  — never `'fail'`, never `'pass'` (a reading that comes back above the DL is
  judged on z and bias as usual). Only that physically impossible pair is
  excused; a below-detection reading of a value the method CAN resolve is
  still a real failure.
  Duplicates: a TWO-REGIME verdict — both results ≥
  the project's duplicate DL multiple × DL ⇒ RPD against the tier threshold
  (field 20%/30%, **coarse 20%/30% on its own rung**, pulp+lab 10%/15%);
  either result below ⇒ an **absolute** test, fail only if `|a−b| > 1 × DL`
  (warn to 1.5× that). That multiple is **unset-means-5×** — the
  floor ships ON, the opposite convention to the blank multiple, because it
  can only ever REMOVE failures; `0` switches it off. A **never-stricter
  guard** takes the more permissive of the two tests in the absolute regime,
  so the floor can only rescue a pair and raising the multiple is monotone.
  The per-element project override is resolved AFTER the tier: it tightens
  any tier and may loosen only field. Blanks: a THRESHOLD LADDER — (1) the
  linked certified blank's supplier `<` bound, (2) a per-element blank warning
  limit (element match case-robust, exact case wins), (3)
  the project's blank DL multiple × detection limit, **unset by default, and
  unset means skip the rung**, (4) nothing ⇒ **`'unknown'`, never `'pass'`**;
  warn band still threshold × 1.5. Each row carries `threshold_source` +
  `threshold_reason` so the page can say which rung answered — and duplicate
  rows carry the same pair plus `duplicate_regime`, because two rows in one
  table can be judged by different statistics. No trending/consecutive rules
  exist; every verdict is per-row and stateless.
  ⭐ **A BLANK MAY CARRY A CRM** (certified blanks are real products; the link is
  permitted everywhere). It
  changes no verdict: the row stays on the blank ladder and the CRM feeds
  **rung 1 only**, the supplier `<` bound. No certified-value verdict, no
  Z-score — for that the user RETYPES the row to a standard, their call. Never
  imply the link did more than it did.
  ⛔ Near-DL duplicate pairs are RE-JUDGED, never dropped.
- **One DOCUMENTED divergence — state it, never paper over it: two SD
  ladders.** The certificate page/approval resolves SD as 1SD →
  calc-SD (the batch's own scatter) → 2SD-derived → 0; the project-summary
  reads resolve 1SD → 2SD-derived → bias fallback. Deliberate and recorded.
  Consequence: the two surfaces can disagree for CRMs without a certified
  1SD. The calc-SD rung is unsupported by industry guidance — never
  *recommend* it (`qaqc_missing_certified_sd`).
- **Blanks read the same everywhere.** Every surface runs the same blank
  ladder, so an unjudgeable blank is `'unknown'` and EXCLUDED from the
  denominator everywhere. If blanks read all-`unknown`, that is missing
  configuration honestly reported — not clean blanks
  (`qaqc_blank_thresholds`).
- **Rows and statistics.** Certified values are method-matched (digestion +
  finish fingerprint); the detection limit is resolved onto standard, blank
  AND duplicate rows (duplicates carry both sides' limits and are judged
  against the coarser one). Blank and duplicate rows are born JUDGED, so no
  downstream consumer can invent a second verdict. RPD/HARD math; the BDL
  sentinel (both-BDL = agree, one-BDL = not evaluable — stated on the row).
  Insertion rate (min 3%, target 5%) + re-assay flags (<85% selective, <70%
  critical) + an evidence advisor that states on the approval page what the
  QC evidence supports (no QC at all, a missing QC type, a below-floor
  insertion rate, a category nothing could be judged in). Every approval
  snapshots that guidance onto the approval record.

  ⚠️ **GUIDANCE, NOT PROHIBITION.** Approval is never blocked and no reason is
  ever required — a company manager may approve any certificate they want to,
  including one with zero QC (many certificates carry none, especially
  historical imports). So an `approved` status is a manager's
  decision, NOT evidence that QC was present or passing. If asked whether a
  certificate's QC is good, do not read the approval status as the answer;
  the guidance snapshot on the approval records the evidence, and older
  approvals have none (they simply predate the guidance —
  never flag, question or re-open a signed-off certificate that did not flip
  pass↔fail). The page also draws control charts with certified asymmetric
  2SD/3SD bands, contamination and precision.

**Where the project's QC rules live: `qc-configuration/`.** Every threshold
the verdict engine applies can be set per project, so the industry defaults
are only defaults. One read returns the rules in force as geoDB resolves them
now: the standards Z and bias thresholds with the maximum-bias ceiling, the
blank and duplicate detection-limit multiples, the per-element blank warning
limits and duplicate RPD thresholds, the elements left out of pass rates, the
QC protocol's insertion intervals, and whether results wait for QAQC approval
before they are used. Read it before you explain a verdict or quote a limit,
and quote the project's value, not a default it may have overridden. An
element with no blank limit is judged `unknown` there: missing configuration,
not a clean blank. These rules are changed by the user on the project's QAQC
settings pages, never by a data write.

Your own analysis = **what the pages don't draw**. Frame every result as
analysis, never as the official verdict — and label every statistic (RPD =
exactly 2× HARD; mixing them silently doubles/halves every threshold).

**"How are my CRMs performing?" is ALWAYS the aggregate first** — one row per
(CRM, element, method comparability, unit) over the engine's OWN judged rows,
never a hand-built groupby over paged readings.

- **Unjudged readings are EXCLUDED from every z and bias statistic** — report
  them as *unjudged*, never as clean, and never describe a group by a mean z
  most of its readings never entered.
- **State coverage:** if the read covered only some certificates, say how many
  of how many — not the whole project.
- **Method comparability is part of the KEY** — one CRM on two methods is two
  populations. Never pool them.

**Reading it — guidance a QP weighs, never our verdict, and no threshold of
ours beyond the 2σ/3σ the engine already applied:**

- **A huge one-sided bias on nearly every reading** (mean z far past 3, nearly
  every reading the same sign — say +150 % on every insertion) is a **DATA question,
  not lab performance**: a wrong certified value on the library row, a
  mistagged CRM, or a unit mismatch. Say that FIRST, and have them check the
  CRM's own certificate against the library row and the QC rows' CRM tag
  **before** anyone questions the lab.
- **A moderate consistent bias** (mean z a few units, one sign) is EITHER a
  certified-value question OR a real lab bias. **Name both**, suggest comparing
  the CRM's certificate against the lab's own QC, and leave the call to the QP.
- **A small bias failing a TIGHT certified SD** (a few percent off, an SD of
  hundredths of a ppm) means the tolerance is tight, **not that the assays are
  bad** — say so plainly and point at the certificate's SD.
- **Both sides of zero with ~5 % past 2σ is NORMAL** — say so rather than
  hunting for a story.

**The rhythm:** aggregate → name the CRM(s) that stand out, with the reading
count, mean z, bias and which SD answered → the rows for that ONE CRM if they
want them → the certificate's QAQC page. Never a hand-rolled z, never a
threshold of our own; a read that failed is *"I couldn't read that just now"*,
never an absence claim.

1. **Ranked-HARD** (population precision, the 90/80/70 rule): per duplicate
   pair HARD = |a−b|/(a+b)×100; sort ascending, x = percentile rank, y =
   HARD; horizontal line y=10; the rule reads "pulp: 90% of pairs under 10%,
   coarse 80%, field 70%" — draw vertical guides at 90/80/70 and judge per
   duplicate TYPE, never pooled.
2. **Thompson–Howarth** (precision vs grade): sort pairs by pair-mean, group
   in 11s, x = group mean concentration, y = group MEDIAN |a−b|, log-log
   scatter + a ROBUST (median/Theil-Sen) fit — **never OLS** (outliers
   inflate the practical detection limit). Skewed-data bias is a known
   limitation — say so.
3. **CRM control chart** (the page draws per-certificate ones — and, in
   Z-score mode, an all-CRM overlay; a CROSS-certificate one is what is left
   as legitimate analysis): x = sequence (certificate date
   order), y = measured value for ONE (CRM, element, method); bands from the
   certificate's own `std_dev_2sd_low/high`, `std_dev_3sd_low/high` —
   **certified asymmetric bounds, not mean±k·(your SD)**. Same-side runs ≥2
   beyond 2SD = the 2-2s bias signal (`qaqc_westgard_consecutive_rules`).
4. **Q-Q original vs duplicate**: sorted originals vs sorted duplicates on
   a 1:1 line — distribution-level bias, insensitive to pairing errors.

Traps that void these analyses: apply the ×DL **line of significance** —
below ~5–10× detection limit, relative stats are noise; use an absolute test
(|a−b| vs 1–2× DL) instead of discarding pairs. BDL sentinels are −1 —
exclude via the same convention the engine uses, and say when you excluded.
Certified 2SD bounds are asymmetric — never symmetrize. And the standing
rule: **no invented thresholds.**

⛔ **A QC sample's `weight` has no unit column** — the number is stored bare. Quote
it as entered and say the unit is not recorded; never assume kg or g, never
convert it.

**Recommend a QC program from MEASURED project facts, never from
assumptions.** No methods or no assay data ⇒ say what's missing and gather
commodity, grade range, nugget character, lab + methods from the user instead.
Never invent a threshold (`qaqc_no_code_mandates_numbers`).

* **Achieved insertion rates** (`qaqc_insertion_rates`): QC counts per type
  (the QC type's `category`: BLN/BLB = blanks, STD/SLB = standards, DUP/DLB = dups) ÷
  primary counts, PER PERIOD — achieved ≠ planned is one of the commonest
  real findings; the data is the evidence, not the protocol document.
  ⛔ **Denominator = the SAME PERIOD's primaries, never the whole table.**
  Decades of legacy rows against one season's QC yields a fake ~0.1% that
  reads as protocol failure. Scope both sides or say you cannot.
* **Blanks with no limit** — the headline: the distinct (element, method,
  units) the blanks were read on, against the configured limits (per-method
  row, else the method-null fallback). Report it with the real numbers.
* **CRM coverage** (`qaqc_crm_selection`): Standards' certified grades vs
  the project grade distribution — bracket cut-off / average / ~P95; few
  CRMs with many results beats many with few.

**Draft blank limits** (`qaqc_blank_thresholds`), per (element, method),
precedence strict: **(1)** a certified blank's supplier limit where blank QC
links to one (the CRM's `<` value; the bound is in its detection limit) —
supplier limit BEATS a DL multiple; **(2)** else the method's detection limit
× N (default 10×) — a FLOOR, not a recommendation: a DL multiple can be
economically meaningless and mass-ratio can understate carry-over; say so and
name the QP. ⚠️ Draft these for the elements the blanks EXIST TO POLICE, never
across a whole multi-element scan — a barren blank legitimately carries
percent-level Na/Ca/Fe/Mg, thousands of times their DL (a global 10× floor
over a multi-element suite produces thousands of false warn/fail readings).
The project-wide alternative is the project's blank DL multiple (rung 3 of
the verdict ladder, unset by default = no floor) — offer it only when the
project's blanks and elements genuinely suit one number. **(3)** else LIST the
pair as "cannot draft — no detection limit on the method" (passing path: add
the DL on the method settings page). Never silently skip a pair. Units must be
the method's REPORTING units.

**The QC configuration's shape.** The QC protocol's intervals are "one every N
samples": CONVERT percentage targets to 1-in-N (5% ⇒ interval 20); there are
NO rate/percentage columns and NO umpire field (insertion shape: ~20% total,
~4–6% per type — `qaqc_insertion_rates`).

**The approved-certificates rule:** criteria changes — and updates to limits
whose pairs have readings on approved certificates — retroactively change how
APPROVED certificates read (verdicts recompute on read). geoDB refuses such a
change unless it names exactly the affected certificates as acknowledged; put
those names in front of the user and get a real yes first. Fresh limits don't
need that, but their preview states the measured impact (which approved certs,
how many previously auto-passed readings now judged, how many exceed) — show
it. Deleting limits or protocols, and touching verdict or approval rows, are
the QAQC settings pages' job, not a data write.

Two CRM catalogs, and the difference is what a stuck QC row usually turns on:

- **`Standard` / `StandardUnit`** — THIS company's CRMs. Company-scoped.
- **`CommonStandard` / `CommonStandardUnit`** — the GLOBAL, staff-curated
  library of commercial CRMs. The same rows for every customer, never
  company-filtered. ⚠️ The child's parent link is `common_standard`, **not**
  `standard`.

**When a QC standard marker will not resolve to a company `Standard`, look in
the library before telling anyone we do not have that CRM.** Most company
Standards match a library row by name — "we don't have it" is usually the
wrong answer, and it sends people off to key in certified values we hold.

⛔ **Match the name EXACTLY (case- and punctuation-insensitive). Never on a
substring, never fuzzily.** Many library names are substrings of a *different*
library row — two CRMs whose names differ only by a trailing letter carry
different certified values, and two same-supplier codes differing in a few
digits score highly similar. A wrong CRM does not fail loudly — it launders
into a passing Z-score. When the name is not an exact match, OFFER the
candidates and let the user choose; never pick one for them.

Copying a library CRM into the company is the library page's Import button
(Configure → Standards), or it happens automatically on import when a
certificate's CRM matches a library name exactly.
