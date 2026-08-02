"""
Build IQAir vs climate comparison table in PostgreSQL.

This script:
1. Reads IQAir CSVs (parking, roofGround, roofTop)
2. Keeps temperature and relative humidity per minute (UTC)
3. Pulls matching minute-level climate data from harm_greenroof and harm_parkplatz
4. Creates and populates iqair_climate_comparison table

Usage:
    python scripts/create_iqair_comparison_table.py
    python scripts/create_iqair_comparison_table.py --table iqair_climate_comparison
"""
import sys
import argparse
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR
from pipeline.ingest.base import get_connection


IQAIR_FILE_MAP = {
    "parking": "parking_temperature_PM_humidity.csv",
    "roof_ground": "roofGround_temperature_PM_humidity.csv",
    "roof_top": "roofTop_temperature_PM_humidity.csv",
}


def _to_minute_utc_naive(series: pd.Series) -> pd.Series:
    """Convert timestamps to UTC minute precision, then drop tz info for DB joins."""
    ts = pd.to_datetime(series, utc=True, errors="coerce")
    return ts.dt.floor("min").dt.tz_localize(None)


def _load_iqair_position(iqair_dir: Path, position_key: str, filename: str) -> pd.DataFrame:
    """Load one IQAir position CSV and return minute-level temp/RH dataframe."""
    path = iqair_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing IQAir file: {path}")

    df = pd.read_csv(path)

    required = ["Datetime_start(UTC)", "Temperature (Celsius)", "Humidity (%)"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")

    temp_col = f"iqair_{position_key}_temp_c"
    rh_col = f"iqair_{position_key}_humidity_pct"

    out = df[["Datetime_start(UTC)", "Temperature (Celsius)", "Humidity (%)"]].copy()
    out["timestamp"] = _to_minute_utc_naive(out["Datetime_start(UTC)"])
    out[temp_col] = pd.to_numeric(out["Temperature (Celsius)"], errors="coerce")
    out[rh_col] = pd.to_numeric(out["Humidity (%)"], errors="coerce")
    out = out[["timestamp", temp_col, rh_col]].dropna(subset=["timestamp"])

    # Keep one row per minute in case there are duplicates.
    out = out.groupby("timestamp", as_index=False).agg({temp_col: "mean", rh_col: "mean"})
    return out


def _load_iqair_merged(iqair_dir: Path) -> pd.DataFrame:
    """Load and merge all IQAir positions into one timestamp-aligned dataframe."""
    merged = None
    for position_key, filename in IQAIR_FILE_MAP.items():
        current = _load_iqair_position(iqair_dir, position_key, filename)
        if merged is None:
            merged = current
        else:
            merged = merged.merge(current, on="timestamp", how="outer")

    assert merged is not None
    return merged.sort_values("timestamp").reset_index(drop=True)


def _load_greenroof_climate(conn) -> pd.DataFrame:
    """Fetch minute-level greenroof temperature and relative humidity."""
    sql = """
        SELECT
            date_trunc('minute', timestamp) AS timestamp,
            ROUND(AVG(air_temperature::numeric), 3) AS greenroof_air_temp_c,
            ROUND(AVG(relative_humidity::numeric), 3) AS greenroof_rel_humidity_pct
        FROM harm_greenroof
        WHERE timestamp IS NOT NULL
        GROUP BY 1
        ORDER BY 1 ASC;
    """
    return pd.read_sql_query(sql, conn)


def _load_parkplatz_climate(conn) -> pd.DataFrame:
    """Fetch minute-level parkplatz Air Temp/Humidity for both sensor levels."""
    sql = """
        SELECT
            date_trunc('minute', timestamp) AS timestamp,
            ROUND(AVG("Air Temp 1 [C]"::numeric), 3) AS parkplatz_air_temp_1_c,
            ROUND(AVG("Air Humidity 1 [%RH]"::numeric), 3) AS parkplatz_air_humidity_1_pct,
            ROUND(AVG("Air Temp 2 [C]"::numeric), 3) AS parkplatz_air_temp_2_c,
            ROUND(AVG("Air Humidity 2 [%RH]"::numeric), 3) AS parkplatz_air_humidity_2_pct
        FROM harm_parkplatz
        WHERE timestamp IS NOT NULL
        GROUP BY 1
        ORDER BY 1 ASC;
    """
    return pd.read_sql_query(sql, conn)


def _create_output_table(cur, table_name: str):
    """Drop and recreate output table."""
    cur.execute(f"DROP TABLE IF EXISTS {table_name};")
    cur.execute(
        f"""
        CREATE TABLE {table_name} (
            timestamp TIMESTAMP PRIMARY KEY,
            iqair_parking_temp_c NUMERIC,
            iqair_parking_humidity_pct NUMERIC,
            iqair_roof_ground_temp_c NUMERIC,
            iqair_roof_ground_humidity_pct NUMERIC,
            iqair_roof_top_temp_c NUMERIC,
            iqair_roof_top_humidity_pct NUMERIC,
            greenroof_air_temp_c NUMERIC,
            greenroof_rel_humidity_pct NUMERIC,
            parkplatz_air_temp_1_c NUMERIC,
            parkplatz_air_humidity_1_pct NUMERIC,
            parkplatz_air_temp_2_c NUMERIC,
            parkplatz_air_humidity_2_pct NUMERIC
        );
        """
    )


def _insert_output_rows(cur, table_name: str, df: pd.DataFrame):
    """Bulk insert dataframe rows into output table."""
    if df.empty:
        return

    ordered_cols = [
        "timestamp",
        "iqair_parking_temp_c",
        "iqair_parking_humidity_pct",
        "iqair_roof_ground_temp_c",
        "iqair_roof_ground_humidity_pct",
        "iqair_roof_top_temp_c",
        "iqair_roof_top_humidity_pct",
        "greenroof_air_temp_c",
        "greenroof_rel_humidity_pct",
        "parkplatz_air_temp_1_c",
        "parkplatz_air_humidity_1_pct",
        "parkplatz_air_temp_2_c",
        "parkplatz_air_humidity_2_pct",
    ]

    insert_sql = f"""
        INSERT INTO {table_name} (
            timestamp,
            iqair_parking_temp_c,
            iqair_parking_humidity_pct,
            iqair_roof_ground_temp_c,
            iqair_roof_ground_humidity_pct,
            iqair_roof_top_temp_c,
            iqair_roof_top_humidity_pct,
            greenroof_air_temp_c,
            greenroof_rel_humidity_pct,
            parkplatz_air_temp_1_c,
            parkplatz_air_humidity_1_pct,
            parkplatz_air_temp_2_c,
            parkplatz_air_humidity_2_pct
        ) VALUES %s
    """

    insert_df = df[ordered_cols].copy().where(pd.notnull(df[ordered_cols]), None)
    rows = [tuple(row) for row in insert_df.itertuples(index=False, name=None)]
    execute_values(cur, insert_sql, rows, page_size=5000)


def build_comparison_table(table_name: str = "iqair_climate_comparison"):
    """Orchestrate IQAir + climate merge and write output table."""
    iqair_dir = Path(RAW_DATA_DIR) / "IQair"
    print(f"[iqair_comparison] Reading IQAir files from: {iqair_dir}")
    iqair_df = _load_iqair_merged(iqair_dir)
    print(f"[iqair_comparison] IQAir rows (minute-level): {len(iqair_df):,}")

    conn = get_connection()
    cur = conn.cursor()

    try:
        print("[iqair_comparison] Loading minute-level climate data from PostgreSQL...")
        greenroof_df = _load_greenroof_climate(conn)
        parkplatz_df = _load_parkplatz_climate(conn)

        for frame in (greenroof_df, parkplatz_df):
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce").dt.floor("min")

        merged = iqair_df.merge(greenroof_df, on="timestamp", how="left")
        merged = merged.merge(parkplatz_df, on="timestamp", how="left")
        merged = merged.sort_values("timestamp").drop_duplicates(subset=["timestamp"]) 

        print(f"[iqair_comparison] Final merged rows: {len(merged):,}")
        print(f"[iqair_comparison] Creating table: {table_name}")
        _create_output_table(cur, table_name)
        _insert_output_rows(cur, table_name, merged)
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_ts ON {table_name}(timestamp);")
        cur.execute(f"ANALYZE {table_name};")
        conn.commit()

        print(f"[iqair_comparison] Done. Wrote {len(merged):,} rows into {table_name}.")
    finally:
        cur.close()
        conn.close()


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Create IQAir vs roof/parking temperature-humidity comparison table"
    )
    parser.add_argument(
        "--table",
        default="iqair_climate_comparison",
        help="Output PostgreSQL table name (default: iqair_climate_comparison)",
    )
    return parser.parse_args()


def main():
    """CLI entrypoint."""
    args = parse_args()
    build_comparison_table(table_name=args.table)


if __name__ == "__main__":
    main()
