"""Optional Tasks 8 and 9: drydown and structured log signals.

The drydown output is derived from cleaned VWC; the log output parses only
values the supplied text states.

ponytail: both live here because neither is load-bearing. The brief marks them
optional, and dropping either removes this file without touching anything else.
Split them the moment one grows a second caller.
"""

import pandas as pd

# ------------------------------------------------------- Task 8: drydown rate


def drydown_rate(sensor: pd.DataFrame, window: int = 96,
                 min_periods: int = 48) -> pd.DataFrame:
    """Estimate %VWC lost per day from trailing median changes.

    Group by device before differencing, then divide each VWC change by elapsed
    days. Calibration still applies: for `reported = a * true + b`,
    differentiation removes `b` but retains `a`. Rates therefore compare within
    a probe under stable conditions, rather than across substrates.

    A watering step reverses the sign and can dominate a mean. The trailing
    median resists those events. The window counts readings rather than elapsed
    time, so `drydown_asof` records the last valid timestamp when the current
    VWC value is null.

    `window=96` readings is one day; `min_periods=48` requires twelve hours.

    The returned frame contains `device_id`, `ts_aligned`,
    `drydown_pct_per_day`, and `drydown_asof`. Consumers should compare
    `drydown_asof` with their required freshness before treating the estimate as
    current.

    A null current VWC can still have a valid trailing estimate. The as-of
    timestamp makes that distinction explicit without filling the gap.

    Gaps change elapsed-time differences without changing the rolling reading
    count, which the output reports rather than hides.
    """
    df = sensor[["device_id", "ts_aligned", "soil_moisture_vwc_clean"]].copy()
    by_dev = df.groupby("device_id")
    # Divide by elapsed days so gaps do not create rate spikes.
    gap_days = by_dev["ts_aligned"].diff().dt.total_seconds() / 86400
    df["_rate"] = -by_dev["soil_moisture_vwc_clean"].diff() / gap_days

    # ponytail: the window counts READINGS, not time, so a device with gaps gets
    # a slightly longer effective window. Fine at this size and with this much
    # data; move to a time-based rolling window if gaps become the norm.
    df["drydown_pct_per_day"] = (
        df.groupby("device_id")["_rate"]
          .transform(lambda s: s.rolling(window, min_periods=min_periods).median()))

    # Expose the last valid timestamp for a rate whose current value is null.
    df["drydown_asof"] = (df["ts_aligned"]
                          .where(df["soil_moisture_vwc_clean"].notna())
                          .groupby(df["device_id"]).ffill())
    return df.drop(columns="_rate")


# ------------------------------------------------- Task 9: log text, structured

#: Ordinal watering intensity from 14 phrases; only one carries a volume.
INTENSITY = {
    "Quick water": 1,
    "Watered a bit, leaves drooping": 1,
    "Watered ~200ml": 2,
    "Top soil was dry, watered": 2,
    "Bottom-watered today": 3,
    "Gave it a good soak": 3,
}

#: The one numeric the text contains, in 5 of 49 rows.
VOLUME = r"~?\s*(\d+)\s*ml"


def log_signals(contextual: pd.DataFrame) -> pd.DataFrame:
    """Map log text to the existing one-to-one `log_type` vocabulary.

    The 14-phrase vocabulary across 49 rows does not require a classifier.
    Output preserves the source log id, plant, text, and created time, then adds
    coarse watering intensity and the stated volume where present. F11 limits
    these fields to text interpretation: logs do not become timestamped sensor
    events.
    """
    out = contextual[["log_id", "user_plant_id", "log_type", "text", "created_at"]].copy()
    # Assert the phrase-to-type property required by the lookup.
    assert out.groupby("text")["log_type"].nunique().eq(1).all(), \
        "a phrase maps to more than one log_type, so this is not a lookup"
    out["intensity"] = out["text"].map(INTENSITY).astype("Int64")
    out["volume_ml"] = out["text"].str.extract(VOLUME, expand=False).astype("Float64")
    return out
