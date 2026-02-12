"""
Ingest Empower-Gruendach greenroof CSV files into Bingen_Greenroof_DB.
Table: ingested_empower_greenroof

Based on: empower_greenroof_code.py

SIMPLIFIED SCHEMA - Dropped columns:
- Device metadata (device_type, device_name, description, device_number, location_name, location_number)
- Rain/counters (counter_1, rain_abs, counter_diff, rain_rel, count_duration)
- System (battery_voltage, internal_temp, alarm_level, field_strength)
- Import tracking (source_directory, import_timestamp)

KEPT columns (17 total):
- id, timestamp, serial_no
- ir1, sr1, ir2, sr2 (radiation)
- temperature, air_pressure
- soil_moisture, soil_temp_1, soil_temp_2
- air_humidity_1, air_temp_1, air_humidity_2, air_temp_2
- wind_speed, wind_direction
- file_name
"""
import os
from datetime import datetime
from pipeline.ingest.base import get_connection
from config.settings import GREENROOF_DIR


DROP_SQL = 'DROP TABLE IF EXISTS ingested_empower_greenroof CASCADE;'

CREATE_SQL = '''
CREATE TABLE IF NOT EXISTS ingested_empower_greenroof (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    serial_no TEXT,

    -- Radiation measurements
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


def is_empower_greenroof_file(file_path):
    '''Verify file is Empower greenroof format (starts with Geraetetyp or ONLINEMESSUNG).'''
    try:
        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
            first_line = f.readline().strip()
        return first_line.startswith('Geraetetyp') or first_line.startswith('ONLINEMESSUNG')
    except Exception:
        return False


def parse_german_float(value):
    '''Parse German formatted numbers (comma decimal, spaces).'''
    if value is None:
        return None
    s = str(value).strip()
    if s == '' or s.upper() == 'NAN':
        return None
    try:
        return float(s.replace(' ', '').replace(',', '.'))
    except (ValueError, AttributeError):
        return None


def parse_datetime_german(date_str):
    '''Parse German datetime: DD.MM.YY HH:MM:SS or DD.MM.YYYY HH:MM:SS'''
    if not date_str:
        return None
    s = str(date_str).strip()
    if s == '':
        return None
    for fmt in ('%d.%m.%y %H:%M:%S', '%d.%m.%Y %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def extract_serial_number(file_path):
    '''Extract serial number from header lines.'''
    try:
        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
            first_line = f.readline().strip()

            # Online format uses default serial
            if first_line.startswith('ONLINEMESSUNG'):
                return 'A27212'

            # Regular format - find Seriennummer line
            f.seek(0)
            for _ in range(16):
                line = f.readline()
                if not line:
                    break
                if ';' in line:
                    parts = line.split(';')
                    if len(parts) >= 2 and 'Seriennummer' in parts[0]:
                        return parts[1].strip()
    except Exception:
        pass
    return None


def ingest_empower_greenroof():
    '''Ingest Empower-Gruendach CSVs using positional column mapping.'''
    conn = get_connection()
    cur = conn.cursor()
    print('[ingest_empower_greenroof] Dropping existing table...')
    cur.execute(DROP_SQL)
    cur.execute(CREATE_SQL)

    if not os.path.isdir(GREENROOF_DIR):
        print(f'[ingest_empower_greenroof] Directory not found: {GREENROOF_DIR}')
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

    print(f'[ingest_empower_greenroof] Found {len(files)} CSV files to scan')
    imported_total = 0

    for path in files:
        file = os.path.basename(path)

        # Validate file format - must be Empower type
        if not is_empower_greenroof_file(path):
            continue

        try:
            with open(path, 'r', encoding='latin-1', errors='ignore') as f:
                lines = f.readlines()

            if len(lines) < 18:
                print(f'[ingest_empower_greenroof] File too short: {file}')
                continue

            # Extract serial number
            serial_no = extract_serial_number(path)

            # Find header line (Nr.;Datum)
            header_line_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith('Nr.;Datum') or ('Nr.;' in line and 'Datum' in line):
                    header_line_idx = i
                    break

            if header_line_idx is None:
                print(f'[ingest_empower_greenroof] No header found in {file}')
                continue

            # Process data rows
            data_start = header_line_idx + 1
            rows_imported = 0

            for line in lines[data_start:]:
                if not line.strip():
                    continue

                row = [cell.strip() for cell in line.strip().split(';')]

                # Validate: need enough columns and first must be record number
                if len(row) < 25 or not row[0].isdigit():
                    continue

                # POSITIONAL column mapping (matching empower_greenroof_code.py)
                timestamp = parse_datetime_german(row[1]) if len(row) > 1 else None

                if timestamp is None:
                    continue

                ir1 = parse_german_float(row[2]) if len(row) > 2 else None
                sr1 = parse_german_float(row[3]) if len(row) > 3 else None
                ir2 = parse_german_float(row[4]) if len(row) > 4 else None
                sr2 = parse_german_float(row[5]) if len(row) > 5 else None
                temperature = parse_german_float(row[6]) if len(row) > 6 else None
                air_pressure = parse_german_float(row[7]) if len(row) > 7 else None
                soil_moisture = parse_german_float(row[8]) if len(row) > 8 else None
                air_humidity_1 = parse_german_float(row[9]) if len(row) > 9 else None
                air_temp_1 = parse_german_float(row[10]) if len(row) > 10 else None
                air_humidity_2 = parse_german_float(row[11]) if len(row) > 11 else None
                air_temp_2 = parse_german_float(row[12]) if len(row) > 12 else None
                wind_speed = parse_german_float(row[13]) if len(row) > 13 else None
                wind_direction = parse_german_float(row[14]) if len(row) > 14 else None
                soil_temp_1 = parse_german_float(row[15]) if len(row) > 15 else None
                soil_temp_2 = parse_german_float(row[16]) if len(row) > 16 else None

                cur.execute('''
                    INSERT INTO ingested_empower_greenroof (
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
            print(f'[ingest_empower_greenroof] {file}: {rows_imported} rows')

        except Exception as e:
            print(f'[ingest_empower_greenroof] Error in {file}: {e}')
            continue

    conn.commit()
    print(f'[ingest_empower_greenroof] Total: {imported_total} rows ingested.')
    
    # Create index for efficient timestamp ordering
    print('[ingest_empower_greenroof] Creating timestamp index...')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_ingested_empower_greenroof_ts ON ingested_empower_greenroof(timestamp ASC);')
    conn.commit()
    
    cur.close()
    conn.close()
