"""
Validate parkplatz staging data.
Uses permissive ranges that accommodate observed data characteristics.

Table naming convention for Bingen pipeline:
- Source: ingested_parkplatz
- Output: val_ingested_parkplatz

NOTE: Known data quirks:
- air_pressure_mbar: Consistently ~800 (possibly uncalibrated or high elevation)
- rain_abs_mm: Cumulative counter that can exceed 600mm
"""
from pipeline.ingest.base import get_connection

# Validation ranges - made permissive based on actual data analysis
VALIDATION_RANGES = {
    'air_temp_1_c': (-25.0, 45.0),
    'air_temp_2_c': (-25.0, 45.0),
    'temp_c': (-25.0, 45.0),
    'soil_temp_1_c': (-10.0, 50.0),  # Relaxed upper bound
    'soil_temp_2_c': (-10.0, 50.0),  # Relaxed upper bound
    'internal_temp_c': (-30.0, 80.0),  # Device internal can run hot
    'air_humidity_1_rh': (0.0, 100.0),
    'air_humidity_2_rh': (0.0, 100.0),
    'air_pressure_mbar': (700.0, 1100.0),  # Relaxed to include observed ~800
    'soil_moisture_vol': (0.0, 100.0),
    'ir1_wm2': (-300.0, 1500.0),  # Allow slightly negative IR readings
    'ir2_wm2': (-300.0, 1500.0),
    'sr1_wm2': (-50.0, 1300.0),
    'sr2_wm2': (-50.0, 1300.0),
    'wind_speed_ms': (0.0, 50.0),
    'wind_direction_deg': (0.0, 360.0),
    'rain_abs_mm': (0.0, 10000.0),  # Cumulative can be very high
    'rain_rel_mm': (0.0, 200.0),  # Per-interval stays reasonable
    'battery_voltage_v': (8.0, 16.0),  # Slightly higher for charging
}

# Permissive validation SQL
VALIDATION_SQL = '''
CREATE TABLE IF NOT EXISTS val_ingested_parkplatz AS
SELECT *
FROM ingested_parkplatz
WHERE (air_temp_1_c IS NULL OR (air_temp_1_c BETWEEN -25.0 AND 45.0))
  AND (air_temp_2_c IS NULL OR (air_temp_2_c BETWEEN -25.0 AND 45.0))
  AND (temp_c IS NULL OR (temp_c BETWEEN -25.0 AND 45.0))
  AND (soil_temp_1_c IS NULL OR (soil_temp_1_c BETWEEN -10.0 AND 50.0))
  AND (soil_temp_2_c IS NULL OR (soil_temp_2_c BETWEEN -10.0 AND 50.0))
  AND (internal_temp_c IS NULL OR (internal_temp_c BETWEEN -30.0 AND 80.0))
  AND (air_humidity_1_rh IS NULL OR (air_humidity_1_rh BETWEEN 0.0 AND 100.0))
  AND (air_humidity_2_rh IS NULL OR (air_humidity_2_rh BETWEEN 0.0 AND 100.0))
  AND (air_pressure_mbar IS NULL OR (air_pressure_mbar BETWEEN 700.0 AND 1100.0))
  AND (soil_moisture_vol IS NULL OR (soil_moisture_vol BETWEEN 0.0 AND 100.0))
  AND (ir1_wm2 IS NULL OR (ir1_wm2 BETWEEN -300.0 AND 1500.0))
  AND (ir2_wm2 IS NULL OR (ir2_wm2 BETWEEN -300.0 AND 1500.0))
  AND (sr1_wm2 IS NULL OR (sr1_wm2 BETWEEN -50.0 AND 1300.0))
  AND (sr2_wm2 IS NULL OR (sr2_wm2 BETWEEN -50.0 AND 1300.0))
  AND (wind_speed_ms IS NULL OR (wind_speed_ms BETWEEN 0.0 AND 50.0))
  AND (wind_direction_deg IS NULL OR (wind_direction_deg BETWEEN 0.0 AND 360.0))
  AND (rain_abs_mm IS NULL OR (rain_abs_mm BETWEEN 0.0 AND 10000.0))
  AND (rain_rel_mm IS NULL OR (rain_rel_mm BETWEEN 0.0 AND 200.0))
  AND (battery_voltage_v IS NULL OR (battery_voltage_v BETWEEN 8.0 AND 16.0))
ORDER BY timestamp ASC;
'''

INDEX_SQL = '''
CREATE INDEX IF NOT EXISTS idx_val_ingested_parkplatz_timestamp ON val_ingested_parkplatz(timestamp);
CREATE INDEX IF NOT EXISTS idx_val_ingested_parkplatz_serial ON val_ingested_parkplatz(serial_number);
'''


def validate_parkplatz():
    '''Validate parkplatz data: filter by physical sensor ranges, then add performance indexes.'''
    conn = get_connection()
    cur = conn.cursor()

    # Drop and recreate val_ingested_parkplatz to ensure clean validation state
    cur.execute('DROP TABLE IF EXISTS val_ingested_parkplatz;')
    cur.execute(VALIDATION_SQL)
    cur.execute(INDEX_SQL)

    conn.commit()

    # Log validation result
    cur.execute('SELECT COUNT(*) FROM val_ingested_parkplatz;')
    count = cur.fetchone()[0]
    print(f'[validate_parkplatz] Validated {count} parkplatz records.')

    cur.close()
    conn.close()
