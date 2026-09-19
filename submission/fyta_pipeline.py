"""FYTA Data Engineer assessment -- the runnable report.

Tasks 1-5, on the four source tables in ../data/. The logic lives in the `fyta`
package; this file is the entry point and the printed narrative, so the code
that produces the run log is the same code you can import and read.

Section index (grep the banner text). The number is the TASK; the letter is
the section within it, so `3a` is the first section of Task 3.

   1a. LOAD          what was read, and in what form       } Task 1
   1b. STRUCTURE     entities, declared grain, coverage    }  ingest
   1c. CHANNELS      raw value ranges                      }  & orient
   1d. EVENTS        what the other three tables hold      }
   1e. FIRST LOOK    figures, cadence self-check           }
   2a. EVIDENCE      measured evidence per problem         } Task 2
   2b. FINDINGS      what it is, how serious, what kind    }  quality
   2c. DETECTION     what caught it, what is blind to it   }
   3a. CLEAN         sensor: two-tier, then the audit gate } Task 3
   3b. NORMALIZE     image: JSON blob -> flat table        }
   4a. SOURCE        do the four sources agree?            } Task 4
   5a. FEATURES      one time-indexed table per plant      } Task 5
   6a. TRIANGULATION can three sources confirm an event?   } Task 6
   8a. SIGNAL        drydown rate                          } Task 8
   9a. LOG TEXT      structured, not classified            } Task 9

Task 7 has no banner: it is a design sketch, so it lives in the notebook.

The Task 1 / Task 2 line is strict: 1a-1e state what is PRESENT, 2a-2c state
what is WRONG. (4a breaks it deliberately: a source question is neither.)

ponytail: one entry point, five modules. The split is by CHANGE REASON, not by
size -- sensor reading changes when we learn about the hardware, the cleaning
policy when we decide how to treat a defect, the source assessment when a feed
changes, the feature table when the modelling team's needs change. The findings
table stays in sensors.py beside the detectors it cites, so a claim is never
separated from its evidence. Merged back into one file only if a module loses
its reader.

Run:  uv run fyta_pipeline.py
"""

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fyta.cleaning import audit, clean
from fyta.domain import CADENCE, CHANNELS, IMPOSSIBLE, SPEC
from fyta.features import assert_grain, plant_features
from fyta.sensors import (
    COVERAGE_COLS, EVIDENCE_NOTES, FINDINGS, align_clocks, check_grid,
    detection_coverage_frame,
    device_coverage, evidence_tables, findings_frame, frozen_windows,
    key_uniqueness, parse_timestamps, plot_by_device, plot_fleet,
)
from fyta.signals import drydown_rate, log_signals
from fyta.sources import assess_source, image_predictions, triangulate

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data"
OUT = ROOT / "out"


def h(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# Each detector below produces evidence. The classification that follows is a
# judgement, stated separately and visibly, so the two can be checked against
# each other rather than blended into one confident sentence.


def main() -> None:
    # Headless when run as a script. Deliberately NOT at module level: the
    # notebook imports this module, and forcing Agg here would stop figures
    # rendering inline there.
    import matplotlib

    matplotlib.use("Agg")
    (OUT / "figures").mkdir(parents=True, exist_ok=True)

    sensor = pd.read_csv(DATA / "fyta_sensor_sample.csv")
    sensor["ts"] = parse_timestamps(sensor["timestamp"])
    sensor = sensor.sort_values(["device_id", "ts"], ignore_index=True)

    # one date format each, so pandas' own inference is safe here
    contextual = pd.read_csv(DATA / "fyta_contextual.csv", parse_dates=["created_at"])
    images = pd.read_csv(DATA / "fyta_images.csv", parse_dates=["captured_at"])
    mapping = pd.read_csv(DATA / "user_plant_device_map.csv")

    declared = [
        ("sensor", sensor, ["device_id", "ts"]),
        ("contextual", contextual, ["log_id"]),
        ("images", images, ["image_id"]),
        ("mapping", mapping, ["device_id"]),
    ]

    # ================================================================== TASK 1
    # Ingest and orient. Shape, contract, coverage -- no judgement. Every
    # statement here is a fact about what is present, not about what is wrong.

    h("1a. LOAD - what was read, and in what form")
    for name, df in [("sensor", sensor), ("contextual", contextual),
                     ("images", images), ("mapping", mapping)]:
        print(f"  {name:11} {df.shape[0]:>6} rows x {df.shape[1]} cols")
    fmt = (sensor["timestamp"].astype(str).str.match(r"^\d{4}-")
           .map({True: "ISO YYYY-MM-DD", False: "DD/MM/YYYY"}))
    print(f"\n  sensor date formats: {fmt.value_counts().to_dict()}")
    print(f"  of the {int((fmt == 'DD/MM/YYYY').sum())} slash-dated rows, every one is "
          f"resolvable: a first field above 12 cannot be a month")

    h("1b. STRUCTURE - entities, declared grain, coverage of the window")
    print(f"  sensors {mapping['device_id'].nunique()}   plants {mapping['user_plant_id'].nunique()}"
          f"   -> {mapping.groupby('user_plant_id').size().to_dict()}")
    print()
    print(key_uniqueness(declared).to_string(index=False))
    print()
    print(device_coverage(sensor, CADENCE)[COVERAGE_COLS].to_string(index=False))

    h("1c. CHANNELS - raw, as delivered, nothing filtered")
    print(sensor[CHANNELS].describe().T.round(2).to_string())

    h("1d. EVENTS AND IMAGES - what the other three tables hold")
    print(f"  log types: {contextual['log_type'].value_counts().to_dict()}")
    print(f"  distinct log texts: {contextual['text'].nunique()} of {len(contextual)} rows")
    print(f"  images: {len(images)}, captured hours "
          f"{sorted(set(images['captured_at'].dt.hour))}")

    h("1e. FIRST LOOK")
    for name, fig in [("task1_fleet", plot_fleet(sensor)),
                      ("task1_by_device", plot_by_device(sensor, mapping, contextual))]:
        fig.savefig(OUT / "figures" / f"{name}.png", dpi=75)
        plt.close(fig)
    check_grid(sensor, CADENCE)
    print("  wrote figures/task1_fleet.png and task1_by_device.png")
    print("  self-check: every device is on the 15-minute grid")

    # ================================================================== TASK 2
    # Data quality. Every statement from here is a judgement about what is
    # wrong, how badly, and what kind of wrong it is.

    h("2a. QUALITY - EVIDENCE")
    gaps = device_coverage(sensor, CADENCE)
    for title, frame in evidence_tables(sensor, mapping, contextual, images).items():
        print(f"\n-- {title}")
        note = EVIDENCE_NOTES.get(title, "")
        if note:
            print(textwrap.fill(note, 74, initial_indent="   ",
                                subsequent_indent="   "))
        print(frame.to_string(index=False))

    h("2b. FINDINGS - what it is, how serious, and what kind of problem")

    # Numbers below are the verified outputs of the detectors above; they are
    # written out because the classification is prose, not computation. The
    # evidence tables sit immediately above so every claim can be checked.
    for fid, what, device, how, severity, kind, nxt in FINDINGS:
        print(f"\n{fid}  {what}   [{device}]")
        print(f"    detected : {how}")
        print(f"    severity : {severity:<7} class: {kind}")
        print(f"    next     : {nxt}")

    findings_df = findings_frame()
    findings_df.to_csv(OUT / "task2_findings.csv", index=False)
    print(f"\n{len(findings_df)} findings; by class:")
    print(findings_df["class"].str.split(" - ").str[0].value_counts().to_string())

    h("2c. DETECTION COVERAGE - what caught it, and what is blind to it")
    coverage = detection_coverage_frame()
    for _, r in coverage.iterrows():
        print(f"\n{r['id']}  {r['finding']}")
        print(f"    caught by : {r['caught_by']}")
        print(f"    missed by : {r['missed_by']}")
    coverage.to_csv(OUT / "task2_detection_coverage.csv", index=False)
    print(f"\n{len(coverage)} findings; every one defeats at least one obvious check")

    # ================================================================== TASK 3
    h("3a. CLEAN - first pass, then audit before anything is published")

    windows = frozen_windows(sensor)
    cleaned, rejections = clean(sensor, windows)
    print(f"  rows in          : {len(sensor)}")
    print(f"  duplicates dropped: {int(sensor.duplicated(['device_id', 'ts']).sum())}")
    print(f"  rows out         : {len(cleaned)}")
    print(f"  values nulled    : {len(rejections)}")
    print(f"  values flagged   : {int((cleaned['qc_flags'] != '').sum())} "
          f"(kept, marked outside the specified range)")

    print("\n-- what was nulled, by reason")
    print(rejections["reason"].str.split(" (", regex=False).str[0].value_counts().to_string())

    print("\n-- raw vs cleaned, the channels that changed")
    for channel in CHANNELS:
        r, c = sensor[channel], cleaned[f"{channel}_clean"]
        print(f"  {channel:18} raw [{r.min():8.2f}, {r.max():8.2f}]   "
              f"clean [{c.min():8.2f}, {c.max():8.2f}]   nulls {int(c.isna().sum())}")

    print("\n-- audit gate (nothing publishes unless every check passes)")
    checks = audit(cleaned, sensor, rejections)
    print(checks.to_string(index=False))
    assert checks["passed"].all(), "audit failed - refusing to publish"

    cleaned.to_csv(OUT / "cleaned_sensor.csv", index=False)
    rejections.to_csv(OUT / "qc_rejections.csv", index=False)
    print(f"\n  published: cleaned_sensor.csv ({len(cleaned)} rows), "
          f"qc_rejections.csv ({len(rejections)} rows)")

    print("""
  Deliberately NOT done, and why:
    F4 SENS-03 EC drift   detected, but NOT flagged per row. The cleaner flags
                          only values outside the published range, so the flag
                          marks the excursion past 1700 (from 06-17), NOT the
                          drift regime (from 06-11): 354 of 1,056 drifting rows
                          carry it. Dropping a channel is a modelling decision,
                          not a data fix. Values kept.
    F7 the 48.5h outage  left as a hole. Interpolating would fabricate 193
                          readings that were never taken.
    F9 fan-out            the log carries no device id, so on a two-sensor plant
                          "the user watered" has no device to attach to. Kept at
                          plant grain rather than duplicated. D11 decides whether
                          the fix is the mapping or the log schema.
    F10 two sensors       unresolved. Averaging them would invent a number
                          describing neither pot.
    F11 log mismatch      a label problem. The sensor values are not wrong.
    F12 shared ambient    a constraint on what may be tested, not a defect.
    F13 substrate label   a snapshot with no history. Needs effective dating from
                          the app before any VWC comparison across a repot.

  Not clipped to range, not averaged, not interpolated: all three would have
  manufactured measurements that were never taken.""")

    h("3b. NORMALIZE - the image table, JSON blob -> flat")

    heads, head_cols, children = image_predictions(images)
    # The check for the parse. The first version of the hierarchy took chain[-1]
    # as the parent, and `nutrient-related issue` is a label on the taxonomy
    # rather than a class in it -- so it named a parent with no column.
    assert all(p in head_cols for p in children), \
        f"hierarchy names a parent that is not a head: {set(children) - set(head_cols)}"
    assert set(head_cols) >= set(sum(children.values(), [])), \
        "a child is missing from the head columns"

    print(f"  rows in          : {len(images)}   (one JSON blob each)")
    print(f"  rows out         : {len(heads)}   (one column per head)")
    print(f"  heads            : {len(head_cols)}")
    for parent, kids in children.items():
        print(f"    {parent}  <-  {', '.join(kids)}")
    heads.to_csv(OUT / "images_flattened.csv", index=False)
    print("\n  published: images_flattened.csv")

    print("""
  NORMALIZING, not cleaning. Nothing is removed -- the image table has no values
  to correct. What it has is a JSON blob in one column, which no consumer can
  filter, join or aggregate. Flattening it is the same job the sensor table got:
  turn what was delivered into what can be used.

  The hierarchy is read from each head's own `classification` chain rather than
  transcribed, so a model version that renames or re-parents a class needs no
  code edit. `nutrient-related issue` is why: it appears as a classification but
  is never scored, so it is a label ON the taxonomy, not a class IN it.

  The CSV is for CONSUMERS. The pipeline still parses data/fyta_images.csv
  directly -- reading back a file this pipeline wrote would make it depend on its
  own history, and a stale copy would go unnoticed.""")

    # ================================================================== TASK 4
    h("4a. SOURCE - do the four sources agree?")

    # Controlled comparison: the SAME code on two sensor frames. Time is held
    # constant -- the clock offset is proven (F2) and is not in dispute -- so
    # the only thing that varies is the VALUES. One variable, so a gap between
    # the columns can be attributed to it rather than to the pairing.
    raw_arm = align_clocks(sensor).rename(columns={"ts": "ts_aligned"})
    arms = pd.DataFrame({
        "raw": assess_source(raw_arm, "soil_moisture_vwc", heads, head_cols,
                             children, mapping, contextual),
        "cleaned": assess_source(cleaned, "soil_moisture_vwc_clean", heads,
                                 head_cols, children, mapping, contextual),
    })
    arms["delta"] = (pd.to_numeric(arms["cleaned"], errors="coerce")
                     - pd.to_numeric(arms["raw"], errors="coerce"))
    arms.to_csv(OUT / "task4_source_assessment.csv")
    a = arms["cleaned"]

    print("-- 1. plant species      static label, no timestamps")
    print(f"     one substrate per species      {bool(a['species -> one substrate'])}")
    print("     checkable against a date?      no - it never changes (F13)")

    print("\n-- 2. contextual logs    user-entered")
    print(f"     one log_type per phrase        {bool(a['log phrase -> one log_type'])}"
          f"   -- and that is not a compliment, see below")
    print("     do they line up with sensors?  no - the two were never connected (F11)")

    print("\n-- 3. image predictions  model output")
    print(f"     internally consistent          {bool(a['is_healthy == (prob > 0.5)'])}"
          f"   is_healthy is exactly (probability > 0.5)")
    print(f"     agree with the sensors?        yes - r = {a['r(Water deficiency, dryness)']:.2f}"
          f" vs dryness")
    print("     ...but that establishes less than it looks. Calling it 'circular'")
    print("     was wrong -- two instruments measuring one latent variable IS")
    print("     corroboration. Calling it 'convergent evidence' is unsupported too:")
    print("     this dataset is SYNTHETIC, so if one generator emitted both series")
    print("     from the same latent state, r says nothing about the world. Neither")
    print("     reading is earned without model lineage from the vendor.")
    print(f"     independent heads fire?        no - Fungi and Animalia never exceed 0.06")
    print(f"                                    {int(a['heads ever above 0.10'])} of "
          f"{len(head_cols)} heads carry any signal")

    print("\n-- 4. sensor data        the reference the other three are read against")
    print(f"     {len(sensor):,} readings; its own defects are Tasks 1-3")

    agree = pd.DataFrame(
        [["plant species", f"{mapping['user_plant_id'].nunique()} plants", "static",
          "cannot be checked - no timestamps"],
         ["contextual logs", f"{len(contextual)}", "user-entered",
          "no - unrelated to the sensor (F11)"],
         ["image predictions", f"{int(a['photos'])}", "model output",
          "yes on water - independence unestablished"],
         ["sensor data", f"{len(sensor):,}", "instrument", "the reference"]],
        columns=["source", "rows", "kind", "agrees with the sensors?"])

    print("\n-- the four sources side by side")
    print(agree.to_string(index=False))
    print(f"\n  Raw vs cleaned: every metric is identical except the r() rows "
          f"(max move {arms['delta'].abs().max():.3f}).\n"
          f"  The answer does not depend on Task 3's choices. Full table: "
          f"out/task4_source_assessment.csv")

    print("""
  THE LOGS ARE CONSISTENT, AND THAT IS NOT A COMPLIMENT. Fourteen phrases, all
  single-purpose, and not one of the 49 rows is ambiguous -- no "watered and fed",
  no "repotted, watered it in". Either the text is canned (a picker in the app),
  in which case 1:1 is a schema constraint rather than a quality signal; or it is
  free text, in which case perfect consistency across 49 rows is a generation
  signature. Either way the tick is not earned, and product can settle it.

  Verdict: use the water heads as a FEATURE, never as a LABEL. Their agreement
  cannot settle a disagreement with the sensors, because independence is
  unestablished and the data is synthetic (see F10, still open). What would
  settle it is lineage: did the image model consume VWC, or did one generator
  emit both? is_healthy is withheld -- it is exactly (probability > 0.5).

  Gate it at ingestion: pin model_version, fail on an unknown head name, and
  treat a new class as a schema event rather than a column that appears.""")

    # ================================================================== TASK 5
    h("5a. FEATURES - one time-indexed table per plant")

    features = plant_features(cleaned, mapping)
    rows = assert_grain(features)

    print("  grain        : (user_plant_id, ts_aligned) -- declared and asserted")
    print(f"  rows         : {rows:,}   (0 duplicate keys)")
    print(f"  columns      : {len(features.columns)}")
    print(f"  plants       : {features['user_plant_id'].nunique()}")
    print(f"  span         : {features['ts_aligned'].min()} -> "
          f"{features['ts_aligned'].max()}")

    print("\n-- per plant")
    per = features.groupby(["user_plant_id", "species"], sort=True).agg(
        rows=("ts_aligned", "size"),
        probes=("n_sensors", "first"),
        vwc_coverage=("vwc_1", lambda s: round(float(s.notna().mean()), 3)),
        longest_gap_h=("gap_minutes", lambda s: round(float(s.max()) / 60, 1)))
    print(per.to_string())

    features.to_csv(OUT / "plant_features.csv", index=False)
    print("\n  published: plant_features.csv")

    print("""
  Two things this table does NOT hide:

    F10  UP-1001 and UP-1003 carry two probes each. Both are kept side by side,
         with `vwc_delta` as their disagreement. Averaging them would produce one
         number describing neither pot -- and would throw away the fault signal
         that a second probe exists to provide.

    F13  `substrate` is what the app says today. There is no effective dating, so
         a repot mid-window is invisible. Do not read this column as "true at
         this timestamp" -- D7 and D11 are the conversations that fix it.

  SCOPE, stated because the brief says "unified": this table unifies the cleaned
  sensor channels and the plant metadata, and deliberately does NOT join in the
  logs or the images. There are 49 log rows and 28 photos against 11,903
  fifteen-minute rows -- spreading a log across its neighbourhood would duplicate
  it hundreds of times, and a photo the model evaluates once cannot be sampled at
  15-minute resolution. Consumers should join both AS-OF with an explicit
  tolerance. That is a modelling decision, not one this table makes silently.

  Also not done: the 48.5-hour outage (F7) is left as absent rows, made visible
  by `gap_minutes` on the row that follows it. Filling it would fabricate 193
  readings that were never taken.""")

    # ================================================================== TASK 6
    h("6a. TRIANGULATION - can three sources confirm a fertilising event?")

    tri = triangulate(cleaned, features, contextual, heads)
    shown = tri.assign(fertilised=tri["fertilised"].dt.strftime("%m-%d %H:%M"),
                       image=tri["image"].dt.strftime("%m-%d %H:%M"))
    print(shown[["log", "plant", "fertilised", "d_ec", "noise_sd", "d_ec_sigma",
                 "image", "hours_off", "nutrient_def", "sensor_leg", "model_leg"]]
          .round(3).to_string(index=False))
    tri.to_csv(OUT / "task6_triangulation.csv", index=False)

    legs = (f"{int(tri['sensor_leg'].eq('rises').sum())} with an EC rise, "
            f"{int(tri['model_leg'].eq('responds').sum())} with a model response, "
            f"{int(tri['model_leg'].eq('no post-event image').sum())} with no photo after the event")
    print(f"""
  {len(tri)} fertilising logs: {legs}.

  Triangulation does not occur -- and not because the effect is weak. Two of the
  three legs carry no fertiliser signal at all: every dEC sits inside one step of
  the device's own noise, and two of the five are negative. The model leg cannot
  corroborate either, because its nutrient head never exceeds 0.073 on any photo
  (section 9). A head that never fires can neither agree nor disagree.

  THE WINDOW IS THE TRAP. Widen it and UP-1002 appears to confirm: its EC climbs
  1,289 uS/cm across the record, so "fertilised, then EC rose" looks true. It is
  not -- the climb starts TEN DAYS after the feed and is a straight line, which
  is SENS-03's gain drift (F4), not chemistry. A drift on the same plant is what
  makes the false positive convincing.""")

    # ================================================================== TASK 8
    h("8a. SIGNAL - drydown rate (Task 8, optional)")

    rate = drydown_rate(cleaned)
    by_dev = rate.groupby("device_id", sort=True)["drydown_pct_per_day"]
    per_dev = by_dev.agg(median="median", p10=lambda s: s.quantile(0.10),
                         p90=lambda s: s.quantile(0.90))
    per_dev["readings"] = by_dev.count()
    print(per_dev.round(2).to_string())
    rate.to_csv(OUT / "task8_drydown.csv", index=False)

    print(f"""
  THE RATE IS COMPARABLE WHERE THE LEVEL IS NOT. An absolute VWC threshold is
  wrong across substrates -- that is what the conversion curve is for, and what
  is still unresolved here (F13, D7). But "this pot loses 2 %/day" means the
  same thing in coir as in bark, so the rate carries across the fleet without a
  calibration nobody has confirmed.

  Median, not mean: a watering event is a large jump the other way, and a mean
  would average drying together with watering. Positive = drying.

  A per-step rate also amplifies per-reading noise -- 0.4 %VWC of jitter over
  15 minutes reads as 38 %/day -- which is exactly why the median is taken over
  a full day rather than reported per step.

  THAT CORRECTION IS WHAT MAKES THE OUTLIER MEANINGFUL. SENS-04 reads
  {per_dev.loc['SENS-04', 'median']:.1f} %/day against 3-6 for the rest of the fleet.
  A pot cannot lose that much water and still read 15-100. It is the sawtooth
  from F5, whose cause is still unclassified -- gain error, or a different pot.
  The signal rediscovers the same device the range checks flagged, from an
  unrelated angle, which is the point of having a signal at all.""")

    # ================================================================== TASK 9
    h("9a. LOG TEXT - structured, not classified (Task 9, optional)")

    logs = log_signals(contextual)
    vocab = (logs[logs["intensity"].notna()]
             .groupby(["log_type", "text", "intensity"], sort=True)
             .agg(n=("log_id", "size"), ml=("volume_ml", "max"))
             .reset_index())
    print(vocab.to_string(index=False))
    logs.to_csv(OUT / "task9_log_signals.csv", index=False)

    print("""
  A LOOKUP, NOT A CLASSIFIER. Fourteen phrases over 49 rows, and the
  phrase-to-log_type mapping is already one-to-one -- a model would be a more
  expensive way to write a dict, and would need labels nobody has.

  The text adds a coarse intensity and one volume. That is all it encodes: only
  1 of the 14 phrases contains a number, and the vocabulary is closed.

  Limit, shared with everything else here: F11 showed the logs do not align with
  the sensors in time, so a cleaner log is still not a timestamped event.""")

    check_grid(sensor, CADENCE)
    print("\nself-check passed: every device on the 15-minute grid; "
          "day-first parse proven by impossibility")

    gaps.to_csv(OUT / "task2_coverage_gaps.csv", index=False)
    print("wrote out/: run.log, cleaned_sensor.csv, qc_rejections.csv, "
          "task2_findings.csv, task2_coverage_gaps.csv, "
          "task2_detection_coverage.csv, task4_source_assessment.csv, "
          "plant_features.csv, task6_triangulation.csv, images_flattened.csv, "
          "task8_drydown.csv, "
          "task9_log_signals.csv, figures/")


if __name__ == "__main__":
    main()
