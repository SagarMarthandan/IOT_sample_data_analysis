"""Task 3: the first pass a modelling team can trust.

Raw is immutable. Every fix lands in a NEW column and the original is kept
alongside it. Nothing is clipped, averaged or interpolated.
"""

import json

import numpy as np
import pandas as pd

from .domain import CHANNELS, CLOCK_OFFSET_H, IMPOSSIBLE, SPEC, UNIT_FIXES
from .sensors import (align_clocks, dark_hour_spikes, detect_unit_outliers,
                      frozen_windows)

#: Columns that make up a reading's payload. Two rows with the same key are
#: identical only if every one of these agrees -- otherwise they are conflicting
#: and unorderable.
CHANNEL_COLS = [*CHANNELS, "substrate_label"]

#: `channel` value marking a rejection of a WHOLE ROW rather than one value.
ROW_REJECTION = "(row)"

#: The rejection ledger's columns. `raw_value` identifies the value for a
#: single-value rejection; a whole-row rejection has no single value, so it
#: carries its payload in `row_payload` instead.
LEDGER_COLS = ["device_id", "timestamp", "ts_aligned", "channel", "raw_value",
               "row_payload", "reason"]


def clean(sensor: pd.DataFrame, windows: pd.DataFrame) -> tuple:
    """Clean sensor readings while preserving source evidence.

    `sensor` contains parsed `ts` plus source-text `timestamp`; `windows` lists
    frozen runs in the device clock. Each correction writes a `_clean` column.
    Raw channels remain beside cleaned values, and no value is clipped, averaged,
    or interpolated.

    Duplicate keys are losslessly deduplicated only when every payload field
    agrees. Any disagreement quarantines every row at that key because no
    ordering rule can identify a true value. The rejection ledger preserves
    enough information to inspect every nulled value later -- values are set
    to NULL in the `_clean` column, never deleted, and whole rows appear in the
    ledger only when a conflicting duplicate is quarantined.

    `timestamp` remains the delivered text, including SENS-07 DD/MM and ISO
    formats. `ts_aligned` is the uniform, clock-corrected datetime used for
    downstream joins. Rejections retain device, source timestamp, aligned time,
    channel, raw value, reason, and whole-row payload where applicable.

    Impossible values and frozen readings become null in their clean columns.
    Out-of-spec values stay with flags because the vendor guarantee is weaker
    than a proof of an invalid reading. Isolated dark-hour spikes also remain
    values with `qc_flags`: a true temporary light source is possible.

    `qc_flags` is additive text per retained row. The ledger uses `(row)` for a
    duplicate-key quarantine, where `raw_value` has no single meaning and
    `row_payload` contains the original channel payload. Value-level rejections
    retain `raw_value` and leave `row_payload` empty. Both cases keep one stable
    schema so a consumer can count, filter, and preserve all rejection types.

    Returns `(cleaned, rejections)`.
    """
    df = sensor.reset_index(drop=True).copy()
    rejections = []

    # F2 clock: align before duplicate handling so ledger and cleaned rows share
    # the same datetime key. The raw timestamp column remains untouched.
    offset = pd.to_timedelta(df["device_id"].map(CLOCK_OFFSET_H).fillna(0), unit="h")
    df["ts_aligned"] = df["ts"] - offset

    # Only identical duplicate payloads are losslessly deduplicated. Any
    # disagreement makes the whole key unorderable, so every version is
    # quarantined with its payload; choosing one would invent a fact.
    key = ["device_id", "ts"]
    distinct = df.drop_duplicates(key + CHANNEL_COLS)     # identical twins collapse
    conflicted = distinct.loc[distinct.duplicated(key, keep=False), key].drop_duplicates()
    conflict = pd.MultiIndex.from_frame(df[key]).isin(
        pd.MultiIndex.from_frame(conflicted))
    if conflict.any():
        head = df.loc[conflict, ["device_id", "timestamp", "ts_aligned"]].copy()
        head["channel"] = ROW_REJECTION
        head["raw_value"] = np.nan
        # Quarantined rows survive only in the ledger, so it stores each payload.
        head["row_payload"] = [json.dumps(p, default=str, sort_keys=True)
                               for p in df.loc[conflict, CHANNEL_COLS].to_dict("records")]
        head["reason"] = (f"conflicting_duplicate: {len(conflicted)} key(s) carry "
                          "payloads that disagree -- every version quarantined, "
                          "none chosen")
        rejections.append(head[LEDGER_COLS])
        df = df.loc[~conflict].reset_index(drop=True)
    df = df.drop_duplicates(key).reset_index(drop=True)

    # F1 units: start _clean as a copy, then convert where declared
    for channel in CHANNELS:
        df[f"{channel}_clean"] = df[channel]
    for device, fixes in UNIT_FIXES.items():
        for channel, kind in fixes.items():
            if kind == "fahrenheit":
                m = df["device_id"] == device
                df.loc[m, f"{channel}_clean"] = (df.loc[m, channel] - 32) * 5 / 9

    # Two per-row reason columns, in the same shape: `qc_nulled` says which
    # values were emptied (and why), `qc_flags` says which were kept and marked.
    # The raw column beside each `_clean` one still holds the value, so the
    # published table shows both the number and the reason it is not trusted.
    nulled = pd.Series("", index=df.index)
    flags = pd.Series("", index=df.index)

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
        nulled[m] += f"{w['channel']}:frozen_channel;"
        df.loc[m, col] = np.nan

    # F5/F6 two-tier: null the impossible, flag the merely out-of-spec
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
            nulled[impossible] += f"{channel}:impossible;"
            df.loc[impossible, col] = np.nan

        if channel in SPEC:
            lo_spec, hi_spec = SPEC[channel]
            out = df[col].notna() & ((df[col] < lo_spec) | (df[col] > hi_spec))
            flags[out] += f"{channel}:outside_spec;"

    # Dark-hour spikes are physically possible, so flag rather than null them.
    # Use aligned time for detection and for the flagged row.
    aligned = align_clocks(df)
    spikes = dark_hour_spikes(aligned)
    for _, sp in spikes.iterrows():
        m = (df["device_id"] == sp["device"]) & (aligned["ts"] == sp["ts"])
        flags[m] += f"{sp['channel']}:dark_hour_single_sample;"

    df["qc_nulled"] = nulled
    df["qc_flags"] = flags
    # Keep source text and the consumer datetime; drop the working time column.
    df = df.drop(columns=["ts"])
    # Reindex so the ledger schema is independent of this batch's defect types.
    rejections = (pd.concat(rejections, ignore_index=True) if rejections
                  else pd.DataFrame(columns=LEDGER_COLS)).reindex(columns=LEDGER_COLS)
    return df, rejections


def audit(cleaned: pd.DataFrame, raw: pd.DataFrame, rejections: pd.DataFrame) -> pd.DataFrame:
    """Audit the cleaning output before publishing it.

    `raw` is the frame passed to `clean()`. The audit re-derives retained keys,
    duplicate quarantine, frozen windows, unit-outlier detection, and flags
    instead of trusting cleaner intermediates. It checks each impossible bound
    against the clean columns, raw-channel preservation after key alignment, and
    arithmetic Fahrenheit conversion for every declared present device.

    Reconciliation uses `(device_id, timestamp)`, channel, and detector output.
    Aggregate counts can place nulls, flags, or ledger rows on wrong readings.
    Frozen windows are detected again from raw and compared in device-clock time;
    out-of-spec flags and dark-hour flags reconcile both missing and extra keys.

    The ledger links every value-level null to a reason. Whole-row duplicate
    quarantine instead requires every conflicting source row and payload. A clean
    batch may have an empty ledger; a defective batch accounts for every source
    row exactly once as retained, losslessly deduplicated, or quarantined.
    """
    checks = []
    checks.append(("no duplicate keys remain",
                   not cleaned.duplicated(["device_id", "timestamp"]).any(),
                   f"{len(raw) - len(cleaned)} row(s) left the frame; "
                   f"{int(raw.duplicated(['device_id', 'ts'], keep=False).sum())} shared a key"))
    for channel, (lo, hi) in IMPOSSIBLE.items():
        bad = int(((cleaned[f"{channel}_clean"] < lo) | (cleaned[f"{channel}_clean"] > hi)).sum())
        checks.append((f"{channel}: no impossible values left", bad == 0, f"{bad} remain"))

    # Key accounting: every source row is retained, losslessly deduplicated, or
    # quarantined with its payload.
    key = ["device_id", "timestamp"]
    distinct = raw.drop_duplicates(key + CHANNEL_COLS)
    conflicted = distinct.loc[distinct.duplicated(key, keep=False), key].drop_duplicates()
    marked = raw.merge(conflicted, on=key, how="left", indicator=True)
    keep = marked["_merge"].eq("left_only")
    expected = marked.loc[keep].drop_duplicates(key)      # one row per clean key
    deduped = int(keep.sum()) - len(expected)
    quarantined = raw.merge(conflicted, on=key)
    checks.append(("every source row is retained, deduped or quarantined",
                   len(cleaned) == len(expected)
                   and len(raw) == len(cleaned) + deduped + len(quarantined),
                   f"{len(raw):,} source = {len(cleaned):,} retained + {deduped} "
                   f"identical duplicate(s) + {len(quarantined)} quarantined"))
    # Align by key before comparison so an unchanged reordering passes.
    left = cleaned.sort_values(key, ignore_index=True)
    right = expected.sort_values(key, ignore_index=True)
    untouched = all(left[c].equals(right[c]) for c in CHANNELS)
    checks.append(("raw columns untouched", untouched,
                   f"all {len(CHANNELS)} raw channels equal the source on "
                   f"{len(right):,} keys"))
    # Reconcile rejections against cleaned values by key and channel.
    unapplied = 0
    # `(row)` quarantines an entire duplicate key; the accounting check covers it.
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

    # `qc_nulled` is a claim the published table makes about itself, so it is
    # reconciled against the ledger like every other claim: same keys, same
    # channels. Without this, the column could name the wrong values and the
    # reader would have no way to see it.
    ledger_nulls = rejections[rejections["channel"] != ROW_REJECTION]
    want = set(zip(ledger_nulls["device_id"], ledger_nulls["timestamp"],
                   ledger_nulls["channel"]))
    named = {(d, t, part.split(":")[0])
             for d, t, tok in zip(cleaned["device_id"], cleaned["timestamp"],
                                  cleaned["qc_nulled"].fillna(""))
             for part in tok.split(";") if part}
    checks.append(("qc_nulled names exactly the ledger's value rejections",
                   named == want,
                   f"{len(want)} value(s) in the ledger, {len(named)} named -- "
                   f"{len(want - named)} missing, {len(named - want)} extra"))

    # Re-detect frozen windows from raw instead of trusting the supplied windows.
    # Convert aligned timestamps back because windows use the device clock.
    ts_raw = cleaned["ts_aligned"] + pd.to_timedelta(
        cleaned["device_id"].map(CLOCK_OFFSET_H).fillna(0), unit="h")
    ledger_keys = set(zip(rejections["device_id"], rejections["timestamp"]))
    windows = frozen_windows(raw)
    unhandled = []
    for _, w in windows.iterrows():
        m = (cleaned["device_id"].eq(w["device"])
             & (ts_raw >= w["first"]) & (ts_raw <= w["last"]))
        handled = (m.any()
                   and cleaned.loc[m, f"{w['channel']}_clean"].isna().all()
                   and all(k in ledger_keys for k in
                           zip(cleaned.loc[m, "device_id"], cleaned.loc[m, "timestamp"])))
        if not handled:
            unhandled.append(f"{w['device']} {w['channel']} ({w['samples']} samples)")
    checks.append(("every frozen window in the source is nulled and recorded",
                   not unhandled,
                   f"{len(windows)} window(s) re-detected from raw; "
                   f"unhandled: {unhandled or 'none'}"))

    # Reconcile each out-of-spec flag with its detector. Nulled impossible values
    # are excluded because their rejection is already recorded.
    for channel, (lo, hi) in SPEC.items():
        col = f"{channel}_clean"
        detected = cleaned[col].notna() & ((cleaned[col] < lo) | (cleaned[col] > hi))
        flagged = cleaned["qc_flags"].fillna("").str.contains(f"{channel}:outside_spec")
        missed, extra = int((detected & ~flagged).sum()), int((~detected & flagged).sum())
        checks.append((f"{channel}: outside_spec flags match the detector",
                       missed == 0 and extra == 0,
                       f"{int(detected.sum())} detected -- {missed} unflagged, "
                       f"{extra} flagged but in range"))

    # Use aligned local time and reconcile dark-hour flags by key, not count.
    spikes = dark_hour_spikes(cleaned.rename(columns={"ts_aligned": "ts"}))
    detected = {(sp["device"], sp["ts"]) for _, sp in spikes.iterrows()}
    flagged_rows = cleaned.loc[cleaned["qc_flags"].fillna("")
                               .str.contains("dark_hour_single_sample")]
    flagged = set(zip(flagged_rows["device_id"], flagged_rows["ts_aligned"]))
    checks.append(("every dark-hour spike is flagged, and nothing else is",
                   detected == flagged,
                   f"{len(detected)} spike(s) detected, {len(flagged)} flagged -- "
                   f"{len(detected - flagged)} unflagged, "
                   f"{len(flagged - detected)} flagged without a spike"))
    # An empty ledger passes for a healthy batch.
    checks.append(("every rejection has a reason",
                   bool(rejections["reason"].notna().all()),
                   f"{len(rejections)} rejections recorded"))

    # Re-derive declared unit conversions from raw to audit shipped values.
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

    # Every conflicting-key row needs its payload in the ledger.
    logged = rejections[rejections["channel"] == ROW_REJECTION]
    logged_keys = sorted(zip(logged["device_id"], logged["timestamp"]))
    raw_keys = sorted(zip(quarantined["device_id"], quarantined["timestamp"]))
    checks.append(("every row of a conflicting key is quarantined, with its payload",
                   logged_keys == raw_keys
                   and bool(logged["row_payload"].notna().all()),
                   f"{len(raw_keys)} conflicting row(s) in raw, {len(logged_keys)} "
                   f"quarantined; {int(logged['row_payload'].isna().sum())} "
                   f"without a payload"))
    # Only declared fixes for devices present in this batch are owed detection.
    present = set(raw["device_id"].unique())
    owed = declared & present
    checks.append(("declared unit fixes were all detected",
                   owed <= detected, f"declared {sorted(owed)} of the "
                   f"{len(declared)} declared, present in this batch; "
                   f"detected {sorted(detected)}"))
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])
