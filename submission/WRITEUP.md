# FYTA — Data Engineer assessment

**Sagar Marthandan**

Three weeks, 8 soil sensors, 15,950 readings, 49 user notes, 28 plant photos.
`uv run fyta_pipeline.py` reproduces every number below (`out/run.log`);
`uv run test_gates.py` runs 18 regression checks, each verified to fail when its
fix is reverted; `fyta_analysis.ipynb` executes from a fresh kernel.

## Findings

**SENS-06 moisture stayed at 25.01 for 1,344 readings** — fourteen days — while
its other four channels kept moving. I nulled that interval and kept a reason per
row. The cause is unresolved.

**SENS-07 reads Fahrenheit and runs two hours off local time.** Its temperature
scale and offset fit the Fahrenheit conversion, and aligning its light series
against the fleet supports a two-hour clock offset (r 0.802 → 0.9997).
Correlation alone sees neither: it correlates at 0.9843 with its peers while in
the wrong unit.

**SENS-05 missed 193 slots (48.5 h) with no empty cells anywhere** — the rows are
absent, so only an expected-slot count finds them. **SENS-08 delivered 15
duplicate rows** with identical payloads, so deduplicating them is lossless.
**Plant IDs repeat:** joining logs or photos to the device map expands 49 rows to
67 and 28 to 35.

Two questions stay open: SENS-03's EC climbs in a straight line from 06-11 with
no logged cause, and the two-sensor plants disagree (r −0.08, +0.14), which
depth, placement or a failed probe would each explain.

## Treatment and outputs

Raw columns are never edited. Corrections land in `_clean` columns beside them:
physically impossible values are nulled and recorded in `out/qc_rejections.csv`,
while values merely outside the published range are kept and flagged — 21% of
SENS-04's readings sit above the 65% ceiling, and that excursion is the shape of
its drying cycle. Nothing is clipped, averaged or interpolated.

`out/plant_features.csv` (11,903 rows, grain `(user_plant_id, ts_aligned)`,
asserted) carries the sensor channels and plant metadata. It excludes logs and
photos: spreading 49 events and 28 photos across 15-minute rows would duplicate a
sparse event hundreds of times. Both probes are kept, with `vwc_delta` between
them.

## Cross-source result

The image model's water-deficiency score tracks sensor dryness at r = 0.75 — the
axis the sensor already measures — and one synthetic generator could have produced
both, so independence is unestablished. Its other heads never exceed 0.06.

For the five fertilising logs, the selected windows established no corroboration:
screening five events at 3σ against each probe's own noise is low-power, and the
log is not a known event time. A wider window would have made UP-1002 look
confirmed, from SENS-03's drift rather than chemistry.

## Limits and next steps

Completeness is measured against each device's observed span, not an installation
window; grid spacing and phase are asserted, boundary slots are not. The
frozen-channel rule misses a light sensor that dies at exactly zero, and SENS-03's
drift is not flagged per row. Unit fixes, clock offsets and ranges rest on
published specs and the substrate conversion curve, which FYTA can confirm (D1,
D7).

For production: one compacted Parquet object per device per day ($15/month of
requests at 100k devices), with the per-device-window checks running hourly off
the ingestion buffer — hourly lake files cost 24× that to hold four readings each.
Arithmetic in `docs/PIPELINE_DESIGN.md` §5.
