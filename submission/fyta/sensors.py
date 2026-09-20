"""Tasks 1-2: data inventory and defect detection.

Task 1 describes delivered rows, timestamps, coverage, declared keys, and
plots. Task 2 applies independent detectors for ranges, clocks, unit scale,
drift, duplicate keys, frozen channels, join fan-out, and event alignment.
The same detector outputs feed the notebook and run log.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .domain import (CADENCE, CHANNELS, CLOCK_OFFSET_H, FROZEN_MIN_RUN,
                    LEGITIMATE_PLATEAU, SPEC)

# --------------------------------------------------------------------- Task 1

def parse_timestamps(raw: pd.Series) -> pd.Series:
    """Parse ISO and DD/MM timestamps; reject every other format.

    Coercion would turn a new source format into a silent `NaT`.
    """
    # Preserve source text until parsing succeeds. The regexes intentionally
    # accept only the two delivered layouts, then the slash-date assertion proves
    # whether day-first order is justified for this batch.
    text = raw.astype(str)
    iso = text.str.match(r"^\d{4}-\d{2}-\d{2} ").fillna(False).astype(bool)
    dmy = text.str.match(r"^\d{1,2}/\d{1,2}/\d{4} ").fillna(False).astype(bool)

    unknown = ~(iso | dmy)
    if unknown.any():
        raise ValueError(
            f"{int(unknown.sum())} timestamp(s) match no known format, "
            f"first few: {text[unknown].head(3).tolist()}"
        )

    out = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns]")
    out[iso] = pd.to_datetime(text[iso], format="%Y-%m-%d %H:%M:%S")
    out[dmy] = pd.to_datetime(text[dmy], format="%d/%m/%Y %H:%M")

    # Slash dates are day-first only when a first field exceeds 12. Skip the
    # assertion when no slash dates exist.
    if dmy.any():
        first = pd.to_numeric(text[dmy].str.extract(r"^(\d{1,2})/")[0], errors="coerce")
        assert first.max() > 12, (
            "day-first is unproven on this input - every slash date is parseable "
            "both ways, so the ordering is a guess")

    return out


def check_grid(sensor: pd.DataFrame, cadence: pd.Timedelta) -> None:
    """Assert per-device spacing and grid phase.

    Spacing misses a uniform clock shift; phase catches it. Day/month ambiguity
    can still land on the grid and is checked in `parse_timestamps`.
    """
    # Modal spacing checks cadence within each device. Phase checks every
    # timestamp against the cadence origin, so a fleet shifted together still
    # fails even though successive gaps remain regular.
    for device, g in sensor.groupby("device_id", sort=True):
        modal = g["ts"].diff().dropna().mode()
        assert len(modal) and modal.iloc[0] == cadence, (
            f"{device}: modal gap {modal.tolist() if len(modal) else None} != {cadence}"
        )
    # Use seconds since midnight so cadences over an hour also work.
    seconds = (sensor["ts"].dt.hour * 3600 + sensor["ts"].dt.minute * 60
               + sensor["ts"].dt.second)
    off = (seconds % int(cadence.total_seconds())).ne(0) | sensor["ts"].dt.microsecond.ne(0)
    assert not off.any(), (
        f"{int(off.sum())} reading(s) are off the {cadence} grid -- spacing alone "
        f"cannot see this: {sensor.loc[off, 'ts'].head(3).tolist()}"
    )


def device_coverage(sensor: pd.DataFrame, cadence: pd.Timedelta) -> pd.DataFrame:
    """Coverage and observed-grid compliance per device.

    `rows` includes duplicate delivery; `delivered` counts distinct timestamps;
    `surplus` is their difference. `slots_due` spans a device's first and last
    delivered reading, and `missing` measures holes within that observed span.
    Completeness therefore describes delivered coverage, not installation
    coverage: activation time from the platform would be required for that.
    """
    rows = []
    for device, g in sensor.groupby("device_id", sort=True):
        span = g["ts"].max() - g["ts"].min()
        due = int(span / cadence) + 1
        delivered = g["ts"].nunique()
        gaps = g["ts"].drop_duplicates().diff().dropna()
        rows.append({
            "device": device, "rows": len(g), "slots_due": due, "delivered": delivered,
            "span_days": round(span.total_seconds() / 86400, 2),
            "first": g["ts"].min(), "last": g["ts"].max(),
            "missing": due - delivered, "surplus": len(g) - delivered,
            "completeness": round(delivered / due, 4),
            "gaps": int((gaps > cadence).sum()),
            "longest_gap": gaps.max() if len(gaps) else pd.Timedelta(0),
        })
    return pd.DataFrame(rows)


#: Task 1 columns (present data).
COVERAGE_COLS = ["device", "rows", "slots_due", "span_days", "first", "last"]


COMPLIANCE_COLS = ["device", "slots_due", "delivered", "missing", "surplus",
                   "completeness", "gaps", "longest_gap"]


def key_uniqueness(declared: list) -> pd.DataFrame:
    """Which declared keys are actually unique. A schema fact, not a finding."""
    return pd.DataFrame(
        [{"table": name, "declared_grain": "+".join(keys),
          "unique": not df.duplicated(keys).any()}
         for name, df, keys in declared]
    )


def plot_fleet(sensor: pd.DataFrame):
    """Build the fleet overview. Caller saves or displays it."""
    fig, axes = plt.subplots(len(CHANNELS), 1, figsize=(16, 16), sharex=True)
    for ax, channel in zip(axes, CHANNELS):
        for device, g in sensor.groupby("device_id", sort=True):
            ax.plot(g["ts"], g[channel], lw=0.7, label=device)
        ax.set_ylabel(channel, fontsize=9)
        ax.grid(alpha=0.3)
        ax.legend(ncol=8, fontsize=7, loc="upper left")
    fig.tight_layout()
    return fig


def plot_by_device(sensor: pd.DataFrame, mapping: pd.DataFrame, contextual: pd.DataFrame):
    """Moisture per device, with the user's event logs overlaid."""
    plant_of = mapping.set_index("device_id")["user_plant_id"]
    kinds = [("watering", "crimson"), ("fertilising", "seagreen"),
             ("repotting", "purple"), ("light", "orange")]
    devices = sorted(sensor["device_id"].unique())

    fig, axes = plt.subplots(len(devices), 1, figsize=(15, 18), sharex=True)
    for ax, device in zip(axes, devices):
        g = sensor[sensor["device_id"] == device]
        ax.plot(g["ts"], g["soil_moisture_vwc"], lw=0.8, color="steelblue")
        events = contextual[contextual["user_plant_id"] == plant_of[device]]
        for kind, colour in kinds:
            for t in events.loc[events["log_type"] == kind, "created_at"]:
                ax.axvline(t, color=colour, alpha=0.55, lw=0.8, ls="--")
        ax.set_ylabel(device, fontsize=8)
        ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig



# --------------------------------------------------------------------- Task 2

def spec_violations(sensor: pd.DataFrame) -> pd.DataFrame:
    """Classify published-range violations by contiguous run.

    An isolated reading and a sustained excursion require different treatment:
    the former can be a glitch, while removing the latter can erase a regime.
    """
    rows = []
    for channel, (lo, hi) in SPEC.items():
        for device, g in sensor.groupby("device_id", sort=True):
            g = g.sort_values("ts")
            bad = (g[channel] < lo) | (g[channel] > hi)
            n = int(bad.sum())
            if not n:
                continue
            # Run-length encoding counts samples in sustained excursions, not
            # just runs.
            b = bad.to_numpy()
            edges = np.flatnonzero(np.diff(np.r_[False, b, False].astype(int)))
            lengths = edges[1::2] - edges[::2]
            isolated, in_runs = int((lengths == 1).sum()), int(lengths[lengths >= 2].sum())
            assert isolated + in_runs == n, "run encoding lost or invented samples"
            rows.append({
                "device": device, "channel": channel, "n_bad": n,
                "pct": round(100 * n / len(g), 1),
                "runs": int(len(lengths)), "isolated": isolated, "in_runs": in_runs,
                "longest_run": int(lengths.max()),
                "min": round(g[channel].min(), 2), "max": round(g[channel].max(), 2),
            })
    return pd.DataFrame(rows)


def align_clocks(sensor: pd.DataFrame) -> pd.DataFrame:
    """Put `ts` onto local time with declared offsets.

    The returned copy permits detectors to use local time without mutating
    source data. Keeping the operation here prevents a detector from applying an
    offset twice.
    """
    out = sensor.copy()
    out["ts"] = out["ts"] - pd.to_timedelta(
        out["device_id"].map(CLOCK_OFFSET_H).fillna(0), unit="h")
    return out


def dark_hour_spikes(sensor: pd.DataFrame, channel: str = "light_par",
                     dark_hours=(22, 23, 0, 1, 2, 3, 4),
                     quiet: float = 0.25) -> pd.DataFrame:
    """Find isolated dark-hour light spikes.

    Night light can be real: a lamp produces consecutive samples. This detector
    instead requires a positive dark-hours reading that is far above both
    neighbouring samples using `quiet`; range checks cannot distinguish that
    temporal pattern.
    """
    # The detector requires both adjacent values below `quiet * value`; boundary
    # samples lack one neighbour and remain unflagged. It returns the sample and
    # neighbour values so review can distinguish a transient from sustained light.
    rows = []
    for device, g in sensor.groupby("device_id", sort=True):
        g = g.sort_values("ts").set_index("ts")
        s = g[channel]
        dark = s.index.hour.isin(list(dark_hours))
        alone = (s.shift(1) < s * quiet) & (s.shift(-1) < s * quiet)
        for ts, value in s[dark & alone & (s > 0)].items():
            rows.append({"device": device, "ts": ts, "channel": channel,
                         "value": round(float(value), 1),
                         "neighbours": f"{s.shift(1)[ts]:.1f} / {s.shift(-1)[ts]:.1f}"})
    return pd.DataFrame(rows)


def clock_offsets(sensor: pd.DataFrame, max_shift: int = 6) -> pd.DataFrame:
    """Estimate each device's clock offset from the shared daylight curve."""
    hourly = (sensor.pivot_table(index="ts", columns="device_id", values="light_par")
              .resample("1h").mean())
    rows = []
    for device in hourly.columns:
        ref = hourly.drop(columns=device).median(axis=1)
        corr = {s: hourly[device].shift(-s).corr(ref) for s in range(-max_shift, max_shift + 1)}
        best = max(corr, key=lambda s: np.nan_to_num(corr[s], nan=-2))
        rows.append({"device": device, "offset_h": best, "corr_at_zero": round(corr[0], 4),
                     "corr_when_aligned": round(corr[best], 4)})
    return pd.DataFrame(rows)


def unit_scale(sensor: pd.DataFrame, channel: str = "soil_temp_c") -> pd.DataFrame:
    """Measure per-device median absolute changes for a channel.

    Differencing removes an additive calibration offset and preserves a
    multiplicative unit scale.
    """
    jitter = (sensor.sort_values("ts").groupby("device_id")[channel]
              .apply(lambda s: s.diff().abs().median()))
    return pd.DataFrame({"device": jitter.index,
                         "median_abs_delta": jitter.round(3).values,
                         "ratio_vs_fleet": (jitter / jitter.median()).round(2).values})


def detect_unit_outliers(sensor: pd.DataFrame, tol: float = 0.15) -> set:
    """Return devices whose jitter ratio indicates a unit-scale outlier.

    Fahrenheit scales Celsius differences by 1.8; a calibration offset leaves
    jitter unchanged. `tol` is the permitted distance from the fleet ratio of
    1. Detection stays separate from `UNIT_FIXES`, because automatic fitted
    conversions can silently damage a valid device.
    """
    # Ratios use each device's median absolute consecutive difference against the
    # fleet median. A device farther than `tol` from 1 is returned for explicit
    # review; this function never selects a correction.
    scale = unit_scale(sensor)
    return set(scale.loc[scale["ratio_vs_fleet"].sub(1).abs() > tol, "device"])


def screen_drift(sensor: pd.DataFrame, channels, days: int = 7) -> pd.DataFrame:
    """Screen channel levels against their own early baseline.

    Resample to daily means, compare the first and last `days` medians, then
    scale the shift by median absolute day-to-day change. A channel needs 14
    daily observations so both windows have evidence; zero noise has no ratio.
    """
    rows = []
    for device, g in sensor.groupby("device_id", sort=True):
        daily = g.sort_values("ts").set_index("ts")[list(channels)].resample("D").mean()
        for channel in channels:
            series = daily[channel].dropna()
            if len(series) < 14:
                continue
            early, late = series.iloc[:days].median(), series.iloc[-days:].median()
            noise = series.diff().abs().median()
            rows.append({"device": device, "channel": channel,
                         "early": round(early, 1), "late": round(late, 1),
                         "shift": round(late - early, 1),
                         "shift_vs_own_noise": round(abs(late - early) / noise, 1) if noise else None})
    return pd.DataFrame(rows).sort_values("shift_vs_own_noise", ascending=False)


#: Expected channel response and direction for each log type. `None` is
#: non-directional.
LOG_EXPECTATION = {
    "watering":    ("soil_moisture_vwc", "rises"),
    "fertilising": ("ec_us_cm",          "rises"),
    "light":       ("light_par",         "peak moves as the phrase says"),
    "repotting":   (None,                "some channel steps"),
}

#: Light phrases with a testable peak direction. Rotation has no implied
#: direction because distance from the window is unchanged.
LIGHT_DIRECTION = {"Moved closer to window": +1, "Too much direct sun, moved back": -1}


def log_alignment(sensor: pd.DataFrame, mapping: pd.DataFrame,
                  contextual: pd.DataFrame, window_h: int = 6,
                  sigma: float = 3.0) -> pd.DataFrame:
    """Test each logged event against its expected sensor response.

    The `sigma` threshold uses each channel's own step noise, so EC and moisture
    do not share an arbitrary absolute threshold. Every mapped probe is tested;
    a log matches when any probe responds. Logs lack device ids, so the result
    cannot attribute a response to one probe.
    """
    # For light logs, test phrase-specific daily peaks because the two supported
    # phrases expect opposite directions. Repotting compares 24-hour means;
    # directional events inspect changes in `window_h` after the log.
    rows = []
    for log_type, (channel, expectation) in LOG_EXPECTATION.items():
        logs = contextual[contextual["log_type"] == log_type]
        # Report light phrases separately because they imply opposite directions.
        groups = ([(text, logs[logs["text"] == text])
                   for text in sorted(set(logs["text"]) & set(LIGHT_DIRECTION))]
                  if log_type == "light" else [("", logs)])
        for text, group in groups:
            if group.empty:
                continue
            direction = LIGHT_DIRECTION.get(text) if text else None
            tested = matched = 0
            shifts = []
            for _, lg in group.iterrows():
                t = lg["created_at"]
                for device in sorted(mapping.loc[mapping["user_plant_id"]
                                                 == lg["user_plant_id"], "device_id"]):
                    g = sensor[sensor["device_id"] == device].sort_values("ts")
                    if g.empty:
                        continue
                    shift = pd.Timedelta(hours=CLOCK_OFFSET_H.get(device, 0))
                    if log_type == "repotting":
                        before = g.loc[(g["ts"] > t - pd.Timedelta(hours=24)) & (g["ts"] <= t)]
                        after = g.loc[(g["ts"] > t) & (g["ts"] <= t + pd.Timedelta(hours=24))]
                        if len(before) < 8 or len(after) < 8:
                            continue
                        tested += 1
                        matched += int(any(
                            abs(after[c].mean() - before[c].mean()) > sigma * g[c].diff().std()
                            for c in CHANNELS))
                    elif log_type == "light":
                        peak = g.set_index(g["ts"] - shift)["light_par"].resample("1D").max()
                        b = peak[peak.index < t.normalize()].tail(3).mean()
                        a = peak[peak.index >= t.normalize()].head(3).mean()
                        if pd.isna(a) or pd.isna(b):
                            continue
                        tested += 1
                        shifts.append(a - b)
                        matched += int((a - b) * direction > sigma * peak.std())
                    else:
                        movement = pd.Series(g[channel].to_numpy(),
                                             index=g["ts"] - shift).diff()
                        window = movement[(movement.index > t)
                                          & (movement.index <= t + pd.Timedelta(hours=window_h))]
                        if window.empty:
                            continue
                        tested += 1
                        matched += int(window.max() > sigma * g[channel].diff().std())
            rows.append({
                "log_type": log_type,
                "phrase": text or "(all)",
                "logs": len(group), "tested": tested, "responded": matched,
                "expected": (
                    f"{channel} peak {'rises' if direction and direction > 0 else 'falls'}"
                    if direction else
                    f"{channel} {expectation}" if channel else expectation),
                "mean_shift": round(float(np.mean(shifts)), 1) if shifts else None,
            })
    return pd.DataFrame(rows)


def grain_violations(sensor: pd.DataFrame) -> dict:
    """Rows that break the declared key, split redundant vs conflicting."""
    keys = ["device_id", "ts"]
    payload = [c for c in sensor.columns if c not in keys + ["timestamp"]]
    dup = sensor[sensor.duplicated(keys, keep=False)]
    return {
        "rows_with_a_twin": len(dup),
        "superfluous": int(sensor.duplicated(keys).sum()),
        "conflicting": int(dup.groupby(keys)[payload].nunique().gt(1).any(axis=1).sum()),
    }


def join_fanout(sensor: pd.DataFrame, contextual: pd.DataFrame,
                images: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Row count before and after joining each fact table to the mapping."""
    rows = []
    for name, left, on in [("contextual", contextual, "user_plant_id"),
                           ("images", images, "user_plant_id"),
                           ("sensor", sensor, "device_id")]:
        after = len(left.merge(mapping, on=on))
        rows.append({"fact_table": name, "join_on": on, "before": len(left),
                     "after": after, "fans_out": after != len(left)})
    return pd.DataFrame(rows)




def frozen_windows(sensor: pd.DataFrame, min_run: int = FROZEN_MIN_RUN) -> pd.DataFrame:
    """Find unchanged runs long enough to indicate a dead channel.

    `min_run` defaults to `FROZEN_MIN_RUN`. `LEGITIMATE_PLATEAU` excludes values
    that a channel may honestly hold, including nighttime PAR at zero. A frozen
    run records its device, channel, first and last timestamps, sample count,
    and fixed value for cleaning.

    ponytail: a light sensor that dies at exactly 0 is therefore missed here. The
    check that would catch it is a daytime-zero test -- PAR at 0 while the same
    device's own history shows light at that hour -- which is a second detector,
    not a wider bound. No device in this sample is affected.
    """
    # Grouping on changes identifies runs independently for each device and
    # channel. A plateau listed in `LEGITIMATE_PLATEAU` skips only when every
    # reading in the run equals that allowed value.
    rows = []
    for device, g in sensor.groupby("device_id", sort=True):
        g = g.sort_values("ts")
        for channel in CHANNELS:
            floor = LEGITIMATE_PLATEAU.get(channel)
            for _, part in g.groupby((g[channel].diff() != 0).cumsum()):
                if len(part) < min_run:
                    continue
                if floor is not None and bool((part[channel] == floor).all()):
                    continue
                rows.append({"device": device, "channel": channel,
                             "first": part["ts"].iloc[0], "last": part["ts"].iloc[-1],
                             "samples": len(part), "frozen_at": part[channel].iloc[0]})
    return pd.DataFrame(rows)


FINDINGS = [
    ("F1", "SENS-07 soil_temp_c is Fahrenheit, not Celsius", "SENS-07",
     "jitter ratio 1.82 vs fleet; /1.8 gives 0.400 exactly; mean and sd also "
     "match after conversion",
     "high", "data problem - unit error",
     "convert to Celsius; ask firmware whether the payload or the conversion is wrong"),

    ("F2", "SENS-07 on a +2h clock, and DD/MM while the fleet is ISO", "SENS-07",
     "light cross-correlation 0.802 -> 0.9997 when shifted 2h",
     "high", "data problem - clock/timezone",
     "ask firmware; testable - a timezone offset becomes +1h in winter"),

    ("F3", "SENS-06 moisture frozen at exactly 25.01 for 14 days", "SENS-06",
     "longest constant run 1344 samples; its other four channels all keep moving",
     "high", "sensor fault - dead channel",
     "null the frozen window; do not treat 25.01 as a reading"),

    ("F4", "SENS-03 EC climbs monotonically, no logged cause", "SENS-03",
     "a straight climb from 06-11 -- see the drift fit in the evidence above for "
     "the onset, rate and R2; 354 out-of-range readings in 17 runs, 346 of them "
     "inside a run (longest 307), only 8 isolated; no fertilising log near onset; "
     "the four devices that WERE fertilised show no EC response (section 6a)",
     "high", "sensor fault - drift",
     "exclude EC for this device, or recalibrate; ask calibration whether a "
     "straight-line climb is possible"),

    ("F5", "SENS-04 moisture exceeds the instrument's specified 65% ceiling", "SENS-04",
     "431 readings (21.4%) above 65%, peaking 107.12. Every one sits in a run of two "
     "or more -- 11 runs, longest 44, ZERO isolated -- so this is a sustained "
     "excursion, not glitches; jitter 0.47 vs 0.14 fleet; dry-down 38.4 %VWC/day "
     "vs 3-6 fleet (the Task 8 signal)",
     "high", "unknown - fault or different physical setup",
     "measure pot size and probe seating, or gravimetric reference; ask horticulture"),

    ("F6", "SENS-08 emits single-sample values that cannot be explained", "SENS-08",
     "22 are physically impossible -- 12 moisture below 0, 10 humidity above 100 -- "
     "and are emptied. 8 more are possible but implausible: a light reading at "
     "night, bracketed by zeros. The other seven devices read exactly 0 at all 8 "
     "moments, so it was not a shared light -- but a lamp near one pot would do it",
     "low", "22 sensor artefacts; 8 unresolved",
     "empty the impossible 22; keep and flag the 8 -- a real light would be deleted "
     "by emptying. Ask firmware at D13"),

    ("F7", "SENS-05 missing 193 slots (48.5h)", "SENS-05",
     "coverage ledger against the expected 15-min grid",
     "medium", "data problem - availability",
     "leave the gap. The ~320-reading buffer makes 193 slots stay WITHIN capacity, "
     "so recovery was possible -- an upper bound, not evidence the readings "
     "survived. Whether they did needs transport telemetry, not arithmetic. "
     "Reported as absence; cause unresolved"),

    ("F8", "SENS-08 has 15 superfluous duplicate rows", "SENS-08",
     "identical payloads, 0 conflicting",
     "low", "data problem - at-least-once redelivery",
     "deduplicate; lossless because nothing disagrees"),

    ("F9", "user_plant_id is not unique, so log/image joins multiply rows", "all",
     "contextual 49->67, images 28->35; the sensor join is clean, which is the trap",
     "medium", "schema problem",
     "dedupe the mapping to one row per plant before joining"),

    ("F10", "Two plants have two sensors, and the pairs do not correlate", "UP-1001, UP-1003",
     "r = -0.076 and +0.103 over the full overlap; excluding SENS-06's 1,344 "
     "frozen samples the second is +0.140. Both are near zero, so the probes do "
     "not move together either way -- the frozen stretch pulls the figure toward "
     "zero rather than hiding a stronger relationship. Same-pot probes share a "
     "reservoir and must move together",
     "high", "unknown - real config or mapping bug",
     "ask product whether the app allows two sensors per plant; do not average"),

    ("F11", "Watering logs and sensor events are unrelated", "all plants",
     "31 of 34 watering logs have no moisture rise within 6h -- and 3 hits is "
     "below the ~3.5 expected by chance, so the matches carry no information. "
     "All four log types were tested against the channel their own event should "
     "move, and none lines up. LIGHT CONTRADICTS: 'Moved closer to window' moves "
     "the daily light peak DOWN by 4.4 on average, the opposite of what it claims "
     "(n=3, within the daily sd of 5.3 -- suggestive, not proof). The sensor's own "
     "rises land exactly on the hour -- 35 of 37 excluding SENS-08 -- while the "
     "logs are all at human times, so the two look independently generated",
     "high", "label problem",
     "do not use logs as event ground truth; ask firmware whether the device does "
     "anything at 00:00"),

    ("F12", "Environment is near-identical across all eight devices", "all",
     "mean pairwise r on aligned time: light 0.991, temp 0.974, humidity 0.937 -- "
     "against moisture 0.201 and EC -0.005. Moisture is an order of magnitude "
     "lower because each pot is its own reservoir",
     "medium", "artefact - shared or generated ambient series",
     "use the fleet as the reference for the shared channels -- a deviating device "
     "is visible against a tight signal -- and read a change common to all eight "
     "as one event, not eight faults. Leave temp/light/humidity peer tests usable; "
     "ask product (D10) whether these devices really share one environment"),

    ("F13", "substrate_label is a snapshot with no effective dating", "UP-1006",
     "one label per device for the whole window, yet UP-1006 logged "
     "'Fresh substrate + repot' on 06-13 and the label never moves",
     "medium", "semantic problem - calibration parameter without history",
     "ask whether that pot's substrate actually changed; if it did, pre-06-13 VWC "
     "was produced by a different conversion curve than this label implies"),
]


FINDING_COLS = ["id", "finding", "device", "detected_by", "severity", "class", "next"]


def findings_frame() -> pd.DataFrame:
    """The classification as a table. Same rows the notebook renders."""
    return pd.DataFrame(FINDINGS, columns=FINDING_COLS)


#: How each finding was caught and the check structurally blind to it.
DETECTION_COVERAGE = [
    ("F1", "Fahrenheit temperature", "jitter ratio = 1.8 (the F signature)",
     "correlation -- affine-invariant, blind to scale"),
    ("F2", "clock +2h on SENS-07", "light cross-correlation vs peers",
     "cadence check -- grid is regular, just offset"),
    ("F3", "moisture frozen at 25.01", "run-length + cross-channel",
     "range check -- 25.01 is a legal value"),
    ("F4", "SENS-03 EC drift", "early-vs-late median vs own noise",
     "correlation -- EC has no shared signal"),
    ("F5", "SENS-04 above the spec ceiling", "spec range + jitter + dry-down",
     "null check -- the readings are present"),
    ("F6", "single-sample glitches and one unexplained pattern",
     "range check; light spikes found by comparing against neighbours",
     "run-length -- they are isolated samples"),
    ("F7", "SENS-05 missing 193 slots", "expected-slot grid",
     "null count -- there are zero nulls"),
    ("F8", "15 duplicate rows on SENS-08", "key cardinality",
     "value checks -- the duplicates are all legal"),
    ("F9", "user_plant_id fans out on join", "join cardinality, before joining",
     "value checks -- the data is fine, the key is not"),
    ("F10", "two sensors on one plant", "inter-device correlation",
     "single-device checks -- each looks healthy alone"),
    ("F11", "watering logs vs the sensor", "event detection vs the log table",
     "sensor-only or log-only -- each consistent"),
    ("F12", "environment near-identical", "cross-device correlation per channel",
     "single-device checks; also range checks"),
    ("F13", "substrate label, no effective dating", "manual log cross-reference",
     "everything -- needs the app's config history"),
]

DETECTION_COLS = ["id", "finding", "caught_by", "missed_by"]


def detection_coverage_frame() -> pd.DataFrame:
    """Detection coverage as a table. Same rows the notebook renders."""
    return pd.DataFrame(DETECTION_COVERAGE, columns=DETECTION_COLS)


def ec_drift_fit(sensor: pd.DataFrame, device: str = "SENS-03",
                 sigma: float = 3.0) -> dict:
    """Fit EC drift from its detected onset.

    The initial quarter establishes a baseline. A point must exceed that median
    by `sigma` baseline step deviations before it starts the ramp. The returned
    ramp slope and R² describe only post-onset data; the whole-record rate remains
    available to show how the initial flat period changes the estimate.
    """
    g = sensor[sensor["device_id"] == device].sort_values("ts")
    ec = g["ec_us_cm"]
    baseline = ec.iloc[:len(ec) // 4]
    climbing = ec > baseline.median() + sigma * baseline.diff().std()
    if not climbing.any():
        return {"device": device, "onset": None, "slope_per_day": None, "r2": None,
                "whole_record_per_day": None}
    onset = g.loc[climbing.idxmax(), "ts"]
    ramp = g.loc[g["ts"] >= onset]
    days = (ramp["ts"] - onset).dt.total_seconds() / 86400
    slope, intercept = np.polyfit(days, ramp["ec_us_cm"], 1)
    resid = float(((ramp["ec_us_cm"] - (slope * days + intercept)) ** 2).sum())
    total = float(((ramp["ec_us_cm"] - ramp["ec_us_cm"].mean()) ** 2).sum())
    whole = np.polyfit((g["ts"] - g["ts"].min()).dt.total_seconds() / 86400, ec, 1)[0]
    return {"device": device, "onset": onset,
            "ramp_per_day": round(float(slope), 1), "r2": round(1 - resid / total, 4),
            "whole_record_per_day": round(float(whole), 1)}


def cross_device_correlation(sensor: pd.DataFrame, channels=None) -> pd.DataFrame:
    """Mean pairwise correlation between devices by channel.

    Pivoting aligns readings at each timestamp, then the upper triangle removes
    self-correlation and duplicate pair directions. Shared ambient channels give
    a fleet reference for device deviations; moisture remains more local to each
    pot. A fleet-wide change is one event, rather than eight simultaneous faults.
    """
    channels = CHANNELS if channels is None else channels
    rows = []
    for channel in channels:
        wide = sensor.pivot_table(index="ts", columns="device_id", values=channel)
        corr = wide.corr()
        # Upper triangle only: the diagonal is 1 by construction and the matrix
        # is symmetric, so including either would inflate the mean.
        upper = corr.where(~np.tril(np.ones(corr.shape), k=0).astype(bool))
        rows.append({"channel": channel, "mean_pairwise_r": upper.stack().mean()})
    return pd.DataFrame(rows).round(3)


def rise_timing(sensor: pd.DataFrame, threshold: float = 1.0) -> pd.DataFrame:
    """Count moisture rises above `threshold` by clock minute.

    The output is evidence about timing, not an irrigation detector. A physical
    watering event is not tied to a clock minute; repeated :00 rises indicate a
    generator or scheduler artefact.
    """
    rows = []
    for device, g in sensor.groupby("device_id", sort=True):
        g = g.sort_values("ts")
        rises = g.loc[g["soil_moisture_vwc"].diff() > threshold, "ts"]
        rows.append({"device": device, "rises": len(rises),
                     "on_the_hour": int((rises.dt.minute == 0).sum())})
    return pd.DataFrame(rows)


def colocated_correlation(sensor: pd.DataFrame, mapping: pd.DataFrame,
                          channel: str = "soil_moisture_vwc") -> pd.DataFrame:
    """Correlate probes mapped to the same plant.

    Each pair aligns by timestamp and drops missing values before correlation.
    Co-located probes should share a water reservoir; near-zero correlation
    leaves the mapping or placement unresolved.
    """
    rows = []
    for plant, g in mapping.groupby("user_plant_id", sort=True):
        devices = sorted(g["device_id"])
        if len(devices) < 2:
            continue
        wide = (sensor[sensor["device_id"].isin(devices)]
                .pivot_table(index="ts", columns="device_id", values=channel))
        for a, b in zip(devices, devices[1:]):
            pair = wide[[a, b]].dropna()
            rows.append({"plant": plant, "a": a, "b": b, "n": len(pair),
                         "r": round(float(pair[a].corr(pair[b])), 3)})
    return pd.DataFrame(rows)


#: Evidence-table descriptions keyed by their rendered title.
EVIDENCE_NOTES = {
    "declared grain violated":
        "rows sharing a key. Identical payloads are a redelivery; differing ones "
        "are unorderable. Both kept.",
    "joins that multiply rows":
        "row count before and after joining each table to the mapping. A rise "
        "means the join key is not unique on the right.",
    "coverage against the grid":
        "every slot each device was due, as delivered / missing / surplus. Row "
        "counts hide a device that is half-present.",
    "outside published range":
        "readings outside the spec. `runs` = separate stretches; `isolated` = a "
        "stretch of one; `in_runs` = inside a stretch of 2+.",
    "dark-hour light spikes":
        "a light reading at night its own neighbours cannot explain. Flagged, not "
        "deleted -- a lamp would be a real observation.",
    "frozen channels":
        "runs of an unchanged value long enough to be a dead channel. Only a fault "
        "if the device's OTHER channels keep moving.",
    "clock offsets":
        "each device's clock, from sliding its daylight curve against the fleet's. "
        "Correlation at zero shift vs at the best shift.",
    "temperature unit scale":
        "how much each device's temperature jitters. A unit change scales jitter "
        "by 1.8, which correlation cannot see.",
    "EC drift fit":
        "where a device's EC starts climbing, and how fast. The onset must be "
        "found first -- a whole-record fit halves the rate.",
    "drift vs own history (top 6 of 40)":
        "channels whose recent level has left their own band, ranked against that "
        "channel's own noise rather than the fleet's.",
    "watering logs vs sensor":
        "for each log type, does the channel its own event should move, move? "
        "F11 was first claimed from the watering leg alone.",
    "cross-device correlation":
        "mean pairwise r between devices, per channel. High = one shared ambient "
        "signal, so a deviating device stands out against a tight reference -- "
        "and a change common to every device is one event, not eight faults.",
    "where a moisture rise lands":
        "the minute each rise falls on. A real watering does not care what minute "
        "it is; rises on :00 are a scheduler.",
    "co-located probes, same plant":
        "two probes on one plant share a reservoir, so they must move together. A "
        "near-zero r means they do not.",
    "moisture jitter by device":
        "median change between consecutive readings. A noisy or wrongly-scaled "
        "channel shows up as a ratio against the fleet.",
}


def evidence_tables(sensor: pd.DataFrame, mapping: pd.DataFrame, contextual: pd.DataFrame,
                    images: pd.DataFrame) -> dict:
    """Return each detector output keyed by its rendered title."""
    return {
        "declared grain violated": pd.DataFrame([grain_violations(sensor)]),
        "joins that multiply rows": join_fanout(sensor, contextual, images, mapping),
        "coverage against the grid": device_coverage(sensor, CADENCE)[COMPLIANCE_COLS],
        "outside published range": spec_violations(sensor),
        "dark-hour light spikes": dark_hour_spikes(align_clocks(sensor)),
        "frozen channels": frozen_windows(sensor)[
            ["device", "channel", "samples", "frozen_at", "first", "last"]],
        "clock offsets": clock_offsets(sensor),
        "temperature unit scale": unit_scale(sensor),
        # Top 6 of 40 by drift ratio; the tail is ordinary day-to-day movement.
        "drift vs own history (top 6 of 40)": screen_drift(sensor, CHANNELS).head(6),
        "watering logs vs sensor": log_alignment(sensor, mapping, contextual),
        # Use aligned time so SENS-07's two-hour offset does not lower ambient
        # correlations or conflate the result with F2.
        "EC drift fit": pd.DataFrame([ec_drift_fit(sensor)]),
        "cross-device correlation": cross_device_correlation(align_clocks(sensor)),
        "co-located probes, same plant": colocated_correlation(sensor, mapping),
        "where a moisture rise lands": rise_timing(sensor),
        "moisture jitter by device": unit_scale(sensor, "soil_moisture_vwc")[
            ["device", "median_abs_delta", "ratio_vs_fleet"]],
    }
