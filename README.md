# IOT_sample_data_analysis

Data-quality assessment of a synthetic IoT soil-sensor fleet — 8 devices,
~16,000 readings over three weeks. Nine tasks: ingest and orient, quality
analysis, cleaning, source validation, a per-plant feature table,
triangulation, a pipeline design sketch, and two optional stretches.

## Run it

```bash
cd submission
uv run fyta_pipeline.py          # writes out/ and the full run log
```

Idempotent: same input, same output. `submission/fyta_analysis.ipynb` imports
the same code and renders the narrative with the figures.

## Layout

```
data/                     the four source tables — never written to
docs/                     findings, decisions, open questions, pipeline design
submission/
  fyta/                   the logic, split by change reason
    domain.py               assertions; no I/O, no pandas
    sensors.py              Tasks 1-2 — read, detect, findings
    cleaning.py             Task 3  — two-tier clean + audit gate
    sources.py              Tasks 4, 6 — source assessment, triangulation
    features.py             Task 5  — the per-plant feature table
    signals.py              Tasks 8, 9 — a derived signal, log text
  fyta_pipeline.py        entry point + printed narrative
  fyta_analysis.ipynb     the same results, rendered
  out/                    published artefacts and the run log
```

## Outputs

`submission/out/`: `cleaned_sensor.csv`, `qc_rejections.csv`,
`plant_features.csv`, one CSV per analysis section, `figures/`, and `run.log`.

## Notes

Raw data is never modified — every fix lands in a **new** column with the
original kept beside it, and nothing is clipped, averaged or interpolated.
`AGENTS.md` records the rules this follows and why.
