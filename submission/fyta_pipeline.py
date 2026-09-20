"""FYTA Data Engineer assessment -- the runnable report.

Tasks 1-5, on the four source tables in ../data/. The logic lives in the `fyta`
package; this file is the entry point and the printed narrative, so the code
that produces the run log is the same code you can import and read.

Section index (grep the banner text). The number is the task; the letter is
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

The Task 1 / Task 2 line is strict: 1a-1e state what is present, 2a-2c state
what is wrong. (4a breaks it deliberately: a source question is neither.)

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
from fyta.features import assert_grain, plant_features, plant_summary
from fyta.sensors import (
    COVERAGE_COLS, EVIDENCE_NOTES, FINDINGS, align_clocks, check_grid,
    detection_coverage_frame,
    device_coverage, evidence_tables, findings_frame, frozen_windows,
    key_uniqueness, parse_timestamps, plot_by_device, plot_fleet,
)
from fyta.signals import drydown_rate, log_signals
from fyta.sources import assess_source, image_predictions, triangulate

ROOT = Path(__file__).resolve().parent


def find_data_dir() -> Path:
    """Where the four source CSVs are, wherever this copy happens to sit.

    Two layouts are supported, in this order:

        data/ beside this file     a self-contained copy of the folder
        data/ one level up         the repository layout

    Both candidates are named in the error rather than falling back silently: a
    wrong guess would surface later as a confusing pandas error instead of a
    missing file.
    """
    for candidate in (ROOT / "data", ROOT.parent / "data"):
        if (candidate / "fyta_sensor_sample.csv").exists():
            return candidate
    raise FileNotFoundError(
        "no data/ containing fyta_sensor_sample.csv found at:\n"
        f"  {ROOT / 'data'}\n  {ROOT.parent / 'data'}")


DATA = find_data_dir()
OUT = ROOT / "out"


def h(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# Each detector below produces evidence. The classification that follows is a
# judgement, stated separately and visibly, so the two can be checked against
# each other rather than blended into one confident sentence.


def main() -> None:
    # Set Agg only for script runs so notebook figures still render inline.
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
    print("  self-check: every device is on the 15-minute grid -- spacing and phase")

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
  Decisions:
    F4 SENS-03 EC drift   1,056 rows drift from 06-11; 354 past 1700 from
                          06-17 are flagged. Values kept.
    F7 the 48.5h outage  left as a hole: 193 readings were not taken.
    F9 fan-out            kept at plant grain; a two-sensor plant has no device
                          id in the log. D11 decides between mapping and schema.
    F10 two sensors       unresolved; both readings remain separate.
    F11 log mismatch      label problem; sensor values remain.
    F12 shared ambient    fleet reference for all eight devices; D10 checks the
                          shared environment.
    F13 substrate label   snapshot without history; effective dating is needed
                          before VWC comparison across a repot.""")

    h("3b. NORMALIZE - the image table, JSON blob -> flat")

    heads, head_cols, children = image_predictions(images)
    # Every hierarchy parent must be a scored head.
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
  JSON is flattened to usable columns; no values are removed.
  The hierarchy comes from each `classification` chain; `nutrient-related issue`
  is a taxonomy label outside the scored classes.
  The pipeline parses data/fyta_images.csv directly; images_flattened.csv is for
  consumers.""")

    # ================================================================== TASK 4
    h("4a. SOURCE - do the four sources agree?")

    # Compare the same assessment with the proven F2 clock offset; only values vary.
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
    print(f"     one log_type per phrase        {bool(a['log phrase -> one log_type'])} (F11)")
    print("     do they line up with sensors?  no - the two were never connected (F11)")

    print("\n-- 3. image predictions  model output")
    print(f"     internally consistent          {bool(a['is_healthy == (prob > 0.5)'])}"
          f"   is_healthy is exactly (probability > 0.5)")
    print(f"     agree with the sensors?        yes - r = {a['r(Water deficiency, dryness)']:.2f}"
          f" vs dryness")
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
          f"(max move {arms['delta'].abs().max():.3f}). Full table: "
          f"out/task4_source_assessment.csv")

    print("""
  Use water heads as a feature. Vendor lineage must establish whether the image
  model consumed VWC or one generator emitted both; `is_healthy` stays withheld.
  The 14 phrases across 49 rows are one-to-one; pin model_version and fail on
  unknown heads.""")

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
    print(plant_summary(features).to_string())

    features.to_csv(OUT / "plant_features.csv", index=False)
    print("\n  published: plant_features.csv")

    print("""
  F10: UP-1001 and UP-1003 retain two probes each; `vwc_delta` exposes their gap.
  F13: `substrate` has no effective dating, so a repot is invisible. D7 and D11
  must resolve that before timestamp-level comparison.

  The table contains cleaned sensor channels and plant metadata. It excludes 49
  log rows and 28 photos from 11,903 fifteen-minute rows; consumers join AS-OF
  with an explicit tolerance.

  F7's 48.5-hour outage remains 193 absent rows in UP-1004's `missing` column;
  `gap_minutes` flags the following row. `missing` counts unreported slots and
  `probes_filled` counts delivered rows with every probe: UP-1003 is 0.324,
  rather than 0.976 for its first probe, because SENS-06 is frozen for 1,344
  slots. UP-1004 is missing 9.6% of its grid and filled within the 90.4% it
  delivered.""")

    # ================================================================== TASK 6
    h("6a. TRIANGULATION - can three sources confirm a fertilising event?")

    tri = triangulate(cleaned, features, contextual, heads)
    shown = tri.assign(fertilised=tri["fertilised"].dt.strftime("%m-%d %H:%M"),
                       image=tri["image"].dt.strftime("%m-%d %H:%M"))
    print(shown[["log", "plant", "fertilised", "d_ec_sigma", "probe_leg",
                 "image", "hours_off", "nutrient_def", "sensor_leg", "model_leg"]]
          .to_string(index=False))
    print("\n  sigma is per probe and the leg reads every probe the plant owns; "
          "`probe_leg` names the one that moved most.\n  `not testable` means a "
          "window had no baseline or no response, which is not a failed test.")
    for _, r in shown.iterrows():
        print(f"    {r['log']}  {r['leg_detail']}")
    tri.to_csv(OUT / "task6_triangulation.csv", index=False)

    legs = (f"{int(tri['sensor_leg'].eq('rises').sum())} with an EC rise, "
            f"{int(tri['model_leg'].eq('responds').sum())} with a model response, "
            f"{int(tri['model_leg'].eq('no post-event image').sum())} with no photo after the event")
    print(f"""
  {len(tri)} fertilising logs: {legs}.

  Five events screened at 3 sigma against each probe's step noise did not
  establish corroboration. The test has low power: a response can fall below the
  threshold, timing is unknown (F11), two of five EC deltas are negative, and
  the nutrient head never exceeds 0.073; no leg shows a detectable signal.

  In UP-1002, EC climbs 1,289 uS/cm across the record, starting ten days after
  the feed as SENS-03 gain drift (F4), outside the event window.""")

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
  This is a within-probe feature: substrate calibration remains unresolved (F13,
  D7), and differentiating reported = a * true + b retains gain a. Per-step rates
  amplify per-reading noise (a 0.4 %VWC jitter over 15 minutes reads as 38 %/day),
  so the median is taken over a full day. Positive = drying.

  SENS-04 is {per_dev.loc['SENS-04', 'median']:.1f} %/day against 3-6 for the
  fleet. Its ratio remains useful under an unknown shared gain; 21% of readings
  exceed the 65% spec ceiling (F5), with cause unclassified.""")

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
  A lookup, not a classifier: 14 phrases across 49 rows already map one-to-one
  to log_type. The vocabulary is closed; 1 of 14 phrases contains a number and
  one volume. F11 leaves the logs unaligned with sensor time.""")

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


class _Tee:
    """Writes stdout to the terminal and out/run.log."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for st in self.streams:
            st.write(text)

    def flush(self):
        for st in self.streams:
            st.flush()


if __name__ == "__main__":
    import sys

    # Create out/ before opening run.log.
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "run.log", "w") as log:
        sys.stdout = _Tee(sys.stdout, log)
        try:
            main()
        finally:
            sys.stdout = sys.__stdout__
