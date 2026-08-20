# Instructions

This folder contains operational documentation for the Bingen pipeline.

## Files

- `PIPELINE_GUIDE.md`: Full pipeline behavior and stage-by-stage details
- `QUICK_START.md`: Fast setup and execution steps
- `DATASET_ACCESS_GUIDE.md`: Querying the synchronized dataset via SQLite/Parquet without a live PostgreSQL connection

## Pipeline Overview

The production pipeline runs five stages:

1. Ingest (`ingested_*` tables)
2. QC filtering (`qc_filtered_*` tables)
3. Harmonize (`harm_greenroof`, `harm_parkplatz`)
4. Sync (`synchronized_data_filtered`)
5. Partition (`synchronized_data_yearly`)

Run all stages:

```bash
python scripts/run_pipeline.py
```

Run a subset:

```bash
python scripts/run_pipeline.py --from harmonize --to sync
```
