import os
import glob
from pipeline.ingest.ingest_parkplatz import read_csv_clean

# Test 2020 file (old format)
print('=== Testing 2020 file (Kissel format) ===')
f2020 = 'data/raw/parkplatz/Kissel_Parkplatz_data/2020-07-02 1553 60.900.20_215 Datensatz 112725-112959.csv'
df2020 = read_csv_clean(f2020)
print(f'2020: {len(df2020)} rows, {df2020["Date / Time"].min()}')

# Test 2024 file (new format)
print('\n=== Testing 2024 file (Empower format) ===')
f2024 = 'data/raw/parkplatz/Empower_Parkplatz_data/2024-07-10 1359 60.900.20_215 Datensatz 2060001-2069999.csv'
df2024 = read_csv_clean(f2024)
print(f'2024: {len(df2024)} rows, {df2024["Date / Time"].min()}')
