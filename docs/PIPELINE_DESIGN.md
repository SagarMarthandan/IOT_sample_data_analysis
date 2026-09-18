# Task 7 — Pipeline design for 100,000+ devices

*"How would you productionize this as an ingestion + quality pipeline? What would
you monitor, where would bad data get caught, and how would you make the checks
maintainable as new substrates and sensors appear?"*

Two variants, one decision rule, and the numbers behind both. Vendor rates are
AWS published list, us-east-1, read 2026-09-18 — re-check before quoting.

---

## 1. First, size it

Everything below follows from this table, so it goes first.

| | |
|:---|:---|
| Devices | 100,000 |
| Readings/day | 100,000 × 96 = **9,600,000** |
| Average rate | **111 msg/s** |
| Messages/month | **288 M** |
| Row size (measured: file bytes / rows) | **67.9 B** |
| **Raw arrival** | **0.65 GB/day · 238 GB/year** |
| Parquet + zstd (measured **7.6×**) | **0.086 GB/day · 31 GB/year** |
| Published table, raw + cleaned side by side | 119 B/row · 0.17 GB/day compressed |

The published table is ~2× the arrival volume, because it keeps the raw column
beside every cleaned one. That is the price of never destroying the original, and
at this scale it is still nothing. All figures measured from the shipped sample;
the compression ratio is a real Parquet+zstd write, not an estimate.

**This is not big data.** 111 msg/s is a single process. 238 GB/year fits on a
laptop. Any architecture that leads with Spark, a data mesh, or "web-scale
streaming" is solving a problem this fleet does not have.

The real difficulties are elsewhere, and they are the ones this assessment is
about:

1. **100,000 things that can each be individually wrong** — a fleet average looks
   perfect while 300 devices are dead
2. **Data arrives late and out of order** (see §2)
3. **The semantics are hard** — substrate curves, unit errors, drift, artefacts
   vs signal. The checks are the product, not the plumbing

## 2. The constraint that actually shapes it

The Beam is **BLE** — it cannot reach the internet on its own. So ingestion is
relayed: phone app or hub. Two consequences that decide the whole design:

**Uploads are bursty and human-scheduled.** The app syncs when the phone is open
and online. A phone offline for three days delivers three days at once.

**The buffer bounds the lateness.** ~320 measurements per device. **If the
deployed generation buffers 320 readings at four per hour**, that is **up to ~80
hours late** — but the published figures are ambiguous: Beam 1.0 is listed at
1/hour and Beam 2.0 at 4/hour, and the 320-reading store is described as ~13 days,
which matches 1/hour. The watermark below is therefore conditional. **Confirm
generation-specific storage with firmware** (D2/D6). So:

> **Partition by event time, not arrival time.** An 80-hour watermark is normal,
> not exceptional. Late writes must replay and re-audit the *affected* partition,
> not just append to today's.

This is the single constraint most likely to be got wrong, and it comes straight
from the hardware spec rather than from the data volume.

It is also the strongest argument for dbt (§12): `is_incremental()` with a
`unique_key` compiles to a `MERGE`, which is exactly the upsert a late partition
needs. Hand-written, that logic is a test-free liability.

## 3. The shape, in both variants

```
  device ──BLE──▶ phone app / hub
                        │  HTTPS, bursty, late by hours to days
                        ▼
                 ┌─────────────┐
                 │   INGEST    │  auth, schema, per-reading range check
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │    RAW      │  immutable, append-only, partitioned by
                 │  (the lake) │  EVENT DATE. Never edited. Replayable.
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐   ┌──────────────┐
                 │  VALIDATE   │──▶│  QUARANTINE  │  rows + the reason
                 └──────┬──────┘   └──────────────┘
                        │  publish only if every gate passes
                 ┌──────▼──────┐
                 │  PUBLISHED  │  cleaned · per-plant features
                 └──────┬──────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
        dashboards / alerting   model + calibration training
```

Both variants are this shape. They differ only in **what each box is made of**,
and that is a build-vs-buy question, not an architecture question.

## 4. Variant A — self-hosted / OSS

| Concern | Choice | Why this and not the obvious one |
|:---|:---|:---|
| Ingest buffer | **Redpanda** | Kafka API in one binary. No ZooKeeper, no JVM tuning. Kafka's own ops are the cost here, not its throughput |
| Stream checks | **a Python consumer** | Per-*message* checks only — reject at ingest. A loop, not complex event processing; Flink or Spark Streaming would be a second system to operate for 111 msg/s. The per-*window* checks are SQL and belong in dbt (§12) |
| Lake | **MinIO + Parquet** | S3 API, so the code is portable to AWS later. This is the whole point of MinIO |
| Transform | **DuckDB + dbt** (`dbt-duckdb`) | 0.6 GB/day in a columnar file. DuckDB reads Parquet faster than a warehouse cluster starts up; dbt is the layer above it — models, tests, lineage (§12) |
| Orchestration | **Airflow** | Ubiquitous, so new hires already know it. Dagster is nicer and less known |
| Serving | **Postgres (+ TimescaleDB)** | The per-plant feature table is 12k rows here, ~150M at fleet scale. Still Postgres |
| Dashboards | **Grafana** | Same tool for infra and data freshness |
| Analytics | **Metabase** | Non-technical users, self-serve, no SQL needed |
| Deploy | **Docker Compose → k8s when it hurts** | Compose on one box until it doesn't fit. It won't fit at ~10× |
| Ops agent | **a small on-box watchdog** | Restarts, log tailing, disk pressure, certificate expiry — the things that page someone at 3am. And the first component to delete when moving to Variant B, because managed services absorb exactly this job |
| Model lifecycle | **MLflow** | Calibration curves are models (§10) |

Rough infrastructure: **one to four nodes**, ~€150–400/month. Plus an engineer.

## 5. Variant B — AWS managed

| Concern | Choice | Why |
|:---|:---|:---|
| Ingest | **IoT Core** → rules → S3 | Device registry, per-device auth and revocation out of the box. Certificates are the hard part of a fleet; don't build them |
| Messaging cost | **Basic Ingest** (reserved topic `$aws/rules/…`) | **Messaging is free on this path** — you pay rules + actions only. This is the single biggest lever in the design |
| Buffer (optional) | **Kinesis Data Streams** | Only if you need sub-minute alerting. See below |
| Lake | **S3**, Parquet, partitioned by event date | Already in use — the image path is `s3://fyta-plant-images/…` |
| Transform | **dbt** on **DuckDB/Lambda** or **Athena** | Skip Glue/EMR Spark. 0.6 GB/day does not need a cluster. Only the dbt adapter changes — `dbt-duckdb`, `dbt-athena` |
| Orchestration | **Step Functions** (or MWAA) | Step Functions is cheaper and needs no one to run it |
| Serving | **RDS Postgres** | Same schema as Variant A |
| Dashboards | **Managed Grafana** | Same query language as Variant A |
| Analytics | **QuickSight**, or Metabase on EC2 | Keep Metabase if the team already knows it |
| Model lifecycle | **SageMaker**, or MLflow on EC2 | The calibration registry is the same shape either way |

### Cost, from published rates

```
connectivity, 15 min every hour     1,080 M-min  × $0.08 = $ 86.40/mo
connectivity, 24/7 connected        4,320 M-min  × $0.08 = $345.60/mo
messaging via Basic Ingest            288 M      × $1.00 = $  0.00/mo   ← free
rules + actions                       576 M      × $0.15 = $ 86.40/mo
                                                    IoT Core ≈ $173–432/mo
S3, raw 18 GB/mo                                                  $0.41/mo
S3, compressed ~4 GB/mo                                           $0.09/mo
```

**The pipeline is not the cost driver — the connection model is.** Keeping 100k
devices connected 24/7 costs $346/month; connecting only to send costs $86. And a
BLE sensor relayed by a phone may never hold an IoT Core connection at all.

### And the option that needs no broker

If readings only need to reach a dashboard in **minutes, not seconds**, skip the
stream tier entirely:

```
IoT Core rule → S3 (event-date partition) → batch validation on the new partition
```

At 0.6 GB/day that is a few seconds of DuckDB. A broker earns its place when
something must react *per message* — live alerting, or a device command. Until
then it is a system to operate for no benefit. **Start here; add Kinesis when a
requirement actually needs it.**

## 6. The decision rule

**Volume does not decide this.** 0.6 GB/day runs on a laptop, so the choice
between Variant A and Variant B is not technical capacity, it is **total cost of
ownership**:

| | Variant A | Variant B |
|:---|:---|:---|
| Infrastructure | €150–400/mo | ~$200–500/mo |
| **Operational load** | Kafka + Airflow + MinIO + Grafana to patch, upgrade and be paged for — **~0.3–0.5 FTE** | ~0.05 FTE |
| Lock-in | none | IoT Core rules, Kinesis, QuickSight are sticky |
| Marginal cost at 10× | unchanged | scales linearly |

At a loaded engineer cost of ~€7,000/month, **0.3 FTE is ~€2,100/month**. That is
10–20× the infrastructure difference. So:

> **Managed wins, and it is not close — because the scarce resource is the
> engineer, not the euro.**

**Flip to Variant A when:**

1. **10× the fleet.** 1M devices → ~$860–3,450/month on IoT Core alone, and
   per-message pricing starts to bite. Self-hosted infra grows sublinearly
2. **A residency or on-prem requirement.** Professional/B2B sites may contract for
   it, and that is a contract, not an engineering preference
3. **The team already runs k8s competently.** Then Variant A's ops cost is much
   lower than 0.3 FTE, and the calculus changes
4. **Egress or vendor repricing.** AWS changed IoT Core pricing once already

And the point that makes the two not really rivals:

> **Keep the checks portable and the substrate becomes a deployment detail.**
> The validation logic is Python and SQL over Parquet. It runs on MinIO + DuckDB
> exactly as it runs on S3 + Athena. Design the exit on day one, so the decision
> above can be revisited cheaply rather than re-litigated.

## 7. Where bad data gets caught

Six layers, cheapest first. A check belongs in the earliest layer that can hold
it — the firmware rejecting an impossible reading costs nothing; the same reading
caught after it has been written, replicated and indexed costs a pipeline.

| # | Layer | Catches | Failure mode if missing |
|:---|:---|:---|:---|
| 1 | **Firmware** | physically impossible readings, before transmission | you pay to transport garbage |
| 2 | **Ingest** | malformed payloads, unknown device, **unknown substrate**, impossible ranges | a schema change becomes silent NULLs |
| 3 | **Stream / per-reading** | out-of-range, impossible, duplicate keys | at-least-once delivery becomes duplicates |
| 4 | **Batch / per-device window** | frozen channel, **slot-grid gaps**, drift, clock offset, unit outliers, co-located disagreement | **the expensive class** — invisible per row |
| 5 | **Publish gate** | nothing reaches a consumer unless every check passed | a consumer reads half-verified data |
| 6 | **Post-publish monitoring** | what the gates missed — freshness, volume, distribution | you find out from a model, weeks later |

**Layer 4 is where this assessment's findings live**, and it is where the effort
belongs. Every one of the 13 findings is a per-device-window question that a
per-row check cannot see:

| Finding | Blind to it |
|:---|:---|
| F3 frozen channel | every value is *in range* and the value is *constant* |
| F7 the 48.5 h hole | the file has zero nulls — only the expected-slot grid shows it |
| F2 clock offset | a correctly-formatted timestamp that is simply two hours wrong |
| F5 sustained out-of-spec | each reading is individually possible |
| F12 shared ambient | the reading is correct; the *comparison* was the error |

**Rules that keep the gates honest**

- **Parse strictly.** Match an explicit registry; fail loudly on the unknown with
  the offending rows named. `errors="coerce"` turns a schema change into silent
  NULLs — the failure you find three weeks later from a model that lost 12 % of
  its rows
- **Two tiers, never one.** *Physically impossible* → quarantine. *Outside the
  specified range but possible* → **flag and keep**. Collapsing these starts
  deleting real data
- **Detection and remediation are separate claims**, and must reconcile **in both
  directions** — a detector with no fix is a bug, a fix with no detector is a bug
- **Never clip, never average away, never interpolate.** Each manufactures a
  measurement that was never taken

## 8. What to monitor

The four standard pillars, plus two that matter disproportionately for a fleet.
All per device — a fleet average hides exactly the failures you are looking for.

| Pillar | Check | Alert on |
|:---|:---|:---|
| **Freshness** | age of the newest reading per device | a device silent past its cadence, with hysteresis |
| **Volume** | readings per device per day | *below* expected, not just zero |
| **Schema** | unknown field, substrate or sensor family | immediately — this is a contract break |
| **Distribution** | per-channel drift vs its own history | movement that exceeds its own noise band |
| **Slot-grid completeness** | every slot the device *should* have produced, accounted as present / missing / surplus | a device at 60 % present looks fine on row counts |
| **Frozen-channel detection** | zero variance over a rolling window **while the same device's other channels keep moving** | the cross-channel comparison is what separates a dead sensor from a genuine plateau |

Alerts must not flap: require the condition to persist, and use **different
thresholds to raise and to clear**.

## 9. Making the checks maintainable

This is the part that decays, and the brief asks about it directly. Four
mechanisms, in order of importance.

**1. One declarative registry — domain knowledge, no I/O.**

```
substrates:   substrate → conversion-curve version, expected VWC band
sensors:      family → channels, units, cadence, spec range, impossible range
devices:      device → family, substrate, install date, clock offset
```

A new substrate is a **row**, not a deploy. A new sensor family is a **registry
entry**, and an unrecognised one **fails loudly** rather than being silently
mapped to a default. The registry contains no `import pandas` — pipeline code
depends on domain knowledge, never the reverse.

**2. Every check declares what it is blind to.**

This is the mechanism that actually keeps coverage honest, and it is already in
this submission as `task2_detection_coverage.csv`. Each finding carries the check
that caught it *and* the obvious check that is structurally blind to it:

| Finding | Caught by | Blind because |
|:---|:---|:---|
| F2 clock offset | cross-device daylight correlation | every timestamp is well-formed |
| F3 frozen channel | run-length + cross-channel | every value is in range |
| F7 the hole | expected-slot grid | there are no nulls to find |
| F8 duplicates | key cardinality | the payloads are identical |

Without this table, adding checks creates the *feeling* of coverage. With it,
the gap is visible, so the next check is aimed at a real blind spot rather than
at another angle on something already covered.

**3. Detection ≠ remediation, reconciled both ways.**

```
for device in detect_unit_outliers(raw):  assert device in UNIT_FIXES
for device in UNIT_FIXES:                 assert device in detect_unit_outliers(raw)
```

A fix with no detector silently rots; a detector with no fix is a warning nobody
acts on. The pair is the unit of maintenance.

**4. Regression fixtures.**

A frozen copy of a known-bad window per failure class, replayed on every change,
asserting each is still caught. Cheap, and it is the only thing that stops a
refactor from quietly removing coverage. (This is the same job as `assert_grain`
and the audit gate in the current code, scaled up.)

## 10. Model and calibration lifecycle

The thing most likely to be forgotten, and it is already a finding here.

**`soil_moisture_vwc` is not a measurement — it is a model output.** Dielectric
permittivity through a **substrate-specific conversion curve**. So every VWC value
has a model version, and in this dataset that version is **unrecorded and
undated** (F13: the substrate label has no effective dating, and UP-1006 is
repotted mid-window with the label never moving).

The pipeline must therefore treat derived values as **versioned artefacts**:

- Every derived column records the **code + curve version** that produced it
- The substrate curve is a **registered artefact**, not a constant in a script
- A curve change is a **rebuild**, not a backfill — you cannot mix vintages in one
  column and still compare rows
- Third-party model output (the image feed) is **gated at ingestion**: pin
  `model_version`, fail on an unknown head name, treat a new class as a schema
  event

## 11. What I would ask FYTA

The design forks on these, and none can be answered from the data.

| # | Question | Why it changes the design |
|:---|:---|:---|
| 1 | **Is there a hub/gateway, or does the phone relay?** | Sets the burst size, the lateness bound, and whether IoT Core connectivity is even billable |
| 2 | **What latency does a dashboard need — minutes or hours?** | Decides whether a stream tier exists at all (§5) |
| 3 | **Do professional sites contract for residency or on-prem?** | A contract requirement makes Variant A mandatory regardless of cost |
| 4 | **Who is on call, and for what?** | The whole build-vs-buy argument (§6) |
| 5 | **What is the fleet plan — 1M devices?** | The only thing that moves the marginal-cost line |

## 12. dbt — the transform layer

Both variants name dbt in their Transform row. It earns a section of its own,
because the first draft of this design left it out and that was wrong. The test is
simple: **map each operation in the cleaning code to the thing that expresses
it.**

| Operation | Expressed as |
|:---|:---|
| parse two date formats | `try_strptime` + `CASE` |
| clock offset by device | join to a device lookup |
| unit conversion | arithmetic |
| impossible → null, out-of-spec → flag | `CASE` |
| frozen window (run-length) | gaps-and-islands |
| dark-hour spikes | window over neighbours |
| `vwc_pct` trailing rank | `percent_rank() OVER (ROWS BETWEEN 672 PRECEDING …)` |
| per-plant wide table | conditional aggregation |
| correlation, affine fit | `corr()`, `regr_slope()` |

**14 of the 15 operations in this submission are expressible in SQL.** The
Python is a choice, not a constraint — so the transform layer belongs in dbt, and
it belongs there in *both* variants, because only the adapter changes.

**What it adds over the Python:**

| In this submission | As a dbt construct |
|:---|:---|
| `assert_grain()` | `unique: [device_id, ts]` — a test, not a function |
| `SPEC` / `IMPOSSIBLE` ranges | `accepted_values`, or a custom range test |
| the audit gate's 12 checks | a test group that must pass before publish |
| registry integrity | `relationships: device_id → registry` |
| **the registry table** | **a seed** — "a new substrate is a data change, not a deploy", literally |
| the late-arrival upsert | `is_incremental()` + `unique_key` → `MERGE` |
| lineage and docs | an output, not an artefact to maintain |

**Where it is NOT the answer.** dbt runs on a warehouse or a lake; it does not
run inside a broker consumer. Per-message checks — reject at ingest, live
alerting — stay in Python. The boundary is clean: **per-message in the consumer,
per-window in dbt.**

**The cost, stated honestly.** dbt means a second execution model, a
`profiles.yml`, and a project layout beside 1,100 lines of working Python. At one
developer that is a real cost, and it is not obviously worth paying today. It is
worth paying the moment a **second person** has to read, review or extend the
transforms — which at 100k devices is a matter of when, not if.

---

## Recommendation

**Build Variant B, but write it so Variant A stays cheap.** IoT Core + S3 +
DuckDB, no broker until a requirement needs one, orchestration in Step Functions.
Keep validation as SQL over Parquet — in dbt once a second person needs to read
it, in plain scripts until then — with the domain registry in one place and no
I/O in it.

That is ~$200–500/month and near-zero operational load, on a stack FYTA is
already using. Revisit it at 1M devices, or the first residency requirement —
and because the checks were kept portable, revisiting it is a deployment change
rather than a rewrite.
