"""
Unit tests for ICLogger class.

Tests dual-level logging, sensitive data masking, and Rich console integration.
"""

import os
import logging
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock

from src.ic.core.logging import ICLogger, get_logger, init_logger
from src.ic.config.security import SecurityManager


class TestICLogger:
    """Test cases for ICLogger class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'file_path': 'logs/ic_{date}.log',
                'max_files': 30,
                'format': '%(asctime)s [%(levelname)s] - %(message)s',
                'mask_sensitive': True
            },
            'security': {
                'sensitive_keys': ['password', 'token', 'key'],
                'mask_pattern': '***MASKED***'
            }
        }
    
    def test_ic_logger_initialization(self):
        """Test ICLogger initialization."""
        logger = ICLogger(self.config)
        
        assert logger.config == self.config
        assert logger.logging_config == self.config['logging']
        assert logger.console_level == logging.ERROR
        assert logger.file_level == logging.INFO
        assert logger.max_files == 30
        assert logger.log_format == '%(asctime)s [%(levelname)s] - %(message)s'
        assert isinstance(logger.security_manager, SecurityManager)
        assert logger.logger is not None
    
    def test_ic_logger_initialization_without_config(self):
        """Test ICLogger initialization without configuration."""
        logger = ICLogger()
        
        assert logger.config == {}
        assert logger.logging_config == {}
        assert logger.console_level == logging.ERROR  # Default
        assert logger.file_level == logging.INFO  # Default
        assert logger.max_files == 30  # Default
    
    def test_get_log_file_path(self):
        """Test log file path generation."""
        logger = ICLogger(self.config)
        
        log_path = logger._get_log_file_path()
        
        assert 'logs/ic_' in log_path
        assert log_path.endswith('.log')
        assert '{date}' not in log_path  # Should be replaced with actual date
    
    @patch('pathlib.Path.mkdir')
    def test_get_log_file_path_creates_directory(self, mock_mkdir):
        """Test that log file path creation creates directory."""
        logger = ICLogger(self.config)
        
        logger._get_log_file_path()
        
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    
    @patch('src.ic.core.logging.RICH_AVAILABLE', True)
    @patch('src.ic.core.logging.RichHandler')
    @patch('logging.handlers.RotatingFileHandler')
    def test_setup_logger_with_rich(self, mock_file_handler, mock_rich_handler):
        """Test logger setup with Rich available."""
        mock_console_handler = Mock()
        mock_rich_handler.return_value = mock_console_handler
        
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance
        
        logger = ICLogger(self.config)
        
        # Verify Rich handler was created
        mock_rich_handler.assert_called_once()
        
        # Verify file handler was created
        mock_file_handler.assert_called_once()
        
        # Verify handlers were added to logger
        assert len(logger.logger.handlers) >= 2
    
    @patch('src.ic.core.logging.RICH_AVAILABLE', False)
    @patch('logging.StreamHandler')
    @patch('logging.handlers.RotatingFileHandler')
    def test_setup_logger_without_rich(self, mock_file_handler, mock_stream_handler):
        """Test logger setup without Rich available."""
        mock_console_handler = Mock()
        mock_stream_handler.return_value = mock_console_handler
        
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance
        
        logger = ICLogger(self.config)
        
        # Verify StreamHandler was created instead of RichHandler
        mock_stream_handler.assert_called_once()
        
        # Verify file handler was created
        mock_file_handler.assert_called_once()
    
    def test_mask_message_enabled(self):
        """Test message masking when enabled."""
        logger = ICLogger(self.config)
        
        message = "Connecting with password=secret123 to database"
        masked = logger._mask_message(message)
        
        assert 'password=***MASKED***' in masked
        assert 'secret123' not in masked
    
    def test_mask_message_disabled(self):
        """Test message masking when disabled."""
        config = self.config.copy()
        config['logging']['mask_sensitive'] = False
        
        logger = ICLogger(config)
        
        message = "Connecting with password=secret123 to database"
        masked = logger._mask_message(message)
        
        assert masked == message  # Should be unchanged
    
    @patch('src.ic.core.logging.RICH_AVAILABLE', True)
    def test_log_args_with_rich(self):
        """Test logging arguments with Rich console."""
        logger = ICLogger(self.config)
        logger.console = Mock()
        
        # Test with argparse-like object
        args = Mock()
        args.profile = 'test-profile'
        args.region = 'us-east-1'
        args.verbose = True
        args._private = 'should_be_ignored'
        args.func = 'should_be_ignored'
        
        logger.log_args(args)
        
        # Verify console output
        logger.console.print.assert_called_once()
        call_args = logger.console.print.call_args[0][0]
        assert 'Args:' in call_args
        assert 'profile=test-profile' in call_args
        assert 'region=us-east-1' in call_args
        assert 'verbose=True' in call_args
        assert '_private' not in call_args
        assert 'func' not in call_args
    
    @patch('src.ic.core.logging.RICH_AVAILABLE', False)
    @patch('builtins.print')
    def test_log_args_without_rich(self, mock_print):
        """Test logging arguments without Rich console."""
        logger = ICLogger(self.config)
        
        args = {'profile': 'test-profile', 'region': 'us-east-1'}
        
        logger.log_args(args)
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert 'Args:' in call_args
        assert 'profile=test-profile' in call_args
        assert 'region=us-east-1' in call_args
    
    def test_log_args_with_none_values(self):
        """Test logging arguments with None values."""
        logger = ICLogger(self.config)
        logger.console = Mock()
        
        args = {'profile': None, 'region': 'us-east-1', 'verbose': None}
        
        logger.log_args(args)
        
        # Verify None values are replaced with "default"
        call_args = logger.console.print.call_args[0][0]
        assert 'profile=default' in call_args
        assert 'region=us-east-1' in call_args
        assert 'verbose=default' in call_args
    
    def test_log_info_file_only(self):
        """Test logging INFO messages to file only."""
        logger = ICLogger(self.config)
        logger.logger = Mock()
        
        message = "Operation completed successfully"
        logger.log_info_file_only(message)
        
        # Verify logger.info was called with masked message
        logger.logger.info.assert_called_once()
        call_args = logger.logger.info.call_args[0][0]
        assert message in call_args
    
    def test_log_info_file_only_with_sensitive_data(self):
        """Test logging INFO messages with sensitive data masking."""
        logger = ICLogger(self.config)
        logger.logger = Mock()
        
        message = "Connected with password=secret123"
        logger.log_info_file_only(message)
        
        # Verify sensitive data was masked
        logger.logger.info.assert_called_once()
        call_args = logger.logger.info.call_args[0][0]
        assert 'password=***MASKED***' in call_args
        assert 'secret123' not in call_args
    
    @patch('src.ic.core.logging.RICH_AVAILABLE', True)
    def test_log_error_with_rich(self):
        """Test logging ERROR messages with Rich console."""
        logger = ICLogger(self.config)
        logger.logger = Mock()
        logger.console = Mock()
        
        message = "Database connection failed"
        logger.log_error(message)
        
        # Verify both logger and console were called
        logger.logger.error.assert_called_once()
        logger.console.print.assert_called_once()
        
        # Verify console formatting
        console_call_args = logger.console.print.call_args[0][0]
        assert 'ERROR:' in console_call_args
        assert message in console_call_args
    
    @patch('src.ic.core.logging.RICH_AVAILABLE', False)
    @patch('builtins.print')
    def test_log_error_without_rich(self, mock_print):
        """Test logging ERROR messages without Rich console."""
        logger = ICLogger(self.config)
        logger.logger = Mock()
        
        message = "Database connection failed"
        logger.log_error(message)
        
        # Verify both logger and print were called
        logger.logger.error.assert_called_once()
        mock_print.assert_called_once()
        
        # Verify print formatting
        print_call_args = mock_print.call_args[0][0]
        assert 'ERROR:' in print_call_args
        assert message in print_call_args
    
    @patch('src.ic.core.logging.RICH_AVAILABLE', True)
    def test_log_critical_with_rich(self):
        """Test logging CRITICAL messages with Rich console."""
        logger = ICLogger(self.config)
        logger.logger = Mock()
        logger.console = Mock()
        
        message = "System failure detected"
        logger.log_critical(message)
        
        # Verify both logger and console were called
        logger.logger.critical.assert_called_once()
        logger.console.print.assert_called_once()
        
        # Verify console formatting
        console_call_args = logger.console.print.call_args[0][0]
        assert 'CRITICAL:' in console_call_args
        assert message in console_call_args
    
    def test_log_warning(self):
        """Test logging WARNING messages (file only)."""
        logger = ICLogger(self.config)
        logger.logger = Mock()
        
        message = "Configuration file not found, using defaults"
        logger.log_warning(message)
        
        # Verify only logger was called (no console output)
        logger.logger.warning.assert_called_once()
        call_args = logger.logger.warning.call_args[0][0]
        assert message in call_args
    
    def test_log_debug(self):
        """Test logging DEBUG messages (file only)."""
        logger = ICLogger(self.config)
        logger.logger = Mock()
        
        message = "Processing item 1 of 100"
        logger.log_debug(message)
        
        # Verify only logger was called (no console output)
        logger.logger.debug.assert_called_once()
        call_args = logger.logger.debug.call_args[0][0]
        assert message in call_args
    
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.unlink')
    def test_cleanup_old_logs(self, mock_unlink, mock_stat, mock_glob):
        """Test cleanup of old log files."""
        logger = ICLogger(self.config)
        
        # Mock log files with different timestamps
        mock_files = []
        for i in range(35):  # More than max_files (30)
            mock_file = Mock()
            mock_file.stat.return_value.st_mtime = 1000000 + i  # Different timestamps
            mock_files.append(mock_file)
        
        mock_glob.return_value = mock_files
        
        logger.cleanup_old_logs()
        
        # Verify oldest files were removed (first 5 files)
        for i in range(5):
            mock_files[i].unlink.assert_called_once()
        
        # Verify newer files were not removed
        for i in range(5, 35):
            mock_files[i].unlink.assert_not_called()
    
    @patch('pathlib.Path.exists')
    def test_cleanup_old_logs_no_directory(self, mock_exists):
        """Test cleanup when log directory doesn't exist."""
        mock_exists.return_value = False
        
        logger = ICLogger(self.config)
        
        # Should not raise exception
        logger.cleanup_old_logs()
    
    @patch('pathlib.Path.glob')
    def test_cleanup_old_logs_error_handling(self, mock_glob):
        """Test cleanup with error handling."""
        logger = ICLogger(self.config)
        logger.logger = Mock()
        
        # Mock glob to raise exception
        mock_glob.side_effect = Exception("Permission denied")
        
        # Should not raise exception, just log warning
        logger.cleanup_old_logs()
        
        # Verify warning was logged
        logger.logger.warning.assert_called()
    
    def test_get_log_file_path_method(self):
        """Test getting current log file path."""
        logger = ICLogger(self.config)
        
        log_path = logger.get_log_file_path()
        
        assert log_path == logger.log_file_path
        assert isinstance(log_path, str)
    
    def test_get_logger_method(self):
        """Test getting underlying logger instance."""
        logger = ICLogger(self.config)
        
        underlying_logger = logger.get_logger()
        
        assert underlying_logger == logger.logger
        assert isinstance(underlying_logger, logging.Logger)


class TestGlobalLoggerFunctions:
    """Test cases for global logger functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset global logger
        import src.ic.core.logging
        src.ic.core.logging._global_logger = None
    
    def test_get_logger_first_call(self):
        """Test getting logger on first call."""
        config = {'logging': {'console_level': 'DEBUG'}}
        
        logger = get_logger(config)
        
        assert isinstance(logger, ICLogger)
        assert logger.config == config
    
    def test_get_logger_subsequent_calls(self):
        """Test getting logger on subsequent calls."""
        config = {'logging': {'console_level': 'DEBUG'}}
        
        logger1 = get_logger(config)
        logger2 = get_logger()  # No config provided
        
        # Should return same instance
        assert logger1 is logger2
    
    def test_get_logger_with_new_config(self):
        """Test getting logger with new configuration."""
        config1 = {'logging': {'console_level': 'DEBUG'}}
        config2 = {'logging': {'console_level': 'ERROR'}}
        
        logger1 = get_logger(config1)
        logger2 = get_logger(config2)  # New config provided
        
        # Should create new instance with new config
        assert logger1 is not logger2
        assert logger2.config == config2
    
    def test_init_logger(self):
        """Test initializing global logger."""
        config = {'logging': {'console_level': 'WARNING'}}
        
        logger = init_logger(config)
        
        assert isinstance(logger, ICLogger)
        assert logger.config == config
        
        # Subsequent get_logger calls should return same instance
        logger2 = get_logger()
        assert logger is logger2


class TestICLoggerIntegration:
    """Integration tests for ICLogger with real logging."""
    
    def test_real_logging_to_file(self):
        """Test actual logging to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, 'test.log')
            config = {
                'logging': {
                    'console_level': 'ERROR',
                    'file_level': 'INFO',
                    'file_path': log_file,
                    'max_files': 5,
                    'format': '%(asctime)s [%(levelname)s] - %(message)s',
                    'mask_sensitive': True
                }
            }
            
            logger = ICLogger(config)
            
            # Log various levels
            logger.log_info_file_only("Info message")
            logger.log_warning("Warning message")
            logger.log_error("Error message")
            logger.log_debug("Debug message")
            
            # Verify file was created and contains logs
            assert os.path.exists(log_file)
            
            with open(log_file, 'r') as f:
                content = f.read()
            
            assert "Info message" in content
            assert "Warning message" in content
            assert "Error message" in content
            assert "Debug message" in content
            assert "[INFO]" in content
            assert "[WARNING]" in content
            assert "[ERROR]" in content
            assert "[DEBUG]" in content
    
    def test_sensitive_data_masking_integration(self):
        """Test sensitive data masking in real logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, 'test.log')
            config = {
                'logging': {
                    'file_path': log_file,
                    'mask_sensitive': True
                },
                'security': {
                    'sensitive_keys': ['password', 'token'],
                    'mask_pattern': '***MASKED***'
                }
            }
            
            logger = ICLogger(config)
            
            # Log message with sensitive data
            logger.log_info_file_only("Login with password=secret123 successful")
            
            # Verify sensitive data was masked in file
            with open(log_file, 'r') as f:
                content = f.read()
            
            assert "password=***MASKED***" in content
            assert "secret123" not in content


if __name__ == '__main__':
    pytest.main([__file__])