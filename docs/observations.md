# Observations

Everything noticed while working on this dataset, written up for the **report**.

This merges what were two files — my consolidated observations, and the running
record of questions asked during the work. Nearly every method lesson traced
back to one of those questions, so the lessons now carry their questions with
them.

**Where each thing lives:**

| File | Holds |
|---|---|
| `DATA.md` | what the data actually **is** |
| `decision_register.md` | choices waiting on a **conversation** (D1–D12) |
| **this file** | findings · method · mistakes · open items |

Machine-readable versions: `submission/out/task2_findings.csv`,
`task2_detection_coverage.csv`, `qc_rejections.csv`, `cleaned_sensor.csv`.

---

# Part 1 — The findings

13 findings. Full detail is in `task2_findings.csv`.

| # | Finding | Device | Severity | Class |
|---|---|---|---|---|
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
|---|---|
| **Grain ambiguity** | What is "the plant's moisture"? You must pick an aggregation, and the reflex answer — average them — produces a number describing *neither* pot |
| **Averaging hides faults** | A stuck sensor at 25 averaged with a healthy one at 45 gives a plausible 35. The pipeline hides a hardware failure |
| **User-facing contradiction** | If they disagree, which number does the app show? |

### What this dataset shows

| | Two probes in one pot (*expected*) | UP-1001 / UP-1003 (*actual*) |
|---|---|---|
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
|---|---|
| **Plant species** | One substrate per species ✅ — but static, so it can never be checked against a date (F13) |
| **Contextual logs** | One `log_type` per phrase ✅ (14 phrases) — but unrelated to the sensor (F11) |
| **Image predictions** | Internally consistent ✅ — agrees with the sensors on water at r = 0.75, **and that agreement is circular**. Independent heads never fire |
| **Sensor data** | The reference. Its own defects are Tasks 1–3 |

### Why the image model's agreement is not a pass

`Water deficiency` correlates with dryness at **+0.75** and `Water excess` at
**−0.75** — mirror images, with both parent classes between them. That is a
consistent taxonomy, and also a **single-factor model**.

**If the model's dominant signal is the same quantity the sensor measures,
agreement is a restatement, not a confirmation.** Two instruments reading one
quantity is not two measurements.

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

---

## Task 5 — one table, and the two decisions inside it

Grain is `(user_plant_id, ts_aligned)`, declared **and asserted** — 11,903 rows,
0 duplicate keys.

| Plant | Rows | Probes | Longest gap |
|---|---|---|---|
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
|---|---|---|
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
|---|---|---|
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
|---|---|
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
|---|---|---|
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
|---|---|
| **F9** joins multiply rows | yes, directly |
| **F10** sensors do not correlate | yes, that *is* the finding |
| Task 5, the per-plant table | yes, blocked by it |

And the five most serious findings are on plants with **one** sensor:

| Finding | Device | Plant | Sensors there |
|---|---|---|---|
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
|---|---|---|
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
|---|---|---|
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

---

# Part 3 — What went wrong, and what caught it

An honest record. Most of these were caught by a mechanism, not by care.

| What | Caught by | The lesson |
|---|---|---|
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
| The sensor count read as 6, not 8 | **Your question** | `DATA.md` §4 mixed up two different things |
| Claimed light at night is impossible | **Your correction** — a person can switch a lamp on | The right test is duration, not time of day. See §2.9 |
| A first fix flagged 11 legitimate SENS-07 readings | The audit | A time-of-day check on a misaligned timeline produces nonsense |
| The hierarchy parser named a parent the model never scores | **Running it** — `KeyError: 'nutrient-related issue'` | A taxonomy chain contains groups, not only classes. `chain[-1]` is not the parent; the last *known class* is |
| A "delete the duplicate line" edit added two instead | Reading the result instead of assuming | The edit tool reported success. It matched, and matched again |
| The notebook kept the old 3-argument call after a signature change | nbconvert **aborting** — which then left stale outputs behind, so the first check *looked* clean | Same class as the deleted-function bug above. Nothing in the notebook is compiled against the module |
| Claimed the context compaction had worked | **Your screenshot** — the counter was unchanged | I asserted a mechanism I had not verified. It is *"report a number you have not seen the output for"*, applied to a claim about my own tooling |
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
|---|---|---|---|
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
