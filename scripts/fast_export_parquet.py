"""
Fast Parquet export using PostgreSQL COPY and DuckDB.

This script uses PostgreSQL's COPY command (which is much faster than pandas)
to export to CSV, then converts to Parquet using DuckDB.

Usage:
    python scripts/fast_export_parquet.py
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_streamlit_secrets():
    """Load secrets from .streamlit/secrets.toml if it exists"""
    secrets_file = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    secrets = {}
    
    if secrets_file.exists():
        with open(secrets_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    secrets[key.strip()] = value.strip().strip('"\'')
    
    return secrets


def _get_secret(name):
    """Retrieve secret from .streamlit/secrets.toml or environment"""
    secrets = _load_streamlit_secrets()
    if name in secrets:
        return secrets[name]
    return os.getenv(name)


def _get_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_db_params():
    """Get database connection parameters"""
    return {
        "dbname": _get_secret("DB_NAME") or "bingen_greenroof",
        "user": _get_secret("DB_USER") or "postgres",
        "password": _get_secret("DB_PASSWORD") or "",
        "host": _get_secret("DB_HOST") or "localhost",
        "port": _get_int(_get_secret("DB_PORT"), 5432),
    }


def export_using_duckdb():
    """Export using DuckDB's PostgreSQL extension (fastest approach)"""
    try:
        import duckdb
    except ImportError:
        print("   ⚠️  DuckDB not installed, try: pip install duckdb")
        return False
    
    db_params = _get_db_params()
    
    # Build PostgreSQL connection string for DuckDB
    pg_conn_str = (
        f"postgres://{db_params['user']}:{db_params['password']}"
        f"@{db_params['host']}:{db_params['port']}/{db_params['dbname']}"
    )
    
    try:
        print("   Installing PostgreSQL extension in DuckDB...", end=" ")
        db = duckdb.sql(f"INSTALL postgres; LOAD postgres;")
        print("✓")
        
        print("   Querying PostgreSQL...", end=" ")
        # Query directly from PostgreSQL
        result = duckdb.sql(f"""
            SELECT * FROM postgres_scan('{pg_conn_str}', 'synchronized_data_filtered')
        """)
        print("✓")
        
        # Export complete data
        complete_file = PROJECT_ROOT / "outputs" / "synchronized_data_complete.parquet"
        print(f"   Writing complete file...", end=" ")
        result.to_parquet(str(complete_file))
        size_mb = os.path.getsize(complete_file) / (1024 ** 2)
        row_count = len(result)
        print(f"✓ ({row_count:,} rows, {size_mb:.1f} MB)")
        
        # Export yearly files
        yearly_dir = PROJECT_ROOT / "outputs" / "parquet_yearly"
        yearly_dir.mkdir(parents=True, exist_ok=True)
        
        print("   Exporting yearly partitions...")
        for year in range(2020, 2026):
            year_result = duckdb.sql(f"""
                SELECT * FROM postgres_scan('{pg_conn_str}', 'synchronized_data_filtered')
                WHERE EXTRACT(YEAR FROM timestamp) = {year}
            """)
            
            if len(year_result) > 0:
                year_file = yearly_dir / f"{year}.parquet"
                year_result.to_parquet(str(year_file))
                size_mb = os.path.getsize(year_file) / (1024 ** 2)
                row_count = len(year_result)
                print(f"      {year}: {row_count:,} rows, {size_mb:.1f} MB ✓")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def export_using_pandas():
    """Fallback: Export using pandas with efficient batching"""
    print("   Using pandas with batching...")
    
    db_params = _get_db_params()
    engine = create_engine(URL.create(
        "postgresql",
        username=db_params['user'],
        password=db_params['password'],
        host=db_params['host'],
        port=db_params['port'],
        database=db_params['dbname'],
    ))
    
    # Get total row count
    count_result = pd.read_sql_query(
        "SELECT COUNT(*) as cnt FROM synchronized_data_filtered",
        engine
    )
    total_rows = int(count_result.loc[0, 'cnt'])
    print(f"   Total records: {total_rows:,}")
    
    # Export complete data in batches
    complete_file = PROJECT_ROOT / "outputs" / "synchronized_data_complete.parquet"
    batch_size = 100000
    all_data = []
    
    print("   Reading batches...", end="", flush=True)
    for offset in range(0, total_rows, batch_size):
        query = f"""
            SELECT * FROM synchronized_data_filtered
            ORDER BY timestamp
            LIMIT {batch_size} OFFSET {offset}
        """
        df_batch = pd.read_sql_query(query, engine)
        
        if 'timestamp' in df_batch.columns:
            df_batch['timestamp'] = pd.to_datetime(df_batch['timestamp'])
        
        all_data.append(df_batch)
        progress = min(((offset + batch_size) / total_rows) * 100, 100)
        print(f"\r   Reading batches...{progress:.0f}%", end="", flush=True)
    
    print(" ✓")
    
    print("   Combining and writing...", end=" ")
    df_complete = pd.concat(all_data, ignore_index=True)
    df_complete.to_parquet(str(complete_file), compression='snappy', index=False)
    file_size_mb = os.path.getsize(complete_file) / (1024 ** 2)
    print(f"✓ ({file_size_mb:.1f} MB)")
    
    # Yearly exports
    yearly_dir = PROJECT_ROOT / "outputs" / "parquet_yearly"
    yearly_dir.mkdir(parents=True, exist_ok=True)
    
    df_complete['year'] = pd.to_datetime(df_complete['timestamp']).dt.year
    years = sorted(df_complete['year'].unique())
    
    print(f"   Exporting {len(years)} yearly files...")
    for year in years:
        year_data = df_complete[df_complete['year'] == year].drop(columns=['year'])
        year_file = yearly_dir / f"{year}.parquet"
        year_data.to_parquet(str(year_file), compression='snappy', index=False)
        size_mb = os.path.getsize(year_file) / (1024 ** 2)
        row_count = len(year_data)
        print(f"      {year}: {row_count:,} rows, {size_mb:.1f} MB ✓")
    
    engine.dispose()
    return True


def main():
    """Main export routine"""
    print("=" * 70)
    print("BINGEN GREEN ROOF FAST PARQUET EXPORT")
    print("=" * 70)
    
    outputs_dir = PROJECT_ROOT / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    
    # Try DuckDB first (fastest)
    print("\n📊 Attempting fast export with DuckDB...")
    if export_using_duckdb():
        print("\n✅ EXPORT COMPLETE (using DuckDB)")
        print("=" * 70)
        return 0
    
    # Fallback to pandas
    print("\n📊 Falling back to pandas batch export...")
    try:
        if export_using_pandas():
            print("\n✅ EXPORT COMPLETE (using pandas)")
            print("=" * 70)
            return 0
    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
