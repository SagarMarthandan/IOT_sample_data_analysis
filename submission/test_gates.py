"""Regression checks for the three defects a second-opinion review found.

    uv run test_gates.py

No framework -- one function per defect, each one FAILING if its fix is
reverted. They exist because `assert` inside the pipeline disappears under
`python -O`, and because the audit gate's original check was tautological: it
could approve the exact defect it claimed to prevent.
"""

import pandas as pd

from fyta.cleaning import audit, clean
from fyta.sensors import frozen_windows, parse_timestamps, spec_violations
from fyta.sources import triangulate


def test_audit_catches_an_uncleaned_frozen_window():
    """The gate must fail when a frozen window is restored.

    The original check asked "is there at least one null in moisture?", which
    any unrelated null satisfies -- 1,344 restored values passed it.
    """
    raw = pd.read_csv("../data/fyta_sensor_sample.csv")
    raw["ts"] = parse_timestamps(raw["timestamp"])
    raw = raw.sort_values(["device_id", "ts"], ignore_index=True)
    cleaned, rejections = clean(raw, frozen_windows(raw))
    assert audit(cleaned, raw, rejections)["passed"].all(), "baseline must pass"

    frozen = rejections[rejections["reason"].str.startswith("frozen_channel")]
    broken = cleaned.merge(
        frozen[["device_id", "timestamp", "channel", "raw_value"]],
        on=["device_id", "timestamp"], how="left")
    for channel in frozen["channel"].unique():
        m = broken["channel"] == channel
        broken.loc[m, f"{channel}_clean"] = broken.loc[m, "raw_value"]
    broken = broken.drop(columns=["channel", "raw_value"])

    assert not audit(broken, raw, rejections)["passed"].all(), \
        "the audit approved a restored frozen window"


def test_run_lengths_not_run_starts():
    """A long excursion must report as ONE run, not one 'isolated' sample.

    The original arithmetic, `n - (bad & bad.shift()).sum()`, counts run starts.
    """
    ts = pd.date_range("2026-01-01", periods=20, freq="15min")
    vwc = [10.0] * 20
    vwc[3:8] = [70.0] * 5                      # one run of five, above the 65 ceiling
    vwc[12] = 70.0                             # one genuinely isolated sample
    s = pd.DataFrame({"device_id": "X", "ts": ts, "soil_moisture_vwc": vwc,
                      "soil_temp_c": 20.0, "ec_us_cm": 500.0,
                      "light_par": 0.0, "air_humidity_pct": 50.0})

    row = spec_violations(s).iloc[0]
    assert row["n_bad"] == 6
    assert row["runs"] == 2, row.to_dict()
    assert row["isolated"] == 1, "a run was counted as isolated"
    assert row["in_runs"] == 5, "in_runs must be sum(L) for L>=2, not sum(L-1)"
    assert row["longest_run"] == 5


def test_a_falling_ec_does_not_corroborate():
    """The brief says fertilising should raise EC. A fall must contradict.

    The original leg used `.abs()`, so a 400 uS/cm collapse counted as support.
    """
    ts = pd.date_range("2026-06-01", periods=200, freq="15min")
    ec = pd.Series(700.0, index=ts)
    ec.iloc[120:] = 300.0                      # large fall AFTER the event
    cleaned = pd.DataFrame({"device_id": "SENS-99", "ts_aligned": ts,
                            "ec_us_cm_clean": ec.to_numpy()})
    features = pd.DataFrame({"user_plant_id": "UP-99", "ts_aligned": ts,
                             "ec_1": ec.to_numpy(), "device_1": "SENS-99"})
    contextual = pd.DataFrame({"log_id": ["L"], "user_plant_id": ["UP-99"],
                               "log_type": ["fertilising"], "created_at": [ts[100]]})
    heads = pd.DataFrame({"user_plant_id": ["UP-99"], "captured_at": [ts[110]],
                          "Nutrient deficiency": [0.01]})

    out = triangulate(cleaned, features, contextual, heads)
    assert out["d_ec_sigma"].iloc[0] < -3, "fixture must produce a large fall"
    assert out["sensor_leg"].iloc[0] == "no rise", \
        f"a fall was treated as corroboration: {out['sensor_leg'].iloc[0]!r}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name[5:].replace('_', ' ')}")
    print("\n3 of 3 regression checks passed")
