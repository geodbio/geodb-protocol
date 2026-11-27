# Modelling engines: measured

Which engine to use for a 3D model at which size, as measured. The teaching
(topic `3d-meshes`, "Choosing the engine") states the durable rules; this page
holds the numbers and the version-specific traps behind them. Numbers are
**approximate and depend on the sandbox**: check your own CPUs and memory, and
re-measure with `benchmark/benchmark.py` when it matters.

## The 2026-11-26 run

- **Sandbox:** a chat app's code sandbox, 2 vCPU, 7.8 GiB memory, x86_64,
  Python 3.13.
- **Packages:** gstlearn 1.11.1, LoopStructural 1.12.0, ferreus_rbf 0.3.0, and
  scipy's `RBFInterpolator`. Each installed with one plain `pip install` in its
  own virtual environment.
- **Data:** synthetic drilling with an analytic truth, 300 samples per hole: a
  layered unit (`unit`) and a grade body (`grade`), at about 2,400, 25,000,
  250,000 and 1,000,000 samples (8, 83, 833 and 3,333 holes). The grid is
  10 x 8 x 3 m. The full table is `benchmark/results_2026-11-26.csv`.
- **Time cap:** 900 s per run.

### Layered unit: error of the surface (mean, m), volume error, time, memory

| engine | ~2,400 pts (8 holes) | ~25,000 (83) | ~250,000 (833) | ~1,000,000 (3,333) |
|---|---|---|---|---|
| gstlearn potential-field kriging | **2.3 m**, −4%, 5 s, 0.2 GB | 0.7 m, −5%, 58 s | 0.2 m, −5%, 681 s, 1.1 GB | not run (predicted over the cap) |
| LoopStructural FDI | 7.2 m, −9%, 103 s, 0.9 GB | 0.8 m, −6%, 123 s | 0.8 m, −6%, 85 s | 0.5 m, −6%, 84 s, 0.9 GB |
| scipy RBF, global | 12.3 m, −27%, 6 s | timeout (4.8 GB at the cap) | | |
| scipy RBF, coarse to fine | 12.5 m, −37%, 1 s | 1.7 m, −14%, 6 s | | |
| scipy RBF, local (64) | 15.1 m, −12%, 10 s, 0.1 GB | 2.1 m, −12%, 22 s | 0.4 m, −4%, 23 s | 0.2 m, −4%, 28 s, 0.3 GB |
| ferreus_rbf | 12.3 m, −27%, 5 s | 1.7 m, −13%, 3 s | 0.3 m, −5%, 54 s, 1.3 GB | 0.2 m, −4%, 149 s, 5.5 GB |

LoopStructural FDI honours the contacts by least squares: it put 96% of the
inside samples inside at ~2,400 points and 97 to 99.9% when denser. Every other
engine here was at 99.4% or better.

### Grade body: error of the shell (mean, m), volume error, time, memory

| engine | ~2,400 pts (8 holes) | ~25,000 (83) | ~250,000 (833) | ~1,000,000 (3,333) |
|---|---|---|---|---|
| gstlearn SPDE | 31.3 m, −65%, 8 s, 0.4 GB | 5.0 m, −6%, 8 s | 2.1 m, −0.6%, 12 s | 1.6 m, −0.1%, 40 s, 0.7 GB |
| scipy RBF, global | 31.7 m, −74%, 5 s | timeout (4.8 GB at the cap) | | |
| scipy RBF, coarse to fine | 29.9 m, −85%, 1 s | 5.2 m, −7%, 7 s | | |
| scipy RBF, local (64) | 35.4 m, −65%, 10 s | 7.0 m, −7%, 23 s | 2.0 m, −0.1%, 29 s | 1.1 m, +0.4%, 27 s, 0.3 GB |
| ferreus_rbf | 31.7 m, −74%, 5 s | 5.1 m, −7%, 4 s | 1.9 m, −0.2%, 62 s, 1.3 GB | 1.0 m, +0.4%, 187 s, 5.5 GB |
| gstlearn kriging, unique neighbourhood | 31.4 m, −70%, 319 s | not run | | |
| gstlearn kriging, moving neighbourhood | 30.0 m, −25%, 290 s | timeout | | |

At ~2,400 points the grade body was crossed by only two fences of holes, and
every engine missed most of its volume. Sparse drilling decides more than the
engine.

## What it means (rules of thumb)

- **Layered unit, sparse drilling:** potential-field kriging (gstlearn) is the
  most accurate by a wide margin. Its cost grows with the equations (about four
  per contact, about 0.1 s each here): keep it to roughly 1,500 to 2,000
  contacts. Past that, LoopStructural FDI holds its time and memory flat.
- **Grade body:** scipy RBF over all points up to about 5,000; coarse to fine
  with thinning further, though it lost the most volume on sparse data. Past
  about 25,000, gstlearn SPDE or scipy with a local neighbourhood of about 50 to
  70 points (cost grows with grid nodes times neighbours cubed: 150 neighbours
  on 2.5 million nodes was slow). ferreus_rbf scales to a million points but
  needs about 5.5 GB there: offer it only on escalation.
- **Never** gstlearn ordinary kriging, unique or moving neighbourhood, over a
  whole grid: minutes at a few thousand points.
- **Extrapolation:** a potential field carries a layer on to the model box's
  edge and a signed-distance interpolation closes it. They agree where drilled
  and differ away from the holes (on one demo project the extra volume lay 120
  to 180 m from drilling). Clip to the drilled volume or state the distance.

## Version-specific traps

| package | version | trap |
|---|---|---|
| gstlearn | 1.11.1 | `simulatePotential` crashes the process (also on gstlearn's own tutorial data). Do not call it. For uncertainty, condition simulations yourself (for example random Fourier features with the same covariance, conditioned by the potential cokriging), check them against the kriged field, report P10 / P50 / P90 volumes |
| gstlearn | 1.11.1 | `setDriftIRF(1)` makes `krigingPotential` fail: set no drift |
| gstlearn | 1.11.1 | `krigingPotential` takes no neighbourhood (unique only) and writes only to a grid (`DbGrid`; select nodes with a selection column) |
| gstlearn | 1.11.1 | potential kriging needs a gradient-capable covariance (`CovGradientAnalytic` over a cubic one). A cubic covariance is stable; a Gaussian one without a drift swings away from the data and is ill-conditioned at long ranges |

The reference recipe `recipes/potential_field.py` avoids each of these.

## Re-measure

    uv run benchmark/benchmark.py --sizes 2400,24900 --cases unit,grade --timeout 900 --out results.csv

The script generates the drilling (no geoDB data, no key), runs each engine in
its own process under the time cap and writes the same columns as
`benchmark/results_2026-11-26.csv`. The synthetic shapes differ from the
2026-11-26 run's, so compare engines within one run, not numbers across runs.
