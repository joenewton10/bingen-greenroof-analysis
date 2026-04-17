"""
Pre-flight checks for pipeline: DB connection, .env loading, data folder checks.
"""
import logging
from pathlib import Path
from dotenv import load_dotenv
from pipeline.ingest.base import get_connection


def run_preflight_checks(logger: logging.Logger, project_root: Path) -> bool:
    """
    Run all pre-flight checks before pipeline starts.
    
    Args:
        logger: Logger instance
        project_root: Root directory of project
    
    Returns:
        True if all checks pass, False otherwise
    """
    logger.info('\n' + '=' * 60)
    logger.info('PRE-FLIGHT CHECKS'.center(60))
    logger.info('=' * 60)
    
    checks_passed = 0
    checks_failed = 0
    
    # Check 1: .env file exists
    env_file = project_root / "config" / ".env"
    if env_file.exists():
        logger.info(f'[OK] .env file found: {env_file}')
        checks_passed += 1
    else:
        logger.error(f'[ERROR] .env file not found: {env_file}')
        logger.error('  Please copy config/.env.example to config/.env and fill in credentials')
        checks_failed += 1
        return False
    
    # Check 2: Load .env
    load_dotenv(env_file, override=True)
    
    # Check 3: Database connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT version();')
        db_version = cur.fetchone()[0].split(',')[0]
        cur.close()
        conn.close()
        logger.info(f'[OK] Database connection OK: {db_version}')
        checks_passed += 1
    except Exception as exc:
        logger.error(f'[ERROR] Database connection failed: {exc}')
        checks_failed += 1
        return False
    
    # Check 4: Data directories exist
    greenroof_dir = project_root / "data" / "raw" / "greenroof"
    parkplatz_dir = project_root / "data" / "raw" / "parkplatz"
    
    if greenroof_dir.exists():
        csv_count = len(list(greenroof_dir.rglob('*.csv')))
        logger.info(f'[OK] Greenroof data directory exists: {csv_count} CSV files')
        checks_passed += 1
    else:
        logger.error(f'[ERROR] Greenroof directory not found: {greenroof_dir}')
        checks_failed += 1
    
    if parkplatz_dir.exists():
        csv_count = len(list(parkplatz_dir.rglob('*.csv')))
        logger.info(f'[OK] Parkplatz data directory exists: {csv_count} CSV files')
        checks_passed += 1
    else:
        logger.error(f'[ERROR] Parkplatz directory not found: {parkplatz_dir}')
        checks_failed += 1
    
    # Check 5: Logs directory writable
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    try:
        test_file = logs_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        logger.info(f'[OK] Logs directory writable: {logs_dir}')
        checks_passed += 1
    except Exception as exc:
        logger.error(f'[ERROR] Cannot write to logs directory: {exc}')
        checks_failed += 1
        return False
    
    # Summary
    logger.info('-' * 60)
    logger.info(f'Pre-flight checks: {checks_passed} passed, {checks_failed} failed')
    
    if checks_failed > 0:
        logger.error('Pre-flight checks FAILED. Please fix issues above.')
        return False
    
    logger.info('[OK] All pre-flight checks passed!\n')
    return True
