"""Task 4: assess the image model as a source.

Assessment separates claims the model declares internally from claims checked
against paired sensor readings, mapping, and user logs. It tests taxonomy
coherence, probability-head consistency, source pairing, and correlations with
device-relative dryness. The module does not train, calibrate, or alter the
model.
"""

import json

import numpy as np
import pandas as pd

def image_predictions(images: pd.DataFrame) -> tuple:
    """Flatten model output into one row per photo and one column per head.

    Read head names and classification chains from each response rather than a
    transcribed taxonomy. A model version can add heads without a parallel column
    list. The deepest ancestor that is itself a scored head becomes the parent;
    unscored taxonomy labels cannot become score columns.

    Return `(heads, head_cols, children)`, where `children` contains scored child
    heads for each scored parent head.
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

    # A parent must be an emitted head; taxonomy labels without score columns are
    # not parents.
    children = {}
    for name, chain in chains.items():
        known = [c for c in chain if c in chains]
        if known:
            children.setdefault(known[-1], []).append(name)
    # Emitted heads define the ordered column list.
    return (pd.DataFrame(rows), list(chains),
            {k: sorted(set(v)) for k, v in children.items()})


def assess_source(sensor: pd.DataFrame, value: str, heads: pd.DataFrame,
                  head_cols: list, children: dict, mapping: pd.DataFrame,
                  contextual: pd.DataFrame) -> pd.Series:
    """Assess the image model against one sensor frame.

    Raw and cleaned sensor frames are passed separately. Metrics independent of
    sensors stay identical; differences identify conclusions dependent on
    cleaning. Photos pair with mapped device readings at capture time. A
    two-probe plant contributes two pairs rather than an invented averaged
    moisture value. Dryness is rank-based within device because raw VWC is
    substrate-specific.
    """
    # Rank dryness within device because VWC is substrate-specific.
    s = sensor.assign(_dry=1 - sensor.groupby("device_id")[value].rank(pct=True))

    # Losslessly deduplicate the join key to prevent F8 from fanning out pairs.
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


#: A fertiliser response must exceed each sensor's step noise and rise.
LEG_SIGMA = 3.0
#: The image model must assert a result before it corroborates.
LEG_PROB = 0.10
#: A photo must follow the event within this many hours.
IMAGE_WINDOW_H = 48.0


def triangulate(cleaned: pd.DataFrame, features: pd.DataFrame,
                contextual: pd.DataFrame, heads: pd.DataFrame,
                window: str = "24h") -> pd.DataFrame:
    """Triangulate each fertilising log with sensor and image evidence.

    `window` bounds before and after EC values for every mapped probe. The
    resulting probe change is divided by that device's EC step noise and must be
    positive and above `LEG_SIGMA`. Missing before or after observations, or
    non-finite or zero noise, leaves that probe untestable rather than treating
    absent evidence as a failed response.

    The bound separates a fertiliser response from F4 gain drift, whose EC climb
    begins ten days after the feed. `IMAGE_WINDOW_H` considers post-event photos
    only and selects the nearest. Its nutrient score is a level after the event,
    rather than a pre/post response; that comparison needs photos on both sides.

    The output preserves one row per fertilising log. `d_ec_sigma` names the
    strongest testable probe, `leg_detail` retains all mapped-probe results, and
    `only_pre_event_image` distinguishes a nearby pre-event photo from no nearby
    photo. Final corroboration requires both a sensor rise and a responding model
    score.

    `sensor_leg` has three states: rises, no rise, and not testable. `model_leg`
    separates no post-event image, silent score, and responding score. These
    states avoid collapsing missing evidence into a negative conclusion.

    The image leg does not infer disease causality. It reports whether the model
    asserted nutrient deficiency after the logged event within the stated window.
    """
    win = pd.Timedelta(window)
    rows = []
    for _, lg in contextual[contextual["log_type"] == "fertilising"].iterrows():
        plant, at = lg["user_plant_id"], lg["created_at"]
        g = features[features["user_plant_id"] == plant]

        # Evaluate every mapped probe. Scale each response by that probe's own
        # step noise so SENS-03 drift cannot inflate a pooled figure.
        sigmas, detail = {}, []
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
            # Both windows need valid observations and finite nonzero noise;
            # otherwise the probe is untestable.
            if not (b.notna().any() and a.notna().any()
                    and bool(np.isfinite(sd)) and sd > 0):
                detail.append(f"{dev} untestable")
                continue
            sigmas[str(dev)] = float((a.mean() - b.mean()) / sd)
            detail.append(f"{str(dev)} {sigmas[str(dev)]:+.2f}")
        best = max(sigmas, key=sigmas.get) if sigmas else None

        near = heads[heads["user_plant_id"] == plant]
        hours = ((near["captured_at"] - at).dt.total_seconds() / 3600
                 if len(near) else pd.Series(dtype=float))
        # Only post-event photos can be a response.
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
            "probe_leg": best or "no probe had a testable window",
            "leg_detail": ", ".join(detail) or "no probe is mapped to this plant",
            "image": image_at, "hours_off": hours_off, "nutrient_def": nutrient,
            "only_pre_event_image": only_pre,
        })

    out = pd.DataFrame(rows)
    # Require a rise: `.abs()` would count a fall. Keep untestable windows
    # separate from evidence of no rise.
    out["d_ec_sigma"] = out["d_ec_sigma"].round(2)
    out["sensor_leg"] = np.where(
        out["d_ec_sigma"].isna(), "not testable",
        np.where(out["d_ec_sigma"] > LEG_SIGMA, "rises", "no rise"))
    # Distinguish no post-event image from a silent score. Scores are post-event
    # levels; testing a response would require photos on both sides.
    out["model_leg"] = "no post-event image"
    out["nutrient_def"] = pd.to_numeric(out["nutrient_def"], errors="coerce")
    out.loc[out["nutrient_def"].notna() & (out["nutrient_def"] <= LEG_PROB), "model_leg"] = "silent"
    out.loc[out["nutrient_def"].fillna(0) > LEG_PROB, "model_leg"] = "responds"
    out["corroborated"] = out["sensor_leg"].eq("rises") & out["model_leg"].eq("responds")
    return out
