"""Domain assertions for hardware, vendor ranges, and policy limits.

This module contains no I/O or pandas so pipeline code depends on domain
knowledge without importing pipeline concerns. Values are declared assumptions
to review when hardware, environment, vendor evidence, or deployment changes.
`SPEC` records vendor guarantees; `IMPOSSIBLE` records the stricter nulling
policy used by cleaning.

`CADENCE`, `CHANNELS`, offsets, and remediation tables are shared constants.
They describe source and deployment facts rather than values inferred from a
single batch.
"""

from datetime import timedelta

# 15-minute maximum cadence gives 96 daily slots and this 2,016-slot window.
# Offsets are hours to subtract; SENS-07's 22:00 is really 20:00.
CLOCK_OFFSET_H = {"SENS-07": 2}

CADENCE = timedelta(minutes=15)
CHANNELS = [
    "soil_moisture_vwc",
    "soil_temp_c",
    "ec_us_cm",
    "light_par",
    "air_humidity_pct",
]

# FYTA published measuring ranges. A violation signals an instrument or
# conversion problem rather than an outlier to trim. Soil temperature is absent:
# FYTA publishes an ambient range, which cannot be applied to a soil reading
# (D12).
SPEC = {
    "soil_moisture_vwc": (0, 65),
    "ec_us_cm": (300, 1700),
    "air_humidity_pct": (0, 100),
    "light_par": (0, 2000),
}


FROZEN_MIN_RUN = 48                                       # F3, 12 hours

#: Values that can remain unchanged without a fault, including PAR at zero from
#: dusk to dawn.
LEGITIMATE_PLATEAU = {"light_par": 0.0}


# Per-device defects are declared here; a new device fault changes these tables.
UNIT_FIXES = {"SENS-07": {"soil_temp_c": "fahrenheit"}}   # F1




# Two tiers distinguish values known to be unusable from values outside the
# vendor guarantee. Values outside `IMPOSSIBLE` are nulled and recorded; values
# outside `SPEC` but inside `IMPOSSIBLE` remain available with a flag.
#
# `IMPOSSIBLE` combines physical, definitional, and deployment-plausibility
# bounds. The latter are policy, revisited when D1 is answered. The ceilings are
# deliberately wide, 1.25x-12x above specification. A narrow bound irreversibly
# nulls real data; a wide bound leaves visible, reversible flags. Do not derive
# them from current data: a fleet-wide fault could shift a quantile or 3-sigma
# cutoff with the defect.
IMPOSSIBLE = {
    "soil_moisture_vwc": (0, 100),      # definitional: a volume fraction
    "soil_temp_c": (-30, 70),           # potted soil. Below -30 it is frozen
                                        # solid, above 70 it would kill the
                                        # plant. Wide enough for a Berlin
                                        # winter outdoors. Checked after the
                                        # unit fix: before it, SENS-07's
                                        # 61.9-78.0 F reads as 62-78 C and 982
                                        # good readings get nulled
    "ec_us_cm": (0, 20_000),            # ~12x the published ceiling, ~40% of
                                        # seawater. Real salinity must survive
    "light_par": (0, 2_500),            # full summer sun is ~2000-2200. 2500
                                        # is "brighter than the sun"
    "air_humidity_pct": (0, 100),       # definitional: capped by definition
}
