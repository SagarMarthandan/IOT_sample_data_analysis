"""Task 3: the first pass a modelling team can trust.

Raw is immutable. Every fix lands in a NEW column and the original is kept
alongside it. Nothing is clipped, averaged or interpolated.
"""

import numpy as np
import pandas as pd

from .domain import CHANNELS, CLOCK_OFFSET_H, IMPOSSIBLE, SPEC, UNIT_FIXES
from .sensors import align_clocks, dark_hour_spikes, detect_unit_outliers

def clean(sensor: pd.DataFrame, windows: pd.DataFrame) -> tuple:
    """First pass into something a modelling team can trust.

    Raw is immutable: every fix lands in a NEW column and the original is kept
    alongside it. Nothing is clipped, averaged or interpolated. Every value that
    is removed is recorded with its reason, in a separate table.

    Returns (cleaned, rejections, flags).
    """
    df = sensor.drop_duplicates(["device_id", "ts"]).reset_index(drop=True).copy()
    rejections = []

    # F2 clock: an aligned copy; the raw timestamp column is untouched
    offset = pd.to_timedelta(df["device_id"].map(CLOCK_OFFSET_H).fillna(0), unit="h")
    df["ts_aligned"] = df["ts"] - offset

    # F1 units: start _clean as a copy, then convert where declared
    for channel in CHANNELS:
        df[f"{channel}_clean"] = df[channel]
    for device, fixes in UNIT_FIXES.items():
        for channel, kind in fixes.items():
            if kind == "fahrenheit":
                m = df["device_id"] == device
                df.loc[m, f"{channel}_clean"] = (df.loc[m, channel] - 32) * 5 / 9

    # F3 frozen: the whole run is untrustworthy, not just its first sample
    for _, w in windows.iterrows():
        col = f"{w['channel']}_clean"
        m = ((df["device_id"] == w["device"]) & (df["ts"] >= w["first"])
             & (df["ts"] <= w["last"]))
        rejections.append(pd.DataFrame({
            "device_id": df.loc[m, "device_id"], "timestamp": df.loc[m, "timestamp"],
            "channel": w["channel"], "raw_value": df.loc[m, w["channel"]],
            "reason": f"frozen_channel ({w['samples']} samples at {w['frozen_at']})"}))
        df.loc[m, col] = np.nan

    # F5/F6 two-tier: null the impossible, flag the merely out-of-spec
    flags = pd.Series("", index=df.index)
    for channel, (lo_imp, hi_imp) in IMPOSSIBLE.items():
        col = f"{channel}_clean"
        impossible = (df[col] < lo_imp) | (df[col] > hi_imp)
        if impossible.any():
            rejections.append(pd.DataFrame({
                "device_id": df.loc[impossible, "device_id"],
                "timestamp": df.loc[impossible, "timestamp"],
                "channel": channel, "raw_value": df.loc[impossible, channel],
                "reason": f"impossible (outside [{lo_imp}, {hi_imp}])"}))
            df.loc[impossible, col] = np.nan

        if channel in SPEC:
            lo_spec, hi_spec = SPEC[channel]
            out = df[col].notna() & ((df[col] < lo_spec) | (df[col] > hi_spec))
            flags[out] += f"{channel}:outside_spec;"

    # Context-based check. The range checks above cannot see a reading that is
    # physically possible but statistically implausible -- see dark_hour_spikes().
    #
    # FLAGGED, NOT EMPTIED. A light at night is physically possible: a lamp or a
    # torch held near one pot would do it. So these fail the same test the
    # out-of-spec values fail. Emptying them would apply a stricter standard here
    # than everywhere else -- and would delete a real observation if the light
    # was real.
    spikes = dark_hour_spikes(align_clocks(df))
    for _, sp in spikes.iterrows():
        m = (df["device_id"] == sp["device"]) & (df["ts"] == sp["ts"])
        flags[m] += f"{sp['channel']}:dark_hour_single_sample;"

    df["qc_flags"] = flags
    # Drop the working `ts`: `timestamp` keeps the source text and `ts_aligned`
    # is the only datetime a consumer needs. For 7 of 8 devices they coincide.
    df = df.drop(columns=["ts"])
    rejections = (pd.concat(rejections, ignore_index=True) if rejections
                  else pd.DataFrame(columns=["device_id", "timestamp", "channel",
                                             "raw_value", "reason"]))
    return df, rejections


def audit(cleaned: pd.DataFrame, raw: pd.DataFrame, rejections: pd.DataFrame) -> pd.DataFrame:
    """Re-check the output before anyone downstream reads it.

    Write-Audit-Publish: nothing is published until it passes. Each row is a
    claim the cleaning pass makes about itself.
    """
    checks = []
    checks.append(("no duplicate keys remain", not cleaned.duplicated(["device_id", "timestamp"]).any(),
                   f"{int(raw.duplicated(['device_id', 'ts']).sum())} dropped"))
    for channel, (lo, hi) in IMPOSSIBLE.items():
        bad = int(((cleaned[f"{channel}_clean"] < lo) | (cleaned[f"{channel}_clean"] > hi)).sum())
        checks.append((f"{channel}: no impossible values left", bad == 0, f"{bad} remain"))
    checks.append(("raw columns untouched",
                   all(cleaned[c].equals(
                       raw.drop_duplicates(["device_id", "ts"]).reset_index(drop=True)[c])
                       for c in CHANNELS),
                   f"all {len(CHANNELS)} raw channels match the source"))
    # Reconcile rejections against the cleaned values, BOTH ways.
    #
    # The first version of this check asked "is there at least one null in
    # moisture?" -- which any unrelated null satisfies, so it could approve the
    # exact defect it claimed to prevent: 1,344 restored frozen values still
    # passed, carried by 61 impossible-value nulls elsewhere. Asserting the PAIR
    # cannot be satisfied by a null somewhere else.
    unapplied = 0
    for channel, grp in rejections.groupby("channel"):
        vals = cleaned.set_index(["device_id", "timestamp"])[f"{channel}_clean"]
        unapplied += int(vals.reindex(
            grp.set_index(["device_id", "timestamp"]).index).notna().sum())
    checks.append(("every rejection is null in its clean column",
                   unapplied == 0,
                   f"{unapplied} of {len(rejections)} rejections still hold a value"))

    unexplained = {c: int(cleaned[f"{c}_clean"].isna().sum())
                   - int((rejections["channel"] == c).sum()) for c in CHANNELS}
    orphaned = {k: v for k, v in unexplained.items() if v}
    checks.append(("every null has a rejection behind it",
                   not orphaned,
                   f"unexplained: {orphaned or 'none'}"))

    # Flags must reconcile with their detector too, not only rejections. The
    # first version of this gate checked the dark-hour flags and stopped there:
    # stripping all 736 `outside_spec` flags still passed all 13 checks, so the
    # gate could approve data where every out-of-spec warning had vanished.
    #
    # Nulled values are excluded by `notna()`: an impossible reading has already
    # been emptied and recorded as a rejection, so it is not double-counted here.
    for channel, (lo, hi) in SPEC.items():
        col = f"{channel}_clean"
        detected = cleaned[col].notna() & ((cleaned[col] < lo) | (cleaned[col] > hi))
        flagged = cleaned["qc_flags"].fillna("").str.contains(f"{channel}:outside_spec")
        missed, extra = int((detected & ~flagged).sum()), int((~detected & flagged).sum())
        checks.append((f"{channel}: outside_spec flags match the detector",
                       missed == 0 and extra == 0,
                       f"{int(detected.sum())} detected -- {missed} unflagged, "
                       f"{extra} flagged but in range"))

    # `ts_aligned` is the right time base here: the ceiling is a time-of-day
    # question, so a device with a clock offset must be judged on real local
    # time, not on what its clock said.
    spikes_left = len(dark_hour_spikes(
        cleaned.rename(columns={"ts_aligned": "ts"}), channel="light_par_clean"))
    spikes_kept = int(cleaned["qc_flags"].fillna("")
                      .str.contains("dark_hour_single_sample").sum())
    # The detector and the flag must agree. The COUNT is data-dependent and must
    # not be asserted -- an earlier version hardcoded `== 8`, which would break
    # silently on a fleet that produced a ninth spike.
    checks.append(("every dark-hour spike is flagged, and nothing else is",
                   spikes_left == spikes_kept,
                   f"{spikes_left} detected, {spikes_kept} flagged"))
    checks.append(("every rejection has a reason",
                   bool(rejections["reason"].notna().all() and len(rejections) > 0),
                   f"{len(rejections)} rejections recorded"))

    # The detector and the remediation must agree. If they drift, a new device
    # with the same fault is flagged but never fixed -- and nothing complains.
    detected, declared = detect_unit_outliers(raw), set(UNIT_FIXES)
    checks.append(("detected unit outliers are all fixed",
                   detected <= declared, f"detected {sorted(detected)}, fixed {sorted(declared)}"))
    checks.append(("declared unit fixes were all detected",
                   declared <= detected, f"fixed {sorted(declared)}, detected {sorted(detected)}"))
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])
