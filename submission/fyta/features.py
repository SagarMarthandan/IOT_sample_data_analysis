"""Task 5: one time-indexed table per plant.

Grain is `(user_plant_id, ts_aligned)`, with one row whenever at least one
mapped device reports. `gap_minutes` exposes missing shared slots on the next
reported row, so the table retains delivered observations without fabricating
an interpolation across a sensor outage.

Two-probe plants retain device-id-ordered positional columns. Device ids travel
with every row, readings are never averaged, and `vwc_delta` exposes the gap.
`vwc_pct_1/2` ranks each cleaned reading inside that device's trailing recent
range. It compares readings on a within-device scale without using future values
in an earlier feature row, while leaving the raw VWC values available.

The table joins cleaned sensor channels to current plant metadata. Metadata
requires one mapping per device and one substrate per plant before the merge.
Logs and images remain sparse events: projecting 49 logs or 28 photos across
11,903 fifteen-minute rows would turn one event into many claims. Consumers can
join them as-of with an explicit tolerance and preserve no recent event
separately from no event. This table does not fill the F7 outage, resolve F10,
or infer effective dates for F13 metadata.

    `n_sensors` is the mapped probe count. Each output row carries all device
    slots, cleaned feature slots, species, and substrate so consumers can trace a
    value back to a reporting instrument. A substrate label is current metadata,
    not historical evidence at each timestamp.

    `FEATURE_COLS` shortens repeated channel names before slot suffixes. The
    original raw columns remain upstream in the cleaned sensor frame.

    `gap_minutes` is computed after sorted plant-time rows, so it describes
    elapsed reporting time for the same plant.
"""

import pandas as pd

#: Source column to concise per-device feature name.
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

#: 7 days of 15-minute readings with 1 day of warm-up.
WINDOW, MIN_PERIODS = 672, 96


def plant_features(sensor: pd.DataFrame, mapping: pd.DataFrame,
                   window: int = WINDOW, min_periods: int = MIN_PERIODS) -> pd.DataFrame:
    """Build the plant-time feature table from the cleaned sensor frame.

    `window` and `min_periods` control per-device trailing VWC percentiles.
    Every sensor device requires one mapping entry before the merge. `pivot`
    enforces a unique `(plant, timestamp, slot)` shape, while sorted device ids
    make positional slots reproducible. Slots with no reporting device remain
    absent rather than becoming synthetic rows.
    """
    df = sensor.copy()          # `_pct` must not leak into the caller's frame
    # Rank within device: VWC is only comparable within a substrate.
    df["vwc_pct"] = (df.groupby("device_id")["soil_moisture_vwc_clean"]
                       .transform(lambda s: s.rolling(window, min_periods=min_periods)
                                               .rank(pct=True)))
    df = df.rename(columns=FEATURE_COLS)

    # Stable device-id slots keep positional columns and `device_1/2` meaningful.
    slots = mapping.sort_values(["user_plant_id", "device_id"])
    slots["slot"] = slots.groupby("user_plant_id").cumcount() + 1
    assert not slots.duplicated(["device_id"]).any(), \
        "a device maps to more than one plant; the slot join would fan out"
    # Check both join sides: unmapped sensor rows would be silently dropped.
    unmapped = sorted(set(sensor["device_id"]) - set(slots["device_id"]))
    assert not unmapped, (
        f"sensor rows for {unmapped} have no mapping row, so an inner merge would "
        f"drop them silently; every reporting device needs a plant")
    df = df.merge(slots, on="device_id")

    keys = ["user_plant_id", "ts_aligned"]
    # `pivot` rejects duplicate (index, column) pairs.
    wide = df.pivot(index=keys, columns="slot", values=KEEP)
    wide.columns = [f"{c}_{s}" for c, s in wide.columns]
    out = wide.reset_index()
    n_slots = int(slots["slot"].max())

    out["n_sensors"] = out["user_plant_id"].map(slots.groupby("user_plant_id").size())
    for s in range(1, n_slots + 1):
        out[f"device_{s}"] = out["user_plant_id"].map(
            slots.loc[slots["slot"] == s].set_index("user_plant_id")["device_id"])

    if "vwc_2" in out:
        # Keep the two-probe disagreement.
        out["vwc_delta"] = (out["vwc_1"] - out["vwc_2"]).abs()

    # Point-in-time substrate metadata has no effective dating (F13).
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
    """Summarize plant rows against the observed grid.

    `missing` compares rows with slots between observed endpoints. `probes_filled`
    is the share of delivered rows where every plant-owned probe has moisture.
    It excludes non-existent device slots and remains distinct from grid coverage
    or a first-probe-only measure. `longest_gap_h` is measured from consecutive
    aligned feature timestamps.
    """
    n = int(features["n_sensors"].max())
    vwcs = [f"vwc_{i}" for i in range(1, n + 1)]
    # Columns for probes a plant does not own pass automatically.
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
