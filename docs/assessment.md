# FYTA Data Engineer — Assessment

> **Provenance.** Merged from `assessment details.txt` (task brief) and
> `assessment.txt` (message-thread export) on 2026-09-16. **Those two `.txt`
> sources have since been removed from the repository, so this file is now the
> canonical copy** — the `Source:` attributions below are historical.
>
> **Merged 2026-09-20.** `DATA.md` is now Part 3 of this file; Parts 1–2 (the
> brief and the thread) are unchanged.
>
> Both bodies are reproduced verbatim, including original typos, inconsistent
> capitalisation and emoji. The only edits are presentational: redundant `**`
> inside headings removed, bare-table rows given header rows so they render, and
> bare URLs turned into links. The second source was a UI export and contains
> profile/timestamp chrome, reproduced as-is.

## At a glance

| | |
| :--- | :--- |
| **Role** | Data Engineer |
| **Company** | FYTA |
| **Contact** | Gregor Herdmann, CTO — gregor@fyta.de |
| **Timebox** | ~2–4 hours (brief) · *"not more than about 3 hours"* (email) |
| **Deadline** | Monday, 21 September 2026, end of day |
| **Submit to** | gregor@fyta.de |
| **Deliverable** | *Brief:* runnable code **+** ~1-page write-up or Loom/Zoom. *Email:* write-up only — *"You don't need to send anything else."* |
| **Next step** | ~1–1.5 hour interview, ideally in the Berlin office |

> ⚠️ The two sources disagree on what to submit. Safest reading: send code **and**
> the write-up.

---

# Part 1 — Task brief

*Source: `assessment details.txt`*

## FYTA Data Engineer - Test

Thanks for taking the time. This task is designed to be **realistic**: it looks like a slice of the work you'd actually do at FYTA. We care far more about how you *think* than about a polished, "finished" result.

### A few ground rules first

**Timebox: ~2-4 hours.** Please don't over-invest — we'd rather see sharp judgment on the important things than a perfect solution. If you run out of time, tell us in your write-up what you'd have done next.

**Use any tools you like — including AI (ChatGPT, Copilot, Claude, whatever).** We use these tools every day and expect you to. We're evaluating *your* judgment on top of them: what you choose to do, what you notice, and what you'd never ship. Using AI well is a plus, not something to hide.

**The dataset is synthetic** (no real customer data), but it's built to behave like our real sensor fleet, quirks and all.

### Context

FYTA runs tens of thousands of soil/environment sensors in real homes, gardens and professional sites. Each sensor reports every 15 minutes. This raw data is the foundation everything else stands on — our calibration and our ML models are only as good as the pipeline that cleans and normalizes it. Real-world sensor data is messy: substrates differ, sensors drift, users mislabel things, and readings drop out.

### Data Sets

~16,000 readings from 8 devices, and 6 user plants respectively,  over 3 weeks (including image and user input data).

#### fyta_sensor_sample.csv

| **Column** | **Meaning** |
| :--- | :--- |
| device_id | Sensor identifier |
| timestamp | Local reading time |
| substrate_label | Substrate the *user* selected in the app (e.g. potting_soil, coco_coir, orchid_bark) |
| soil_moisture_vwc | Volumetric water content, % (typically ~0–60% in real substrates) |
| soil_temp_c | Soil temperature, °C |
| ec_us_cm | Electrical conductivity / salinity, µS/cm |
| light_par | Light intensity (PAR) |
| air_humidity_pct | Relative air humidity, % |

#### fyta_contextual.csv

| **Column** | **Meaning** |
| :--- | :--- |
| log_id | User event log identifier |
| user_plant_id | user plant identifier |
| log_type | unique logs |
| text | string |
| created_at | datetime |

#### fyta_images.csv

| **Column** | **Meaning** |
| :--- | :--- |
| image_id | User plant image identifier |
| user_plant_id | user plant identifier |
| captured_at | datetime |
| image_path | test url cloud location |
| prediction | json |

#### user_plant_device_map.csv

*(no column list provided in the source)*

### Your task

1. **Ingest & explore.** Load the data and get oriented. Show us how you'd first look at it.
2. **Data quality — the core of this task.** Find and characterize the problems in this dataset. There are several, and they're of different kinds. For each: what is it, how did you detect it, how serious is it, and — importantly — **is it a sensor/data problem or a real physical signal?** (That distinction is most of the job.) Where you genuinely can't tell from the data alone, say what you'd measure or which domain expert you'd ask.
3. **Cleaning & normalization.** Implement a first pass at turning this raw data into something a modelling team could trust. You don't need to solve everything — be explicit about what you handle, what you deliberately leave, and why. Naïvely deleting or averaging away problems is usually the wrong call; tell us your reasoning.
4. **Label validation / weak supervision / Cross validation.** Does the image model's prediction agree with what the sensors say? Do labels agree Cross plant species, contextual logs, image predictions and sensor data
5. **Unified per-plant feature table:** Build a single time-indexed table per user_ plant
6. **Can a feature triangulation occur?** For example a log type fertilizing log should produce a rise in ec_us_cm data and the image prediction return "Nutrient deficiency"
7. **Pipeline design (sketch, don't build).** In prose or a diagram: how would you productionize this as an ingestion + quality pipeline for 100,000+ devices reporting every 15 minutes? What would you monitor, where would bad data get caught, and how would you make the checks maintainable as new substrates and sensors appear?
8.  **(Optional stretch, only if you have time.)** Derive one simple, useful signal or anomaly flag from the cleaned data and briefly justify it.
9. **Optional text characterization stretch, only if you have time**: Classification of logged text to structured signals?

### What to submit

**Your code** — a runnable notebook or script (Python preferred, but your call). It doesn't need to be production-perfect; it needs to run and be readable.

**A short write-up or Loom/Zoom recording (max ~1 page)** — your key findings, the decisions you made, and what you'd do next with more time. Walk us through your thinking.

**Please submit your results by Monday, Sept 21, EOD via email to gregor@fyta.de.**

### How we evaluate (so it's transparent)

We score every candidate on the same five dimensions:

**Judgment & data-quality thinking** — do you catch the real issues and tell artefacts from genuine signal?

**Correctness & rigor** — does your cleaning hold up

**Reasoning & communication** — is your write-up and Loom clear, honest about limits, and well-prioritized?

We are explicitly **not** scoring you on finishing everything or on using (or avoiding) AI. Thoughtful and unfinished beats polished and shallow.

Questions? Sent an email to gregor@fyta.de. Have fun with it — this is genuinely the kind of problem we spend our days on. 🌱

---

# Part 2 — Correspondence

*Source: `assessment.txt` — message-thread export. Profile and timestamp lines are UI chrome, reproduced as-is.*

## Message 1

Hi Sagar,

Thank you for applying to FYTA – and for your patience. We received an overwhelming number of applications, which is why it took us longer than we would have liked to get back to you.

We'd love to get to know you in a short 15-minute call – a first conversation about you, about us, and about the role. You can pick a time that works for you here:
<https://calendly.com/gregor-fyta/15min>

Looking forward to speaking with you.

Best regards,
Gregor Herdmann
CTO at FYTA

---

*Tuesday*
*View Gregor’s profileGregor Herdmann*
*Gregor Herdmann  (He/Him)  10:57 PM*

👏
👍
😊

---

## Message 2

Hi Sagar,

Thank you for our patience and our recent conversation - I really enjoyed getting to know you.

We're happy to let you know that we would like to continue the interview process with you.

We were fortunate to have a lot of strong people apply, and the second-round group is still fairly large. To be fair to everyone and to keep our decision grounded in the actual work, we've decided to change the process from what I might have mentioned to you on the call and to ask all candidates to complete a short, practical task instead of a call with our data analyst.

It's a realistic, time boxed exercise based on the kind of data we work with every day — please don't spend more than about 3 hours on it. You're welcome to use any tools you like, including AI. All the details, data, and instructions are here:

👉 [FYTA Test instructions](https://fyta-io.notion.site/FYTA-Data-Engineer-Test-3dc0ebd61ce88040a780df2f76d0aa84)

What we'd like back from you: a short write-up (1 page) or alternatively a brief Loom/Zoom recording, in which you share your key findings, the decisions you made, and what you'd do next with more time — in other words, walk us through your thinking. You don't need to send anything else.

Please send your results via email to me (gregor@fyta.de) by end of day on Monday, 21 September 2026.

What happens next:
Once we've reviewed your submission and based on the results, we'll select candidates for a ~1-1,5 hour interview (ideally in our office in Berlin) to talk through your work and get to know each other properly. We intend to then make our final decision based on that round of conversations.

If anything is unclear or you run into any trouble, please reach out via email (gregor@fyta.de).

Looking forward to seeing what you come up with!

Best regards,
Gregor Herdmann
CTO at FYTA

---

# Part 3 — What this data actually is

**Read this before writing a line of code against `data/`.**

A profiling script tells you a column is `float64` with range `-5.43 … 107.12`.
It cannot tell you that `-5.43` is a failed sensor reading rather than a dry pot,
and it cannot tell you that `107.12` is not "a bit high" but outside the range
the instrument is specified to measure at all. Those are the two facts that
decide what you do next, and **neither is in the CSV.**

This document records what the data *is*: how a reading is produced, what each
field means, how the tables relate, and where the meaning runs out.

Provenance of every claim is tagged:

| Tag | Meaning |
| :--- | :--- |
| **[D]** | From FYTA's published documentation — citable, but verify against the actual device generation |
| **[M]** | **Measured** from this sample — reproducible from `data/` |
| **[I]** | **Inferred** — reasoning from [D] + [M], not stated by either |

---

## 0. Plain-language primer

Skip this if you already work with sensors. Otherwise read it first — the rest
of the document assumes these words.

### The sensor in one paragraph

FYTA's sensor is a plastic stake you push into a plant pot. Two metal prongs go
into the soil; the electronics sit in the body above it. Every 15 minutes it
takes five readings and sends them to your phone over Bluetooth, or to a hub
over Wi-Fi. It is measuring the soil it is stuck into, at one spot, roughly a
third of the way up from the bottom of the pot.

### Why "soil moisture" is harder than it sounds

The prongs **cannot see water.** Nobody has a cheap sensor that can. What they
can do is measure how strongly the soil reacts to an electric field — a property
called **dielectric permittivity**, which just means *"how much does this stuff
respond to electricity"*. Water responds about 80× more strongly than air, so the
wetter the soil, the stronger the response.

That strength then has to be **converted** into a water percentage, and the
conversion depends on what the soil is made of. This is the single most important
idea in this document, so here is the analogy:

> **Think of a car's fuel gauge.** The gauge doesn't see petrol. It measures a
> float position, then converts that into "full" or "empty" using the known shape
> of the tank. Put that same gauge in a differently-shaped tank and it will read
> wrong — while still working perfectly.
>
> The soil sensor is the same. Same prong, same electronics, same electric field.
> Different growing medium (bark, coconut fibre, potting compost) → different
> conversion → **different number for the same actual wetness.**

So when this document says VWC is *substrate-dependent*, it means: **you cannot
compare a moisture number from a bark pot with one from a compost pot.** They are
different currencies. Neither is wrong; they are just not the same unit.

### Glossary

| Term | What it actually means |
| :--- | :--- |
| **VWC** — Volumetric Water Content | The share of the pot's *volume* that is water. Fill a 1-litre pot; if 0.3 litres of it is water, that is 30 % VWC. Volume, not weight. |
| **EC** — Electrical Conductivity | How well the soil carries electricity. Dissolved fertiliser salts make water conductive, so EC ≈ "how much plant food is in there". |
| **PAR** | The part of light plants can actually use to grow — roughly the light we can see. Measured as light particles hitting a square metre each second. **Not the same as brightness:** a bright green lamp can be almost useless to a plant. |
| **RH** — Relative Humidity | How full the air is of water vapour. 100 % means it cannot hold any more — that is when you get fog, or condensation on a window. |
| **substrate** | The stuff in the pot. In this data: `potting_soil`, `coco_coir` (coconut fibre), `orchid_bark` (chunky bark chips). |
| **calibration** | Fitting a measuring device to the thing it is measuring, so its numbers mean something. |
| **grain** | *What one row represents.* If a table's grain is `device + timestamp`, then one row = one reading, one device, one moment — and no two rows may share that pair. |
| **primary key** | The column(s) that make a row unique. |
| **null** | An empty cell. Means *"we don't know"*. **Never** means zero. |
| **fan-out** | A join that copies your rows because the key you joined on appears more than once in the other table. One log becomes two. Silent, and the results still look plausible. |
| **idempotent** | Running it twice gives the same result as running it once. Essential for anything that might be retried. |
| **correlation** | A number from −1 to +1 describing whether two things move together. See below. |
| **out of spec** | Outside the range the manufacturer says the device measures *reliably*. Not the same as "unusual". |

### How to read a correlation

Used in §2. It is just a measure of "do these two move together?"

| Value | Means |
| :--- | :--- |
| **+1.0** | Move together perfectly |
| **+0.9** | Very strongly linked — for practical purposes the same signal |
| **0** | No relationship at all |
| **−1.0** | Move in perfect opposition — one up, the other down |

---

## 1. How a reading gets from the soil to this CSV

A number in `fyta_sensor_sample.csv` is the end of a long chain. Every link can
introduce error, and knowing where they are is what makes cleaning possible.

```
  The soil in the pot
        │   wetter soil reacts more strongly to electricity
        ▼
  Two metal prongs  ──►  measure that electrical response        [D]
        │
        ▼
  The device's firmware converts that response into a
  water percentage, using a table for the chosen substrate:
        │
        │   response ──► [ substrate-specific conversion ] ──► VWC %
        ▼
  Separately, from the body above the soil:
  EC, light, air temperature and humidity                        [I]
        │
        ▼
  Bluetooth Low Energy (BLE 5.0)  ──►  phone app
        │                    or        Wi-Fi / LTE hub           [D]
        ▼
  Cloud ingestion  ──►  these CSV exports
```

Three consequences that govern everything downstream:

1. **VWC is not a water measurement.** It is a conversion from an electrical
   reading, and that conversion depends on the substrate. The same physical
   wetness produces different VWC numbers in bark, coconut fibre and compost. **[D]**
2. **The sensor measures a point, not a pot.** The prongs sit in the lower third,
   where water collects. **[D]** It is not "how much water the plant has".
3. **A missing row and a failed reading are different things.** Neither shows up
   as an empty cell in this dataset — see §7.

---

## 2. What each channel measures

The five readings, in plain terms first, then the precise version.

### `soil_moisture_vwc` — how wet the soil is

The device sends a signal into the soil and sees how strongly the soil responds;
wetter soil responds more. That response is converted to a percentage using a
table for the chosen substrate. **[D]**

Because it is a *conversion*, it inherits the conversion's assumptions — see the
fuel-gauge analogy in §0. **Specified range 0–65 %, accuracy ±5 %** **[D]**.
Values here run **−5.43 to 107.12** **[M]** — both ends impossible, see §8.

### `soil_temp_c` — soil temperature

A temperature sensor on the prongs. It also feeds into the corrections applied to
the other readings. **Specified ambient range −5 to 50 °C** **[D]**. Values here
reach **78** **[M]** — see §8.

### `ec_us_cm` — how much plant food is in the soil

Dissolved fertiliser salts let water carry electricity, so the device passes a
tiny current between the same two prongs and measures how easily it flows. More
salts = easier = higher number. It is the closest thing to "how much food is in
the soil". **[D]**

**Because it uses the same prongs as the moisture reading, the two are linked.**
Wet soil makes better electrical contact and reads higher; as soil dries, salts
concentrate and that *also* reads higher. So EC cannot be read on its own — you
need to know the moisture at the same moment. **[I]**

Note the unit: FYTA publishes EC in **mS/cm**; this column is **µS/cm**, which is
1000× smaller. **[D]** So 700 µS/cm = 0.7 mS/cm.

### `light_par` — how much usable light the plant gets

A light sensor in the body. It measures only the part of light plants can use
(wavelengths 400–700 nm) — not overall brightness. **Specified up to 2000,
±0.5 %** **[D]**.

Zero at night is *correct*, not missing. Indoor windowsills rarely exceed ~600,
which is where this data sits — except for a handful of night-time spikes that
cannot be real, since PAR must be zero in the dark (§8).

### `air_humidity_pct` — how humid the air around the plant is

Measured in the body **above** the soil, so this is the room's air, not the soil.
Capped at 100 % by definition — the air cannot be more than completely full.

### The same five, as a table

| Field | Unit | How it is measured | Key caveat |
| :--- | :--- | :--- | :--- |
| `soil_moisture_vwc` | % vol | electrical response via prongs → converted per substrate | A *derived* value. Substrate-dependent. Spec **0–65 %**, ±5 % **[D]** |
| `soil_temp_c` | °C | temperature sensor on the prongs | Also corrects the other channels. Ambient spec −5 … 50 °C **[D]**; values reach **78** **[M]** |
| `ec_us_cm` | µS/cm | conductivity between the same prongs | **Coupled to moisture** **[I]**. Published unit is mS/cm — this column is µS/cm (÷1000) **[D]** |
| `light_par` | µmol/m²/s | light sensor in the body | Spec up to 2000, ±0.5 % **[D]**. Zero at night is correct |
| `air_humidity_pct` | % RH | sensor in the body, **above** the soil | Ambient air, not soil. Capped at 100 by definition |

### Which channels are shared, and which are per-device

Measured over this sample **[M]** — see §0 for how to read these numbers:

| Signal | Correlation between devices (median) | In plain terms |
| :--- | :--- | :--- |
| light | **0.998** | essentially the same signal everywhere |
| soil temperature | **0.974** | essentially the same signal everywhere |
| air humidity | **0.946** | strongly shared |
| **moisture** | 0.103 | unrelated between devices |
| **EC** | **−0.002** | completely unrelated between devices |

**Translation:** the *environment* (light, temperature, humidity) is nearly
identical across all eight devices — as if they were all in one room, or drawn
from one shared weather series. The *soil* drying out is different in every pot.

**Why this matters:** you cannot detect a faulty device by asking "does this one
differ from the others?" for light, temperature or humidity — they are nearly the
same by construction. For moisture and EC, that test is meaningful.

---

## 3. The four tables at a glance

All figures **[M]**. "Grain" = what one row represents (§0).

| File | Rows | Grain | Entities | Time span | Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `fyta_sensor_sample.csv` | 15,950 | `device_id` + `timestamp` | 8 devices | 21 days @ 15 min | The readings |
| `fyta_contextual.csv` | 49 | `log_id` | 6 plants | same window | What the human did |
| `fyta_images.csv` | 28 | `image_id` | 6 plants | same window | Model guesses about photos |
| `user_plant_device_map.csv` | 8 | `device_id` | 6 plants → 8 devices | (no time) | Which sensor is in which pot |

**Not one cell in any of these files is empty** **[M]**. That sounds good and
isn't — see §7.

---

## 4. The entity model

### Count them once, carefully — they are different numbers

| | Count | What it refers to |
| :--- | :--- | :--- |
| **Sensors** | **8** | `SENS-01` … `SENS-08`. Physical devices pushed into a pot |
| **Plants** | **6** | `UP-1001` … `UP-1006`. A registered plant — one per pot |

8 sensors, 6 pots. They differ because **two of the pots have two sensors in
them**:

```
6 PLANTS / POTS       UP-1001     UP-1002      UP-1003      UP-1004   UP-1005    UP-1006
                      Monstera    Ficus        Zamioculcas  Basil     Orchid     Pothos
                         │           │             │           │         │          │
8 SENSORS            SENS-01     SENS-03       SENS-04      SENS-05   SENS-07    SENS-08
                     SENS-02                   SENS-06
                     ▔▔▔▔▔▔▔                   ▔▔▔▔▔▔▔
                     2 sensors                 2 sensors
                     in one pot                in one pot

4 plants × 1 sensor  =  4
2 plants × 2 sensors =  4
                       ──
                        8 sensors across 6 pots
```

That's the whole structure. **Four plants have one sensor each — no ambiguity.
Two plants have two sensors each** — `UP-1001` (Monstera) and `UP-1003`
(Zamioculcas).

The map table is what records which sensor is in which pot, and the only place
where the species meets the readings. Everything joins through it (see §9 for
how, and for the one join that duplicates rows).

### The problem with those two plants

**The map says two sensors share a pot. The readings say they don't.**

If two probes really are in the same soil, they share the same water. Water the
plant and **both** must jump. Let it dry and **both** must fall. Probe depth
varies, so one might lag or sit at a different level — but they cannot disagree
about *direction*.

```
  What two sensors in ONE pot look like:        What these actually look like:

     ╲ ╱╲ ╱╲ ╱      both refill together         ╲    ╱╲    ╱     different peaks,
     ╲╱  ╲╱  ╲╱                                   ╲__╱  ╲__╱      different days
                        ╲      ╱╲      ╱╲
                         ╲____╱  ╲____╱  ╲
```

Measured over the full window **[M]**:

| Plant | Its two sensors | Correlation | Reads as |
| :--- | :--- | :--- | :--- |
| UP-1001 Monstera | SENS-01, SENS-02 | **−0.076** | unrelated |
| UP-1003 Zamioculcas | SENS-04, SENS-06 | **0.140** | unrelated |

I checked whether depth explains it. It doesn't — a different depth shifts the
*level* and the *timing*, but two wicks in one reservoir cannot drain in
opposite directions. **[I]**

So either the plant genuinely has two sensors in it, or the mapping is wrong.
**[I]** **Either way, do not average these two plants' sensors together** — you
would be blending readings from what look like two different pots.

**The question to ask:** for UP-1001 and UP-1003, is the second sensor really in
that pot? This blocks Task 5 (the per-plant table) for those two plants.

---

## 5. Column dictionary

### `fyta_sensor_sample.csv`

| Column | Type | Meaning | Notes |
| :--- | :--- | :--- | :--- |
| `device_id` | str | Sensor identifier | `SENS-01` … `SENS-08`. Unique in the map |
| `timestamp` | str→datetime | **Local** reading time | Brief says *local*, not UTC. **Two different text formats present** — §6 |
| `substrate_label` | str | Growing medium **the user picked in the app** | 3 values. One per device **[M]**. This selects the conversion table **[D]** — so it is a *setting that changes the number*, not a description |
| `soil_moisture_vwc` | float | Water content, % | Range here: **−5.43 … 107.12** **[M]** |
| `soil_temp_c` | float | Soil temperature, °C | Range here: **16.10 … 78.01** **[M]** |
| `ec_us_cm` | float | Conductivity, µS/cm | Range here: **556 … 2266** **[M]** |
| `light_par` | float | Usable light | Range here: **0 … 589** **[M]** |
| `air_humidity_pct` | float | Air humidity, % | Range here: **27.5 … 131.0** **[M]** |

`substrate_label` values present: `potting_soil`, `coco_coir`, `orchid_bark`.
FYTA ships **20+** substrate profiles **[D]**; this sample exercises three.

### `fyta_contextual.csv`

| Column | Type | Meaning | Notes |
| :--- | :--- | :--- | :--- |
| `log_id` | str | Event identifier | Sequential `LOG-00000` … `LOG-00048` **[M]** |
| `user_plant_id` | str | Which plant | Links to the map |
| `log_type` | str | Event category | 4 values: `watering` (34), `light` (7), `fertilising` (5), `repotting` (3) **[M]** |
| `text` | str | The user's own words | Only **14 different strings** across 49 rows **[M]** |
| `created_at` | str→datetime | When they logged it | 49 rows give 47 distinct times — two pairs share one, both across *different* plants, so not a key problem **[M]** |

`log_type` is **completely determined by `text`** **[M]** — 14 strings, each
mapping to exactly one category. So this is a lookup table, not a job for a
classifier.

The free text also carries something the category column throws away:
`"Watered ~200ml"` states a **volume**. Compare that against how much the
moisture reading jumped, and you have a way to check whether the sensor's
numbers are trustworthy. **[I]**

### `fyta_images.csv`

| Column | Type | Meaning | Notes |
| :--- | :--- | :--- | :--- |
| `image_id` | str | Image identifier | Format `IMG-<plant#>-<YYYYMMDDHHMM>` — **fully reconstructable** from the other columns, verified on all 28 rows **[M]** |
| `user_plant_id` | str | Which plant | Links to the map |
| `captured_at` | str→datetime | When the photo was taken | All between 09:00 and 18:00 **[M]** |
| `image_path` | str | `s3://` link | **The actual photos are not in this dataset.** Only the model's guesses about them |
| `prediction` | JSON | Model output | Structure identical across all 28 rows **[M]** |

The prediction looks like this **[M]**:

```
{ "is_plant": true/false, "is_plant_probability": 0.99,
  "model_version": "health_all_v3",
  "health_assessment": {
      "is_healthy": true/false, "is_healthy_probability": 0.54,
      "diseases":        [ {name, probability, classification[]} … ],
      "diseases_simple": [ {name, probability} … ] } }
```

Three things to know before you use it:

- **The `diseases` list is a family tree, not a flat list of options.**
  `Abiotic` ("caused by environment, not a pest") is the *parent* of
  `Water-related issue` and `Nutrient deficiency`. Parent scores tend to track
  their strongest child. So grabbing the top-scoring entry — the usual reflex —
  hands you the broad category ("environmental"), not a diagnosis ("too dry").
  **[M]**
- **`is_healthy` is just `is_healthy_probability > 0.5`** — checked on all 28
  rows. It is the same information, rounded to yes/no, and adds nothing. **[M]**
- **`model_version` never changes** here (`health_all_v3`), so you cannot check
  whether the model was updated mid-window.

### `user_plant_device_map.csv`

| Column | Type | Meaning | Notes |
| :--- | :--- | :--- | :--- |
| `user_plant_id` | str | Plant instance | **Repeated** — 2 plants occupy 2 rows each |
| `device_id` | str | Sensor | **Unique** — which is what makes the sensor join safe |
| `species` | str | Species name | 6 values, free text. Only 3 are proper two-word scientific names (`Pothos`, `Basil (indoor)` and `Phalaenopsis orchid` are not) **[M]** |

`species` needs cleaning into a standard list before use. `"Basil (indoor)"`
mixes the plant with where it is grown.

---

## 6. Polling rate and time semantics

**One reading every 15 minutes = 4 per hour.** **[M]**

FYTA's published spec is **1×/hour typical, up to 4×/hour** **[D]**. So this
sample is running at the sensor's **maximum** rate, not its normal rate. That
changes what "complete" means: a full day is **96 readings**, not 24.

Over the 21-day window each device should therefore have **2,016 readings** **[M]**.

What we actually have **[M]**:

| Device | Readings | Missing | Extra | Longest silence | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| SENS-01 … 04, 06 | 2,016 | 0 | 0 | 15 min | clean |
| SENS-05 | 1,823 | **193** | 0 | **48.5 hours** | went silent 06-12 23:45 → 06-15 00:15 |
| SENS-07 | 2,016 | 0 | 0 | 15 min | **runs 02:00 → 01:45** instead of 00:00 → 23:45, ending one day later (06-22) |
| SENS-08 | 2,031 | 0 | **15** | 15 min | 15 repeated rows |

### Two different date formats in one column **[M]**

| Format | Rows | Devices |
| :--- | :--- | :--- |
| `2026-06-01 00:00:00` | 13,934 | all except SENS-07 |
| `01/06/2026 02:00` | 2,016 | SENS-07 only |

The second format is ambiguous: `01/06/2026` could be 1 June or 6 January. It
can be resolved without guessing, because **872 of those rows have a first field
between 13 and 22 — and there is no 13th month.** **[M]**

> **A tempting but wrong check:** "if I read it wrong, the timestamps will stop
> being 15 minutes apart." They won't. Misreading `01/06` as 6 January leaves
> every reading exactly 15 minutes from its neighbour, because the misreading is
> consistent. A cadence check still scores ~99 % **[M]**. Impossibility is the
> evidence, not spacing.

### SENS-07's clock is two hours off

SENS-07's readings run from 02:00 to 01:45 the next day — **two hours later** than
every other device. **[M]** This was found by lining up the light readings of each
device against the others and seeing which shift makes them match: agreement goes
from 0.802 to **0.9997** once shifted by 2 hours **[M]**.

Germany is **UTC+2** in June (summer time). So the simplest explanation is a
timezone difference: the fleet records local time, and SENS-07 records UTC — or
the reverse. **[I]**

That matters because the fix is different. **This is testable:** a timezone
difference becomes **1 hour** in winter, whereas a wrong hardware clock stays at
2 hours year-round. Worth one question to the firmware team.

---

## 7. What "missing" looks like here

**Not one cell in any of the four files is empty.** **[M]**

That is the trap. The usual completeness check — "count the empty cells" —
returns 0 everywhere and tells you nothing, because this dataset expresses
absence as **rows that were never written**, not as blank cells.

What that means in practice:

- **Count against the expected schedule, not against empty cells.** SENS-05 is
  missing 193 readings — 90.4 % complete — yet has no empty cells at all. **[M]**
- **A gap looks exactly like an outage** unless you have the expected schedule to
  compare against.
- **Repeated rows exist** (SENS-08, 15 of them). They are byte-identical, not
  conflicting **[M]** — the same reading delivered twice, safe to remove the
  copies.
- **Failed readings are not marked.** A nonsense value sits in the data looking
  exactly like a good one. Nothing in the file flags it.

---

## 8. Values that are impossible, and why it matters

Checked against FYTA's published specification **[D]** and against physics.

| Field | Range in this data **[M]** | Allowed | Verdict |
| :--- | :--- | :--- | :--- |
| `soil_moisture_vwc` | −5.43 … **107.12** | 0–65 %, ±5 % **[D]** | Impossible **both ways**: 12 readings below 0 (SENS-08), 431 above 65 % (SENS-04) |
| `soil_temp_c` | 16.10 … **78.01** | −5 … 50 °C **[D]** | 78 °C cannot happen in a pot. Converted from Fahrenheit, 78.01 °F = 25.6 °C — which matches every other device **[I]** |
| `ec_us_cm` | 556 … **2266** (0.56 … 2.27 mS/cm) | 0.3–1.7 mS/cm **[D]** | 354 readings above the published range (SENS-03) |
| `air_humidity_pct` | 27.5 … **131.0** | ≤ 100, by definition | 10 readings above 100 (SENS-08) |
| `light_par` | 0 … **589** | up to 2000 **[D]** | Within range — but 5 readings of 429–589 happen **in the middle of the night**, when light must be zero |

**The rule this establishes.** A value outside the instrument's specified range
is not an outlier to trim away. It is **evidence** that the instrument failed or
the conversion is wrong. Deleting it destroys the evidence. Record it, count it,
investigate it. (Rounding it to the nearest allowed value is worse still — that
invents a measurement that was never taken.)

One more thing worth knowing: **±5 % is the sensor's own rated accuracy** **[D]**.
Much of the small up-and-down between consecutive readings (±0.14) is *within
spec* and is not a fault — it is what the device is allowed to do.

### How the "impossible" bounds were chosen

Two of the five are **definitional** — arithmetic, not judgement:

| Bound | Why it is provable |
| :--- | :--- |
| `soil_moisture_vwc` 0 … 100 | a volume fraction cannot exceed 100 % or go below 0 |
| `air_humidity_pct` 0 … 100 | relative humidity is capped by definition |

The other three are **judgement calls, and deliberately wide**:

| Bound | Reasoning |
| :--- | :--- |
| `soil_temp_c` −30 … 70 °C | Potted soil. Below −30 it is frozen solid; above 70 it would kill the plant, so it is not a soil temperature. Wide enough that an outdoor pot in a Berlin winter cannot trip it |
| `ec_us_cm` 0 … 20 000 µS/cm | ~12× the published ceiling, and about 40 % of seawater. Real salinity extremes must not be nulled |
| `light_par` 0 … 2 500 µmol | Full summer sun is ~2000–2200. 2500 is *brighter than the sun* |

**The asymmetry decides the width.** A bound set too narrow **nulls real data** —
destructive, and unrecoverable in the published table. A bound set too wide
merely leaves junk *flagged*, which is visible and reversible. So the impossible
ceiling sits well above the specified ceiling (1.25× to 12×), and the flag band
does the work in between.

**They are deliberately not derived from the data.** A quantile cut or a "3σ from
the fleet mean" rule moves with the data, so a fleet-wide fault would shift the
bound and hide inside it. A fixed physical limit cannot.

**Order matters as much as the bound.** `soil_temp_c` is checked *after* the
Fahrenheit conversion. Checked before it, SENS-07's raw range of 61.9–78.0 °F
looks like 62–78 °C and **982 perfectly good readings would be nulled**.

**And all three rest on a conversation.** They depend on **D1** — are the
published ranges current for this hardware generation? They are set generously so
a wrong answer is survivable, but hardware can settle them properly.

---

## 9. Join recipes — and the one trap

Verified by actually running the joins **[M]**:

| Join | Rows before | Rows after | Safe? |
| :--- | :--- | :--- | :--- |
| `sensor` joined to `map` on `device_id` | 15,950 | 15,950 | ✅ fine — `device_id` appears once per row in the map |
| `contextual` joined to `map` on `user_plant_id` | 49 | **67** | ❌ **rows duplicated ×2** |
| `images` joined to `map` on `user_plant_id` | 28 | **35** | ❌ **rows duplicated ×2** |

Because two plants occupy two rows in the map, joining the logs or the images to
it **copies every row for those plants.** 49 logs become 67. Nothing errors;
the numbers just quietly double for those two plants.

Fix it by aggregating the map to one row per plant first, or by joining on
`device_id` where possible.

> **Why this one is dangerous:** the *sensor* join is completely clean. Test one
> relationship, conclude the schema is fine, and this ships.

### The intended join path

```
sensor ──device_id──► map ──user_plant_id──► contextual
                          └─user_plant_id──► images

sensor  + map         →  readings, with species & substrate   (safe, 1:1)
map     + contextual  →  events per plant                     (duplicates — dedupe first)
map     + images      →  predictions per plant                (duplicates — dedupe first)

The per-plant table = sensor + map, then attach events and images
by plant and time window — never a plain match on plant alone.
```

---

## 10. What this data cannot tell you

State these as limits. Do not paper over them with assumptions.

| Question | Why the data cannot answer it |
| :--- | :--- |
| Is a photographed plant actually diseased? | `image_path` is a link. **The photos are not in this dataset** |
| How much water does a pot hold? | No pot size, no drainage, no volume. `"Watered ~200ml"` is the only quantity, and only in some logs |
| How deep is each probe? | Probe lengths vary (3–35 cm) **[D]** and the map does not record which was used |
| Is `substrate_label` the conversion actually applied? | It is what the *user selected*. It may be stale, wrong, or changed since |
| Did any device recalibrate itself mid-window? | Newer devices self-calibrate, which shifts readings for up to 48 h **[D]** and leaves no trace in the export |
| How wet is "full" for this pot? | Needs an experiment or per-substrate lab measurements |
| Is 13 % VWC dry? | Depends on the substrate. In orchid bark it is normal; in compost it is drought |

### Who to ask

| Question | Who |
| :--- | :--- |
| Which device generation produced this; are the spec ranges current? | Gregor / hardware |
| Why is SENS-07 two hours out — timezone or clock? | Firmware |
| Two devices on one plant: real, or a mapping bug? | Product / whoever owns the map |
| Is 78 °C a Fahrenheit payload, or a real fault? | Firmware |
| What VWC counts as "dry", per substrate? | Horticulture |
| Is a perfectly straight EC climb physically possible? | Calibration |

---

## 11. Reading order

When you pick this dataset up cold:

1. **Part 3 of this file** — what the data is.
2. **Parts 1–2 of this file** — what is being asked, and the submission rules.
3. `AGENTS.md` — the engineering rules that bind the work.
4. **Only then write code.** The first script should *verify* this document's
   measured claims, not discover the structure for the first time.

That order is the point. A script written before step 1 will report a `float64`
column with range `-5.43 … 107.12` and call it clean.
