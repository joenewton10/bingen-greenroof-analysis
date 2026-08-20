# Dataset Access Guide (Without PostgreSQL)

## Quick Start

The pipeline provides multiple ways to access your 2M+ synchronized records **without PostgreSQL**:

---

## Option 1: SQLite Database ⭐ RECOMMENDED

**Status**: Export in progress (`scripts/export_to_sqlite.py`)  
**File**: `outputs/bingen_greenroof.db` (~600-800 MB)  
**Yearly splits**: `outputs/bingen_greenroof_yearly/*.db`

### Why SQLite?
✅ Portable single file (no server needed)  
✅ Full SQL query support (like PostgreSQL)  
✅ Works on Windows/Mac/Linux  
✅ Open with Excel tools or command line  

### How to Use

**In Python**:
```python
import pandas as pd
import sqlite3

# Open database
conn = sqlite3.connect('outputs/bingen_greenroof.db')

# Load all data
df = pd.read_sql_query(
    'SELECT * FROM synchronized_data_filtered',
    conn
)

# Query with filters
df_2024 = pd.read_sql_query(
    'SELECT * FROM synchronized_data_filtered '
    'WHERE timestamp > ? AND timestamp < ?',
    conn,
    params=('2024-01-01', '2024-12-31')
)

conn.close()
```

**In Command Line**:
```bash
sqlite3 outputs/bingen_greenroof.db
> SELECT COUNT(*) FROM synchronized_data_filtered;
> .schema synchronized_data_filtered
> SELECT * FROM synchronized_data_filtered LIMIT 10;
> .quit
```

**In Excel/Database Tools**:
1. Download [DB Browser for SQLite](https://sqlitebrowser.org/) (free, open-source)
2. Open `.db` file
3. Browse tables, run queries, export to CSV/Excel

---

## Option 2: Parquet Files

**Status**: Available  
**Files**: 
- `outputs/synchronized_data_complete.parquet` (all records)
- `outputs/parquet_yearly/*.parquet` (yearly splits)

### How to Use

```python
import pandas as pd

# Load complete dataset
df = pd.read_parquet('outputs/synchronized_data_complete.parquet')

# Or load yearly
df_2024 = pd.read_parquet('outputs/parquet_yearly/2024.parquet')

# Query with pandas
greenroof_data = df[df['timestamp'] > '2024-01-01']
```

---

## Option 3: CSV Files

**Generate on demand**: `scripts/generate_csv_exports.py` (to be created)

```python
# Load complete CSV
df = pd.read_csv('outputs/synchronized_data_complete.csv')

# Works with Excel (in chunks due to size)
```

---

## Data Schema

### Main Table: `synchronized_data_filtered`

**Columns** (40 total):

| Column | Type | Description |
|--------|------|-------------|
| timestamp | datetime | Minute-level synchronized timestamp |
| **Greenroof Data** (12 cols) | |
| avg_ir1_greenroof | float | Incoming longwave radiation (W/m²) |
| avg_air_temperature_greenroof | float | Air temperature (°C) |
| avg_air_temp_2_greenroof | float | Secondary air temperature (°C) |
| avg_air_humidity_1_greenroof | float | Air humidity 1 (%RH) |
| avg_air_humidity_2_greenroof | float | Air humidity 2 (%RH) |
| avg_wind_speed_greenroof | float | Wind speed (m/s) |
| avg_soil_temperature_greenroof | float | Soil temperature (°C) |
| avg_ir1_out_lw_greenroof | float | Outgoing longwave (W/m²) |
| avg_sr1_in_sw_greenroof | float | Incoming shortwave (W/m²) |
| avg_sr1_out_sw_greenroof | float | Outgoing shortwave (W/m²) |
| avg_rnet_greenroof | float | Net radiation (W/m²) |
| temp_diff_1_greenroof | float | Temperature differential (calculated) |
| temp_diff_2_greenroof | float | Temperature differential 2 (calculated) |
| **Parkplatz Data** (12 cols) | |
| avg_ir1_parkplatz | float | Incoming longwave (W/m²) |
| avg_temp_parkplatz | float | Temperature (°C) |
| avg_air_pressure_parkplatz | float | Air pressure (mbar) |
| avg_soil_moisture_parkplatz | float | Soil moisture (vol%) |
| avg_air_humidity_1_parkplatz | float | Air humidity 1 (%RH) |
| avg_air_humidity_2_parkplatz | float | Air humidity 2 (%RH) |
| avg_wind_speed_parkplatz | float | Wind speed (m/s) |
| avg_wind_direction_parkplatz | float | Wind direction (°) |
| avg_soil_temp_1_parkplatz | float | Soil temp 1 (°C) |
| avg_soil_temp_2_parkplatz | float | Soil temp 2 (°C) |
| avg_sr1_parkplatz | float | Shortwave radiation (W/m²) |
| avg_sr2_parkplatz | float | Shortwave 2 (W/m²) |
| **Availability Flags** | |
| greenroof_available | boolean | Greenroof sensors operational |
| parkplatz_available | boolean | Parkplatz sensors operational |
| **Analysis Metrics** | |
| albedo_greenroof | float | Reflected/incoming shortwave ratio |
| albedo_parkplatz | float | Reflected/incoming shortwave ratio |
| ... | | (energy balance columns) |

**Time Range**: 2020-01-01 to 2025-12-31  
**Records**: 2,045,749 (minute-level)  
**Partitioning**: By year (6 yearly tables available)

---

## Export Scripts Available

### 1. SQLite Export ✓
```bash
python scripts/export_to_sqlite.py
```
Generates: `outputs/bingen_greenroof.db` and yearly splits

### 2. Parquet Export ✓
```bash
python scripts/export_to_parquet.py
```
Generates: Complete and yearly `.parquet` files

### 3. Fast Export (DuckDB fallback) ✓
```bash
python scripts/fast_export_parquet.py
```
Uses DuckDB's PostgreSQL extension for speed

---

## Common Queries (SQLite)

### Get all 2024 data
```sql
SELECT * FROM synchronized_data_filtered
WHERE strftime('%Y', timestamp) = '2024'
LIMIT 10;
```

### Average temperature by month
```sql
SELECT 
    strftime('%Y-%m', timestamp) as month,
    AVG(avg_air_temperature_greenroof) as avg_temp_greenroof,
    AVG(avg_temp_parkplatz) as avg_temp_parkplatz
FROM synchronized_data_filtered
GROUP BY strftime('%Y-%m', timestamp)
ORDER BY month;
```

### Find high albedo events
```sql
SELECT timestamp, albedo_greenroof, albedo_parkplatz
FROM synchronized_data_filtered
WHERE albedo_greenroof > 0.3 OR albedo_parkplatz > 0.3
ORDER BY timestamp DESC
LIMIT 100;
```

### Temperature difference analysis
```sql
SELECT 
    timestamp,
    avg_air_temperature_greenroof - avg_temp_parkplatz as temp_diff
FROM synchronized_data_filtered
WHERE timestamp > '2024-06-01' AND timestamp < '2024-09-01'
ORDER BY temp_diff DESC
LIMIT 20;
```

---

## Sharing the Dataset

### Option A: SQLite (Recommended for sharing)
- Single file, portable
- No installation needed
- Download SQLite Browser to open

### Option B: Parquet
- Compressed, efficient
- Best for data science workflows
- Install: `pip install pandas pyarrow`

### Option C: CSV (if needed)
- Universal, works everywhere
- Large file size (~1.5-2 GB uncompressed)

---

## Installation for Data Analysis

### Python Setup
```bash
# If not using SQLite natively
pip install pandas sqlite3

# For advanced queries
pip install duckdb  # Optional, faster SQL processing
```

### Database Tools (Free)
- **DB Browser for SQLite**: https://sqlitebrowser.org/
- **DataGrip**: https://www.jetbrains.com/datagrip/ (free trial)
- **VS Code Extension**: SQLite Viewer

---

## File Sizes (Approximate)

| Format | Size | Best For |
|--------|------|----------|
| PostgreSQL | ~2.5 GB (live DB) | Development, real-time queries |
| SQLite | 600-800 MB | Sharing, portable analysis |
| Parquet | 200-300 MB (compressed) | Python/data science |
| CSV | 1.5-2 GB | Excel, universal access |

---

## Troubleshooting

### "SQLite database is locked"
- Close other applications accessing the file
- Use read-only mode: `sqlite3 file.db <query>`

### "File too large for Excel"
- Use SQLite query to export filtered CSV
- Or use pandas with chunking

### "ODBC connection failed"
- Verify path is correct
- Use absolute paths: `C:\full\path\to\file.db`

---

## Next Steps

1. **Export**: Run `python scripts/export_to_sqlite.py`
2. **Download**: Get `outputs/bingen_greenroof.db`
3. **Open**: Use DB Browser or Python
4. **Analyze**: Query the data using SQL or pandas

---

**Need PostgreSQL back?**  
The pipeline still supports direct PostgreSQL queries:
```python
from dashboard.analysis import BingenGreenRoofAnalyzer
analyzer = BingenGreenRoofAnalyzer()
df = analyzer.load_data(year=2024)
```
