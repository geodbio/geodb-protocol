# Geostatistics: compositing, declustering, capping and variography

Preparing drill assays for estimation (one sampling pass, composites that honour domains, declustered statistics, capping with the metal it removes, variogram conventions) and which part geoDB serves versus what stays the user's own work.

### Before any statistic: the inputs

Estimation statistics are only as good as the table under them. Before you
compute anything:

- **One sampling pass.** A hole can carry two passes over the same ground
  (primary bags and composites of their pulps). Pooling them double-counts
  that ground. Use one pass, and say which.
- **Below detection is not a number.** The stored `-1` is a sentinel: use the
  project's substitute (half the detection limit by default), never `-1` and
  never by dropping the sample, and never substitute twice (merged tables
  already did). An over-range value is a floor, not a grade.
- **Lab values only.** Field (portable) XRF readings are not grades and never
  enter an estimate. A raw list of values can carry them beside lab results,
  marked by their source (`field_xrf`): drop them first.
- **Withheld rows stay withheld.** Values from a certificate whose QAQC review
  rejected or superseded it are not data for an estimate; name them.
- **Units.** Check each element against its method's detection limit and
  typical range before trusting the unit.
- **Positions in metres.** Desurveyed sample positions on a projected or
  local grid; never latitude/longitude degrees for distances, search
  ellipses or variograms.

### Compositing: equal support, inside one domain

Samples of different lengths have different support, and an average or a
variogram that mixes them weights them wrongly. Composite to one length
first, length-weighting each composite (value × length, summed, over the
summed length).

- **Choose the length from the data:** commonly the dominant sample length
  or a multiple of it, and small against the planned block size. Compositing
  far longer than the samples smooths away the grade variability you will
  later need to model.
- **Honour the domains.** Break composites at every estimation-domain
  contact (lithology, oxidation, a grade shell): a composite that straddles
  a contact blends two populations and blurs exactly the boundary the
  estimate depends on. Composite within each domain separately.
- **Unsampled is not zero.** A gap with no sample is missing, not barren.
  Treat it as missing unless the geologist states the interval was left
  unsampled because it is barren, and say which you did. Report each
  composite's coverage (sampled length over composite length).
- **Short end pieces.** At a domain contact or the end of a hole the last
  composite is short. Keep, merge or drop it by one stated rule, and check
  that the rule does not bias the domain's mean.

### Declustering: the naive mean is biased

Drilling clusters where grade is high (infill around a discovery hole), so
the plain average of the samples over-represents the high-grade ground.
Weight each composite by the area or volume it stands for before quoting a
domain mean or building a histogram for the estimate:

- **Cell declustering:** overlay a grid, weight each composite by the
  inverse of the number of composites sharing its cell, and repeat over a
  range of cell sizes (Deutsch 1989, *Computers & Geosciences* 15, 325–332).
  Where the clustering is in high grade, the declustered mean dips below
  the naive mean as the cell nears the spacing of the sparser drilling;
  choose the size with a reason (commonly that spacing) and state it.
- **Polygonal (nearest-neighbour) weights** are the older alternative
  (Isaaks & Srivastava 1989, *An Introduction to Applied Geostatistics*,
  Oxford University Press).

Report the naive and the declustered statistics side by side. Declustering
changes the weights, never the data.

### Capping (top-cutting): with the metal it removes

A few extreme values can carry a large share of a domain's metal and spread
it far through an estimate. Capping resets values above a chosen grade to
that grade. It is a judgement for the person responsible for the estimate,
not a rule:

- **Per domain**, usually on the composites and judged on the declustered
  distribution; say whether you capped samples or composites.
- **Look before you choose:** the log-probability plot (a break in slope),
  the histogram's tail, the coefficient of variation, and how much metal the
  top few percent of composites carry. A classic treatment of high-grade
  outliers in epithermal gold deposits is Parker 1991 (*Mathematical Geology* 23,
  175–199).
- **State the effect:** how many values were capped and the share of the
  domain's metal (mean grade before and after) the cap removes. A cap
  reported without that number cannot be judged.
- **Never invent a cap.** Propose one with the evidence above and leave the
  choice to the user; a percentile is a starting point to look at, not an
  answer.

### Variograms: state every convention

The experimental semivariogram is half the mean squared difference between
values a lag apart: γ(h) = Σ (zᵢ − zⱼ)² / 2N(h), over the N(h) pairs of
values zᵢ, zⱼ separated by the lag h (Matheron 1963, *Economic Geology* 58,
1246–1266). Read
from it: the **nugget** (the jump at the origin; a downhole variogram at the
sample spacing estimates it best), the **sill** (where it levels off) and the
**range** (the lag where it gets there).

- **Directions:** compute along at least the strike, down-dip and across
  directions of the domain, each with its lag, lag tolerance, angular
  tolerance and bandwidth. Report anisotropy as the major, semi-major and
  minor ranges with their orientation. Rotation conventions differ between
  software packages (azimuth clockwise from north, dip sign, the order of
  rotations): state the one you used, or the numbers cannot be reproduced.
- **Skewed grades** give noisy variograms. A normal-score or log transform,
  or a pairwise-relative variogram, shows the structure more clearly; say
  which you used. Its ranges and anisotropy carry over; its sill does not:
  before kriging raw grades, rescale the sill to the domain's variance (a
  normal-score model can instead be back-transformed, e.g. through Hermite
  polynomials), and say which you did. A pairwise-relative variogram has no
  back-transform of its own.
- **Use composites, within one domain**, positioned in metres.

Standard references for the whole workflow: Journel & Huijbregts 1978,
*Mining Geostatistics* (Academic Press); Sinclair & Blackwell 2002, *Applied
Mineral Inventory Estimation* (Cambridge University Press); Rossi & Deutsch
2014, *Mineral Resource Estimation* (Springer).

**What geoDB serves, and what stays your work.** geoDB stores and serves the
inputs; it runs no estimation. Read:

- **Samples and grades:** `drill-samples/` (each row names its sampling pass
  and carries its desurveyed from/to positions on the project local grid, in
  metres) and `assay-results/` (one row per value, with its below-detection
  and over-range flags, its detection limit and its `source_type`: keep `lab`,
  drop `field_xrf`).
- **Fixed-length composites:** `drill-samples/composited/`, one hole at a
  time, at the length set in one of the project's assay configurations with
  compositing switched on, over ONE sampling pass (the project's export pass
  unless you name another), length-weighted, merged per the project's settings
  (below-detection already substituted). It composites straight down the
  hole: it does NOT break at domain contacts. Where domains matter, composite
  the samples yourself.
- **Intervals over boundaries you choose:** `drill-intercepts/`, each with its
  coverage.
- **Positions:** a hole's desurveyed trace (`drill-collars/<id>/trace/`) and
  the position at any depth (`drill-collars/<id>/xyz_at_depth/`), on the
  project local grid in metres. They need the project's coordinate system: a
  project without one answers `project_crs_required` (the stored collar
  coordinates are untouched). Tell the user and follow its remedy (they
  confirm the coordinate system); never treat native coordinates as metres
  instead.
- **Detection limits per method and element:** `detection-limits/`.

Declustering, capping, variography, block models, grade interpolation,
classification and any resource statement are the user's own work, in their
own tools, and a disclosed estimate is the responsibility of its Qualified or
Competent Person. Offer the analysis; never present it as geoDB's.
