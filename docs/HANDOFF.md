# HANDOFF

State of the work, written so someone with **no memory of any session** can
continue. Updated at phase boundaries per `AGENTS.md` §18.

**Last updated:** 2026-09-18 · **Complete.** Tasks 1–9 done, write-up shipped.
**Deadline:** Monday 21 September 2026, EOD, to gregor@fyta.de

---

## 1. What exists, and whether it runs

```
FYTA Assessment/
  AGENTS.md                    engineering rules, binding (484 lines)
  data/                        the four source CSVs — NEVER WRITTEN TO
  docs/
    assessment.md              the brief + correspondence (canonical)
    DATA.md                    what the data is (561)
    decision_register.md       D1–D13, awaiting conversations (364)
    observations.md            findings + method + mistakes, for the report (583)
    HANDOFF.md                 this file
    fyta_..._inventory.md      SUPERSEDED — safe to delete
  submission/
    fyta/                      the logic, split by change reason
      domain.py                  60  assertions; no I/O, no pandas
      sensors.py                485  Tasks 1-2: read, detect, findings
      cleaning.py               131  Task 3: two-tier clean + audit
      sources.py                 97  Task 4: image model assessment
      features.py               127  Task 5: the per-plant table
    fyta_pipeline.py           480  entry point + printed narrative
    test_gates.py               86  regression checks for the three fixes
    fyta_analysis.ipynb        38 cells — narrative + rendered output
    pyproject.toml / uv.lock / requirements.txt
    out/                       published artifacts + run.log
```

**Verified at this boundary:**

```
uv run fyta_pipeline.py    exit 0 · no warnings · 545 log lines
uv run test_gates.py       3 of 3 regression checks pass
fyta_analysis.ipynb        51 cells · 0 errors · 2 figures · 0 function defs
data/                      unmodified — proven by multiset comparison
```

Environment: Python 3.12.12, pandas 2.3.3, numpy 2.4.6, matplotlib 3.11.2.
**numpy is pinned `<2.5` deliberately** — 2.5 deprecates the generic timedelta
unit pandas 2.3.3 still uses, so every `pd.Timedelta` warns.

## 2. Done — Tasks 1, 2, 3

| Task | State |
|:---|:---|
| **1 — Ingest & orient** | ✅ §1–5. Load, structure, channels, events, two figures. **Proven non-destructive** |
| **2 — Data quality** | ✅ §6–7. 10 detectors → 13 findings → detection-coverage table |
| **3 — Cleaning** | ✅ §8. Two-tier treatment, 12-check audit gate, 1,415 rejections |
| **4 — Source agreement** | ✅ §9. Four sources, four answers. The image model's independence is unestablished |
| **5 — Feature table** | ✅ §10. Grain `(user_plant_id, ts_aligned)`, asserted. Probes kept side by side |
| **6 — Triangulation** | ✅ §11. Negative, for three structural reasons. The window is the trap |
| **7 — Pipeline design** | ✅ §12. Sketch only. Two variants, one decision rule, both diagrams rendered |
| **8 — Derived signal** | ✅ §13. `drydown_pct_per_day`. Independently rediscovers SENS-04 / F5 |
| **9 — Log text** | ✅ §13. A lookup, not a classifier — 14 phrases, mapping already 1:1 |

**13 findings (F1–F13).** 4 data problems · 2 sensor faults · 2 unknown ·
1 artefact · 1 schema · 1 label · 1 semantic · 1 unresolved.
Full detail: `out/task2_findings.csv`.

**Cleaning output:**
- `cleaned_sensor.csv` — 15,935 rows. Raw columns + `ts_aligned` + five `_clean` + `qc_flags`
- `qc_rejections.csv` — 1,415 rows: 1,344 frozen (SENS-06) + 71 impossible

**Cleaning refuses three things:** clip to range · average co-located sensors ·
fill in the 48.5-hour gap.

## 3. Not done

Nothing. All nine tasks are done and the write-up exists.

`submission/WRITEUP.md` → `submission/WRITEUP.pdf`, **one page**, built by
`uv run --with markdown python md_to_pdf.py` (markdown → styled HTML →
headless Chrome print). `WRITEUP.md` is the source; edit that and rebuild.

## 4. Decisions taken, and why

Full detail with owners in `docs/decision_register.md`. The load-bearing ones:

**Task 1 reports shape; Task 2 reports violations.** Orientation states what is
*present*; quality states what is *wrong*. Task 1 reports the contract, Task 2
the violations. One acknowledged exception: `key_uniqueness` lives in Task 1 and
reports `unique: False`.

**Raw is never modified.** Every fix is a new column; the original stays beside
it. Proven by multiset comparison across all four tables.

**Two tiers, because "outside spec" ≠ "provably wrong".** Physically impossible
→ empty. Outside the specified range but possible → **flag and keep**. This rule
was violated once (see §6) and the violation was caught.

**The bar for deleting a value is "physically impossible" — not "implausible".**
Using the weaker bar would delete real observations, irreversibly.

**Isolated vs sustained decides the treatment.** A single impossible reading is a
glitch; a long run is a regime change.

**Detection and remediation are separate and must reconcile.** `detect_unit_outliers()`
and `UNIT_FIXES` are checked against each other **in both directions**.

**One file, not modules.** The notebook is already the per-task view; `SPEC` is
shared across tasks 2 and 3, so splitting would need a fourth file.

**Task 4 compares the model against the *cleaned* values, with *raw* as a
sensitivity column.** The model is what is on trial, so the sensor side must be
the best estimate of the physical quantity — and raw contains 1,415 values
already proven not to be measurements. A frozen channel is constant, so it can
only dilute a correlation: using raw would turn "the sensor is dead" into "the
model disagrees", which is a spurious negative caused by the input choice.

**Time is held constant across both arms.** The clock offset is proven (F2) and
not in dispute, so both arms pair on `ts_aligned`. One variable varies, which is
what makes a gap between the columns attributable rather than ambiguous.

**The code is five modules, split by change reason — not by size.** Sensor
reading changes when we learn about the hardware; the cleaning policy when we
decide how to treat a defect; the source assessment when a feed changes; the
feature table when the modelling team's needs change. `domain.py` holds the
assertions and imports **no pandas** — `AGENTS.md` §7 made structural. The
findings table stays in `sensors.py` beside the detectors it cites, so a claim is
never separated from its evidence (the failure §17 exists to prevent). The split
was verified by diffing the run log: **byte-identical**.

**The feature table never averages the two probes.** `vwc_delta` carries their
disagreement instead — 19.9% VWC on UP-1003, 8.8% on UP-1001. Averaging is
exactly what destroys the fault signal a second probe exists to give.

**`vwc_pct` is ranked over a TRAILING window.** A whole-window rank would judge a
day-1 reading against day-21 data — leakage the moment the table feeds a model.

## 4b. Second-opinion fixes — what was wrong and what changed

An external review found three correctness defects and several stale claims.
All were verified before being fixed, and all three fixes now have a regression
check that fails if reverted (`submission/test_gates.py`).

**The audit gate was tautological.** `cleaning.py` asked *"is there at least one
null in moisture?"* — satisfied by any null. Restoring all 1,344 frozen SENS-06
values still passed it, behind prose saying *"nothing publishes unless every check
passes."* Now reconciles rejections against the cleaned values **both ways**:
every rejection is null in its column, and every null has a rejection behind it.
The `== 8` hardcode on the dark-hour check is gone too — the invariant is
detector↔flag agreement, not a frozen count.

**Run counting was wrong.** `spec_violations` used `n - (bad & bad.shift()).sum()`,
which counts **runs**, not isolated readings. SENS-04's 431-sample excursion
reported as 11 "isolated"; it is actually 11 runs, 431 in-run, **0 isolated**.
`in_runs` was also Σ(L−1) instead of ΣL. Fixed by run-length encoding. The
corrected numbers make F5 *stronger*: every out-of-spec reading is sustained.

**Triangulation accepted a fall as corroboration.** The brief specifies a *rise*;
the code used `.abs()`. Fixed to require `d_ec_sigma > 0`. Timing fixed too: the
offset is now signed hours via `total_seconds()` (`abs(timedelta.days)` truncated,
so a photo 10.75 h *before* an event read as one day away), bounded to ±48 h, and
"no image in window" is a distinct state from "the model looked and was silent."

**Numbers with no computation behind them.** F10, F12 and F11's corroborating
figures were transcribed from one-off analyses — nothing in the code produced
them. Three detectors added (`colocated_correlation`, `cross_device_correlation`,
`rise_timing`); the numbers changed where the transcription was wrong:
F12 light 0.998→0.991, humidity 0.946→0.937, moisture 0.103→0.201; F11
"35 of 35"→**35 of 37**; F10's second pair +0.140→+0.103.

**Also corrected:** F4's prose claimed the drift is "flagged in qc_flags" — it
isn't; only 354 of 1,056 drifting rows carry the range flag, from 06-17. The
sizing figures were **assumed**, not measured: row size 63→**67.9 B**, compression
~5×→**7.57×** measured. The Task 5 scope is now stated rather than implied. The
Task 4 circularity claim was reframed — "circular" was wrong, "convergent" is
unsupported, and the synthetic generator is the reason neither is earned.

## 5. Open items — each with an owner

| # | Question | Owner |
|:---|:---|:---|
| D1 | Are the spec ranges current for this generation? | Hardware |
| D2 | Is 15 min the configured rate or a buffer flush? | Firmware |
| D3 | SENS-07 +2h: timezone or clock fault? | Firmware |
| D4 | Is °F one device or a firmware variant? | Firmware |
| D5 | Can analysis use flagged out-of-spec values? | Analysis |
| D6 | Longest a healthy channel holds a value? | Firmware |
| D7 | Is `substrate_label` the curve actually applied? | Product |
| D8 | Can analysis tolerate a 48.5 h gap? | Analysis |
| D9 | Does the device do anything at 00:00? | Firmware |
| D10 | Are the 8 devices co-located? | Product |
| **D11** | **Does the app allow two sensors on one plant?** | **Product** |
| D12 | Does a soil-temperature spec exist? | Hardware |
| D13 | Can a light at that pot be real? | Firmware |

**Four conversations.** D11 blocks Task 5 for two plants.

## 6. Corrections made — do not repeat these

| Believed | Reality | Caught by |
|:---|:---|:---|
| The cadence check resolves the date ambiguity | It does not — a uniform misread still scores 99%. Impossibility is the evidence | Testing it |
| SENS-07's Fahrenheit evidence looked weak | The **clock offset was contaminating it**. After −2h: 0.444 vs 0.380 control | Re-testing |
| **Light at night is impossible** | **Wrong.** A person can switch a lamp on | **Your correction** |
| The dark-hour spikes should be emptied | **Wrong.** 589 is inside the rated 2000 — possible. Flag, don't delete | **Your correction** |
| "Nine checks" (then "ten") | Eleven detectors now | Reading the output |
| A detector could apply the clock offset itself | Double-shifted already-aligned data | The audit, twice |
| `import re` / `from __future__` were used | Dead | ponytail-review |
| `stuck_channels` was removed | Survived in the notebook; the script had deleted it | A consistency check |
| Merge on `["id","finding"]` | The two frames label findings differently — all NaN | Reading the output |
| The raw-vs-clean table covered every channel | It hardcoded 4, missing `light_par` | Your question |
| A taxonomy chain's last element is its parent | **Wrong.** `nutrient-related issue` groups a head but is never scored — `KeyError` at runtime | Running it |
| An edit that removed a duplicate line | Added two instead — the tool matched, then matched again | Reading the result, not the success message |
| The notebook survived a signature change | It didn't; nbconvert aborted and left **stale outputs**, so the first check looked clean | Running the notebook |
| The context compaction worked | It didn't — the counter was unchanged | **Your screenshot** |

**The pattern:** the audit gate, the ponytail review, and running the code each
caught things reading did not. Four were mistakes I made minutes earlier.

## 7. Next actions

1. **Write-up** — required. Distil `observations.md`: 5 findings that matter, the
   calls I'd defend, what I'd never ship, what needs Gregor's team.
2. **Tasks 8/9** are implemented in §13 — the optional stretches.

## 8. Unrecoverable if lost

Nothing below is derivable from the CSVs. It exists only in prose.

**The method lessons** (`observations.md` Part 2, ten of them). The three that
carry the most:

- **Correlation cannot see a unit error.** SENS-07's temperature correlates at
  **0.9843** — the highest in the fleet — while reading Fahrenheit. `y = ax + b`
  leaves correlation untouched. Correlation detects *timing*, not *scaling*.
- **Two problems can hide each other.** The clock offset had to be removed before
  the unit error became clean evidence (sd 1.363 → 0.444). Structural defects
  before semantic ones.
- **A magnitude check cannot see a context problem.** The light spikes sit inside
  every stated limit. Finding them needed a fourth kind of question — comparing a
  reading against its *neighbours*, not a constant or the device's own history.

**The corrections record** (§6) — evidence of method, not of success.

**The causality analysis.** The two-sensor issue is the most *interesting*
problem but causes only 2 of 13 findings; the five worst are on single-sensor
plants. That rules it out as the root cause, which matters because the fix is not
one thing.

**Why flag-vs-empty matters.** A successor reading only the code would likely
"simplify" the two-tier rule into one threshold — and start deleting real data.

**The four questions that changed the work.** Domain intuition beating statistics
("a person can turn on a light"), and skepticism about necessity ("is that
unnecessary?"). Three of the four corrections came from those.

**The independence argument, and why it decides Task 4.** The image model agrees
with the moisture sensor at r ≈ 0.75. The naive reading is "validated." An early
draft called it "circular" — also wrong, since two instruments on one latent
variable *is* corroboration. The defensible reading is narrower than both: the
model adds nothing beyond water status, and the dataset is **synthetic**, so
whether even that is independent is unverifiable without lineage from the vendor.
The numbers support any of the three; only the argument picks between them.

**Why one code path matters here.** `assess_source()` exists so the raw and
cleaned arms cannot drift. The notebook drifting from the script has now bitten
three times (`stuck_channels`, `light_par`, the 3-arg call). Keep call sites
thin.
