'''
Sync Sites - Synchronize greenroof and parkplatz data per minute.

Based on: synchronize+filter_data_code.py

Table naming convention for Bingen pipeline:
- Parkplatz source: val_ingested_parkplatz
- Greenroof source: harm_greenroof
- Outputs: harm_parkplatz, synchronized_data_filtered

Final output table: synchronized_data_filtered
- 24 columns total (see canonical columns documentation)
- Minute-level aggregation with AVG and ROUND(..., 3)
- HAVING filters for outlier removal
'''
from pipeline.ingest.base import get_connection


# Harmonize parkplatz to use quoted column names matching reference
# Reference uses: "IR1 [W/m2]", "Air Temp 1 [C]", etc.
HARM_PARKPLATZ_SQL = '''
CREATE TABLE IF NOT EXISTS harm_parkplatz AS
SELECT
    id,
    timestamp,
    ir1_wm2 AS "IR1 [W/m2]",
    sr1_wm2 AS "SR1 [W/m2]",
    ir2_wm2 AS "IR2 [W/m2]",
    sr2_wm2 AS "SR2 [W/m2]",
    temp_c AS "Temp [C]",
    air_pressure_mbar AS "Air Pressure [mbar]",
    soil_moisture_vol AS "Soil Moisture [vol%]",
    air_humidity_1_rh AS "Air Humidity 1 [%RH]",
    air_temp_1_c AS "Air Temp 1 [C]",
    air_humidity_2_rh AS "Air Humidity 2 [%RH]",
    air_temp_2_c AS "Air Temp 2 [C]",
    wind_speed_ms AS "Wind Speed [m/s]",
    wind_direction_deg AS "Wind Direction [deg]",
    soil_temp_1_c AS "Soil Temp 1 [C]",
    soil_temp_2_c AS "Soil Temp 2 [C]",
    serial_number
FROM val_ingested_parkplatz
ORDER BY timestamp ASC;
'''

# Synchronized data: minute-level aggregation matching reference exactly
# Output columns match synchronize+filter_data_code.py
SYNC_SQL = '''
CREATE TABLE IF NOT EXISTS synchronized_data_filtered AS
SELECT
    date_trunc('minute', g.timestamp) AS timestamp,

    -- Parkplatz sensor averages (15 columns)
    ROUND(AVG(p."IR1 [W/m2]"::numeric), 3) AS avg_ir1_parkplatz,
    ROUND(AVG(p."SR1 [W/m2]"::numeric), 3) AS avg_sr1_parkplatz,
    ROUND(AVG(p."IR2 [W/m2]"::numeric), 3) AS avg_ir2_parkplatz,
    ROUND(AVG(p."SR2 [W/m2]"::numeric), 3) AS avg_sr2_parkplatz,
    ROUND(AVG(p."Temp [C]"::numeric), 3) AS avg_temp_parkplatz,
    ROUND(AVG(p."Air Pressure [mbar]"::numeric), 3) AS avg_air_pressure_parkplatz,
    ROUND(AVG(p."Soil Moisture [vol%]"::numeric), 3) AS avg_soil_moisture_parkplatz,
    ROUND(AVG(p."Air Humidity 1 [%RH]"::numeric), 3) AS avg_air_humidity_1_parkplatz,
    ROUND(AVG(p."Air Temp 1 [C]"::numeric), 3) AS avg_air_temp_1_parkplatz,
    ROUND(AVG(p."Air Humidity 2 [%RH]"::numeric), 3) AS avg_air_humidity_2_parkplatz,
    ROUND(AVG(p."Air Temp 2 [C]"::numeric), 3) AS avg_air_temp_2_parkplatz,
    ROUND(AVG(p."Wind Speed [m/s]"::numeric), 3) AS avg_wind_speed_parkplatz,
    ROUND(AVG(p."Wind Direction [deg]"::numeric), 3) AS avg_wind_direction_parkplatz,
    ROUND(AVG(p."Soil Temp 1 [C]"::numeric), 3) AS avg_soil_temp_1_parkplatz,
    ROUND(AVG(p."Soil Temp 2 [C]"::numeric), 3) AS avg_soil_temp_2_parkplatz,

    -- Greenroof sensor averages (6 columns)
    ROUND(AVG(g.air_temperature::numeric), 3) AS avg_air_temperature_greenroof,
    ROUND(AVG(g.relative_humidity::numeric), 3) AS avg_relative_humidity_greenroof,
    ROUND(AVG(g.wind_speed_avg::numeric), 3) AS avg_wind_speed_greenroof,
    ROUND(AVG(g.soil_temperature::numeric), 3) AS avg_soil_temperature_greenroof,
    ROUND(AVG(g.soil_moisture::numeric), 3) AS avg_soil_moisture_greenroof,
    ROUND(AVG(g.global_radiation::numeric), 3) AS avg_global_radiation_greenroof,

    -- Record counts for quality assessment
    COUNT(p.id) AS parkplatz_record_count,
    COUNT(g.id) AS greenroof_record_count,

    -- Computed columns: Temperature differences (cooling effect indicators)
    ROUND(AVG(g.air_temperature::numeric) - AVG(p."Air Temp 1 [C]"::numeric), 3) AS temp_diff_1,
    ROUND(AVG(g.air_temperature::numeric) - AVG(p."Air Temp 2 [C]"::numeric), 3) AS temp_diff_2,

    -- Computed columns: Energy calculations (Stefan-Boltzmann: σ=5.67e-8, ε=0.95)
    ROUND(AVG(p."IR1 [W/m2]"::numeric) + POWER(AVG(p."Temp [C]"::numeric) + 273.15, 4) * 5.67e-8 * 0.95, 3) AS energy_from_air_parkplatz,
    ROUND(AVG(p."IR2 [W/m2]"::numeric) + POWER(AVG(p."Temp [C]"::numeric) + 273.15, 4) * 5.67e-8 * 0.95, 3) AS energy_from_surface_parkplatz,

    -- Computed column: Radiation balance (net radiation)
    ROUND(AVG(p."SR1 [W/m2]"::numeric) - AVG(p."SR2 [W/m2]"::numeric) + AVG(p."IR1 [W/m2]"::numeric) - AVG(p."IR2 [W/m2]"::numeric), 3) AS radiation_balance_parkplatz

FROM harm_greenroof g
INNER JOIN harm_parkplatz p
    ON date_trunc('minute', g.timestamp) = date_trunc('minute', p.timestamp)

GROUP BY date_trunc('minute', g.timestamp)

-- INTEGRATED FILTERING LOGIC from synchronize+filter_data_code.py
HAVING
    -- Temperature filters (custom ranges)
    (ROUND(AVG(g.air_temperature::numeric), 3) IS NULL OR (ROUND(AVG(g.air_temperature::numeric), 3) >= -25.0 AND ROUND(AVG(g.air_temperature::numeric), 3) <= 45.0))
    AND (ROUND(AVG(p."Air Temp 1 [C]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Air Temp 1 [C]"::numeric), 3) >= -25.0 AND ROUND(AVG(p."Air Temp 1 [C]"::numeric), 3) <= 45.0))
    AND (ROUND(AVG(p."Air Temp 2 [C]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Air Temp 2 [C]"::numeric), 3) >= -25.0 AND ROUND(AVG(p."Air Temp 2 [C]"::numeric), 3) <= 45.0))
    AND (ROUND(AVG(p."Temp [C]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Temp [C]"::numeric), 3) >= -25.0 AND ROUND(AVG(p."Temp [C]"::numeric), 3) <= 45.0))
    AND (ROUND(AVG(g.soil_temperature::numeric), 3) IS NULL OR (ROUND(AVG(g.soil_temperature::numeric), 3) >= -20.0 AND ROUND(AVG(g.soil_temperature::numeric), 3) <= 50.0))
    AND (ROUND(AVG(p."Soil Temp 1 [C]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Soil Temp 1 [C]"::numeric), 3) >= -20.0 AND ROUND(AVG(p."Soil Temp 1 [C]"::numeric), 3) <= 50.0))
    AND (ROUND(AVG(p."Soil Temp 2 [C]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Soil Temp 2 [C]"::numeric), 3) >= -20.0 AND ROUND(AVG(p."Soil Temp 2 [C]"::numeric), 3) <= 50.0))

    -- Humidity filters (custom ranges)
    AND (ROUND(AVG(g.relative_humidity::numeric), 3) IS NULL OR (ROUND(AVG(g.relative_humidity::numeric), 3) >= 0.0 AND ROUND(AVG(g.relative_humidity::numeric), 3) <= 100.0))
    AND (ROUND(AVG(p."Air Humidity 1 [%RH]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Air Humidity 1 [%RH]"::numeric), 3) >= 0.0 AND ROUND(AVG(p."Air Humidity 1 [%RH]"::numeric), 3) <= 100.0))
    AND (ROUND(AVG(p."Air Humidity 2 [%RH]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Air Humidity 2 [%RH]"::numeric), 3) >= 0.0 AND ROUND(AVG(p."Air Humidity 2 [%RH]"::numeric), 3) <= 100.0))

    -- Wind speed filters (custom ranges)
    AND (ROUND(AVG(g.wind_speed_avg::numeric), 3) IS NULL OR (ROUND(AVG(g.wind_speed_avg::numeric), 3) >= 0.0 AND ROUND(AVG(g.wind_speed_avg::numeric), 3) <= 50.0))
    AND (ROUND(AVG(p."Wind Speed [m/s]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Wind Speed [m/s]"::numeric), 3) >= 0.0 AND ROUND(AVG(p."Wind Speed [m/s]"::numeric), 3) <= 40.0))

    -- Soil moisture filters (custom ranges)
    AND (ROUND(AVG(g.soil_moisture::numeric), 3) IS NULL OR (ROUND(AVG(g.soil_moisture::numeric), 3) >= 0.0 AND ROUND(AVG(g.soil_moisture::numeric), 3) <= 60.0))
    AND (ROUND(AVG(p."Soil Moisture [vol%]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Soil Moisture [vol%]"::numeric), 3) >= 0.0 AND ROUND(AVG(p."Soil Moisture [vol%]"::numeric), 3) <= 60.0))

    -- Pressure filter (custom range)
    AND (ROUND(AVG(p."Air Pressure [mbar]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Air Pressure [mbar]"::numeric), 3) >= 700.0 AND ROUND(AVG(p."Air Pressure [mbar]"::numeric), 3) <= 1500.0))

ORDER BY timestamp ASC;
'''

INDEX_SYNC_SQL = '''
CREATE INDEX IF NOT EXISTS idx_sync_filtered_timestamp ON synchronized_data_filtered(timestamp);
'''

INDEX_HARM_PARKPLATZ_SQL = '''
CREATE INDEX IF NOT EXISTS idx_harm_parkplatz_ts ON harm_parkplatz(timestamp);
CREATE INDEX IF NOT EXISTS idx_harm_parkplatz_ts_min ON harm_parkplatz(date_trunc('minute', timestamp));
'''


def harmonize_parkplatz():
    '''Harmonize parkplatz to quoted column names matching reference.'''
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('DROP TABLE IF EXISTS harm_parkplatz;')
    cur.execute(HARM_PARKPLATZ_SQL)
    cur.execute(INDEX_HARM_PARKPLATZ_SQL)

    conn.commit()

    cur.execute('SELECT COUNT(*) FROM harm_parkplatz;')
    count = cur.fetchone()[0]
    print(f'[harmonize_parkplatz] Harmonized {count} parkplatz records.')

    cur.close()
    conn.close()


def sync_data():
    '''Synchronize greenroof and parkplatz data per minute with production filters.'''
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('DROP TABLE IF EXISTS synchronized_data_filtered;')
    cur.execute(SYNC_SQL)
    cur.execute(INDEX_SYNC_SQL)

    conn.commit()

    cur.execute('SELECT COUNT(*) FROM synchronized_data_filtered;')
    count = cur.fetchone()[0]
    print(f'[sync_data] Synchronized {count} minute-level records.')

    # Show data quality summary
    cur.execute('''
    SELECT
        MIN(timestamp) AS earliest,
        MAX(timestamp) AS latest,
        COUNT(*) AS total_minutes
    FROM synchronized_data_filtered;
    ''')
    summary = cur.fetchone()
    if summary:
        print(f'  Earliest: {summary[0]}')
        print(f'  Latest: {summary[1]}')
        print(f'  Total minutes: {summary[2]}')

    cur.close()
    conn.close()
