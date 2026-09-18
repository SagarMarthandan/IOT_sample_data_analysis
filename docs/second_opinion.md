# FYTA Data Engineer Assessment: Second Opinion

## Consultant verdict

**Do not submit this version yet.**

The analytical foundation is strong. It shows better-than-average sensor-data judgment and would likely support an interview after a focused correction pass. As submitted now, one required deliverable is missing and several confident claims are not supported by the implementation.

**My assessment: approximately 6.5/10 as-is.**  
With the priority fixes below: **roughly 8/10 and interview-worthy.**

I reviewed every substantive repository artifact: the brief, all project documentation, eight Python files, all 51 notebook cells and stored outputs, raw datasets, generated CSVs, run log, figures, and dependency metadata. I excluded generated `.venv`, `__pycache__`, and the stale notebook checkpoint body.

I made no file changes during the review. I did not execute `fyta_pipeline.py` because it writes into `submission/out/`. I recomputed its main transformations in memory:

- Raw sensor rows: **15,950**
- Cleaned rows: **15,935**
- Rejections: **1,415**
- Feature rows: **11,903**
- Notebook stored errors: **0**
- Saved artifact shapes match the in-memory results

## What is strong

### 1. The exploratory work catches genuinely difficult defects

The best findings are valuable and well reasoned:

- Mixed timestamp formats parsed explicitly rather than coerced.
- Fahrenheit/Celsius unit defect found through scale behavior.
- Two-hour clock offset found through daylight cross-correlation.
- Frozen moisture channel distinguished from a real plateau by checking other channels.
- Missing readings detected against an expected slot grid rather than null counts.
- Redundant duplicates separated from conflicting duplicates.
- Join fan-out measured before joining.
- Co-located sensors kept separate rather than averaged.
- User-entered substrate treated as a calibration parameter, not a harmless label.
- Unknown cases name the person or measurement needed to resolve them.

These address the core of the exercise: distinguishing sensor faults, transport/schema problems, real physical signals, and unresolved cases.

### 2. Cleaning policy is mostly mature

`submission/fyta/cleaning.py` preserves raw values and adds `_clean` columns. It does not clip, interpolate, or average away anomalies.

The two-tier policy is good:

- Physically impossible values become null with a rejection reason.
- Merely out-of-spec values remain present and receive a quality flag.

That is much better than generic "remove outliers" cleaning.

### 3. The feature table has a clear grain

`submission/fyta/features.py:48-118` declares and asserts:

```text
(user_plant_id, ts_aligned)
```

It also preserves two probes independently, exposes `vwc_delta`, uses trailing within-device VWC ranks, and keeps missing periods visible.

### 4. The production section contains several sound principles

Strong points include:

- Write-audit-publish.
- Event-time partitioning.
- Per-device rather than fleet-average monitoring.
- Slot-grid completeness.
- Frozen-channel detection with cross-channel evidence.
- A declarative device/substrate registry.
- Detection and remediation treated separately.
- No broker unless latency requirements justify one.

The AWS Basic Ingest claim is also supported: AWS currently charges no MQTT/HTTP messaging fee for Basic Ingest reserved topics, although rules and actions remain billable. See [AWS IoT Core pricing](https://aws.amazon.com/iot-core/pricing/).

## Blocking issue

### The required one-page write-up does not exist

The brief explicitly requests a maximum one-page write-up or recording in `docs/assessment.md:105-121`.

`docs/HANDOFF.md:74-81` confirms:

> required deliverable, does not exist

The 51-cell notebook is not a substitute. The correspondence says the short write-up is what FYTA expects back.

This alone makes the repository **not submission-ready**.

## Critical correctness findings

### 1. The audit gate can approve an uncleaned frozen channel

Location: `submission/fyta/cleaning.py:107-109`

The check named `frozen window nulled` verifies only that the moisture column contains at least one null:

```python
int(cleaned["soil_moisture_vwc_clean"].isna().sum()) > 0
```

It does not reconcile detected frozen windows against the cleaned rows.

I restored all **1,344** frozen SENS-06 moisture values in memory and reran `audit()`. Result:

```text
restored frozen values: 1344
audit failures after restoration: 0
frozen window nulled: True, 61 nulls in moisture
```

The remaining 61 unrelated moisture nulls satisfy the audit. `main()` would publish the broken output.

This is the most important engineering defect because the code advertises the audit as a publication gate.

**Required correction:** assert every `(device, channel, start, end)` frozen window is null in the corresponding clean column, and reconcile every rejection with the modified value.

### 2. Sustained range violations are misclassified as isolated readings

Location: `submission/fyta/sensors.py:150-154`

The implementation uses:

```python
adjacent = (bad & bad.shift()).sum()
isolated = n - adjacent
```

`n - adjacent` counts the start of every run as "isolated." It does not count samples that have no bad neighbor.

Reported versus actual:

| Device/channel | Reported | Actual |
|---|---:|---:|
| SENS-04 moisture | 11 isolated, 420 in runs | **0 isolated, 431 in sustained runs** |
| SENS-03 EC | 17 isolated, 337 in runs | **8 isolated, 346 in sustained runs** |

These incorrect values appear in `task2_findings.csv` and the narrative.

The overall fault conclusions remain plausible, but this is exactly the kind of reasonable-looking metric a data engineer must not misreport.

### 3. Task 6 can treat an EC decrease as corroboration

Location: `submission/fyta/sources.py:149-155`

The sensor leg uses:

```python
out["d_ec_sigma"].abs() > LEG_SIGMA
```

The requirement says fertilization should produce an EC **rise**. A large fall must contradict the hypothesis, not support it.

I forced a large post-event decrease in memory:

```text
d_ec_sigma: -12.26
sensor_leg: moves
```

Additional timing defects:

- The model leg tests a static probability above `0.10`; it does not test a pre/post response.
- The nearest image has no maximum time tolerance.
- An image before the event can be selected.
- Current data includes a nearest image **110.75 hours** after an event.
- `abs(timedelta.days)` truncates and mishandles signed partial days. A timestamp 10.75 hours before the event appears as one day away.

The current conclusion of zero corroborated events happens to survive, but the method can produce false positives.

**Required correction:** require positive EC change, compare pre/post image scores where possible, impose a signed time tolerance, and report elapsed hours using `total_seconds()`.

### 4. The claimed EC drift remediation does not exist

Notebook cell 29 and `submission/out/run.log:320-323` say SENS-03 EC drift is flagged in `qc_flags`.

The cleaner only flags values after they exceed the published EC range. It does not flag the detected drift regime.

From the claimed drift onset on 2026-06-11:

- SENS-03 rows: **1,056**
- Rows with EC quality flag: **354**
- Drifting rows with no EC flag: **702**
- First range-based flag: **2026-06-17 16:15**

The narrative therefore promises more than the cleaning code implements.

Either add an explicit drift-regime flag from the detected onset or change the write-up to state that drift remains detected but unremediated.

### 5. The "unified" feature table includes only sensor data and mapping

`plant_features()` accepts:

```python
plant_features(sensor, mapping)
```

It contains no image, contextual-log, prediction, or event fields.

This may satisfy a narrow reading of "single time-indexed table per plant," but Task 5 follows Tasks 4 and 6 and may reasonably be read as unifying the four sources.

Treat this as a **scope ambiguity**, not an automatic failure. The one-page write-up should say explicitly:

> The modelling table currently unifies cleaned sensor channels and plant metadata. Logs and images remain separate sparse event tables because joining them to every 15-minute row would duplicate information. Production consumers would use as-of joins with explicit tolerances.

That explanation would turn an apparent omission into a defensible design choice.

### 6. The image/sensor relationship is dismissed too aggressively

The cleaned association between `Water deficiency` and sensor-derived dryness is:

```text
r = 0.7516
```

The notebook calls this circular and "a restatement."

That conclusion needs model-lineage evidence. An image model and a soil probe are two different measurement modalities. Both may respond to water stress, but that does not make their agreement circular unless the image model consumed sensor/VWC information or both outputs came from the same synthetic generator.

A better conclusion:

> The correlation is useful convergent or weak-supervision evidence, but it does not establish either source as ground truth. Shared synthetic generation or confounding may explain it, so model lineage must be confirmed.

The association is also robust enough to deserve attention rather than dismissal.

### 7. The production lateness assumption mixes hardware generations

Notebook cell 41 states:

> ~320-measurement buffer bounds lateness at ~80 hours

FYTA's current technical page separates:

- Beam 1.0: once per hour
- Beam 2.0: four times per hour
- FYTA Beam storage section: 320 measurements, described as around 13 days

The page does not clearly assign that 320-reading storage figure to Beam 2.0. The submission combines Beam 2's four-per-hour cadence with the storage figure to derive 80 hours and then makes that the architecture-defining watermark.

This requires confirmation from FYTA firmware/product rather than assertion.

The same official page says Beam 1.0 and 2.0 do **not** measure humidity; Sphere does. Claims that the Beam body supplies humidity should therefore be qualified until the assessment's sensor family is known.

Sources:

- [FYTA technical data](https://fyta.de/en/pages/technische-daten)
- [FYTA Beam G2](https://fyta.de/en/products/fyta-beam-gen2)

## Communication and maintainability concerns

### Stale contradictions

Examples:

- Notebook cell 23 says **five** light anomalies; current detector and output report **eight**.
- Notebook cell 45 says Tasks 8 and 9 were not attempted.
- The following cells implement Tasks 8 and 9.
- `docs/HANDOFF.md:180-184` repeats that they were not attempted.
- The findings table says SENS-04 drydown is 6.5/day versus 0.5–1.9.
- Current Task 8 output says **38.4/day versus roughly 3–6**.

A reviewer will infer that the generated narrative was not reconciled after the code changed.

### Excessive volume for a three-hour exercise

Measured project size:

- Python: **1,473 lines**
- Markdown: **2,999 lines**
- Notebook: **51 cells**
- Two architecture variants plus diagram-generation prompts
- Both optional tasks
- No required one-page write-up

The issue is not AI use. FYTA explicitly permits it. The issue is prioritization: optional breadth displaced the required deliverable and left contradictions unreviewed.

### No project regression tests

No repository-owned test files exist.

The code contains assertions and in-memory checks, but the highest-risk audit is tautological. Several data-integrity gates use Python `assert`, which disappears under `python -O`.

One small regression suite covering the frozen-window gate, run classification, and triangulation direction would provide more value than the optional text task or second architecture variant.

### Complexity

Measured approximate cyclomatic complexity:

| Function | CC | Assessment |
|---|---:|---|
| `clean` | 11 | Refactor or split by cleaning rule |
| `image_predictions` | 9 | Watch |
| `plant_features` | 9 | Watch |
| `main` | 8 | Branching acceptable, but **357 lines** |
| `triangulate` | 6 | Moderate |

The architecture is not disastrously complex, but the submission is larger than the timebox justifies.

## Scorecard

These are consultant scores, not FYTA's internal weighting.

| Area | Score | Reason |
|---|---:|---|
| Task 1: ingest and explore | **9/10** | Strict parsing, useful orientation, good figures |
| Task 2: data quality | **8/10** | Strong defect discovery; incorrect run split and some overclaims |
| Task 3: cleaning | **5/10** | Sound policy, but publication gate gives false assurance and drift claim is wrong |
| Task 4: source validation | **6/10** | Good measurements; circularity conclusion is unsupported |
| Task 5: feature table | **6/10** | Strong grain and probe handling; source scope is unclear |
| Task 6: triangulation | **4/10** | Direction and timing semantics are incorrect |
| Task 7: production design | **6/10** | Good principles; unsupported hardware assumptions and overbuilt OSS option |
| Communication/deliverable | **4/10** | Required write-up absent; stale contradictions and poor timebox prioritization |

**Overall: approximately 6.5/10.**

## Recommended fix order

1. **Write the required one-page submission.**
2. **Repair the frozen-window audit and add one regression check.**
3. **Correct isolated-versus-sustained run counting.**
4. **Fix triangulation direction, timing, and model-response semantics.**
5. **Either flag the full drift regime or stop claiming it is flagged.**
6. **Explain why the feature table excludes sparse logs/images, or add bounded as-of features.**
7. **Reframe the image correlation as weak/convergent evidence.**
8. **Remove every stale count and contradiction.**
9. **Cut optional material. Keep one architecture recommendation, not two elaborate variants.**
10. **Label hardware, pricing, compression, row-size, and burst assumptions explicitly.**

## Hiring signal

The work demonstrates strong instincts around sensor data, grain, missingness, joins, physical plausibility, and uncertainty. Those are the valuable parts of the assessment.

The present version also signals that a large AI-generated result was not subjected to a final adversarial review. The failed audit mutation is the clearest example: the prose says "nothing publishes unless every check passes," while the check can approve the exact defect it claims to prevent.

A focused correction and a concise one-page narrative would change the impression from **ambitious but insufficiently reviewed** to **strong judgment with honest limits**.
