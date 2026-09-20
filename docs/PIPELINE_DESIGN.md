# Task 7 — Pipeline design for 100,000+ devices

This note recommends a production ingestion and quality pipeline for 100,000+
devices. Vendor rates are AWS published list, us-east-1, read 2026-09-18 —
re-check before quoting.

---

## 1. First, size it

The size determines the processing choices.

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

Published raw+cleaned output is ~2× arrival volume. Figures use the shipped
sample; the compression ratio is a Parquet+zstd write.

**This is not big data.** 111 msg/s is a single process and 238 GB/year fits on
a laptop. The fleet risks are individual device failures, late or out-of-order
data, and substrate, unit, drift, and artefact semantics.

## 2. The constraint that actually shapes it

The Beam is **BLE** — it cannot reach the internet on its own. So ingestion is
relayed: phone app or hub. Two consequences that decide the whole design:

**Uploads are bursty and human-scheduled.** The app syncs when the phone is open
and online. A phone offline for three days delivers three days at once.

**The buffer caps device-side backlog; it does not bound end-to-end arrival.**
~320 measurements per device, so a device that cannot reach a phone keeps at most
**~80 hours** of readings before it starts dropping the oldest — *if* the deployed
generation buffers 320 readings at four per hour. The published figures are
ambiguous: Beam 1.0 is listed at 1/hour and Beam 2.0 at 4/hour, and the 320-reading
store is described as ~13 days, which matches 1/hour. Confirm generation-specific
storage with firmware (D2/D6).

The delay from a reading to its arrival is set by when the phone next syncs, and
that is a human schedule rather than a device limit: a phone offline for a week
delivers a week at once — minus whatever the buffer already discarded. Retention
therefore bounds *loss*, not latency, and the watermark below is conditional on
both. So:

Partition by event time, not arrival time. An 80-hour watermark is normal. Late
writes must replay and re-audit the affected partition.

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

The variants use this flow with different infrastructure.

### Failure handling

- Retry transient transport and write failures idempotently on `(device_id, ts)`;
  duplicate-key checks make replay safe.
- Quarantine payloads that fail authentication, schema parsing, or range checks
  with the reason and raw payload retained for replay.
- If validation or publication fails for a device-day, leave that partition
  unpublished and replay its immutable raw input after recovery.

## 4. Variant A — self-hosted / OSS

| Concern | Choice |
|:---|:---|
| Ingest buffer | **Redpanda** |
| Stream checks | **a Python consumer** for per-message checks; dbt (§12) for per-window SQL |
| Lake | **MinIO + Parquet** |
| Transform | **DuckDB + dbt** (`dbt-duckdb`); 0.6 GB/day in a columnar file |
| Orchestration | **Airflow** |
| Serving | **Postgres (+ TimescaleDB)**; the feature table is 12k rows here, ~150M at fleet scale |
| Dashboards / analytics | **Grafana** / **Metabase** |
| Deploy / operations | **Docker Compose → k8s when it hurts**; a small on-box watchdog |
| Model lifecycle | **MLflow** |

Redpanda retains the Kafka API without ZooKeeper/JVM; the Python consumer avoids
Flink, Spark Streaming, and Kafka operations. MinIO's S3 API supports AWS
portability. Airflow over Dagster; the watchdog handles restarts, log tailing,
disk pressure, certificate expiry, and pages someone at 3am; move to k8s at ~10×.

Rough infrastructure: **one to four nodes**, ~€150–400/month. Plus an engineer.

## 5. Variant B — AWS managed

| Concern | Choice | Why |
|:---|:---|:---|
| Ingest | **IoT Core** → rules → S3 | Device registry, per-device auth and revocation out of the box. Certificates are the hard part of a fleet; don't build them |
| Messaging cost | **Basic Ingest** (reserved topic `$aws/rules/…`) | **Messaging is free on this path** — you pay rules + actions only. This is the single biggest lever in the design |
| Buffer (optional) | **Kinesis Data Streams** | Only if you need sub-minute alerting. See below |
| Lake | **S3**, Parquet, partitioned by event date | The assessment's image paths use the `s3://` scheme, which *suggests* S3 — but they are synthetic fixtures and the path is a pure function of other columns. Treat as a hint; confirm the real stack |
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

S3 rule actions write individual MQTT messages, so the object count is a design
decision:

```
one object per message      288,000,000 ÷ 1,000 × $0.005 = $1,440/mo
one object per device/hour   72,000,000 ÷ 1,000 × $0.005 = $  360/mo
one object per device/day     3,000,000 ÷ 1,000 × $0.005 = $   15/mo   ← chosen
```

**Chosen: one compacted Parquet object per device per day.** An hourly object at
this cadence holds four readings, so it pays 24× the request cost to put four rows
in a file; it buys nothing the serving tier does not already provide. The total,
with that policy:

```
IoT Core (connectivity + rules)                                $173–432/mo
S3 requests, 3 M PUTs at one object per device-day             $     15/mo
S3 storage (compressed published + raw, both retained)         $   0.50/mo
                                                        total ≈ $188–447/mo
```

**What that policy costs in latency, stated plainly:** the lake is up to **one
day** behind the last reading of a completed UTC day, plus the upload delay of §2.
So the lake does not serve anything that must react within hours — and that is why
the gates do not run there. The per-device-window checks (layer 4 of §7) run
**hourly in the ingestion consumer, over the buffer**, and the serving table is
refreshed by the same hourly pass. The daily lake object is validated as it is
written, and a late reading rewrites the affected device-day object.

A static object key overwrites data. **Fresh lake files** require hourly objects:
**$360/mo** of requests, total **≈$533–792/mo**, above the $200–500 envelope.
**Batching is required:** Parquet avoids a listing-and-scan problem from 288 M
tiny JSON objects.

Sources: [AWS IoT S3 rule action](https://docs.aws.amazon.com/iot/latest/developerguide/s3-rule-action.html) ·
[S3 pricing](https://aws.amazon.com/s3/pricing/).

The connection model drives cost: 100k devices connected 24/7 cost $346/month;
connecting only to send costs $86. A phone-relayed BLE sensor may not hold an IoT
Core connection.

### Brokerless option

For dashboards needing **minutes, not seconds**, use:

```
IoT Core rule → ingestion buffer (batches + compacts) → S3 Parquet → validation
```

The buffer turns 288 M objects into 3 M ($1,440/mo versus $15/mo). At 0.6 GB/day,
DuckDB needs a few seconds. Add Kinesis for live alerting or a device command.

## 6. The decision rule

The choice is total cost of ownership:

| | Variant A | Variant B |
|:---|:---|:---|
| Infrastructure | €150–400/mo | ~$190–450/mo (§5 policy) |
| **Operational load** | Kafka + Airflow + MinIO + Grafana to patch, upgrade and be paged for — **~0.3–0.5 FTE** | ~0.05 FTE |
| Lock-in | none | IoT Core rules, Kinesis, QuickSight are sticky |
| Marginal cost at 10× | unchanged | scales linearly |

The FTE estimate is a ratio, not a currency figure: a third of someone's time is
**10–20× the whole infrastructure difference**. I would start with managed
ingestion, the §5 batching policy, and portable checks.

**Flip to Variant A when:**

1. **10× the fleet.** 1M devices → ~$860–3,450/month on IoT Core alone, and
   per-message pricing starts to bite. Self-hosted infra grows sublinearly
2. **A residency or on-prem requirement.** Professional/B2B sites may contract for
   it, and that is a contract, not an engineering preference
3. **The team already runs k8s competently.** Then Variant A's ops cost is much
   lower than 0.3 FTE, and the calculus changes
4. **Egress or vendor repricing.** AWS changed IoT Core pricing once already

Keep validation logic portable: Python and SQL over Parquet run on MinIO + DuckDB
and S3 + Athena. This makes a later substrate change a deployment change rather
than a rewrite.

## 7. Where bad data gets caught

Six layers, cheapest first.

| # | Layer | Catches | Failure mode if missing |
|:---|:---|:---|:---|
| 1 | **Firmware** | physically impossible readings, before transmission | you pay to transport garbage |
| 2 | **Ingest** | malformed payloads, unknown device, **unknown substrate**, impossible ranges | a schema change becomes silent NULLs |
| 3 | **Stream / per-reading** | out-of-range, impossible, duplicate keys | at-least-once delivery becomes duplicates |
| 4 | **Batch / per-device window** | frozen channel, **slot-grid gaps**, drift, clock offset, unit outliers, co-located disagreement | **the expensive class** — invisible per row |
| 5 | **Publish gate** | nothing reaches a consumer unless every check passed | a consumer reads half-verified data |
| 6 | **Post-publish monitoring** | what the gates missed — freshness, volume, distribution | you find out from a model, weeks later |

Layer 4 contains the 13 per-device-window findings that per-row checks miss:

| Finding | Blind to it |
|:---|:---|
| F3 frozen channel | every value is *in range* and the value is *constant* |
| F7 the 48.5 h hole | the file has zero nulls — only the expected-slot grid shows it |
| F2 clock offset | a correctly-formatted timestamp that is simply two hours wrong |
| F5 sustained out-of-spec | each reading is individually possible |
| F12 shared ambient | the reading is correct; the *comparison* was the error |

Rules:

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

Four maintenance mechanisms:

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

`task2_detection_coverage.csv` records the check that caught each finding and
the check structurally blind to it:

**3. Detection ≠ remediation, reconciled both ways.**

```
for device in detect_unit_outliers(raw):  assert device in UNIT_FIXES
for device in UNIT_FIXES:                 assert device in detect_unit_outliers(raw)
```

Each known failure class has a frozen bad-window fixture that must remain caught
after a change. `assert_grain` and the audit gate provide this pattern in the
current code.

## 10. Model and calibration lifecycle

Calibration is already a finding:

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

dbt is the transform layer in both variants; the adapter changes. The operation
mapping is:

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
equivalents include `assert_grain()` as `unique: [device_id, ts]`, `SPEC` /
`IMPOSSIBLE` range tests, audit test groups, `relationships: device_id → registry`,
the registry table as a seed, `is_incremental()` + `unique_key` → `MERGE`, and
lineage and docs output.

**Where it is not the answer.** dbt runs on a warehouse or a lake, not inside a
broker consumer. Per-message checks such as reject-at-ingest and live alerting
stay in Python; dbt handles per-window work.

**The cost, stated honestly.** dbt means a second execution model, a
`profiles.yml`, and a project layout beside 1,100 lines of working Python. At one
developer that is a real cost, and it is not obviously worth paying today. It is
worth paying the moment a **second person** has to read, review or extend the
transforms — which at 100k devices is a matter of when, not if.

---

## Recommendation

Build Variant B while keeping Variant A portable: IoT Core + S3 + DuckDB, no
broker until required, and Step Functions orchestration. Keep validation as SQL
over Parquet in dbt when a second person needs to read it; use plain scripts until
then. Keep the domain registry in one place with no I/O.

The §5 batching policy costs **≈$190–450/month** with near-zero operational load.
The `s3://` image paths suggest FYTA may already use AWS, but they are synthetic
fixtures. Revisit the choice at 1M devices or the first residency requirement.
