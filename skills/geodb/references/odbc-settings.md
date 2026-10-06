# "ODBC settings: the frame and units connected modelling and GIS tools read"

What a project's ODBC settings decide (the coordinate frame and the length units that connected modelling and GIS packages read), the frame choices and what each needs, that stored coordinates never change, and who may change them.

### What the ODBC settings decide

Modelling and GIS packages connected to a project through ODBC read its
drill holes, samples and intervals in one coordinate frame and one length
unit, set per project:

- **WGS84** latitude and longitude;
- **UTM**, the project's coordinate system (needs the project's coordinate
  system to be set);
- **the local grid** (needs the project's local grid);
- **a custom EPSG code** (needs the code);
- **original**, each record in the coordinate system it was imported in.

A further switch transforms straight from each record's own coordinate
system instead of through WGS84. Depths and lengths are served in the
project's length units, or in metres or feet.

### Stored coordinates never change

These settings change only what the connected tools are SERVED. Every
record keeps its native coordinates exactly as imported; a frame change
moves no stored number. A change does reach every tool that reads the
project, on its next refresh, so tell the user before making one.

### Who may change them

Changing them needs the permission to manage the project's settings.

### Changing them through the API

On the records endpoint the ODBC settings are a settings model grant-context
lists under `writes.settings_models`, with the intent update only: one per
project, named by the project. Read the describe contract first, dry-run,
tell the user what will change, and send it after their yes. Every write can
be undone. The settings in force, and the frame they resolve to, are read at
`odbc-settings/`.
