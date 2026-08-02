'''
Sync Sites - Synchronize greenroof and parkplatz data per minute.

Based on: synchronize+filter_data_code.py

Table naming convention for Bingen pipeline:
- Parkplatz source: harm_parkplatz
- Greenroof source: harm_greenroof
- Output: synchronized_data_filtered

Final output table: synchronized_data_filtered
- Includes dual-level availability flags and thesis-derived metrics
- Minute-level aggregation with AVG and ROUND(..., 3)
- HAVING filters for outlier removal
'''
import time
from pipeline.ingest.base import get_connection

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

    -- Greenroof sensor averages
    ROUND(AVG(g.ir1_in_lw::numeric), 3) AS avg_ir1_greenroof,
    ROUND(AVG(g.air_temperature::numeric), 3) AS avg_air_temperature_greenroof,
    ROUND(AVG(g.air_temp_2::numeric), 3) AS avg_air_temp_2_greenroof,
    ROUND(AVG(g.relative_humidity::numeric), 3) AS avg_air_humidity_1_greenroof,
    ROUND(AVG(g.air_humidity_2::numeric), 3) AS avg_air_humidity_2_greenroof,
    ROUND(AVG(g.wind_speed_avg::numeric), 3) AS avg_wind_speed_greenroof,
    ROUND(AVG(g.soil_temperature::numeric), 3) AS avg_soil_temperature_greenroof,
    ROUND(AVG(g.soil_moisture::numeric), 3) AS avg_soil_moisture_greenroof,
    ROUND(AVG(g.sr1_in_sw::numeric), 3) AS avg_global_radiation_greenroof,
    ROUND(AVG(g.sr2_ref_sw::numeric), 3) AS avg_sr2_greenroof,
    ROUND(AVG(g.ir2_out_lw::numeric), 3) AS avg_ir2_greenroof,

    -- Record counts for quality assessment
    COUNT(p.id) AS parkplatz_record_count,
    COUNT(g.id) AS greenroof_record_count,

    -- Data availability: dual-level instrumentation on greenroof
    (AVG(g.air_temp_2::numeric) IS NOT NULL AND AVG(g.air_humidity_2::numeric) IS NOT NULL) AS has_dual_level_greenroof,
    CASE
        WHEN AVG(g.air_temp_2::numeric) IS NOT NULL AND AVG(g.air_humidity_2::numeric) IS NOT NULL THEN 'dual_level'
        ELSE 'single_level'
    END AS measurement_period,

    -- Computed columns: Temperature differences (cooling effect indicators)
    ROUND(AVG(g.air_temperature::numeric) - AVG(p."Air Temp 1 [C]"::numeric), 3) AS temp_diff_1,
    ROUND(AVG(g.air_temperature::numeric) - AVG(p."Air Temp 2 [C]"::numeric), 3) AS temp_diff_2,
    ROUND(AVG(g.air_temperature::numeric) - AVG(g.air_temp_2::numeric), 3) AS delta_t_roof,
    ROUND(AVG(g.relative_humidity::numeric) - AVG(g.air_humidity_2::numeric), 3) AS delta_rh_roof,
    ROUND(AVG(p."Air Temp 1 [C]"::numeric) - AVG(p."Air Temp 2 [C]"::numeric), 3) AS delta_t_parkplatz,
    ROUND(AVG(p."Air Humidity 1 [%RH]"::numeric) - AVG(p."Air Humidity 2 [%RH]"::numeric), 3) AS delta_rh_parkplatz,

    -- Computed columns: Energy calculations (Stefan-Boltzmann: σ=5.67e-8, ε=0.95)
    ROUND(AVG(p."IR1 [W/m2]"::numeric) + POWER(AVG(p."Temp [C]"::numeric) + 273.15, 4) * 5.67e-8 * 0.95, 3) AS energy_from_air_parkplatz,
    ROUND(AVG(p."IR2 [W/m2]"::numeric) + POWER(AVG(p."Temp [C]"::numeric) + 273.15, 4) * 5.67e-8 * 0.95, 3) AS energy_from_surface_parkplatz,

    -- Computed columns: Radiation balance and albedo
    ROUND(AVG(g.sr1_in_sw::numeric) - AVG(g.sr2_ref_sw::numeric) + AVG(g.ir1_in_lw::numeric) - AVG(g.ir2_out_lw::numeric), 3) AS radiation_balance_greenroof,
    ROUND(AVG(p."SR1 [W/m2]"::numeric) - AVG(p."SR2 [W/m2]"::numeric) + AVG(p."IR1 [W/m2]"::numeric) - AVG(p."IR2 [W/m2]"::numeric), 3) AS radiation_balance_parkplatz,
    ROUND(
        AVG(g.sr2_ref_sw::numeric)
        / NULLIF(CASE WHEN AVG(g.sr1_in_sw::numeric) >= 10 THEN AVG(g.sr1_in_sw::numeric) END, 0),
        4
    ) AS albedo_greenroof,
    ROUND(
        AVG(p."SR2 [W/m2]"::numeric)
        / NULLIF(CASE WHEN AVG(p."SR1 [W/m2]"::numeric) >= 10 THEN AVG(p."SR1 [W/m2]"::numeric) END, 0),
        4
    ) AS albedo_parkplatz,

    -- Computed columns: specific humidity (Magnus over water, Bingen pressure p = 1002 hPa, q in g/kg)
    -- e_s(T) = 6.112 * exp(17.62 * T / (243.12 + T))  [hPa]
    -- e      = (RH/100) * e_s
    -- q      = 0.622 * e / (p - 0.378 * e)  [kg/kg], multiplied by 1000 -> g/kg
    -- Reference: WMO No. 8 (Annex 4.B); Alduchov & Eskridge (1996); Allen et al. (1998) FAO-56
    ROUND(
        (0.622 * (AVG(g.relative_humidity::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(g.air_temperature::numeric) / (243.12 + AVG(g.air_temperature::numeric))))
        / (1002.0 - 0.378 * (AVG(g.relative_humidity::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(g.air_temperature::numeric) / (243.12 + AVG(g.air_temperature::numeric))))
        * 1000.0,
        4
    ) AS q_greenroof_50cm,
    ROUND(
        (0.622 * (AVG(g.air_humidity_2::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(g.air_temp_2::numeric) / (243.12 + AVG(g.air_temp_2::numeric))))
        / (1002.0 - 0.378 * (AVG(g.air_humidity_2::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(g.air_temp_2::numeric) / (243.12 + AVG(g.air_temp_2::numeric))))
        * 1000.0,
        4
    ) AS q_greenroof_2m,
    ROUND(
        (0.622 * (AVG(p."Air Humidity 1 [%RH]"::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(p."Air Temp 1 [C]"::numeric) / (243.12 + AVG(p."Air Temp 1 [C]"::numeric))))
        / (1002.0 - 0.378 * (AVG(p."Air Humidity 1 [%RH]"::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(p."Air Temp 1 [C]"::numeric) / (243.12 + AVG(p."Air Temp 1 [C]"::numeric))))
        * 1000.0,
        4
    ) AS q_parkplatz_50cm,
    ROUND(
        (0.622 * (AVG(p."Air Humidity 2 [%RH]"::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(p."Air Temp 2 [C]"::numeric) / (243.12 + AVG(p."Air Temp 2 [C]"::numeric))))
        / (1002.0 - 0.378 * (AVG(p."Air Humidity 2 [%RH]"::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(p."Air Temp 2 [C]"::numeric) / (243.12 + AVG(p."Air Temp 2 [C]"::numeric))))
        * 1000.0,
        4
    ) AS q_parkplatz_2m,
    -- Specific-humidity gradient delta_q = q_50cm - q_2m  (g/kg); positive = moister near surface
    -- Roof delta_q is only physically meaningful when has_dual_level_greenroof = TRUE (Jan 2024 onwards)
    ROUND(
        ((0.622 * (AVG(g.relative_humidity::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(g.air_temperature::numeric) / (243.12 + AVG(g.air_temperature::numeric))))
         / (1002.0 - 0.378 * (AVG(g.relative_humidity::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(g.air_temperature::numeric) / (243.12 + AVG(g.air_temperature::numeric))))
         * 1000.0)
        -
        ((0.622 * (AVG(g.air_humidity_2::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(g.air_temp_2::numeric) / (243.12 + AVG(g.air_temp_2::numeric))))
         / (1002.0 - 0.378 * (AVG(g.air_humidity_2::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(g.air_temp_2::numeric) / (243.12 + AVG(g.air_temp_2::numeric))))
         * 1000.0),
        4
    ) AS delta_q_roof,
    ROUND(
        ((0.622 * (AVG(p."Air Humidity 1 [%RH]"::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(p."Air Temp 1 [C]"::numeric) / (243.12 + AVG(p."Air Temp 1 [C]"::numeric))))
         / (1002.0 - 0.378 * (AVG(p."Air Humidity 1 [%RH]"::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(p."Air Temp 1 [C]"::numeric) / (243.12 + AVG(p."Air Temp 1 [C]"::numeric))))
         * 1000.0)
        -
        ((0.622 * (AVG(p."Air Humidity 2 [%RH]"::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(p."Air Temp 2 [C]"::numeric) / (243.12 + AVG(p."Air Temp 2 [C]"::numeric))))
         / (1002.0 - 0.378 * (AVG(p."Air Humidity 2 [%RH]"::numeric)/100.0)
            * 6.112 * exp(17.62 * AVG(p."Air Temp 2 [C]"::numeric) / (243.12 + AVG(p."Air Temp 2 [C]"::numeric))))
         * 1000.0),
        4
    ) AS delta_q_parkplatz

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
    AND (ROUND(AVG(g.soil_temperature::numeric), 3) IS NULL OR (ROUND(AVG(g.soil_temperature::numeric), 3) >= -20.0 AND ROUND(AVG(g.soil_temperature::numeric), 3) <= 70.0))
    AND (ROUND(AVG(p."Soil Temp 1 [C]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Soil Temp 1 [C]"::numeric), 3) >= -20.0 AND ROUND(AVG(p."Soil Temp 1 [C]"::numeric), 3) <= 70.0))
    AND (ROUND(AVG(p."Soil Temp 2 [C]"::numeric), 3) IS NULL OR (ROUND(AVG(p."Soil Temp 2 [C]"::numeric), 3) >= -20.0 AND ROUND(AVG(p."Soil Temp 2 [C]"::numeric), 3) <= 70.0))

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


def sync_data():
    '''Synchronize greenroof and parkplatz data per minute with production filters.'''
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('DROP TABLE IF EXISTS synchronized_data_filtered;')
    print('[sync_data] Joining greenroof + parkplatz per minute (this may take a while)...', flush=True)
    t0 = time.time()
    cur.execute(SYNC_SQL)
    cur.execute(INDEX_SYNC_SQL)
    cur.execute('CLUSTER synchronized_data_filtered USING idx_sync_filtered_timestamp;')
    cur.execute('ANALYZE synchronized_data_filtered;')

    conn.commit()

    cur.execute('SELECT COUNT(*) FROM synchronized_data_filtered;')
    count = cur.fetchone()[0]
    print(f'[sync_data] Synchronized {count} minute-level records ({time.time() - t0:.1f}s)')

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
