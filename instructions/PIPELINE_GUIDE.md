# Pipeline Guide

## Purpose

This guide describes the end-to-end data workflow from raw CSV ingestion to dashboard-ready synchronized data.

## Stages

1. Ingestion
- Inputs: CSV files in `data/raw/greenroof/` and `data/raw/parkplatz/`
- Outputs: `ingested_empower_greenroof`, `ingested_kissel_greenroof`, `ingested_parkplatz`

2. QC Filtering
- Applies sensor and radiation bounds
- Outputs: `qc_filtered_greenroof`, `qc_filtered_parkplatz`

3. Harmonization
- Greenroof: maps source columns to canonical schema (`harm_greenroof`)
- Parkplatz: maps source columns to canonical/analysis schema (`harm_parkplatz`)

4. Synchronization
- Minute-level join of harmonized site tables
- Output: `synchronized_data_filtered`

5. Yearly Partitioning
- Builds partitioned structure for long-term query performance
- Output parent: `synchronized_data_yearly`

## Commands

Full run:

```bash
python scripts/run_pipeline.py
```

Dry run:

```bash
python scripts/run_pipeline.py --dry-run
```

Resume from a stage:

```bash
python scripts/run_pipeline.py --from qc-filter
```

Run range:

```bash
python scripts/run_pipeline.py --from harmonize --to partition
```

Post-run verification:

```bash
python scripts/verify_pipeline.py
```

## Dashboard

After a successful run:

```bash
streamlit run dashboard/app.py
```
