"""Tasks 8 and 9 -- the optional stretches.

One derived signal from the cleaned sensor data, and one lookup that turns the
user's log text into structured values.

ponytail: both live here because neither is load-bearing. The brief marks them
optional, and dropping either removes this file without touching anything else.
Split them the moment one grows a second caller.
"""

import pandas as pd

# ------------------------------------------------------- Task 8: drydown rate


def drydown_rate(sensor: pd.DataFrame, window: int = 96,
                 min_periods: int = 48) -> pd.DataFrame:
    """%VWC lost per day, from the trailing median of consecutive changes.

    THE RATE IS COMPARABLE WHERE THE LEVEL IS NOT. An absolute VWC threshold is
    wrong across substrates -- that is precisely what the conversion curve exists
    for, and precisely what is unresolved here (F13, D7). But "this pot loses
    2 %/day" means the same thing in coir as in bark, so the rate carries across
    the fleet without a calibration nobody has confirmed yet.

    MEDIAN, not mean. A watering event is a large jump in the other direction,
    and a handful of them would swamp a mean. The median ignores them by
    construction, so the signal stays a drying rate rather than an average of
    drying and watering.

    window=96 readings is one day; min_periods=48 refuses to report a rate from
    less than twelve hours.
    """
    df = sensor[["device_id", "ts_aligned", "soil_moisture_vwc_clean"]].copy()
    by_dev = df.groupby("device_id")
    # Per DAY, not per step: a gap would otherwise fake a spike. Dividing by the
    # real elapsed time makes the outage harmless rather than loud.
    gap_days = by_dev["ts_aligned"].diff().dt.total_seconds() / 86400
    df["_rate"] = -by_dev["soil_moisture_vwc_clean"].diff() / gap_days

    # ponytail: the window counts READINGS, not time, so a device with gaps gets
    # a slightly longer effective window. Fine at this size and with this much
    # data; move to a time-based rolling window if gaps become the norm.
    df["drydown_pct_per_day"] = (
        df.groupby("device_id")["_rate"]
          .transform(lambda s: s.rolling(window, min_periods=min_periods).median()))
    return df.drop(columns="_rate")


# ------------------------------------------------- Task 9: log text, structured

#: Watering intensity, read off the phrase. An ORDINAL, not a measurement: the
#: whole vocabulary is 14 phrases and only ONE of them carries a volume, so
#: anything finer would be invention.
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
    """Task 9: the log text as structured values.

    A LOOKUP, NOT A CLASSIFIER. The vocabulary is fourteen phrases over 49 rows
    and the phrase-to-`log_type` mapping is already one-to-one, so a model would
    be a more expensive way to write a dict -- and it would need labelled data
    nobody has. (AGENTS.md §12: look for the vocabulary before building a
    classifier on it.)

    What this adds beyond the `log_type` column that already exists is a coarse
    watering intensity and the one volume present. That is genuinely all the text
    encodes. Note the limit this shares with everything else here: F11 showed the
    logs do not align with the sensors in time, so a cleaner log is still not a
    timestamped event.
    """
    out = contextual[["log_id", "user_plant_id", "log_type", "text", "created_at"]].copy()
    # Derive the mapping from the data, and ASSERT the property the lookup
    # depends on -- that a phrase determines its type.
    assert out.groupby("text")["log_type"].nunique().eq(1).all(), \
        "a phrase maps to more than one log_type, so this is not a lookup"
    out["intensity"] = out["text"].map(INTENSITY).astype("Int64")
    out["volume_ml"] = out["text"].str.extract(VOLUME, expand=False).astype("Float64")
    return out
