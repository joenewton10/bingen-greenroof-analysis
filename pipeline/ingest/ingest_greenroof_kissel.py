"""
Ingest Raw/Kissel greenroof CSV files (MXmini format) into Bingen_Greenroof_DB.
Table: ingested_kissel_greenroof

Based on: actual file analysis of 081000388_*.csv

File format:
- Line 0: Station Name;[value]
- Line 1: Station ID;[value]
- Line 2: Serial No;[value]
- Line 3: Timezone;[value]
- Line 4: ; (empty)
- Line 5: Header row with sensor names like 'MXmini.Spannungsversorgung...'
- Line 6: Units row (V;mm;m/s;...)
- Line 7+: Data rows

Data format:
- ISO datetime (first column): YYYY-MM-DD HH:MM:SS
- German decimals: comma separator (12,67)
- Semicolon delimited
- 'nan' for missing values

Actual columns discovered (081000388 file):
0: Timestamp
1: MXmini.Spannungsversorgung Vin 4.1 (V) - battery voltage
2: MXmini.Niederschlag 4.1 (mm) - precipitation
3: Arco SDI-12.Windstaerke AVG (m/s) - wind speed avg
4: Arco SDI-12.Windstaerke MAX (m/s)
5: Arco SDI-12.Windstaerke MIN (m/s)
6: Arco SDI-12.Windrichtung (deg) - wind direction
7: Arco SDI-12.Windrichtung (deg)
8: Arco SDI-12.Windrichtung (deg)
9: Lambrecht 1.4.Lufttemperatur (C) - air temp
10: Lambrecht 1.4.Lufttemperatur MAX (C)
11: Lambrecht 1.4.Lufttemperatur MIN (C)
12: Lambrecht 1.4.Relative Feuchte (%) - air humidity
13: Lambrecht 1.4.Relative Feuchte MAX (%)
14: Lambrecht 1.4.Relative Feuchte MIN (%)
15: Lambrecht 1.10.Globalstrahlung (W/m2) - solar radiation
16: Lambrecht 1.10.Globalstrahlung MAX (W/m2)
17: Lambrecht 1.10.Globalstrahlung MIN (W/m2)
18: SMT100.2.1.Bodentemperatur (C) - soil temp
19: SMT100.2.1.Bodenfeuchte (vol%) - soil moisture
20: SMT100.2.1.Permittivitaet
21: Virtual.Bodenfeuchte_korregiert (vol%)
"""
import os
from datetime import datetime
from pipeline.ingest.base import get_connection
from config.settings import GREENROOF_DIR


DROP_SQL = 'DROP TABLE IF EXISTS ingested_kissel_greenroof CASCADE;'

CREATE_SQL = '''
CREATE TABLE IF NOT EXISTS ingested_kissel_greenroof (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    serial_no TEXT,

    -- Radiation measurements (using sr1 for global radiation)
    ir1 NUMERIC,
    sr1 NUMERIC,
    ir2 NUMERIC,
    sr2 NUMERIC,

    -- Temperature & pressure
    temperature NUMERIC,
    air_pressure NUMERIC,

    -- Soil
    soil_moisture NUMERIC,
    soil_temp_1 NUMERIC,
    soil_temp_2 NUMERIC,

    -- Air sensors (pair 1)
    air_humidity_1 NUMERIC,
    air_temp_1 NUMERIC,

    -- Air sensors (pair 2)
    air_humidity_2 NUMERIC,
    air_temp_2 NUMERIC,

    -- Wind
    wind_speed NUMERIC,
    wind_direction NUMERIC,

    -- Source tracking
    file_name TEXT
);
'''


def is_kissel_greenroof_file(file_path):
    '''Check if file is Raw/Kissel format (Station Name header + MXmini sensors).'''
    try:
        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
            lines = [f.readline() for _ in range(7)]

        # Check if starts with Station Name (Raw/Kissel format)
        if lines[0].strip().lower().startswith('station name'):
            return True

        # Also check if line 5 contains MXmini sensor names
        if len(lines) >= 6:
            header_line = lines[5].lower()
            if 'mxmini' in header_line:
                return True

        return False
    except Exception:
        return False


def extract_serial_from_kissel(file_path):
    '''Extract serial number from line 2 (Serial No;value).'''
    try:
        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
            for i, line in enumerate(f):
                if i == 2:  # Serial No line
                    parts = line.strip().split(';')
                    if len(parts) >= 2:
                        return parts[1].strip()
                if i > 3:
                    break
    except Exception:
        pass
    return 'KISSEL_UNKNOWN'


def parse_german_float(value):
    '''Parse German formatted numbers (comma decimal), handle 'nan'.'''
    if value is None:
        return None
    s = str(value).strip()
    if s == '' or s.lower() == 'nan':
        return None
    try:
        # Replace comma with decimal point
        return float(s.replace(' ', '').replace(',', '.'))
    except (ValueError, AttributeError):
        return None


def parse_datetime_iso(date_str):
    '''Parse ISO datetime: YYYY-MM-DD HH:MM:SS (used in Raw/Kissel files).'''
    if not date_str:
        return None
    s = str(date_str).strip()
    if s == '':
        return None

    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def ingest_kissel_greenroof():
    '''Ingest Raw/Kissel (MXmini) greenroof CSVs using positional column mapping.'''
    conn = get_connection()
    cur = conn.cursor()
    print('[ingest_kissel_greenroof] Dropping existing table...')
    cur.execute(DROP_SQL)
    cur.execute(CREATE_SQL)

    if not os.path.isdir(GREENROOF_DIR):
        print(f'[ingest_kissel_greenroof] Directory not found: {GREENROOF_DIR}')
        conn.commit()
        cur.close()
        conn.close()
        return

    # Recursively find all CSV files in all subfolders
    files = []
    for root, dirs, filenames in os.walk(GREENROOF_DIR):
        for f in filenames:
            if f.lower().endswith('.csv'):
                files.append(os.path.join(root, f))

    print(f'[ingest_kissel_greenroof] Found {len(files)} CSV files to scan')
    imported_total = 0

    for path in files:
        file = os.path.basename(path)

        # Validate file format - must be Kissel type
        if not is_kissel_greenroof_file(path):
            continue

        try:
            with open(path, 'r', encoding='latin-1', errors='ignore') as f:
                lines = f.readlines()

            if len(lines) < 8:  # Need at least header + units + 1 data row
                print(f'[ingest_kissel_greenroof] File too short: {file}')
                continue

            serial_no = extract_serial_from_kissel(path)

            # Data starts at line 7 (skip metadata 0-4, header 5, units 6)
            data_start = 7
            rows_imported = 0

            for line_num, line in enumerate(lines[data_start:], start=data_start):
                line = line.strip()
                if not line:
                    continue

                row = [cell.strip() for cell in line.split(';')]

                # Skip rows that don't have enough columns (need at least timestamp + some data)
                if len(row) < 10:
                    continue

                # POSITIONAL column mapping based on discovered format:
                # 0: Timestamp
                timestamp = parse_datetime_iso(row[0])

                if timestamp is None:
                    continue

                # 1: Battery voltage (skip - not in target schema)
                # 2: Precipitation (skip - not in target schema)

                # 3-5: Wind speed AVG/MAX/MIN - use AVG
                wind_speed = parse_german_float(row[3]) if len(row) > 3 else None

                # 6-8: Wind direction (3 columns) - use first
                wind_direction = parse_german_float(row[6]) if len(row) > 6 else None

                # 9-11: Air temperature AVG/MAX/MIN - use AVG
                air_temp_1 = parse_german_float(row[9]) if len(row) > 9 else None

                # 12-14: Relative humidity AVG/MAX/MIN - use AVG
                air_humidity_1 = parse_german_float(row[12]) if len(row) > 12 else None

                # 15-17: Global radiation AVG/MAX/MIN - map to sr1
                sr1 = parse_german_float(row[15]) if len(row) > 15 else None

                # 18: Soil temperature
                soil_temp_1 = parse_german_float(row[18]) if len(row) > 18 else None

                # 19: Soil moisture
                soil_moisture = parse_german_float(row[19]) if len(row) > 19 else None

                # Fields not in Kissel files - set to None
                ir1 = None
                ir2 = None
                sr2 = None
                temperature = None
                air_pressure = None
                soil_temp_2 = None
                air_humidity_2 = None
                air_temp_2 = None

                cur.execute('''
                    INSERT INTO ingested_kissel_greenroof (
                        timestamp, serial_no,
                        ir1, sr1, ir2, sr2,
                        temperature, air_pressure,
                        soil_moisture, soil_temp_1, soil_temp_2,
                        air_humidity_1, air_temp_1, air_humidity_2, air_temp_2,
                        wind_speed, wind_direction,
                        file_name
                    ) VALUES (
                        %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s
                    )
                ''', (
                    timestamp, serial_no,
                    ir1, sr1, ir2, sr2,
                    temperature, air_pressure,
                    soil_moisture, soil_temp_1, soil_temp_2,
                    air_humidity_1, air_temp_1, air_humidity_2, air_temp_2,
                    wind_speed, wind_direction,
                    file
                ))
                rows_imported += 1

            imported_total += rows_imported
            print(f'[ingest_kissel_greenroof] {file}: {rows_imported} rows')

        except Exception as e:
            print(f'[ingest_kissel_greenroof] Error in {file}: {e}')
            import traceback
            traceback.print_exc()
            continue

    conn.commit()
    print(f'[ingest_kissel_greenroof] Total: {imported_total} rows ingested.')
    
    # Create index for efficient timestamp ordering
    print('[ingest_kissel_greenroof] Creating timestamp index...')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_ingested_kissel_greenroof_ts ON ingested_kissel_greenroof(timestamp ASC);')
    conn.commit()
    
    cur.close()
    conn.close()
