# IOT_sample_data_analysis

Data-quality assessment of a synthetic IoT soil-sensor fleet — 8 devices,
~16,000 readings over three weeks. Nine tasks: ingest and orient, quality
analysis, cleaning, source validation, a per-plant feature table,
triangulation, a pipeline design sketch, and two optional stretches.

## Run it

```bash
cd submission
uv run fyta_pipeline.py          # writes out/ and the full run log
uv run test_gates.py             # regression checks; each fails if its fix is reverted
```

Idempotent: same input, same output. `submission/fyta_analysis.ipynb` imports
the same code and renders the narrative with the figures.

The one-page submission note is `submission/WRITEUP.md` → `WRITEUP.pdf`. Edit
the Markdown and rebuild:

```bash
cd submission && uv run --with markdown python md_to_pdf.py
```

## Layout

```
data/                     the four source tables — never written to
docs/                     findings, decisions, open questions, pipeline design
submission/
  fyta/                   the logic, split by change reason
    domain.py               assertions; no I/O, no pandas
    sensors.py              Tasks 1-2 — read, detect, findings
    cleaning.py             Task 3  — two-tier clean + audit gate, and
                                    the image JSON → flat table
    sources.py              Tasks 4, 6 — source assessment, triangulation
    features.py             Task 5  — the per-plant feature table
    signals.py              Tasks 8, 9 — a derived signal, log text
  fyta_pipeline.py        entry point + printed narrative
  fyta_analysis.ipynb     the same results, rendered
  test_gates.py           regression checks; each one fails if its fix is reverted
  images/                 hand-made architecture diagrams the notebook embeds
                                  — NOT under out/, which is regenerated
  WRITEUP.md / .pdf       the one-page submission note
  md_to_pdf.py            builds the PDF: markdown -> HTML -> headless Chrome
  out/                    published artefacts and the run log (all regenerated)
```

## Outputs

`submission/out/`: `cleaned_sensor.csv`, `qc_rejections.csv`,
`images_flattened.csv`, `plant_features.csv`, one CSV per analysis section,
`figures/`, and `run.log`.

**Everything under `out/` is regenerable — delete it and re-run.** That makes it
the wrong home for anything the code does not write itself: a hand-made asset kept
there dies on the next `rm -rf out`, and nothing reports it. The architecture
diagrams the notebook embeds live in `submission/images/` for exactly that reason,
and `test_gates.py` fails if any image the notebook references is missing.

Two time columns, and the difference matters. `timestamp` is the **source text as
delivered** — mixed format on purpose, because SENS-07 writes DD/MM while the
rest write ISO — and rewriting it would destroy the evidence that both formats
coexist. `ts_aligned` is the ISO, uniform, clock-corrected column that every join
uses.

## Notes

Raw data is never modified — every fix lands in a **new** column with the
original kept beside it, and nothing is clipped, averaged or interpolated.
`AGENTS.md` records the rules this follows and why.
