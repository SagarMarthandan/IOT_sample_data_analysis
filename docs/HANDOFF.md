# HANDOFF

State of the work, written so someone with **no memory of any session** can
continue. Updated at phase boundaries per `AGENTS.md` §18.

**Last updated:** 2026-09-19 · **Complete and submission-ready.**
**Deadline:** Monday 21 September 2026, EOD, to gregor@fyta.de

---

## 1. What exists, and whether it runs

```
FYTA Assessment/
  AGENTS.md                    engineering rules, binding
  README.md                    how to run it, what the layout is
  data/                        the four source CSVs — NEVER WRITTEN TO
  docs/
    assessment.md              the brief + correspondence (canonical)
    DATA.md                    what the data is, incl. the impossible bounds
    second_opinion.md          two external audits, both acted on
    observations.md            findings + method + mistakes (report source)
    decision_register.md       D1–D13, each with an owner
    HANDOFF.md                 this file
    PIPELINE_DESIGN.md         Task 7, both variants
    diagram_*.md               the prompts used to generate the two diagrams
  submission/
    fyta/                      the logic, split by change reason
      domain.py                  assertions; no I/O, no pandas
      sensors.py                 Tasks 1–2: read, detect, findings
      cleaning.py                Task 3: two-tier clean + audit gate
      sources.py                 Tasks 4, 6: source assessment, triangulation
      features.py                Task 5: the per-plant feature table
      signals.py                 Tasks 8, 9: a derived signal, log text
    fyta_pipeline.py           entry point + printed narrative
    fyta_analysis.ipynb        the same results, rendered
    test_gates.py              regression checks for the corrected defects
    WRITEUP.md / WRITEUP.pdf   the one-page submission note
    md_to_pdf.py               builds the PDF
    out/                       11 CSVs, 4 figures, run.log
```

**Verified at this boundary:**

```
uv run fyta_pipeline.py    exit 0 · writes out/run.log itself · 634 lines
uv run test_gates.py       11 of 11 regression checks pass
                           each verified to FAIL when its fix is reverted
fyta_analysis.ipynb        52 cells · 0 errors · 2 figures
WRITEUP.pdf                1 page, A4 · 783 words
data/                      unmodified — md5 df7b5d41cd79…
```

**Three external reviews have run.** The third (`second_opinion_astra.md`) found
ten defects and three wrong claims; all are fixed and every fix has a test.

Environment: Python 3.12.12, pandas 2.3.3, numpy 2.4.6 (**pinned `<2.5`** — 2.5
deprecates a generic timedelta unit pandas 2.3.3 still uses), matplotlib 3.11.2.
The PDF needs `uv run --with markdown`; Chrome does the print step.

## 2. Done — all nine tasks

| Task | Where |
|:---|:---|
| **1 — Ingest & orient** | §1a–1e. Load, structure, channels, events, two figures |
| **2 — Data quality** | §2a–2c. 11 detectors → 13 findings → detection coverage |
| **3 — Cleaning** | §3a Clean (sensor) · **§3b Normalize (image JSON → flat)** |
| **4 — Source agreement** | §4a. Four sources, four answers |
| **5 — Feature table** | §5a. Grain `(user_plant_id, ts_aligned)`, asserted |
| **6 — Triangulation** | §6a. Negative, for structural reasons |
| **7 — Pipeline design** | §7a–7g. Sketch only; both diagrams rendered |
| **8 — Derived signal** | §8a. `drydown_pct_per_day` |
| **9 — Log text** | §9a. A lookup, not a classifier |
| **Write-up** | `submission/WRITEUP.pdf`, one page |

**Outputs:** `cleaned_sensor.csv` · `qc_rejections.csv` · `images_flattened.csv`
· `plant_features.csv` · `task2_*.csv` (3) · `task4_source_assessment.csv` ·
`task6_triangulation.csv` · `task8_drydown.csv` · `task9_log_signals.csv` ·
`figures/` · `run.log`

## 3. Not done

Nothing. Every task and the required write-up exist.

## 4. Decisions taken, and why

Full list in `docs/decision_register.md`. The load-bearing ones:

**Two tiers, because "outside spec" ≠ "provably wrong".** Impossible → null with
a reason. Outside spec but *possible* → **flag and keep**. Collapsing them starts
deleting real data. The impossible ceilings are set **1.25×–12× above** the spec
ceilings, because a too-narrow bound nulls real data while a too-wide one merely
leaves junk flagged. Derivation per channel is in `docs/DATA.md` §8.

**Never derive a physical bound from the data.** A quantile or 3σ cut moves with
the data, so a fleet-wide fault would shift the bound and hide inside it.

**Raw is never modified.** Every fix is a new column; the original stays beside
it. Proven by multiset comparison across all four tables.

**Two time columns, and the difference matters.** `timestamp` is the **source
text as delivered** — mixed format on purpose (SENS-07 writes DD/MM), because
rewriting it destroys the evidence that two formats coexist. `ts_aligned` is the
ISO, uniform, clock-corrected column that **every join uses**.

**Detection and remediation are separate, reconciled both ways.** The audit gate
checks rejections↔nulls *and* detector↔flags. Both directions, or a check that
cannot fail.

**The code is six modules, split by change reason.** `domain.py` imports no
pandas — `AGENTS.md` §7 made structural.

**Task 3 normalizes as well as cleans.** The sensor table needed *cleaning*; the
image table needed *normalizing* — a JSON blob in one column that no consumer can
filter, join or aggregate. Both are "turn what was delivered into what can be
used", so both live under Task 3.

**The pipeline parses `data/fyta_images.csv`; consumers read
`out/images_flattened.csv`.** Reading back a file the pipeline wrote would make
it depend on its own history, and a stale copy would go unnoticed.

**Task 4 is pure prose — no code cells.** Its working is in `run.log` §4a and
`out/task4_source_assessment.csv`.

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
| **D16** | Is there a staged-publish convention to follow? | Platform |
| **D17** | What should a feature table DO about two probes? (sharpens D11) | Product |

**Plus two raised by this work, neither in the register yet:**

| Question | Owner | Why |
|:---|:---|:---|
| Did the image model consume VWC, or did one generator emit both series? | Vendor | decides whether `r = 0.75` is corroboration or an artefact |
| Does the app offer canned log phrases, or free text? | Product | decides whether the 1:1 phrase→type mapping is a schema fact or a generation signature |

**D11 blocks the most.** It closes both F9 (the join fan-out) and F10 (the probes
that don't correlate) — they are one cause with two symptoms.

## 6. Corrections made — do not repeat these

Two external audits were run; both were acted on. Every item below was
reproduced before being fixed.

**From the first audit:**

| Believed | Reality | Caught by |
|:---|:---|:---|
| The audit gate prevented bad publication | It asked *"is there ≥1 null?"* — any null satisfied it. **1,344 restored frozen values passed** | Mutation testing |
| `isolated: n - adjacent` counted isolated readings | It counted **runs**. A 431-sample excursion reported as 11 isolated; it is 11 runs, 431 in-run, **0 isolated** | Recomputation |
| `.abs()` on the EC delta was fine | A large **fall** counted as corroboration of a **rise** | Direction testing |
| F10/F12/F11's numbers | They were **transcribed**, not computed — no code produced them | Reading the code |

**From the second audit:**

| Believed | Reality | Caught by |
|:---|:---|:---|
| The gate was fixed | It reconciled **rejections** but not **flags**. Stripping all **736** `outside_spec` flags passed all 13 checks | Mutation testing |
| The image window was bounded | It was **symmetric**, so a photo 2.5 h *before* an event counted as a response | Fixture |
| "A dead sensor… one continuous fault" (write-up) | SENS-04 is *unknown*, not dead, and it is 11 runs, longest 44 — errors I introduced while rewriting for plain language | Re-verification |
| "Soil type, sensor model and plant are code" | All three are already **data** | Reading the data |
| `log_alignment` tested the plant | It tested `device_id.first()` — **one arbitrary probe** per plant | Your question about F9 |
| F11 was about watering | **Only one of four log legs was tested** | Your question |

**Process errors, self-inflicted:**

| What | Cost |
|:---|:---|
| Sliced `sensors.py` with a boundary *before* the start — duplicated half the file (983 lines) | Caught by inspecting the result |
| `git checkout HEAD -- sensors.py` to repair it | **Destroyed two pieces of uncommitted work** (`EVIDENCE_NOTES`, the multi-probe fix). Both redone. `git checkout` reverts to the last *commit*, not to "a moment ago" |
| Rewrote Task 2's evidence section when Task 4 was asked for | Reverted. **Fourth** time an adjacent-but-unrequested change was made |
| nbconvert aborting on an error **without writing**, leaving the previous run's outputs | Looks like `0 errors`. Has happened **three times**; only caught by reading the outputs |

**From the third review (Astra) — all 18 checkable claims reproduced:**

| Believed | Reality | Caught by |
|:---|:---|:---|
| The frozen rule was safe fleet-wide | It nulls **any** long unchanged run, including legitimate darkness — 52 night light readings | Fixture |
| Duplicates were deduped losslessly | Identical ones were; **conflicting** ones were dropped to an arbitrary winner | Fixture |
| The audit passed on healthy input | `len(rejections) > 0` was required, so clean batches **failed** | Fixture |
| "detected unit outliers are all fixed" | Membership, not arithmetic — every SENS-07 temp replaced with 25 °C passed | Mutation |
| `triangulate` tested the plant | It read `ec_1` / `device_1` — **probe 1 only** | Fixture |
| Untestable windows | `NaN` was reported as `"no rise"` — absent evidence as negative evidence | Fixture |
| A rate escapes the substrate calibration | **`d(ax+b)/dt = a·dx/dt`.** The gain survives; that was simply wrong | Arithmetic |
| High cross-device r makes fleet checks meaningless | Backwards — a tight shared signal is a *better* reference. And the code used it anyway | Reading |
| A NULL expected slot is fabricated data | It is not. Sparse and dense are both honest; it is a downstream choice | Reading |
| "FYTA is already using S3" | Synthetic fixture paths | Reading |
| The script wrote `run.log` | It printed a claim; the shell redirect wrote the file | Reading |
| Notebook: "65–107 … keep it" | The code nulls above **100** | Reading |
| Notebook: "F4 flagged in `qc_flags`" | 702 of 1,056 drifting rows carry no flag | Reading |

**The root cause of most of these was `AGENTS.md` itself**, which stated
assumptions as rules — "two probes must be positively correlated" propagated into
the code, the write-up, and an answer given to the owner. The file now opens by
saying it records decisions rather than evidence, and the specific claims are
amended.

**The pattern:** the audits, the ponytail review, and *running the code* each
caught what reading did not. But the third review asked questions the first two
never did — **"does the header describe what is computed?"** and **"is the stated
reason true?"** No amount of re-running the same checks reaches those.

## 7. Next actions

1. **Review the diff, then commit.** The working tree holds every fix from the
   third review and is **deliberately uncommitted** — the owner asked to see the
   changes first. Nothing else is pending.
2. **Ship.** Run kuchiku when the review is done.
3. **After the deadline**, if the repo becomes a portfolio piece: decide whether
   `docs/assessment.md` (Gregor's full email thread) and the three
   `second_opinion*.md` files should stay in it.

## 8. Unrecoverable if lost

Nothing below is derivable from the CSVs. It exists only in prose.

**The method lessons** (`observations.md` Part 2, eleven of them). The four that
carry the most:

- **Correlation cannot see a unit error.** SENS-07's temperature correlates at
  **0.9843** — the highest in the fleet — while reading Fahrenheit. `y = ax + b`
  leaves correlation untouched.
- **Two problems can hide each other.** The clock offset had to be removed before
  the unit error became clean evidence (sd 1.363 → 0.444). Structural defects
  before semantic ones.
- **A magnitude check cannot see a context problem.** The light spikes sit inside
  every stated limit. Finding them needed a fourth kind of question — comparing a
  reading against its *neighbours*.
- **A claim tested on one leg is not tested.** F11 was claimed from watering
  alone. All four log types tested, **none lines up, and light contradicts** —
  *"moved closer to window"* moves the daily peak **down** (−4.4).

**The corrections record** (§6) — evidence of method, not of success.

**The causality analysis.** The two-sensor issue is the most *interesting*
problem but causes only 2 of 13 findings; the five worst are on single-sensor
plants. That rules it out as the root cause.

**Why flag-vs-empty matters.** A successor reading only the code would likely
"simplify" the two-tier rule into one threshold — and start deleting real data.

**The four questions that changed the work.** Domain intuition beating statistics
("a person can turn on a light"), skepticism about necessity ("is that
unnecessary?"), and the two that found real defects: *"how can you fix the join if
the logs have no sensor id?"* and *"doesn't every log type have a channel that
should respond?"* Both exposed under-tested claims.
