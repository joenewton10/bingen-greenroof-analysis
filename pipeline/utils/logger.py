"""
Centralized logging module for pipeline with file + console output and rotation.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str, log_dir: Path = None, verbose: bool = False) -> logging.Logger:
    """
    Configure logger with file + console output and auto-rotation.
    
    Args:
        name: Logger name (typically __name__)
        log_dir: Directory to store logs (default: PROJECT_ROOT/logs)
        verbose: If True, set DEBUG level; otherwise INFO
    
    Returns:
        Configured logger instance
    """
    # Avoid Windows console encoding errors when log messages include symbols.
    for stream_name in ('stdout', 'stderr'):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    
    log_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Remove existing handlers to avoid duplication
    logger.handlers = []
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation (keep last 5 files, each up to 10MB)
    log_file = log_dir / f"pipeline_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def log_section(logger: logging.Logger, title: str, width: int = 60):
    """Log a formatted section header."""
    logger.info('=' * width)
    logger.info(title.center(width))
    logger.info('=' * width)


def log_stage(logger: logging.Logger, stage_num: int, stage_name: str):
    """Log a stage header."""
    logger.info(f'\n[STAGE {stage_num}] {stage_name}')
    logger.info('-' * 40)


def log_success(logger: logging.Logger, message: str):
    """Log success message."""
    logger.info(f'[OK] {message}')


def log_warning(logger: logging.Logger, message: str):
    """Log warning message."""
    logger.warning(f'[WARN] {message}')


def log_error(logger: logging.Logger, message: str):
    """Log error message."""
    logger.error(f'[ERROR] {message}')
