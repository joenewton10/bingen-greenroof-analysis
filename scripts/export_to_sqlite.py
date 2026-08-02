"""
Export synchronized_data_filtered to SQLite database.

This creates a portable SQLite database file that can be opened on any
system without PostgreSQL. Supports full SQL queries.

Usage:
    python scripts/export_to_sqlite.py

Output:
    outputs/bingen_greenroof.db (~600-800 MB)
    outputs/bingen_greenroof_yearly/*.db (optional yearly splits)
"""

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

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
    """Get PostgreSQL connection parameters"""
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
    """Get total row count"""
    query = text("SELECT COUNT(*) as cnt FROM synchronized_data_filtered;")
    result = pd.read_sql_query(query, engine)
    return int(result.loc[0, 'cnt'])


def export_complete_sqlite(pg_engine, sqlite_path):
    """
    Export complete dataset to SQLite using chunked batch processing.
    """
    print(f"\n📊 Exporting complete dataset to SQLite: {sqlite_path}")
    
    total_rows = get_total_rows(pg_engine)
    print(f"   Total records to export: {total_rows:,}")
    
    # Create SQLite connection
    sqlite_conn = sqlite3.connect(sqlite_path)
    
    batch_size = 50000
    offset = 0
    
    print("   Reading and writing in batches...", end="", flush=True)
    
    while offset < total_rows:
        # Read batch from PostgreSQL
        query = f"""
            SELECT * FROM synchronized_data_filtered
            ORDER BY timestamp
            LIMIT {batch_size} OFFSET {offset}
        """
        df_batch = pd.read_sql_query(query, pg_engine)
        
        if len(df_batch) == 0:
            break
        
        # Convert timestamp to string for SQLite compatibility
        if 'timestamp' in df_batch.columns:
            df_batch['timestamp'] = pd.to_datetime(df_batch['timestamp']).astype(str)
        
        # Write to SQLite (append mode)
        df_batch.to_sql(
            'synchronized_data_filtered',
            sqlite_conn,
            if_exists='append' if offset > 0 else 'replace',
            index=False,
            chunksize=1000
        )
        
        offset += batch_size
        progress = min(((offset) / total_rows) * 100, 100)
        print(f"\r   Reading and writing in batches...{progress:.0f}%", end="", flush=True)
    
    # Create index for faster queries
    print("\n   Creating index on timestamp...", end=" ")
    cursor = sqlite_conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON synchronized_data_filtered(timestamp)")
    sqlite_conn.commit()
    print("✓")
    
    # Get file size
    file_size_mb = os.path.getsize(sqlite_path) / (1024 ** 2)
    print(f"   ✓ SQLite database created: {file_size_mb:.1f} MB")
    
    sqlite_conn.close()
    return total_rows


def export_yearly_sqlite(pg_engine, yearly_dir):
    """
    Export yearly data to separate SQLite databases.
    """
    print(f"\n📅 Exporting yearly SQLite databases to: {yearly_dir}")
    
    yearly_dir.mkdir(parents=True, exist_ok=True)
    
    # Get available years
    query = text("""
        SELECT DISTINCT EXTRACT(YEAR FROM timestamp)::int AS year
        FROM synchronized_data_filtered
        WHERE timestamp IS NOT NULL
        ORDER BY year;
    """)
    years_df = pd.read_sql_query(query, pg_engine)
    years = sorted(years_df['year'].dropna().astype(int).tolist())
    
    print(f"   Found {len(years)} years: {years}")
    
    for year in years:
        sqlite_path = yearly_dir / f"{year}.db"
        print(f"   Exporting {year}...", end=" ")
        
        # Query year data
        query = f"""
            SELECT * FROM synchronized_data_filtered
            WHERE EXTRACT(YEAR FROM timestamp)::int = {year}
            ORDER BY timestamp
        """
        df_year = pd.read_sql_query(query, pg_engine)
        
        if 'timestamp' in df_year.columns:
            df_year['timestamp'] = pd.to_datetime(df_year['timestamp']).astype(str)
        
        # Write to SQLite
        sqlite_conn = sqlite3.connect(sqlite_path)
        df_year.to_sql(
            'synchronized_data_filtered',
            sqlite_conn,
            if_exists='replace',
            index=False,
            chunksize=1000
        )
        
        # Create index
        cursor = sqlite_conn.cursor()
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON synchronized_data_filtered(timestamp)")
        sqlite_conn.commit()
        sqlite_conn.close()
        
        file_size_mb = os.path.getsize(sqlite_path) / (1024 ** 2)
        row_count = len(df_year)
        print(f"✓ ({row_count:,} rows, {file_size_mb:.1f} MB)")


def main():
    """Main export routine"""
    print("=" * 70)
    print("BINGEN GREEN ROOF SQLITE EXPORT")
    print("=" * 70)
    
    # Setup paths
    outputs_dir = PROJECT_ROOT / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    
    complete_file = outputs_dir / "bingen_greenroof.db"
    yearly_dir = outputs_dir / "bingen_greenroof_yearly"
    
    # Get database connection
    print("\n🔌 Connecting to PostgreSQL...")
    db_params = _get_db_params()
    print(f"   Host: {db_params['host']}")
    print(f"   Database: {db_params['dbname']}")
    
    try:
        pg_engine = create_engine_connection(db_params)
        
        # Test connection
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("   ✓ Connection successful")
        
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return 1
    
    try:
        # Export complete dataset
        total_complete = export_complete_sqlite(pg_engine, complete_file)
        
        # Export yearly datasets
        export_yearly_sqlite(pg_engine, yearly_dir)
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ SQLITE EXPORT COMPLETE")
        print("=" * 70)
        
        complete_size = os.path.getsize(complete_file) / (1024 ** 2)
        print(f"\n📁 Output files:")
        print(f"   Complete:    {complete_file.name} ({complete_size:.1f} MB)")
        print(f"   {total_complete:,} records")
        
        if yearly_dir.exists():
            yearly_files = sorted(yearly_dir.glob("*.db"))
            print(f"\n   Yearly splits ({len(yearly_files)} files):")
            total_yearly_size = 0
            for f in yearly_files:
                size_mb = os.path.getsize(f) / (1024 ** 2)
                total_yearly_size += size_mb
                print(f"      {f.name}: {size_mb:.1f} MB")
            print(f"      Total: {total_yearly_size:.1f} MB")
        
        print("\n📖 How to use:")
        print("   # In Python:")
        print("   import pandas as pd")
        print("   import sqlite3")
        print("   ")
        print("   conn = sqlite3.connect('outputs/bingen_greenroof.db')")
        print("   df = pd.read_sql_query('SELECT * FROM synchronized_data_filtered', conn)")
        print("   ")
        print("   # Or query with filters:")
        print("   df = pd.read_sql_query(")
        print("       'SELECT * FROM synchronized_data_filtered WHERE timestamp > ?',")
        print("       conn,")
        print("       params=('2024-01-01',)")
        print("   )")
        print("   ")
        print("   # In Excel/Sheets:")
        print("   - Download SQLite Browser (DB Browser for SQLite)")
        print("   - Open .db file and browse/export tables")
        print("   ")
        print("   # Command line:")
        print("   sqlite3 outputs/bingen_greenroof.db")
        print("   > SELECT COUNT(*) FROM synchronized_data_filtered;")
        print("   > .schema")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        pg_engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
