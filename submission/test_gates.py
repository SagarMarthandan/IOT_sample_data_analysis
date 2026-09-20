"""Regression checks for the defects two external reviews found.

    uv run test_gates.py

No framework -- one function per defect, each one failing if its fix is
reverted. They exist because `assert` inside the pipeline disappears under
`python -O`, and because the audit gate's original check was tautological: it
could approve the exact defect it claimed to prevent.
"""

import json

import pandas as pd

from fyta.cleaning import audit, clean
from fyta.domain import CADENCE
from fyta_pipeline import DATA, ROOT      # resolved once, layout-agnostic
from fyta.features import plant_features
from fyta.sensors import (check_grid, frozen_windows, parse_timestamps,
                          spec_violations)
from fyta.sources import image_predictions, triangulate


def test_audit_catches_an_uncleaned_frozen_window():
    """The gate must fail when a frozen window is restored.

    The original check asked "is there at least one null in moisture?", which
    any unrelated null satisfies -- 1,344 restored values passed it.
    """
    raw = pd.read_csv(DATA / "fyta_sensor_sample.csv")
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
    ec.iloc[120:] = 300.0                      # large fall after the event
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
    hours earlier came back corroborated=True.
    """
    ts = pd.date_range("2026-06-01", periods=200, freq="15min")
    ec = pd.Series(700.0, index=ts)
    ec.iloc[120:] = 1200.0                     # strong post-event rise
    cleaned = pd.DataFrame({"device_id": "SENS-99", "ts_aligned": ts,
                            "ec_us_cm_clean": ec.to_numpy()})
    features = pd.DataFrame({"user_plant_id": "UP-99", "ts_aligned": ts,
                             "ec_1": ec.to_numpy(), "device_1": "SENS-99"})
    contextual = pd.DataFrame({"log_id": ["L"], "user_plant_id": ["UP-99"],
                               "log_type": ["fertilising"], "created_at": [ts[100]]})
    # the only photo is 2.5 hours before the event, and scores 0.9
    heads = pd.DataFrame({"user_plant_id": ["UP-99"],
                          "captured_at": [ts[100] - pd.Timedelta("2.5h")],
                          "Nutrient deficiency": [0.9]})

    out = triangulate(cleaned, features, contextual, heads)
    assert out["sensor_leg"].iloc[0] == "rises", "fixture must produce a rise"
    assert out["model_leg"].iloc[0] == "no post-event image", \
        f"a pre-event photo was used as a response: {out['model_leg'].iloc[0]!r}"
    assert not out["corroborated"].iloc[0], "a pre-event photo corroborated the event"


def _parsed():
    """The sample, read the way the pipeline reads it.

    `timestamp` stays the source text and `ts` is the parsed column -- the
    difference the pipeline actually carries. An earlier helper assigned
    `raw["timestamp"] = raw["ts"]`, which hid a crash: the quarantine branch
    subtracted a Timedelta from `timestamp` and only a datetime column let that
    pass. A fixture that has to lie about the input shape is not a regression
    test for code that reads the real one.
    """
    raw = pd.read_csv(DATA / "fyta_sensor_sample.csv")
    raw["ts"] = parse_timestamps(raw["timestamp"])
    raw["substrate_label"] = raw["substrate_label"].astype(str)
    return raw


def test_night_darkness_is_not_a_frozen_channel():
    """A long run of exactly-zero PAR is a dark pot, not a dead sensor.

    The detector treated any unchanged run as frozen. Night is 12+ hours of
    exactly 0.0, so a fixture nulled 52 legitimate measurements. The rule is
    only sound if the channel could have moved.
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

    # A light channel frozen above the floor is still a fault.
    stuck = night.copy()
    stuck["light_par"] = 37.5
    assert (frozen_windows(stuck)["channel"] == "light_par").any(), \
        "a frozen non-floor light run must still be detected"


def test_conflicting_duplicates_are_quarantined_not_resolved():
    """Payloads that disagree on one key are unorderable; none may be published.

    `drop_duplicates` kept an arbitrary winner and the audit approved it. The
    identical case is still deduped losslessly -- but the conflict is decided on
    the key group, not on whether a row happens to have a twin of its own. With
    A, A, B, B on one key every row is quarantined, because keeping A (the
    majority, or merely the twin) is the same arbitrary choice with an extra step.
    """
    raw = _parsed()
    baseline, _ = clean(raw, frozen_windows(raw))

    # `iloc[[0]]` keeps the dtypes; `iloc[0].to_frame().T` upcasts them to object
    # and the audit then sees a non-numeric column it never gets in practice.
    same, other = raw.iloc[[0]].copy(), raw.iloc[[0]].copy()
    other["ec_us_cm"] = other["ec_us_cm"] + 100
    conflicted = pd.concat([raw, same, other, other], ignore_index=True)
    cleaned, rejections = clean(conflicted, frozen_windows(conflicted))

    key = raw.iloc[0]
    quarantined = rejections[(rejections["channel"] == "(row)")
                             & (rejections["timestamp"] == key["timestamp"])]
    assert len(quarantined) == 4, \
        f"every row of a conflicting key must be quarantined, got {len(quarantined)}"
    assert not (cleaned["device_id"].eq(key["device_id"])
                & cleaned["timestamp"].eq(key["timestamp"])).any(), \
        "quarantine left a version of the conflicting key in the frame"
    assert not cleaned.duplicated(["device_id", "timestamp"]).any(), \
        "quarantine left a duplicate key behind"

    # The ledger is the only surviving copy of those payloads, so it must carry
    # the values themselves -- `raw_value = NaN` preserved no evidence at all.
    payloads = sorted(json.loads(p)["ec_us_cm"] for p in quarantined["row_payload"])
    assert payloads == sorted([key["ec_us_cm"], key["ec_us_cm"], key["ec_us_cm"] + 100,
                               key["ec_us_cm"] + 100]), \
        f"the quarantined payloads were not preserved: {payloads}"

    result = audit(cleaned, conflicted, rejections)
    assert result["passed"].all(), \
        f"the quarantine was not reconciled: {result.loc[~result['passed'], 'check'].tolist()}"

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
    mapping = pd.read_csv(DATA / "user_plant_device_map.csv")
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
    mapping = pd.read_csv(DATA / "user_plant_device_map.csv")
    features = plant_features(cleaned, mapping)
    contextual = pd.read_csv(DATA / "fyta_contextual.csv", parse_dates=["created_at"])
    images = pd.read_csv(DATA / "fyta_images.csv", parse_dates=["captured_at"])
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
    """Every image the notebook references must be on disk, as markdown.

    Two ways this check passed while the notebook was broken. A diagram lived in
    `out/figures/`, which the pipeline regenerates, so `rm -rf out` deleted it.
    Then a prose rewrite turned `![alt](path)` into a shell call, which dropped
    the leading `!` the reference regex needs: the test found ZERO references and
    approved. An empty result set is not a pass.

    The shell-call form is checked for directly, because it is what this notebook
    actually lost: the viewer showed `__omp_shell("Variant A")` where the diagram
    belonged.
    """
    import json
    import re
    from pathlib import Path

    nb_path = ROOT / "fyta_analysis.ipynb"
    if not nb_path.exists():
        # A code-only bundle is a legitimate submission. Say so out loud: an
        # absent input is not a check that passed -- this suite exists because
        # a check satisfied by finding nothing is how the diagrams broke.
        print("      (skipped: this bundle has no notebook, so it references no assets)")
        return

    nb = json.loads(nb_path.read_text())
    text = "".join("".join(c["source"]) for c in nb["cells"])

    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    assert refs, ("no image references found, but the notebook embeds the two "
                  "architecture diagrams -- the markdown was altered")

    # A reference is satisfied either by a file beside the notebook or by an
    # attachment carried inside it. Attachments are why the diagrams survive
    # being copied to another machine, or opened by a viewer that resolves
    # relative paths against its own working directory.
    missing, unattached = [], []
    for cell in nb["cells"]:
        for ref in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", "".join(cell["source"])):
            if ref.startswith(("http://", "https://")):
                continue
            if ref.startswith("attachment:"):
                if ref.split(":", 1)[1] not in (cell.get("attachments") or {}):
                    unattached.append(ref)
            elif not (nb_path.parent / ref).exists():
                missing.append(ref)
    assert not missing, f"notebook references missing asset(s): {missing}"
    assert not unattached, f"notebook references attachment(s) it does not carry: {unattached}"

    mangled = re.findall(r"__omp_shell\(\"[^\"]*\]\(([^)]+)\)", text)
    assert not mangled, f"image markdown was rewritten into a shell call: {mangled}"


def test_audit_catches_a_deleted_device():
    """Losing an entire device must fail the gate, not just losing a column.

    The raw-column check compared only the keys present in both frames, so
    deleting all 2,016 SENS-01 rows left every surviving value identical and
    passed all 19 checks.
    """
    raw = _parsed()
    cleaned, rejections = clean(raw, frozen_windows(raw))
    thinned = cleaned[cleaned["device_id"] != "SENS-01"]

    result = audit(thinned, raw, rejections)
    failed = result.loc[~result["passed"], "check"].tolist()
    assert any("retained, deduped or quarantined" in c for c in failed), \
        f"2,016 deleted rows passed the gate; failures were {failed}"


def test_audit_tolerates_a_reordered_frame():
    """A re-ordered frame changed nothing, so the gate must not fail it.

    The value comparison was positional, so sorting the same rows differently
    read as "the raw columns were edited" -- which makes the gate both blind to a
    real edit and noisy about a harmless one.
    """
    raw = _parsed()
    cleaned, rejections = clean(raw, frozen_windows(raw))
    shuffled = cleaned.sample(frac=1, random_state=0).reset_index(drop=True)

    result = audit(shuffled, raw, rejections)
    assert result["passed"].all(), \
        f"a re-order failed the audit: {result.loc[~result['passed'], 'check'].tolist()}"


def test_audit_catches_moved_dark_hour_flags():
    """Flags must sit on the readings the detector found, not merely be counted.

    `8 detected == 8 flagged` approved a frame where every flag had been moved
    onto unrelated readings.
    """
    raw = _parsed()
    cleaned, rejections = clean(raw, frozen_windows(raw))
    spikes = cleaned.index[cleaned["qc_flags"].str.contains("dark_hour_single_sample")]
    assert len(spikes), "the fixture must contain dark-hour spikes"

    moved = cleaned.copy()
    moved.loc[spikes, "qc_flags"] = moved.loc[spikes, "qc_flags"].str.replace(
        "light_par:dark_hour_single_sample;", "", regex=False)
    device = moved.loc[spikes[0], "device_id"]
    others = moved.index[(moved["device_id"] == device) & ~moved.index.isin(spikes)]
    moved.loc[others[:len(spikes)], "qc_flags"] = "light_par:dark_hour_single_sample;"

    result = audit(moved, raw, rejections)
    failed = result.loc[~result["passed"], "check"].tolist()
    assert any("dark-hour" in c for c in failed), \
        f"moved flags passed the gate; failures were {failed}"


def test_audit_catches_a_skipped_frozen_detection():
    """A cleaner that never detected the frozen window must not pass.

    Every previous check reconciled the rejections that were recorded, so a
    cleaner that omitted the detector entirely -- no window, no null, no ledger
    row -- approved the input and left the frozen channel published.
    """
    raw = _parsed()
    empty = frozen_windows(raw).iloc[0:0]
    cleaned, rejections = clean(raw, empty)

    result = audit(cleaned, raw, rejections)
    failed = result.loc[~result["passed"], "check"].tolist()
    assert any("frozen window in the source" in c for c in failed), \
        f"a skipped frozen detection passed the gate; failures were {failed}"


def test_an_unavailable_probe_does_not_mask_the_other():
    """Probe 1 with no usable baseline must not hide probe 2's rise.

    The score was accepted whenever the window had rows, so a NaN delta entered
    `sigmas`, `max()` kept it as the first element, and the log reported "not
    testable" while the same plant's second probe rose.
    """
    raw = _parsed()
    cleaned, _ = clean(raw, frozen_windows(raw))
    mapping = pd.read_csv(DATA / "user_plant_device_map.csv")
    features = plant_features(cleaned, mapping)
    contextual = pd.read_csv(DATA / "fyta_contextual.csv", parse_dates=["created_at"])
    images = pd.read_csv(DATA / "fyta_images.csv", parse_dates=["captured_at"])
    heads, _, _ = image_predictions(images)

    at = pd.Timestamp("2026-06-03 14:00")
    blanked = features.copy()
    blanked.loc[blanked["user_plant_id"].eq("UP-1001"), "ec_1"] = float("nan")
    m = ((blanked["user_plant_id"] == "UP-1001") & (blanked["ts_aligned"] > at)
         & (blanked["ts_aligned"] <= at + pd.Timedelta("48h")))
    blanked.loc[m, "ec_2"] = blanked.loc[m, "ec_2"] + 500

    out = triangulate(cleaned, blanked, contextual, heads).set_index("log")
    assert out.loc["LOG-00001", "probe_leg"] == "SENS-02", \
        f"an invalid probe won the selection: {out.loc['LOG-00001', 'leg_detail']}"
    assert out.loc["LOG-00001", "sensor_leg"] == "rises", \
        f"probe 2's rise was hidden: {out.loc['LOG-00001', 'leg_detail']}"


def test_audit_reconciles_the_nulled_column():
    """`qc_nulled` must name the values the ledger emptied, by key and channel.

    The column is a claim the published table makes about itself. Stripping it
    leaves 1,415 values empty in `_clean` with no reason attached to the row,
    which is the defect the ledger exists to prevent.
    """
    raw = _parsed()
    cleaned, rejections = clean(raw, frozen_windows(raw))
    named = int(cleaned["qc_nulled"].fillna("").ne("").sum())
    ledger_values = int((rejections["channel"] != "(row)").sum())
    assert named == ledger_values and named > 0, \
        f"the fixture must name its nulled values: {named} named, {ledger_values} in the ledger"

    stripped = cleaned.copy()
    stripped["qc_nulled"] = ""
    result = audit(stripped, raw, rejections)
    failed = result.loc[~result["passed"], "check"].tolist()
    assert any("qc_nulled" in c for c in failed), \
        f"a stripped qc_nulled column passed the gate; failures were {failed}"


def test_notebook_defines_heads_before_using_it():
    """The Task 6 cell consumes `heads`; a cell must define it first.

    R1: the cell that created `heads` was removed by an edit, and the notebook
    only failed at execution -- from a fresh kernel, in front of a reviewer.
    It happened twice, so the dependency is pinned here rather than remembered.
    """
    import json
    import re
    from pathlib import Path

    nb_path = ROOT / "fyta_analysis.ipynb"
    if not nb_path.exists():
        print("      (skipped: this bundle has no notebook)")
        return

    code = [c for c in json.loads(nb_path.read_text())["cells"] if c["cell_type"] == "code"]
    defines = [i for i, c in enumerate(code)
               if any(re.match(r"\s*heads\s*(,|=)", l) for l in "".join(c["source"]).splitlines())]
    uses = [i for i, c in enumerate(code)
            if any("triangulate(" in l and "heads" in l
                   for l in "".join(c["source"]).splitlines())]
    assert defines, "no cell defines `heads`"
    assert uses, "no cell consumes `heads`"
    assert min(defines) <= min(uses), \
        f"`heads` is consumed in code cell {min(uses)} but only defined in {defines}"


def test_a_uniform_timestamp_shift_is_off_grid():
    """Spacing cannot see a uniform shift; grid membership can.

    Moving one timestamp by a minute kept the modal gap at 15 minutes and left
    completeness at 100 %, because both are computed from the device's own
    readings. Grid membership is the only one of the three that can see it.
    """
    raw = _parsed()
    check_grid(raw, CADENCE)                      # the fixture itself is on the grid

    shifted = raw.copy()
    shifted.loc[shifted.index[0], "ts"] += pd.Timedelta("1min")
    try:
        check_grid(shifted, CADENCE)
    except AssertionError as e:
        assert "off the" in str(e), f"the wrong thing failed: {e}"
        return
    raise AssertionError("a one-minute shift passed the grid check")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name[5:].replace('_', ' ')}")
    print(f"\n{sum(1 for n in globals() if n.startswith('test_'))} regression checks passed")
