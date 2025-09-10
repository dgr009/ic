"""
Common utilities and shared components for the IC CLI tool.

This module provides shared functionality across all cloud platform modules
including logging, configuration utilities, and progress tracking.
"""

# Import progress decorator components for easy access
from .progress_decorator import (
    ProgressBarDecorator,
    progress_bar,
    spinner,
    concurrent_progress,
    ManualProgress,
    ProgressContext
)

# Import logging utilities
from .log import (
    log_info,
    log_error,
    log_exception,
    log_decorator,
    print_table,
    console
)

__all__ = [
    # Progress tracking
    'ProgressBarDecorator',
    'progress_bar', 
    'spinner',
    'concurrent_progress',
    'ManualProgress',
    'ProgressContext',
    
    # Logging
    'log_info',
    'log_error', 
    'log_exception',
    'log_decorator',
    'print_table',
    'console'
]