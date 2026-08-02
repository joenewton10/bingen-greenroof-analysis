"""
Export synchronized_data_filtered table to Parquet format.

Generates:
1. outputs/synchronized_data_complete.parquet (all records)
2. outputs/parquet_yearly/*.parquet (one file per year)

Usage:
    python scripts/export_to_parquet.py
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_streamlit_secrets():
    """Load secrets from .streamlit/secrets.toml if it exists"""
    secrets_file = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    secrets = {}
    
    if secrets_file.exists():
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # Fallback for earlier Python versions
            except ImportError:
                # Try simple TOML parsing manually
                with open(secrets_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            secrets[key.strip()] = value.strip().strip('"\'')
                return secrets
        
        with open(secrets_file, 'rb') as f:
            secrets = tomllib.load(f)
    
    return secrets


def _get_secret(name):
    """Retrieve secret from .streamlit/secrets.toml, environment, or .env"""
    # First try Streamlit secrets
    secrets = _load_streamlit_secrets()
    if name in secrets:
        return secrets[name]
    
    # Then try environment
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


def create_engine_connection(db_params):
    """Create SQLAlchemy engine for PostgreSQL"""
    engine = create_engine(URL.create(
        "postgresql",
        username=db_params['user'],
        password=db_params['password'],
        host=db_params['host'],
        port=db_params['port'],
        database=db_params['dbname'],
    ))
    return engine


def get_total_rows(engine):
    """Get total row count in synchronized_data_filtered"""
    query = text("SELECT COUNT(*) as cnt FROM synchronized_data_filtered;")
    result = pd.read_sql_query(query, engine)
    return int(result.loc[0, 'cnt'])


def export_complete_data(engine, output_path):
    """
    Export all data to a single parquet file using simple batching.
    """
    print(f"\n📊 Exporting complete dataset to: {output_path}")
    
    total_rows = get_total_rows(engine)
    print(f"   Total records to export: {total_rows:,}")
    
    # Use simple DataFrame.to_parquet with chunked read
    batch_size = 50000
    all_data = []
    
    print("   Reading in batches...", end=" ")
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
        print(f"\r   Reading in batches...{progress:.0f}%", end="", flush=True)
    
    print(" ✓")
    
    print("   Concatenating data...", end=" ")
    df_complete = pd.concat(all_data, ignore_index=True)
    print("✓")
    
    print("   Writing to parquet...", end=" ")
    df_complete.to_parquet(output_path, compression='snappy', index=False, engine='pyarrow')
    file_size_mb = os.path.getsize(output_path) / (1024 ** 2)
    print(f"✓ ({file_size_mb:.1f} MB)")
    
    return df_complete


def export_yearly_data(engine, output_dir):
    """
    Export data partitioned by year.
    Creates one parquet file per year in output_dir.
    """
    print(f"\n📅 Exporting yearly partitions to: {output_dir}")
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get years from database
    query = text(
        """
        SELECT DISTINCT EXTRACT(YEAR FROM timestamp)::int AS year
        FROM synchronized_data_filtered
        WHERE timestamp IS NOT NULL
        ORDER BY year;
        """
    )
    years_df = pd.read_sql_query(query, engine)
    years = sorted(years_df['year'].dropna().astype(int).tolist())
    
    print(f"   Found {len(years)} years: {years}")
    
    # Export each year
    for year in years:
        output_file = output_dir / f"{year}.parquet"
        query = f"""
            SELECT * FROM synchronized_data_filtered
            WHERE EXTRACT(YEAR FROM timestamp)::int = {year}
            ORDER BY timestamp
        """
        print(f"   Exporting {year}...", end=" ")
        
        year_data = pd.read_sql_query(query, engine)
        
        if 'timestamp' in year_data.columns:
            year_data['timestamp'] = pd.to_datetime(year_data['timestamp'])
        
        year_data.to_parquet(output_file, compression='snappy', index=False)
        file_size_mb = os.path.getsize(output_file) / (1024 ** 2)
        row_count = len(year_data)
        print(f"✓ ({row_count:,} rows, {file_size_mb:.1f} MB)")


def main():
    """Main export routine"""
    print("=" * 70)
    print("BINGEN GREEN ROOF PARQUET EXPORT")
    print("=" * 70)
    
    # Setup paths
    outputs_dir = PROJECT_ROOT / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    
    complete_file = outputs_dir / "synchronized_data_complete.parquet"
    yearly_dir = outputs_dir / "parquet_yearly"
    
    # Get database connection
    print("\n🔌 Connecting to PostgreSQL...")
    db_params = _get_db_params()
    print(f"   Host: {db_params['host']}")
    print(f"   Database: {db_params['dbname']}")
    
    try:
        engine = create_engine_connection(db_params)
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("   ✓ Connection successful")
        
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return 1
    
    try:
        # Export complete dataset
        df_complete = export_complete_data(engine, complete_file)
        
        # Export yearly partitions
        export_yearly_data(engine, yearly_dir)
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ EXPORT COMPLETE")
        print("=" * 70)
        print(f"\n📁 Output files:")
        print(f"   Complete file: {complete_file.relative_to(PROJECT_ROOT)}")
        print(f"   Yearly files:  {yearly_dir.relative_to(PROJECT_ROOT)}/")
        
        # List yearly files
        if yearly_dir.exists():
            yearly_files = sorted(yearly_dir.glob("*.parquet"))
            total_size = 0
            for f in yearly_files:
                size_mb = os.path.getsize(f) / (1024 ** 2)
                total_size += size_mb
                print(f"      - {f.name} ({size_mb:.1f} MB)")
        
        complete_size = os.path.getsize(complete_file) / (1024 ** 2)
        complete_rows = len(df_complete) if hasattr(df_complete, '__len__') else get_total_rows(engine)
        
        print(f"\n💾 Complete file: {complete_size:.1f} MB ({complete_rows:,} records)")
        
        print("\n📖 How to load in Python:")
        print("   import pandas as pd")
        print("   df = pd.read_parquet('outputs/synchronized_data_complete.parquet')")
        print("   # Or load yearly:")
        print("   df_2024 = pd.read_parquet('outputs/parquet_yearly/2024.parquet')")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
