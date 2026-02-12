"""
Validate greenroof ingested tables for both Empower and Kissel sources.
Uses simplified schema (no metadata/counter/system columns).

Table naming convention for Bingen pipeline:
- Source: ingested_empower_greenroof, ingested_kissel_greenroof
- Output: val_ingested_empower_greenroof, val_ingested_kissel_greenroof

NOTE: Known data quirks:
- soil_temp_2: Often -50.0 (sentinel for missing/disconnected sensor)
- This is handled by allowing values equal to -50 to pass through
"""
from pipeline.ingest.base import get_connection

# Validation ranges based on Bingen am Rhein climate and sensor capabilities
VALIDATION_RANGES = {
    'air_temperature': (-25.0, 45.0),
    'soil_temperature': (-20.0, 50.0),
    'relative_humidity': (0.0, 100.0),
    'wind_speed': (0.0, 50.0),
    'wind_direction': (0.0, 360.0),
    'soil_moisture': (0.0, 60.0),
    'global_radiation': (-50.0, 1200.0),  # W/m2 for sr1
    'infrared_radiation': (-500.0, 500.0),  # W/m2 for ir1/ir2
    'temperature': (-25.0, 45.0),  # Generic temperature sensor
    'air_pressure': (900.0, 1100.0),  # hPa
}

# Validate Empower greenroof ingested table
# soil_temp_2 allows -50 as sentinel value for missing sensor
VAL_EMPOWER_SQL = '''
CREATE TABLE IF NOT EXISTS val_ingested_empower_greenroof AS
SELECT
    id,
    timestamp,
    serial_no,
    ir1, sr1, ir2, sr2,
    temperature,
    air_pressure,
    soil_moisture,
    soil_temp_1, soil_temp_2,
    air_humidity_1, air_temp_1,
    air_humidity_2, air_temp_2,
    wind_speed, wind_direction,
    file_name
FROM ingested_empower_greenroof
WHERE
    -- Air temperature checks
    (air_temp_1 IS NULL OR (air_temp_1 BETWEEN -25.0 AND 45.0))
    AND (air_temp_2 IS NULL OR (air_temp_2 BETWEEN -25.0 AND 45.0))
    AND (temperature IS NULL OR (temperature BETWEEN -25.0 AND 45.0))

    -- Soil temperature checks (allow -50 sentinel)
    AND (soil_temp_1 IS NULL OR (soil_temp_1 BETWEEN -20.0 AND 50.0))
    AND (soil_temp_2 IS NULL OR soil_temp_2 = -50.0 OR (soil_temp_2 BETWEEN -20.0 AND 50.0))

    -- Humidity checks
    AND (air_humidity_1 IS NULL OR (air_humidity_1 BETWEEN 0.0 AND 100.0))
    AND (air_humidity_2 IS NULL OR (air_humidity_2 BETWEEN 0.0 AND 100.0))

    -- Wind checks
    AND (wind_speed IS NULL OR (wind_speed BETWEEN 0.0 AND 50.0))
    AND (wind_direction IS NULL OR (wind_direction BETWEEN 0.0 AND 360.0))

    -- Soil moisture check
    AND (soil_moisture IS NULL OR (soil_moisture BETWEEN 0.0 AND 60.0))

    -- Radiation checks
    AND (sr1 IS NULL OR (sr1 BETWEEN -50.0 AND 1200.0))
    AND (sr2 IS NULL OR (sr2 BETWEEN -50.0 AND 1200.0))
    AND (ir1 IS NULL OR (ir1 BETWEEN -500.0 AND 500.0))
    AND (ir2 IS NULL OR (ir2 BETWEEN -500.0 AND 500.0))

    -- Pressure check
    AND (air_pressure IS NULL OR (air_pressure BETWEEN 900.0 AND 1100.0))
ORDER BY timestamp ASC;
'''

# Validate Kissel greenroof ingested table
VAL_KISSEL_SQL = '''
CREATE TABLE IF NOT EXISTS val_ingested_kissel_greenroof AS
SELECT
    id,
    timestamp,
    serial_no,
    ir1, sr1, ir2, sr2,
    temperature,
    air_pressure,
    soil_moisture,
    soil_temp_1, soil_temp_2,
    air_humidity_1, air_temp_1,
    air_humidity_2, air_temp_2,
    wind_speed, wind_direction,
    file_name
FROM ingested_kissel_greenroof
WHERE
    -- Air temperature checks
    (air_temp_1 IS NULL OR (air_temp_1 BETWEEN -25.0 AND 45.0))
    AND (air_temp_2 IS NULL OR (air_temp_2 BETWEEN -25.0 AND 45.0))
    AND (temperature IS NULL OR (temperature BETWEEN -25.0 AND 45.0))

    -- Soil temperature checks (allow -50 sentinel)
    AND (soil_temp_1 IS NULL OR (soil_temp_1 BETWEEN -20.0 AND 50.0))
    AND (soil_temp_2 IS NULL OR soil_temp_2 = -50.0 OR (soil_temp_2 BETWEEN -20.0 AND 50.0))

    -- Humidity checks
    AND (air_humidity_1 IS NULL OR (air_humidity_1 BETWEEN 0.0 AND 100.0))
    AND (air_humidity_2 IS NULL OR (air_humidity_2 BETWEEN 0.0 AND 100.0))

    -- Wind checks
    AND (wind_speed IS NULL OR (wind_speed BETWEEN 0.0 AND 50.0))
    AND (wind_direction IS NULL OR (wind_direction BETWEEN 0.0 AND 360.0))

    -- Soil moisture check
    AND (soil_moisture IS NULL OR (soil_moisture BETWEEN 0.0 AND 60.0))

    -- Radiation checks
    AND (sr1 IS NULL OR (sr1 BETWEEN -50.0 AND 1200.0))
    AND (sr2 IS NULL OR (sr2 BETWEEN -50.0 AND 1200.0))
    AND (ir1 IS NULL OR (ir1 BETWEEN -500.0 AND 500.0))
    AND (ir2 IS NULL OR (ir2 BETWEEN -500.0 AND 500.0))

    -- Pressure check (allow NULL since Kissel doesn't have pressure)
    AND (air_pressure IS NULL OR (air_pressure BETWEEN 900.0 AND 1100.0))
ORDER BY timestamp ASC;
'''

INDEX_EMPOWER_SQL = '''
CREATE INDEX IF NOT EXISTS idx_val_ingested_empower_greenroof_ts ON val_ingested_empower_greenroof(timestamp);
CREATE INDEX IF NOT EXISTS idx_val_ingested_empower_greenroof_serial ON val_ingested_empower_greenroof(serial_no);
'''

INDEX_KISSEL_SQL = '''
CREATE INDEX IF NOT EXISTS idx_val_ingested_kissel_greenroof_ts ON val_ingested_kissel_greenroof(timestamp);
CREATE INDEX IF NOT EXISTS idx_val_ingested_kissel_greenroof_serial ON val_ingested_kissel_greenroof(serial_no);
'''


def validate_greenroof():
    '''Validate BOTH greenroof ingested tables: empower and kissel.'''
    conn = get_connection()
    cur = conn.cursor()

    # Validate Empower greenroof
    cur.execute('DROP TABLE IF EXISTS val_ingested_empower_greenroof;')
    cur.execute(VAL_EMPOWER_SQL)
    cur.execute(INDEX_EMPOWER_SQL)

    cur.execute('SELECT COUNT(*) FROM val_ingested_empower_greenroof;')
    empower_count = cur.fetchone()[0]
    print(f'[validate_greenroof] Validated {empower_count} Empower records.')

    # Validate Kissel greenroof
    cur.execute('DROP TABLE IF EXISTS val_ingested_kissel_greenroof;')
    cur.execute(VAL_KISSEL_SQL)
    cur.execute(INDEX_KISSEL_SQL)

    cur.execute('SELECT COUNT(*) FROM val_ingested_kissel_greenroof;')
    kissel_count = cur.fetchone()[0]
    print(f'[validate_greenroof] Validated {kissel_count} Kissel records.')

    conn.commit()
    cur.close()
    conn.close()

    print(f'[validate_greenroof] Total: {empower_count + kissel_count} greenroof records validated.')
