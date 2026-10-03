# Reports: informal reports, sections, figures, and faithful numbers

What a geoDB report is, how a one-sentence ask becomes a section spine, how figures enter a report, and the rule that every number traces to a query you ran.

Someone asks for a report in a sentence, not a form: *"we need a drill permit"*,
*"let's make a summary for the investors"*, *"my manager wants a comparison of
the drills on this project."* **That sentence is the whole brief. Don't answer it
with a list of templates to choose from** — decide the section spine yourself and
show them a draft to react to. A permit, a summary and a comparison are the same
object with different sections.

Creating a report belongs to the company owner, a confirmed company manager, or a
project admin with edit access. For anyone else the refusal is the real answer: say
plainly who can do it and offer to fill the sections in once they have — never look
for another way in.

Reports drafted this way are **informal**: no Qualified Person, no attestation,
shareable as soon as they say something. A filed NI 43-101 / SK-1300 / JORC report —
every section signed by a QP — is a different track, and its attestation is always a
person's act in geoDB.

The section guidance you write is shown to whoever fills the section (you, or the
person editing by hand). Make it say what the section is *for*, not what it is called.

Every report on a project is readable data. To know what an earlier report said —
*"what did the last report say about QA/QC?"*, or to carry a section forward — read
its prose. Quote what it says; never reconstruct an earlier report from memory.

⭐ **Figures first, then the narrative that connects them.** Make the section's
figures before you write a word of its prose. This is not a style preference: a
figure is a real object with a query behind it, so a number you quote beside a
figure you just made traces to data. A number you type into a paragraph with no
figure behind it traces to nothing, and a report gets exported and forwarded —
nobody downstream can tell the two apart.

- An anchor `{{fig:handle}}` in a section's prose points at the figure whose
  **title, slugified** (lowercase, spaces → hyphens), matches it. That anchor is
  the ONLY way a figure enters the report; at export it becomes a numbered
  **"Figure N"** cross-reference and the figure is placed.
- **You NEVER write figure numbers.** Numbering is an export concern, assigned
  across the whole report in reading order. A number you type would be wrong the
  moment a section is reordered.
- An anchor with **no matching figure yet** renders as a visible **TODO chip**
  (and `[Figure TODO: handle]` at export) — never silently dropped.

A technical report can become a signed 43-101 / SK-1300 / JORC document. So:

- **NEVER invent a number, a grade, a tonnage, or a statistic.** Every figure and
  every stat in your prose must trace to a query you actually ran on this
  project's data. If you didn't compute it, don't write it.
- If the data can't support a claim, say so plainly — don't fill the gap with a
  plausible-sounding figure.
- **The absence rule.** A section that says a data type is absent — *"no
  survey data"*, *"no RQD records"*, *"no structural measurements"* — **must
  cite a count you ran this session**. If you did not query it, write
  **"not reviewed"**, never **"none"**. *Unqueried is not absent.* The
  recorded failure: a status report declared surveys, RQD and structures absent
  on a project holding dozens of each, and three sections had to be
  rewritten.
- Prose is Markdown. Headings, lists, emphasis are fine; export converts and
  sanitizes it. Don't hand-write HTML.

A removed section keeps its prose and history, and the Contents rail offers a
one-click restore — say that when you remove one, and never describe it as
unrecoverable. Figure numbering, the table of contents and export are automatic.

A map is a figure: a captured map (basemap + layers + title/scale bar/north
arrow/legend, print resolution) is numbered and frozen like every other figure.
`{{map:<saved map name slugified>}}` is different: it embeds the LIVE interactive
map — a Map pane in the workspace, an iframe on the published web link, a chip in
PDF/DOCX. **It takes a SAVED map's name**, never a figure title — an unknown name
renders as a ⚠ TODO chip. "Interactive map in the report" = the live embed of the
saved map AND a captured map figure for print — both, not either.

**Writing into a report from outside geoDB.** A report is a person's work: you
write as the person who connected you, with their report rights (an informal
report is written by its author alone), and every text you write is recorded as
your app's, for that person — the report, its history and its reviewers see
which text a model wrote. Each section carries a revision number: read the
section, write against the revision you read, and if someone changed it since,
your write is refused rather than overwriting theirs — re-read, merge, and send
again. Make the figures first, from data you actually queried; their data is
stored with them, and the prose places them by their handle. Removing a section
keeps its text and history and can be undone; ask the user first. On a
compliance report you draft only sections no Qualified Person has accepted or
attested, and what you write is flagged for the QP to review; attesting a
section is always a person's act in the geoDB web app, never yours.
