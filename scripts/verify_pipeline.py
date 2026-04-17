"""
Verify pipeline output - post-run QC-check script.

Run after pipeline completes to check:
- All tables exist and have data
- Timestamp ranges are reasonable
- Data freshness
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.ingest.base import get_connection
from pipeline.utils.logger import setup_logger, log_section, log_success, log_warning, log_error


def verify_table_exists_and_count(logger, cur, table_name):
    """Check if table exists and return row count."""
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        return count
    except Exception as exc:
        logger.error(f"  ✗ {table_name}: {exc}")
        return None


def get_timestamp_range(logger, cur, table_name):
    """Get min/max timestamp from table."""
    try:
        cur.execute(f'''
            SELECT 
                MIN(timestamp) as min_ts,
                MAX(timestamp) as max_ts,
                COUNT(*) as total_count
            FROM {table_name}
            WHERE timestamp IS NOT NULL
        ''')
        result = cur.fetchone()
        return result
    except Exception:
        return None


def main():
    """Main verification loop."""
    logger = setup_logger('verify_pipeline', verbose=False)
    
    log_section(logger, 'PIPELINE VERIFICATION')
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        conn.autocommit = True
        
        logger.info('\nChecking tables...\n')
        
        # Define all expected tables
        tables_to_check = {
            'Ingested': [
                'ingested_empower_greenroof',
                'ingested_kissel_greenroof',
                'ingested_parkplatz',
            ],
            'QC-filtered': [
                'qc_filtered_greenroof',
                'qc_filtered_parkplatz',
            ],
            'Harmonized': [
                'harm_greenroof',
                'harm_parkplatz',
            ],
            'Final': [
                'synchronized_data_filtered',
                'synchronized_data_yearly',
            ],
        }
        
        all_good = True
        total_rows = 0
        
        for category, tables in tables_to_check.items():
            logger.info(f'{category} Tables:')
            logger.info('-' * 40)
            
            for table_name in tables:
                count = verify_table_exists_and_count(logger, cur, table_name)
                
                if count is None:
                    logger.error(f"  ✗ {table_name}: TABLE NOT FOUND")
                    all_good = False
                elif count == 0:
                    logger.warning(f"  ⚠ {table_name}: {count:,} rows (empty)")
                    all_good = False
                else:
                    log_success(logger, f'{table_name}: {count:,} rows')
                    total_rows += count
                    
                    # Get timestamp range for final synchronized table
                    if table_name == 'synchronized_data_filtered':
                        ts_result = get_timestamp_range(logger, cur, table_name)
                        if ts_result:
                            min_ts, max_ts, count = ts_result
                            logger.info(f'    Time range: {min_ts} to {max_ts}')
                            
                            # Check data freshness
                            if max_ts:
                                now = datetime.now()
                                max_ts_dt = max_ts if isinstance(max_ts, datetime) else datetime.fromisoformat(str(max_ts))
                                age_days = (now - max_ts_dt).days
                                
                                if age_days == 0:
                                    logger.info('    Freshness: TODAY [OK]')
                                elif age_days <= 7:
                                    logger.info(f'    Freshness: {age_days} days old [OK]')
                                else:
                                    log_warning(logger, f'Data is {age_days} days old')
            
            logger.info('')
        
        # Final summary
        cur.close()
        conn.close()
        
        log_section(logger, 'VERIFICATION COMPLETE')
        
        if all_good:
            logger.info('\n[OK] All tables verified successfully')
            logger.info(f'[OK] Total rows across all tables: {total_rows:,}')
            logger.info(f'\nPipeline is ready for dashboard:')
            logger.info(f'  streamlit run dashboard/app.py')
            return 0
        else:
            log_error(logger, 'Some tables are missing or empty. Check logs above.')
            return 1
        
    except Exception as exc:
        log_error(logger, f'Verification failed: {exc}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
