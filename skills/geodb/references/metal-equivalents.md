# "Metal equivalents: price decks and the equivalent grade every surface shows"

What a metal-equivalent price deck holds (the target element and units, one priced term per element with price, recovery and payability), why the project default deck is the equivalent column every surface shows, who may change decks, and what removing one does.

### What a price deck holds

A metal-equivalent price deck turns several metals into one equivalent
grade of a target element (for example gold equivalent). It names the
target element and the units the equivalent is shown in, and one priced
term per contributing element: its price and price units, its metallurgical
recovery and its payability (100 percent by default), with a note of where
the price came from and the date the prices were struck. Each element's
contribution is its grade times price times recovery times payability,
expressed in the target element. A term without a stated recovery cannot be
rendered until it has one: a missing recovery is never assumed.

### The default deck is the equivalent everyone sees

A project can hold several decks; one is the project default, and its
equivalent is the column every surface shows (tables, maps, exports). Its
grades come from combined assay values, under the merge settings the deck
names or else the project's default merge settings. Making another deck the
default changes that column everywhere. A deck is a commercial assumption:
quote its prices, recoveries and date with any equivalent grade.

### Who may change them

Creating, changing or removing a deck needs the permission to manage the
project's settings. A removed deck goes to the Trash with its terms and can
be restored.

### Changing them through the API

On the records endpoint a deck is a settings model grant-context lists under
`writes.settings_models`, with the intents create, update, retract and
restore; its priced elements are its `terms`, each with an `action` (add,
change or remove) on an update, named by its id or element. Read its
describe contract first, dry-run, tell the user what changes, and send it
after their yes. Every write can be undone. Decks are read at
`metal-equivalents/`.
