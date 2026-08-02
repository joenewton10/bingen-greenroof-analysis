# Chapter 6: Reproducible Setup and Execution Procedure

## Overview

This chapter provides a complete, step-by-step procedure for setting up the pipeline on Windows and executing all required stages (Ingestion through Yearly Partitioning) described in the Methodology section. The procedure is designed to enable future students and operators to reliably reproduce the data synchronization workflow with newly arriving data from the weather stations.

---

## 6.1 System Prerequisites

Before beginning pipeline setup, ensure the following are available on the Windows system:

- **Python 3.10 or newer** (required for NumPy 2.4+ compatibility)  
  Download: https://www.python.org/downloads/windows/
- **Visual Studio Code** (recommended IDE)  
  Download: https://code.visualstudio.com/Download
- **PostgreSQL 12 or newer** (database backend)  
  Download: https://www.postgresql.org/download/windows/
- **PostgreSQL client tools** (psql command-line client and/or pgAdmin GUI)  
  psql (bundled with PostgreSQL installer): https://www.postgresql.org/download/windows/  
  pgAdmin: https://www.pgadmin.org/download/pgadmin-4-windows/
- **Git** (optional, for version control)  
  Download: https://git-scm.com/download/win

### Recommended VS Code Extensions

- Python (Microsoft)
- Pylance (Python language server)
- Jupyter (if exploratory analysis notebooks are needed)

---

## 6.2 Environment Setup

### 6.2.1 Create Python Virtual Environment

Open PowerShell in the project root directory and execute:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 6.2.2 Configure Python Interpreter in VS Code

1. Press `Ctrl+Shift+P`
2. Search for "Python: Select Interpreter"
3. Choose `.venv\Scripts\python.exe` from the dropdown
4. VS Code will now use the virtual environment for all terminal operations

---

## 6.3 PostgreSQL Database Setup

### 6.3.1 Install PostgreSQL

Download and install PostgreSQL from https://www.postgresql.org/download/windows/:

- Accept default installation port (5432)
- Set and record a secure password for the `postgres` superuser account
- Ensure PostgreSQL service starts automatically on system boot

### 6.3.2 Create Database and User (Option A: psql Command Line)

Open PowerShell and connect to PostgreSQL as the superuser:

```bash
psql -U postgres -h localhost -p 5432
```

At the psql prompt, execute:

```sql
CREATE DATABASE bingen_greenroof;
CREATE ROLE pipeline_user WITH LOGIN PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE bingen_greenroof TO pipeline_user;
\c bingen_greenroof
GRANT ALL ON SCHEMA public TO pipeline_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO pipeline_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO pipeline_user;
```

Exit psql with `\q`.

### 6.3.3 Create Database and User (Option B: pgAdmin GUI)

As an alternative or complement to psql:

1. Launch pgAdmin (installed with PostgreSQL)
2. Connect with default superuser credentials
3. In the Object Explorer, right-click "Databases" → "Create" → "Database"
   - Name: `bingen_greenroof`
4. Right-click "Login/Group Roles" → "Create" → "Login/Group Role"
   - Name: `pipeline_user`
   - Set a secure password in the "Definition" tab
5. Grant privileges:
   - Select the new role and navigate to "Privileges"
   - Grant all privileges on `bingen_greenroof` database

### 6.3.4 Configure Project Environment Variables

Copy the environment template:

```bash
copy config\.env.example config\.env
```

Edit `config/.env` with your PostgreSQL credentials:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bingen_greenroof
DB_USER=pipeline_user
DB_PASSWORD=your_secure_password
```

**Security Note:** Never commit `config/.env` to version control. The `.gitignore` file excludes it by default.

---

## 6.4 Input Data Staging

### 6.4.1 Raw Data Directory Structure

The pipeline expects raw CSV files in two locations:

```
data/raw/
├── greenroof/
│   ├── Empower_Greenroof/
│   │   └── *.csv (Empower greenroof records from January 2024 onwards)
│   └── Kissel_GreenRoof_Data/
│       └── *.csv (Kissel greenroof records from December 2019 to December 2023)
└── parkplatz/
    ├── Empower_Parkplatz_data/
    │   └── *.csv (Empower parking lot records from January 2024 onwards)
    └── Kissel_Parkplatz_data/
        └── *.csv (Kissel parking lot records from December 2019 to December 2023)
```

Place newly arriving CSV files in the appropriate subdirectories. The ingest stage scans these directories recursively for all `.csv` files.

---

## 6.5 Pre-Execution Validation

Before running the full pipeline, verify that all prerequisites are satisfied:

### 6.5.1 Preflight Check (Dry-Run Mode)

Execute a dry-run to validate configuration without modifying the database:

```bash
python scripts/run_pipeline.py --dry-run --verbose
```

This command performs the following checks:

1. **Environment file:** Confirms `config/.env` exists and is readable
2. **Database connectivity:** Tests PostgreSQL connection with configured credentials
3. **Data directories:** Verifies `data/raw/greenroof/` and `data/raw/parkplatz/` exist
4. **Logs directory:** Confirms `logs/` is writable
5. **SQL preview:** Displays the SQL that would be executed without applying changes

**Expected Output:**

```
============================================================
              PRE-FLIGHT CHECKS
============================================================
[OK] .env file found: config/.env
[OK] Database connection OK: PostgreSQL 12.x
[OK] Greenroof data directory exists: N CSV files
[OK] Parkplatz data directory exists: N CSV files
[OK] Logs directory writable: logs/
============================================================
Pre-flight checks: 5 passed, 0 failed
[OK] All pre-flight checks passed!
```

If any check fails, address the error before proceeding to production execution.

---

## 6.6 Pipeline Execution

### 6.6.1 Full Pipeline Run (All Stages)

Execute the complete pipeline from Ingestion through Yearly Partitioning:

```bash
python scripts/run_pipeline.py
```

This command runs all five required stages in order:

1. **INGESTION** – Parses CSV files and populates `ingested_*` tables (~5–10 min)
2. **QC FILTERING** – Applies physically valid sensor ranges to create `qc_filtered_*` tables (~3–4 min)
3. **HARMONIZATION** – Maps sources to canonical schemas, producing `harm_*` tables (~2–3 min)
4. **SYNCHRONIZATION** – Joins harmonized data at minute resolution, creating `synchronized_data_filtered` (~4–5 min)
5. **YEARLY PARTITIONING** – Splits synchronized data into yearly partitions, creating `synchronized_data_yearly` and yearly child tables (~1–2 min)

**Total Runtime:** Approximately 15–25 minutes depending on data volume and system performance.

### 6.6.2 Stage-Range Execution (Partial Runs)

For operational scenarios requiring reprocessing of specific stages:

**Run from a specific stage onward:**

```bash
python scripts/run_pipeline.py --from harmonize
```

**Run a stage range only:**

```bash
python scripts/run_pipeline.py --from harmonize --to partition
```

**Verbose diagnostics (useful for debugging):**

```bash
python scripts/run_pipeline.py --verbose
```

**Dry-run with explicit end point:**

```bash
python scripts/run_pipeline.py --from qc-filter --to sync --dry-run
```

All stage names are: `ingest`, `qc-filter`, `harmonize`, `sync`, `partition`.

---

## 6.7 Post-Run Verification

### 6.7.1 Automated Verification Script

After pipeline completion, run the verification script to confirm all stages produced valid outputs:

```bash
python scripts/verify_pipeline.py
```

### 6.7.2 Expected Verification Output

The script checks table existence, row counts, and data freshness. Successful output includes (example aligned to the latest full pipeline run on 2026-05-18):

```
============================================================
          PIPELINE VERIFICATION
============================================================

Checking tables...

Ingested Tables:
–––––––––––––––––––––––––––––––
  ✓ ingested_empower_greenroof: 1,160,241 rows
  ✓ ingested_kissel_greenroof: 2,007,520 rows
  ✓ ingested_parkplatz: 3,393,249 rows

QC-filtered Tables:
–––––––––––––––––––––––––––––––
  ✓ qc_filtered_greenroof: 3,011,463 rows
  ✓ qc_filtered_parkplatz: 2,850,511 rows

Harmonized Tables:
–––––––––––––––––––––––––––––––
  ✓ harm_greenroof: 3,011,463 rows
  ✓ harm_parkplatz: 2,850,511 rows

Final Tables:
–––––––––––––––––––––––––––––––
  ✓ synchronized_data_filtered: 2,178,878 rows
    Time range: 2020-07-02 11:58 to 2026-05-10 23:57
    Freshness: verify against current reporting date [OK]
  ✓ synchronized_data_yearly: 2,178,878 rows (partitioned)

============================================================
          VERIFICATION COMPLETE
============================================================
[OK] All tables verified successfully
[OK] Total rows across all tables: 22,642,714

Pipeline is ready for downstream analysis.
```

### 6.7.3 Verification Checks

The script validates:

- **Table existence:** Confirms all output tables from each stage exist in PostgreSQL
- **Row counts:** Verifies non-zero row counts for all critical tables
- **Timestamp ranges:** Checks min/max timestamp of `synchronized_data_filtered` to ensure data covers the intended period
- **Data freshness:** Compares the latest timestamp against the current date to flag stale datasets
- **Partition coverage:** Confirms yearly child tables exist for all years in the data

If any check fails, the script will report the specific failure. Consult the pipeline logs (in `logs/`) for detailed error messages.

---

## 6.8 Continuous Data Update Workflow

### 6.8.1 Monthly/Weekly Update Procedure

When new CSV files arrive from the weather stations, follow this standard procedure:

**Step 1: Stage new files**

Place newly received CSV files into the appropriate `data/raw/` subdirectories:
- Greenroof files: `data/raw/greenroof/`
- Parkplatz files: `data/raw/parkplatz/`

**Step 2: Validate with dry-run**

```bash
python scripts/run_pipeline.py --dry-run
```

Review console output for any parsing errors or configuration issues. Do not proceed if warnings or errors appear.

**Step 3: Execute full pipeline**

```bash
python scripts/run_pipeline.py
```

Wait for completion. Monitor the console for stage completion messages and total runtime.

**Step 4: Verify outputs**

```bash
python scripts/verify_pipeline.py
```

Confirm all tables are present, contain expected row counts, and timestamp range includes the new reporting period.

**Step 5: Record update metadata**

Document in lab notes or report appendix:
- Date of update
- Operator initials
- Row counts from verification output
- Min/max timestamp range of `synchronized_data_filtered`
- Any issues encountered and resolution

### 6.8.2 Data Replacement Behavior

**Important:** Each pipeline run completely replaces all data (no incremental appending). 

- All ingested tables are dropped and recreated
- Cascading transformations regenerate all downstream tables
- Final `synchronized_data_filtered` and `synchronized_data_yearly` contain only the newly ingested data

This design ensures consistency and avoids duplicate rows or partial-state inconsistencies.

### 6.8.3 Safe Rerun and Failure Recovery

If a pipeline stage fails partway through:

1. **Identify the failure:** Inspect the most recent log file in `logs/pipeline_run_YYYYMMDD_HHMMSS.log`
2. **Fix the root cause:** Common issues include incorrect DB credentials, missing CSV files, or resource limits
3. **Resume from the failed stage:** Use `--from` and `--to` flags to restart only the failed stages
4. **Re-verify:** Run `verify_pipeline.py` again to confirm successful recovery

Example recovery after sync stage failure:

```bash
python scripts/run_pipeline.py --from harmonize --to partition
```

All stage outputs are idempotent (safe to re-run). Using `DROP TABLE IF EXISTS` ensures clean state without duplicate rows or conflicts.

### 6.8.4 One-Command Monthly Operator Run

For routine monthly updates, use the consolidated operator script to execute the full sequence in one command:

```bash
python scripts/run_monthly_update.py
```

Default sequence executed by this command:

1. `run_pipeline.py --dry-run --verbose`
2. `run_pipeline.py`
3. `verify_pipeline.py`
4. `build_30min_table.py`

Optional flags:

```bash
python scripts/run_monthly_update.py --skip-dry-run
python scripts/run_monthly_update.py --skip-30min
python scripts/run_monthly_update.py --continue-on-30min-error
```

This command is recommended for standard operations because it reduces manual step errors and ensures a consistent execution order.

---

## 6.9 Troubleshooting Guide

| Error | Root Cause | Solution |
|-------|-----------|----------|
| "Database connection failed: FATAL: Ident authentication failed" | Wrong credentials or incorrect PostgreSQL settings | Verify `config/.env` with actual DB credentials; test login via psql or pgAdmin |
| "Database connection failed: could not translate host name" | DB_HOST unreachable or wrong | Ensure PostgreSQL service is running; verify `DB_HOST=localhost` if using local installation |
| "Greenroof directory not found / 0 CSV files detected" | Missing data or wrong folder structure | Confirm CSV files are under `data/raw/greenroof/` and `data/raw/parkplatz/`; check file extensions (must be `.csv`) |
| "QC-filtered tables have 0 rows" | All data filtered out by QC bounds | Review QC filter ranges in config/pipeline.yaml; inspect raw data for outliers or sensor malfunctions |
| "Sync stage produced empty table" | Harmonized tables have no overlapping timestamps | Check timestamp ranges in `harm_greenroof` and `harm_parkplatz`; verify both sites have simultaneous data |
| "Partition stage fails / cannot create yearly tables" | Syntax error in SQL or schema conflict | Check PostgreSQL logs; ensure `synchronized_data_filtered` is not empty |
| "Memory error or timeout during execution" | Large data volume exceeds system resources | Reduce CSV file count per run; increase PostgreSQL `work_mem` setting; run stages separately with `--from` / `--to` |

---

## 6.10 Reproducibility Checklist

Use this checklist before submitting a monthly/quarterly report to confirm all pipeline executions are documented and reproducible:

- [ ] Python 3.10+ installed and virtual environment activated
- [ ] PostgreSQL service running and accessible via configured credentials
- [ ] `config/.env` populated with correct DB host, port, name, user, password
- [ ] New raw CSV files staged in `data/raw/greenroof/` and `data/raw/parkplatz/`
- [ ] Dry-run executed and passed all preflight checks
- [ ] Full pipeline executed successfully (all 5 stages completed)
- [ ] Verification script confirms all output tables are present and non-empty
- [ ] Latest timestamp in `synchronized_data_filtered` includes current reporting period
- [ ] Pipeline execution log saved and archived (in `logs/`)
- [ ] Update metadata recorded (date, operator, row counts, timestamp range)
- [ ] One-command monthly run completed successfully (`python scripts/run_monthly_update.py`)

---

## 6.11 Summary

This chapter has provided a complete, executable procedure for setting up and running the Bingen greenroof data pipeline on Windows. The procedure is designed for reproducibility: any operator with access to the project code, raw data files, and this guide can reliably execute the pipeline and produce identical, analysis-ready synchronized datasets.

The five-stage architecture (Ingestion → QC Filtering → Harmonization → Synchronization → Partitioning) ensures consistent data quality and enables continuous ingestion of newly arriving weather station data. Monthly or weekly repetition of this procedure (Section 6.8) will maintain an up-to-date analysis dataset as discussed in the project objectives.

---
