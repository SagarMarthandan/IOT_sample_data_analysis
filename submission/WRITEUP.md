# FYTA — Data Engineer assessment

**Sagar Marthandan** — three weeks, 8 soil sensors, 15,950 readings, 49 user notes,
28 plant photos. `run.sh` rebuilds every number below.

Walkthrough (11 min): <https://www.loom.com/share/3450a82ff2e540a1b4253eaf1a3e4c75>  
Full analysis: `FYTA_full_analysis.html`, or the notebook it renders from.

## Findings

- **SENS-06 moisture frozen at 25.01 for 1,344 readings** (14 days) while its other
  four channels kept moving. Nulled, with a reason recorded per row. Cause unresolved.
- **SENS-07 reads Fahrenheit and runs 2 h off local time.** Its scale and offset fit
  the Fahrenheit conversion, and aligning its light series supports the clock offset
  (r 0.802 → 0.9997). Correlation alone sees neither: it correlates 0.9843 with its
  peers while in the wrong unit.
- **SENS-05 missed 193 slots (48.5 h) with no empty cells anywhere.** Those rows do not
  exist, so only an expected-slot count finds them.
- **SENS-08 delivered 15 duplicate rows** with identical payloads — deduplicating is
  lossless.
- **Plant IDs repeat:** joining logs or photos to the device map expands 49 rows to 67
  and 28 to 35.
- **Still open:** SENS-03's EC climbs in a straight line from 06-11 with no logged
  cause, and the two-sensor plants disagree (r −0.08, +0.14).

## The solution

- **Raw data is never edited.** Corrections land in `_clean` columns beside the
  originals. Nothing is clipped, averaged or interpolated.
- **Two tiers, not one.** Physically impossible values are nulled and recorded per
  row; values outside the published range are kept and flagged. 21% of SENS-04's
  readings sit above the 65% ceiling, and that excursion is the shape of its drying
  cycle.
- **Write, audit, publish.** 22 checks reconcile every published value against the row
  it came from, so a stripped flag or a deleted device fails the gate instead of passing quietly.
- **Outputs:** 15,935 cleaned rows, 1,415 nulled values with their reasons, and an
  11,903-row feature table at `(user_plant_id, ts_aligned)` grain, asserted.
- **The feature table keeps its scope.** Sensor channels and plant metadata only:
  spreading 49 events and 28 photos across 15-minute rows would duplicate a sparse
  event hundreds of times. Both probes are kept, with `vwc_delta` between them.

## Cross-source result

- **Image model:** its water-deficiency score tracks sensor dryness at r = 0.75, which
  is the axis the sensor already measures — and the data is synthetic, so independence
  is unverified. The heads that could disagree never exceed 0.06.
- **Fertilising logs:** no selected window established corroboration. Five events
  screened at 3σ against each probe's own noise is low-power, and the log is not a
  known event time. A wider window made UP-1002 look confirmed, from SENS-03's drift
  rather than chemistry.

## Limits and next steps

- Completeness is measured against each device's observed span, not an installation
  window; grid spacing and phase are asserted, boundary slots are not.
- The frozen-channel rule misses a light sensor that dies at exactly zero.
- Unit fixes, clock offsets and ranges rest on published specs and the substrate
  conversion curve, which FYTA can confirm.
- Production: one compacted Parquet object per device per day ($15/month at 100k
  devices), with the per-device-window checks running hourly as data arrives.

