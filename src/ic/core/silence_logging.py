"""
Logging silencer module to suppress console output except for ERROR messages.
"""

import logging
import sys
from typing import Any


class SilentFilter(logging.Filter):
    """Filter to suppress all log messages except ERROR and CRITICAL."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


class SilentHandler(logging.Handler):
    """Handler that does nothing - completely silent."""
    
    def emit(self, record: logging.LogRecord) -> None:
        pass


def silence_all_logging():
    """Silence all logging output to console except ERROR and CRITICAL."""
    # Get root logger
    root_logger = logging.getLogger()
    
    # Remove all existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add silent handler for everything below ERROR
    silent_handler = SilentHandler()
    silent_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(silent_handler)
    
    # Add console handler only for ERROR and above
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.ERROR)
    console_handler.addFilter(SilentFilter())
    root_logger.addHandler(console_handler)
    
    # Set root logger level to DEBUG to catch everything
    root_logger.setLevel(logging.DEBUG)
    
    # Also silence specific loggers that might be problematic
    problematic_loggers = [
        'ic.config.manager',
        'ic.config.secrets', 
        'ic.config.external',
        'ic.config.security',
        'ic.core.logging',
        'rich'
    ]
    
    for logger_name in problematic_loggers:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.addHandler(SilentHandler())
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False


def restore_error_only_logging():
    """Restore logging to show only ERROR and CRITICAL messages."""
    silence_all_logging()