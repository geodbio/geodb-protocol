# "QAQC protocols: how often QC goes in, and the criteria every verdict is judged by"

What a project's QC protocol holds (insertion rates for standards, blanks and duplicates, and the acceptance criteria), why the default protocol decides every verdict, who may change it, and what a change does to verdicts already reached.

### What a QC protocol holds

A QC protocol is a project's plan and rulebook for quality control. The plan
says how often each kind of QC sample goes into the sample stream: a
standard every N samples, a blank every N, a duplicate every N, inserted
independently, staggered by an offset, or in a round robin, and counted per
hole or continuously. The rulebook is the acceptance criteria: how far a
standard may read from its certified value (in standard deviations and in
percent bias, each with a pass and a warn level, and a bias ceiling that never
passes), how far above the detection limit a blank may read, and below what
multiple of the detection limit a duplicate pair is judged on the absolute
difference instead of its relative difference. Its type (drilling or soils)
is only a label.

### The default protocol judges every verdict

A project can hold several protocols, but exactly one is the default, and the
default's criteria decide every pass, warn and fail on the project. A
project's first protocol becomes its default. Making another protocol the
default, or changing the criteria of the default, re-judges QC results that
have already been judged. Changing a non-default protocol, or only its
insertion rates, moves no verdict. No protocol is ever deleted; one stops
judging when another becomes the default.

### Who may change them

Changing a protocol needs the QAQC approval permission on the project (the
same permission that approves or rejects a certificate), because it changes
what every verdict means.

### When a change moves verdicts

A change that re-judges results is shown before it is made: which verdicts
would change (pass to fail and the reverse) and which certificates that a
person has already reviewed it reaches. A review decision already taken is
never changed by it; the reviewer may want to look again. Tell the user
both before they agree.

### Changing them through the API

On the records endpoint a protocol is a settings model grant-context lists
under `writes.settings_models`, with the intents create and update; read its
describe contract first (the fields, their meanings and defaults). A change
that moves verdicts answers its dry run with `verdicts` (what changes and the
reviewed certificates it reaches) and a `confirm` value: show the user both,
and send the change with that `confirm` only after their yes. Every write can
be undone.
