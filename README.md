# Bingen Green Roof Cooling Analysis

A comprehensive data pipeline and interactive dashboard system for analyzing thermal performance of green roof installations in Bingen, Germany. The system ingests multi-source sensor data, performs validation and harmonization, and provides quantitative analysis through an interactive web-based dashboard to evaluate cooling effectiveness across environmental conditions.

---

## Quick Start

Prerequisites: Python 3.10+ and PostgreSQL installation with database access.

```bash
# 1. Clone repository
git clone <repository-url>
cd bingen_greenroof_pipeline

# 2. Create Python virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure database credentials
copy .env.example .env
# Edit .env with PostgreSQL connection details

# 6. Execute data pipeline
python scripts/run_pipeline.py

# 7. Launch dashboard application
streamlit run dashboard/app.py
```

The dashboard will be accessible at `http://localhost:8502`

---

## Prerequisites Installation

### Python 3.10+

**Windows:**
1. Visit https://www.python.org/downloads/ and download Python 3.10 or later
2. Execute the installer
3. Select "Add Python to PATH" during installation
4. Complete installation process
5. Verify installation via command prompt:
   ```bash
   python --version
   ```

**macOS:**
```bash
# Using Homebrew package manager
brew install python@3.10

# Verify installation
python3 --version
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv
python3.10 --version
```

---

### PostgreSQL Database Server

**Windows:**
1. Navigate to https://www.postgresql.org/download/windows/
2. Download PostgreSQL installer (version 13+)
3. Execute installer and follow prompts
4. Record the password set for the `postgres` superuser
5. Retain default port configuration (5432)
6. Verify installation:
   ```bash
   psql --version
   ```

**macOS:**
```bash
# Using Homebrew
brew install postgresql@14
brew services start postgresql

# Verify
psql --version
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
psql --version
```

**Create project database:**
```bash
psql -U postgres

# Within PostgreSQL interactive shell:
CREATE DATABASE bingen_greenroof_db;
\q
```

---

### Git Version Control

Download and install from https://git-scm.com/downloads

Verify installation:
```bash
git --version
```

---

### VS Code (Recommended)

1. Download from https://code.visualstudio.com/
2. Install application
3. Open VS Code
4. Access Extensions panel (Ctrl+Shift+X)
5. Install "Python" extension by Microsoft
6. Restart VS Code

---

## Environment Configuration

### 1. Clone the Repository

```bash
git clone <repository-url>
cd bingen_greenroof_pipeline
```

Verify: Directory should contain `pipeline/`, `dashboard/`, `data/`, and `README.md`.

---

### 2. Create Python Virtual Environment

A virtual environment isolates project dependencies from system-wide Python packages.

```bash
# Create virtual environment
python -m venv .venv

# Activate environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

Verify: Command prompt should display `(.venv)` prefix.

---

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Requires 1-2 minutes. Verify: No error messages in output.

---

### 4. Configure Database Connection

```bash
# Create .env file from template
copy .env.example .env               # Windows
cp .env.example .env                 # macOS/Linux
```

Edit `.env` with PostgreSQL credentials:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bingen_greenroof_db
DB_USER=postgres
DB_PASSWORD=<postgresql-password>
```

**Security Notice:** The `.env` file contains sensitive credentials. Never commit to version control. Only `.env.example` should be committed.

---

### 5. Test Database Connection

```bash
python -c "from dashboard.analysis import BingenGreenRoofAnalyzer; a = BingenGreenRoofAnalyzer(); print('Database connection successful')"
```

Expected output: `Database connection successful`

Troubleshooting: Verify `.env` credentials and PostgreSQL is running.

---

## Data Processing Pipeline

The pipeline consists of four sequential stages:

1. **Ingestion:** Load raw CSV sensor data into PostgreSQL
2. **Validation:** Verify data quality and integrity
3. **Harmonization:** Standardize data schema across multiple sensor sources
4. **Synchronization:** Align data by timestamp and compute derived metrics (temperature differences, energy balance)

### Execution

```bash
python scripts/run_pipeline.py
```

Typical execution time: 5-15 minutes (variable based on dataset size).

### Expected Output

```
[STAGE 1] INGEST
[ingest_empower_greenroof] 913280 records ingested
[ingest_kissel_greenroof] 1852938 records ingested
...
[STAGE 4] SYNCHRONIZATION
[sync_data] Synchronized 2053156 minute-level records
  Temporal range: 2020-07-02 to 2025-08-11
  Total observations: 2053156

============================================================
PIPELINE COMPLETED SUCCESSFULLY
============================================================
```

### Verification Criteria

Success indicators:
- No fatal errors reported (warnings acceptable)
- Database tables created: `harm_greenroof`, `harm_parkplatz`, `synchronized_data_filtered`
- Final status message indicates successful completion
- Log files written to `logs/` directory

### Troubleshooting

**Database Connection Failed**
- Verify PostgreSQL service is running
- Test: `psql -U postgres -c "SELECT 1"`
- Confirm `.env` credentials

**Pipeline Crashes**
- Review logs in `logs/pipeline_log_latest.txt`
- Verify data file availability in `data/raw/`
- Check system disk space and memory availability

---

## Dashboard Application

Interactive web-based visualization and analysis platform. Launches after pipeline completion.

### Starting the Dashboard

```bash
streamlit run dashboard/app.py
```

Access point: `http://localhost:8502`

### User Interface

**Sidebar Controls:**
- Yearly Analysis Mode: Query single year for optimized performance
- Custom Timestamp Filter: Restrict analysis to specific date/time ranges
- Yearly Analysis Display: View multi-year trend analysis
- Temperature Difference Metric: Select between primary and secondary sensor pairs

**Analysis Tabs:**
1. **Cooling Effectiveness** — Mean cooling effect segmented by environmental condition
2. **Distribution Analysis** — Statistical distribution of temperature differences
3. **Cooling Frequency** — Occurrence rates of meaningful cooling events
4. **Performance Matrix** — Comparative analysis of cooling magnitude vs. frequency
5. **Seasonal Analysis** — Temporal patterns across seasons
6. **Energy Balance** — Hourly and seasonal energy flux analysis

### Performance Optimization

For large datasets:
- Enable "Yearly analysis mode" to reduce query scope
- Use "Custom timestamp filter" to narrow temporal range
- Run database optimization script: `psql -d bingen_greenroof_db -f sql/postgresql_dashboard_optimization.sql`

### Network Access

**Local Network Deployment**

The dashboard is accessible on the local network at the network IP address and port 8502. The host system must remain active with the Streamlit service running.

Example: `http://<network-ip>:8502`

---

## Project Architecture

```
bingen_greenroof_pipeline/
├── README.md                          # Documentation
├── .env.example                       # Database configuration template
├── .gitignore                         # Version control exclusions
├── requirements.txt                   # Python package dependencies
│
├── scripts/                           # Pipeline orchestration
│   ├── run_pipeline.py                # Main execution script
│   ├── run_ingest.py                  # Ingest-only execution
│   └── verify_counts.py               # Data validation utility
│
├── config/
│   └── settings.py                    # Configuration parameters
│
├── pipeline/                          # Data processing modules
│   ├── ingest/                        # Data ingestion stage
│   │   ├── ingest_greenroof.py
│   │   ├── ingest_parkplatz.py
│   │   └── base.py
│   ├── validate/                      # Data validation stage
│   ├── harmonize/                     # Data harmonization stage
│   └── sync/                          # Data synchronization stage
│
├── dashboard/                         # Web application
│   ├── app.py                         # Streamlit application entry point
│   ├── analysis.py                    # Analysis engine
│   └── requirements-dashboard.txt     # Dashboard dependencies
│
├── data/
│   └── raw/                           # Raw sensor data files
│       ├── greenroof/
│       └── parkplatz/
│
├── tests/                             # Automated test suite
│   └── test_2020.py
│
├── logs/                              # Execution logs (auto-generated)
│   ├── pipeline_log.txt
│   ├── pipeline_log_latest.txt
│   └── [other logs]
│
├── outputs/                           # Generated exports (optional)
│
└── sql/                               # Database optimization scripts
    └── postgresql_dashboard_optimization.sql
```

### Key Components

- `scripts/run_pipeline.py` — Primary execution entry point
- `dashboard/app.py` — Analytics interface
- `.env` — Runtime database credentials (create from `.env.example`)
- `requirements.txt` — Dependency manifest

---

## Troubleshooting

### Module Import Errors

**Error:** `ModuleNotFoundError: No module named 'streamlit'`

**Resolution:**
1. Verify virtual environment is activated (prompt should show `(.venv)`)
2. Reinstall dependencies: `pip install -r requirements.txt`

---

### Database Connection Failures

**Error:** `psycopg2.OperationalError: could not connect to server`

**Root Causes and Solutions:**
1. PostgreSQL service not running:
   - Windows: Services → PostgreSQL → Start
   - macOS: `brew services start postgresql`
   - Linux: `sudo systemctl start postgresql`

2. Incorrect credentials in `.env`:
   - Verify DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
   - Test manually: `psql -h localhost -U postgres -d bingen_greenroof_db`

---

### Database Read Failures

**Error:** `FEHLER konnte Blöcke nicht lesen` (PostgreSQL storage read error)

**Indicates:** Table corruption or storage-level issues

**Resolution:**
```sql
-- Execute in PostgreSQL:
REINDEX TABLE synchronized_data_filtered;
VACUUM (VERBOSE, ANALYZE) synchronized_data_filtered;
```

**Workaround:** Use dashboard filtering:
- Enable "Yearly analysis mode" to query smaller data subsets
- Use "Custom timestamp filter" for narrower ranges

---

### Port Already in Use

**Error:** Port 8502 is already occupied

**Solution:**
```bash
# Method 1: Terminate existing Streamlit process
# Windows: Press Ctrl+C in active terminal

# Method 2: Use alternative port
streamlit run dashboard/app.py --server.port 8503
```

---

### Performance Issues

**Symptom:** Long execution time or memory exhaustion

**Solutions:**
1. Process single year:
   ```bash
   python scripts/run_ingest.py --year 2023
   ```

2. Apply database optimization:
   ```bash
   psql -U postgres -d bingen_greenroof_db -f sql/postgresql_dashboard_optimization.sql
   ```

3. Increase system resources or process data in smaller batches

---

## Database Optimization

Database performance optimization is recommended after pipeline execution, particularly for large datasets or frequent queries.

### Apply Optimization

```bash
psql -U postgres -d bingen_greenroof_db -f sql/postgresql_dashboard_optimization.sql
```

This creates:
- Time-series indexes on timestamp columns
- Optimized query execution plans
- Optional materialized views for aggregated data access

### Performance Impact

- Dashboard query latency: 10-50x improvement typical
- Memory footprint: Reduced for aggregated queries
- Scalability: Supports efficient long-term growth

Refresh materialized views after major data ingestion:
```sql
REFRESH MATERIALIZED VIEW mv_hourly_aggregates;
REFRESH MATERIALIZED VIEW mv_daily_aggregates;
```

---

## Version Control

### Preparing for Publication

Ensure project structure follows version control best practices before committing:

```bash
# Verify .gitignore coverage
cat .gitignore

# List pending changes
git status

# Verify no credentials in staging area
git diff --cached .env

# Stage project files
git add .

# Create descriptive commit message
git commit -m "feat: Bingen green roof analysis pipeline and dashboard"

# Push to remote repository
git push -u origin main
```

### Important Notes

- Never commit `.env` file (contains database credentials)
- Only `.env.example` should be version controlled
- Log files and temporary outputs are automatically excluded
- Large data files in `data/raw/` are excluded by `.gitignore`

---

## Docker Deployment (Optional)

For containerized deployment without local configuration requirements.

### Container Setup

**Dockerfile:**
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8502

CMD ["streamlit", "run", "dashboard/app.py"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8502:8502"
    environment:
      DB_HOST: postgres
      DB_USER: postgres
      DB_PASSWORD: postgres
      DB_NAME: bingen_greenroof_db
    depends_on:
      - postgres

  postgres:
    image: postgres:14
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: bingen_greenroof_db
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Deployment

```bash
docker-compose up
```

Access: `http://localhost:8502`

### Advantages

- Single command deployment with all dependencies
- Environment consistency across systems
- Simplified sharing and collaboration
- Easy scaling and cloud deployment

---

## Support and Documentation

For additional information:
- Streamlit Documentation: https://docs.streamlit.io/
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- Python Virtual Environments: https://docs.python.org/3/tutorial/venv.html

---

**System Version:** 1.0.0  
**Last Updated:** February 2026
