'''
Bingen Greenroof Data Pipeline - Main Orchestrator

Table naming convention for Bingen pipeline:
- Ingested: ingested_empower_greenroof, ingested_kissel_greenroof, ingested_parkplatz
- Validated: val_ingested_empower_greenroof, val_ingested_kissel_greenroof, val_ingested_parkplatz
- Harmonized: harm_greenroof, harm_parkplatz
- Final: synchronized_data_filtered

Pipeline stages:
1. INGEST: CSV files -> ingested_empower_greenroof, ingested_kissel_greenroof, ingested_parkplatz
2. VALIDATE: Apply sensor range filters -> val_ingested_* tables
3. HARMONIZE: Map to canonical columns -> harm_greenroof, harm_parkplatz
4. SYNC: Minute-level join with filters -> synchronized_data_filtered
'''
from pipeline.ingest.ingest_greenroof import ingest_greenroof
from pipeline.ingest.ingest_parkplatz import ingest_parkplatz
from pipeline.validate.validate_greenroof import validate_greenroof
from pipeline.validate.validate_parkplatz import validate_parkplatz
from pipeline.harmonize.harmonize_greenroof import harmonize_greenroof
from pipeline.sync.sync_sites import harmonize_parkplatz, sync_data


if __name__ == '__main__':
    print('=' * 60)
    print('BINGEN GREENROOF PIPELINE START')
    print('=' * 60)

    # STAGE 1: INGEST
    print('\n[STAGE 1] INGESTION')
    print('-' * 40)
    print('Ingesting Greenroof data (Empower + Kissel)...')
    ingest_greenroof()

    print('\nIngesting Parkplatz data...')
    ingest_parkplatz()

    # STAGE 2: VALIDATE
    print('\n[STAGE 2] VALIDATION')
    print('-' * 40)
    print('Validating Greenroof data...')
    validate_greenroof()

    print('\nValidating Parkplatz data...')
    validate_parkplatz()

    # STAGE 3: HARMONIZE
    print('\n[STAGE 3] HARMONIZATION')
    print('-' * 40)
    print('Harmonizing Greenroof data (combining sources)...')
    harmonize_greenroof()

    print('\nHarmonizing Parkplatz data...')
    harmonize_parkplatz()

    # STAGE 4: SYNCHRONIZE
    print('\n[STAGE 4] SYNCHRONIZATION')
    print('-' * 40)
    print('Synchronizing Greenroof + Parkplatz per minute...')
    sync_data()

    print('\n' + '=' * 60)
    print('PIPELINE COMPLETED SUCCESSFULLY')
    print('=' * 60)
    print('\nOutput tables created:')
    print('  Ingested:')
    print('    - ingested_empower_greenroof (Empower source)')
    print('    - ingested_kissel_greenroof (Kissel source)')
    print('    - ingested_parkplatz')
    print('  Validated:')
    print('    - val_ingested_empower_greenroof')
    print('    - val_ingested_kissel_greenroof')
    print('    - val_ingested_parkplatz')
    print('  Harmonized:')
    print('    - harm_greenroof (12 canonical columns)')
    print('    - harm_parkplatz')
    print('  Final:')
    print('    - synchronized_data_filtered (24 columns, minute-level)')
