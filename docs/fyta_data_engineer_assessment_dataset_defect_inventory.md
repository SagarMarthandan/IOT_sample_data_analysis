---
type: solution
title: 'FYTA data-engineer assessment: dataset defect inventory'
tags:
- fyta
- data-quality
- sensor
- interview
- assessment
---

# FYTA Data Engineer assessment — dataset defect inventory

Vault: `~/Projects/FYTA Assessment`. 15,950 sensor rows, 8 devices, 6 plants, 21 days
(2026-06-01 .. 2026-06-22), 15-min cadence. Expected 2016 slots/device.

## Parse traps
- `SENS-07` timestamps are `DD/MM/YYYY HH:MM`; all other devices ISO. `pandas.to_datetime(format='mixed')`
  mis-parses SENS-07 to Jan/Dec — parse per-row with explicit formats, `dayfirst` only for SENS-07.
- `SENS-07` timestamps are also **+2h vs the fleet** (clock/TZ offset). Correct with `-2h` before any cross-device join.

## Confirmed defects (evidence-backed)
| # | Defect | Evidence |
|:---|:---|:---|
| 1 | SENS-07 TZ offset | rows run 02:00 -> 01:45 (+2h), DD/MM format |
| 2 | SENS-07 unit error | soil_temp_c is Fahrenheit: 61.9-78.0 -> 16.6-25.6 C, matches fleet 16.1-26.0 |
| 3 | SENS-06 stuck channel | moisture frozen at exactly 25.01 from 06-08 00:00, 1344/2016 rows; temp/EC/PAR/humidity all still vary |
| 4 | Impossible values | VWC<0 x12 (SENS-08), VWC>100 x49 (SENS-04 peak 107.1); humidity 105-131 x10 (SENS-08); night PAR 429-589 x5 (SENS-08) |
| 5 | SENS-03 EC drift | linear ramp +135 uS/cm/day from 06-10, R2=0.9918, zero response to 4 waterings => drift not chemistry |
| 6 | Exact duplicates | 15 identical (device,timestamp) pairs on SENS-08; dedupe is lossless |
| 7 | Outage | SENS-05 missing 193 slots = 48.5h (06-12 23:45 -> 06-15 00:15) |
| 8 | Twin-device fan-out | UP-1001=[SENS-01,SENS-02] r=-0.076; UP-1003=[SENS-04,SENS-06] r=0.140. Two sensors in one pot MUST correlate >0.9 => mapping suspect or wrong pot; averaging is invalid |
| 9 | SENS-04 gain anomaly | drydown 6.5 VWC/day vs fleet 0.5-1.9; median |delta| 0.47 vs 0.14; 49 peaks >100% |
| 10 | Log<->sensor mismatch | 0/33 watering logs align within 3h. Grid search over +-96h constant shift: best 3/6 hits, inconsistent across plants => NOT a clock offset, it is label quality |
| 11 | Periodic watering | rise gaps exactly 108h (SENS-01), 120h (SENS-02), 72h (SENS-07), 96h (SENS-05), mostly landing on 00:00/12:00. Not human => irrigation schedule or synthetic artefact; watering TIMING is not a usable label |
| 12 | Shared environment | soil_temp cross-device sd 0.38 C, r=0.974; light_par r=0.998; humidity r=0.946. But moisture r=0.103 and EC r=-0.002. Environment is ONE replicated series; moisture/EC are per-device |
| 13 | Static substrate label | 1 substrate_label per device for the whole window despite repotting logs on UP-1002 (06-04) and UP-1006 (06-13) => dimension joined without SCD-2 history, or stale labels |

## Image predictions (Plant.id-style, model_version `health_all_v3`, 28 rows)
- Hierarchical taxonomy: `Abiotic` is the PARENT of `Water-related issue` / `Nutrient deficiency`; its
  probability ~= max(child). Naive argmax always returns the coarse parent -> must walk the hierarchy.
- `is_plant` = True with p >= 0.9515 on all 28 -> head untestable, no negatives in sample.
- `is_healthy` is exactly `is_healthy_probability > 0.5` (derived field, zero extra info). 7/28 in [0.4,0.6].
- `Nutrient deficiency` never exceeds 0.073 -> the task-6 example (fertilising log -> EC rise -> nutrient
  deficiency prediction) is NOT observable in this sample.
- Water deficiency vs Water excess are anti-correlated (mutually exclusive).
- AGREEMENT (real finding): water-deficiency prob vs substrate-normalised dryness percentile r = **-0.79**;
  vs raw VWC r = **-0.70** => normalising VWC by substrate improves image/sensor agreement.
  At dryness_pct<0.25 the model calls deficiency (>0.4) in 10/12 cases.
- Confound: the disease head is essentially a 1-D moisture readout, i.e. NOT independent evidence for
  validating the moisture sensor. The genuinely independent heads (is_plant, Fungi, Animalia) never fire.

## Method notes
- "Sensor problem vs physical signal" test that worked: (a) does it violate physics? (b) does the SAME
  device's other channels stay healthy? (c) is the shape a clean mathematical function (R2=0.99 ramp,
  exact 25.01 constant, exact 120h period) rather than organic? (d) does it respond to logged events?
- Substrate normalization matters: orchid_bark runs 9-31% VWC, potting_soil 18-51%, coco_coir 16-39%.
  Absolute thresholds are wrong across substrates.

