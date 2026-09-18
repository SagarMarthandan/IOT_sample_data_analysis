# FYTA Data Engineer — Assessment

> **Provenance.** Merged from `assessment details.txt` (task brief) and
> `assessment.txt` (message-thread export) on 2026-09-16. **Those two `.txt`
> sources have since been removed from the repository, so this file is now the
> canonical copy** — the `Source:` attributions below are historical.
>
> Both bodies are reproduced verbatim, including original typos, inconsistent
> capitalisation and emoji. The only edits are presentational: redundant `**`
> inside headings removed, bare-table rows given header rows so they render, and
> bare URLs turned into links. The second source was a UI export and contains
> profile/timestamp chrome, reproduced as-is.

## At a glance

| | |
| --- | --- |
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
| --- | --- |
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
| --- | --- |
| log_id | User event log identifier |
| user_plant_id | user plant identifier |
| log_type | unique logs |
| text | string |
| created_at | datetime |

#### fyta_images.csv

| **Column** | **Meaning** |
| --- | --- |
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
