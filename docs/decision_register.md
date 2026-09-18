# Decision register

Every implementation choice in `submission/` that rests on information **I do not
have**. Recorded here rather than buried in a code comment, because the
resolution is a conversation with hardware, firmware, product or the analysis
team — not a fix I can make alone.

**Why this exists.** A comment in the source records *what the code does*. It
cannot record *what the choice depends on*, *who owns the answer*, or *what
happens if it's wrong*. Those outlive the code and they change it. A decision
taken with the wrong premise is a re-run, not a patch.

**Status:** `OPEN` awaiting an answer · `CONFIRMED` verified · `REVISED` changed.

## Summary

| # | The choice | Rests on | Owner | Impact if wrong |
|---|---|---|---|---|
| **D1** | SPEC ranges are the validity thresholds | Ranges scraped from the website, aggregated across product generations | Hardware | Flags the wrong readings — or misses real ones |
| **D2** | 15 min = the sensor's **maximum** rate | Reporting-rate spec | Firmware | Expected slots off by 4×; completeness numbers meaningless |
| **D3** | SENS-07's clock corrected by a constant −2 h | Timezone, not a drifting clock | Firmware | Wrong at the window edges if the clock drifts |
| **D4** | SENS-07's temperature is Fahrenheit | One device, not a firmware variant | Firmware | Other devices with the same fault stay undetected |
| **D5** | Two-tier: null impossible, **flag** out-of-spec | Whether the analysis team can use 65–107 % VWC | Analysis | 382 SENS-04 readings carry unstated reliability |
| **D6** | 48 samples (12 h) = a frozen channel | Longest a healthy channel can hold a value | Firmware / Analysis | False positives, or missed shorter outages |
| **D7** | `substrate_label` treated as device-level config | It *is* the conversion curve, not a UI label | Product / Backend | A repot silently relabels history (F13) |
| **D8** | The 48.5 h outage left as a hole | Whether the analysis team can tolerate a gap | Analysis | 193 readings absent from every downstream model |
| **D9** | Logs excluded as event truth | Whether the **device** does something at 00:00 | Firmware | Whether some rises are waterings at all |
| **D10** | Near-identical environment treated as an artefact | Whether these 8 devices are co-located | Product / Data | Discarding a real shared ambient signal (F12) |
| **D11** | Two sensors on one plant left separate | Real configuration, or a mapping bug | Product | Task 5 cannot build a per-plant table (F10) |
| **D12** | `soil_temp_c` deliberately absent from `SPEC` | Ambient range ≠ soil range | Hardware | A soil spec exists and I'm not applying it |
| **D13** | The 8 dark-hour light readings are flagged, not deleted | Whether a light at that pot can be real | Firmware | Deleting real observations, or keeping glitches |

---

## D1 · The spec ranges are scraped, not supplied

```python
SPEC = {"soil_moisture_vwc": (0, 65), "ec_us_cm": (300, 1700),
        "air_humidity_pct": (0, 100), "light_par": (0, 2000)}
```

**Choice.** Use FYTA's published ranges as the boundary between "in spec" and
"out of spec".

**Rests on.** Numbers taken from `fyta.de/en/pages/technische-daten` and the Beam
G2 product page, surfaced by search and **aggregated across Beam / Beam 2.0 /
Mini / Sphere generations.** I never confirmed which generation produced this
sample, and never saw a datasheet.

**If wrong.** Every flag and every null in Task 3 inherits the error. A too-tight
range flags healthy readings (and hides real ones behind noise); a too-loose one
lets instrument failures through as data. The detection *logic* survives; only
the thresholds move.

**Also unresolved:** `air_humidity_pct: (0, 100)` is not from FYTA — it's capped
by definition. Calling it a "spec" in the same dict is a slight category error.

**Ask:** which product generation produced this data, and are these ranges current
for it? Is there a machine-readable spec sheet rather than the marketing page?

---

## D2 · Fifteen minutes is treated as the maximum rate

```python
CADENCE = pd.Timedelta("15min")   # a day is 96 slots, the window 2,016
```

**Choice.** The sample is at the sensor's **maximum** reporting rate, so a full
day is 96 slots.

**Rests on.** FYTA's published *"1×/hour typical, up to 4×/hour"*. I read
observed 15-minute spacing as the "up to 4×" case.

**If wrong.** If the true nominal rate is hourly, expected slots drop from 2,016
to 504 and **every completeness number changes meaning** — SENS-05's 90.4 % could
become ~100 %, or the fleet could be 4× over-reporting. The gap detection and the
duplicate detection are the parts most exposed.

**Ask:** is 15 minutes the configured rate, or a buffer flush? Does a
hub-connected device report at a different cadence than a BLE-only one?

---

## D3 · SENS-07's clock is corrected by a constant

```python
CLOCK_OFFSET_H = {"SENS-07": 2}
```

**Choice.** Subtract a fixed 2 hours from one device's timestamps.

**Rests on.** A 2-hour phase shift recovered by cross-correlating its daylight
curve against the peer median (0.802 → 0.9997). Germany is UTC+2 in June, so a
local-vs-UTC difference fits exactly.

**If wrong.** A *timezone* difference is constant and a fixed offset is correct.
A *drifting* hardware clock is not — then a constant offset is right in the
middle of the window and progressively wrong at the edges, which is worse than
obvious corruption because the middle looks fine.

**Also:** hardcoding a device ID does not scale. If timezone misconfiguration is
common, this wants to be a detector, not a lookup.

**Testable without anyone's help:** a timezone offset becomes **+1 h** in winter;
a hardware clock fault stays at 2 h. One winter sample settles it.

---

## D4 · One device's temperature is declared Fahrenheit

```python
UNIT_FIXES = {"SENS-07": {"soil_temp_c": "fahrenheit"}}
```

**Choice.** Convert one device's readings, declared by device ID.

**Rests on.** Three independent tests on that device: jitter ratio 1.82 vs the
fleet (÷1.8 lands exactly on 0.400), converted mean 20.997 vs fleet 20.994, and
converted sd 2.516 vs 2.510. A plain offset would match the mean and fail the
other two.

**If wrong.** The diagnosis is strong; the *scope* is the risk. If a firmware
variant emits Fahrenheit, **other devices in the real fleet may have the same
fault and nothing here would catch it** — SENS-07 is the only one visible because
it's the only one in this sample.

**Ask:** is °F a per-device setting, a firmware variant, or a payload bug? If it's
a variant, the fix belongs upstream and this lookup becomes a stopgap.

---

## D5 · Out-of-spec is flagged, impossible is nulled

```python
IMPOSSIBLE = {"soil_moisture_vwc": (0, 100), ...}   # null above this
SPEC       = {"soil_moisture_vwc": (0, 65),  ...}   # flag above this
```

**Choice.** VWC between 65 and 100 is **kept and flagged**; above 100 is nulled.

**Rests on.** The device is not *specified* to be accurate above 65 %, which is
not the same as the reading being wrong. Nulling would delete **21 % of SENS-04's
readings and destroy the sawtooth** that makes its dry-down legible.

**If wrong / unresolved.** 382 readings now carry a flag whose meaning the
consumer must interpret. The analysis team may prefer them nulled, or may have a
use for them. **This is genuinely their call, not mine.**

**Ask:** can you use readings outside the specified range if they're marked? Or
should the modelling table contain only in-spec values?

---

## D6 · Twelve hours of an unchanged value means a dead channel

```python
FROZEN_MIN_RUN = 48   # samples = 12 hours
```

**Choice.** Any run of ≥48 identical values is treated as a dead channel and
nulled.

**Rests on.** Soil does not hold a value to two decimals for half a day. The
detector is corroborated by the cross-channel check — SENS-06's moisture froze
while its other four channels kept moving.

**If wrong.** Too short and a genuinely slow-drying pot gets nulled. Too long and
a shorter stall passes as data. The threshold is a judgement, and the reasoning
behind 12 hours is mine, not measured.

**Ask:** what's the longest a healthy channel can plausibly hold a value? Is there
a firmware-level stall signature we could detect instead of inferring it?

---

## D7 · `substrate_label` is treated as the calibration parameter

**Choice.** Keep one label per device, and record the effective-dating gap as
F13 rather than inventing history.

**Rests on.** FYTA's documentation: the substrate profile selects the VWC
conversion curve, and there are 20+ profiles.

**If wrong.** If it's only a UI label, F13's severity drops from a magnitude
error to cosmetics. If it *is* the curve, then every pre-repot VWC for UP-1006 may
have been produced by a different curve than the label implies — and the export
cannot tell you, because it carries one label per device with no valid-from date.

**Ask:** is `substrate_label` the profile the value was computed with? Does the
app historise substrate changes? Did UP-1006's substrate actually change on 06-13?

---

## D8 · The 48.5-hour outage is left as a hole

**Choice.** No interpolation, no forward-fill. SENS-05 has 193 genuinely absent
readings and the published table has 193 genuinely absent rows.

**Rests on.** `AGENTS.md` §6 — any imputation must be a new labelled column, and
interpolating 48 hours of soil moisture would fabricate readings that were never
taken. The offline buffer is ~320 measurements, so the data *was* recoverable —
this was a sync failure, not a loss.

**If wrong / unresolved.** Downstream models must handle the gap. If they can't,
interpolation becomes necessary and belongs in a named column with the method
recorded — not silently in the existing one.

**Ask:** does the analysis team need a filled series? If so, what method, and can
the filled rows be excluded from training?

---

## D9 · Does the device do something at 00:00?

**Choice.** Exclude the watering logs from event detection. They are not a
reliable time source.

**Rests on — and this is stronger than a mismatch.** The logs are entered by
users, and they look it: every logged time is human-shaped (07:15, 09:00, 13:30,
19:45, 20:30), spread through daylight hours, and never once at midnight or noon.

The sensor rises do the opposite:

```
31 of 48 rises land exactly on 00:00 or 12:00
SENS-07's six are all at 02:00 — which is also 00:00 once its 2-hour clock
error is removed
excluding SENS-08: 35 of 35 land on the hour
```

**Nobody waters a plant at midnight, six times in three weeks, across five
devices.** So the human side looks human and the machine side looks mechanical.
The odd one out is the *sensor*, not the user.

Grid-searching a constant shift across ±96 h yields 2–3 hits out of 6 at the
best offset, and the best offset differs per plant — so it is not a clock
offset either.

**Most likely explanation:** the dataset is synthetic, and the log and the sensor
series were generated independently. Neither can validate the other.

**The alternative that would matter:** if the device does something at midnight —
a recalibration, a baseline reset, a reporting cycle — then some of those rises
are **not waterings at all**, and the moisture data means something different
than it appears to.

**Ask:** does the device do anything special at 00:00? A recalibration, a
baseline reset, a reporting cycle?

**If wrong.** If the app timestamps logs in a frame we have not identified, this
discards a real signal source, and Task 6's triangulation loses its events.

---

## D10 · The near-identical environment is treated as an artefact

**Choice.** Do not use "differs from the fleet" as an anomaly test for
temperature, light or humidity.

**Rests on.** Cross-device correlation of 0.974 (temp), 0.998 (light), 0.946
(humidity) — against 0.103 for moisture and −0.002 for EC. Soil temperature
agreeing to a median of 0.38 °C across eight devices is not eight independent
pots in eight rooms.

**If wrong.** If these devices genuinely *are* co-located (one site, one
greenhouse), the shared signal is real and useful — a good ambient reference
rather than a generator artefact. The conclusion flips entirely on that fact.

**Ask:** are these eight devices co-located, or is the ambient series synthetic?

---

## D11 · Two sensors on one plant are kept separate

**Choice.** No averaging, no fusion. Both sensors stay as their own columns.

**Rests on.** Inter-device moisture correlation of −0.076 and +0.140. Probes in
one pot share a water reservoir and must be positively correlated even at
different depths. Different depth shifts level and timing; it cannot invert
direction.

**If wrong.** If the mapping is simply a bug, the fix is to correct the dimension
and the two devices resolve into two normal plants. If it's a real configuration,
Task 5 needs an explicit rule and I have none to propose without knowing the
intent.

**Ask:** does the FYTA app allow two sensors on one plant, or does pairing
replace?

---

## D12 · Soil temperature is deliberately excluded from `SPEC`

```python
SPEC = {"soil_moisture_vwc": ..., "ec_us_cm": ...,
        "air_humidity_pct": ..., "light_par": ...}   # soil_temp_c absent
```

**Choice.** No spec range for `soil_temp_c`.

**Rests on.** FYTA publishes an **ambient** operating range (−5…50 °C). Applying
an ambient range to a *soil* reading is a category error — different quantity,
different sensor path. Separately, SENS-07's 78 °C is a unit problem handled by
`UNIT_FIXES`, not a range violation.

**Why it's in this register.** The omission is correct but **currently looks like
an oversight**, and the next reader will assume it was one. It also means soil
temperature has no validity ceiling at all: `IMPOSSIBLE` bounds it loosely at
−30…70 °C, which is a sanity check, not a specification.

**Ask:** does a soil-temperature measurement range exist? If it does, it belongs
in `SPEC`.

---

## Who owns what

| Conversation | Decisions to settle |
|---|---|
| **Hardware** | D1 (ranges, generation), D12 (soil temp spec) |
| **Firmware** | D2 (cadence), D3 (timezone vs clock), D4 (°F scope), D6 (stall signature), D9 (behaviour at 00:00), D13 (light spikes) |
| **Product / Backend** | D7 (substrate historisation), D10 (co-location), D11 (two sensors) |
| **Analysis team** | D5 (can you use flagged values?), D8 (can you tolerate a gap?) |

Four conversations. Every one of them can change code, so it's cheaper to have
them before Task 5 than after.

---

## D13 · Eight dark-hour light readings are kept, not deleted

**Choice.** Flag them and leave the values in place. Do not empty them.

**Rests on.** They are **physically possible**. PAR is rated to 2000 µmol/m²/s and
the highest of the eight is 589, so nothing about the value is out of range. A
lamp or a torch held near that one pot would produce exactly this.

What makes them suspicious is **duration**, not magnitude:

```
SENS-08  01:00   0.0  0.0  429.6  0.0  0.0
```

A switched-on lamp persists; it would appear in several consecutive readings. A
single 15-minute sample bracketed by zeros means the light was on for under 15
minutes, eight separate times, in the middle of the night.

And they are **device-specific**: at all eight moments the other seven devices
read exactly `0`.

**That rules out a shared light event. It does not rule out a local one.** A desk
lamp next to one pot would do it, and no other device would see it.

**So the honest treatment is flag-and-keep.** "Physically impossible" is the bar
for deleting a value. "Statistically implausible for this device" is not — and
emptying these would delete a real observation if the light was real.

**If wrong.** If the light channel has a known stall or spike behaviour, these
are glitches and should be emptied at ingest instead. If a light at that pot is
plausible, then they are real and the flag is the correct record.

**Ask:** does the light channel have a known spike or stall behaviour? What is
the device doing at 00:15–02:30?
