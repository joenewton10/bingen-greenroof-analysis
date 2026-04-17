# Quick Start

## 1. Environment Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config\.env.example config\.env
```

Set database credentials in `config/.env`.

## 2. Pipeline

```bash
python scripts/run_pipeline.py --dry-run
python scripts/run_pipeline.py
python scripts/verify_pipeline.py
```

## 3. Dashboard

```bash
streamlit run dashboard/app.py
```

Open: `http://localhost:8501` (or the port shown by Streamlit)

## Useful Variants

```bash
python scripts/run_pipeline.py --from harmonize --to sync
python scripts/run_pipeline.py --verbose
```
