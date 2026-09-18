# Task 7 diagrams — Mermaid source

Exact text by construction. No image model, so no `Grafanna`.

**To export a PNG:** paste a block into <https://mermaid.live> → *Actions* →
*PNG* → save to `submission/out/figures/`. (Or GitHub renders these natively in
a `.md` file, which is the better home if you would rather not carry images.)

Both use the same left-to-right lane structure as the generated versions, so they
are drop-in replacements.

---

## Variant A — self-hosted / OSS

```mermaid
flowchart LR
  subgraph DEVICE
    A["BLE Soil Sensor"] --> B["Phone App / Hub"]
  end
  subgraph INGEST
    C["Redpanda<br/><small>Kafka API</small>"] --> D["Python Checks<br/><small>per-message only</small>"]
  end
  subgraph RAW
    E["MinIO<br/><small>Parquet, event-date partitions</small>"]
  end
  subgraph TRANSFORM
    F["dbt"] --> G["DuckDB"]
    G --> Q["Quarantine"]
  end
  subgraph SERVE
    H["Postgres"]
    I["Grafana"]
    J["Metabase"]
  end
  subgraph MODEL
    K["MLflow"]
  end

  B --> C
  D --> E
  E --> F
  G --> H
  H --> I
  H --> J

  K -. "curves" .-> G
  ORCH["Airflow"] -.-> D
  ORCH -.-> F
  OPS["Ops Agent"] -.-> C
  OPS -.-> ORCH
```

---

## Variant B — AWS managed

```mermaid
flowchart LR
  subgraph DEVICE
    A["BLE Soil Sensor"] --> B["Phone App / Hub"]
  end
  subgraph INGEST
    C["AWS IoT Core<br/><small>registry + auth</small>"] --> D["Basic Ingest<br/><small>messaging free</small>"]
  end
  subgraph RAW
    E["Amazon S3<br/><small>Parquet, event-date partitions</small>"]
  end
  subgraph TRANSFORM
    F["dbt<br/><small>on DuckDB or Athena</small>"]
    Q["Quarantine"]
  end
  subgraph SERVE
    H["RDS Postgres"]
    I["Managed Grafana"]
    J["QuickSight"]
  end
  subgraph MODEL
    K["SageMaker"]
  end

  B --> C
  D -.-> KI["Kinesis<br/><small>optional</small>"]
  KI -.-> E
  E --> F
  F --> Q
  F --> H
  H --> I
  H --> J
  K -. "calibration curves" .-> E

  SF["Step Functions"] -.-> C
  SF -.-> F
  SF -.-> K
```

---

## Why these are worth having either way

- **The labels are exact.** No model deciding that `Redpanda` belongs in the
  DEVICE lane.
- **They diff.** A Mermaid block in a git repo shows a reviewable change when the
  architecture changes; a PNG does not.
- **The trade-off:** a Mermaid-rendered PNG is plainer than the generated
  diagram. For a design sketch that is fine — it is a diagram, not a graphic.

If you would rather keep the Gemini version, use the good one you already have
and apply the two-label edit above. Either works; do not spend more generations
on it.
