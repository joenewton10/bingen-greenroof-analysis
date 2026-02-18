"""
Bingen Greenroof Data Pipeline - Ingest Runner

This script runs the ingest process for Bingen_Greenroof_DB.
It will create two tables:
  - ingested_empower_greenroof (Empower format files)
  - ingested_kissel_greenroof (Kissel/MXmini format files)

Usage:
  cd "C:\\Users\\Joe\\Analysis code\\bingen_greenroof_pipeline"
  python run_ingest.py
"""
import sys
import os

# Ensure we can import from the pipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.ingest.ingest_greenroof import ingest_greenroof


if __name__ == '__main__':
    print('=' * 60)
    print('BINGEN GREENROOF PIPELINE - INGEST')
    print('Database: Bingen_Greenroof_DB')
    print('=' * 60)
    
    print('\nIngesting Greenroof data (Empower + Kissel)...')
    ingest_greenroof()
    
    print('\n' + '=' * 60)
    print('INGEST COMPLETED')
    print('=' * 60)
    print('\nTables created:')
    print('  - ingested_empower_greenroof (Empower format files)')
    print('  - ingested_kissel_greenroof (Kissel/MXmini format files)')
