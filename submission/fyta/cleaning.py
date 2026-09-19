"""Task 3: the first pass a modelling team can trust.

Raw is immutable. Every fix lands in a NEW column and the original is kept
alongside it. Nothing is clipped, averaged or interpolated.
"""

import numpy as np
import pandas as pd

from .domain import CHANNELS, CLOCK_OFFSET_H, IMPOSSIBLE, SPEC, UNIT_FIXES
from .sensors import align_clocks, dark_hour_spikes, detect_unit_outliers

#: Columns that make up a reading's payload. Two rows with the same key are
#: identical only if every one of these agrees -- otherwise they are conflicting
#: and unorderable.
CHANNEL_COLS = [*CHANNELS, "substrate_label"]

#: `channel` value marking a rejection of a WHOLE ROW rather than one value.
ROW_REJECTION = "(row)"


def clean(sensor: pd.DataFrame, windows: pd.DataFrame) -> tuple:
    """First pass into something a modelling team can trust.

    Raw is immutable: every fix lands in a NEW column and the original is kept
    alongside it. Nothing is clipped, averaged or interpolated. Every value that
    is removed is recorded with its reason, in a separate table.

    TWO TIME COLUMNS, and the difference matters. `timestamp` is the SOURCE TEXT
    exactly as delivered -- mixed format on purpose, because SENS-07 writes
    DD/MM while the rest write ISO, and rewriting it would destroy the evidence
    that the two formats coexist. `ts_aligned` is the single datetime a consumer
    should use: ISO, uniform, clock-corrected. Anything that joins two outputs
    joins on `ts_aligned`.

    Returns (cleaned, rejections, flags).
    """
    df = sensor.reset_index(drop=True).copy()
    rejections = []

    # Duplicates come in two kinds, and only one is safe to dedupe.
    #
    #   identical payload  -> at-least-once redelivery. Lossless: keep one.
    #   conflicting payload -> unorderable. There is no rule that says which is
    #                          true, so keeping either silently invents a fact.
    #
    # AGENTS.md 4 forbids resolving those arbitrarily. Both are routed to the
    # ledger with the reason attached and removed from the cleaned frame -- the
    # grain stays intact, nothing is silently dropped, and both payloads survive
    # for whoever can order them.
    twin = df.duplicated(["device_id", "ts"], keep=False)
    identical = df.duplicated(["device_id", "ts"] + CHANNEL_COLS, keep=False)
    conflict = twin & ~identical
    if conflict.any():
        cols = ["device_id", "timestamp", "ts_aligned", "channel", "raw_value", "reason"]
        head = df.loc[conflict, ["device_id", "timestamp"]].copy()
        head["ts_aligned"] = head["timestamp"] - pd.to_timedelta(
            head["device_id"].map(CLOCK_OFFSET_H).fillna(0), unit="h")
        head["channel"] = ROW_REJECTION
        head["raw_value"] = np.nan
        head["reason"] = ("conflicting_duplicate: rows share this key and disagree "
                          "-- both quarantined, neither chosen")
        rejections.append(head[cols])
        df = df.loc[~conflict].reset_index(drop=True)
    df = df.drop_duplicates(["device_id", "ts"]).reset_index(drop=True)

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
            "ts_aligned": df.loc[m, "ts_aligned"],
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
                "ts_aligned": df.loc[impossible, "ts_aligned"],
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
                  else pd.DataFrame(columns=["device_id", "timestamp", "ts_aligned",
                                             "channel", "raw_value", "reason"]))
    return df, rejections


def audit(cleaned: pd.DataFrame, raw: pd.DataFrame, rejections: pd.DataFrame) -> pd.DataFrame:
    """Re-check the output before anyone downstream reads it.

    Write-Audit-Publish: nothing is published until it passes. Each row is a
    claim the cleaning pass makes about itself.
    """
    checks = []
    checks.append(("no duplicate keys remain",
                   not cleaned.duplicated(["device_id", "timestamp"]).any(),
                   f"{len(raw) - len(cleaned)} row(s) left the frame; "
                   f"{int(raw.duplicated(['device_id', 'ts'], keep=False).sum())} shared a key"))
    for channel, (lo, hi) in IMPOSSIBLE.items():
        bad = int(((cleaned[f"{channel}_clean"] < lo) | (cleaned[f"{channel}_clean"] > hi)).sum())
        checks.append((f"{channel}: no impossible values left", bad == 0, f"{bad} remain"))
    # Compared on the keys BOTH frames have, not positionally. Quarantining a
    # conflicting duplicate legitimately removes two rows, so a positional
    # `equals` would report the raw columns as edited when every surviving value
    # is byte-identical to the source.
    # `raw` still holds its duplicate deliveries, so it must be deduped before the
    # merge or the right side comes back 15 rows longer than the left and a
    # length mismatch reads as "the values were edited".
    shared = cleaned[["device_id", "timestamp"]].merge(
        raw[["device_id", "timestamp"]].drop_duplicates(), how="inner")
    left = cleaned.merge(shared, on=["device_id", "timestamp"], how="inner")
    right = (raw.drop_duplicates(["device_id", "timestamp"])
                .merge(shared, on=["device_id", "timestamp"], how="inner"))
    untouched = all(left[c].reset_index(drop=True).equals(right[c].reset_index(drop=True))
                    for c in CHANNELS)
    checks.append(("raw columns untouched", untouched,
                   f"all {len(CHANNELS)} raw channels match the source on "
                   f"{len(shared):,} shared keys"))
    # Reconcile rejections against the cleaned values, BOTH ways.
    #
    # The first version of this check asked "is there at least one null in
    # moisture?" -- which any unrelated null satisfies, so it could approve the
    # exact defect it claimed to prevent: 1,344 restored frozen values still
    # passed, carried by 61 impossible-value nulls elsewhere. Asserting the PAIR
    # cannot be satisfied by a null somewhere else.
    unapplied = 0
    # `(row)` is the whole-row sentinel used by the duplicate quarantine. It has
    # no `_clean` column to compare against and its rows are removed outright,
    # so it is reconciled by the quarantine check below instead.
    for channel, grp in rejections[rejections["channel"] != ROW_REJECTION].groupby("channel"):
        vals = cleaned.set_index(["device_id", "timestamp"])[f"{channel}_clean"]
        unapplied += int(vals.reindex(
            grp.set_index(["device_id", "timestamp"]).index).notna().sum())
    checks.append(("every rejection is null in its clean column",
                   unapplied == 0,
                   f"{unapplied} of {len(rejections)} rejections still hold a value"))

    unexplained = {c: int(cleaned[f"{c}_clean"].isna().sum())
                   - int((rejections["channel"] == c).sum()) for c in CHANNELS}  # noqa: E501
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
    # `len(rejections) > 0` used to be required here, which failed every healthy
    # batch: a clean input has nothing to reject, and a gate that fires on clean
    # input trains people to ignore it (AGENTS.md 5). An empty ledger is a pass.
    checks.append(("every rejection has a reason",
                   bool(rejections["reason"].notna().all()),
                   f"{len(rejections)} rejections recorded"))

    # The detector and the remediation must agree. If they drift, a new device
    # with the same fault is flagged but never fixed -- and nothing complains.
    #
    # `detected <= declared` alone was membership, not arithmetic: replacing every
    # corrected SENS-07 temperature with 25 degrees passed it. So the conversion
    # is re-derived here from the raw column and compared with what shipped.
    detected, declared = detect_unit_outliers(raw), set(UNIT_FIXES)
    checks.append(("detected unit outliers are all fixed",
                   detected <= declared, f"detected {sorted(detected)}, fixed {sorted(declared)}"))
    for device, fixes in UNIT_FIXES.items():
        for channel, kind in fixes.items():
            if kind != "fahrenheit":
                continue
            m = cleaned["device_id"] == device
            want = (cleaned.loc[m, channel] - 32) * 5 / 9
            their = cleaned.loc[m, f"{channel}_clean"]
            agree = bool(want.round(6).equals(their.round(6)))
            checks.append((f"{device}: {channel} conversion is arithmetic",
                           agree, "re-derived from raw, matches"
                           if agree else "does NOT match the declared conversion"))

    # Conflicting duplicates must be quarantined, not resolved. Quarantining
    # removes BOTH payloads, so the cleaned frame can legitimately have fewer
    # rows than the raw one -- but the difference is only legal if the ledger
    # accounts for it.
    conflict_raw = int(raw.duplicated(["device_id", "timestamp"], keep=False).sum()
                       - raw.duplicated(["device_id", "timestamp"] + CHANNEL_COLS,
                                        keep=False).sum())
    conflict_logged = int((rejections["channel"] == ROW_REJECTION).sum())
    checks.append(("conflicting duplicates are quarantined, not silently resolved",
                   conflict_logged >= conflict_raw,
                   f"{conflict_raw} conflicting rows in raw, {conflict_logged} quarantined"))
    # `declared <= detected` is the right shape but the wrong scope: a declared
    # fix for a device that is not in this batch was never expected to be
    # detected, so requiring it fails every input that lacks SENS-07. Only the
    # devices actually present are owed a detection.
    present = set(raw["device_id"].unique())
    owed = declared & present
    checks.append(("declared unit fixes were all detected",
                   owed <= detected, f"declared {sorted(owed)} of the "
                   f"{len(declared)} declared, present in this batch; "
                   f"detected {sorted(detected)}"))
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])
