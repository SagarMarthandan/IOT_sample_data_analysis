"""Tasks 1-2: what the data is, and what is wrong with it.

Section banners below are greppable. Task 1 states what is PRESENT, Task 2 what
is WRONG -- the split the notebook and the run log both rely on.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .domain import CADENCE, CHANNELS, CLOCK_OFFSET_H, FROZEN_MIN_RUN, SPEC

# --------------------------------------------------------------------- Task 1

def parse_timestamps(raw: pd.Series) -> pd.Series:
    """Parse the two date formats present. Raise on anything else.

    Coercing would turn a format change into silent NaT.
    """
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

    # `01/06/2026` is ambiguous. Day-first is provable, not assumed: a first
    # field above 12 cannot be a month.
    first = pd.to_numeric(text[dmy].str.extract(r"^(\d{1,2})/")[0], errors="coerce")
    assert first.max() > 12, "day-first is unproven on this input - parse is ambiguous"

    return out


def check_grid(sensor: pd.DataFrame, cadence: pd.Timedelta) -> None:
    """Assert every device is on the declared grid.

    Does NOT catch the day/month ambiguity: a uniform misread still lands on
    the grid. That one is proven by impossibility in parse_timestamps.
    """
    for device, g in sensor.groupby("device_id", sort=True):
        modal = g["ts"].diff().dropna().mode()
        assert len(modal) and modal.iloc[0] == cadence, (
            f"{device}: modal gap {modal.tolist() if len(modal) else None} != {cadence}"
        )


def device_coverage(sensor: pd.DataFrame, cadence: pd.Timedelta) -> pd.DataFrame:
    """What each device covers, and how that compares to the grid it was due.

    One computation, split at the *presentation*: Task 1 prints the coverage
    columns, Task 2 prints the compliance columns. The task boundary belongs
    where the reader meets it, not duplicated into a second groupby loop.
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


#: Columns Task 1 shows (what is present) vs Task 2 shows (what is wrong).
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
    """Readings outside the published range, split isolated vs sustained.

    The split is the treatment decision, not a detail: an isolated impossible
    sample is a glitch you null, while a sustained excursion is a regime change
    and nulling it would delete real history.
    """
    rows = []
    for channel, (lo, hi) in SPEC.items():
        for device, g in sensor.groupby("device_id", sort=True):
            g = g.sort_values("ts")
            bad = (g[channel] < lo) | (g[channel] > hi)
            n = int(bad.sum())
            if not n:
                continue
            adjacent = int((bad & bad.shift(fill_value=False)).sum())
            rows.append({
                "device": device, "channel": channel, "n_bad": n,
                "pct": round(100 * n / len(g), 1),
                "isolated": n - adjacent, "in_runs": adjacent,
                "min": round(g[channel].min(), 2), "max": round(g[channel].max(), 2),
            })
    return pd.DataFrame(rows)


def align_clocks(sensor: pd.DataFrame) -> pd.DataFrame:
    """Put `ts` onto real local time, using the declared offsets.

    Kept separate from the checks so a check can never shift a timestamp twice:
    it uses whatever time it is handed, and only this function moves the clock.
    """
    out = sensor.copy()
    out["ts"] = out["ts"] - pd.to_timedelta(
        out["device_id"].map(CLOCK_OFFSET_H).fillna(0), unit="h")
    return out


def dark_hour_spikes(sensor: pd.DataFrame, channel: str = "light_par",
                     dark_hours=(22, 23, 0, 1, 2, 3, 4),
                     quiet: float = 0.25) -> pd.DataFrame:
    """A dark-hours light reading that its own neighbours cannot explain.

    Night light is **not wrong by itself** -- a person can switch a lamp on, and
    the sensor would correctly see it.

    What is wrong is a *single* 15-minute sample. A switched-on lamp persists: it
    appears in several consecutive readings. One sample bracketed by near-zero on
    both sides means the light was on for less than 15 minutes, several separate
    times, in the middle of the night.

    Magnitude checks cannot see this. PAR is rated to 2000, so both 589 and 232
    sit well inside spec, and a plain "no light at night" rule would flag
    legitimate lighting -- SENS-07 shows small *consecutive* dusk readings that
    are real.

    So the test uses **duration**, not magnitude: a reading is a glitch when it
    stands far above both of its neighbours.
    """
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
    """Channels written in different units show up as a constant scale vs peers.

    Jitter is the tell: Fahrenheit noise divided by 1.8 lands exactly on the
    Celsius fleet's. A plain offset would match the mean and fail this test.
    """
    jitter = (sensor.sort_values("ts").groupby("device_id")[channel]
              .apply(lambda s: s.diff().abs().median()))
    return pd.DataFrame({"device": jitter.index,
                         "median_abs_delta": jitter.round(3).values,
                         "ratio_vs_fleet": (jitter / jitter.median()).round(2).values})


def detect_unit_outliers(sensor: pd.DataFrame, tol: float = 0.15) -> set:
    """Devices whose jitter ratio marks them as a unit outlier.

    1.8 is the Fahrenheit signature: an affine transform scales differences by
    its slope, so a Fahrenheit channel jitters 1.8x a Celsius one. A pure offset
    would leave the jitter unchanged -- which is what separates a unit error
    from a calibration offset.

    Detection only. Correcting a fitted transform automatically would silently
    mangle data, so the fix stays explicit in UNIT_FIXES and the two are
    reconciled in audit().
    """
    scale = unit_scale(sensor)
    return set(scale.loc[scale["ratio_vs_fleet"].sub(1).abs() > tol, "device"])


def screen_drift(sensor: pd.DataFrame, channels, days: int = 7) -> pd.DataFrame:
    """Channels whose recent level has left their own historical band."""
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


def log_alignment(sensor: pd.DataFrame, mapping: pd.DataFrame,
                  contextual: pd.DataFrame, window_h: int = 6, rise: float = 1.0) -> pd.DataFrame:
    """Does each watering log coincide with a moisture rise?"""
    first = mapping.groupby("user_plant_id").device_id.first()
    rows = []
    for plant, device in first.items():
        g = sensor[sensor.device_id == device].sort_values("ts")
        shift = pd.Timedelta(hours=2) if device == "SENS-07" else pd.Timedelta(0)
        movement = pd.Series(g.soil_moisture_vwc.values, index=g.ts - shift).diff()
        logs = contextual[(contextual.user_plant_id == plant)
                          & (contextual.log_type == "watering")].created_at
        hits = sum(1 for t in logs
                   if movement[(movement.index >= t)
                               & (movement.index <= t + pd.Timedelta(hours=window_h))].max() > rise)
        rows.append({"plant": plant, "device": device, "watering_logs": len(logs),
                     "with_sensor_rise": hits})
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
    """Every run of an unchanged value long enough to be a dead channel."""
    rows = []
    for device, g in sensor.groupby("device_id", sort=True):
        g = g.sort_values("ts")
        for channel in CHANNELS:
            for _, part in g.groupby((g[channel].diff() != 0).cumsum()):
                if len(part) >= min_run:
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
     "136 uS/cm/day at R2=0.99; 337 of 354 out-of-range readings are in runs, i.e. "
     "sustained; no fertilising log near onset; the four devices that WERE fertilised "
     "show no EC response (-6..+3 against daily noise 42)",
     "high", "sensor fault - drift",
     "exclude EC for this device, or recalibrate; ask calibration whether a "
     "straight-line climb is possible"),

    ("F5", "SENS-04 moisture exceeds the instrument's specified 65% ceiling", "SENS-04",
     "431 readings (21.4%) above 65%, peaking 107.12, and 420 of them are in runs -- "
     "sustained excursions, not glitches; dry-down 6.5/day vs 0.5-1.9 fleet; "
     "jitter 0.47 vs 0.14",
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
     "leave the gap; the ~320-reading buffer means it was recoverable, so this was "
     "a sync failure not lost data - confirm with firmware"),

    ("F8", "SENS-08 has 15 superfluous duplicate rows", "SENS-08",
     "identical payloads, 0 conflicting",
     "low", "data problem - at-least-once redelivery",
     "deduplicate; lossless because nothing disagrees"),

    ("F9", "user_plant_id is not unique, so log/image joins multiply rows", "all",
     "contextual 49->67, images 28->35; the sensor join is clean, which is the trap",
     "medium", "schema problem",
     "dedupe the mapping to one row per plant before joining"),

    ("F10", "Two plants have two sensors, and the pairs do not correlate", "UP-1001, UP-1003",
     "r = -0.076 and +0.140; same-pot probes must move together",
     "high", "unknown - real config or mapping bug",
     "ask product whether the app allows two sensors per plant; do not average"),

    ("F11", "Watering logs and sensor events are unrelated", "all plants",
     "32 of 34 watering logs have no moisture rise within 6h. The sensor's rises "
     "land on the hour (35 of 35, excluding SENS-08) while the logs are all at "
     "human times -- so the two look independently generated",
     "high", "label problem",
     "do not use logs as event ground truth; ask firmware whether the device does "
     "anything at 00:00"),

    ("F12", "Environment is near-identical across all eight devices", "all",
     "temp r=0.974, light r=0.998, humidity r=0.946 -- while moisture r=0.103",
     "medium", "artefact - shared or generated ambient series",
     "do not use 'differs from the fleet' as an anomaly test for temp/light/humidity"),

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


#: How each finding was caught, and the natural check that is *structurally
#: blind* to it.
#:
#: The second column is the point. Every trap in this dataset defeats at least
#: one obvious test, which is why the detector set is orthogonal rather than
#: deep -- eight different questions about the same rows, not one question
#: asked eight ways. A check that repeats an existing angle adds nothing; only
#: a new angle finds a new class of defect.
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


def evidence_tables(sensor: pd.DataFrame, mapping: pd.DataFrame, contextual: pd.DataFrame,
                    images: pd.DataFrame) -> dict:
    """Every detector's output, keyed by what it shows.

    Returns data only -- main() prints it, the notebook displays it. Same rows
    either way, so the two artifacts cannot drift.
    """
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
        # top 6 of 40 by drift ratio; the tail is ordinary day-to-day movement
        "drift vs own history (top 6 of 40)": screen_drift(sensor, CHANNELS).head(6),
        "watering logs vs sensor": log_alignment(sensor, mapping, contextual),
    }
