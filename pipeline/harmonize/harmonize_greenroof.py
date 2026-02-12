'''
Harmonize Greenroof Data - Combine BOTH validated sources into canonical schema.

Based on: combine_greenroof.py

Table naming convention for Bingen pipeline:
- Sources: val_ingested_empower_greenroof, val_ingested_kissel_greenroof
- Output: harm_greenroof

Both validated tables have identical schema:
  id, timestamp, serial_no, ir1, sr1, ir2, sr2, temperature, air_pressure,
  soil_moisture, soil_temp_1, soil_temp_2, air_humidity_1, air_temp_1,
  air_humidity_2, air_temp_2, wind_speed, wind_direction, file_name

Canonical columns (12 total):
1. id, 2. timestamp, 3. serial_number, 4. global_radiation, 5. air_temperature,
6. relative_humidity, 7. wind_speed_avg, 8. wind_direction_1, 9. soil_temperature,
10. soil_moisture, 11. source, 12. filename
'''
from pipeline.ingest.base import get_connection


# Combine BOTH validated greenroof tables with column mapping to canonical names
HARM_SQL = '''
CREATE TABLE IF NOT EXISTS harm_greenroof AS

-- Empower source: map column names to canonical
SELECT
    id,
    timestamp,
    serial_no AS serial_number,
    sr1 AS global_radiation,
    air_temp_1 AS air_temperature,
    air_humidity_1 AS relative_humidity,
    wind_speed AS wind_speed_avg,
    wind_direction AS wind_direction_1,
    soil_temp_1 AS soil_temperature,
    soil_moisture,
    'empower' AS source,
    file_name AS filename
FROM val_ingested_empower_greenroof

UNION ALL

-- Kissel source: same schema, just different source marker
SELECT
    id,
    timestamp,
    serial_no AS serial_number,
    sr1 AS global_radiation,
    air_temp_1 AS air_temperature,
    air_humidity_1 AS relative_humidity,
    wind_speed AS wind_speed_avg,
    wind_direction AS wind_direction_1,
    soil_temp_1 AS soil_temperature,
    soil_moisture,
    'kissel' AS source,
    file_name AS filename
FROM val_ingested_kissel_greenroof

ORDER BY timestamp ASC;
'''

INDEX_SQL = '''
CREATE INDEX IF NOT EXISTS idx_harm_greenroof_ts ON harm_greenroof(timestamp);
CREATE INDEX IF NOT EXISTS idx_harm_greenroof_ts_min ON harm_greenroof(date_trunc('minute', timestamp));
'''


def harmonize_greenroof():
    '''Combine both validated greenroof sources into canonical harm_greenroof table.'''
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('DROP TABLE IF EXISTS harm_greenroof;')
    cur.execute(HARM_SQL)
    cur.execute(INDEX_SQL)

    conn.commit()

    # Log result
    cur.execute('SELECT COUNT(*) FROM harm_greenroof;')
    count = cur.fetchone()[0]
    print(f'[harmonize_greenroof] Combined {count} greenroof records into canonical schema.')

    # Show source breakdown
    cur.execute('''
        SELECT source, COUNT(*) AS records
        FROM harm_greenroof
        GROUP BY 1;
    ''')
    for row in cur.fetchall():
        print(f'  {row[0]}: {row[1]} records')

    cur.close()
    conn.close()
