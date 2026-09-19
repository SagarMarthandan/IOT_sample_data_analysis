# Task 7 diagram prompt — Variant B (final)

Single-row layout, matching `Open_Source.jpeg` so the two sit side by side as a
pair. Reference arrows are given **by label, not by number** — the numbering in
the earlier prompt is what produced visible `1 2 3 …` labels on the OSS image.

**Save as:** `submission/images/task7_variant_b.jpeg`

---

```
A clean flat technical pipeline diagram, wide horizontal format. Pure white
background. No shadows, no 3D, no gradients, no glossy effects, no decorative
imagery, no people, no logos. Thin dark-grey rounded rectangles with short
black bold labels centred inside.

Draw ONE single horizontal row of exactly TEN (10) boxes, evenly spaced,
left to right, in this order:

  "BLE Soil Sensor"     amber fill
  "Phone App / Hub"     amber fill
  "AWS IoT Core"        orange fill
  "Basic Ingest"        orange fill
  "Amazon S3"           blue fill
  "dbt"                 violet fill
  "RDS Postgres"        green fill
  "Managed Grafana"     green fill
  "QuickSight"          green fill
  "SageMaker"           rose fill

Plus TWO more boxes, drawn OUTSIDE that row:
  "Quarantine"          violet fill, placed BELOW the "dbt" box
  "Kinesis (optional)"  pale grey fill with a DASHED border, placed ABOVE the
                        "Amazon S3" box, not inside any band

Draw each box exactly once. Do not repeat any box. There are TWELVE boxes in
total. Count them before you finish.

Small grey captions underneath these boxes only:
  under "AWS IoT Core":  "registry + auth"
  under "Basic Ingest":  "messaging free"
  under "Amazon S3":     "Parquet, event-date partitions"
  under "dbt":           "on DuckDB or Athena"

Grey arrows, 1 pixel. Draw exactly these arrows and NO others:

  "BLE Soil Sensor" -> "Phone App / Hub" -> "AWS IoT Core" -> "Basic Ingest"
  -> "Amazon S3" -> "dbt" -> "RDS Postgres"

  "RDS Postgres" -> "Managed Grafana"

  "RDS Postgres" -> "QuickSight"
      Draw this as a line that leaves the BOTTOM of "RDS Postgres", runs
      underneath "Managed Grafana", and turns up into the bottom of
      "QuickSight". Do not draw a direct arrow between "Managed Grafana" and
      "QuickSight".

  "dbt" -> "Quarantine"                 arrow pointing DOWN

  "AWS IoT Core" -> "Kinesis (optional)"     DASHED
  "Kinesis (optional)" -> "Amazon S3"        DASHED

  "SageMaker" -> "Amazon S3"            DASHED, routed ABOVE the boxes,
                                        with the small label "calibration curves"

Pale background bands behind the row of boxes, drawn side by side, each with a
small uppercase grey label at the BOTTOM edge of the band:

  "DEVICE"     behind "BLE Soil Sensor" and "Phone App / Hub"
  "INGEST"     behind "AWS IoT Core" and "Basic Ingest"
  "RAW"        behind "Amazon S3"
  "TRANSFORM"  behind "dbt"
  "SERVE"      behind "RDS Postgres", "Managed Grafana" and "QuickSight"
  "MODEL"      behind "SageMaker"

One more element: a small grey box labelled "Step Functions" near the TOP
RIGHT of the image, with thin dotted lines going down from it to three boxes:
"AWS IoT Core", "dbt" and "SageMaker".

Use a clean sans-serif font. Spell every label exactly as written above. Do NOT
number the boxes. Do not add any box, arrow, band, caption, text or annotation
that is not listed.
```

---

## Check before you save

| | |
|:---|:---|
| **Boxes** | 12 — the 10 in the row, plus Quarantine and Kinesis |
| **Row order** | BLE Soil Sensor · Phone App / Hub · AWS IoT Core · Basic Ingest · Amazon S3 · dbt · RDS Postgres · Managed Grafana · QuickSight · SageMaker |
| **Bands** | DEVICE · INGEST · RAW · TRANSFORM · SERVE · MODEL |
| **No `Ops Agent` bar** | managed services absorb that job — its absence is the point |

## The two differences from the OSS diagram

They should look like a pair, differing only in what the boxes are made of:

| OSS (`Open_Source.jpeg`) | AWS (this one) |
|:---|:---|
| Redpanda | **AWS IoT Core + Basic Ingest** |
| MinIO | **Amazon S3** |
| Postgres / Grafana / Metabase | **RDS Postgres / Managed Grafana / QuickSight** |
| MLflow | **SageMaker** |
| Airflow | **Step Functions** |
| Quarantine, under DuckDB | Quarantine, under dbt |
| **Ops Agent bar** | *(none — absorbed by managed services)* |
| — | **Kinesis (optional), dashed** |
