# Bingen Green Roof Pipeline

End-to-end pipeline and dashboard for comparing thermal behavior between a green roof site and a parking lot site.

## Pipeline Stages

The production workflow runs in this order:

1. `ingest` -> raw CSV files into `ingested_*` tables
2. `qc-filter` -> physically plausible filtering into `qc_filtered_*`
3. `harmonize` -> schema mapping into `harm_greenroof` and `harm_parkplatz`
4. `sync` -> minute-level joined analytics table `synchronized_data_filtered`
5. `partition` -> yearly partitioned parent `synchronized_data_yearly`

## Quick Start (Step by Step)

### 1) Create and activate environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Configure database credentials

```bash
copy config\.env.example config\.env
```

Edit `config/.env` with your PostgreSQL values.

### 3) Place raw input files

- Green roof files: `data/raw/greenroof/`
- Parkplatz files: `data/raw/parkplatz/`

Folder guidance is documented in:
- `data/raw/README.md`
- `data/raw/greenroof/README.md`
- `data/raw/parkplatz/README.md`

### 4) Dry-run the pipeline (recommended)

```bash
python scripts/run_pipeline.py --dry-run
```

### 5) Execute full pipeline

```bash
python scripts/run_pipeline.py
```

### 6) Verify outputs

```bash
python scripts/verify_pipeline.py
```

### 7) Launch dashboard

```bash
streamlit run dashboard/app.py
```

## Stage Control Examples

Run from a stage onward:

```bash
python scripts/run_pipeline.py --from qc-filter
```

Run a stage range only:

```bash
python scripts/run_pipeline.py --from harmonize --to sync
```

Verbose logging:

```bash
python scripts/run_pipeline.py --verbose
```

## Repository Architecture

```text
bingen_greenroof_pipeline/
├── README.md
├── .gitignore
├── requirements.txt
├── config/
│   ├── settings.py
│   ├── pipeline.yaml
│   └── .env.example
├── data/
│   └── raw/
│       ├── README.md
│       ├── greenroof/
│       └── parkplatz/
├── pipeline/
│   ├── ingest/
│   ├── qc_filtering/
│   ├── harmonize/
│   ├── sync/
│   ├── partition/
│   └── utils/
├── scripts/
│   ├── run_pipeline.py
│   ├── verify_pipeline.py
│   └── benchmark_pipeline.py
├── dashboard/
│   ├── app.py
│   └── analysis.py
├── instructions/
│   ├── README.md
│   ├── QUICK_START.md
│   └── PIPELINE_GUIDE.md
├── logs/
└── outputs/
```

## GitHub Publishing: What to Include vs Exclude

### Include in GitHub

- Source code: `pipeline/`, `scripts/`, `dashboard/`, `config/settings.py`
- Config template: `config/.env.example`
- Documentation: `README.md`, `instructions/`, selected `outputs/*.md`
- Folder placeholders and folder README files in `data/raw/` and `logs/`

### Exclude from GitHub

- Secrets: `config/.env`, any `.env` variants with credentials
- Raw datasets and large generated artifacts under `data/raw/`
- Runtime logs under `logs/`
- Generated outputs (`.csv`, `.json`, figures, temporary analysis artifacts)
- Internal-only scripts (`scripts/thesis_plots.py`, `scripts/thesis_summary.py`)
- Internal tooling and notes (`.claude/`, `docs/superpowers/`, generated context dumps)
- Local environment and cache folders (`.venv`, `__pycache__`, notebook checkpoints)

These exclusions are enforced by `.gitignore`.

## Where to Read More

- `instructions/QUICK_START.md` -> short operational path
- `instructions/PIPELINE_GUIDE.md` -> stage behavior and command patterns
