"""Regression checks for the defects two external reviews found.

    uv run test_gates.py

No framework -- one function per defect, each one FAILING if its fix is
reverted. They exist because `assert` inside the pipeline disappears under
`python -O`, and because the audit gate's original check was tautological: it
could approve the exact defect it claimed to prevent.
"""

import pandas as pd

from fyta.cleaning import audit, clean
from fyta.features import plant_features
from fyta.sensors import frozen_windows, parse_timestamps, spec_violations
from fyta.sources import image_predictions, triangulate


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


def test_a_pre_event_image_is_not_a_response():
    """A photo taken before a fertilising event cannot be a response to it.

    The window was `hours.abs() <= 48`, so a fixture whose only photo was 2.5
    hours EARLIER came back corroborated=True.
    """
    ts = pd.date_range("2026-06-01", periods=200, freq="15min")
    ec = pd.Series(700.0, index=ts)
    ec.iloc[120:] = 1200.0                     # strong post-event RISE
    cleaned = pd.DataFrame({"device_id": "SENS-99", "ts_aligned": ts,
                            "ec_us_cm_clean": ec.to_numpy()})
    features = pd.DataFrame({"user_plant_id": "UP-99", "ts_aligned": ts,
                             "ec_1": ec.to_numpy(), "device_1": "SENS-99"})
    contextual = pd.DataFrame({"log_id": ["L"], "user_plant_id": ["UP-99"],
                               "log_type": ["fertilising"], "created_at": [ts[100]]})
    # the ONLY photo is 2.5 hours BEFORE the event, and scores 0.9
    heads = pd.DataFrame({"user_plant_id": ["UP-99"],
                          "captured_at": [ts[100] - pd.Timedelta("2.5h")],
                          "Nutrient deficiency": [0.9]})

    out = triangulate(cleaned, features, contextual, heads)
    assert out["sensor_leg"].iloc[0] == "rises", "fixture must produce a rise"
    assert out["model_leg"].iloc[0] == "no post-event image", \
        f"a pre-event photo was used as a response: {out['model_leg'].iloc[0]!r}"
    assert not out["corroborated"].iloc[0], "a pre-event photo corroborated the event"


def _parsed():
    """The sample, read the way the pipeline reads it."""
    raw = pd.read_csv("../data/fyta_sensor_sample.csv")
    raw["ts"] = parse_timestamps(raw["timestamp"])
    raw["timestamp"] = raw["ts"]
    raw["substrate_label"] = raw["substrate_label"].astype(str)
    return raw


def test_night_darkness_is_not_a_frozen_channel():
    """A long run of exactly-zero PAR is a dark pot, not a dead sensor.

    The detector treated any unchanged run as frozen. Night is 12+ hours of
    exactly 0.0, so a fixture nulled 52 legitimate measurements. The rule is
    only sound if the channel COULD have moved.
    """
    n = 52
    ts = pd.date_range("2026-06-01 18:00", periods=n, freq="15min")
    night = pd.DataFrame({
        "device_id": "T-01", "ts": ts, "timestamp": ts,
        "substrate_label": "potting_soil",
        "soil_moisture_vwc": [40.0 - i * 0.1 for i in range(n)],
        "soil_temp_c": [20.0 + i * 0.01 for i in range(n)],
        "ec_us_cm": [700.0 + i for i in range(n)],
        "light_par": [0.0] * n,
        "air_humidity_pct": [60.0 + i * 0.1 for i in range(n)]})
    cleaned, rejections = clean(night, frozen_windows(night))
    assert rejections.empty, f"dark light was nulled: {rejections['reason'].tolist()}"

    # A light channel frozen ABOVE the floor is still a fault.
    stuck = night.copy()
    stuck["light_par"] = 37.5
    assert (frozen_windows(stuck)["channel"] == "light_par").any(), \
        "a frozen non-floor light run must still be detected"


def test_conflicting_duplicates_are_quarantined_not_resolved():
    """Two payloads on one key are unorderable; neither may be chosen.

    `drop_duplicates` kept an arbitrary winner and the audit approved it. The
    identical case is still deduped losslessly.
    """
    raw = _parsed()
    baseline, _ = clean(raw, frozen_windows(raw))

    # `iloc[[0]]` keeps the dtypes; `iloc[0].to_frame().T` upcasts them to object
    # and the audit then sees a non-numeric column it never gets in practice.
    twin = raw.iloc[[0]].copy()
    twin["ec_us_cm"] = twin["ec_us_cm"] + 100
    conflicted = pd.concat([raw, twin], ignore_index=True)
    cleaned, rejections = clean(conflicted, frozen_windows(conflicted))

    quarantined = rejections[rejections["channel"] == "(row)"]
    assert len(quarantined) == 2, \
        f"both conflicting payloads must be quarantined, got {len(quarantined)}"
    assert not cleaned.duplicated(["device_id", "timestamp"]).any(), \
        "quarantine left a duplicate key behind"
    assert audit(cleaned, conflicted, rejections)["passed"].all(), \
        f"the quarantine was not reconciled: {rejections['channel'].tolist()}"

    # Identical redelivery is still lossless.
    assert len(baseline) == 15935, f"identical dedupe changed: {len(baseline)}"


def test_healthy_input_passes_the_audit():
    """A gate that fires on clean input trains people to ignore it.

    `len(rejections) > 0` was required, so a batch with nothing to reject
    failed -- and `declared <= detected` failed every batch without SENS-07.
    """
    raw = _parsed()
    s = raw[raw["device_id"].eq("SENS-03")].head(6).copy()
    for col, val in [("soil_moisture_vwc", 40.0), ("soil_temp_c", 21.0),
                     ("ec_us_cm", 700.0), ("light_par", 100.0),
                     ("air_humidity_pct", 55.0)]:
        s[col] = val
    ts = pd.date_range("2026-06-01", periods=6, freq="15min")
    s["ts"] = ts
    s["timestamp"] = ts

    cleaned, rejections = clean(s, frozen_windows(s))
    assert rejections.empty, "the fixture must be clean"
    result = audit(cleaned, s, rejections)
    failed = result[~result["passed"]]
    assert failed.empty, f"healthy input failed: {failed['check'].tolist()}"


def test_audit_re_derives_the_unit_conversion():
    """Membership is not arithmetic.

    `detected <= declared` passed with every corrected SENS-07 temperature
    replaced by 25 degrees, because it only checked that the device was named.
    """
    raw = _parsed()
    cleaned, rejections = clean(raw, frozen_windows(raw))
    tampered = cleaned.copy()
    tampered.loc[tampered["device_id"].eq("SENS-07"), "soil_temp_c_clean"] = 25.0
    result = audit(tampered, raw, rejections)
    assert not result["passed"].all(), "a tampered conversion passed the audit"


def test_unmapped_devices_fail_loudly():
    """An inner merge must not delete a device silently."""
    raw = _parsed()
    cleaned, _ = clean(raw, frozen_windows(raw))
    mapping = pd.read_csv("../data/user_plant_device_map.csv")
    partial = mapping[mapping["device_id"] != "SENS-08"]
    try:
        plant_features(cleaned, partial)
    except AssertionError as e:
        assert "SENS-08" in str(e), f"the wrong thing failed: {e}"
        return
    raise AssertionError("an unmapped device was dropped without an error")


def test_iso_only_input_parses():
    """The day-first guard must not fire when there are no slash dates."""
    out = parse_timestamps(pd.Series(["2026-06-01 00:00:00", "2026-06-01 00:15:00"]))
    assert len(out) == 2 and out.notna().all(), "ISO-only input failed to parse"
    try:
        parse_timestamps(pd.Series(["01/06/2026 09:00"]))     # ambiguous both ways
    except AssertionError:
        return
    raise AssertionError("an ambiguous slash date was accepted without proof")


def test_untestable_is_not_a_negative():
    """No baseline is not the same finding as no response."""
    raw = _parsed()
    cleaned, _ = clean(raw, frozen_windows(raw))
    mapping = pd.read_csv("../data/user_plant_device_map.csv")
    features = plant_features(cleaned, mapping)
    contextual = pd.read_csv("../data/fyta_contextual.csv", parse_dates=["created_at"])
    images = pd.read_csv("../data/fyta_images.csv", parse_dates=["captured_at"])
    heads, _, _ = image_predictions(images)

    at = pd.Timestamp("2026-06-03 14:00")
    # Probe 1 flat, probe 2 rises: the plant's own instrument must be consulted.
    moved = features.copy()
    m = ((moved["user_plant_id"] == "UP-1001") & (moved["ts_aligned"] > at)
         & (moved["ts_aligned"] <= at + pd.Timedelta("48h")))
    moved.loc[m, "ec_2"] = moved.loc[m, "ec_2"] + 500
    out = triangulate(cleaned, moved, contextual, heads).set_index("log")
    assert out.loc["LOG-00001", "sensor_leg"] == "rises", \
        f"probe 2 was ignored: {out.loc['LOG-00001', 'leg_detail']}"

    # Remove the baseline entirely: untestable, not "no rise".
    blanked = features.copy()
    pre = (blanked["user_plant_id"] == "UP-1001") & (blanked["ts_aligned"] <= at)
    blanked.loc[pre, ["ec_1", "ec_2"]] = float("nan")
    out2 = triangulate(cleaned, blanked, contextual, heads).set_index("log")
    assert out2.loc["LOG-00001", "sensor_leg"] == "not testable", \
        f"missing evidence reported as {out2.loc['LOG-00001', 'sensor_leg']!r}"


def test_notebook_assets_exist():
    """Every image the notebook references must be on disk.

    A hand-made architecture diagram lived in `out/figures/`, which the pipeline
    regenerates -- so `rm -rf out` (a legitimate clean-rebuild step) destroyed it
    and the notebook rendered a broken image with no error anywhere.
    """
    import json
    import re
    from pathlib import Path
    nb = json.loads(Path("fyta_analysis.ipynb").read_text())
    missing = []
    for cell in nb["cells"]:
        for ref in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", "".join(cell["source"])):
            if not ref.startswith(("http://", "https://")) and not Path(ref).exists():
                missing.append(ref)
    assert not missing, f"notebook references missing asset(s): {missing}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name[5:].replace('_', ' ')}")
    print(f"\n{sum(1 for n in globals() if n.startswith('test_'))} regression checks passed")
