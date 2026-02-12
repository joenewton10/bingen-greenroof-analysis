# Bingen Greenroof Analysis

Streamlit dashboard and data pipeline for analyzing green roof cooling performance in Bingen. The dashboard connects to a PostgreSQL database populated by the pipeline and provides interactive visualizations and summaries.

## Contents
- pipeline/: ingest, sync, validate, and harmonize modules
- dashboard/: Streamlit app and analysis logic
- data/: raw source files

## Requirements
- Python 3.10+
- PostgreSQL (for the dashboard and analysis data)

Install Python dependencies:

```
pip install -r requirements.txt
```

## Database configuration
The dashboard reads database settings from environment variables or Streamlit secrets:
- DB_NAME
- DB_USER
- DB_PASSWORD
- DB_HOST
- DB_PORT

You can set environment variables locally, or create a Streamlit secrets file.

Example secrets file:
- .streamlit/secrets.example.toml (copy to .streamlit/secrets.toml; do not commit secrets.toml)

## Run the pipeline (local)
From the repo root:

```
python run_ingest.py
python run_pipeline.py
python verify_counts.py
```

## Run the dashboard (local)
From the repo root:

```
streamlit run dashboard/app.py
```

## Deploy to Streamlit Community Cloud
- Push this repository to GitHub.
- In Streamlit Cloud, set the entry point to: dashboard/app.py
- Add the same DB_* values under app secrets.

## Notes
- The dashboard requires a reachable PostgreSQL instance with the expected tables.
- Large raw data files are stored under data/.
