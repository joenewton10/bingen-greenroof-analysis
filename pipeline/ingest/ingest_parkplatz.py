"""
Ingest Parkplatz CSV files into ingested_parkplatz table.
Based on: parkplatz_code_combine.py

Table naming convention for Bingen pipeline:
- Output: ingested_parkplatz

Handles BOTH Empower and Kissel Parkplatz formats:
- Empower: 27 columns, clean German decimals
- Kissel: 54 columns with Min/Max, corrupted numeric format (-83,511,000)

Key features ported from parkplatz_code_combine.py:
- find_data_start() - finds semicolon divider or Nr.;Datum header
- convert_column_numeric() - handles corrupt comma format (first comma = decimal)
- normalize_scales() - detects 1000x multiplication issues
- Header translation from German to English
- Min/Max column support
"""
import os
import re
import csv
import gc
from datetime import datetime
import pandas as pd
import numpy as np
from pipeline.ingest.base import get_connection
from config.settings import PARKPLATZ_DIR


# --- FINAL COLUMN SET ---
FINAL_COLS = [
    'No.', 'Date / Time', 'IR1 [W/m2]', 'IR1 Min [W/m2]', 'IR1 Max [W/m2]',
    'SR1 [W/m2]', 'SR1 Min [W/m2]', 'SR1 Max [W/m2]', 'IR2 [W/m2]', 'IR2 Min [W/m2]', 'IR2 Max [W/m2]',
    'SR2 [W/m2]', 'SR2 Min [W/m2]', 'SR2 Max [W/m2]', 'Temp [C]', 'Temp Min [C]', 'Temp Max [C]',
    'Air Pressure [mbar]', 'Air Pressure Min [mbar]', 'Air Pressure Max [mbar]',
    'Soil Moisture [vol%]', 'Soil Moisture Min [vol%]', 'Soil Moisture Max [vol%]',
    'Air Humidity 1 [%RH]', 'Air Humidity 1 Min [%RH]', 'Air Humidity 1 Max [%RH]',
    'Air Temp 1 [C]', 'Air Temp 1 Min [C]', 'Air Temp 1 Max [C]',
    'Air Humidity 2 [%RH]', 'Air Humidity 2 Min [%RH]', 'Air Humidity 2 Max [%RH]',
    'Air Temp 2 [C]', 'Air Temp 2 Min [C]', 'Air Temp 2 Max [C]',
    'Wind Speed [m/s]', 'Wind Speed Min [m/s]', 'Wind Speed Max [m/s]',
    'Wind Direction [deg]', 'Wind Direction Min [deg]', 'Wind Direction Max [deg]',
    'Soil Temp 1 [C]', 'Soil Temp 1 Min [C]', 'Soil Temp 1 Max [C]',
    'Soil Temp 2 [C]', 'Soil Temp 2 Min [C]', 'Soil Temp 2 Max [C]',
    'Counter 1 [Impulses]', 'Rain Abs [mm]', 'Counter 1 Diff [Impulses]', 'Rain Rel [mm]',
    'Duration Counting', 'Battery Voltage [V]', 'Internal Temp [C]', 'Alarm Level', 'Field Strength 1',
    'Serial Number', 'source_file'
]


DROP_SQL = 'DROP TABLE IF EXISTS ingested_parkplatz CASCADE;'

CREATE_SQL = '''
CREATE TABLE IF NOT EXISTS ingested_parkplatz (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    record_number TEXT,

    -- Radiation (with min/max)
    ir1_wm2 NUMERIC, ir1_min_wm2 NUMERIC, ir1_max_wm2 NUMERIC,
    sr1_wm2 NUMERIC, sr1_min_wm2 NUMERIC, sr1_max_wm2 NUMERIC,
    ir2_wm2 NUMERIC, ir2_min_wm2 NUMERIC, ir2_max_wm2 NUMERIC,
    sr2_wm2 NUMERIC, sr2_min_wm2 NUMERIC, sr2_max_wm2 NUMERIC,

    -- Temperature & Pressure (with min/max)
    temp_c NUMERIC, temp_min_c NUMERIC, temp_max_c NUMERIC,
    air_pressure_mbar NUMERIC, air_pressure_min_mbar NUMERIC, air_pressure_max_mbar NUMERIC,

    -- Soil Moisture (with min/max)
    soil_moisture_vol NUMERIC, soil_moisture_min_vol NUMERIC, soil_moisture_max_vol NUMERIC,

    -- Air Humidity/Temp Sensor 1 (with min/max)
    air_humidity_1_rh NUMERIC, air_humidity_1_min_rh NUMERIC, air_humidity_1_max_rh NUMERIC,
    air_temp_1_c NUMERIC, air_temp_1_min_c NUMERIC, air_temp_1_max_c NUMERIC,

    -- Air Humidity/Temp Sensor 2 (with min/max)
    air_humidity_2_rh NUMERIC, air_humidity_2_min_rh NUMERIC, air_humidity_2_max_rh NUMERIC,
    air_temp_2_c NUMERIC, air_temp_2_min_c NUMERIC, air_temp_2_max_c NUMERIC,

    -- Wind (with min/max)
    wind_speed_ms NUMERIC, wind_speed_min_ms NUMERIC, wind_speed_max_ms NUMERIC,
    wind_direction_deg NUMERIC, wind_direction_min_deg NUMERIC, wind_direction_max_deg NUMERIC,

    -- Soil Temperature (with min/max)
    soil_temp_1_c NUMERIC, soil_temp_1_min_c NUMERIC, soil_temp_1_max_c NUMERIC,
    soil_temp_2_c NUMERIC, soil_temp_2_min_c NUMERIC, soil_temp_2_max_c NUMERIC,

    -- Counters & Rain (no min/max)
    counter_1_impulses NUMERIC,
    rain_abs_mm NUMERIC,
    counter_diff_impulses NUMERIC,
    rain_rel_mm NUMERIC,
    duration_counting NUMERIC,

    -- System
    battery_voltage_v NUMERIC,
    internal_temp_c NUMERIC,
    alarm_level NUMERIC,
    field_strength_1 NUMERIC,
    serial_number TEXT,

    -- Import tracking
    filename TEXT,
    import_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
'''


def clean_colname(name):
    '''Clean column name for comparison/mapping.'''
    return re.sub(r'[\s/\[\]\(\)\.,:;"\'-]', '_', name)


def find_data_start(filepath):
    '''Find line number where data starts.'''
    def is_semicolon_line(line):
        return bool(re.match(r'^\s*;{5,}\s*$', line))

    try:
        with open(filepath, encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(filepath, encoding='latin-1') as f:
            lines = f.readlines()

    for i, line in enumerate(lines):
        if is_semicolon_line(line):
            return i + 2
        if re.search(r'\bNr\.\s*;.*\bDatum\b', line, flags=re.IGNORECASE) or line.strip().startswith('Nr.;'):
            return i + 1

    for i, line in enumerate(lines):
        if line.strip() == '':
            continue
        if 'Nr' in line or ';' in line:
            return i + 1
    return None


def extract_name_unit(h):
    '''Extract name and unit from header like "IR1 [W/m2] = m1 /E1/800016"'''
    h = h.strip().strip('"')
    match = re.match(r'^([^\[]+)\[([^\]]+)\]', h)
    if match:
        name = match.group(1).strip()
        unit = match.group(2).strip()
        return f"{name} [{unit}]"
    return h.split('[')[0].split('=')[0].strip()


def convert_column_numeric(series):
    '''
    Vectorized numeric conversion that treats the FIRST comma as decimal separator,
    then removes remaining commas (handles the corrupt -83,511,000 format).
    '''
    s = series.fillna('').astype(str).str.strip()
    s = s.str.replace('\xa0', '', regex=False).str.replace(' ', '', regex=False)

    has_comma = s.str.contains(',', regex=False)
    if has_comma.any():
        parts = s[has_comma].str.split(',', n=1)
        right = parts.str[1].fillna('').str.replace(',', '', regex=False)
        left = parts.str[0].fillna('')
        s.loc[has_comma] = left + '.' + right

    s = s.str.replace(r'[^0-9\.\-]', '', regex=True)

    multi_dot_mask = s.str.count(r'\.') > 1
    if multi_dot_mask.any():
        def collapse_dots(x):
            if '.' not in x:
                return x
            parts = x.split('.', 1)
            return parts[0] + '.' + parts[1].replace('.', '')
        s.loc[multi_dot_mask] = s.loc[multi_dot_mask].apply(collapse_dots)

    return pd.to_numeric(s.replace('', pd.NA), errors='coerce')


def normalize_scales(df):
    '''Detect and fix scale differences (1000x multiplication issues).'''
    if df is None or df.empty:
        return df

    exclude_kw = ('Impulse', 'Counter', 'Rain', 'Zaehler', 'Regen', 'source_file', 'Serial', 'No.', 'Date')
    for col in df.columns:
        if col in ('source_file', 'Serial Number', 'No.', 'Date / Time'):
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        if any(kw.lower() in col.lower() for kw in exclude_kw):
            continue

        med = df[col].abs().median(skipna=True)
        if pd.isna(med):
            continue

        if 1000.0 < med < 1e9:
            med_after = med / 1000.0
            if med_after < 1000.0:
                print(f"  [normalize_scales] Dividing '{col}' by 1000 (median {med:.1f} -> {med_after:.3f})")
                df[col] = df[col] / 1000.0

    return df


def normalize_variant_header(col):
    '''Normalize header variants (RH-unten -> Luftfeu-1, etc.)'''
    main = col.split('=')[0].strip()
    l = main.lower()

    if ('rh' in l and 'unten' in l) or 'rh-unten' in l or 'rh unten' in l:
        return 'Luftfeu-1 [%RH]'
    if ('lt' in l and 'unten' in l) or 'lt-unten' in l or 'lt unten' in l:
        return 'Lufttemp-1 [degC]'
    if ('rh' in l and 'oben' in l) or 'rh-oben' in l or 'rh oben' in l:
        return 'Luftfeu-2 [%RH]'
    if ('lt' in l and 'oben' in l) or 'lt-oben' in l or 'lt oben' in l:
        return 'Lufttemp-2 [degC]'
    
    # Handle typo in older files: "Luftemp-1" instead of "Lufttemp-1"
    if 'luftemp-1' in l or 'luftemp 1' in l:
        return 'Lufttemp-1 [degC]'
    if 'luftemp-2' in l or 'luftemp 2' in l:
        return 'Lufttemp-2 [degC]'

    return main


def parse_any_date(val):
    '''Parse various date formats found in Parkplatz files.'''
    if pd.isna(val):
        return None
    val = str(val).strip()
    if not val:
        return None

    m1 = re.match(r'^(\d{2})(\d{2})(\d{4})[\sT](\d{2}):(\d{2})(?::(\d{2}))?$', val)
    if m1:
        day, month, year, hour, minute, second = m1.groups()
        second = second or '00'
        return f"{year}-{month}-{day} {hour}:{minute}:{second}"

    m2 = re.match(r'^(\d{2})\.(\d{2})\.(\d{2,4})[\sT](\d{2}):(\d{2})(?::(\d{2}))?$', val)
    if m2:
        day, month, year, hour, minute, second = m2.groups()
        if len(year) == 2:
            year = '20' + year if int(year) < 50 else '19' + year
        second = second or '00'
        return f"{year}-{month}-{day} {hour}:{minute}:{second}"

    m3 = re.match(r'^(\d{4})-(\d{2})-(\d{2})[\sT](\d{2}):(\d{2}):(\d{2})$', val)
    if m3:
        return val.replace('T', ' ')

    try:
        dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


# Header translation map (German -> English)
HEADER_MAP = {
    clean_colname('Nr.'): 'No.',
    clean_colname('Datum / Uhrzeit'): 'Date / Time',
    clean_colname('IR1 [W/m2]'): 'IR1 [W/m2]',
    clean_colname('IR1 [W/m2]_1'): 'IR1 Min [W/m2]',
    clean_colname('IR1 [W/m2]_2'): 'IR1 Max [W/m2]',
    clean_colname('SR1 [W/m2]'): 'SR1 [W/m2]',
    clean_colname('SR1 [W/m2]_1'): 'SR1 Min [W/m2]',
    clean_colname('SR1 [W/m2]_2'): 'SR1 Max [W/m2]',
    clean_colname('IR2 [W/m2]'): 'IR2 [W/m2]',
    clean_colname('IR2 [W/m2]_1'): 'IR2 Min [W/m2]',
    clean_colname('IR2 [W/m2]_2'): 'IR2 Max [W/m2]',
    clean_colname('SR2 [W/m2]'): 'SR2 [W/m2]',
    clean_colname('SR2 [W/m2]_1'): 'SR2 Min [W/m2]',
    clean_colname('SR2 [W/m2]_2'): 'SR2 Max [W/m2]',
    clean_colname('Temp [degC]'): 'Temp [C]',
    clean_colname('Temp [degC]_1'): 'Temp Min [C]',
    clean_colname('Temp [degC]_2'): 'Temp Max [C]',
    clean_colname('Luftdruck [mbar]'): 'Air Pressure [mbar]',
    clean_colname('Luftdruck [mbar]_1'): 'Air Pressure Min [mbar]',
    clean_colname('Luftdruck [mbar]_2'): 'Air Pressure Max [mbar]',
    clean_colname('Bodenfeucht [vol%]'): 'Soil Moisture [vol%]',
    clean_colname('Bodenfeucht [vol%]_1'): 'Soil Moisture Min [vol%]',
    clean_colname('Bodenfeucht [vol%]_2'): 'Soil Moisture Max [vol%]',
    clean_colname('Luftfeu-1 [%RH]'): 'Air Humidity 1 [%RH]',
    clean_colname('Luftfeu-1 [%RH]_1'): 'Air Humidity 1 Min [%RH]',
    clean_colname('Luftfeu-1 [%RH]_2'): 'Air Humidity 1 Max [%RH]',
    clean_colname('Lufttemp-1 [degC]'): 'Air Temp 1 [C]',
    clean_colname('Lufttemp-1 [degC]_1'): 'Air Temp 1 Min [C]',
    clean_colname('Lufttemp-1 [degC]_2'): 'Air Temp 1 Max [C]',
    clean_colname('Luftfeu-2 [%RH]'): 'Air Humidity 2 [%RH]',
    clean_colname('Luftfeu-2 [%RH]_1'): 'Air Humidity 2 Min [%RH]',
    clean_colname('Luftfeu-2 [%RH]_2'): 'Air Humidity 2 Max [%RH]',
    clean_colname('Lufttemp-2 [degC]'): 'Air Temp 2 [C]',
    clean_colname('Lufttemp-2 [degC]_1'): 'Air Temp 2 Min [C]',
    clean_colname('Lufttemp-2 [degC]_2'): 'Air Temp 2 Max [C]',
    clean_colname('Windgeschw [m/s]'): 'Wind Speed [m/s]',
    clean_colname('Windgeschw [m/s]_1'): 'Wind Speed Min [m/s]',
    clean_colname('Windgeschw [m/s]_2'): 'Wind Speed Max [m/s]',
    clean_colname('Windricht [grad]'): 'Wind Direction [deg]',
    clean_colname('Windricht [grad]_1'): 'Wind Direction Min [deg]',
    clean_colname('Windricht [grad]_2'): 'Wind Direction Max [deg]',
    clean_colname('Bodentemp-1 [degC]'): 'Soil Temp 1 [C]',
    clean_colname('Bodentemp-1 [degC]_1'): 'Soil Temp 1 Min [C]',
    clean_colname('Bodentemp-1 [degC]_2'): 'Soil Temp 1 Max [C]',
    clean_colname('Bodentemp-2 [degC]'): 'Soil Temp 2 [C]',
    clean_colname('Bodentemp-2 [degC]_1'): 'Soil Temp 2 Min [C]',
    clean_colname('Bodentemp-2 [degC]_2'): 'Soil Temp 2 Max [C]',
    clean_colname('Zaehler1 [Impulse]'): 'Counter 1 [Impulses]',
    clean_colname('Regen-abs [mm]'): 'Rain Abs [mm]',
    clean_colname('Zaehler1-Differenz [Impulse]'): 'Counter 1 Diff [Impulses]',
    clean_colname('Regen-rel [mm]'): 'Rain Rel [mm]',
    clean_colname('Dauer Zahlvorgang'): 'Duration Counting',
    clean_colname('Vbatt [V]'): 'Battery Voltage [V]',
    clean_colname('Tintern [degC]'): 'Internal Temp [C]',
    clean_colname('Alarmstufe'): 'Alarm Level',
    clean_colname('Feldstarke 1'): 'Field Strength 1',
    clean_colname('Seriennummer'): 'Serial Number',
}


DB_COL_MAP = {
    'No.': 'record_number',
    'Date / Time': 'timestamp',
    'IR1 [W/m2]': 'ir1_wm2', 'IR1 Min [W/m2]': 'ir1_min_wm2', 'IR1 Max [W/m2]': 'ir1_max_wm2',
    'SR1 [W/m2]': 'sr1_wm2', 'SR1 Min [W/m2]': 'sr1_min_wm2', 'SR1 Max [W/m2]': 'sr1_max_wm2',
    'IR2 [W/m2]': 'ir2_wm2', 'IR2 Min [W/m2]': 'ir2_min_wm2', 'IR2 Max [W/m2]': 'ir2_max_wm2',
    'SR2 [W/m2]': 'sr2_wm2', 'SR2 Min [W/m2]': 'sr2_min_wm2', 'SR2 Max [W/m2]': 'sr2_max_wm2',
    'Temp [C]': 'temp_c', 'Temp Min [C]': 'temp_min_c', 'Temp Max [C]': 'temp_max_c',
    'Air Pressure [mbar]': 'air_pressure_mbar', 'Air Pressure Min [mbar]': 'air_pressure_min_mbar', 'Air Pressure Max [mbar]': 'air_pressure_max_mbar',
    'Soil Moisture [vol%]': 'soil_moisture_vol', 'Soil Moisture Min [vol%]': 'soil_moisture_min_vol', 'Soil Moisture Max [vol%]': 'soil_moisture_max_vol',
    'Air Humidity 1 [%RH]': 'air_humidity_1_rh', 'Air Humidity 1 Min [%RH]': 'air_humidity_1_min_rh', 'Air Humidity 1 Max [%RH]': 'air_humidity_1_max_rh',
    'Air Temp 1 [C]': 'air_temp_1_c', 'Air Temp 1 Min [C]': 'air_temp_1_min_c', 'Air Temp 1 Max [C]': 'air_temp_1_max_c',
    'Air Humidity 2 [%RH]': 'air_humidity_2_rh', 'Air Humidity 2 Min [%RH]': 'air_humidity_2_min_rh', 'Air Humidity 2 Max [%RH]': 'air_humidity_2_max_rh',
    'Air Temp 2 [C]': 'air_temp_2_c', 'Air Temp 2 Min [C]': 'air_temp_2_min_c', 'Air Temp 2 Max [C]': 'air_temp_2_max_c',
    'Wind Speed [m/s]': 'wind_speed_ms', 'Wind Speed Min [m/s]': 'wind_speed_min_ms', 'Wind Speed Max [m/s]': 'wind_speed_max_ms',
    'Wind Direction [deg]': 'wind_direction_deg', 'Wind Direction Min [deg]': 'wind_direction_min_deg', 'Wind Direction Max [deg]': 'wind_direction_max_deg',
    'Soil Temp 1 [C]': 'soil_temp_1_c', 'Soil Temp 1 Min [C]': 'soil_temp_1_min_c', 'Soil Temp 1 Max [C]': 'soil_temp_1_max_c',
    'Soil Temp 2 [C]': 'soil_temp_2_c', 'Soil Temp 2 Min [C]': 'soil_temp_2_min_c', 'Soil Temp 2 Max [C]': 'soil_temp_2_max_c',
    'Counter 1 [Impulses]': 'counter_1_impulses',
    'Rain Abs [mm]': 'rain_abs_mm',
    'Counter 1 Diff [Impulses]': 'counter_diff_impulses',
    'Rain Rel [mm]': 'rain_rel_mm',
    'Duration Counting': 'duration_counting',
    'Battery Voltage [V]': 'battery_voltage_v',
    'Internal Temp [C]': 'internal_temp_c',
    'Alarm Level': 'alarm_level',
    'Field Strength 1': 'field_strength_1',
    'Serial Number': 'serial_number',
    'source_file': 'filename',
}


def read_csv_clean(filepath):
    '''Read and clean a Parkplatz CSV file.'''
    data_start = find_data_start(filepath)
    if data_start is None:
        raise ValueError(f"Could not find data start in {filepath}")

    try:
        with open(filepath, encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(filepath, encoding='latin-1') as f:
            lines = f.readlines()

    header_line = lines[data_start - 1].strip()
    header_raw = [extract_name_unit(h) for h in header_line.split(';')]

    while header_raw and (header_raw[-1] == '' or header_raw[-1] is None):
        header_raw.pop()
    header = [h for h in header_raw if h]

    # Make unique column names
    counts = {}
    unique_header = []
    for n in header:
        if n not in counts:
            counts[n] = 0
            unique_header.append(n)
        else:
            counts[n] += 1
            unique_header.append(f"{n}_{counts[n]}")
    header = unique_header

    # Read data rows
    raw_rows = []
    try:
        with open(filepath, encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            for i, row in enumerate(reader):
                if i < data_start:
                    continue
                while row and (row[-1] == '' or row[-1] is None):
                    row.pop()
                if not raw_rows and row:
                    row[0] = row[0].lstrip('\ufeff')
                if len(row) != len(header):
                    if len(row) < len(header):
                        row = row + [''] * (len(header) - len(row))
                    else:
                        row = row[:len(header)]
                raw_rows.append(row)
    except UnicodeDecodeError:
        with open(filepath, encoding='latin-1') as f:
            reader = csv.reader(f, delimiter=';')
            for i, row in enumerate(reader):
                if i < data_start:
                    continue
                while row and (row[-1] == '' or row[-1] is None):
                    row.pop()
                if not raw_rows and row:
                    row[0] = row[0].lstrip('\ufeff')
                if len(row) != len(header):
                    if len(row) < len(header):
                        row = row + [''] * (len(header) - len(row))
                    else:
                        row = row[:len(header)]
                raw_rows.append(row)

    if not raw_rows:
        return pd.DataFrame(columns=FINAL_COLS)

    df = pd.DataFrame(raw_rows, columns=header)
    df['source_file'] = os.path.basename(filepath)

    # Parse date column FIRST (before any other processing)
    date_col_candidates = [col for col in header if 'Datum' in col or 'Uhrzeit' in col or 'Date' in col]
    date_col = date_col_candidates[0] if date_col_candidates else header[1]
    parsed_dates = df[date_col].apply(parse_any_date)

    # Now drop the original date column to avoid confusion
    if date_col in df.columns:
        df = df.drop(columns=[date_col])

    # Normalize variant headers
    df.columns = [normalize_variant_header(col) for col in df.columns]

    # Clean column names for mapping
    df.columns = [clean_colname(col) for col in df.columns]

    # Handle Seriennummer columns
    seriennummer_cols = [col for col in df.columns if 'seriennummer' in col.lower()]
    if seriennummer_cols:
        df['Seriennummer'] = df[seriennummer_cols[0]].astype(str).str.strip()
        for col in seriennummer_cols:
            if col != 'Seriennummer' and col in df.columns:
                df = df.drop(columns=[col])

    # Convert numeric columns (EXCLUDING date-related columns)
    exclude_cols = ['source_file', 'Seriennummer', 'Nr_']
    for col in df.columns:
        if any(ex in col for ex in exclude_cols):
            continue
        if pd.api.types.is_object_dtype(df[col]):
            try:
                df[col] = convert_column_numeric(df[col])
            except Exception:
                pass

    # Apply header translation
    df.rename(columns=HEADER_MAP, inplace=True)

    # Apply scale normalization
    df = normalize_scales(df)

    # Align to FINAL_COLS
    df = df.reindex(columns=FINAL_COLS)

    # NOW set the Date / Time column with parsed dates
    df['Date / Time'] = parsed_dates.values

    # Filter out rows without valid dates
    df = df[df['Date / Time'].notna()]

    return df


def _insert_batch(conn, df, batch_size=1000):
    '''Insert DataFrame rows into ingested_parkplatz.'''
    if df.empty:
        return 0

    cur = conn.cursor()
    inserted = 0

    db_cols = [DB_COL_MAP[col] for col in FINAL_COLS if col in DB_COL_MAP]

    for start in range(0, len(df), batch_size):
        batch = df.iloc[start:start + batch_size]

        for _, row in batch.iterrows():
            values = []
            for col in FINAL_COLS:
                val = row.get(col)
                if pd.isna(val):
                    values.append(None)
                elif col == 'Date / Time':
                    try:
                        ts = pd.to_datetime(val, errors='coerce')
                        values.append(ts if not pd.isna(ts) else None)
                    except:
                        values.append(None)
                else:
                    values.append(val)

            placeholders = ', '.join(['%s'] * len(db_cols))
            col_names = ', '.join(db_cols)

            cur.execute(f'''
                INSERT INTO ingested_parkplatz ({col_names})
                VALUES ({placeholders})
            ''', values)
            inserted += 1

    conn.commit()
    cur.close()
    return inserted


def ingest_parkplatz():
    '''Ingest all Parkplatz CSVs from both Empower and Kissel subfolders.'''
    conn = get_connection()
    cur = conn.cursor()
    print('[ingest_parkplatz] Dropping existing table...')
    cur.execute(DROP_SQL)
    cur.execute(CREATE_SQL)
    conn.commit()

    subfolders = ['Empower_Parkplatz_data', 'Kissel_Parkplatz_data']
    all_files = []

    for subfolder in subfolders:
        folder_path = os.path.join(PARKPLATZ_DIR, subfolder)
        if os.path.isdir(folder_path):
            count_before = len(all_files)
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    if f.lower().endswith('.csv'):
                        all_files.append(os.path.join(root, f))
            print(f"[ingest_parkplatz] Found {len(all_files) - count_before} files in {subfolder}")

    if os.path.isdir(PARKPLATZ_DIR):
        for f in os.listdir(PARKPLATZ_DIR):
            fpath = os.path.join(PARKPLATZ_DIR, f)
            if f.lower().endswith('.csv') and os.path.isfile(fpath):
                all_files.append(fpath)

    print(f"[ingest_parkplatz] Processing {len(all_files)} total CSV files...")

    total_rows = 0
    for i, fpath in enumerate(all_files, 1):
        print(f"[{i}/{len(all_files)}] {os.path.basename(fpath)}")
        try:
            df = read_csv_clean(fpath)
            if df is not None and not df.empty:
                rows = _insert_batch(conn, df)
                total_rows += rows
                print(f"  Inserted {rows} rows")
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if i % 50 == 0:
            gc.collect()

    # Create index for efficient timestamp ordering
    print('[ingest_parkplatz] Creating timestamp index...')
    cur = conn.cursor()
    cur.execute('CREATE INDEX IF NOT EXISTS idx_ingested_parkplatz_ts ON ingested_parkplatz(timestamp ASC);')
    conn.commit()
    cur.close()
    
    conn.close()
    print(f"[ingest_parkplatz] Ingested {total_rows} parkplatz records total.")
