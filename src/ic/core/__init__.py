"""
Core utilities for IC (Infra Resource Management CLI).

This package contains core functionality including:
- Enhanced logging system with security features
- Session management utilities
- Common utilities and helpers
"""

try:
    from .logging import ICLogger, get_logger, init_logger
except ImportError:
    try:
        from src.ic.core.logging import ICLogger, get_logger, init_logger
    except ImportError:
        from ic.core.logging import ICLogger, get_logger, init_logger

__all__ = [
    'ICLogger',
    'get_logger', 
    'init_logger',
]