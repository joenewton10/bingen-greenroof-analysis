# 🌿 Bingen Green Roof Cooling Analysis

A complete data pipeline and interactive dashboard for analyzing green roof cooling performance in Bingen, Germany. 

**What it does:** Ingests sensor data from green roof and parkplatz (parking lot) sites, validates & harmonizes the data, and provides an interactive Streamlit dashboard to explore cooling effectiveness under various environmental conditions.

---

## ⚡ Quick Start (5 minutes)

If you already have Python 3.10+ and PostgreSQL installed:

```bash
# 1. Clone repository
git clone <your-repo-url>
cd bingen_greenroof_pipeline

# 2. Create Python virtual environment
python -m venv .venv

# 3. Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure database (copy and edit .env)
copy .env.example .env
# Edit .env with your PostgreSQL credentials

# 6. Run pipeline
python scripts/run_pipeline.py

# 7. Launch dashboard
streamlit run dashboard/app.py
```

✅ **Dashboard will open at:** `http://localhost:8502`

---

## 📋 Prerequisites Installation (Beginner Guide)

### Step 1: Install Python 3.10+

**Windows:**
1. Go to https://www.python.org/downloads/ → Download Python 3.10 or 3.11
2. Run installer
3. ⚠️ **IMPORTANT:** Check "Add Python to PATH"
4. Click "Install Now"
5. Verify installation:
   ```bash
   python --version
   ```

**Mac:**
```bash
# Using Homebrew (if you have it)
brew install python@3.10

# Or download from https://www.python.org/downloads/
python3 --version
```

**Linux:**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv
python3.10 --version
```

---

### Step 2: Install PostgreSQL

**Windows:**
1. Go to https://www.postgresql.org/download/windows/
2. Download installer (v13+)
3. Run installer
4. Remember the password you set for user `postgres`
5. Keep port as default (5432)
6. Finish installation
7. Open Command Prompt and test:
   ```bash
   psql --version
   ```

**Mac:**
```bash
# Using Homebrew
brew install postgresql@14
brew services start postgresql

# Verify
psql --version
```

**Linux:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
psql --version
```

**Create a database for the project:**
```bash
psql -U postgres

# Inside PostgreSQL prompt:
CREATE DATABASE bingen_greenroof_db;
\q
```

---

### Step 3: Install Git

Go to https://git-scm.com/downloads and install.

Verify:
```bash
git --version
```

---

### Step 4: Install VS Code (Optional but Recommended)

1. Go to https://code.visualstudio.com/
2. Download and install
3. Open VS Code
4. Go to Extensions (Ctrl+Shift+X)
5. Search and install: **"Python"** by Microsoft
6. Restart VS Code

---

## 🚀 Project Setup (Step-by-Step)

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd bingen_greenroof_pipeline
```

✅ **Check:** You should see `pipeline/`, `dashboard/`, `data/`, and `README.md` in the folder.

---

### 2. Create Virtual Environment

A virtual environment isolates this project's Python packages from your system Python.

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

✅ **Check:** Your command prompt should show `(.venv)` at the start.

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

⏳ *This takes 1-2 minutes. Coffee break!*

✅ **Check:** No red error messages at the end.

---

### 4. Configure Database Connection

```bash
# Copy the example environment file
copy .env.example .env               # Windows
cp .env.example .env                 # Mac/Linux
```

Then edit `.env` with a text editor (VS Code recommended):

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bingen_greenroof_db
DB_USER=postgres
DB_PASSWORD=<your-postgres-password>
```

⚠️ **WARNING:** Never commit `.env` to Git (it contains secrets!). Only commit `.env.example`.

✅ **Check:** Save the file. You should see `.env` in your project folder (but NOT in Git).

---

### 5. Test Database Connection

```bash
python -c "from dashboard.analysis import BingenGreenRoofAnalyzer; a = BingenGreenRoofAnalyzer(); print('✅ Database connected!')"
```

✅ **Expected output:** `✅ Database connected!`

❌ **If it fails:** Check your `.env` settings and PostgreSQL is running.

---

## 📊 Running the Pipeline

The pipeline has 4 stages:

1. **Ingest:** Load raw CSV data into PostgreSQL
2. **Validate:** Check data quality
3. **Harmonize:** Combine data from different sensors into a standard format
4. **Sync:** Align data by timestamp and calculate temperature differences & energy metrics

### Run the Full Pipeline

```bash
python scripts/run_pipeline.py
```

⏳ *Takes 5-15 minutes depending on data size.*

**Expected output:**
```
[STAGE 1] INGEST
[ingest_empower_greenroof] 913280 records...
[ingest_kissel_greenroof] 1852938 records...
...
[STAGE 4] SYNCHRONIZATION
[sync_data] Synchronized 2053156 minute-level records.

============================================================
PIPELINE COMPLETED SUCCESSFULLY
============================================================
```

✅ **Success indicators:**
- No errors (warnings are OK)
- Database tables created: `harm_greenroof`, `harm_parkplatz`, `synchronized_data_filtered`
- Final message says "PIPELINE COMPLETED SUCCESSFULLY"
- Log files created in `logs/` folder

❌ **If it fails:**
- Check `.env` credentials
- Verify PostgreSQL is running: `psql -U postgres -c "SELECT 1"`
- Check logs in `logs/` folder for error details
- See "Troubleshooting" section below

---

## 📈 Viewing the Dashboard

Once the pipeline completes, launch the interactive dashboard:

```bash
streamlit run dashboard/app.py
```

**Open in browser:** http://localhost:8502

### Dashboard Features

**Sidebar Controls:**
- **Yearly analysis mode:** Query only one year (faster for large datasets)
- **Custom timestamp filter:** Select a specific date/time range
- **Show yearly analysis display:** View trends across all years
- **Temperature Difference Metric:** Choose between temp_diff_1 or temp_diff_2 (two different sensor pairs)

**Tabs:**
1. **📊 Cooling Effectiveness** — Mean cooling effect by environmental condition
2. **📦 Distribution Analysis** — Box plots showing data spread
3. **📈 Cooling Frequency** — How often meaningful cooling occurs
4. **🎯 Performance Matrix** — Mean effect vs. frequency comparison
5. **🍂 Seasonal Analysis** — Seasonal patterns in cooling
6. **⚡ Energy Balance** — Hourly energy fluxes and radiation patterns

### Sharing with Your Professor

**Option 1: Same Wi-Fi Network**
- Share this URL: `http://192.168.178.21:8502`
- (Your PC must stay on and Streamlit running)

**Option 2: Remote Access (using a tunnel)**
See "Advanced: Sharing Remotely" section below.

---

## 📁 Project Structure Explained

```
bingen_greenroof_pipeline/
├── README.md                          # This file
├── .env.example                       # Template for database credentials
├── .gitignore                         # Files to exclude from Git
├── requirements.txt                   # Python dependencies
│
├── scripts/                           # Entry point scripts (run these!)
│   ├── run_pipeline.py                # Main orchestrator (ingest→validate→harmonize→sync)
│   ├── run_ingest.py                  # Alternative: run just ingest stage
│   └── verify_counts.py               # Verify data counts after pipeline
│
├── config/
│   └── settings.py                    # Configuration constants
│
├── pipeline/                          # Data processing modules
│   ├── ingest/                        # Load raw CSVs into database
│   │   ├── ingest_greenroof.py
│   │   ├── ingest_parkplatz.py
│   │   └── base.py
│   ├── validate/                      # Validate data quality
│   ├── harmonize/                     # Standardize data schema
│   └── sync/                          # Align & sync by timestamp
│
├── dashboard/                         # Streamlit app
│   ├── app.py                         # Main dashboard code
│   ├── analysis.py                    # Data analysis logic
│   └── requirements-dashboard.txt     # Dashboard-specific dependencies
│
├── data/
│   └── raw/                           # Raw sensor CSV files
│       ├── greenroof/
│       └── parkplatz/
│
├── tests/                             # Automated tests
│   └── test_2020.py
│
├── logs/                              # Pipeline execution logs (auto-generated)
│   ├── pipeline_log.txt
│   ├── pipeline_log_latest.txt
│   ├── ingest_log.txt
│   └── parkplatz_log.txt
│
├── outputs/                           # Generated exports/reports (optional)
│
└── sql/                               # Database optimization scripts
    └── postgresql_dashboard_optimization.sql
```

**Key Files You'll Use:**
- `scripts/run_pipeline.py` — Run this to load/process data
- `dashboard/app.py` — Run this to view results
- `.env` — Put your database password here (don't commit!)
- `requirements.txt` — List of all Python packages

---

## ⚠️ Troubleshooting

### "ModuleNotFoundError: No module named 'streamlit'"

**Solution:**
```bash
# Make sure virtual environment is activated (.venv should show in prompt)
pip install -r requirements.txt
```

---

### "psycopg2.OperationalError: could not connect to server"

**Means:** PostgreSQL is not running or credentials are wrong.

**Solutions:**
1. **Start PostgreSQL:**
   - Windows: Services → PostgreSQL → Start
   - Mac: `brew services start postgresql`
   - Linux: `sudo systemctl start postgresql`

2. **Check credentials in `.env`:**
   ```bash
   # Test connection manually
   psql -h localhost -U postgres -d bingen_greenroof_db
   ```
   If this fails, check your password and database name.

---

### "Database read failed: FEHLER konnte Blöcke nicht lesen"

**Means:** PostgreSQL table is corrupted (storage issue).

**Solutions:**
```sql
-- Run in PostgreSQL:
REINDEX TABLE synchronized_data_filtered;
VACUUM (VERBOSE, ANALYZE) synchronized_data_filtered;
```

Or try the dashboard with **Yearly analysis mode** enabled (loads smaller chunks).

---

### "Port 8502 already in use"

**Means:** Streamlit is already running.

**Solution:**
```bash
# Kill existing Streamlit process
# Windows: Ctrl+C in the terminal
# Or specify different port:
streamlit run dashboard/app.py --server.port 8503
```

---

### "Pipeline takes too long / Memory errors"

**Solutions:**
1. **Run by year** (edit `run_pipeline.py`):
   ```python
   # Process 2023 only
   analyzer.load_data(year=2023)
   ```

2. **Enable PostgreSQL optimization:**
   ```bash
   psql -U postgres -d bingen_greenroof_db -f sql/postgresql_dashboard_optimization.sql
   ```

---

## 🔧 Database Optimization (Recommended)

After running the pipeline, optimize for faster queries:

```bash
psql -U postgres -d bingen_greenroof_db -f sql/postgresql_dashboard_optimization.sql
```

This creates indexes and materialized views for 10x faster dashboard loads.

---

## 📤 Preparing for GitHub

Before pushing to GitHub:

```bash
# 1. Verify .gitignore exists and includes secrets
cat .gitignore

# 2. Never commit credentials
git status  # Should NOT show .env

# 3. Add all code
git add .

# 4. Create first commit
git commit -m "Initial commit: Bingen green roof analysis pipeline"

# 5. Push to GitHub
git push -u origin main
```

---

## 🐳 Advanced: Docker Setup (Optional)

For sharing with your professor or deploying to a server without manual setup:

### Create Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8502

CMD ["streamlit", "run", "dashboard/app.py"]
```

### Create docker-compose.yml

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

### Run with Docker

```bash
docker-compose up
# Opens at http://localhost:8502
```

👉 **Share this URL with your professor** — they just need Docker, nothing else!

---

## 🤝 Support & Questions

- **Dashboard issues?** Check sidebar error messages
- **Pipeline fails?** Check the logs: `pipeline_log_latest.txt`
- **Database problems?** Verify PostgreSQL is running and `.env` is correct

---

## 📚 Learn More

- Streamlit docs: https://docs.streamlit.io/
- PostgreSQL docs: https://www.postgresql.org/docs/
- Python virtual environments: https://docs.python.org/3/tutorial/venv.html

---

**Happy analyzing! 🌱**
