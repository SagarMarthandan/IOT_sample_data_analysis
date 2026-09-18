# AGENTS.md — Data Engineering Principles

This file is binding for every task in this repository. Read it before acting.
It exists because the expensive mistakes in data work are not bugs — they are
**reasonable-looking decisions made without knowing what the data physically
is.** A pipeline that runs cleanly and reports the wrong number is worse than
one that crashes, because nobody investigates a pipeline that works.

Sources are listed at the end. Where a rule is derived from a published
standard or framework, the rule says so, so you can go and check it.

---

## TL;DR — the seven rules most often broken

1. **Understand the instrument before interpreting the value.** A number from a
   sensor is not the physical quantity; it is a conversion, and the conversion
   has assumptions.
2. **Never repair data in place.** Raw is immutable. Every fix is a new column
   with a name that says what it is.
3. **`NULL` means "unknown". It never means zero, and it is never filled
   silently.** Interpolation is a separate, labelled column.
4. **Declare the grain of every table and assert it.** Check join cardinality
   before joining — an unnoticed fan-out silently multiplies every average.
5. **State what you did not handle.** An unfinished analysis that names its gaps
   is worth more than a finished one that hides them.
6. **Every script is written in ponytail mode.** Smallest thing that works; no
   speculative abstraction, no boilerplate, no dependency for what stdlib does.
   Read `skill://ponytail` before you write code. See §16.

---

## Part 1 — Domain ground truth (FYTA)

Read this before touching sensor data. Full provenance in Sources.

The **FYTA Beam** is a BLE sensor with metal prongs driven into the pot. It does
**not** measure water. It measures **dielectric permittivity** in the root zone
and converts that to Volumetric Water Content through a **substrate-specific
conversion curve**.

Consequences that govern everything downstream:

| Fact | What follows |
|---|---|
| VWC is a *derived* value from a dielectric reading | `soil_moisture_vwc` is only comparable across plants when the substrate conversion is comparable. Absolute thresholds are wrong across substrates. |
| Substrate is a **calibration parameter**, not a label | A wrong or stale substrate label means the number was produced by the wrong curve. That is a magnitude error, not a cosmetic one. |
| Probes sit in the **lower third** of the pot | It is a *point* reading near the bottom where water collects — not a pot average. Do not read it as "the plant's water". |
| Probes are modular, **3–35 cm** | Two sensors in one pot need not be at the same depth. They must still be *positively correlated* — they share one water reservoir. |
| Device reports **1×/hr typical, up to 4×/hr** | 15-minute data is at the sensor's maximum rate. Absence is meaningful. |
| Offline buffer ≈ **320 measurements** | At 4×/hr that is ~80 hours. Longer outages lose data permanently — not a recoverable gap. |
| G2 **self-calibration** causes shifts for up to **48 h** after | A step change may be a legitimate calibration, not a fault. Rule it out before calling it one. |
| Self-calibration is **unsupported** without drainage holes | Some users structurally cannot calibrate. Not every bad reading is user error. |

Published specification (verify against the actual device generation in use):

| Quantity | Spec |
|---|---|
| VWC | 0–65 %, variance ±5 % |
| EC | 0.3–1.7 mS/cm |
| PAR | up to 2000 µmol/m²/s, ±0.5 % |
| Ambient temperature | −5 … 50 °C |

**A reading outside the manufacturer's specified range is not an outlier — it is
evidence that the instrument failed or the conversion is wrong.** Those are
different conclusions with different fixes, and only the domain can tell you which.

### Prove it or flag it

Published specs are marketing-adjacent and go stale. When a decision depends on
a spec, say which source it came from and mark it for confirmation. When the
data cannot settle a question, **name the expert and the question** — firmware
for clock and sampling behaviour, horticulture for substrate norms, calibration
for sensor tolerances. Never guess silently and never leave a load-bearing
assumption unlabelled.

---

## Part 2 — The principles

### 1. Immutability of raw
Raw data is an append-only log. Never edit, never "fix", never normalise in place.
Every transformation must be re-runnable from raw. If a transform is wrong, the
fix is a code change and a re-run — not a patch to the data.

### 2. Idempotency
Running the same job twice on the same input must produce the same output and
must not duplicate anything.
- Derive batch boundaries from parameters (date, watermark, file), **never from
  `NOW()`**.
- Prefer `MERGE`/upsert on a deterministic key, or atomic partition overwrite.
- Before shipping anything, ask: *what happens on retry?*

### 3. Write–Audit–Publish
Never write unvetted data where a consumer can read it.
1. **Write** to staging.
2. **Audit** — schema, volume, nulls, keys, ranges, distribution.
3. **Publish** atomically, and only if every gate passed.

On failure: halt, alert, route the offending rows to a **quarantine table with
the reason attached**. Do not drop silently. Do not promote partially.

### 4. Grain and keys are contracts
Declare the grain of every table. Assert it on load. Before every join, check
cardinality of both sides — a non-unique right-hand key turns a `LEFT JOIN` into
a row multiplier, and the resulting wrong numbers look completely plausible.

When duplicates exist, **separate redundant copies from conflicting ones**.
Identical payloads are an at-least-once redelivery and dedupe losslessly.
Rows that disagree on the same key are unorderable — keep both, flag both, and
never resolve them by arbitrarily keeping one.

### 5. Parse strictly; never coerce
Match input against an explicit registry of known formats and **fail loudly on
anything unrecognised**, naming the offending rows.
- `errors="coerce"` turns a schema change into silent `NULL` — the failure mode
  you discover three weeks later from a model that quietly lost 12 % of its rows.
- When a format is ambiguous, resolve it with **evidence**, not convention. Show
  which reading is impossible, not which one is usual.
- A self-check must not fire on healthy input. A monitor that cries wolf is worse
  than no monitor, because it trains people to ignore it.

### 6. Missing ≠ zero ≠ interpolated
- `NULL` means unknown.
- **Never clip** an out-of-range value to the boundary — that manufactures a
  measurement that was never taken. Null it, and keep the fact that it failed.
- **Never average away** an anomaly.
- Any imputation is a **new column** (`x_filled`, `x_interpolated`) with the
  method recorded. The original column keeps its holes.
- Record *why* a value was rejected, per value, in a reason column.

### 7. Domain assertions live in one reviewable place
Physical limits, expected cadence, grain, and per-substrate norms belong in a
declarative table — **not as inline magic numbers scattered through transforms**.
A new substrate or sensor family should be a data change, not a code deploy.

Keep it free of I/O. Domain knowledge must not know that CSVs or pandas exist.
Dependency runs one way: **pipeline code depends on domain knowledge, never the
reverse.**

### 8. Point-in-time correctness
Any attribute that can change — substrate, probe depth, calibration state, the
plant a device is assigned to — needs **effective dating**. A snapshot join puts
today's value onto all history and silently rewrites the past.

Distinguish two timelines:
- **Valid time** — when the value was true in the world.
- **Transaction time** — when we learned it.

For sensor work, valid time is what the model needs; transaction time is what an
audit needs. Conflating them is how a backfill corrupts a training set.

### 9. Quality gates — the six dimensions
Check every one of these explicitly. Name them in the output so a reader can see
which were tested (DAMA-DMBOK):

| Dimension | The question | Concrete check |
|---|---|---|
| **Validity** | Does it conform to the declared domain? | type, format, range, allowed values |
| **Completeness** | Is it all there? | against an **expected slot grid**, not row counts |
| **Uniqueness** | Any unintended duplicates? | primary key cardinality |
| **Consistency** | Do related values agree? | cross-table totals, redundant-channel agreement |
| **Timeliness** | Is it fresh enough for its purpose? | lag vs SLA; staleness at point of use |
| **Accuracy** | Does it match reality? | against a trusted source — **state which** |

Accuracy is the one you usually cannot test alone. Say so, and say what would
test it.

### 10. Observability — four pillars
Monitor **freshness, volume, schema, distribution** for every asset. Two checks
that matter disproportionately for fleets:
- **Completeness against a slot grid.** Build the grid each device *should* have
  produced and account for every slot as present, missing, or surplus. Row counts
  hide a device that is half-present.
- **Frozen-channel detection.** Zero variance over a rolling window, while the
  same device's *other* channels keep moving, is a dead sensor — not a plateau.
  The cross-channel comparison is what distinguishes them.

Alerts must be actionable and must not flap: require a condition to persist, and
use distinct thresholds for raising and clearing.

### 11. Distinguish event from artefact — and name the third option
For any anomaly, decide explicitly which it is:
- **Sensor/data problem** — the instrument, the transport, or the transform failed.
- **Real physical signal** — the world did that.
- **Third option, easy to forget** — generation/production artefacts, schema
  changes, human error in labels, or a documented device behaviour such as
  self-calibration.

Useful discriminators: Does it violate the instrument's own spec? Do the *other
channels on the same device* stay healthy? Is the shape a clean mathematical
function (a perfectly linear ramp, an exactly periodic interval, an exact
constant) where the domain says it should be organic? Does it respond to logged
events? Does it recur at a suspiciously round time?

Some anomalies are **single-sample artefacts** and are safe to null; others are
**regime changes** and are not. Never apply one treatment to both.

### 12. Labels are data, and usually the dirtiest kind
User-entered labels, model predictions, and free text all carry error rates.
- Do not validate a measurement with a label you have not characterised.
- **Check whether a model's output is independent evidence at all.** If the
  model's dominant signal is the same quantity your sensor measures, agreement is
  a restatement, not a confirmation. Say so.
- A derived field that is a threshold on another field adds no information.
- Look for the vocabulary before building a classifier on it. A lookup beats a
  model when the vocabulary is small.

### 13. Schema evolution is a contract
Breaking changes: removing a required field, adding a required field without a
default, incompatible type change, direct rename. Safe changes: adding optional
fields, removing optional fields, widening numeric types.

When a producer changes shape, the contract changes first and the consumers
follow. Do not discover it from a `NULL` column.

### 14. Security and privacy
No secrets in code or notebooks — environment or a secret manager only. Least
privilege for anything that reads data. Mask, hash, or tokenise personal data at
the ingestion boundary, before it can be copied downstream.

### 15. Evidence over assertion
Every claim in a report or write-up must be traceable to a query, a file, or a
command whose output you have seen. Distinguish what you **measured** from what
you **infer**, and label the inference.

A result you cannot reproduce is not a result.

---

### 16. Every script is written in ponytail mode

**Standing instruction from the repo owner: all code in this repository is
written under the `ponytail` skill.** I do not need redundant code.

#### Why this is not "self-activation"

Every ponytail skill ships with `Never self-activate` in its description, and
that guard exists to stop an agent deciding on its own to change how it writes
code. **This rule is not that.** It is the owner's explicit opt-in, recorded
durably in the file the owner controls — which is the trigger the skill itself
names: *"Apply ONLY when the user explicitly asks for it."* The guard is
satisfied by this paragraph, once, here.

It applies to **code**. It does not license activating ponytail for prose,
analysis, documentation or explanation the owner did not ask you to shorten.

#### Before writing any code

Read the skill. It is `hide: true`, so it will **not** appear in the
auto-surfaced skill list — fetch it explicitly:

```
skill://ponytail          (or ~/.omp/skills/ponytail/SKILL.md)
```

**Standing level: `full`** — the ladder enforced. Switch per session with
`/skill:ponytail lite|ultra`; `ultra` challenges requirements, which is a poor
fit for a fixed brief. Deactivate with "stop ponytail" / "normal mode".

#### The ladder — stop at the first rung that holds

1. **Does this need to exist at all?** Speculative need = skip it, say so.
2. **Does it already exist in this repo?** Reuse it. Look before you write.
3. **Stdlib does it?** Use it.
4. **Native platform feature covers it?** Use it.
5. **An already-installed dependency solves it?** Use it — never add a new one
   for what a few lines can do.
6. **Can it be one line?** One line.
7. **Only then:** the minimum code that works.

#### What this rules out

- No interface with one implementation, no factory with one product, no config
  for a value that never changes.
- No scaffolding "for later". Later can scaffold for itself.
- No abstraction before the second use site exists.
- Deletion over addition. Boring over clever.
- Fewest files possible. Shortest working diff wins.

#### What it does NOT cut

Ponytail is explicit that laziness shortens **the solution, never the reading**:
*"Never lazy about understanding the problem… Laziness that skips comprehension
to ship a small diff is the dangerous kind."* That is the same rule as §1 and §11
of this file, and it is not optional here.

Never simplify away: input validation at trust boundaries, error handling that
prevents data loss, security, or **anything explicitly requested**.

Also exempt, and directly relevant to this project: *"Hardware is never the
ideal on paper: a real clock drifts, a real sensor reads off… Leave the
calibration knob."* Sensor-facing code keeps its tolerance parameters.

#### Mark deliberate corners

A simplification that knowingly cuts a corner with a real ceiling gets a comment
naming the ceiling and the upgrade path:

```python
# ponytail: O(n^2) dedupe, fine below ~10k rows; index by device_id if this grows
```

#### It is not finished without a check

*"Lazy code without its check is unfinished."* Non-trivial logic — a branch, a
loop, a parser, anything touching money or data integrity — leaves **one
runnable check** behind. That check is the ponytail minimum, not bloat.

#### Close the loop on every diff

Before presenting code, run the review form over what you wrote:

```
skill://ponytail-review
```

It reports over-engineering as `L<line>: <tag> <what>. <replacement>.` and ends
with `net: -<N> lines possible.` **Apply the findings** — a review that produces
a list nobody acts on is just more prose. If the honest answer is that the diff
is already lean, it will say `Lean already. Ship.`

#### Scope note for the assessment

The brief explicitly requests explanation — *"walk us through your thinking"*,
*"be explicit about what you handle… and why"*. Ponytail's own carve-out applies:
*"Explanation the user explicitly asked for (a report, a walkthrough, per-phase
notes) is not debt, give it in full."* So: **minimal code, full reasoning.** The
two do not conflict, and both are graded.

---

### 17. Record the observations as the work happens

**Nothing noticed in a session may exist only in that session.** The conversation
is not durable. The reasoning behind a decision is worth more than the decision,
and neither survives if it isn't written down.

Record these, as they occur — not at the end:

| Kind | Example |
|---|---|
| **Findings** | a defect, its evidence, its severity, its class |
| **Decisions and why** | the choice made, what it rests on, what would reverse it |
| **Corrections** | *"I believed X; tested it; wrong, because Y"* |
| **Open questions** | with the **owner** — who can actually answer it |
| **Questions asked and answered** | recorded verbatim, not paraphrased |

**Where it goes:**

| File | Holds |
|---|---|
| `docs/observations.md` | findings, method lessons, mistakes, open items — the report material |
| `docs/decision_register.md` | choices awaiting an external conversation, with owners |
| `docs/HANDOFF.md` | current state, so a new session can continue |

**Questions belong with their answers.** When the owner asks something, record
the question **verbatim** at the top of the section that answers it — not in a
separate log. A lesson separated from the question that produced it loses the
reason it was learned.

**When:** after each discussion or phase boundary. Not batched to the end.

**Record the corrections.** An entry that says *"here is what I got wrong and
what caught it"* is stronger evidence of method than one that only lists
successes — and it is the first thing a reviewer trusts. Three of the bugs found
in this project were introduced and caught within the same hour; the record of
that is the point.

### 18. Maintain a handoff document

**The context window is finite, and most harnesses expose no API to measure it.**
Verify before relying on a threshold: a token *budget* counter is not a context
metric, and `total: None` means no ceiling exists to measure against.

Because detection cannot be assumed, the safe rule is **continuous maintenance,
not threshold triggering.** The document is *updated*, never recreated, so there
is no moment where a long session holds insights that exist nowhere else.

**Triggers, in order:**

1. **If** the harness exposes context usage and it reaches **85%** — write
   immediately, before doing anything else.
2. **Otherwise** — at every phase boundary, check whether the session has grown
   long or accumulated substantial work. If so, update the document.
3. **On request** — always.
4. **Before a long or risky operation** — a large refactor, a batch of parallel
   agents, anything whose output could flood the context.

**What it must contain** — a reader with no memory of the session should be able
to continue:

- **State now.** What exists, where, and whether it runs. Exact paths.
- **Decisions taken, and the reasoning.** Not just *what* — *why*, and what would
  reverse it.
- **Open items**, each with the **name of who can resolve it**.
- **Corrections made**, so a successor doesn't repeat them.
- **Next actions**, specific enough to start on.
- **Anything unrecoverable if lost** — the highest-value section, and the reason
  the document exists at all.

**Never lose a session's insights to a context limit.** A handoff written
proactively costs minutes; one written too late costs the work.

---

## Part 3 — Hard rules

**Never**
- Edit raw data in place.
- Silently coerce, drop, or impute.
- Clip to a boundary, or average away an anomaly.
- Write to a consumer-facing table without a passing audit gate.
- Join on a key whose uniqueness you have not checked.
- Report a number you have not seen the output for.
- Present a vendor spec as established fact without naming its source.
- Leave a load-bearing assumption unlabelled.
- Write code without reading `skill://ponytail` first (§16).
- Add an abstraction, a config value, or a dependency before the second use case
  exists.
- Ship non-trivial logic with no runnable check.

**Always**
- Declare and assert grain.
- Rebuild from raw rather than patching forward.
- Distinguish sensor fault / physical signal / artefact.
- Name what you left unsolved, and what would solve it.
- Prefer a boring, readable solution to a clever one.
- Run `skill://ponytail-review` over new code before presenting it, and apply
  what it finds.
- Mark deliberate corners with a `ponytail:` comment naming the ceiling.
- Record observations, decisions and corrections to `docs/` **as they occur**,
  not at the end of the work (§17).
- Keep `docs/HANDOFF.md` current at every phase boundary — never wait for a
  threshold to trigger it (§18).

---

## Part 4 — Definition of done

A task is done when **all** of these hold, and the write-up states them:

1. The result is **reproducible** from raw by running the code.
2. Re-running is **idempotent**.
3. Declared **grain holds**, or its violation is reported with a count.
4. **Quality gates** ran, and the output names which ones.
5. Every anomaly is **classified** — fault / signal / artefact / unknown — with
   the evidence used.
6. Anything **left unhandled is named**, along with what would handle it and who
   to ask.
7. Claims are supported by **output you have seen**, not by expectation.
8. Code was written under `skill://ponytail` and reviewed with
   `skill://ponytail-review`; findings applied or explicitly declined.

---

## Sources

- **Ponytail** — lazy-senior-dev mode, the ladder, and the review skill.
  Installed locally at `~/.omp/skills/ponytail*/SKILL.md`.
  [github.com/DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)

- **DAMA-DMBOK** data quality dimensions — Accuracy, Completeness, Consistency,
  Timeliness, Validity, Uniqueness.
  [IBM](https://www.ibm.com/docs/en/ws-and-kc?topic=quality-data-dimensions) ·
  [Collibra](https://www.collibra.com/blog/the-6-dimensions-of-data-quality)
- **Write-Audit-Publish** and idempotency patterns.
  [Prefect](https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience) ·
  [WAP walkthrough](https://medium.com/@sathishdba/write-audit-publish-wap-pattern-in-data-pipelines-19defcfe73a8)
- **Data contracts and schema compatibility.**
  [Confluent schema evolution](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) ·
  [Conduktor data contracts](https://www.conduktor.io/blog/kafka-data-contracts)
- **IoT / time-series validation and anomaly detection** — frozen-sensor
  detection, gap alerting, physical bounds, alert hysteresis.
  [PyCharm anomaly detection guide](https://blog.jetbrains.com/pycharm/2025/01/anomaly-detection-in-time-series/) ·
  [VictoriaMetrics handbook](https://victoriametrics.com/blog/victoriametrics-anomaly-detection-handbook-chapter-3/)
- **SCD Type 2 / bi-temporal point-in-time correctness.**
  [Dual-SCD2 design](https://medium.com/model-driven-data-engineering/why-we-choose-dual-scd2-bi-temporal-historization-for-a-bank-grade-data-platform-9c879ec1a25b) ·
  [SCD2 reference](https://www.ssp.sh/brain/slowly-changing-dimension-type-2/)
- **FYTA hardware specifications.**
  [Technical data](https://fyta.de/en/pages/technische-daten) ·
  [Beam G2](https://fyta.de/en/products/fyta-beam-gen2) ·
  [Why soil moisture measurement is complex](https://magazin.fyta.de/en/website-en/fyta-app-guide-en/why-soil-moisture-measurement-is-complex-fyta/) ·
  [Self-calibration (G2)](https://magazin.fyta.de/website/fyta-app-guide/selbstkalibrierung-so-passt-du-deinen-fyta-sensor-an-dein-individuelles-substrat-an/)
