# HANDOFF

State of the work, written so someone with **no memory of any session** can
continue. Updated at phase boundaries per `AGENTS.md` §18.

**Last updated:** 2026-09-20 · **Reassessment pass (R1–R6 + editorial) complete,
verified, uncommitted.**
**Current HEAD:** `b5ddc81` — this session's work is in the working tree, not yet
committed or pushed.
**Deadline:** Monday 21 September 2026, EOD, to gregor@fyta.de

---

## 1. What exists, and whether it runs

```
FYTA Assessment/
  AGENTS.md                    engineering rules, binding
  README.md                    how to run it, layout, regenerable out/ note
  data/                        the four source CSVs — NEVER WRITTEN TO (md5 unchanged)
  docs/
    assessment.md              the brief + thread + what the data actually IS
                               (Parts 1–3; DATA.md merged in 2026-09-20)
    observations.md            findings, method, mistakes, open items, and the
                               three external reviews verbatim (Parts 1–7)
    decision_register.md       D1–D18, each with an owner
    PIPELINE_DESIGN.md         Task 7: one batching policy, latency, cost arithmetic
    HANDOFF.md                 this file
  submission/
    images/                    hand-made architecture diagrams (static, NOT in out/)
    fyta/                      domain.py · sensors.py · cleaning.py · sources.py
                               features.py · signals.py
    fyta_pipeline.py           entry point + stdout tee to out/run.log
    fyta_analysis.ipynb        50 cells (21 code) · executed fresh · 0 errors
    test_gates.py              18 regression checks (each fails on revert)
    WRITEUP.md / WRITEUP.pdf   the submission note: 1 page, 533 words, 10.6 pt
    md_to_pdf.py               builds the PDF via headless Chrome
    out/                       11 CSVs, 2 figures, run.log (all regenerable)
```

**Verified at this boundary — each line is an output that was read, not expected:**

```
uv run fyta_pipeline.py    exit 0 · 21 of 21 audit checks pass · 565 lines of run.log
uv run test_gates.py       18 of 18 pass · 7 new checks each verified to FAIL on revert
fyta_analysis.ipynb        50 cells · 21 code · all executed · 0 errors · 2 figures
idempotency                a full re-run reproduced all 14 artifacts byte-for-byte (md5)
prose pass                 module prose 6,057→3,616 w · prints 1,745→940 w ·
                           notebook 5,357→4,245 w · design doc 3,754→3,021 w
WRITEUP.pdf                1 page, A4 · 533 words at 10.6 pt (was 783 words at 9.3 pt)
data/                      unmodified — `git status` clean on data/
environment                Python 3.12.12 · pandas 2.3.3 · numpy 2.4.6 (<2.5) · matplotlib 3.11.2
```

The PDF needs `uv run --with markdown`; Chrome does the print step. The notebook
needs `uv run --with nbconvert` to execute headlessly.

---

## 2. What this session changed (the reassessment's R1–R6)

| # | Defect | Fix | Evidence it fails when reverted |
|:---|:---|:---|:---|
| R1 | Fresh-kernel `NameError` at Task 6 — `heads` consumed, never defined | Image-normalisation cell restored in §3b | cell 31 now defines it; notebook executes clean |
| R2 | Quarantine: raw-text timestamp arithmetic, group masking (`A,A,B,B` → 0 quarantined), payloads lost | Conflict decided per **key group**; `ts_aligned` computed before the branch; ledger gains `row_payload` | `test_conflicting_duplicates_are_quarantined_not_resolved` |
| R3 | Audit accepted 2,016 deleted rows, rejected re-orders, counted flags, never re-detected frozen windows | Row accounting (retained + deduped + quarantined = source), value compare **after aligning by key**, key-level flag reconciliation, independent frozen re-detection | four tests: deleted device · reordered frame · moved flags · skipped frozen detection |
| R4 | A `NaN` probe score won `max()` and hid the other probe's rise | Scores require valid observations; every probe reports an outcome in `leg_detail` | `test_an_unavailable_probe_does_not_mask_the_other` |
| R5 | Claims contradicted the fixes (dry-down calibration, shared environment, "all fixed", triangulation power, off-grid) | Docstrings, printed claims, notebook prose and article corrected; `check_grid` now asserts grid **phase**, which catches the one-minute-shift fixture | `check_grid` on a shifted frame; claims re-read against the run |
| R6 | Batching policy inconsistent; $200–500 envelope unsupported | One policy stated: **daily Parquet objects, $15/mo of PUTs**, total ≈$190–450/mo; hourly = $533–792/mo; lake freshness ≤1 day with hourly buffer checks | arithmetic in `PIPELINE_DESIGN.md` §5, mirrored in the notebook |

Also corrected: the dark-hour flag was matched on the **raw** clock while the
detector ran on the aligned frame (latent — SENS-08, the only spiking device, has
no offset; the 8 detected and 8 flagged rows coincide). Details in
`docs/observations.md`, "The fourth review — the reassessment".

### The prose pass (the reviewer's closing editorial section)

Applied to submission-facing prose, with each repeated explanation reduced to one
home (the dedup map is in `docs/observations.md`, "The prose pass"):

| Artifact | Before | After |
|:---|---:|---:|
| `fyta/*.py` comments + docstrings | 6,057 w | 3,616 w |
| `fyta_pipeline.py` print literals (→ `out/run.log`) | 1,745 w | 940 w |
| `fyta_analysis.ipynb` markdown | 5,357 w | 4,245 w |
| `docs/PIPELINE_DESIGN.md` | 3,754 w | 3,021 w |

Cut: review history from code, all-caps emphasis, pull-quotes, "not X but Y"
setups, the notebook's second architecture essay (Task 7 now points at the design
doc), and the duplicated probe / clipping / two-tier explanations. Kept: every
threshold, count, path and reversal condition; every `ponytail:` marker; and the
test docstrings, which are the one place an old defect belongs.

**One statement was lost in the process and restored.** `cleaning.py` dropped
`df = df.drop(columns=["ts"])` while its comment was rewritten, and the next
pipeline run failed loudly on it. After the repair: 18/18 regression checks,
pipeline exit 0, and all 14 artifacts byte-identical to the pre-pass run — only
`run.log` differs, because that is the artifact the pass rewrote.

**The notebook lost its diagrams and one code cell** and was repaired after the
owner opened it: the image markdown had been rewritten into a shell call (so both
architecture diagrams rendered as placeholders) and the `image_predictions` cell
that defines `heads` had been dropped. The asset test passed anyway, because the
rewritten reference no longer matched its regex and it never asserted that it had
found anything. All three failure modes now fail loudly (recorded in
`docs/observations.md`, "Correction: the notebook's diagrams were rewritten into
shell calls").

---

## 3. Done — all nine tasks

| Task | Where | Status |
|:---|:---|:---|
| **1 — Ingest & orient** | §1a–1e | Complete |
| **2 — Data quality** | §2a–2c. 11 detectors → 13 findings → detection coverage | Complete |
| **3 — Cleaning** | §3a Clean · §3b Normalize (now *in* the notebook, with its checks) | Complete |
| **4 — Source agreement** | §4a. Four sources, four answers → `out/task4_source_assessment.csv` | Complete |
| **5 — Feature table** | §5a. Grain `(user_plant_id, ts_aligned)`, asserted | Complete |
| **6 — Triangulation** | §6a. Every probe, 3-state leg, per-probe detail | Complete |
| **7 — Pipeline design** | `PIPELINE_DESIGN.md` + two diagrams | Complete |
| **8 — Derived signal** | §8a. `drydown_pct_per_day` + `drydown_asof` | Complete |
| **9 — Log text** | §9a. A lookup, not a classifier | Complete |
| **Write-up** | `WRITEUP.pdf` — one page, 533 words | Complete |

---

## 4. Open items (owners in `docs/decision_register.md`)

| # | Question | Owner | Impact |
|:---|:---|:---|:---|
| D1 | Are the spec ranges current for this hardware generation? | Hardware | Validity flags vs rejections |
| D2/D6 | Is 15 min the configured rate, and what is the real buffer size? | Firmware | Slot-grid expectations, watermark |
| D3 | SENS-07 +2h: timezone or drifting clock? | Firmware | Clock correction |
| D4 | Is °F one device or a firmware variant? | Firmware | Scope of the unit fix |
| D7 | Is `substrate_label` the curve actually applied? | Product | Magnitude of every VWC value |
| D8 | Can downstream tolerate a 48.5 h hole? | Analysis | Sparse vs dense policy |
| D11/D17 | Two sensors on one plant — allowed, and what should a feature table do? | Product | Blocks any fusion rule |
| D14 | Did the image model consume VWC? | Vendor | Independence of r = 0.75 |
| D18 | Does anything need **lake** data fresher than a day? | Platform | Batching policy and cost |

---

## 5. Corrections made — historical reference

| Cycle | Believed | Reality | Caught by |
|:---|:---|:---|:---|
| Review 1 | Gate prevented bad publication | 1,344 restored frozen readings passed | Mutation testing |
| Review 1 | Run-start arithmetic counted isolated points | Counted run starts | Recomputation |
| Review 1 | `.abs()` on EC delta checked rise | A large fall counted as corroboration | Direction testing |
| Review 2 | Gate reconciled flags | 736 stripped flags passed | Mutation testing |
| Review 2 | Symmetric image window safe | A pre-event photo counted as a response | Fixture |
| Review 3 | Frozen rule safe fleet-wide | Nulled 52 legitimate dark-hour zeros | Fixture |
| Review 3 | Duplicates deduped losslessly | Conflicting payloads resolved by first-wins | Fixture |
| Review 3 | Differentiation removes calibration | Gain `a` survives differentiation | Arithmetic |
| Review 3 | Shared environment invalidates peers | A tight shared signal is a *better* reference | Domain logic |
| **Review 4** | **Quarantine fixed** | **Group masking: `A,A,B,B` quarantined nothing; the branch crashed on source text** | **Reassessment + fixture** |
| **Review 4** | **Audit accounted for rows** | **Inner join on shared keys: 2,016 deleted rows passed; re-orders failed** | **Reassessment + fixture** |
| **Review 4** | **Flags reconciled** | **Counts, not keys: moving all 8 flags passed** | **Reassessment + fixture** |
| **Review 4** | **Frozen detection verified** | **Only recorded rejections were audited; skipping the detector passed** | **Reassessment + fixture** |
| **Review 4** | **Probe selection sound** | **`NaN` score won `max()` and reported "not testable" over a real rise** | **Reassessment + fixture** |
| **Review 4 (self)** | **Flag matched the row the detector meant** | **Matched on the raw clock, not the aligned one** | **Reading the code against its own detector** |
| **Prose pass** | **A prose-only edit cannot change behaviour** | **It deleted a statement in `cleaning.py`; the next pipeline run failed on it** | **Running the pipeline, not reading the diff** |
| **Prose pass (2)** | **The diagrams survived the notebook rewrite** | **`![alt](path)` became a shell call, one code cell was dropped, and the asset test passed on an empty reference set** | **The owner, opening the notebook** |

The pattern across all four cycles: **the check that "verifies" a behaviour is the
part most likely to be wrong**, because a check that passes is not investigated.

---

## 6. Next actions

1. **Commit and push** this pass (`submission/*`, `docs/*`) — the tree is dirty by
   design so the owner can review the diff first.
2. **Prose targets are met, with one honest gap.** `WRITEUP.md` is 533 words
   including headings against the reviewer's suggested 400–500 for body prose;
   the remaining prose lives in tables of evidence. Further cuts would remove
   findings or limits, which the reviewer ranked above brevity.
3. If the owner wants the deferred full expected-grid validation: it needs the
   **installation window** from the platform (D2/D6), which the sample does not
   carry. `device_coverage()` documents the observed-span ceiling in the meantime.
4. Nothing else is outstanding from the reassessment: "No additional features or
   architecture diagrams are needed."

---

## 7. Unrecoverable if lost

1. **Correlation cannot see a unit error:** SENS-07 correlates at `0.9843` with
   peers while reading Fahrenheit. Scale and jitter ratio (1.82×) proved it.
2. **Two problems hide each other:** the clock offset had to be aligned before the
   unit-error variance collapsed cleanly (sd 1.363 → 0.444).
3. **A magnitude check cannot see context:** the dark-hour light spikes sit inside
   `[0, 589]` spec; only comparison against neighbours reveals them.
4. **Testing every leg matters:** light *contradicts* its own log phrase (peak
   drops −4.4 when "moved closer to window").
5. **A check that passes is not evidence.** Four review cycles found defects that
   were "verified" by a check which could not fail. Mutation-test every new gate.
6. **The safest-looking code path is the least exercised.** The quarantine branch
   survived two reviews because the real sample has *only* payload-identical
   duplicates, and a test helper had been rewritten to hide the input's true shape.
7. **A comment is not a statement.** Rewriting prose in a file that runs is still
   editing that file; the prose pass deleted a statement whose comment survived.
   Run the artifact, do not read the diff.
