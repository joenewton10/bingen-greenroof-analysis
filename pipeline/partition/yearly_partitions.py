"""
Yearly Table Partitioning for synchronized_data_filtered.

Creates a partitioned parent table `synchronized_data_yearly` using PostgreSQL
declarative PARTITION BY RANGE on timestamp.  For every calendar year present
in `synchronized_data_filtered` (plus a default catch-all partition) a child
table is created automatically:

    synchronized_data_yearly         <- parent (query this for everything)
    sync_data_2020                   <- Jan 2020 – Dec 2020
    sync_data_2021
    sync_data_2022
    ...
    sync_data_default                <- safety net for unexpected years

The parent table is rebuilt from `synchronized_data_filtered` each pipeline
run.  Because the children are proper partitions, year-scoped queries run
against the parent table and PostgreSQL will only read the relevant partition.

Adding a new sensor year: just run the pipeline —
`ensure_year_partition()` creates the missing partition automatically.
"""
import sys
import time
from pathlib import Path

# Allow running this file directly from any working directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.ingest.base import get_connection


# --------------------------------------------------------------------------- #
# DDL                                                                         #
# --------------------------------------------------------------------------- #

CREATE_PARENT_SQL = """
CREATE TABLE IF NOT EXISTS synchronized_data_yearly (
    timestamp                        TIMESTAMP         NOT NULL,

    -- Parkplatz averages
    avg_ir1_parkplatz                NUMERIC,
    avg_sr1_parkplatz                NUMERIC,
    avg_ir2_parkplatz                NUMERIC,
    avg_sr2_parkplatz                NUMERIC,
    avg_temp_parkplatz               NUMERIC,
    avg_air_pressure_parkplatz       NUMERIC,
    avg_soil_moisture_parkplatz      NUMERIC,
    avg_air_humidity_1_parkplatz     NUMERIC,
    avg_air_temp_1_parkplatz         NUMERIC,
    avg_air_humidity_2_parkplatz     NUMERIC,
    avg_air_temp_2_parkplatz         NUMERIC,
    avg_wind_speed_parkplatz         NUMERIC,
    avg_wind_direction_parkplatz     NUMERIC,
    avg_soil_temp_1_parkplatz        NUMERIC,
    avg_soil_temp_2_parkplatz        NUMERIC,

    -- Greenroof averages
    avg_ir1_greenroof                NUMERIC,
    avg_air_temperature_greenroof    NUMERIC,
    avg_air_temp_2_greenroof         NUMERIC,
    avg_air_humidity_1_greenroof     NUMERIC,
    avg_air_humidity_2_greenroof     NUMERIC,
    avg_wind_speed_greenroof         NUMERIC,
    avg_soil_temperature_greenroof   NUMERIC,
    avg_soil_moisture_greenroof      NUMERIC,
    avg_global_radiation_greenroof   NUMERIC,
    avg_sr2_greenroof                NUMERIC,
    avg_ir2_greenroof                NUMERIC,

    -- Record quality counts
    parkplatz_record_count           BIGINT,
    greenroof_record_count           BIGINT,

    -- Dual-level availability
    has_dual_level_greenroof         BOOLEAN,
    measurement_period               TEXT,

    -- Temperature differences
    temp_diff_1                      NUMERIC,
    temp_diff_2                      NUMERIC,
    delta_t_roof                     NUMERIC,
    delta_rh_roof                    NUMERIC,
    delta_t_parkplatz                NUMERIC,
    delta_rh_parkplatz               NUMERIC,

    -- Energy & radiation
    energy_from_air_parkplatz        NUMERIC,
    energy_from_surface_parkplatz    NUMERIC,
    radiation_balance_greenroof      NUMERIC,
    radiation_balance_parkplatz      NUMERIC,
    albedo_greenroof                 NUMERIC,
    albedo_parkplatz                 NUMERIC
) PARTITION BY RANGE (timestamp);
"""

CREATE_DEFAULT_PARTITION_SQL = """
CREATE TABLE IF NOT EXISTS sync_data_default
    PARTITION OF synchronized_data_yearly DEFAULT;
"""

CREATE_YEAR_PARTITION_SQL = """
CREATE TABLE IF NOT EXISTS {table}
    PARTITION OF synchronized_data_yearly
    FOR VALUES FROM ('{year}-01-01') TO ('{next_year}-01-01');
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_sync_yearly_ts
    ON synchronized_data_yearly (timestamp);
"""

POPULATE_SQL = """
INSERT INTO synchronized_data_yearly
SELECT
    timestamp,
    avg_ir1_parkplatz, avg_sr1_parkplatz, avg_ir2_parkplatz, avg_sr2_parkplatz,
    avg_temp_parkplatz, avg_air_pressure_parkplatz, avg_soil_moisture_parkplatz,
    avg_air_humidity_1_parkplatz, avg_air_temp_1_parkplatz,
    avg_air_humidity_2_parkplatz, avg_air_temp_2_parkplatz,
    avg_wind_speed_parkplatz, avg_wind_direction_parkplatz,
    avg_soil_temp_1_parkplatz, avg_soil_temp_2_parkplatz,
    avg_ir1_greenroof, avg_air_temperature_greenroof, avg_air_temp_2_greenroof,
    avg_air_humidity_1_greenroof, avg_air_humidity_2_greenroof,
    avg_wind_speed_greenroof, avg_soil_temperature_greenroof,
    avg_soil_moisture_greenroof, avg_global_radiation_greenroof,
    avg_sr2_greenroof, avg_ir2_greenroof,
    parkplatz_record_count, greenroof_record_count,
    has_dual_level_greenroof, measurement_period,
    temp_diff_1, temp_diff_2, delta_t_roof, delta_rh_roof,
    delta_t_parkplatz, delta_rh_parkplatz,
    energy_from_air_parkplatz, energy_from_surface_parkplatz,
    radiation_balance_greenroof, radiation_balance_parkplatz,
    albedo_greenroof, albedo_parkplatz
FROM synchronized_data_filtered
ORDER BY timestamp ASC;
"""

YEARS_IN_DATA_SQL = """
SELECT DISTINCT EXTRACT(YEAR FROM timestamp)::INT AS yr
FROM synchronized_data_filtered
ORDER BY yr;
"""

DROP_CHILDREN_SQL = """
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename ~ '^sync_data_(\\d{4}|default)$';
"""


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _drop_existing_partitioned_table(cur):
    """Drop the parent (cascades to all partitions)."""
    cur.execute("DROP TABLE IF EXISTS synchronized_data_yearly CASCADE;")


def ensure_year_partition(cur, year: int):
    """Create partition for *year* if it does not already exist."""
    table = f"sync_data_{year}"
    sql = CREATE_YEAR_PARTITION_SQL.format(
        table=table,
        year=year,
        next_year=year + 1,
    )
    cur.execute(sql)
    return table


# --------------------------------------------------------------------------- #
# Public entry point                                                          #
# --------------------------------------------------------------------------- #

def create_yearly_partitions():
    """
    Build synchronized_data_yearly (partitioned) from synchronized_data_filtered.

    Steps:
      1. Detect all years present in synchronized_data_filtered.
      2. Drop and recreate the parent partitioned table.
      3. Create one child partition per year + a default catch-all.
      4. Bulk-copy all rows from synchronized_data_filtered.
      5. Create a covering timestamp index on the parent.
    """
    conn = get_connection()
    cur = conn.cursor()

    print('[yearly_partitions] Reading years in synchronized_data_filtered...')
    cur.execute(YEARS_IN_DATA_SQL)
    years = [row[0] for row in cur.fetchall()]

    if not years:
        print('[yearly_partitions] No data found in synchronized_data_filtered — skipping.')
        cur.close()
        conn.close()
        return

    print(f'[yearly_partitions] Years detected: {years}')
    t0 = time.time()

    # Rebuild partitioned table from scratch
    print('[yearly_partitions] (Re)creating partitioned parent table...')
    _drop_existing_partitioned_table(cur)
    cur.execute(CREATE_PARENT_SQL)

    # Default catch-all partition first (always present)
    cur.execute(CREATE_DEFAULT_PARTITION_SQL)

    # One partition per year
    for year in years:
        table = ensure_year_partition(cur, year)
        print(f'  Created partition: {table}')

    # Copy data
    print('[yearly_partitions] Populating partitions from synchronized_data_filtered...')
    cur.execute(POPULATE_SQL)

    # Index on parent propagates to all children automatically
    cur.execute(CREATE_INDEX_SQL)

    conn.commit()

    # Summary
    cur.execute("""
        SELECT
            EXTRACT(YEAR FROM timestamp)::INT AS yr,
            COUNT(*) AS rows,
            MIN(timestamp) AS first_ts,
            MAX(timestamp) AS last_ts
        FROM synchronized_data_yearly
        GROUP BY yr
        ORDER BY yr;
    """)
    rows = cur.fetchall()
    print(f'\n[yearly_partitions] Partition summary ({time.time() - t0:.1f}s):')
    print(f'  {"Year":<6}  {"Rows":>10}  {"First":>20}  {"Last":>20}')
    print('  ' + '-' * 62)
    for yr, count, first, last in rows:
        print(f'  {yr:<6}  {count:>10,}  {str(first)[:19]:>20}  {str(last)[:19]:>20}')

    cur.execute("SELECT COUNT(*) FROM synchronized_data_yearly;")
    total = cur.fetchone()[0]
    print(f'\n  Total rows across all partitions: {total:,}')

    cur.close()
    conn.close()

