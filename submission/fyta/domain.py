"""Domain assertions -- what the hardware and the physics permit.

No I/O and no pandas: this module has to be readable and reviewable without
knowing that CSVs exist (AGENTS.md §7). Pipeline code depends on domain
knowledge, never the reverse.
"""

from datetime import timedelta

# 15 min = 4/hour = the sensor's maximum rate (spec: 1/hour typical, up to
# 4/hour), so a day is 96 slots and this window is 2,016 -- not 504.
# Declared per-device clock offsets, in hours to subtract. A time-of-day check
# cannot be right without this: SENS-07's 22:00 is really 20:00.
CLOCK_OFFSET_H = {"SENS-07": 2}

CADENCE = timedelta(minutes=15)
CHANNELS = [
    "soil_moisture_vwc",
    "soil_temp_c",
    "ec_us_cm",
    "light_par",
    "air_humidity_pct",
]

# FYTA's published measuring ranges (docs/DATA.md). Outside these the device is
# not specified to be reliable -- so a violation is evidence of instrument or
# conversion failure, not an outlier to trim.
#
# soil_temp_c is absent on purpose: FYTA publishes an *ambient* range, and
# applying it to a soil reading is a category error. See D12 in
# docs/decision_register.md -- every threshold here rests on a conversation.
SPEC = {
    "soil_moisture_vwc": (0, 65),
    "ec_us_cm": (300, 1700),
    "air_humidity_pct": (0, 100),
    "light_par": (0, 2000),
}


FROZEN_MIN_RUN = 48                                       # F3, 12 hours


# Per-device defects found in Task 2, declared rather than sniffed at runtime.
# A new device with the same fault is a change to these tables, not to the code.
UNIT_FIXES = {"SENS-07": {"soil_temp_c": "fahrenheit"}}   # F1




# Two tiers, because "outside spec" and "provably wrong" are different claims.
# IMPOSSIBLE -> null it. Outside SPEC but inside IMPOSSIBLE -> flag and keep:
# the device is not specified to be accurate there, which is not the same as
# the reading being wrong. Nulling SENS-04's peaks would delete the sawtooth.
#
# Two of these bounds are DEFINITIONAL -- arithmetic, not judgement. The other
# three are physics judgements, and deliberately WIDE: a bound set too narrow
# nulls real data (destructive, unrecoverable), while one set too wide merely
# leaves junk flagged (visible, reversible). The impossible ceiling therefore
# sits 1.25x-12x above the specified one. They are deliberately NOT derived from
# the data -- a quantile or 3-sigma cut would move with the data, so a
# fleet-wide fault would shift the bound and hide inside it.
IMPOSSIBLE = {
    "soil_moisture_vwc": (0, 100),      # definitional: a volume fraction
    "soil_temp_c": (-30, 70),           # potted soil. Below -30 it is frozen
                                        # solid, above 70 it would kill the
                                        # plant. Wide enough for a Berlin
                                        # winter outdoors. Checked AFTER the
                                        # unit fix -- before it, SENS-07's
                                        # 61.9-78.0 F reads as 62-78 C and 982
                                        # good readings get nulled
    "ec_us_cm": (0, 20_000),            # ~12x the published ceiling, ~40% of
                                        # seawater. Real salinity must survive
    "light_par": (0, 2_500),            # full summer sun is ~2000-2200. 2500
                                        # is "brighter than the sun"
    "air_humidity_pct": (0, 100),       # definitional: capped by definition
}
