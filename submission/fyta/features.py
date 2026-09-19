"""Task 5: one time-indexed table per plant.

Grain is `(user_plant_id, ts_aligned)`, declared and asserted rather than
assumed.

Two structural facts about this dataset decide the shape of the table.

**Two probes on one plant.** UP-1001 and UP-1003 have two devices each (F10,
still unresolved). Averaging them is not an option -- it would invent a moisture
value describing neither pot. So each device gets a positional column, the
device ids travel *with the row*, and their disagreement is exposed as
`vwc_delta`. That disagreement is the entire point of a second probe: it is
fault detection, and averaging destroys it.

**VWC is only comparable within a substrate.** `vwc_pct_1/2` is the reading's
rank inside that device's own recent range, which is what makes it comparable
*across* plants. The window is TRAILING and that is not a detail -- ranking over
the whole window would judge a day-1 reading against day-21 data, which is
leakage the moment this table feeds a model.

**Scope.** This table unifies the cleaned sensor channels and the plant metadata.
It deliberately does NOT join in the logs or the images. There are 49 log rows
and 28 photos against 11,903 fifteen-minute rows: spreading a log across every
row in its neighbourhood would duplicate it hundreds of times and turn a sparse
event into a claim about every slot, and a photo the model can only evaluate once
cannot be sampled at 15-minute resolution. Production consumers should join both
**as-of**, with an explicit tolerance, and treat "no recent log" as a distinct
state from "no log". That is a modelling decision, and this table does not
silently make it.

What this table also deliberately does NOT do: fill the 48.5-hour outage (F7),
resolve the two-probe question (F10), or date the substrate label (F13). Each is
visible on the row instead of hidden -- see `gap_minutes`, `vwc_delta`, and the
verdict in the run log.
"""

import pandas as pd

#: Source column -> feature name. Short, because every one of these gets
#: suffixed with a device slot and `soil_moisture_vwc_clean_2` is unreadable.
FEATURE_COLS = {
    "soil_moisture_vwc_clean": "vwc",
    "vwc_pct": "vwc_pct",
    "soil_temp_c_clean": "temp",
    "ec_us_cm_clean": "ec",
    "light_par_clean": "par",
    "air_humidity_pct_clean": "humidity",
    "qc_flags": "flags",
}

#: Per-device columns, before the slot suffix is applied.
KEEP = list(FEATURE_COLS.values())

#: 7 days of 15-minute readings, and 1 day of warm-up. See the module docstring.
WINDOW, MIN_PERIODS = 672, 96


def plant_features(sensor: pd.DataFrame, mapping: pd.DataFrame,
                   window: int = WINDOW, min_periods: int = MIN_PERIODS) -> pd.DataFrame:
    """Build the table. `sensor` must be the CLEANED frame from Task 3.

    Returns one row per (plant, aligned timestamp) wherever at least one of the
    plant's devices reported. Slots where nothing reported are absent rows, made
    visible on the following row by `gap_minutes`.
    """
    df = sensor.copy()          # `_pct` below must not leak into the caller's frame
    # VWC is the substrate-converted channel, so it is the one that needs a
    # within-device rank to mean anything across plants.
    df["vwc_pct"] = (df.groupby("device_id")["soil_moisture_vwc_clean"]
                       .transform(lambda s: s.rolling(window, min_periods=min_periods)
                                               .rank(pct=True)))
    df = df.rename(columns=FEATURE_COLS)

    # Positional slots, assigned in device-id order so the table is
    # reproducible. A positional column whose meaning changes between plants
    # would be a trap, so `device_1/2` travel with every row.
    slots = mapping.sort_values(["user_plant_id", "device_id"])
    slots["slot"] = slots.groupby("user_plant_id").cumcount() + 1
    assert not slots.duplicated(["device_id"]).any(), \
        "a device maps to more than one plant; the slot join would fan out"
    df = df.merge(slots, on="device_id")

    keys = ["user_plant_id", "ts_aligned"]
    # `pivot` raises on duplicate (index, column) pairs, so the grain is checked
    # by construction rather than by a rule I have to remember.
    wide = df.pivot(index=keys, columns="slot", values=KEEP)
    wide.columns = [f"{c}_{s}" for c, s in wide.columns]
    out = wide.reset_index()
    n_slots = int(slots["slot"].max())

    out["n_sensors"] = out["user_plant_id"].map(slots.groupby("user_plant_id").size())
    for s in range(1, n_slots + 1):
        out[f"device_{s}"] = out["user_plant_id"].map(
            slots.loc[slots["slot"] == s].set_index("user_plant_id")["device_id"])

    if "vwc_2" in out:
        # The fusion signal, kept rather than averaged away.
        out["vwc_delta"] = (out["vwc_1"] - out["vwc_2"]).abs()

    # Point-in-time: these are today's values. `substrate_label` is a calibration
    # parameter with no effective dating (F13), so a consumer must not read it as
    # "true at this timestamp". Asserted to be one per plant so the merge is safe.
    meta = (mapping.merge(sensor.groupby("device_id")["substrate_label"].first(),
                          on="device_id")
                   .groupby("user_plant_id")
                   .agg(species=("species", "first"),
                        substrate=("substrate_label", "first"),
                        substrates=("substrate_label", "nunique"))
                   .reset_index())
    assert (meta["substrates"] == 1).all(), \
        f"a plant spans substrates: {meta.loc[meta['substrates'] > 1, 'user_plant_id'].tolist()}"
    out = out.merge(meta.drop(columns="substrates"), on="user_plant_id")

    out = out.sort_values(keys, ignore_index=True)
    out["gap_minutes"] = (out.groupby("user_plant_id")["ts_aligned"].diff()
                             .dt.total_seconds() / 60)

    return out[keys + ["species", "substrate", "n_sensors"]
               + [f"device_{s}" for s in range(1, n_slots + 1)]
               + [f"{c}_{s}" for s in range(1, n_slots + 1) for c in KEEP]
               + [c for c in ("vwc_delta", "gap_minutes") if c in out]]


def assert_grain(features: pd.DataFrame) -> int:
    """Assert the declared grain. Returns the row count so the caller can log it."""
    dup = int(features.duplicated(["user_plant_id", "ts_aligned"]).sum())
    assert dup == 0, f"grain (user_plant_id, ts_aligned) broken: {dup} duplicate keys"
    return len(features)


def plant_summary(features: pd.DataFrame) -> pd.DataFrame:
    """Per-plant row counts against the grid each plant was due.

    `missing` exists so a short plant explains its own row count. Without it a
    plant with absent rows is indistinguishable from a filter bug -- which is a
    question a reader asked of UP-1004, whose 193 absent rows are the 48.5-hour
    outage (F7).

    `probes_filled` is a different claim and is named for it: the share of rows
    PRESENT where **every** probe the plant has carries a moisture value.
    UP-1004 is missing 9.6% of its grid and is fully filled within the part it
    delivered.

    It is deliberately not the share of the grid, and deliberately not probe 1
    alone. Probe 1 alone reports UP-1003 at 0.976 while its second probe is frozen
    for 1,344 slots (F3); judged on both probes the plant is 0.324. A column that
    says 0.976 there is not conservative, it is wrong.
    """
    n = int(features["n_sensors"].max())
    vwcs = [f"vwc_{i}" for i in range(1, n + 1)]
    # A plant with one probe must not be judged on its empty `vwc_2` column, so
    # columns the plant does not own pass automatically.
    own = pd.DataFrame({c: features["n_sensors"] >= i + 1 for i, c in enumerate(vwcs)},
                       index=features.index)
    filled = (features[vwcs].notna() | ~own).all(axis=1)

    per = features.assign(_s=pd.to_datetime(features["ts_aligned"]), _f=filled).groupby(
        ["user_plant_id", "species"], sort=True).agg(
        rows=("ts_aligned", "size"),
        _due=("_s", lambda x: int((x.max() - x.min()).total_seconds() // 900) + 1),
        probes=("n_sensors", "first"),
        probes_filled=("_f", lambda x: round(float(x.mean()), 3)),
        longest_gap_h=("gap_minutes", lambda x: round(float(x.max()) / 60, 1)))
    per.insert(1, "missing", per.pop("_due") - per["rows"])
    return per
