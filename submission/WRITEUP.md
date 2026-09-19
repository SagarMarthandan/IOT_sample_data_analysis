# FYTA — Data Engineer assessment

**Sagar Marthandan**

Three weeks, 8 soil sensors, ~16,000 readings, 49 user notes, 28 plant photos.
`uv run fyta_pipeline.py` reproduces everything below.

## Five things that matter

**1. A sensor stopped measuring, and nothing says so.** Sensor 6's moisture reads
exactly 25.01 for fourteen days — 1,344 readings — and looks normal. What gives it
away is that its *own* four other channels kept moving.

**2. A two-day gap that leaves no trace.** One sensor is missing 193 readings. No
blank cells, no errors — the rows are simply absent. Only the expected-slot count
reveals it.

**3. A sensor in the wrong units, on the wrong clock.** Sensor 7 read Fahrenheit
and ran two hours out. Neither is visible in the values — Fahrenheit only from
jittering 1.8× faster than its peers, the clock only from its daylight pattern.

**4. One join is safe, the next is not.** Plant IDs repeat, so joining notes or
photos multiplies rows — 49 become 67. The trap is that the *first* join works.

**5. Two pots have two sensors each, and the pairs disagree.** Their moisture
correlates at −0.08 and +0.14 — flat to negative. What that rules out is *averaging
them*: the average describes neither pot and discards the disagreement. What it does
**not** establish is why — depth, placement, a failed probe and a wrong mapping
all produce this. **I could not settle it from the data alone.**

## Three decisions I would defend

**Not everything out of range is wrong.** Impossible readings are removed and
logged; merely unusual ones are *kept* and marked. Collapsing the two is how real
events get deleted — one sensor has 431 unusual readings in long stretches.

**Finding and fixing are separate jobs, checked both ways.** A detector with no fix
is a warning nobody acts on; a fix with no detector rots. The gate proves every
removed value was removed, *and* every flag matches a detector.

**Never average the two sensors on one pot** — the disagreement is the only reason
to fit two probes.

## What I would never ship

- **Averaged sensors on one pot** — the disagreement *is* the signal.
- **A filled-in gap** — a user note sits inside those missing two days. An
  *expected-but-absent* row is honest; an interpolated one is not.
- **Trimmed readings** — 107 % moisture is a finding, not a typo to clip.
- **Deleted odd readings** — eight 1am light readings are out of pattern but inside
  range. Someone may have switched a lamp on. Kept, marked.
- **A safety check that cannot fail.**

## Where I was wrong

Two external reviews found ten real defects *after* I had reported the work sound.
All are fixed, each with a test that fails if the fix is undone. The four worst:

- **The publishing gate could not fail.** It asked "is any value missing?", which
  any missing value satisfies. I restored 1,344 known-bad readings; it passed.
- **Two rows on one key were resolved by coin-flip.** Disagreeing duplicates were
  dropped to one, silently. Both are now quarantined.
- **A falling reading counted as agreement** — a large conductivity *drop* scored
  as support for "fertiliser raised conductivity".
- **A frozen-channel rule deleted real data.** It nulled any long unchanged run,
  including legitimate darkness — 52 good light readings in a fixture.

One review also caught a claim that was simply wrong: I had written that a drying
*rate* escapes the substrate calibration. It does not — differentiating removes the
offset and keeps the gain, and the gain is what differs between soils.

**The pattern: I checked by re-reading my own writing, not by re-running.**

## Two results that came back negative

**The photo model cannot be validated here.** Its water-deficiency score tracks
sensor dryness at r = 0.75 — the one axis the sensor already measures — and the
dataset is synthetic, so the agreement may be a shared generator rather than two
instruments. The heads that *could* disagree (fungus, pests) never exceed 0.06.
A head that never fires can neither confirm nor contradict.

**Triangulation does not work, and not because the effect is weak.** Across five
fertilising events no probe's conductivity moves outside its own step noise — and
the light logs *contradict*: "moved closer to window" moves the daily peak **down**
by 4.4.

## What I would do next

1. **Put the checks in the build** — every new check gets a test that fails without it.
2. **Move device settings into an effective-dated registry.** Unit fixes, clock
   offsets and specs are code today; plant, soil and species are already data.
3. **Settle the two-sensor question** — it decides how the modelling table is built.
4. **Version each derived value.** Moisture comes from a curve with no version.
