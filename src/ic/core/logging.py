"""
Enhanced logging system with security-aware dual-level logging.

This module provides:
- Console logging for ERROR/CRITICAL only
- Comprehensive file logging with rotation
- Sensitive data masking in all log outputs
- Rich console formatting
- Structured log file management
"""

import logging
import logging.handlers
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    from rich.console import Console
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..config.security import SecurityManager


class ICLogger:
    """Enhanced logger with dual-level logging and security features."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the IC logger with configuration.
        
        Args:
            config: Configuration dictionary with logging settings
        """
        self.config = config or {}
        self.logging_config = self.config.get('logging', {})
        
        # Initialize security manager for sensitive data masking
        self.security_manager = SecurityManager(self.config)
        
        # Console and file log levels
        self.console_level = getattr(logging, self.logging_config.get('console_level', 'ERROR'))
        self.file_level = getattr(logging, self.logging_config.get('file_level', 'INFO'))
        
        # Log file configuration
        self.log_file_path = self._get_log_file_path()
        self.max_files = self.logging_config.get('max_files', 30)
        self.log_format = self.logging_config.get('format', 
                                                 '%(asctime)s [%(levelname)s] - %(message)s')
        
        # Initialize console for Rich output
        self.console = Console() if RICH_AVAILABLE else None
        
        # Setup loggers
        self.logger = self._setup_logger()
        
        # Set global logging level to suppress console output for non-ERROR messages
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Allow all levels for file logging
        
        # Remove any existing console handlers from root logger
        for handler in root_logger.handlers[:]:
            if isinstance(handler, (logging.StreamHandler, RichHandler if RICH_AVAILABLE else type(None))):
                root_logger.removeHandler(handler)
        
    def _get_log_file_path(self) -> str:
        """Generate log file path with date using fixed path logic."""
        log_path_template = self.logging_config.get('file_path', '~/.ic/logs/ic_{date}.log')
        date_str = datetime.now().strftime('%Y%m%d')
        log_path = log_path_template.format(date=date_str)
        
        # Expand user path and resolve
        log_path = Path(log_path).expanduser().resolve()
        
        # Ensure log directory exists with fallback logic
        log_dir = log_path.parent
        
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            # Fallback to temp directory if home directory is not writable
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / "ic" / "logs"
            try:
                temp_dir.mkdir(parents=True, exist_ok=True)
                log_path = temp_dir / f"ic_{date_str}.log"
                print(f"Warning: Using fallback log path {log_path} due to: {e}")
            except Exception as fallback_error:
                # Last resort: current directory
                log_path = Path(f"ic_{date_str}.log")
                print(f"Warning: Using current directory for logs due to: {fallback_error}")
        
        return str(log_path)
    
    def _setup_logger(self) -> logging.Logger:
        """Setup dual-level logger with console and file handlers."""
        logger = logging.getLogger('ic')
        logger.setLevel(logging.DEBUG)  # Set to lowest level, handlers will filter
        
        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # Console handler - ERROR and CRITICAL only
        if RICH_AVAILABLE:
            console_handler = RichHandler(
                console=self.console,
                show_time=False,
                show_path=False,
                rich_tracebacks=True
            )
        else:
            console_handler = logging.StreamHandler()
            
        console_handler.setLevel(self.console_level)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Add filter to suppress non-ERROR messages on console
        def error_only_filter(record):
            return record.levelno >= logging.ERROR
        
        console_handler.addFilter(error_only_filter)
        logger.addHandler(console_handler)
        
        # File handler - comprehensive logging with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=self.max_files,
            encoding='utf-8'
        )
        file_handler.setLevel(self.file_level)
        file_formatter = logging.Formatter(self.log_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def _mask_message(self, message: str) -> str:
        """Mask sensitive data in log messages."""
        if not self.logging_config.get('mask_sensitive', True):
            return message
            
        # Use security manager to mask sensitive data
        return self.security_manager.mask_sensitive_in_text(message)
    
    def log_args(self, args: Union[Dict[str, Any], object]) -> None:
        """
        Display command arguments on console and log to file.
        
        Args:
            args: Arguments dictionary or argparse Namespace object
        """
        # Convert args to dictionary if it's an object
        if hasattr(args, '__dict__'):
            args_dict = {k: v for k, v in vars(args).items() 
                        if not k.startswith('_') and k != 'func'}
        else:
            args_dict = dict(args) if isinstance(args, dict) else {}
        
        # Format arguments for display
        pretty_args = {k: (v if v is not None else "default") 
                      for k, v in args_dict.items()}
        args_str = ", ".join(f"{k}={v}" for k, v in pretty_args.items())
        
        # Console output for args (always shown regardless of log level)
        if self.console and RICH_AVAILABLE:
            self.console.print(f"[bold cyan]Args:[/bold cyan] {args_str}")
        else:
            print(f"Args: {args_str}")
        
        # File logging with masking
        masked_args_str = self._mask_message(f"Args: {args_str}")
        self.logger.info(masked_args_str)
    
    def log_info_file_only(self, message: str) -> None:
        """
        Log INFO message to file only (not console).
        
        Args:
            message: Message to log to file
        """
        masked_message = self._mask_message(message)
        self.logger.info(masked_message)
    
    def log_error(self, message: str) -> None:
        """
        Log ERROR message to both console and file.
        
        Args:
            message: Error message to log
        """
        masked_message = self._mask_message(message)
        self.logger.error(masked_message)
        
        # Also display on console with Rich formatting if available
        if self.console and RICH_AVAILABLE:
            self.console.print(f"[bold red]ERROR:[/bold red] {message}")
        else:
            print(f"ERROR: {message}")
    
    def log_critical(self, message: str) -> None:
        """
        Log CRITICAL message to both console and file.
        
        Args:
            message: Critical message to log
        """
        masked_message = self._mask_message(message)
        self.logger.critical(masked_message)
        
        # Also display on console with Rich formatting if available
        if self.console and RICH_AVAILABLE:
            self.console.print(f"[bold red]CRITICAL:[/bold red] {message}")
        else:
            print(f"CRITICAL: {message}")
    
    def log_warning(self, message: str) -> None:
        """
        Log WARNING message to file only.
        
        Args:
            message: Warning message to log
        """
        masked_message = self._mask_message(message)
        self.logger.warning(masked_message)
    
    def log_debug(self, message: str) -> None:
        """
        Log DEBUG message to file only.
        
        Args:
            message: Debug message to log
        """
        masked_message = self._mask_message(message)
        self.logger.debug(masked_message)
    
    def cleanup_old_logs(self) -> None:
        """Clean up old log files beyond the retention limit."""
        try:
            log_dir = Path(self.log_file_path).parent
            if not log_dir.exists():
                return
            
            # Find all IC log files
            log_files = list(log_dir.glob('ic_*.log*'))
            
            # Sort by modification time (oldest first)
            log_files.sort(key=lambda f: f.stat().st_mtime)
            
            # Remove files beyond retention limit
            if len(log_files) > self.max_files:
                files_to_remove = log_files[:-self.max_files]
                for log_file in files_to_remove:
                    try:
                        log_file.unlink()
                        self.log_debug(f"Removed old log file: {log_file}")
                    except OSError as e:
                        self.log_warning(f"Failed to remove log file {log_file}: {e}")
                        
        except Exception as e:
            self.log_warning(f"Failed to cleanup old logs: {e}")
    
    def get_log_file_path(self) -> str:
        """Get current log file path."""
        return self.log_file_path
    
    def get_logger(self) -> logging.Logger:
        """Get the underlying logger instance."""
        return self.logger


# Global logger instance
_global_logger: Optional[ICLogger] = None


def get_logger(config: Optional[Dict[str, Any]] = None) -> ICLogger:
    """
    Get or create global logger instance.
    
    Args:
        config: Configuration dictionary for logger initialization
        
    Returns:
        ICLogger instance
    """
    global _global_logger
    
    if _global_logger is None or config is not None:
        _global_logger = ICLogger(config)
    
    return _global_logger


def init_logger(config: Dict[str, Any]) -> ICLogger:
    """
    Initialize global logger with configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Initialized ICLogger instance
    """
    global _global_logger
    _global_logger = ICLogger(config)
    return _global_logger