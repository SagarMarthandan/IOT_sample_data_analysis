"""Task 4: is the image model fit to consume?

A third-party model is a SOURCE. The question is not whether it is accurate in
the abstract but what it can and cannot be checked against.
"""

import json

import numpy as np
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


#: A fertiliser response must CLEAR the sensor's own step noise, and it must be
#: a RISE. Three sigma is already a low bar; nothing here reaches even one.
LEG_SIGMA = 3.0
#: The image model has to actually assert something before it can corroborate.
LEG_PROB = 0.10
#: How close a photo must be AFTER the event to count as evidence about it.
#: Asymmetric on purpose -- a photo taken before cannot be a response to it.
IMAGE_WINDOW_H = 48.0


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

    The image window is ASYMMETRIC for the same reason. Only photos taken after
    the event are considered, and the model leg reports a score LEVEL, not a
    change -- see the note at the legs below.
    """
    win = pd.Timedelta(window)
    rows = []
    for _, lg in contextual[contextual["log_type"] == "fertilising"].iterrows():
        plant, at = lg["user_plant_id"], lg["created_at"]
        g = features[features["user_plant_id"] == plant]

        # EVERY probe the plant owns, not probe 1. The first version read `ec_1`
        # and `device_1`, so a fixture where probe 1 sat flat while probe 2 rose
        # 500 uS/cm came back "no rise" -- the plant's own second instrument
        # contradicted the answer and was never consulted.
        #
        # Sigma is per probe, because a probe's own step noise is the only fair
        # yardstick: SENS-03's drift would inflate any pooled figure.
        sigmas = {}
        for i in (1, 2):
            dev_col, ec_col = f"device_{i}", f"ec_{i}"
            if dev_col not in g.columns or ec_col not in g.columns:
                continue
            dev = g[dev_col].iloc[0]
            if pd.isna(dev):
                continue
            b = g.loc[(g["ts_aligned"] > at - win) & (g["ts_aligned"] <= at), ec_col]
            a = g.loc[(g["ts_aligned"] > at) & (g["ts_aligned"] <= at + win), ec_col]
            sd = cleaned.loc[cleaned["device_id"] == dev, "ec_us_cm_clean"].diff().std()
            # A missing side is NOT evidence of no response. Without a baseline
            # there is nothing to compare against, so the window is untestable.
            if len(a) and len(b) and not pd.isna(sd) and sd > 0:
                sigmas[str(dev)] = float((a.mean() - b.mean()) / sd)
        best = max(sigmas, key=lambda d: sigmas[d]) if sigmas else None

        near = heads[heads["user_plant_id"] == plant]
        hours = ((near["captured_at"] - at).dt.total_seconds() / 3600
                 if len(near) else pd.Series(dtype=float))
        # ASYMMETRIC window. A photo taken BEFORE a fertilising event cannot be a
        # response to it. The first version used `hours.abs() <= 48`, so a fixture
        # whose only photo was 2.5 hours EARLIER came back corroborated=True.
        post = near.loc[(hours >= 0) & (hours <= IMAGE_WINDOW_H)] if len(near) else near
        only_pre = bool(len(near) and not len(post)
                        and ((hours < 0) & (hours >= -IMAGE_WINDOW_H)).any())
        if len(post):
            offs = (post["captured_at"] - at).dt.total_seconds() / 3600
            pick = offs.idxmin()
            image_at = post.loc[pick, "captured_at"]
            hours_off = round(float(offs.loc[pick]), 1)
            nutrient = float(post.loc[pick, "Nutrient deficiency"])
        else:
            image_at, hours_off, nutrient = pd.NaT, None, None

        rows.append({
            "log": lg["log_id"], "plant": plant, "fertilised": at,
            "d_ec_sigma": sigmas[best] if best else np.nan,
            "probe_leg": best or "no probe had a window",
            "leg_detail": ", ".join(f"{d} {s:+.2f}" for d, s in sigmas.items())
                          or "no probe had both a baseline and a response window",
            "image": image_at, "hours_off": hours_off, "nutrient_def": nutrient,
            "only_pre_event_image": only_pre,
        })

    out = pd.DataFrame(rows)
    # A RISE, not a change. `.abs()` here would let a large FALL count as
    # corroboration -- the opposite of the hypothesis under test. The label was
    # once quietly renamed from "rises" to "moves" to match the code, which hid
    # the error rather than fixing it.
    #
    # Three states, not two. An untestable window is not a failed one: reporting
    # `NaN` as "no rise" counts absent evidence as negative evidence.
    out["d_ec_sigma"] = out["d_ec_sigma"].round(2)
    out["sensor_leg"] = np.where(
        out["d_ec_sigma"].isna(), "not testable",
        np.where(out["d_ec_sigma"] > LEG_SIGMA, "rises", "no rise"))
    # "no post-event image" is not the same finding as "the model looked and
    # stayed silent", so it is its own state. And even a post-event score is a
    # LEVEL, not a change: it shows the symptoms were present after the feed, not
    # that the model responded to it. A pre/post comparison would test the latter,
    # but 28 photos across 5 events rarely put one on each side of an event.
    out["model_leg"] = "no post-event image"
    out["nutrient_def"] = pd.to_numeric(out["nutrient_def"], errors="coerce")
    out.loc[out["nutrient_def"].notna() & (out["nutrient_def"] <= LEG_PROB), "model_leg"] = "silent"
    out.loc[out["nutrient_def"].fillna(0) > LEG_PROB, "model_leg"] = "responds"
    out["corroborated"] = out["sensor_leg"].eq("rises") & out["model_leg"].eq("responds")
    return out
