# Raw Data

Place raw CSV data files here for the Bingen green roof pipeline. 

## Expected Structure

- **greenroof/**: Raw CSV files from Empower and Kissel green roof sensors
- **parkplatz/**: Raw CSV files from Empower and Kissel parking lot sensors

## Data Sources

- Empower sensors: Subdirectory `Empower_Greenroof/` and `Empower_Parkplatz_data/`
- Kissel sensors: Subdirectory `Kissel_GreenRoof_Data/` and `Kissel_Parkplatz_data/`

The pipeline expects files with timestamps in ISO format and columns for radiation measurements (SR1, SR2, IR1, IR2, etc.).
