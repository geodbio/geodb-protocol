# Lithogeochemistry: indices, element-native screens, pathfinder suites

The standard lithogeochem toolkit (AI, CCPI, Na-K, immobile screens, pathfinder profiles) with its authors, how to read what elements a project really has, and how a classified group becomes a derived set.

Inputs are whole-rock MAJOR-ELEMENT OXIDES in wt% (`FeO*` = total iron as FeO —
reconcile `Fe2O3` to FeO* with `FeO* = Fe2O3 * 0.8998`), except the pathfinder
suites, which are TRACE-element ppm.

Grades for a plot come from the merged wide read: ONE row per sample, already in
the plot-ready wide shape, merged per Assay Merge Settings — ask for every element
you might plot in that one read and drop missing pairs. A dense scatter of all the
samples IS "spread my samples out"; do NOT trim it to an arbitrary subset (that
biases the cloud to database order and helps nothing). Scope only a genuinely
scoped ask (one hole, top-N grades).

**ORIENT FIRST — the opening move of a geochem session is a LOOK, not a chart.**
When the user starts geochem work cold ("let's do some geochem / categorise my
samples"), read before drawing and say what you found in a few lines:
1. **Samples:** how many drill vs surface/point samples, and how many carry assays.
2. **Elements:** name the suite you actually have (majors as elements? immobiles
   Sc/Ti/Zr/Al/V/Cr? pathfinders As/Sb/Bi/Hg/Tl? just Au/Ag/Cu/Pb/Zn?). This decides
   which recipes are even possible.
3. **What is logged already:** lithology / alteration sets and their interval
   counts, and any existing sample groups. A project with rich logging wants a chart
   that TESTS the logging (colour by it); a project with none wants a chart that
   SEPARATES rock types so the user can assign them.
Then choose: if the user's goal is stated or obvious from the data, propose the chart
and draw it (one sentence on WHY that chart). If not, ASK — one short question with
the three common goals and the chart each leads to, e.g. *"Are you sorting out
**lithology** (I'd start with an immobile-element screen, Ti vs Sc), mapping
**alteration** (the AI–CCPI alteration box, if the majors are here), or looking at
**trends** (Au against a pathfinder like As)?"* Never open with a generic Au-vs-As
scatter just because it is easy; never list what the project lacks before checking
the elemental forms.

**FIRST STEP, ALWAYS — enumerate the elements you actually have, THEN pick the path.**
Assay data almost NEVER stores oxide columns (`SiO2`/`Al2O3`/`K2O`) — it stores ELEMENTS
in ppm (`Fe`/`Ca`/`K`/`Al`/`Sc`/`Ti`…). "No `Al2O3` column" is NOT "no whole-rock data";
it is the normal shape, and the elemental forms convert trivially. NEVER tell the user
"you don't have major-element geochemistry, import oxides" without first checking for the
ELEMENTAL forms (the recorded miss: a full suite, incl. Fe/Ca/K/Al/Sc,
dismissed as "only Ag/Cu/Pb").

- **Element → oxide (wt%), when an oxide-input recipe needs it** (multiply element wt% by
  the oxide/element mass ratio): `SiO2 = Si×2.1393`, `Al2O3 = Al×1.8895`, `FeO = Fe×1.2865`
  (`Fe2O3 = Fe×1.4297`), `MnO = Mn×1.2912`, `MgO = Mg×1.6582`, `CaO = Ca×1.3992`,
  `Na2O = Na×1.3480`, `K2O = K×1.2046`, `TiO2 = Ti×1.6681`, `P2O5 = P×2.2916`. ICP values
  are usually ppm → wt% = ppm/10000 first. (Total-digestion / whole-rock ICP only; a
  partial/aqua-regia leach is NOT whole-rock — say so rather than force the conversion.)
- **Or skip oxides entirely — the ELEMENT-native recipes.** For LITHOLOGY work (the common
  ask) you do NOT need oxides at all: **C4(ii)** is an immobile-element-vs-**Sc** lithology
  screen and **C5** pathfinder suites are element-ppm by design. When the project is
  trace-/element-only, ROUTE THERE FIRST — an immobile element (Sc, Ti, Zr, Al, V, Cr) vs a
  discriminant is a far better lithology separator than the Ag/Cu/Pb mineralization signal
  (which tracks ORE, not rock type). e.g. "categorize lithologies" on this data → C4(ii)
  Sc-maficness screen or a Zr/Ti/Sc immobile-element frame, not an Ag-Cu scatter.

| Index | Formula | Attribution |
|---|---|---|
| **AI** (Ishikawa) | `AI = 100*(K2O + MgO) / (K2O + MgO + Na2O + CaO)` | Large, Gemmell, Herrmann, Paulick & Huston 2001, Econ. Geol. 96:957 |
| **CCPI** | `CCPI = 100*(MgO + FeO*) / (MgO + FeO* + Na2O + K2O)` | Large et al. 2001 (denominator is Na2O+K2O — the +CaO variant is wrong) |
| **SEDEX AI3** | `AI3 = 100*(FeO* + 10*MnO) / (FeO* + 10*MnO + MgO + Al2O3)` | Large 2001 (SEDEX/carbonate systems) |
| **MnOd** | `MnOd = MnO * 40.03 / CaO` | Large 2001 (carbonate-chemistry vector; pair with Tl) |
| **Gresens ΔXn** | `dXn = w * (XB_n * (XA_im / XB_im) - XA_n)` — A=precursor, B=altered, _im=immobile ref (e.g. TiO2), w=100. Immobile n ⇒ ΔXn≈0 | Mathieu (Trepanier) 2018 Eq.18, Geosciences 8:245 |
| **Immobility test** | on an immobile-vs-immobile binary (Al2O3 vs TiO2), co-precursor samples sit on a line THROUGH THE ORIGIN; report slope + Pearson r (r>0.85 ⇒ usable reference) | Large/Mathieu lineage |
| **MER/PER** | convert wt%oxide→moles cation (`moles = wt% / molar_mass * cations`), then ratio over a CONSERVED denominator (Zr/TiO2/Al2O3) | Stanley 2020, GEEA 20:233 |
| **MINSQ** | non-negative least squares `min ‖measured_oxides − M·modes‖²`, modes≥0, Σ=100% over an end-member matrix | Herrmann & Berry 2002, GEEA 2:361 |
| **Feldspar Na-K** | molar `Na/Al` and `K/Al` (element wt%: `/22.9898`,`/39.0983`,`/26.9815`; or from oxides Na2O/K2O/Al2O3) | Stanley & Madeisky 1996 |

Oxide molar masses (g/mol) for the molar conversions: SiO2 60.0843, TiO2 79.8658,
Al2O3 101.9613, FeO 71.8444, Fe2O3 159.6882, MnO 70.9374, MgO 40.3044, CaO 56.0774,
Na2O 61.9789, K2O 94.1960 (×2 for the 2-cation oxides Al2O3/Fe2O3/Na2O/K2O). MINSQ
end-members: quartz, albite, k_feldspar, anorthite, muscovite (≈sericite), chlorite,
calcite, dolomite, epidote, pyrite.

**C1 — Alteration box (the headline; Large et al. 2001).** X=AI, Y=CCPI, square axes,
both 0-100. Colour the markers by a grade (log10 for a log colour) or a classification
column — DROP rows whose grade is missing/BDL before colouring by it. The template:
the least-altered box **AI 20-65, CCPI 15-85** (dashed), the four end-member corners
(albite bottom-left, K-feldspar bottom-right, chlorite / pyrite top-right, epidote /
calcite top-left), and a hydrothermal trend arrow from the box centre toward the
ore-proximal corner (90, 90).

**C2 — Ternary.** Alteration: **Al:K:Mg** (argillic vs advanced-argillic) and
**Ca:Fe:S** (anhydrite/pyrite); or any 3-component. Name the apices.

**C3 — Feldspar Na-K control diagram** (Stanley & Madeisky 1996). X=`Na/Al`,
Y=`K/Al` (molar). End-member nodes — K-feldspar (0, 1), albite (1, 0),
muscovite/sericite (0, 0.333), advanced-argillic clay → origin (0, 0); the **AF
alkali-feldspar line** (0,1)→(1,0); K/Al guide lines at **0.333** (muscovite; above ⇒
orthoclase/biotite) and **0.45** (phengite cap; above ⇒ K-feldspar-bearing). Colour by
the 9-class porphyry alteration palette when a class column exists — Potassic
`#FF0000`, Sericite `#FFFF00`, Sericite Chlorite `#009900`, Moderate Phyllic `#99FF99`,
Advanced Argillic `#FF99FF`, Alunite `#FF00FF`, Feldspar Sulfate Sulfide `#FF9900`,
Background `#999999`, Default `#000000`.

**C4 — Immobile-element screen.** (i) immobile-vs-immobile (Al2O3 vs TiO2) with a line
through the origin — the immobility surface; a selection separates precursor groups.
(ii) immobile-vs-**Sc** lithology screen with maficness GUIDE bands (not boundaries):
Basalt 30-50, Andesite 20-30, Dacite 10-20, Rhyolite <10 ppm Sc. Fixed lithology
boundaries are not the method; pick populations by selection + clustering.

**C5 — Pathfinder suite profile** (the correctly-rendered "barcode"). For each
pathfinder element compute its median as a MULTIPLE of crustal abundance (Rudnick & Gao
2003 UCC), plot on a **log-Y** axis over the elements ordered distal→proximal, colour the
oxyanion vs chloride split, and highlight anomalies (**>10× crust**, coherent across
adjacent elements). Crustal abundances (ppm): Mo 1.1, As 4.8, Sb 0.4, Tl 0.9, Bi 0.16,
Te 0.027, Sn 2.1, W 1.9, Zn 67, Mn 774, Cu 28, Pb 17, Cs 4.9, Li 24, Au 0.0015.

- **porphyry_cu** — oxyanion (zoned outflow) **Mo, Sn, W, Bi, Te, As, Sb, Tl** + chloride
  (peripheral doughnut) **Zn, Mn, Cu, Pb, Ag, Co, Ni**. Distal→proximal zonation
  **Tl → Sb → As → Te → Bi → Se → Sn → Mo** (i.e. Mo proximal, Tl distal). Per-element ppm
  thresholds (porphyry only): Mo>5, Sn>5, Bi>1, Te>1, As>50, Sb>5, Tl>2. Needs ICP-MS /
  4-acid (AES DLs are too high for Bi/Te/Sb/Tl). *(Public porphyry-Cu workshop.)*
- **epithermal_au** — Au, Ag, As, Sb, Cs, Li, Mn (LSE clay-blanket; Barker et al. 2019).
  **vms** — Cu, Zn, Pb, Ag, As, Sb, Tl, Ba. **sed_cu** — Cu, Co, Ni (brine-pyrite
  signature). **orogenic_au** — Au, As, Sb, Cs, Li (Sb-Cs-Li outflow). These four have no
  strict ppm threshold in the public literature — anomaly = **>10× crust**.

The charts are not the deliverable; the **classified set you can model in 3D** is. A
**population** is a NAMED colour-group of samples whose colour follows the SAMPLES onto
every plot: select points → give them a colour and a name → recolour/refine → when
real, classify it (it adopts that lithology or alteration code's colour, so plots agree
with 3D and the strip log) → promote it to a durable log. Promotion writes the group's
DRILL samples as intervals into a NEW derived lithology or alteration set whose `source`
marks it as derived (never into a geologist's logged set); point/surface samples
are reported and skipped. A new set is not drawn in 3D until the 3D drill-hole layer is
pointed at it: a layer draws exactly ONE lithology set and ONE alteration set, and with
none chosen it falls through the project's set ladder to whatever the export slot holds,
which may be a near-empty set that renders as grey traces.

**Attribution is load-bearing.** AI/CCPI = Large et al. 2001; Feldspar Na-K = Stanley &
Madeisky 1996; MER/PER = Stanley 2020; Gresens/immobile mass balance = Mathieu 2018;
MINSQ = Herrmann & Berry 2002; crustal table = Rudnick & Gao 2003. The three-stage
classify–alteration–vector WORKFLOW comes from industry workshop practice, but the
FORMULAS are the toolkit above — put their authors on the chart, never a workshop
presenter's name on a formula.

**Field (portable) XRF is guidance, not a grade.** A reading taken on core or
chips with a hand-held analyser is stored like an assay — a point down the
hole with element values — under a reading session whose source is field XRF.
geoDB keeps it OUT of lab-assay analytics, QC verdicts, intercepts, grade
shells and merged reads by default. Use it for what it is good
at — logging decisions, picking intervals to send to the lab, a downhole
pathfinder profile — and always label it as field XRF. Never average it with
lab results, never report it as a grade, and never use it in a resource
estimate. Anything you derive from it is a new set, never an edit to
someone's logged set.
