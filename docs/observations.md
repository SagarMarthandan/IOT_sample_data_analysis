# Observations

Everything noticed while working on this dataset, written up for the **report**.

Parts 1–5 are the running record: findings, method lessons, what went wrong,
smaller observations, and what is still open. Parts 6–7 are the external reviews,
reproduced verbatim, because every defect they name is a claim that has to stay
checkable against the code.

Line numbers and file paths inside Parts 6–7 are as they were when reviewed. The
code, the notebook and this documentation have changed since, so read those
citations as provenance rather than as navigation.

**Where each thing lives:**

| File | Holds |
|:---|:---|
| `assessment.md` | the brief, the thread, and what the data actually **is** |
| `PIPELINE_DESIGN.md` | the Task 7 design: one batching policy, latency, cost arithmetic |
| `decision_register.md` | choices waiting on a **conversation** (D1–D18) |
| `HANDOFF.md` | current state, so a new session can continue |
| **this file** | findings · method · mistakes · open questions · the reviews |

| Part | Holds |
|:---|:---|
| 1–5 | findings · method lessons · mistakes · smaller observations · still open |
| 6 | external reviews 1 and 2, verbatim |
| 7 | third review and its reassessment, verbatim |

Machine-readable versions: `submission/out/task2_findings.csv`,
`task2_detection_coverage.csv`, `qc_rejections.csv`, `cleaned_sensor.csv`.

---

# Part 1 — The findings

13 findings. Full detail is in `task2_findings.csv`.

| # | Finding | Device | Severity | Class |
|:---|:---|:---|:---|:---|
| **F1** | `soil_temp_c` is Fahrenheit | SENS-07 | high | data problem — unit error |
| **F2** | clock is 2h out, and dates use DD/MM | SENS-07 | high | data problem — clock/timezone |
| **F3** | moisture frozen at exactly 25.01 for 14 days | SENS-06 | high | sensor fault — dead channel |
| **F4** | EC climbs steadily, with no logged cause | SENS-03 | high | sensor fault — drift |
| **F5** | moisture goes above the sensor's 65% limit | SENS-04 | high | **unknown** — fault or a different setup |
| **F6** | single-sample values that cannot be explained | SENS-08 | low | 22 artefacts; 8 unresolved |
| **F7** | 193 readings missing (48.5 hours) | SENS-05 | medium | data problem — availability |
| **F8** | 15 duplicate rows | SENS-08 | low | data problem — sent twice |
| **F9** | `user_plant_id` repeats, so joins multiply rows | all | medium | schema problem |
| **F10** | two sensors on one plant, not related | UP-1001/1003 | high | **unknown** — config or mapping bug |
| **F11** | watering logs and sensor events are unrelated | all plants | high | label problem |
| **F12** | environment is near-identical across devices | all | medium | artefact — shared environment |
| **F13** | substrate label has no start/end date | UP-1006 | medium | semantic — a setting with no history |

**Split by class:** data problem 4 · sensor fault 2 · unknown 2 · sensor
artefact 1 · schema 1 · label 1 · artefact 1 · semantic 1.

## Why two are marked "unknown"

**F5** could be a calibration error, or simply a different pot. **F10** could be
two sensors genuinely in one pot, or a mistake in the mapping.

These files cannot tell the difference. So each one names the measurement that
would settle it, or the person who could.

## F10, in full — two sensors on one plant

> *"why would one plant have two sensors? isn't it counterproductive?"*

### The legitimate case

Two real reasons it exists in practice:

**Depth profile.** The probe is a *point* measurement placed in the lower third
of the pot. A 40 cm pot has different moisture at 5 cm than at 30 cm. Two probes
at two depths tell you *where* the water is — reaching the deep roots, or just
wetting the surface?

**Redundancy.** With two sensors, agreement gives confidence, and *disagreement
is itself a signal*. That is the technique that exposed SENS-06's flatline.

So the idea is not silly.

### Where it becomes counterproductive

| Cost | Why it matters |
|:---|:---|
| **Grain ambiguity** | What is "the plant's moisture"? You must pick an aggregation, and the reflex answer — average them — produces a number describing *neither* pot |
| **Averaging hides faults** | A stuck sensor at 25 averaged with a healthy one at 45 gives a plausible 35. The pipeline hides a hardware failure |
| **User-facing contradiction** | If they disagree, which number does the app show? |

### What this dataset shows

| | Two probes in one pot (*expected*) | UP-1001 / UP-1003 (*actual*) |
|:---|:---|:---|
| Correlation | high positive — shared water | **−0.076 / +0.140** |
| Response to watering | both rise, one lags | unrelated |

Different depth shifts the **level** and the **timing**. It cannot make two wicks
in the same reservoir move in opposite directions.

### Position

**For one pot, two sensors is counterproductive unless you build the fusion
rule.** It buys fault detection and a depth profile; it costs a defined grain.

**Carry forward: never average co-located sensors.** Keep both, and treat their
*disagreement* as the signal.

### Open

- **Does the FYTA app let a user pair two sensors to one plant, or does pairing
  replace?** → **D11**
- If it *replaces*, this is an append-without-versioning bug, and the truth is
  6 sensors / 6 plants
- If it *allows* it, the pipeline owes it an explicit rule

## F11, in full — the two sources were probably never connected

The logs are entered by users. The brief calls them *"User event log
identifier"*, and the text reads like a person: *"Watered a bit, leaves
drooping"*.

Compare the two by **time of day**:

```
sensor watering rises            user watering logs
SENS-01  12:00 00:00 12:00 00:00      07:15  08:00  09:00  10:30
SENS-02  00:00 00:00 00:00 00:00      07:30  08:30  10:45  11:15
SENS-03  00:00 00:00 00:00 00:00      11:30  11:45  13:30  14:00
SENS-04  00:00 00:00 00:00 00:00      14:30  16:00  17:30  17:45
SENS-05  00:00 00:00 00:00 00:00      18:00  18:15  18:45  19:00
                                      19:15  19:30  19:45  20:30
```

**31 of 48 sensor rises land exactly on `00:00` or `12:00`.** SENS-07's six are
all at `02:00` — which is also `00:00` once its 2-hour clock error is removed.

Excluding SENS-08 (the noisy device), **every rise lands on the hour: 35 out of
35.**

**Nobody waters a plant at midnight. Six times in three weeks, on five different
devices.**

The user logs, by contrast, are all at human times, spread through daylight
hours, and **never once at midnight or noon.**

**The human side looks human. The machine side looks mechanical.** So the odd one
out is the *sensor*, not the user.

They do not match because they were probably **generated independently**. The
dataset is synthetic; the generator appears to have produced a realistic-looking
log and a realistic-looking sensor series separately, so neither can validate
the other.

**Consequence:** you cannot use the logs to check the sensor or the sensor to
check the logs. **Task 6's triangulation cannot work** on this data.

What survives: the log **text** is real structure (14 phrases, each mapping to
one category), and `"Watered ~200ml"` carries a volume. The labels are usable as
*what the user said*, not as *when it happened*.

---

## Task 4 — the four sources, and which can be checked

The brief asks whether the labels agree across **species, logs, image
predictions and sensor data**. Only the sensors measure anything; the other
three are reports *about* the plant.

| Source | Answer |
|:---|:---|
| **Plant species** | One substrate per species ✅ — but static, so it can never be checked against a date (F13) |
| **Contextual logs** | One `log_type` per phrase ✅ (14 phrases) — but unrelated to the sensor (F11) |
| **Image predictions** | Internally consistent ✅ — agrees with the sensors on water at r = 0.75. **Whether that is corroboration or an artefact of the generator is unestablished** (see below). Independent heads never fire |
| **Sensor data** | The reference. Its own defects are Tasks 1–3 |


### The two controls on the comparison

**Dryness is a within-device rank**, because VWC is only comparable *within* a
substrate — an absolute threshold is the wrong question across substrates.

**Same code, raw and cleaned**, clock held constant, so the sensors are the only
input that differs. If the answer moves, it rests on my cleaning rather than on
the data.

### The head ranges, and which heads can even be tested

Across all 28 photos:

| Head | max | Measures | Independent of the probe? |
|:---|--:|:---|:---|
| `Abiotic` | 0.680 | anything non-living (parent) | ✗ |
| `Water-related issue` | 0.625 | water (parent) | ✗ |
| `Water deficiency` | 0.635 | water | ✗ |
| `Water excess / uneven` | 0.378 | water | ✗ |
| `Nutrient deficiency` | 0.073 | nutrients | ~ |
| `Fungi` | **0.054** | fungus | **✓** |
| `Animalia` | **0.057** | pests | **✓** |

**4 of 7 heads carry any signal.** The three that never fire are the three that
could have said something the probe cannot see — a head that never asserts
anything can neither agree nor disagree.

```
photos crossing a 0.5 threshold:
  Abiotic 6   Water deficiency 4   Water-related 3
  Water excess 0   Nutrient deficiency 0   Fungi 0   Animalia 0
```

`Fungi` and `Animalia` vary (0.008–0.054) so they are not dead channels like
SENS-06 — they report *low*, consistently. The problem is that there is **no
positive example anywhere in the sample**, so there is nothing to validate
against. Two readings fit, and the data supports neither: the plants are healthy,
or the heads cannot fire. What would separate them is one photo with a visible
infection, and that is a horticulture question, not a vendor one.

### The raw-vs-cleaned control, in numbers

Same code, two sensor frames, clock held constant:

- every metric is **identical** on raw and cleaned outside the seven `r()` rows
- those seven move by **at most 0.056**

So the Task 4 conclusions do not rest on Task 3's choices.

### Why the image model's agreement is not a pass

`Water deficiency` correlates with dryness at **+0.75** and `Water excess` at
**−0.75** — mirror images, with both parent classes between them. That is a
consistent taxonomy, and also a **single-factor model**.

**An earlier draft called this "circular". That was wrong.** Two instruments
measuring one latent variable *is* corroboration, not a tautology.

**But the opposite reading is unsupported too.** This dataset is synthetic. If one
generator emitted both the moisture series and the image probabilities from the
same latent state, r = 0.75 says nothing about the world. We cannot tell "two
modalities agree" apart from "one generator emitted both", so neither claim is
earned. What would settle it is **model lineage from the vendor**.

`Fungi` and `Animalia` never exceed 0.06 on any photo, so independence is not
untested here — it is **untestable**. No photo has the model claiming anything
the sensors hold no opinion about. This is §12 of `AGENTS.md` met in the field:
*check whether a model's output is independent evidence at all.*

### The raw-vs-cleaned control

Same code, two sensor frames, clock held constant so only the values differ.
Every metric is identical except the seven `r()` rows, which move by at most
0.056. So the answer does not rest on Task 3's choices — and the zero deltas are
the check that the model-side analysis never touched sensor values.

### Verdict

**A feature, never a label.** `is_healthy` is withheld — it is exactly
`probability > 0.5`. Gate at ingestion: pin `model_version`, fail on an unknown
head name, treat a new class as a schema event.

### The log consistency is not a compliment

Fourteen phrases, all single-purpose, and **not one of the 49 rows is ambiguous** —
no *"watered and fed"*, no *"repotted, watered it in"*. A user typing freely
eventually writes something that belongs to two categories. None of them do.

Either the text is **canned** (a picker in the app), in which case 1:1 is a schema
constraint rather than a quality signal; or it is **free text**, in which case
perfect consistency across 49 rows is a **generation signature**. Either way the
tick is not earned.

It sits alongside F11: the logs do not line up with the sensors, and the sensor's
own rises land exactly on the hour. **Both sources look independently generated**,
so neither can validate the other — and a tidy vocabulary does not change that.

### What would settle each open question

| Question | What settles it | Owner |
|:---|:---|:---|
| Is the image model independent, or does one generator emit both? | Model lineage — did the model consume VWC? | Vendor |
| Are the logs real events, or generated? | Does the app offer canned phrases? | Product |
| Is the sample capable of testing independence at all? | A photo with a real infection, or a plant shot while well watered | Horticulture |

---

## Task 5 — one table, and the two decisions inside it

### "Why does UP-1004 have 1823 rows, not 2016?"

> *"in task 5 UP-1004 Basil (indoor) 1823 1 1.000 48.5 — it shows 1823 rows instead of 2016 .. if vwc had no values, then the single feature table must have 2016 rows for UP 1004 with this null values right ?"*

**No — and there are no null moisture values to carry.**

```
UP-1004   rows 1823   vwc_1 nulls 0   coverage of DELIVERED readings 1.000
```

Every one of its 1823 rows holds a moisture value. And SENS-05 never sent 2016
readings — it sent **1823**. The other 193 are `(device_id, timestamp)` pairs that
do not exist in the raw file: **one outage, 2026-06-12 23:45 → 2026-06-15 00:15,
48.5 hours**, which is F7.

So the real choice is not "values vs nulls". It is:

| Design | UP-1004 rows | What they assert |
|:---|--:|:---|
| **Sparse** — shipped | 1823 | only what the device reported |
| **Dense grid** | 2016 | 1823 real + **193 timestamps no instrument measured** |

**The dense version is not dishonest, and this entry originally said it was.** A
row carrying an expected timestamp, NULL measurements and `reading_received =
false` asserts *"a reading was owed here and is unknown"* — it does not claim an
instrument measured anything. Sparseness and density are both honest; they differ
in what downstream code has to handle. **This is a downstream-use decision, not an
integrity one**, and the first version of this answer collapsed the two.

The sparse table is still the right choice here — a consumer doing a moving average
would otherwise carry a fabricated value across 48 hours unless every query
remembered to test the flag, and `gap_minutes` puts that burden in one column
instead of every consumer. That is a reason, not a rule.

The reconciliation is exact, which is the check that the sparse grain is honest:

```
rows 11,903   vs   expected slots 12,096   →  193 missing = SENS-05's outage, exactly
```

**What the question actually caught — two defects, not one.**

*First, the row does not explain its own count.* `rows 1823` beside five `2016`s
is indistinguishable from a filter bug. `longest_gap_h 48.5` flags that something
happened but not how much. A `missing` column now carries the 193, so the row
answers the question without prose.

*Second — and this is the one that was actually wrong — `vwc_coverage` was
computed on `vwc_1` alone, under a name claiming the plant.* Probe 1 for UP-1003
is SENS-04; probe 2 is SENS-06, the frozen channel (F3). So the column read:

```
UP-1003   vwc_coverage 0.976      <- probe 1 only
UP-1003   every probe   0.324      <- what the header implies
```

**0.976 is not conservative, it is wrong.** A reader would conclude UP-1003 is
almost complete when two thirds of its moisture is unusable. It is now
`probes_filled`, computed as the share of present rows where **every** probe the
plant owns carries a value, with absent probes passing automatically so a
one-probe plant is not judged on its empty `vwc_2` column.

That defect was **pre-existing and independent of the question's premise.** The
premise — that the raw data holds 2016 readings for SENS-05 — was wrong; the raw
data holds 1823, and the 193 absent rows are F7. But `vwc_coverage` described
itself as the plant's coverage while computing probe 1's, and that survived the
first audit, the second audit and the ponytail review, because every check asked
*"does the number compute?"* and none asked *"does the header describe what is
computed?"*

**A wrong premise can still land on a real defect.** The inference was faulty; the
place it pointed at was not. Worth separating, because dismissing the question
along with the premise would have shipped a column reading 0.976 where the truth
is 0.324.

**The general lesson:** when a table's row count varies by key, the expected count
belongs next to it. Not because the current number is wrong, but because a reader
cannot tell a *known* gap from an *unknown* one without it.


Grain is `(user_plant_id, ts_aligned)`, declared **and asserted** — 11,903 rows,
0 duplicate keys.

| Plant | Rows | Probes | Longest gap |
|:---|:---|:---|:---|
| UP-1001 Monstera | 2,016 | 2 | 0.2 h |
| UP-1002 Ficus | 2,016 | 1 | 0.2 h |
| UP-1003 Zamioculcas | 2,016 | 2 | 0.2 h |
| UP-1004 Basil | 1,823 | 1 | **48.5 h** ← F7 |
| UP-1005 Orchid | 2,016 | 1 | 0.2 h |
| UP-1006 Pothos | 2,016 | 1 | 0.2 h |

### The two decisions

**Never average the probes.** UP-1003's two devices disagree by **19.9% VWC** on
average; UP-1001's by **8.8%**. Both pots nominally hold one plant. Averaging
would produce one number describing neither — and would destroy the
disagreement, which is what a second probe is *for*. Both readings are kept side
by side, with the gap exposed as `vwc_delta`.

**Rank within the device, over a trailing window.** VWC is only comparable
inside a substrate, so `vwc_pct_*` is the reading's rank inside that probe's own
recent range — which is what makes it comparable *across* plants. Trailing,
because a whole-window rank judges a day-1 reading against day-21 data: leakage
the moment this table trains a model.

### What it does not hide

- **F3** SENS-06's frozen channel was nulled first, so `vwc_delta` goes null for
  those 1,344 slots rather than silently reading as agreement
- **F7** the 48.5-hour outage is an absent row plus a `gap_minutes` flag, not
  fabricated data
- **F13** `substrate` is today's value with no history, so a repot mid-window is
  invisible

Fusing the probes is a **modelling** decision, not a data one. The table hands
over both readings and their disagreement; choosing the rule is D11's
conversation.

---

## Task 6 — triangulation, and why it fails

The brief's example: a fertilising log should raise `ec_us_cm` **and** the image
model should return `Nutrient deficiency`. Three legs, five events.

| Leg | Should show | Does it? |
|:---|:---|:---|
| **The log** | fertiliser was added | ✅ 5 events |
| **The sensor** | EC rises | ❌ `dEC` is **0.01–0.11σ** of that device's own step noise; 2 of 5 are negative |
| **The model** | `Nutrient deficiency` responds | ❌ never exceeds 0.073 on any photo (§Task 4) |

**No — and not because the effect is weak.** Two of the three legs carry no
fertiliser signal at all. A head that never fires can neither agree nor disagree.

### The window is the trap

Widen the window and **UP-1002 appears to confirm**. Its EC climbs **1,289
µS/cm** across the record, so *"fertilised, then EC rose"* looks true.

It is not true. The climb **starts ten days after the feed** and is a straight
line — SENS-03's gain drift (F4), not chemistry. A separate defect sitting on the
same plant is what makes the false positive convincing.

| UP-1002, one fertilising log | 24 h window | whole record |
|:---|:---|:---|
| `dEC` | +4 µS/cm | **+1,289 µS/cm** |
| against the device's step noise | **0.07σ** | — |
| reading | flat | *looks* like a response |

Same data, two answers. A wide window does not weaken the test — it **manufactures
the positive**, and it does so on the one plant where a drift makes the story
plausible.

### What would make it work

All three, because two were never available here:

1. **A log timestamped when it happened** — the logs do not line up with the
   sensor at all (F11); the sensor's own rises land on the hour, the logs at
   human times
2. **An EC channel without drift** — SENS-03's ramp is larger than any feed
   effect and starts at an arbitrary date
3. **A model head that fires** — `Nutrient deficiency` never exceeds 0.073

---

## Task 7 — pipeline design

Full design in `docs/PIPELINE_DESIGN.md`; the notebook carries the summary and
both diagrams (§12).

Three things worth carrying into the report:

**Sizing first, because it reframes everything.** 100k devices × 96/day =
**9.6M readings/day = 111 msg/s = 0.60 GB/day**. That is not big data, and a
design that leads with Spark is solving a problem the fleet does not have. The
hard parts are 100,000 individually-wrong things, late arrival, and semantics.

**The BLE constraint is the design.** The Beam cannot reach the internet, so
ingestion is relayed and the 320-measurement buffer puts lateness at **~80
hours**. Hence: partition by **event time**, and re-audit the *affected*
partition on a late write.

**The decision is headcount, not volume.** Managed infra costs ~$200–500/month
against ~0.3–0.5 FTE to run the OSS stack — and 0.3 FTE is ~€2,100/month. Not
close. The two variants are not rivals once the checks are kept portable.

---

## Tasks 8 & 9 — the optional stretches

Both deliberately small. Nothing in `fyta/signals.py` is load-bearing.

### 8 — `drydown_pct_per_day`

**%VWC lost per day**, from the trailing median of consecutive changes.

**The rate is comparable where the level is not.** An absolute VWC threshold is
wrong across substrates — that is what the conversion curve exists for, and what
is unresolved here (F13). But *"this pot loses 2 %/day"* means the same thing in
coir as in bark, so the rate carries across the fleet without a calibration
nobody has confirmed.

**Median, not mean** — a watering event is a large jump the other way, and a mean
would average drying together with watering.

**A per-step rate amplifies per-reading noise** — 0.4 %VWC of jitter over fifteen
minutes reads as 38 %/day — so the median is taken over a full day.

**And that is what makes SENS-04 meaningful.** At 38 %/day against 3–6 for the
rest of the fleet it is not a drying rate: a pot cannot lose that much water and
still read 15–100. It is the sawtooth from **F5**. **The signal rediscovers the
same device the range checks flagged, from an unrelated angle** — which is the
point of having a signal at all, and a decent argument that F5 is a device fault
rather than an unusual pot.

### 9 — log text is a lookup, not a classifier

Fourteen phrases over 49 rows, and the phrase-to-`log_type` mapping is **already
one-to-one**. A model would be a more expensive way to write a dict, and would
need labels nobody has.

The text adds a coarse intensity and **exactly one volume**: only 1 of the 14
phrases contains a number. That is all it encodes.

**The limit it shares with everything else here:** F11 showed the logs do not
align with the sensors in time. Structured text is still not a timestamped event,
and this task does not change that.

---

# Part 2 — Method lessons, and the questions that produced them

These generalise beyond this dataset.

## 2.1 Reading a date is not editing data

> *"in the observation phase, are you fixing the data or just reporting? because task 1 is data observation"*

**Reporting. And it is proven, not asserted.** Every column of all four tables
was compared before and after loading:

```
every column holds identical values    same 15,950 rows
columns added: ['ts']     removed: none
empty cells before: 0     after: 0     rows dropped or added: 0
second load identical to the first: True
```

**Parsing is not transformation.** `"40.93"` is five characters, not a number.
Interpreting it as one is what makes the file readable at all.

| Task 1 **may** | Task 1 **must not** |
|:---|:---|
| Interpret text as typed values | Change a value |
| Add derived columns | Drop or add rows |
| Reorder rows | Empty, clip, fill in, or dedupe |
| **Stop** on malformed input | Decide something is *wrong* |

That last pair is the real boundary. Task 1 stops on an unknown date format —
**fixing and refusing are opposites.**

**Where it's genuinely blurry:** the day-first choice is not a "fix", because the
other reading is *impossible*. And the safety net is the tell: the code **stops**
rather than guesses if the proof isn't there.

One acknowledged exception: `key_uniqueness` lives in Task 1 and reports
`unique: False`. It is a judgement call, not a clean line.

## 2.2 Correlation cannot see a unit error

> *"check on only the soil temp ... then we might know that the sensor is throwing in Fahrenheit and its converted values i.e. in celsius is on par with other sensors"*

**And this is the most useful thing the work produced.**

```
SENS-07 temperature, correlation with the fleet:  0.9843   <- the broken one
SENS-01                                           0.9843
SENS-04                                           0.9843
```

**The device reading Fahrenheit has the highest correlation in the fleet.**
Correlation only measures whether two things move together. Multiplying and
shifting one series — which is exactly what a unit change is — does not change
correlation at all.

It fails the other way too:

```
SENS-07 before the clock fix:  r = 0.8517   <- correlation DOES catch the clock error
SENS-07 after the clock fix:   r = 0.9843   <- but MISSES the unit error
```

**Correlation catches timing problems. It cannot catch scale problems.**

| Test | Catches | Cannot catch |
|:---|:---|:---|
| correlation | timing errors, dead devices | unit or scale errors |
| mean and spread | level shifts, scaling | timing |
| fitting a line (`a` and `b`) | both, and tells them apart | needs a shared signal |

## 2.3 Fitting a line separates a shift from a scale change

Multiplying a series changes how much it *moves*, not just its level. So a unit
error is visible from the noise alone:

```
SENS-07 moves between readings by:  0.720
the fleet moves by:                 0.390

a pure SHIFT (+41 C) -> movement UNCHANGED -> predicts 0.720   WRONG
a SCALE of x5/9      -> movement x5/9      -> predicts 0.400   RIGHT
```

Fitting `device = a * fleet + b` gives `a = 1.792, b = 32.17`. The Fahrenheit
conversion is `a = 1.8, b = 32`. Match to within 0.4%.

Then converting settles it completely:

```
                  mean      sd     min      max
SENS-07 raw (F)  69.79    4.53   61.86    78.01
SENS-07 conv (C) 21.00    2.52   16.59    25.56
fleet (7 devs)   20.99    2.49   16.96    24.95

difference from the fleet per timestamp:  mean +0.004 C, sd 0.444
```

**One limit:** this only works on channels that move together across devices.
Three of the five do (temperature, humidity, light). **A unit error in moisture
or EC would be invisible** and would need a reference measurement instead.

## 2.4 Two problems can hide each other, and order matters

> *"it might be temp drift .. did you check its lead and lag?"*

**Both tested. Both eliminated.**

**Drift:**
```
movement over time: +0.0004 C/day  ->  +0.009 C over 21 days
day-to-day noise:    0.444 C
```
The trend is **50× smaller than the noise**. Flat.

**Lead/lag:**
```
shift +1h -> agreement 0.9505
shift +2h -> agreement 0.9843   <- best
shift +3h -> agreement 0.9516
```

**And here is why that is decisive.** The *light* channel's best shift is also
+2h. A thermal lag is a physical property of the substrate — orchid bark has
different thermal mass than potting soil — so a real lag would **add** to the
clock error, and the temperature's best shift would sit somewhere other than
+2h. It does not. One correction moving both channels identically is a **clock**,
not physics.

Five healthy devices all peak at a shift of zero.

**The masking, which is the actual lesson:**

```
difference from the fleet, as recorded:   sd 1.363   <- "too noisy to be a unit error"
difference from the fleet, after -2h:     sd 0.444   (a healthy device: 0.380)
```

1.363 is large enough to make you doubt a finding that is actually correct. The
clock error creates about 1.4 °C of false disagreement, because the daily
temperature swing is about 4 °C and a 2-hour shift moves it.

**So fix structural problems before judging values.** If you look for a unit
error, a drift, or a label mismatch while the timeline is still wrong, you
contaminate your own evidence and may talk yourself out of the right answer.

**The incidental lesson:** the first control test **crashed** on `cannot reindex
on an axis with duplicate labels` — SENS-08's 15 duplicate timestamps. **The bug
under investigation broke the investigation.**

## 2.5 The most interesting problem is not necessarily the cause

> *"the biggest takeaway is the distinction of two sensors for one plant .. its causing these problems"*

**Half right, and the half matters.**

It causes exactly two findings:

| Finding | From the two-sensor mapping? |
|:---|:---|
| **F9** joins multiply rows | yes, directly |
| **F10** sensors do not correlate | yes, that *is* the finding |
| Task 5, the per-plant table | yes, blocked by it |

And the five most serious findings are on plants with **one** sensor:

| Finding | Device | Plant | Sensors there |
|:---|:---|:---|:---|
| F1 Fahrenheit | SENS-07 | UP-1005 | 1 |
| F2 clock error | SENS-07 | UP-1005 | 1 |
| F4 EC drift | SENS-03 | UP-1002 | 1 |
| F7 missing readings | SENS-05 | UP-1004 | 1 |
| F8 duplicate rows | SENS-08 | UP-1006 | 1 |

**That rules the mapping out as their cause.**

**Why it matters for the report.** If every problem traced to one root cause, the
fix would be one thing. It is not. A parser fixes F1. Only hardware fixes F3.
Only a conversation fixes F10. That is what the brief meant by *"they're of
different kinds"*.

## 2.6 Every problem here defeats at least one obvious check

> *"when traps are set .. we'll have to check in many ways"*

That is what makes it a trap rather than just a defect. The full table is in
`task2_detection_coverage.csv`. Three examples:

- **F2** — SENS-07's spacing is *perfect*. Every reading exactly 15 minutes
  apart. **A schedule check says the device is fine.** Only comparing it with
  its peers shows the shift.
- **F7** — there are **no empty cells anywhere**, yet 193 readings are missing.
  The missing readings have no rows at all, so counting empty cells finds
  nothing.
- **F1** — correlation cannot see units (see 2.2).

**So the checks have to ask different questions, not repeat the same one.** The
questions used here: value range · expected number of readings · key uniqueness ·
join size · run length · agreement between channels · agreement between devices
· fitting a line · matching logs against readings.

Repeating a check you already ran adds nothing.

## 2.7 Isolated vs sustained decides what to do

The same check, split two ways, changes the answer for two findings:

```
SENS-04 moisture    431 out of range  ->  11 alone,   420 in a row   <- sustained
SENS-03 EC          354 out of range  ->  17 alone,   337 in a row   <- sustained
SENS-08 moisture     12 out of range  ->  12 alone,     0 in a row   <- glitches
```

A single impossible reading is a glitch. You can safely empty it.

A long run of them is a real change. Emptying it would delete history.

## 2.8 "Outside the range" and "definitely wrong" are different

| Condition | What to do | Why |
|:---|:---|:---|
| Physically impossible (moisture below 0, humidity above 100) | **empty it** | it cannot be true |
| Outside the specified range but possible (moisture 65–107%) | **flag it, keep it** | the device is not *specified* to be accurate there |

Emptying everything outside the range would have deleted **21% of SENS-04's
readings** — and lost the shape that makes its drying cycle readable.

## 2.9 A magnitude check cannot see a context problem

The eight light glitches on SENS-08 sit **inside every stated limit**. PAR is
rated to 2000, so 589 is not remotely abnormal in size. Nothing about the value
is wrong — only about *when* it happened.

Finding them took three attempts, and the two wrong ones are instructive.

**Attempt 1 — "light at night is impossible."** Wrong. A person can switch a
lamp on, and the sensor would correctly see it. This was reasoning from "it is
night" rather than from what the instrument can do.

**Attempt 2 — "brighter than the device's own daylight peak."** Better, and it
caught 7 of the 8. But it missed a `232` reading at 01:00 — below the device's
337 daylight peak, yet still a lone sample surrounded by zeros.

**Attempt 3 — duration.** This is the rule that holds:

> **A switched-on lamp persists.** It appears in several consecutive readings.
> One 15-minute sample bracketed by near-zero on both sides means the light was
> on for less than 15 minutes — eight separate times, in the middle of the night.
> That is not someone switching a light on.

```
SENS-08  01:00   0.0  0.0  429.6  0.0  0.0
```

The test uses the reading's **neighbours**, not a constant.

**And one more trap, hit on the way:** the first version of that rule used the
*raw* clock, and flagged **11 legitimate SENS-07 readings** — because SENS-07's
`22:00` is really `20:00`, which is dusk. A time-of-day check is meaningless
without the clock correction applied first.

That is §2.4 again, in a new place: **a time-based check on a misaligned timeline
produces confident nonsense.**

### The general form

| Check type | Sees | Blind to |
|:---|:---|:---|
| range against a constant | impossible magnitudes | context violations |
| against the device's own history | unusual magnitudes | timing |
| **against its neighbours** | **duration and shape** | slow drifts |

Three different questions. The eight light readings required the third.

### And a fourth thing: they should not have been deleted

My first fix **emptied** those eight readings. That was wrong, and it broke my own
rule from §2.8.

A 589 µmol/m²/s reading is **inside the sensor's rated 2000**. It is physically
possible. Someone could hold a lamp or a torch near that one pot. So it fails the
same test the out-of-spec values fail — and out-of-spec values are **flagged, not
emptied**.

```
SENS-08 spikes:  all 8   →  other seven devices read exactly 0
```

That rules out a *shared* light event, but not a *local* one. So the honest
treatment is **flag and keep**, which is what the pipeline now does.

**The principle I broke:** "physically impossible" is the bar for deleting a
value. "Statistically implausible for this device" is not. Using a weaker bar for
convenience would have deleted real observations — and here it would have been
irreversible, because `light_par_clean` was the only copy.

## 2.10 Detecting a problem and fixing it are two separate claims

> *"i know you are trying to do your best ... but you are missing the most obvious"*

The answer was not a finding — it was a **structural gap**. The check
`unit_scale()` found SENS-07 at ratio 1.82. The fix, `UNIT_FIXES`, was a
hardcoded list. Nothing checked that the two agreed.

Now the audit checks both directions:

```
every device detected is also fixed     True   detected ['SENS-07'], fixed ['SENS-07']
every device fixed was also detected    True   fixed ['SENS-07'], detected ['SENS-07']
```

If a new device arrives with the same fault, the second check fails immediately.

The same kind of drift had already happened between the notebook and the script.

**The rule: whenever two things describe the same fact, something has to check
they still agree.**

## 2.11 A claim tested on one leg is not tested

> *"for every log type -> if fertilizing -> EC_us_cm should change, water -> vwc should change, light -> light_par must change and repotting -> all values must change in some way"*

F11 says the logs do not line up with the sensors. It was claimed from **one leg**:
watering logs against a moisture rise. But every log type names a physical event,
so each has a channel that should respond. Testing all four:

| Log type | Should show | Result |
|:---|:---|:---|
| watering | moisture **rises** | 3 of 45 — **below** the ~3.5 expected by chance |
| fertilising | EC **rises** | 0 of 8 |
| light | daily peak moves, directionally | 0 of 5 — **and one contradicts** |
| repotting | some channel steps | 1 of 3 — **confounded**; every repot has a watering within a day |

The claim holds, and is *stronger* than it was: the light leg contradicts rather
than merely failing. But that only appeared once all four were run.

**The general lesson.** "None of the tests I ran found a signal" is a statement
about the search. "Every test that could have found a signal found none" is a
statement about the world. Only the second is worth reporting, and the difference
is whether you enumerated the legs before you concluded.

It also cuts the other way. The **repotting** leg is not a clean negative —
1 of 3, and every repot has a watering within a day, one of them 30 minutes
later. A repot may well disturb the probe; **the data cannot separate it from the
watering.** That is a third category between "responds" and "doesn't": *cannot
be told apart.*

## 2.12 Ask for the direction, not just the change

Two places where testing *magnitude* instead of *sign* hid a finding.

**`triangulate` used `.abs()`** on the EC delta. The brief specifies a **rise**;
a large **fall** scored as support for the hypothesis. Worse, the label was
renamed from `rises` to `moves` to match the code — which hid the error rather
than fixing it. A rename is not a fix.

**The light logs.** *"Moved closer to window"* should **raise** the daily light
peak. It **falls**, by 4.4 on average. A "did it change?" test gives roughly zero
and reads as nothing happening; a directional test gives the **wrong sign**, which
is a finding.

```
light  "Moved closer to window"          3 tested   peak RISES   −4.4   ✗
light  "Too much direct sun, moved back" 2 tested   peak FALLS   −3.3   ✓
```

**The general lesson.** A difference is ambiguous — it could be noise, drift, or a
response. A **signed** difference against a stated expectation is not. Where the
domain says which way a quantity should move, test that, not whether it moved.

And phrase the expectation per claim, not per category. The three light phrases
imply *different* directions, and one implies none at all — *"rotated toward the
light"* does not change the plant's distance from the window. Collapsing them into
one count diluted the signal and hid the sign.

---

# Part 3 — What went wrong, and what caught it

An honest record. Most of these were caught by a mechanism, not by care.

| What | Caught by | The lesson |
|:---|:---|:---|
| Said the schedule check resolves the ambiguous date | **Testing it** — reading it month-first still scores 99% on the grid | A consistent misread keeps the spacing. Impossibility is the evidence |
| The Fahrenheit evidence looked weak | Re-testing after the clock fix | See 2.4 — one problem hiding another |
| `import re` and `from __future__` were unused | **ponytail-review** | I had claimed the file was lean. It wasn't |
| A "shortening" that actually added 2 lines | Counting honestly | Removing a branch is not the same as removing lines |
| A deleted function survived in the notebook | A consistency check | The notebook still ran fine — **nothing complained** |
| The same loop written twice | ponytail-review | I split the *work* where I only needed to split the *display* |
| `detected [6]` — a position instead of a device name | **The audit gate** | Third time the gate caught a real defect |
| Plot functions never showed anything | Checking the figures were embedded | Building a chart and saving it are different jobs |
| A plot block ran twice | `grep -c savefig` returned 2 | — |
| A control test crashed on duplicate labels | Runtime error | **The bug under investigation broke the investigation** |
| A merge returned all-empty | Reading the output | Joined on a key whose equality was never checked. Same lesson as F9 |
| A cell failed with `NameError` | Running it in the browser | It relied on a variable from a cell 20 rows up |
| The sensor count read as 6, not 8 | **Your question** | `assessment.md` §4 mixed up two different things |
| Claimed light at night is impossible | **Your correction** — a person can switch a lamp on | The right test is duration, not time of day. See §2.9 |
| A first fix flagged 11 legitimate SENS-07 readings | The audit | A time-of-day check on a misaligned timeline produces nonsense |
| The hierarchy parser named a parent the model never scores | **Running it** — `KeyError: 'nutrient-related issue'` | A taxonomy chain contains groups, not only classes. `chain[-1]` is not the parent; the last *known class* is |
| A "delete the duplicate line" edit added two instead | Reading the result instead of assuming | The edit tool reported success. It matched, and matched again |
| The notebook kept the old 3-argument call after a signature change | nbconvert **aborting** — which then left stale outputs behind, so the first check *looked* clean | Same class as the deleted-function bug above. Nothing in the notebook is compiled against the module |
| Claimed the context compaction had worked | **Your screenshot** — the counter was unchanged | I asserted a mechanism I had not verified. It is *"report a number you have not seen the output for"*, applied to a claim about my own tooling |
| F4 read as "SENS-03 ramps 136 µS/cm/day" | It is **flat at ~700 for ten days, then ramps from 06-11** — a regime change with an onset, not a constant drift | Measuring the daily means for Task 6 |
| `log_alignment` tested "the plant" | It tested `device_id.first()` — **one arbitrary probe**. For UP-1001 that changes the answer, because SENS-02 rises where SENS-01 does not | **Your question** about F9 |
| F11 covered "the logs" | **One of four log legs.** All four now tested; the light leg contradicts | **Your question** about the other log types |
| Sliced `sensors.py` with a boundary *before* the start | **Duplicated half the file** (983 lines, 2 defs each) | Inspecting the line count |
| `git checkout HEAD -- sensors.py` to repair that | **Destroyed two pieces of uncommitted work** — `EVIDENCE_NOTES` and the multi-probe fix. Both redone | Noticing the import error |
| Rewrote Task 2's evidence section when Task 4 was asked for | Reverted | **Your correction** — the fourth adjacent-but-unrequested change |
| nbconvert reported `0 errors` | It had **aborted without writing**, leaving the previous run's outputs. Happened three times | Reading the outputs, not the exit code |
| F4 read as "SENS-03 ramps 136 µS/cm/day" | It is **flat at ~700 for ten days, then ramps from 06-11** — a regime change with an onset, not a constant drift | Measuring the daily means for Task 6 |

**The pattern:** the audit gate, the ponytail review, and actually running the
code each caught things that reading did not. Several were mistakes I had made
minutes earlier.

---

# Part 4 — Smaller observations

Not findings, but real properties of the data.

**`image_id` adds nothing.** Its format is `IMG-<plant#>_<YYYYMMDDHHMM>`, and
both parts match the other columns on all 28 rows. A duplicate key.

**`log_type` is fully determined by `text`.** 14 different phrases, each mapping
to exactly one category. A lookup, not a classification problem. The text also
carries a *volume* — `"Watered ~200ml"` — which the category column throws away.

**`is_healthy` is just `is_healthy_probability > 0.5`.** Checked on all 28 rows.
No extra information.

**The disease list is a family tree, not a flat list.** `Abiotic` is the *parent*
of `Water-related issue` and `Nutrient deficiency`, and its score follows its
strongest child. Taking the top-scoring entry returns the broad category, not a
diagnosis.

**`is_plant` is True on all 28 images**, probability at least 0.9515. Nothing to
test it against.

**`Nutrient deficiency` never goes above 0.073.** The brief's own example —
fertilising → EC rise → "Nutrient deficiency" — **cannot be tested** on this data.

**Watering is on a mechanical schedule, not a human one.** Rise-to-rise gaps are
exactly 108h, 120h, 72h and 96h on four devices, and 35 of 35 rises (excluding
SENS-08) land exactly on `00:00` or `12:00`. See F11 above.

**Photos are only taken between 09:00 and 18:00.** Never at night. Same kind of
artefact.

**Fertilising never moves EC.** All five fertilising logs, across four devices,
give changes of −6 to +3 µS/cm — against day-to-day noise of 42. This control
group is what makes F4 (drift) convincing.

**SENS-03's EC ramp has nothing logged near it.** It starts 06-11. The closest
UP-1002 log is a *light* entry on 06-10, and its only fertilising log is 06-01 —
ten days earlier.

**A log test silently used only half the data.** The log-matching check took
*one* device per plant, so for the two-sensor plants it ignored the second
sensor. Checked afterwards: the conclusion holds (1/6 and 0/6 either way). But
nothing flagged the choice.

**The two figures show most of Task 2 at a glance.** Between them they make F1,
F3, F4, F5, F6, F7, F10, F11 and F12 visible before a single test runs.

---

# Part 5 — Still open

Cross-referenced to `decision_register.md`, listed here so the report can name
them.

| # | Open question | Who can answer | What it blocks |
|:---|:---|:---|:---|
| **D1** | Are the spec ranges current for this device generation? | Hardware | every flag and empty value |
| **D2** | Is 15 minutes the configured rate, or a buffer flush? | Firmware | the completeness numbers |
| **D3** | Is SENS-07's 2h offset a timezone, or a clock fault? | Firmware | testable — it becomes 1h in winter |
| **D4** | Is Fahrenheit one device, or a firmware variant? | Firmware | how wide the unit fix needs to be |
| **D5** | Can the analysis team use flagged, out-of-spec values? | Analysis | 382 readings on SENS-04 |
| **D6** | How long can a healthy channel hold one value? | Firmware | the 12-hour freeze threshold |
| **D7** | Is `substrate_label` the conversion actually applied? | Product | how serious F13 is |
| **D8** | Can the analysis team tolerate a 48.5 hour gap? | Analysis | 193 readings |
| **D9** | Does the device do anything at 00:00? | Firmware | whether some rises are waterings at all |
| **D10** | Are the 8 devices in the same place? | Product | whether F12 is an artefact or real |
| **D11** | Can the app put two sensors on one plant? | Product | **F10, and Task 5** |
| **D12** | Is there a soil-temperature spec? | Hardware | what `SPEC` covers |

Four conversations: **Hardware** (D1, D12) · **Firmware** (D2, D3, D4, D6, D9) ·
**Product** (D7, D10, D11) · **Analysis** (D5, D8).

## The one problem with no automatic check

**F13 — the substrate label has no start/end date.** It was found by reading a
repotting log and noticing the label did not move. No check can find this from
the files, because finding it needs the app's configuration history.

## The one that blocks the most

**D11.** Task 5 (the per-plant table) cannot be built for UP-1001 and UP-1003
until it is answered. Averaging two unrelated series produces a number that
describes neither pot — and averaging is exactly what would hide F3.

---

## The third review — the one that found the wrong claims

A frontier model reviewed the repository cold (Part 7) and scored
it 7/10 — *"interview-worthy, with reservations"*. **Every one of its 18 checkable
claims reproduced.** This was not a style critique; it found wrong arithmetic and
a rule file propagating it.

### The defects, and what verified them

| Claim | Verified by |
|:---|:---|
| Frozen detector nulls legitimate dark light | 52 night zeros → all nulled |
| Conflicting duplicates silently discarded | `grain_violations` found it; `clean()` dropped one |
| Healthy input *fails* the audit | `0 rejections recorded` → gate FAILS |
| Expected slots derived from observed endpoints | deleting a day still reported 100 % |
| ISO-only input fails parsing | `assert first.max() > 12` on an empty slice |
| An unmapped device vanishes | 5 plants, 2,016 readings gone, no error |
| `triangulate` reads probe 1 only | probe-2-only rise → `"no rise"` |
| `NaN` reported as `"no rise"` | missing baseline → negative |
| 105 drydown rows stale vs current VWC | 45/48/12 — exact |
| Notebook "65–107 … keep it" vs code nulling >100 | 49 sources, 0 retained |
| Notebook "F4 flagged in `qc_flags`" | 702 of 1,056 drifting rows unflagged |
| "FYTA is already using S3" | synthetic fixture paths |
| Script prints "wrote run.log" without writing one | shell redirection, not the script |

### The claims that were simply wrong

Three of these were mine, stated confidently, in docstrings and in the graded
write-up:

**Differentiation does not escape calibration.** I wrote that a drying *rate*
"carries across the fleet without a calibration". For `reported = a·true + b`:

```
d(reported)/dt = a · d(true)/dt
```

The offset `b` dies; the gain `a` survives — and the gain is precisely what the
substrate curve changes. Arithmetic, not opinion.

**The shared-environment claim was backwards.** The docstring said fleet-deviation
on ambient channels is "meaningless, because every device carries the same series".
A tight shared signal makes the fleet a *better* reference, not a worse one — and
`sensors.py` used exactly that method to find SENS-07's clock and unit faults while
the docstring called it meaningless.

**A NULL expected slot is not a fabricated measurement.** See the correction above.

### The lesson that is about method, not data

> *"The rule file repeats some of these claims. A repository instruction is not
> scientific evidence; encoding an assumption as a rule makes it easier for later AI
> work to repeat it, not more likely to be true."*

That is the failure mode, named exactly. `AGENTS.md` said two same-pot probes "must
still be positively correlated" — an assumption written as a rule. It propagated
into the write-up, into F10/F11, and into the answer I gave the owner about the
dense grid. **The rule was the vector.** It now carries a preamble saying it records
decisions rather than evidence, and the specific claims have been amended.

**Why it took three reviews.** The first two audits asked "does the code do what it
says?" and "does the number compute?" — both passed, repeatedly. This one asked
**"does the header describe what is computed?"** and **"is the stated reason
actually true?"** Those are different questions, and no amount of re-running the
same checks reaches them.

---

## The fourth review — the reassessment, and the holes re-reading could not find

Part 7 was re-read cold after the correction pass and returned
R1–R6. **All six reproduced.** Two of them (R2, R3) were regressions introduced by
the *previous* fix — the correction pass had added a check that could be satisfied
without the behaviour it claimed to test, twice, in the same function.

### What the reassessment found, and what verified it

| Claim | How it was verified here |
|:---|:---|
| Notebook fails from a fresh kernel | `heads` consumed at cell 39, defined nowhere (50 cells scanned) |
| Quarantine crashes on real input | `head["timestamp"] - Timedelta` on source TEXT; the test helper had been overwriting `timestamp` with the parsed column |
| `A, A, B, B` on one key quarantines nothing | reproduced: 0 rows quarantined, arbitrary winner kept, audit passed |
| Ledger preserved no payloads | `channel="(row)"`, `raw_value=NaN` — both payloads gone |
| Audit accepts 2,016 deleted rows | inner-join value comparison over shared keys only |
| Audit rejects a re-ordered frame | same check, compared positionally |
| Flags moved to unrelated rows pass | count comparison (`8 == 8`) rather than key sets |
| Omitting the frozen detector passes | every check reconciled *recorded* rejections |
| A `NaN` probe score masks a valid one | `max()` kept the first element; `SENS-01 +nan, SENS-02 +8.84` |

### What the fixes are

- **Quarantine is decided per key group.** Lossless dedupe only where every payload
  on the key agrees; otherwise every version is quarantined, with its payload
  serialised into a new `row_payload` ledger column. `ts_aligned` is computed
  *before* the duplicate branch, from `ts`, not from the source text.
- **The audit accounts for every source row**: retained + losslessly deduped +
  quarantined must equal the source, and the ledger's quarantined keys must match
  the conflicting keys exactly.
- **Values are compared after aligning by key**, so re-ordering is not an edit and a
  deletion is.
- **Flags are reconciled by key**, not by count.
- **The frozen detector is re-run on the raw frame** inside the audit, so a cleaner
  that never detects a window cannot pass.
- **Probe scores must come from valid observations** (`notna().any()` per window),
  and every probe reports an outcome in `leg_detail`, testable or not.

### Corrections to the record, including one the reviews did not catch

**The dark-hour flag was matched on the raw clock.** `clean()` detected spikes on an
*aligned* frame and then matched `df["ts"]` — the device's own clock. On a device
with a declared offset the flag would land on a different reading than the detector
meant. It does not fire on this sample (SENS-08, the only device with spikes, has no
offset — verified: the 8 detected spikes and the 8 flagged rows coincide), so it was
a latent bug, not a wrong number. The count-based audit could never have seen it.
Now both the detection and the match use the aligned frame.

**`plant_features.csv` counts and the audit's check count are measured, not
remembered.** 11,903 feature rows, 1,415 rejections, 15,935 cleaned rows, 21 audit
checks, 18 regression checks. Each was read off the current run.

**HANDOFF said 51 notebook cells; it had 50.** The cell that created `heads` was
removed in the correction pass and the count was carried forward by hand. Now
re-derived from the file: 51 cells, 21 code cells, 0 errors.

### Verification this pass, and what each proves

| Check | Result |
|:---|:---|
| `uv run fyta_pipeline.py` | exit 0 · 21 of 21 audit checks pass |
| `uv run test_gates.py` | 18 of 18 · **each new check verified to FAIL when its fix is reverted** (7 mutations, one per defect) |
| Notebook, fresh kernel | 51 cells, 21 code, 21 executed, **0 errors**, 2 figures |
| Idempotency | re-running the whole pipeline reproduced **all 14 artifacts byte-for-byte** (md5) |
| `data/` | unmodified (git clean on `data/`) |
| Write-up | 1 A4 page, 533 words, 10.6 pt (was 783 words at 9.3 pt) |

### The batching decision (R6)

One policy, stated once: **one compacted Parquet object per device per day.**
3 M PUTs/month = $15, so the total is **≈$190–450/month** with IoT Core. An hourly
object holds four readings at this cadence and costs 24× the requests
($533–792/month total) — that is the price of fresh *lake files*, not fresh
dashboards. Lake freshness is therefore ≤ 1 day, and the per-device-window checks
and the serving table run hourly off the ingestion buffer instead. The earlier
"$200–500 envelope" was an estimate with no policy behind it; it is now derived.

---

## The prose pass — the editorial work the third review asked for

The reviewer's closing section asked for a separate, authorised editorial pass, and
named where each kind of reasoning belongs. What follows is what was cut, what was
kept, and one correction that the pass itself introduced.

### Where the prose was

Measured before and after, submission-facing only (`docs/observations.md` and
`HANDOFF.md` are the internal record and were left alone):

| Artifact | Before | After | What it is now |
|:---|---:|---:|:---|
| `fyta/*.py` comments + docstrings | 6,057 w | 3,616 w | contracts, units, edge cases, non-obvious decisions, `ponytail:` markers |
| `fyta_pipeline.py` print literals | 1,745 w | 940 w | counts, decisions, limits (run.log is 565 lines, was 647) |
| `fyta_analysis.ipynb` markdown | 5,357 w | 4,245 w | evidence beside the interpretation it supports |
| `docs/PIPELINE_DESIGN.md` | 3,754 w | 3,021 w | one flow, assumptions, failure handling, cost arithmetic |
| `WRITEUP.md` (earlier in this session) | 783 w | 533 w | the hiring-review summary |

That is ~17,700 words of submission prose down to ~12,300, at a larger type size in
the PDF (10.6 pt against 9.3 pt).

### The rule applied

Each repeated explanation keeps **one** home, and code no longer retells review
history:

| Explanation | Kept in | Removed from |
|:---|:---|:---|
| Two probes, never averaged, `vwc_delta` | notebook §5a | module docstrings, pipeline print, findings `next` |
| Nothing clipped, averaged or interpolated | `cleaning.py` module docstring | pipeline print, notebook §3a |
| Impossible → null, out-of-spec → flag | `domain.py` `IMPOSSIBLE` block | pipeline print |
| Which review found which defect, and what the old version did | here, and the tests that pin them | all module comments |
| Task/section numbering | pipeline docstring index | notebook index |
| Task 7 design and cost | `PIPELINE_DESIGN.md` | notebook §7 (now points at the doc) |

Also removed: all-caps emphasis (`FLAGGED, NOT EMPTIED`, `KEY GROUP`, `A RISE, not
a change`), pull-quotes, "X, not Y" setups where Y alone reads, and two of the
reviewer's eleven named passages that had not been touched in the first sweep.

### What was deliberately NOT cut

- Every threshold, count, path, device id and reversal condition, including the
  F4 drift arithmetic, F7's buffer/193-slot limit, the F12 fleet-reference rule,
  `LEG_SIGMA`/`LEG_PROB`/`IMAGE_WINDOW_H`, `WINDOW`/`MIN_PERIODS`, and the
  observed-span coverage ceiling with its activation-time prerequisite.
- The `ponytail:` comments, verbatim, including the one naming the daytime-zero
  blind spot in the frozen detector.
- Test docstrings. A test that says what it protects against is the one place the
  old defect belongs, and deleting it would leave the assertion unexplained.

### Correction: the prose pass deleted a statement

`cleaning.py` lost `df = df.drop(columns=["ts"])` when a comment above it was
rewritten: the comment ("drop the working time column") survived and the statement
did not. The pipeline failed loudly on the next run
(`ValueError: column label 'ts' is not unique`, from `dark_hour_spikes` receiving a
frame with two `ts` columns) and the line was restored.

The mechanical audit that caught nothing else: for each module, every line with
comments *and docstrings* removed was diffed against the same view of the previous
commit. All remaining statement-level differences were attributable to this
session's own R1–R6 edits, and `features.py`, `signals.py` and `domain.py` showed
zero. Verification after the repair: 18/18 regression checks, pipeline exit 0, and
**every CSV and figure byte-identical to the pre-prose run** — only `run.log`
differs, because that is the artifact the pass rewrote.

**The lesson repeats the session's other one:** a prose-only edit is still an edit
to a file that runs. The check is the run, not the diff.

### Correction: the notebook's diagrams were rewritten into shell calls

A prose rewrite of the Task 7 cell turned

```
![Variant A](images/task7_variant_a.jpeg)
```

into

```
__omp_shell("[Variant A](images/task7_variant_a.jpeg)")
```

so the notebook rendered a shell-call placeholder where each architecture diagram
belongs. The same edit path also dropped the `image_predictions` cell that defines
`heads`, which the Task 6 cell consumes — the R1 regression, reintroduced.

**Why the check did not fire.** `test_notebook_assets_exist` matched
`!\[[^\]]*\]\(([^)]+)\)`. Losing the leading `!` removed the reference from the
scan, so the test found zero references and approved. `refs` was never asserted
non-empty.

**Fix.** Image markdown restored, the cell spliced back from the last verified
executed copy, and the test hardened three ways, each mutation-verified:

| Mutation | Result |
|:---|:---|
| one reference rewritten as a shell call | FAILS — `image markdown was rewritten into a shell call` |
| all references removed (empty set) | FAILS — `no image references found` |
| asset renamed away | FAILS — `notebook references missing asset(s)` |

The general rule this is the third instance of in this session: **a check that can
be satisfied by finding nothing is not a check.** Assert the positive case (a
reference exists, a file resolves, a test observes the defect) before asserting
the absence of the bad one.

---

---

# Part 6 — External reviews 1 and 2 (verbatim)

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

---

# Second Audit: Reassessment After Corrections

## Updated verdict

**Substantially improved, but I would still not submit this exact version.**

The previous blocking omission is fixed: `submission/WRITEUP.md` and the one-page `WRITEUP.pdf` now exist. The three regression checks pass, the main row counts reproduce, and several prior correctness defects were repaired.

My updated score is **approximately 7.3/10**, up from **6.5/10**.

Fix the three issues below before submitting:

1. Correct factual errors in the one-page write-up.
2. Make the audit verify `outside_spec` flags.
3. Stop treating a pre-event image score as a post-fertilization response.

After those fixes and a final contradiction cleanup, I would rate it around **8 to 8.5/10** and consider it interview-worthy.

No files were changed during the reassessment. The Git working tree remained clean.

## Verification performed

I compared commit `d6a2893` against the previous version at `ac034cc`, then inspected the current implementation, outputs, notebook, tests, write-up, PDF, and affected documentation.

Fresh in-memory recomputation produced:

| Output | Result |
|---|---:|
| Raw sensor rows | 15,950 |
| Cleaned rows | 15,935 |
| Rejections | 1,415 |
| Feature rows | 11,903 |
| Audit checks | 13 |
| Baseline audit failures | 0 |
| Notebook cells | 51 |
| Stored notebook errors | 0 |

The regression command produced:

```text
ok  a falling ec does not corroborate
ok  audit catches an uncleaned frozen window
ok  run lengths not run starts

3 of 3 regression checks passed
```

## Material improvements

### Required write-up added

`submission/WRITEUP.md` and `submission/WRITEUP.pdf` now provide the requested one-page deliverable.

The PDF is visually professional and genuinely one page, although dense. This resolves the largest submission-level blocker from the first review.

### Frozen-window audit repaired

`submission/fyta/cleaning.py:107-128` now reconciles rejection records with null values in both directions:

- Every rejection must correspond to a null clean value.
- Every null clean value must have a rejection record.

The previous adversarial mutation, restoring all 1,344 frozen values, is now caught.

### Range-run classification corrected

Current output correctly reports:

| Device/channel | Runs | Isolated | In runs | Longest run |
|---|---:|---:|---:|---:|
| SENS-04 moisture | 11 | 0 | 431 | 44 |
| SENS-03 EC | 17 | 8 | 346 | 307 |

This fixes the original run-start counting error.

### EC direction corrected

`submission/fyta/sources.py:165-177` now requires:

```python
d_ec_sigma > LEG_SIGMA
```

A large EC decrease no longer counts as support for fertilization.

### Image timing improved

The triangulation output now includes:

- Signed `hours_off`.
- A ±48-hour tolerance.
- A separate `no image` state.

These changes are materially better than the previous unbounded nearest-image lookup and truncated `days_off`.

### Claims clarified

The revised material now:

- Admits that the SENS-03 drift is not flagged for the full regime.
- Explains why sparse image/log events are not embedded into every feature-table row.
- Corrects the unsupported claim that image/sensor agreement is inherently circular.
- Adds explicit detectors for the F10, F11, and F12 metrics.
- Corrects the raw row-size calculation.
- Adds three focused behavioral regression checks.

## Remaining submission blockers

### 1. The required write-up contains incorrect statements

This is the highest-priority issue because reviewers may read only the one-page PDF before deciding whether to inspect the code.

#### SENS-04 is described incorrectly

`submission/WRITEUP.md:69-71` says:

> A counting error made a dead sensor look intermittent. A 431-reading fault was reported as eleven separate glitches. It is one continuous fault.

The current evidence says:

```text
11 runs
0 isolated readings
431 readings in sustained runs
longest run: 44 readings
```

It is neither eleven isolated glitches nor one continuous 431-reading fault.

SENS-04 is also classified elsewhere as:

```text
unknown - fault or different physical setup
```

It is not established as a dead sensor. The dead channel is SENS-06.

A defensible replacement would be:

> A counting error treated the start of each sustained excursion as an isolated sample. The corrected result is 11 sustained runs containing all 431 out-of-spec readings, with zero isolated readings. The cause remains unresolved.

#### The test statement is false

`submission/WRITEUP.md:64-73` says three defects were fixed and that each has a test. The listed defects are:

1. Frozen-window publication gate.
2. Run counting.
3. Hardcoded finding numbers.

The actual tests in `submission/test_gates.py` cover:

1. Frozen-window audit.
2. Run counting.
3. Falling EC not counting as corroboration.

No test covers the third defect described in the write-up. The triangulation defect is not mentioned in that section.

The write-up must either describe the actual third regression test or add a real test for the hardcoded evidence issue.

#### The configuration statement is inaccurate

`submission/WRITEUP.md:80-81` says:

> Soil type, sensor model and plant are code today.

Plant mapping and substrate labels are already data. Code currently holds device-specific unit fixes, clock offsets, physical/specification ranges, and other domain constants.

A more accurate statement:

> Move device-family specifications, calibration versions, unit policies, and clock corrections into an effective-dated registry.

### 2. The audit still does not verify quality flags

The rejection/null audit is fixed, but `outside_spec` flags are not reconciled against their detector.

I removed all **736** `outside_spec` flags in memory while preserving the dark-hour flags. Result:

```text
outside_spec flags removed: 736
audit failures: 0
```

All 13 audit checks still passed.

This means the publication gate can approve data where every out-of-spec warning has silently disappeared.

`submission/fyta/cleaning.py` audits dark-hour flags explicitly, but it needs the same detector-to-output reconciliation for each channel in `SPEC`:

- Every detected out-of-spec value must carry the expected flag.
- No in-spec value should carry that flag.
- Impossible values that were nulled need clearly defined treatment so they are not double-counted accidentally.

The current write-up says:

> Finding a problem and fixing it are separate jobs, and I check both.

That statement remains too broad until the flags are audited too.

### 3. Task 6 still treats a pre-event image as a response

The image window now has a tolerance, but it is symmetric:

```python
hours.abs() <= IMAGE_WINDOW_H
```

The nearest image can therefore occur before fertilization.

I constructed a fresh fixture with:

- Strong post-event EC rise.
- Nutrient-deficiency score of `0.9`.
- Image captured 2.5 hours **before** the fertilization event.

The result was:

```text
d_ec_sigma: 14.03
hours_off: -2.5
sensor_leg: rises
model_leg: responds
corroborated: True
```

A pre-event image cannot be a response to a later fertilization event.

The model leg also tests a static score, not a change:

```python
nutrient_def > 0.10
```

A high nutrient-deficiency score after fertilization could mean the symptoms persisted. It does not demonstrate that the model responded to the event.

Use one of these interpretations:

- Require a post-event image and call it **temporally aligned evidence**, not a response.
- Preferably compare pre-event and post-event scores and test for a directionally appropriate change.
- If only a pre-event image exists, label the model leg `pre-event only` or `not testable`.

Add a regression fixture for this case. The current triangulation test covers EC direction but not image causality.

## Other important issues

### F4 evidence remains hardcoded

`submission/fyta/sensors.py:354-358` contains:

```text
136 uS/cm/day at R2=0.99
-6..+3 against daily noise 42
```

The new detectors made F10, F11, and F12 more reproducible, but I found no implementation that calculates and injects these F4 values into the finding.

The output remains reproducible only in the weak sense that running the code prints the same hardcoded string. The evidence itself is not recomputed.

### Hardware assumptions remain too confident

The production design still asserts:

```text
320 measurements × 4/hour = approximately 80 hours
```

FYTA's current technical page distinguishes Beam 1.0 at once per hour and Beam 2.0 at four times per hour, while the 320-measurement storage section is presented for the Beam at once per hour and described as about 13 days. It does not clearly assign that storage limit to Beam 2.0.

The 80-hour watermark should therefore be presented as conditional:

> If the deployed generation buffers 320 readings at four readings per hour, the maximum buffered lateness is approximately 80 hours. Confirm generation-specific storage behavior with firmware.

Related overclaims remain:

- F7 calls the gap recoverable and therefore a sync failure. Power loss or failure to measure remains possible.
- `docs/assessment.md` attributes humidity to the Beam body, while the current FYTA comparison lists humidity for Sphere, not Beam 1.0 or 2.0.
- “FYTA already uses AWS” is inferred from synthetic `s3://` image paths.
- The design sizes average throughput but not relay-upload bursts.
- The notebook calls the `7.57×` compression ratio measured, but currently stores it as a constant rather than generating it from a reproducible artifact.
- `docs/PIPELINE_DESIGN.md:32` still says 220 GB/year while the table says 238 GB/year.

Sources:

- [FYTA technical data](https://fyta.de/en/pages/technische-daten)
- [FYTA Beam G2](https://fyta.de/en/products/fyta-beam-gen2)

### Stale contradictions remain

Examples:

- The notebook Task 4 table still says `r = 0.75 and circular`, immediately followed by text explaining that “circular” was wrong.
- `docs/HANDOFF.md` still calls the image agreement circular in one section and corrects itself later.
- The handoff retains stale file, line, module, and cell counts.
- One handoff section says the write-up remains the next action although the write-up now exists.
- Older documentation retains superseded F10, F11, F12, spike, and drydown values.
- `docs/PIPELINE_DESIGN.md` contains the 220/238 GB contradiction.

Not every internal note needs submission polish. The notebook, write-up, README, pipeline design, and generated outputs do.

### Co-located correlation includes known-bad data

The new co-located sensor calculation reports approximately `r = 0.103` for the SENS-04/SENS-06 pair while including the 1,344-sample frozen SENS-06 period.

The valid pre-freeze overlap gives approximately `r = 0.140`.

Both values support the conclusion that the probes do not move together. The numerical conclusion survives, but the statement that the frozen interval attenuates the correlation and makes the “true disagreement worse” is not demonstrated by this comparison.

## Updated scorecard

| Area | Previous | Current | Assessment |
|---|---:|---:|---|
| Task 1: ingest and exploration | 9 | **9** | Remains strong |
| Task 2: data quality | 8 | **8** | Better reproducibility, but F4 still hardcoded |
| Task 3: cleaning | 5 | **7** | Rejection gate fixed; flag audit still missing |
| Task 4: source validation | 6 | **7** | Circularity corrected, notebook still contradictory |
| Task 5: feature table | 6 | **7.5** | Scope is now explicit and defensible |
| Task 6: triangulation | 4 | **6** | EC direction and tolerance fixed; image-response semantics remain wrong |
| Task 7: production design | 6 | **6** | Good structure, same hardware and sizing assumptions |
| Communication/deliverable | 4 | **7** | One-page PDF exists, but contains factual mismatches |

**Overall: approximately 7.3/10.**

## Updated recommendation

The update fixed meaningful defects rather than merely changing prose. That is a positive engineering signal.

Before submitting:

1. Correct `WRITEUP.md:64-81`, then regenerate the PDF.
2. Add `outside_spec` detector-to-flag reconciliation to the audit.
3. Reject pre-event images as responses and add a regression check.
4. Compute or remove the remaining hardcoded F4 metrics.
5. Remove contradictions from the notebook and submission-facing documents.
6. Qualify generation-specific hardware assumptions.

After the first three, the submission is defensible. After all six, it becomes a strong interview submission rather than an ambitious draft with remaining confidence gaps.

---

# Part 7 — Third review, and its reassessment (verbatim)

**Review date:** 20 September 2026  
**Reviewer:** GPT-6 Astra, acting as an independent hiring assessor  
**Overall rating:** **7/10**  
**Hiring recommendation:** **Advance to a technical interview, with reservations.**

> **Latest status:** the correction pass remains around **7/10**. Several fixes work, but the notebook now fails from a fresh state and the audit accepts unexplained row loss. See [Reassessment after the correction pass](#reassessment-after-the-correction-pass) for current findings and [Prose and presentation recommendations](#prose-and-presentation-recommendations) for the requested editorial advice. The original review below remains as a historical record.

This report assesses the repository as reviewed on 20 September 2026. The review itself was read-only. This document was created afterward at the owner's explicit request; no source code, notebook, dataset, or generated output was changed.

The scores and hiring recommendation are an independent assessment, not FYTA's official scoring or a prediction of its decision.

---

## 1. Executive verdict

The submission contains strong data-quality investigation, sensible preservation of raw evidence, and reproducible numerical outputs. It also contains incorrect reasoning, incomplete safeguards, and contradictions between the notebook and implementation.

**The work is not fundamentally wrong. It is interview-worthy, but not yet a strong pass on correctness and reasoning.**

The strongest evidence in its favor is the identification of several distinct failure classes: units, clocks, frozen channels, absent rows, duplicate delivery, join cardinality, drift, and conflicting probes. These directly address the core of the brief.

The main weakness is the gap between what the implementation establishes and what the prose claims. Several reasonable choices for this sample have become absolute rules that do not hold generally:

- A timestamp row with a NULL measurement is called fabricated data.
- Taking a derivative is claimed to remove the need for comparable calibration.
- A shared environmental signal is said to make peer-based anomaly detection unusable.
- Lack of corroboration is described as proof that the sources were never connected.
- Audit checks are described as verifying remediation when some only compare counts or configuration sets.

Using DeepSeek or another AI system is not itself a negative. FYTA explicitly permits AI. The relevant hiring question is whether the candidate can distinguish verified results, useful hypotheses, and unsupported explanations.

I would invite the candidate to discuss the work. I would not record a strong-hire recommendation from the submission alone, and I would not endorse its broad claims of trustworthy cleaning without qualification.

## 2. What the brief actually asks for

The canonical brief is [assessment.md](assessment.md).

Its priorities are:

1. A timeboxed investigation, approximately two to four hours, with the correspondence asking for about three hours.
2. Data-quality judgment, especially distinguishing sensor/data problems from physical signals.
3. A first cleaning pass, with explicit decisions and limitations.
4. Cross-source validation, a time-indexed per-plant table, and consideration of triangulation.
5. A production pipeline **sketch**, not a built production platform.
6. A short write-up or recording explaining findings, decisions, and next steps.

The correspondence requests only the short write-up, while the task brief also requests runnable code. The repository now contains both.

This review does **not** penalize the submission simply for lacking a fully productionized system. Some findings below concern reusable-code behavior rather than errors in the shipped sample. They matter because the submission makes strong claims about its safeguards and general principles, but they should not be confused with a requirement to finish every possible edge case in three hours.

## 3. Review scope and verification method

### Artifacts reviewed

- The assessment brief and correspondence.
- Repository rules, README, domain notes, observations, decision register, handoff, pipeline design, diagram sources/prompts, defect inventory, and previous second-opinion reports.
- All repository Python scripts and modules.
- All 52 notebook cells and their stored outputs.
- The four raw CSV datasets.
- All 11 published CSV outputs and the run log.
- Both exploratory figures and both architecture diagrams.
- Dependency declarations and lockfile metadata relevant to the runtime.
- The write-up Markdown and PDF metadata/extracted text.

Generated virtual-environment internals, bytecode caches, and stale notebook checkpoint bodies were not treated as submission source.

### How verification remained read-only

The entry point and notebook write outputs, so neither was executed end to end.

Data transformations and tests instead ran in a filesystem read-only sandbox using `bwrap`, with networking disabled and Python bytecode writing disabled. Matplotlib initially attempted to create a cache and failed because the filesystem was read-only. For the non-plotting data checks, its imports were replaced with inert in-memory modules. No numerical function used a replacement implementation.

Consequently:

- Data transformations and existing regression tests were executed.
- Saved figures were inspected, not regenerated.
- Clean-environment installation, plot regeneration, notebook execution, and PDF regeneration were not verified in this review.

The Git working tree was clean before and after the review. Only this report was subsequently added with permission.

### Freshly verified results

| Check | Result |
|---|---:|
| Raw sensor rows | 15,950 |
| Cleaned sensor rows | 15,935 |
| Rejection records | 1,415 |
| Per-plant feature rows | 11,903 |
| Duplicate per-plant feature keys | 0 |
| Image predictions flattened | 28 |
| Findings | 13 |
| Baseline audit checks | 17 of 17 passed |
| Existing regression tests | 4 of 4 passed |
| Published CSVs compared with fresh calculations | 11 of 11 matched |
| PDF page count | 1 A4 page |
| Extracted PDF word count | Approximately 811 |

CSV comparisons covered content, not just shapes, allowing negligible floating-point serialization differences. Repeated cleaning also produced identical cleaned and rejection frames.

The following outputs matched fresh in-memory calculations:

- `cleaned_sensor.csv`
- `qc_rejections.csv`
- `plant_features.csv`
- `images_flattened.csv`
- `task2_findings.csv`
- `task2_detection_coverage.csv`
- `task2_coverage_gaps.csv`
- `task4_source_assessment.csv`
- `task6_triangulation.csv`
- `task8_drydown.csv`
- `task9_log_signals.csv`

Matching a findings CSV proves that the current code reproduces it; it does not independently prove every hardcoded narrative claim inside that CSV.

## 4. What is strong

### 4.1 The exploratory investigation finds the important defects

The most valuable findings are:

- **SENS-07 unit mismatch.** The Fahrenheit interpretation is supported by scale and level behavior, not correlation alone. A fresh fit against aligned peer temperatures gave approximately `device = 1.797 × peers + 32.069`, consistent with Fahrenheit conversion.
- **SENS-07 clock mismatch.** Daylight alignment supports a two-hour relative offset. The exact clock/timezone cause remains a separate question.
- **SENS-06 frozen moisture.** The 1,344 samples at 25.01 are convincing evidence of a bad channel. Other channels on that device continue changing.
- **SENS-05 absent readings.** The 193 missing slots are correctly identified despite no empty cells in the source table.
- **Duplicate delivery.** The sample contains 15 redundant copies, with no conflicting payloads in the original input.
- **Join fan-out.** The measured 49-to-67 log expansion and 28-to-35 image expansion expose a genuine grain hazard.
- **SENS-03 EC ramp.** The sustained trend is detected and characterized, rather than treated as isolated noise.
- **Probe disagreement.** Keeping the two assigned probes visible avoids hiding unresolved disagreement in an average.

These address the assessment's central concern: there are different kinds of problems, and a generic null check or outlier filter will not find them all.

### 4.2 The principal cleaning choices are defensible

The cleaner preserves source values, creates corrected columns, retains rejection reasons, and distinguishes impossible values from suspicious but possible observations.

Leaving the two-day outage uninterpolated is reasonable. Keeping the eight suspicious light readings while flagging them is also more defensible than declaring all nighttime light impossible.

Preserving separate probe columns is appropriate while assignment, calibration, and physical setup remain unresolved. The concern is the universal wording around this decision, not the decision for this sample.

### 4.3 The feature table has a clear grain

The table declares and checks `(user_plant_id, ts_aligned)`, preserves device identity with positional columns, and exposes probe disagreement.

Trailing ranks avoid the obvious full-history look-ahead problem in the feature table. The distinction between delivered-row completeness and expected-slot completeness is also valuable.

### 4.4 Previous defects received real fixes

The current implementation fixes several defects described in earlier reviews:

- Run starts are no longer miscounted as isolated observations.
- A large EC fall no longer corroborates an expected rise.
- A pre-event image no longer counts as a post-event response.
- Restoring frozen values while retaining their rejection records is caught.
- Removing outside-spec flags is caught by the current audit.

The four existing regression tests pass. Historical defects should not be scored as though they remain unchanged.

## 5. Confirmed implementation defects

The following findings were reproduced with in-memory fixtures or mutations. No test changed repository files.

### 5.1 High: frozen-channel cleaning deletes legitimate constant light

**Location:** [sensors.py](../submission/fyta/sensors.py), `frozen_windows()`, lines 407–418; [cleaning.py](../submission/fyta/cleaning.py), lines 45–55.

The detector treats any sufficiently long run of identical values as a frozen channel. It applies this rule across all channels. The cleaner then nulls each detected run.

The documentation repeatedly describes cross-channel corroboration, but the detector does not perform that check. More importantly, corroboration alone would not make the rule safe for every channel: zero light throughout the night is normal even while temperature and humidity move.

**Fixture:** 52 consecutive 15-minute zero-light readings from 18:00 to 06:45, with other channels changing and no impossible values.

**Observed result:** all 52 legitimate light measurements were nulled.

The actual SENS-06 moisture diagnosis is strong. The generalized cleaning rule is unsafe.

**Correction direction:** make freeze detection channel-aware, respect expected constant states and elapsed-time continuity, and distinguish a candidate plateau from a confirmed unusable interval.

### 5.2 High: conflicting duplicates are detected but silently discarded

**Location:** [cleaning.py](../submission/fyta/cleaning.py), line 29; [sensors.py](../submission/fyta/sensors.py), `grain_violations()`.

The investigation distinguishes redundant copies from conflicting records. The cleaner does not enforce that distinction: it unconditionally drops duplicate `(device_id, ts)` keys.

**Fixture:** append a duplicate of one real row with its EC value increased by 100.

**Observed result:**

- `grain_violations()` reported one conflicting key.
- The cleaner returned the same 15,935-row output size, discarding one payload.
- The audit approved the result.

This does not invalidate deduplication of the original sample, whose duplicates are identical. It does violate the declared conflict-handling policy.

**Correction direction:** deduplicate only identical payloads; stop or quarantine conflicting keys with both versions preserved.

### 5.3 High: the audit does not verify several claims implied by its labels

**Location:** [cleaning.py](../submission/fyta/cleaning.py), `audit()`, lines 99–180.

| In-memory test | Observed result | What it exposes |
|---|---|---|
| Call `clean()` with no detected frozen windows | Audit approves the retained frozen values | Rejection reconciliation cannot detect an omission shared by cleaning and its ledger |
| Move all eight dark-hour flags onto unrelated rows | Audit approves | The dark-hour audit reconciles counts, not keys |
| Replace all corrected SENS-07 temperatures with 25°C | Audit approves | Unit checks reconcile detector/configuration membership, not converted output |
| Supply an input needing no rejection records | Audit fails | The reason check wrongly requires at least one rejection |

The first mutation differs from the existing regression test. That test restores frozen values while retaining the rejection ledger, which the audit correctly rejects. Omitting both the remediation and its ledger entries still passes.

The unit audit also approved a mutation adding 10°C to SENS-07's corrected temperature. Both mutations stayed within broad sanity bounds.

The healthy-input failure comes from the condition combining `reason.notna().all()` with `len(rejections) > 0`. An empty rejection table is a legitimate success case.

**Correction direction:** independently verify the rules the gate promises to enforce; reconcile flags and rejections at their declared keys; validate conversion arithmetic; allow a healthy batch to contain no rejections.

A gate need not prove every conceivable property. It does need to prove the specific properties its output claims.

### 5.4 Medium: the claimed expected-slot check is incomplete

**Location:** [sensors.py](../submission/fyta/sensors.py), `check_grid()` and `device_coverage()`, lines 43–78.

`check_grid()` checks the modal interval. `device_coverage()` derives expected counts from each device's observed minimum and maximum timestamps.

**Reproductions:**

1. Moving one SENS-01 timestamp one minute off-grid still passed `check_grid()` and reported zero missing, zero surplus, and 100% completeness.
2. Removing the first day from the fixture reported 1,920 expected and 1,920 delivered readings, again 100% completeness.

The current 193-slot interior gap is correctly counted. The implementation does not account for every expected slot or detect missing observation-window boundaries.

**Correction direction:** declare the analysis/installation window separately from observed endpoints, construct the expected keys, and classify missing, duplicate, and off-grid observations explicitly. If the intended window is unknown, say that completeness covers only the observed span.

### 5.5 Medium: valid ISO-only input fails parsing

**Location:** [sensors.py](../submission/fyta/sensors.py), `parse_timestamps()`, lines 15–40.

The day-first evidence assertion runs even when the input has no slash-formatted dates.

**Fixture:** two valid ISO timestamps.

**Observed result:** `AssertionError: day-first is unproven on this input - parse is ambiguous`.

The mixed-format assessment input parses correctly. The failure demonstrates a guard that rejects healthy input outside this exact sample.

**Correction direction:** apply the slash-format ambiguity requirement only when that format is present, and distinguish a known source-format contract from format inference on a small batch.

### 5.6 Medium: unknown device mappings disappear from the feature table

**Location:** [features.py](../submission/fyta/features.py), `plant_features()`, especially the mapping merge at line 81.

The mapping uniqueness assertion protects against a fan-out, but the inner merge can silently lose unmatched devices.

**Fixture:** remove SENS-08 from the supplied mapping while retaining all sensor rows.

**Observed result:** the feature table contained five plants instead of six; 2,016 source readings had no representation. No mapping-coverage error was raised.

The original mapping covers all devices, so the shipped output is unaffected.

**Correction direction:** assert foreign-key coverage and join cardinality in both directions relevant to the contract, not only right-hand uniqueness.

### 5.7 Lower priority: publication guarantees are narrower than advertised

**Location:** [fyta_pipeline.py](../submission/fyta_pipeline.py), especially lines 200–206.

The script audits the cleaned frame and then writes CSVs directly to consumer-facing paths. It does not stage and atomically publish a consistent output set. The gate also uses Python `assert`, which disappears under optimized execution.

For a timeboxed assessment, this is a reasonable implementation limit if stated. It should not be described as a complete write-audit-publish mechanism.

## 6. Incorrect or overstated reasoning

### 6.1 A NULL-valued expected slot is not fabricated measurement data

**Location:** [observations.md](observations.md), lines 290–301.

The notes reject a dense grid because it would manufacture timestamps and say that a NULL row would be false. This is incorrect.

A row with an expected timestamp, `reading_received = false`, and NULL measurements asserts that a reading was expected but is unknown. It does not claim an instrument measured anything.

The distinctions are:

- **Raw readings:** preserve the records received.
- **Expected-slot table:** represent the schedule against which availability is assessed.
- **Imputed values:** estimates that require separate columns and method labels.

A derived dense feature table can contain explicit missing slots without modifying raw records or inventing measurements. A sparse table is also valid. Downstream use determines the choice.

The owner's question about representing missing rows with NULLs was reasonable. The recorded answer incorrectly treated it as a mistaken premise.

### 6.2 Absent data does not identify the failure mechanism

F7 and the decision register infer that a gap shorter than nominal buffer capacity was recoverable and therefore caused by synchronization failure rather than data loss.

Buffer capacity alone cannot establish that the sensor measured anything, remained powered, retained its buffer, or successfully exported the relevant records. The observed fact is missing data. The cause remains unresolved without device/transport telemetry.

A buffer estimate is useful context, not proof of recoverability.

### 6.3 Differentiation does not remove calibration dependence

**Location:** [signals.py](../submission/fyta/signals.py), lines 16–24, and the repeated Task 8 explanation.

The claim that rates remain comparable without confirmed calibration does not follow mathematically.

If `reported = a × true + b`, then `d(reported)/dt = a × d(true)/dt`. A derivative removes a constant offset but retains the gain. A nonlinear conversion also changes the derivative according to the local slope of its calibration curve.

FYTA's own calibration explanation describes substrate-, probe-length-, and sensor-dependent logistic curves. That supports caution rather than calibration-independent rates.

A dry-down statistic can be useful within a device under stable conditions. It should not be presented as eliminating the calibration problem.

Nor does a high observed drying slope alone prove physical impossibility: pot geometry, drainage, placement, watering cycles, and calibration remain relevant. The readings above 100% already establish invalid magnitudes; a slope statistic does not resolve the cause of the entire regime.

### 6.4 VWC, relative rank, and plant-available water are different quantities

VWC remains a volume fraction across substrates. Substrates differ in their calibration behavior and in the relationship between a given VWC and water available to the plant.

A trailing percentile expresses where a reading falls within that device's recent distribution. It does not establish that the same percentile means the same water stress in bark and potting soil, or after a change in watering behavior.

Using ranks as model inputs is reasonable. Claiming they establish physiological comparability is stronger than the evidence supports.

### 6.5 Shared environmental signals can support peer checks

**Location:** [sensors.py](../submission/fyta/sensors.py), lines 601–612 and F12; [assessment.md](assessment.md), lines 204–210.

The statement that highly shared environmental signals make fleet-deviation checks meaningless reverses the usual implication.

If a justified group of sensors shares an environment, its common signal can provide a reference for detecting a deviating sensor. The submission already uses this principle to investigate clocks and units.

The correct restriction is that peer groups require evidence: location, lighting exposure, sensor family, operating conditions, and calibration can differ. A heterogeneous fleet should not be treated as one reference population.

### 6.6 Probe disagreement is evidence to investigate, not proof of mapping error

Preserving the separate probes is a sound decision here. However, statements that same-pot probes must always be positively correlated, cannot move in opposite directions, or must exceed a particular correlation are too strong.

Probe depth, horizontal placement, lagged infiltration, drainage, root uptake, calibration, and defective readings can affect the observed relationship. The known SENS-06 freeze also complicates whole-window correlation.

The correct conclusion is that the observed disagreement makes unqualified averaging unsafe and motivates investigation. It does not establish the physical installation or mapping error by itself.

The rule file repeats some of these claims. A repository instruction is not scientific evidence; encoding an assumption as a rule makes it easier for later AI work to repeat it, not more likely to be true.

### 6.7 Plausible thresholds are not necessarily physical impossibility bounds

The `IMPOSSIBLE` registry describes soil temperature above 70°C as impossible because it would kill the plant, and PAR above 2,500 as impossible because it exceeds typical sunlight.

Those may be useful application-specific plausibility thresholds, but plant survival is not a physical upper bound on a temperature measurement, and typical sunlight is not an absolute limit on local illumination.

This does not change the current Fahrenheit diagnosis. It matters to the broader distinction between a hard physical constraint, a manufacturer's reliable measurement range, and a contextual plausibility policy.

## 7. Tasks 4, 5, and 6: integration and evidential limits

### 7.1 Task 4 contains useful association, not independent accuracy validation

The cleaned correlation between water-deficiency probability and sensor-derived dryness reproduces at **0.751588**.

The calculation uses:

- 35 joined photo/device rows.
- 33 non-null correlation pairs.
- 28 distinct photos.

Two-probe plants contribute repeated image predictions paired with different devices. This is valid as a declared photo/device analysis, but it is not 35 independent photographic observations. Confidence claims would need to account for dependence and the small number of plants.

The current discussion of uncertain image-model lineage is an improvement over calling the association inherently circular. Two modalities responding to the same latent state can corroborate each other; synthetic generation or shared inputs can also create the association. The dataset cannot settle the lineage question.

Other limitations:

- Each species is represented by one plant, so one substrate per species is weak evidence about label correctness.
- A static species label can still be checked against other evidence; lack of timestamps does not make all validation impossible.
- `image_predictions()` drops `model_version`, despite the importance assigned to model provenance.
- Proposed version/head-name contracts are recommendations, not implemented ingestion gates.
- Some child scores exceed their parent scores. Whether that violates the model's probability contract depends on vendor semantics; the taxonomy alone does not prove the scores are coherent marginal probabilities.

### 7.2 Task 5 is a sound sensor/metadata table, with deferred multi-source integration

`plant_features()` accepts cleaned sensor data and mapping data. It does not contain logs, image scores, or event features.

The scope is disclosed, so this is not an automatic failure. A narrow reading of the task asks only for a time-indexed plant table, which exists. A broader reading of “unified” expects integration of the available sources.

The explanation for postponement should be more precise. Sparse events can be represented safely through bounded backward as-of joins, event counts, time-since-event features, and explicit source-age columns. These designs do not require naive row multiplication or pretending that a photograph was captured at every sensor timestamp.

**Assessment:** completed sensor/metadata unification; deferred multi-source feature integration.

### 7.3 Task 6 still ignores the second probe

**Location:** [sources.py](../submission/fyta/sources.py), lines 137–144.

The code reads `ec_1` and estimates noise from `device_1`. It does not evaluate `ec_2`, even for plants carrying two probes.

**Fixture:** the first probe remained near baseline while the second increased by approximately 500 µS/cm after fertilization.

**Observed result:** `sensor_leg = "no rise"`.

A production decision about combining probes can remain unresolved. Silently checking only the first positional probe is not an adequate substitute for reporting that uncertainty.

### 7.4 Missing evidence is classified as a negative

**Fixture:** retain post-event readings but remove all pre-event observations from a triangulation window.

**Observed result:** `d_ec = NaN`, but `sensor_leg = "no rise"`.

That should be “not testable” or equivalent. There is no baseline from which to infer the absence of a rise.

The same distinction matters to watering-log analysis. Fresh checking found:

| Quantity | Count |
|---|---:|
| Watering logs | 34 |
| Logs with evaluable sensor windows | 33 |
| Probe/window trials | 45 |
| Positive probe trials | 3 |
| Distinct positive logs | 3 |
| Log without observations | `LOG-00030` |

The unobserved log sits inside the SENS-05 outage. It should not be counted as a failed sensor response. The three positive probes happen to correspond to three distinct logs in this sample, but `log_alignment()` accumulates probe-level results rather than implementing its documented any-probe-per-log rule.

### 7.5 The statistical and causal conclusions are too strong

Comparing a difference of 24-hour means with the standard deviation of individual 15-minute differences is a screening heuristic. It is not a calibrated uncertainty estimate for the mean difference. Serial dependence, window size, baseline coverage, other events, and response duration matter.

The post-event nutrient score is also a **level**, not a response. The code acknowledges this in comments but labels scores above its threshold as `responds` and combines that label into `corroborated`.

A pre-event deficiency image could be context for why a user fertilized. A high post-event score could reflect persistent symptoms. Neither alone proves a model response to fertilization.

The phrase “none lines up” also conflicts with the repotting screen, which reports one response among three tests. That response may be confounded by watering, but confounded evidence is not the same as no response.

**Supported conclusion:** these data and chosen windows do not establish the requested corroboration.

**Unsupported stronger conclusion:** the sources contain no relevant signal, could not be connected, or prove a specific generation process.

## 8. Optional signals

### 8.1 Dry-down is useful as an exploratory feature, with limits

The median-of-step-rates approach is compact and reduces the influence of positive watering jumps. Its output reproduces.

Besides the calibration issue, there is a freshness issue: the rolling window can emit a rate when the current moisture value is NULL.

Fresh checking found **105 such rows**:

- 45 on SENS-04.
- 48 on SENS-06.
- 12 on SENS-08.

For SENS-06, a rate remained present through 11:45 on the first day of the frozen interval, despite current moisture being rejected.

A trailing estimate can intentionally use earlier valid observations. It then needs an explicit interpretation and freshness/coverage indicator, rather than looking like a current measured drying rate.

The sample-count rolling window also spans more elapsed time around outages. The code acknowledges that simplification, which is appropriate, but consumers should not interpret it as a strict elapsed-time window.

### 8.2 The log lookup is appropriately small, but its ordinal is subjective

A lookup and simple volume extraction are sensible for fourteen phrases. A classifier would add little.

However, “bottom-watered” describes a method, not necessarily a larger quantity than “watered ~200ml.” The intensity mapping is a proposed ordinal, not a measured property. That distinction should remain visible.

The text also includes symptoms and conditions such as drooping leaves and dry topsoil. Saying volume and intensity are all the text encodes is too strong, even if extracting further fields was outside the timebox.

## 9. Production-design assessment

### 9.1 Good principles

The sketch correctly emphasizes:

- Per-device monitoring rather than fleet averages.
- Event time and late-arriving data.
- Immutable raw inputs and replayability.
- Quarantine reasons.
- A domain/device registry.
- Separate per-reading and window-based checks.
- Avoiding a large distributed processing stack solely because there are 100,000 devices.

The average-rate arithmetic is correct: **9.6 million readings/day and approximately 111 readings/second**.

### 9.2 Material omission: batching, object count, and request cost

**Location:** [PIPELINE_DESIGN.md](PIPELINE_DESIGN.md), lines 135–163.

The proposed direct IoT Core rule-to-S3 path does not specify batching or compaction, while the cost estimate emphasizes stored bytes.

AWS documents that the S3 action writes an MQTT message into an object. It does not automatically create efficiently batched Parquet. A static object key overwrites data; unique message keys preserve messages but can produce a tiny-object workload.

**Conditional calculation:** if one reading becomes one S3 object, the submission's 288 million monthly messages imply:

`288,000,000 / 1,000 × $0.005 = $1,440 per month`

That is PUT cost alone using AWS's cited standard US-East-1 example, before reads, transformations, serving, or monitoring. It already exceeds the stated $200–500 overall estimate.

Gateway batching or an ingestion buffer can change the economics substantially. The problem is not that the fleet necessarily costs $1,440 in PUTs; it is that the design omits the assumption that determines whether it does.

Sources:

- [AWS IoT S3 rule action](https://docs.aws.amazon.com/iot/latest/developerguide/s3-rule-action.html).
- [AWS S3 pricing](https://aws.amazon.com/s3/pricing/).
- [AWS US-East-1 request-cost example](https://docs.aws.amazon.com/solutions/latest/live-streaming-on-aws-with-amazon-s3/cost-example-1.html).

### 9.3 Device storage capacity does not establish an end-to-end lateness bound

Even if the deployed generation retains 320 readings at four per hour, that describes sensor retention, not the maximum time until cloud ingestion.

A phone or hub may retrieve readings and hold them for longer. Pipeline failures, retries, exports, and historical reprocessing can add delay. A watermark therefore needs an explicit arrival-time contract and a policy for data beyond that bound.

The hardware-generation qualification in the design document is useful, but it does not resolve this separate issue.

### 9.4 Hardware claims require careful scoping

FYTA's technical page distinguishes Beam generations and lists humidity for Sphere rather than Beam 1.0 or 2.0. The synthetic assessment includes humidity, so the exercise should be evaluated according to its provided schema without claiming that every field proves a particular physical product's implementation.

The brief already declares 15-minute reporting. That is the assessment cadence contract; ambiguity in marketing specifications does not invalidate it.

Source: [FYTA technical data](https://fyta.de/en/pages/technische-daten).

### 9.5 Average throughput is not the full capacity model

A low daily byte volume supports a simple processing engine. It does not determine burst size, object listing overhead, indexed serving cost, retained history, or concurrent query load.

The design names bursty uploads but does not size a burst scenario. The OSS and managed variants also introduce numerous services and unsupported operational-load estimates for a brief that asks for a sketch.

I would prefer one recommended path with explicit batching, lateness, replay, publication, and observability decisions over two elaborate stacks with precise-looking but incomplete cost estimates.

## 10. Communication, consistency, and maintainability

### 10.1 The one-page deliverable exists and meets the page limit

The PDF contains one A4 page and approximately 811 extracted words. This resolves the earlier missing-deliverable problem.

It is dense. The self-correction record is valuable, but it consumes substantial space while the main image-agreement result, triangulation outcome, feature-table scope, and architecture recommendation receive little or no space.

The brief asks for key findings, decisions, and next steps. Debugging history should support those, not displace them.

### 10.2 Current artifacts still contradict each other

| Artifact claim | Current evidence |
|---|---|
| Notebook: VWC 65–107 is possible and retained | Cleaner nulls values above 100; 49 such source readings exist |
| Notebook: SENS-03 drift is flagged in `qc_flags` | Only out-of-spec values are flagged; 702 of 1,056 rows in the declared June 11 onward interval have no flag |
| Notebook: FYTA already uses AWS because image paths use S3 | These are synthetic fixture paths; the design document correctly treats this as an inference |
| README: the run command writes the full run log | The entry point prints to stdout but does not itself capture `run.log` |
| Handoff: nothing remains undone | The submission itself names unresolved cases and deferred integration |

Historical notes can preserve previous beliefs if marked as historical. Submission-facing explanations should agree about the current behavior.

### 10.3 Strong prose sometimes exceeds the evidence

Examples include “must move together,” “not chemistry,” “the two were never connected,” and “all four types tested, none lines up.”

These are not merely style issues. Each turns a hypothesis or limited test result into a stronger claim.

The repeated insistence that averaging, interpolation, or dense grids are intrinsically dishonest also obscures the actual engineering rule: derived or estimated values can be legitimate when their purpose, assumptions, lineage, and uncertainty are explicit.

### 10.4 Code organization is reasonable; duplicated narrative is the larger maintenance risk

The module split is understandable and the dependency set is modest. This is not an abstraction-heavy framework.

An approximate AST decision-point count, including comprehensions, Boolean operators, and assertions, identified these hotspots:

| Function | Approximate complexity |
|---|---:|
| `log_alignment` | 24 |
| `clean` | 11 |
| `plant_features` | 10 |
| `audit` | 10 |
| `image_predictions` | 8 |
| `triangulate` | 7 |

These are review estimates, not a project-linter result. `log_alignment()` combines different event semantics and is the clearest complexity concern.

More consequential than function count is the repeated narrative across the script, notebook, write-up, observations, handoff, and findings strings. Several corrections reached one copy but not another.

## 11. Scorecard

These scores judge the submission against the timeboxed assessment, not a fully deployed production platform. Core data-quality work carries more weight than optional stretches.

| Area | Score | Rationale |
|---|---:|---|
| Ingestion and exploration | **8.5/10** | Strong orientation and useful figures; parser and grid guards have edge-case failures |
| Defect discovery and characterization | **8/10** | Finds the important failure classes; several causes are stated too confidently |
| Cleaning and validation | **6.5/10** | Current sample outputs reproduce, but reusable cleaning and audit claims have material gaps |
| Cross-source validation | **6.5/10** | Useful association and improved lineage caution; limited species validation and incomplete provenance handling |
| Per-plant feature table | **7/10** | Good grain and probe preservation; multi-source integration deferred and missingness justification flawed |
| Triangulation | **5.5/10** | Direction/timing fixes help, but second-probe handling, missing evidence, and response semantics remain weak |
| Production design | **5.5/10** | Sound general principles; batching/request costs, lateness bound, and sizing assumptions need revision |
| Communication and prioritization | **6.5/10** | Required PDF exists and corrections are disclosed, but contradictions and overstatements remain |
| **Overall** | **7/10** | **Interview-worthy, with reservations; not a strong pass yet** |

The optional dry-down and text tasks add some value, but should not compensate for unresolved integrity or reasoning issues in the core tasks.

## 12. Recommended correction order

### Priority 1: correct the central reasoning

- Explain that explicit NULL slots represent missingness, not fabricated measurements.
- Remove the claim that rates bypass calibration.
- Correct the shared-environment/peer-comparison conclusion.
- Treat mapping error, sensor drift, recoverability, and synthetic-generation mechanisms as hypotheses at the appropriate confidence level.
- Distinguish hard physical bounds from application plausibility thresholds.

### Priority 2: close the highest-risk integrity gaps

- Prevent legitimate constant channels from being nulled as frozen.
- Stop or quarantine conflicting duplicate keys.
- Reconcile dark-hour flags by key, not count.
- Verify conversions and promised remediation behavior independently.
- Accept healthy input with no rejection records.
- Validate mapping coverage and expected-slot membership.

### Priority 3: make cross-source outcomes honest

- Preserve “not testable” separately from a negative response.
- Report both probes or an explicit selection policy.
- Distinguish model-score levels from event responses.
- Report the feature table's current source scope without suggesting that sparse integration is inherently unsafe.
- Retain model provenance in normalized outputs.

### Priority 4: reconcile submission-facing artifacts

- Update the notebook's 65–107% and EC-drift statements.
- Remove unsupported claims about FYTA's deployed stack.
- Make run instructions accurate about log capture.
- Condense duplicated explanation and foreground findings, limitations, and next steps in the one-page write-up.

### Priority 5: simplify and repair the architecture sketch

- State batching and Parquet-compaction behavior.
- Account for object requests, not only stored bytes.
- Separate sensor retention from end-to-end lateness.
- Name one burst scenario and one late-data replay/publication policy.
- Prefer one justified recommendation to additional diagrams or optional services.

**Do not add more optional features or presentation assets before these corrections.**

## 13. Questions I would ask in the interview

1. What exactly distinguishes a missing expected slot, a rejected observation, and an imputed value?
2. Why does the Fahrenheit diagnosis require evidence about scale and offset rather than correlation alone?
3. How would the frozen-channel detector avoid deleting normal darkness or a quantized stable sensor value?
4. What should happen if two records have the same key but different payloads?
5. Which audit checks are independent of the transformation they validate, and which can share the same omission?
6. What does a within-device moisture percentile mean physically, and what does it not mean?
7. What would make an event window untestable instead of negative?
8. How would you assess both probes without hiding disagreement or arbitrarily selecting one?
9. How many S3 objects would the proposed architecture create, and where would batching occur?
10. What evidence would change your conclusion that an EC trend is sensor drift rather than a physical or synthetic effect?

The candidate's answers would matter more than the number of files or diagrams in the repository.

## 14. Final hiring judgment

There is enough strong work here to justify an interview. The defect discovery, preservation of raw evidence, declared grain, and reproducible outputs are meaningful positives.

The submission also shows the risk of accepting persuasive AI-generated explanations without challenging their premises. Some of the weakest claims have been repeated across several documents and even embedded in the repository rules, which can make subsequent reviews reinforce rather than question them.

I cannot infer the candidate's understanding from the chosen model or the repository alone. A candidate who can explain the limitations above, revise their conclusions, and identify the smallest useful corrections would leave a substantially stronger impression than one who defends the absolute claims as written.

**Final recommendation: technical interview, with focused scrutiny of reasoning, data-integrity guarantees, and the ability to distinguish uncertainty from a negative result. Overall: 7/10.**

## External references checked during this review

- [FYTA technical data](https://fyta.de/en/pages/technische-daten): generation-specific cadence, buffer wording, and channel availability.
- [FYTA moisture-calibration explanation](https://magazin.fyta.de/en/website-en/fyta-app-guide-en/why-soil-moisture-measurement-is-complex-fyta/): substrate/probe-dependent conversion and logistic calibration curves.
- [AWS IoT S3 rule action](https://docs.aws.amazon.com/iot/latest/developerguide/s3-rule-action.html): per-message object writes and overwrite behavior for static keys.
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/): storage and request pricing are separate cost components.
- [AWS US-East-1 S3 cost example](https://docs.aws.amazon.com/solutions/latest/live-streaming-on-aws-with-amazon-s3/cost-example-1.html): explicit $0.005 per 1,000 PUT/COPY/POST/LIST requests in the example.

External pages can change and do not identify which physical generation produced a synthetic assessment dataset. They were used to check the submission's public hardware and architecture claims, not to replace the brief's declared data contract.

---

## Reassessment after the correction pass

**Reviewed on 20 September 2026, after the owner applied changes in response to the original review.** This section supersedes the original review's status statements where they differ. The reassessment was read-only; the owner subsequently requested this report update.

**Updated verdict: still around 7/10. Do not submit this exact revision yet.** Several corrections work, but new execution and integrity regressions prevent a higher rating. The work remains worth discussing in an interview.

### Verification results

| Check | Current result |
|---|---:|
| Regression suite | 12 of 12 pass |
| Published CSVs versus fresh in-memory calculations | 11 of 11 match |
| Baseline audit | 19 of 19 pass |
| Cleaned sensor rows | 15,935 |
| Rejection records | 1,415 |
| Per-plant feature rows | 11,903 |
| PDF | One A4 page, approximately 783 words |
| Notebook | 50 cells; fresh-state data-cell execution fails at Task 6 |

Verification used the same read-only filesystem sandbox as the first review. Plot-saving cells were skipped, plotting/display imports were inert, and no outputs were regenerated. The skipped plotting cells do not create the variable missing at Task 6. Matching the CSVs verifies the current sample calculations; it does not establish the broader guarantees claimed by the audit.

### Corrections that work

- The overnight fixture retains all 52 legitimate zero-light readings.
- Healthy input with no rejections passes the audit.
- ISO-only timestamp input parses.
- The audit rejects replacement of SENS-07's converted temperatures with a constant 25°C.
- A missing device mapping raises an error rather than dropping the device.
- Triangulation consults both probes and can report an untestable window, subject to the defect below.
- Dry-down output includes an as-of timestamp.
- The notebook now states the 65–100% flag band and discloses incomplete EC-drift flagging.
- The entry point contains run-log capture; hand-made diagram assets have moved outside `out/`.
- The write-up acknowledges that differentiation retains calibration gain.

### R1. High: the notebook fails from a fresh state

The Task 6 cell calls `triangulate(cleaned, features, contextual, heads)`, but the cell creating `heads` has been removed. Fresh-state execution reaches code cell 39, using zero-based numbering, and raises:

```text
NameError: name 'heads' is not defined
```

Saved outputs remain, with no stored error. They therefore give a misleading impression of executability. The handoff still reports 52 cells; the current notebook contains 50.

Restore the image-prediction setup before its consumers and verify execution from a fresh kernel. Checking that image assets exist does not check the notebook's variable dependencies.

**Evidence:** [fyta_analysis.ipynb](../submission/fyta_analysis.ipynb), Task 6; [HANDOFF.md](HANDOFF.md), lines 43–55.

### R2. High: duplicate quarantine fails on real input and repeated conflicts

Three defects remain in the new branch:

1. **Wrong timestamp type.** The branch subtracts a timedelta from raw `timestamp` text. Adding one conflicting row to the real pipeline input raises `TypeError: unsupported operand type(s) for +: 'Timedelta' and 'str'`. The test helper masks this by assigning `raw["timestamp"] = raw["ts"]`, which the pipeline does not do.
2. **Wrong conflict grouping.** For one key with payloads `A, A, B, B`, where A and B disagree, the cleaner records zero quarantined rows, retains an arbitrary winner, and passes the audit. With datetime-normalized `A, A, B` test input, it quarantines B alone and retains A. An identical twin does not make a row's entire key group conflict-free.
3. **Missing payload evidence.** Even the successful two-row test writes ledger entries containing the same key, `channel = "(row)"`, and `raw_value = NaN`. The differing payload fields are absent. The original raw source remains intact, but the quarantine ledger does not preserve both payloads as claimed.

Detect conflict at the key-group level, quarantine all versions, and retain payloads or unambiguous source references. Fixtures must preserve the pipeline's raw/parsed timestamp distinction.

**Evidence:** [cleaning.py](../submission/fyta/cleaning.py), lines 51–65; [test_gates.py](../submission/test_gates.py), lines 115–121 and 151–176.

### R3. High: the revised audit accepts unexplained row loss

The new raw-column check compares only keys present in both frames. Removing all **2,016 SENS-01 rows**, without any rejection records, passes all 19 checks.

This is a regression: the previous full-frame comparison would have rejected the length mismatch. The revised check also rejects an output that only reverses row order, because it still compares the aligned frames positionally without guaranteeing matching order.

The audit needs both key accounting and value comparison:

- Account for each source key as retained, losslessly deduplicated, or quarantined.
- Compare retained payloads after explicit alignment by key.

Two earlier holes remain unchanged:

| Mutation | Result |
|---|---|
| Omit frozen-window detection and its ledger records | Approved |
| Move the eight light flags to unrelated rows, preserving their count | Approved |

The dark-hour check still compares counts rather than key sets. The write-up's claim that every flag matches a detector is therefore unsupported.

**Evidence:** [cleaning.py](../submission/fyta/cleaning.py), lines 148–164 and 208–220.

### R4. Medium: an unavailable first probe hides a valid second probe

The code allows a probe score of `NaN` into `sigmas` because it checks the number of rows in each window rather than the number of valid observations.

A fixture with an unavailable probe-1 baseline and a valid probe-2 rise returned:

```text
leg_detail:  SENS-01 +nan, SENS-02 +8.84
probe_leg:   SENS-01
sensor_leg:  not testable
```

The maximum-selection step retains the first invalid result and misses the second probe's rise. The existing test blanks both probes, so it does not cover this combination.

Establish validity for each probe before selecting a result. Keep per-probe outcomes so a missing baseline, negative result, and positive response remain distinguishable.

**Evidence:** [sources.py](../submission/fyta/sources.py), lines 148–163.

### R5. Important: report claims remain inconsistent with the fixes

- The corrected dry-down docstring says calibration gain survives differentiation. The entry point, current run log, and notebook still claim the rate works across the fleet without confirmed calibration.
- The observations record calls the shared-environment argument backwards. The correlation docstring still calls peer deviations meaningless.
- The write-up says all defects are fixed and both conflicting payloads are now quarantined. R2 and R3 contradict those claims.
- The write-up states that triangulation fails for reasons other than a weak effect. The chosen screening rules do not establish that distinction.
- The off-grid timestamp check still passes the earlier one-minute-shift fixture. Documenting observed-span coverage is useful, but does not fix grid membership.

Use a qualified conclusion for cross-source work: the selected windows did not establish corroboration; sparse images, uncertain event timing, and limited statistical power constrain the result.

**Evidence:** [fyta_pipeline.py](../submission/fyta_pipeline.py), lines 443–448; [sensors.py](../submission/fyta/sensors.py), lines 638–649; [WRITEUP.md](../submission/WRITEUP.md), lines 37–39, 54–70, and 82–85.

### R6. Medium: the batching calculation needs one consistent policy

The updated design adds request costs and an ingestion buffer, which is an improvement. It then recommends hourly objects but describes a reduction to the object count for daily batching.

| Policy for 100,000 devices, 30 days | Objects/month | PUT cost at the document's stated rate |
|---|---:|---:|
| One object per device/hour | 72 million | $360 |
| One object per device/day | 3 million | $15 |

Hourly objects contain only four readings at the stated cadence, so this is still a small-object design. Combining the document's hourly PUT and IoT Core estimates gives approximately **$533–792/month before other services**, inconsistent with its $200–500 envelope. Daily batching also needs reconciliation with the stated dashboard latency.

Choose a batching policy, state its latency and object-size consequences, and recalculate the total. Sensor retention still does not bound end-to-end ingestion delay.

**Evidence:** [PIPELINE_DESIGN.md](PIPELINE_DESIGN.md), lines 135–185.

### Status against the original review

| Concern | Current status |
|---|---|
| Valid nighttime light deleted | Fixed for the demonstrated case |
| ISO-only parsing | Fixed |
| Healthy batch with no rejections | Fixed |
| Unit-conversion arithmetic audit | Fixed for tested mutations |
| Unmapped devices disappear | Fixed |
| Conflicting duplicate handling | Attempted; still incorrect |
| Independent frozen-remediation check | Still open |
| Light-flag reconciliation by key | Still open |
| Both probes in triangulation | Improved; invalid-score selection remains |
| Missing evidence versus negative | Improved; incomplete |
| Full expected-grid validation | Deferred; observed-span limit documented |
| Calibration-rate reasoning | Corrected in some places, contradicted elsewhere |
| Fresh-state notebook execution | New regression |
| Audit accounting for missing rows | New regression |

**Immediate priorities:** repair notebook execution, correct group-level quarantine, account for missing keys in the audit, exclude invalid probe results, and reconcile the submission's claims. No additional features or architecture diagrams are needed.

---

## Prose and presentation recommendations

The owner asked for this addition:

> also there is too much prose, some look very AI generated, please suggest in you report i.e observations.md along with the above status

### Editorial assessment

There is too much repeated explanation in the submission. Several passages read like a polished AI essay rather than an engineer reporting an investigation. The recurring problems are rhetorical headings, repeated contrasts, sweeping rules, all-caps emphasis, and paragraphs that restate why the author is careful instead of showing the result.

This is a judgment about the writing, **not proof of AI authorship**. Punctuation, tables, or a particular phrase cannot establish which model wrote a passage. FYTA permits AI; there is no reason to conceal its use or optimize for an AI detector. The goal is shorter, more accurate writing that the candidate understands and can defend.

Keep the reasoning the brief asks for. Cut repetition, self-praise, and generic lessons. Technical honesty takes priority over sounding concise: preserve material uncertainty, unresolved failures, and scope limits.

### Specific passages to shorten or replace

The replacements below describe the reviewed state. They must not be changed to success claims until the corresponding behavior is verified.

| Current wording or pattern | Problem | Suggested replacement |
|---|---|---|
| "A sensor stopped measuring, and nothing says so." | Dramatic heading; the whole sensor did not stop | "SENS-06 moisture stayed at 25.01 for 1,344 readings while its other channels varied. I rejected that moisture interval." |
| "A two-day gap that leaves no trace." | The timestamps contain evidence of the gap | "SENS-05 missed 193 slots between observed readings, despite no empty source cells." |
| "Neither is visible in the values" and "Fahrenheit only from jittering 1.8× faster" | Overstates the uniqueness of the method; range and level also provide evidence | "SENS-07 temperature scale and offset fit Fahrenheit conversion. Aligning its light series supports a two-hour relative clock offset." |
| "One join is safe, the next is not. The trap is that the first join works." | Repeated setup and reveal instead of naming the grain | "Joining logs to the device map on plant ID expands 49 rows to 67 because two plants have two devices." |
| "A detector with no fix is a warning nobody acts on; a fix with no detector rots." | Generic aphorism; detection without automatic remediation can be intentional | "I check unit conversion against the raw values. The light-flag audit still needs key-level reconciliation." |
| "Never average the two sensors on one pot" and "the disagreement is the only reason to fit two probes" | Universal claim, repeated several times, with an unsupported purpose assigned to the probes | "I retained both probe values because their disagreement and physical setup are unresolved." |
| "An expected-but-absent row is honest; an interpolated one is not." | Moral language replaces the technical distinction; labelled estimates can be legitimate | "I left the gap uninterpolated. An expected-slot table with NULL measurements would also be valid." |
| "Two rows on one key were resolved by coin-flip." | `keep-first` is arbitrary but not random; metaphor obscures behavior | "The old cleaner kept the first conflicting payload. The replacement quarantine path still needs correction." |
| "All are fixed, each with a test that fails if the fix is undone." | Contradicted by the current reassessment | "Twelve regression tests pass. Fresh-state notebook execution and conflict handling still need correction." |
| "Triangulation does not work, and not because the effect is weak." | A rhetorical reversal asserts more than the test establishes | "The selected windows did not establish corroboration for the five fertilization logs." |
| "THE RATE IS COMPARABLE WHERE THE LEVEL IS NOT." | Both emphatic and incorrect | "I use dry-down as a within-probe exploratory feature; calibration still affects its scale." |
| "Managed wins, and it is not close" | Sounds conclusive despite unresolved cost and operational assumptions | "I would start with managed ingestion, subject to a consistent batching policy and a revised cost estimate." |

The repeated "never average" explanation appears under findings, decisions, and "What I would never ship" in the one-page write-up. One explanation is enough. Spend the recovered space on the feature-table scope or a limitation that affects interpretation.

### What to cut from the one-page write-up

1. Merge "Three decisions I would defend" and "What I would never ship" into a short treatment paragraph. They repeat the same decisions.
2. Reduce the debugging autobiography under "Where I was wrong" to one concrete example or a short verification/limitations note. Keep the full history in this internal review, not in the main submission.
3. Remove generic statements about what good engineers do. The findings and tests should demonstrate judgment.
4. Replace dramatic findings headings with the device, defect, and measured extent.
5. Remove unsupported universal claims. Prefer "I retained both probes in this sample" to "Never average probes."
6. Keep the image correlation, the lack of established fertilization corroboration, and the fact that the feature table excludes logs and images. These answer required tasks and deserve space more than repeated philosophy.
7. State known limitations without claiming that every omission is the only principled design choice.

The current PDF is one page because the layout is dense. As an **editorial target, not a new FYTA requirement**, aim for roughly **400–500 words** at a readable font size. Do not keep shrinking margins and type to fit explanations that repeat.

### Suggested one-page structure

Use plain headings and this approximate space budget:

| Section | Include | Suggested length |
|---|---|---:|
| Scope | Four sources, eight devices, analysis window, reproducibility entry point | 30–40 words |
| Findings | Frozen moisture, clock/unit mismatch, missing slots, duplicate/join risks; unresolved drift/probe setup | 130–160 words |
| Treatment and outputs | Raw preservation, corrections/rejections, flagging policy, sensor/metadata feature-table scope | 90–110 words |
| Cross-source result | Water-deficiency association, limited independence, no established fertilization corroboration | 60–80 words |
| Limitations and next steps | Remaining defects or deferred checks, domain questions, one production recommendation | 90–110 words |

These are editing guides, not a template requiring every section to have the same rhythm. Do not claim remaining defects are resolved merely to fit a cleaner ending. If the candidate only supplies the script as the runnable artifact, the packaging and instructions should say so rather than presenting a broken notebook as verified.

### Where detailed reasoning should live

| Artifact | Recommended role | Reduce or avoid |
|---|---|---|
| `WRITEUP.md` / PDF | Hiring-review summary of findings, decisions, outcomes, and limits | Long correction history; repeated safety slogans; generic data-engineering lessons |
| Notebook | Evidence beside the interpretation it supports | Paragraphs explaining the task-numbering system; repeated domain lectures; a second architecture essay |
| `fyta_pipeline.py` / `run.log` | Counts, audit results, output locations, and brief caveats | Hundreds of lines of duplicated narrative embedded in `print()` calls |
| Python comments/docstrings | Input/output contracts, units, edge cases, and non-obvious decisions | Full review history and long defenses of simple loops; claims already explained in the report |
| `PIPELINE_DESIGN.md` | One recommended flow, explicit assumptions, failure handling, and cost arithmetic | Two extensive vendor inventories; repeated claims about how small the data is; unsupported FTE precision |
| `observations.md`, `HANDOFF.md`, review reports | Internal history and detailed review evidence | Treating historical claims as current conclusions or expecting the hiring reviewer to read all of them |

Link to one authoritative explanation rather than copying it. Keep the correction history, but label it as history. Do not delete requested documentation or comments merely to reduce a line count; this section recommends a separate, authorized editorial pass.

### A better paragraph style

Prefer a short chain of evidence, action, and limit. For example:

> SENS-06 moisture remained at 25.01 for 1,344 readings while temperature, EC, light, and humidity varied. I nulled the affected moisture values and retained the raw readings and rejection reasons. The data supports a failed moisture channel, but does not identify whether the device or an upstream process caused the freeze.

That paragraph gives the reviewer a measurement, a decision, and a limit. It does not need a slogan about trustworthy data or an explanation of why the insight matters to every pipeline.

Use first person for decisions the candidate understands and accepts. Avoid claiming personal measurements or checks the candidate cannot explain. Brief disclosure of AI assistance is compatible with the brief; claims about validation must still match the work performed.

### Final editorial check

- Each paragraph should add a result, a decision, a reason, or a material limitation.
- Keep the same decision in one main location; use links elsewhere.
- Match every success claim to a current check, not a comment or saved notebook output.
- Replace "all," "only," "never," and "cannot" when the evidence supports a narrower statement.
- Use emphasis sparingly. Capital letters and bold text cannot strengthen weak evidence.
- Read the write-up aloud. Remove sentences that sound like a general essay rather than an answer about these eight devices.
- Preserve uncertainty where it affects the conclusion. Concision must not turn an untestable result into a negative.

**Editorial priority:** shorten the submission-facing documents after correcting the execution and integrity defects. More polished prose will not compensate for those defects. The overall reassessment remains around **7/10**, with both technical verification and a focused editorial pass still needed before submission.
