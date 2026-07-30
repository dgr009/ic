"""
Unit tests for SecurityManager class.

Tests sensitive data detection, masking, and Git security validation.
"""

import os
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from ic.config.security import SecurityManager, GitSecurityChecker, create_security_config


class TestSecurityManager:
    """Test cases for SecurityManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            'sensitive_keys': ['password', 'token', 'key', 'secret'],
            'mask_pattern': '***MASKED***',
            'warn_on_sensitive_in_config': True
        }
        self.security_manager = SecurityManager(self.config)
    
    def test_security_manager_initialization(self):
        """Test SecurityManager initialization."""
        # Test with config
        manager = SecurityManager(self.config)
        assert manager.sensitive_keys == self.config['sensitive_keys']
        assert manager.mask_pattern == self.config['mask_pattern']
        assert manager.warn_on_sensitive is True
        
        # Test without config (defaults)
        manager_default = SecurityManager()
        assert 'password' in manager_default.sensitive_keys
        assert 'token' in manager_default.sensitive_keys
        assert manager_default.mask_pattern == '***MASKED***'
    
    def test_is_sensitive_key(self):
        """Test sensitive key detection."""
        assert self.security_manager._is_sensitive_key('password') is True
        assert self.security_manager._is_sensitive_key('PASSWORD') is True
        assert self.security_manager._is_sensitive_key('api_token') is True
        assert self.security_manager._is_sensitive_key('secret_key') is True
        assert self.security_manager._is_sensitive_key('username') is False
        assert self.security_manager._is_sensitive_key('region') is False
    
    def test_looks_like_secret(self):
        """Test secret pattern detection."""
        # Test various secret patterns
        assert self.security_manager._looks_like_secret('sk-1234567890abcdefghijklmnopqrstuvwxyz') is True
        assert self.security_manager._looks_like_secret('xoxb-1234567890-abcdefghijklmnopqrstuvwxyz') is True
        assert self.security_manager._looks_like_secret('ghp_1234567890abcdefghijklmnopqrstuvwxyz') is True
        assert self.security_manager._looks_like_secret('gho_1234567890abcdefghijklmnopqrstuvwxyz') is True
        
        # Base64-like strings
        assert self.security_manager._looks_like_secret('YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY3ODkw') is True
        
        # Hex strings
        assert self.security_manager._looks_like_secret('a1b2c3d4e5f6789012345678901234567890abcdef') is True
        
        # Regular strings should not be detected
        assert self.security_manager._looks_like_secret('regular-string') is False
        assert self.security_manager._looks_like_secret('short') is False
        assert self.security_manager._looks_like_secret('') is False
    
    def test_mask_sensitive_data_dict(self):
        """Test masking sensitive data in dictionaries."""
        data = {
            'username': 'testuser',
            'password': 'secret123',
            'api_token': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
            'config': {
                'database_password': 'dbsecret',
                'region': 'us-east-1'
            },
            'normal_key': 'normal_value'
        }
        
        masked = self.security_manager.mask_sensitive_data(data)
        
        assert masked['username'] == 'testuser'
        assert masked['password'] == '***MASKED***'
        assert masked['api_token'] == '***MASKED***'
        assert masked['config']['database_password'] == '***MASKED***'
        assert masked['config']['region'] == 'us-east-1'
        assert masked['normal_key'] == 'normal_value'
    
    def test_mask_sensitive_data_list(self):
        """Test masking sensitive data in lists."""
        data = [
            {'password': 'secret1'},
            {'username': 'user1'},
            'sk-1234567890abcdefghijklmnopqrstuvwxyz',
            'normal-string'
        ]
        
        masked = self.security_manager.mask_sensitive_data(data)
        
        assert masked[0]['password'] == '***MASKED***'
        assert masked[1]['username'] == 'user1'
        assert masked[2] == '***MASKED***'
        assert masked[3] == 'normal-string'
    
    def test_mask_sensitive_data_string(self):
        """Test masking sensitive data in strings."""
        # Secret-like strings should be masked
        secret_string = 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
        masked = self.security_manager.mask_sensitive_data(secret_string)
        assert masked == '***MASKED***'
        
        # Normal strings should not be masked
        normal_string = 'normal-string'
        masked = self.security_manager.mask_sensitive_data(normal_string)
        assert masked == 'normal-string'
    
    def test_mask_sensitive_data_other_types(self):
        """Test masking with other data types."""
        # Numbers should pass through unchanged
        assert self.security_manager.mask_sensitive_data(123) == 123
        assert self.security_manager.mask_sensitive_data(45.67) == 45.67
        
        # Booleans should pass through unchanged
        assert self.security_manager.mask_sensitive_data(True) is True
        assert self.security_manager.mask_sensitive_data(False) is False
        
        # None should pass through unchanged
        assert self.security_manager.mask_sensitive_data(None) is None
    
    def test_validate_config_security(self):
        """Test configuration security validation."""
        config_data = {
            'database': {
                'host': 'localhost',
                'password': 'dbpassword123',
                'port': 5432
            },
            'api': {
                'token': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
                'endpoint': 'https://api.example.com'
            },
            'settings': {
                'debug': True,
                'timeout': 30
            }
        }
        
        warnings = self.security_manager.validate_config_security(config_data)
        
        assert len(warnings) >= 2  # Should find password and token
        assert any('database.password' in warning for warning in warnings)
        assert any('api.token' in warning for warning in warnings)
    
    def test_validate_config_security_with_placeholders(self):
        """Test security validation with placeholder values."""
        config_data = {
            'database': {
                'password': 'your-password-here',
                'token': '<your-token>',
                'secret': '[REPLACE_WITH_SECRET]'
            }
        }
        
        # Mock _is_placeholder_value to return True for these values
        with patch.object(self.security_manager, '_is_placeholder_value', return_value=True):
            warnings = self.security_manager.validate_config_security(config_data)
            
            # Should not generate warnings for placeholder values
            assert len(warnings) == 0
    
    def test_is_placeholder_value(self):
        """Test placeholder value detection."""
        assert self.security_manager._is_placeholder_value('your-password-here') is True
        assert self.security_manager._is_placeholder_value('<your-token>') is True
        assert self.security_manager._is_placeholder_value('[REPLACE_ME]') is True
        assert self.security_manager._is_placeholder_value('TODO: add password') is True
        assert self.security_manager._is_placeholder_value('CHANGE_THIS_PASSWORD') is True
        assert self.security_manager._is_placeholder_value('example-key') is True
        assert self.security_manager._is_placeholder_value('placeholder-value') is True
        
        # Real values should not be detected as placeholders
        assert self.security_manager._is_placeholder_value('sk-1234567890abcdefghijklmnopqrstuvwxyz') is False
        assert self.security_manager._is_placeholder_value('real-password-123') is False
    
    def test_create_gitignore_entries(self):
        """Test .gitignore entries generation."""
        entries = self.security_manager.create_gitignore_entries()
        
        assert '# IC Configuration - Security' in entries
        assert 'config.yaml' in entries
        assert '.env' in entries
        assert '*.key' in entries
        assert '*.pem' in entries
        assert '.aws/credentials' in entries
        assert 'gcp-key/' in entries
        assert '.azure/' in entries
        assert '.oci/config' in entries
        assert 'logs/' in entries
        assert '.DS_Store' in entries
    
    def test_mask_log_message(self):
        """Test log message masking."""
        # Test various credential patterns in log messages
        message1 = "Connecting with password=secret123 to database"
        masked1 = self.security_manager.mask_log_message(message1)
        assert 'password=***MASKED***' in masked1
        
        message2 = "Using API token: sk-1234567890abcdefghijklmnopqrstuvwxyz"
        masked2 = self.security_manager.mask_log_message(message2)
        assert 'token=***MASKED***' in masked2
        
        message3 = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        masked3 = self.security_manager.mask_log_message(message3)
        assert 'Bearer ***MASKED***' in masked3
        
        message4 = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
        masked4 = self.security_manager.mask_log_message(message4)
        assert 'Basic ***MASKED***' in masked4
        
        # Normal messages should not be changed
        normal_message = "Processing request for user john"
        masked_normal = self.security_manager.mask_log_message(normal_message)
        assert masked_normal == normal_message
    
    def test_mask_sensitive_in_text(self):
        """Test sensitive data masking in text (alias for mask_log_message)."""
        text = "password=secret123 and token=abc123"
        masked = self.security_manager.mask_sensitive_in_text(text)
        assert 'password=***MASKED***' in masked


class TestGitSecurityChecker:
    """Test cases for GitSecurityChecker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.git_checker = GitSecurityChecker(self.security_manager)
    
    def test_git_security_checker_initialization(self):
        """Test GitSecurityChecker initialization."""
        checker = GitSecurityChecker(self.security_manager)
        assert checker.security == self.security_manager
    
    def test_should_check_file(self):
        """Test file checking criteria."""
        # Should check these files
        assert self.git_checker._should_check_file('config.yaml') is True
        assert self.git_checker._should_check_file('src/main.py') is True
        assert self.git_checker._should_check_file('README.md') is True
        
        # Should not check these files
        assert self.git_checker._should_check_file('binary.exe') is False
        assert self.git_checker._should_check_file('image.jpg') is False
        assert self.git_checker._should_check_file('__pycache__/module.pyc') is False
        assert self.git_checker._should_check_file('.git/config') is False
        assert self.git_checker._should_check_file('node_modules/package.json') is False
        assert self.git_checker._should_check_file('logs/app.log') is False
    
    def test_contains_secrets(self):
        """Test secret detection in file content."""
        # Content with secrets
        secret_content = """
        database_password = "secret123456"
        api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
        access_token = "xoxb-1234567890-abcdefghijklmnopqrstuvwxyz"
        private_key = "-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC..."
        aws_access_key = "AKIA1234567890ABCDEF"
        """
        
        assert self.git_checker._contains_secrets(secret_content) is True
        
        # Content without secrets
        normal_content = """
        database_host = "localhost"
        api_endpoint = "https://api.example.com"
        username = "testuser"
        timeout = 30
        """
        
        assert self.git_checker._contains_secrets(normal_content) is False
    
    @patch('subprocess.run')
    def test_check_staged_files_success(self, mock_run):
        """Test checking staged files successfully."""
        # Mock git diff output
        mock_run.return_value.stdout = "config.yaml\nsrc/main.py\nREADME.md"
        mock_run.return_value.returncode = 0
        
        # Mock file content reading
        file_contents = {
            'config.yaml': 'host: localhost\nport: 5432',
            'src/main.py': 'print("Hello World")',
            'README.md': '# Project README'
        }
        
        with patch('builtins.open', mock_open()) as mock_file:
            def side_effect(filename, *args, **kwargs):
                mock_file.return_value.read.return_value = file_contents.get(filename, '')
                return mock_file.return_value
            
            mock_file.side_effect = side_effect
            
            warnings = self.git_checker.check_staged_files()
            
            assert isinstance(warnings, list)
            # Should not find secrets in normal content
            assert len(warnings) == 0
    
    @patch('subprocess.run')
    def test_check_staged_files_with_secrets(self, mock_run):
        """Test checking staged files with secrets."""
        # Mock git diff output
        mock_run.return_value.stdout = "config.yaml"
        mock_run.return_value.returncode = 0
        
        # Mock file with secrets
        secret_content = 'password = "secret123456"'
        
        with patch('builtins.open', mock_open(read_data=secret_content)):
            warnings = self.git_checker.check_staged_files()
            
            assert len(warnings) > 0
            assert any('config.yaml' in warning for warning in warnings)
    
    @patch('subprocess.run')
    def test_check_staged_files_git_error(self, mock_run):
        """Test checking staged files when git command fails."""
        # Mock git command failure
        mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
        
        warnings = self.git_checker.check_staged_files()
        
        # Should return empty list when git fails
        assert warnings == []
    
    def test_generate_pre_commit_hook(self):
        """Test pre-commit hook script generation."""
        hook_content = self.git_checker._generate_pre_commit_hook()
        
        assert '#!/bin/bash' in hook_content
        assert 'IC Security Pre-commit Hook' in hook_content
        assert 'git diff --cached --name-only' in hook_content
        assert 'credentials|service-account' in hook_content
        assert 'password|token|secret|key' in hook_content
        assert 'Security checks passed' in hook_content
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.chmod')
    def test_install_pre_commit_hook_success(self, mock_chmod, mock_file, mock_exists):
        """Test successful pre-commit hook installation."""
        # Mock .git directory exists
        mock_exists.return_value = True
        
        result = self.git_checker.install_pre_commit_hook()
        
        assert result is True
        mock_file.assert_called()
        assert mock_chmod.called
    
    @patch('pathlib.Path.exists')
    def test_install_pre_commit_hook_no_git(self, mock_exists):
        """Test pre-commit hook installation when not in git repository."""
        # Mock .git directory doesn't exist
        mock_exists.return_value = False
        
        result = self.git_checker.install_pre_commit_hook()
        
        assert result is False
    
    def test_check_file_content_with_secrets(self):
        """Test checking individual file content for secrets."""
        secret_content = 'api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
        
        with patch('builtins.open', mock_open(read_data=secret_content)):
            warnings = self.git_checker._check_file_content('test.py')
            
            assert len(warnings) > 0
            assert 'test.py' in warnings[0]
    
    def test_check_file_content_without_secrets(self):
        """Test checking individual file content without secrets."""
        normal_content = 'print("Hello World")\nusername = "testuser"'
        
        with patch('builtins.open', mock_open(read_data=normal_content)):
            warnings = self.git_checker._check_file_content('test.py')
            
            assert len(warnings) == 0
    
    def test_check_file_content_read_error(self):
        """Test checking file content when file read fails."""
        with patch('builtins.open', side_effect=IOError("File not found")):
            warnings = self.git_checker._check_file_content('nonexistent.py')
            
            # Should not raise exception, just return empty warnings
            assert warnings == []


class TestSecurityConfigCreation:
    """Test cases for security configuration creation."""
    
    def test_create_security_config(self):
        """Test creating default security configuration."""
        config = create_security_config()
        
        assert 'sensitive_keys' in config
        assert 'mask_pattern' in config
        assert 'warn_on_sensitive_in_config' in config
        assert 'git_hooks_enabled' in config
        
        # Test default values
        assert 'password' in config['sensitive_keys']
        assert 'token' in config['sensitive_keys']
        assert 'key' in config['sensitive_keys']
        assert config['mask_pattern'] == '***MASKED***'
        assert config['warn_on_sensitive_in_config'] is True
        assert config['git_hooks_enabled'] is True


if __name__ == '__main__':
    pytest.main([__file__])