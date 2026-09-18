"""Task 4: is the image model fit to consume?

A third-party model is a SOURCE. The question is not whether it is accurate in
the abstract but what it can and cannot be checked against.
"""

import json

import pandas as pd

def image_predictions(images: pd.DataFrame) -> tuple:
    """Flatten the model's output: one row per photo, one column per head.

    Also returns the head names, and the class hierarchy read from each head's
    own `classification` chain rather than transcribed here -- the model's
    taxonomy is the model's business, and a version bump must not need a code
    edit.

    Returns (heads, head_cols, children).
    """
    rows, chains = [], {}
    for _, r in images.iterrows():
        p = json.loads(r["prediction"])
        h = p["health_assessment"]
        row = {"image_id": r["image_id"], "user_plant_id": r["user_plant_id"],
               "captured_at": r["captured_at"], "is_plant": p["is_plant"],
               "is_plant_p": p["is_plant_probability"],
               "is_healthy": h["is_healthy"],
               "is_healthy_p": h["is_healthy_probability"]}
        row.update({d["name"]: d["probability"] for d in h["diseases"]})
        rows.append(row)
        chains.update({d["name"]: d["classification"] for d in h["diseases"]})

    # Parent = the deepest ancestor that is ITSELF a head. The last element of
    # the chain is not necessarily the parent: `nutrient-related issue` groups
    # Nutrient deficiency but is never scored, so it is a label on the taxonomy
    # rather than a class in it. Taking chain[-1] invents a parent that has no
    # column -- which is how this was first written, and how it failed.
    children = {}
    for name, chain in chains.items():
        known = [c for c in chain if c in chains]
        if known:
            children.setdefault(known[-1], []).append(name)
    # `chains` keys are every head the model emitted, in encounter order, so
    # there is no separate column list to keep in sync.
    return (pd.DataFrame(rows), list(chains),
            {k: sorted(set(v)) for k, v in children.items()})


def assess_source(sensor: pd.DataFrame, value: str, heads: pd.DataFrame,
                  head_cols: list, children: dict, mapping: pd.DataFrame,
                  contextual: pd.DataFrame) -> pd.Series:
    """Task 4: how far the image model can be trusted, against ONE sensor frame.

    Called twice -- raw values, then cleaned. Every metric that does not touch
    the sensors is identical by construction, so the delta between the two calls
    IS the result: it says which conclusions rest on Task 3's choices and which
    stand on their own.

    Two-sensor plants contribute two rows per photo, one per device. Averaging
    them is not an option -- it would invent a moisture value describing neither
    pot (F10, unresolved).
    """
    # Dryness WITHIN device. VWC is only comparable within a substrate, so an
    # absolute threshold is the wrong question across substrates; rank is the
    # right one. 1.0 = driest this device has been.
    s = sensor.assign(_dry=1 - sensor.groupby("device_id")[value].rank(pct=True))

    # Dedupe the right-hand key before joining. F8's duplicated rows would
    # otherwise fan the join out and multiply the pairs -- which is exactly the
    # mistake F9 documents. Lossless: the duplicates are byte-identical.
    pairs = (heads.merge(mapping, on="user_plant_id")
                  .merge(s.drop_duplicates(["device_id", "ts_aligned"])
                          [["device_id", "ts_aligned", "_dry"]],
                         left_on=["device_id", "captured_at"],
                         right_on=["device_id", "ts_aligned"], how="inner"))

    return pd.Series({
        "photos": len(heads),
        "is_plant: min probability": heads["is_plant_p"].min(),
        "is_plant: all True": float(heads["is_plant"].all()),
        "is_healthy == (prob > 0.5)":
            float((heads["is_healthy"] == (heads["is_healthy_p"] > 0.5)).all()),
        "hierarchy: max |parent - best child|": max(
            (heads[p] - heads[c].max(axis=1)).abs().max()
            for p, c in children.items()),
        "heads ever above 0.10": sum(heads[c].max() > 0.10 for c in head_cols),
        "photos paired to a reading": len(pairs),
        **{f"r({head}, dryness)": pairs[head].corr(pairs["_dry"])
           for head in head_cols},
        "log phrase -> one log_type": float(
            contextual.groupby("text")["log_type"].nunique().eq(1).all()),
        "species -> one substrate": float(
            mapping.merge(sensor.groupby("device_id")["substrate_label"].first(),
                          on="device_id")
                   .groupby("species")["substrate_label"].nunique().eq(1).all()),
    })


#: A response has to clear the sensor's own step noise to count. Three sigma is
#: already a low bar; nothing here reaches even one.
LEG_SIGMA = 3.0
#: The image model has to actually assert something before it can corroborate.
LEG_PROB = 0.10


def triangulate(cleaned: pd.DataFrame, features: pd.DataFrame,
                contextual: pd.DataFrame, heads: pd.DataFrame,
                window: str = "24h") -> pd.DataFrame:
    """Task 6: for each fertilising log, do the other two sources corroborate it?

    Three legs, and the answer is that the leg which fails is not the obvious one.

      the log     says fertiliser was added
      the sensor  EC should rise -- it should, that is chemistry
      the model   `Nutrient deficiency` should respond

    THE WINDOW IS THE TASK. Stretch it and UP-1002 looks confirmed: its EC climbs
    1,289 uS/cm across the record, so "fertilised, then EC rose" appears to hold.
    It does not -- the climb starts ten days after the feed and is a straight
    line, which is a gain drift (F4), not chemistry. A wide window manufactures
    that positive.

    A fix is on the same plant as the drift, so the two must be separated by
    timing, not by magnitude.
    """
    win = pd.Timedelta(window)
    rows = []
    for _, lg in contextual[contextual["log_type"] == "fertilising"].iterrows():
        plant, at = lg["user_plant_id"], lg["created_at"]
        g = features[features["user_plant_id"] == plant]
        before = g.loc[(g["ts_aligned"] > at - win) & (g["ts_aligned"] <= at), "ec_1"]
        after = g.loc[(g["ts_aligned"] > at) & (g["ts_aligned"] <= at + win), "ec_1"]
        # The device's own step noise, not a fleet-wide constant: SENS-03's
        # drift would inflate any pooled figure and hide a real response.
        noise = cleaned.loc[cleaned["device_id"] == g["device_1"].iloc[0],
                            "ec_us_cm_clean"].diff().std()

        near = heads[heads["user_plant_id"] == plant]
        near = near.iloc[(near["captured_at"] - at).abs().argsort()[:1]] if len(near) else near
        rows.append({
            "log": lg["log_id"], "plant": plant, "fertilised": at,
            "d_ec": after.mean() - before.mean(), "noise_sd": noise,
            "image": near["captured_at"].iloc[0] if len(near) else pd.NaT,
            "days_off": abs((near["captured_at"].iloc[0] - at).days) if len(near) else None,
            "nutrient_def": near["Nutrient deficiency"].iloc[0] if len(near) else None,
        })

    out = pd.DataFrame(rows)
    out["d_ec_sigma"] = (out["d_ec"] / out["noise_sd"]).round(2)
    # Two legs, judged separately, so a run where one corroborates and the other
    # does not is visible rather than collapsed into one word.
    out["sensor_leg"] = (out["d_ec_sigma"].abs() > LEG_SIGMA).map({True: "moves", False: "flat"})
    out["model_leg"] = (out["nutrient_def"] > LEG_PROB).map({True: "responds", False: "silent"})
    out["corroborated"] = out["sensor_leg"].eq("moves") & out["model_leg"].eq("responds")
    return out
