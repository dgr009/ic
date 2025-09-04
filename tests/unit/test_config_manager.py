"""
Unit tests for ConfigManager class.

Tests configuration loading, validation, merging, and security integration.
"""

import os
import json
import yaml
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from src.ic.config.manager import ConfigManager
from src.ic.config.security import SecurityManager


class TestConfigManager:
    """Test cases for ConfigManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.sample_config = {
            "version": "1.0",
            "logging": {
                "console_level": "ERROR",
                "file_level": "INFO",
                "file_path": "logs/ic_{date}.log",
                "max_files": 30
            },
            "aws": {
                "accounts": ["123456789012"],
                "regions": ["us-east-1"],
                "max_workers": 10
            },
            "security": {
                "sensitive_keys": ["password", "token", "key"],
                "mask_pattern": "***MASKED***"
            }
        }
    
    def test_config_manager_initialization(self):
        """Test ConfigManager initialization."""
        manager = ConfigManager()
        assert manager.config_data == {}
        assert manager.config_sources == []
        assert manager.security_manager is None
        
        # Test with security manager
        manager_with_security = ConfigManager(security_manager=self.security_manager)
        assert manager_with_security.security_manager == self.security_manager
    
    def test_get_default_config(self):
        """Test default configuration generation."""
        manager = ConfigManager()
        default_config = manager._get_default_config()
        
        assert default_config["version"] == "1.0"
        assert "logging" in default_config
        assert "aws" in default_config
        assert "azure" in default_config
        assert "gcp" in default_config
        assert "security" in default_config
        
        # Test logging defaults
        assert default_config["logging"]["console_level"] == "ERROR"
        assert default_config["logging"]["file_level"] == "INFO"
        assert default_config["logging"]["mask_sensitive"] is True
        
        # Test AWS defaults
        assert default_config["aws"]["regions"] == ["ap-northeast-2"]
        assert default_config["aws"]["max_workers"] == 10
        
        # Test security defaults
        assert "password" in default_config["security"]["sensitive_keys"]
        assert default_config["security"]["mask_pattern"] == "***MASKED***"
    
    def test_load_config_file_yaml(self):
        """Test loading YAML configuration file."""
        manager = ConfigManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            temp_file = f.name
        
        try:
            config = manager._load_config_file(Path(temp_file))
            assert config == self.sample_config
        finally:
            os.unlink(temp_file)
    
    def test_load_config_file_json(self):
        """Test loading JSON configuration file."""
        manager = ConfigManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.sample_config, f)
            temp_file = f.name
        
        try:
            config = manager._load_config_file(Path(temp_file))
            assert config == self.sample_config
        finally:
            os.unlink(temp_file)
    
    def test_load_config_file_invalid_format(self):
        """Test loading configuration file with invalid format."""
        manager = ConfigManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("invalid config")
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Unsupported config file format"):
                manager._load_config_file(Path(temp_file))
        finally:
            os.unlink(temp_file)
    
    def test_load_env_config(self):
        """Test loading configuration from environment variables."""
        manager = ConfigManager()
        
        env_vars = {
            'IC_LOG_LEVEL': 'DEBUG',
            'AWS_REGION': 'us-west-2',
            'AWS_ACCOUNTS': '111111111111,222222222222',
            'AWS_MAX_WORKERS': '20',
            'AZURE_SUBSCRIPTIONS': 'sub1,sub2',
            'GCP_PROJECTS': 'project1,project2',
            'SLACK_ENABLED': 'true'
        }
        
        with patch.dict(os.environ, env_vars):
            env_config = manager._load_env_config()
        
        assert env_config['logging']['console_level'] == 'DEBUG'
        assert env_config['aws']['default_region'] == 'us-west-2'
        assert env_config['aws']['accounts'] == ['111111111111', '222222222222']
        assert env_config['aws']['max_workers'] == 20
        assert env_config['azure']['subscriptions'] == ['sub1', 'sub2']
        assert env_config['gcp']['projects'] == ['project1', 'project2']
        assert env_config['slack']['enabled'] is True
    
    def test_merge_configs(self):
        """Test configuration merging."""
        manager = ConfigManager()
        
        base_config = {
            "version": "1.0",
            "logging": {
                "console_level": "ERROR",
                "file_level": "INFO"
            },
            "aws": {
                "regions": ["us-east-1"],
                "max_workers": 10
            }
        }
        
        override_config = {
            "logging": {
                "console_level": "DEBUG"
            },
            "aws": {
                "max_workers": 20,
                "accounts": ["123456789012"]
            },
            "new_section": {
                "key": "value"
            }
        }
        
        merged = manager._merge_configs(base_config, override_config)
        
        assert merged["version"] == "1.0"
        assert merged["logging"]["console_level"] == "DEBUG"
        assert merged["logging"]["file_level"] == "INFO"
        assert merged["aws"]["regions"] == ["us-east-1"]
        assert merged["aws"]["max_workers"] == 20
        assert merged["aws"]["accounts"] == ["123456789012"]
        assert merged["new_section"]["key"] == "value"
    
    def test_set_nested_value(self):
        """Test setting nested configuration values."""
        manager = ConfigManager()
        config = {}
        
        manager._set_nested_value(config, ['logging', 'console_level'], 'DEBUG')
        manager._set_nested_value(config, ['aws', 'regions'], ['us-west-2'])
        manager._set_nested_value(config, ['simple_key'], 'simple_value')
        
        assert config['logging']['console_level'] == 'DEBUG'
        assert config['aws']['regions'] == ['us-west-2']
        assert config['simple_key'] == 'simple_value'
    
    @patch('pathlib.Path.exists')
    def test_load_config_with_security_validation(self, mock_exists):
        """Test configuration loading with security validation."""
        mock_exists.return_value = False  # No config files exist
        
        manager = ConfigManager(security_manager=self.security_manager)
        
        # Mock environment variables with sensitive data
        env_vars = {
            'AWS_SECRET_ACCESS_KEY': 'secret-key-12345',
            'AZURE_CLIENT_SECRET': 'client-secret-67890'
        }
        
        with patch.dict(os.environ, env_vars):
            with patch.object(manager.security_manager, 'validate_config_security') as mock_validate:
                mock_validate.return_value = ['Warning: sensitive data found']
                
                config = manager.load_config()
                
                # Verify security validation was called
                mock_validate.assert_called_once()
                assert config is not None
    
    def test_get_config_value(self):
        """Test getting configuration values using dot notation."""
        manager = ConfigManager()
        manager.config_data = self.sample_config
        
        assert manager.get_config_value('version') == '1.0'
        assert manager.get_config_value('logging.console_level') == 'ERROR'
        assert manager.get_config_value('aws.regions') == ['us-east-1']
        assert manager.get_config_value('nonexistent.key', 'default') == 'default'
        assert manager.get_config_value('aws.nonexistent', None) is None
    
    def test_set_config_value(self):
        """Test setting configuration values using dot notation."""
        manager = ConfigManager()
        manager.config_data = {}
        
        manager.set_config_value('logging.console_level', 'DEBUG')
        manager.set_config_value('aws.regions', ['us-west-2'])
        manager.set_config_value('simple_key', 'simple_value')
        
        assert manager.config_data['logging']['console_level'] == 'DEBUG'
        assert manager.config_data['aws']['regions'] == ['us-west-2']
        assert manager.config_data['simple_key'] == 'simple_value'
    
    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        manager = ConfigManager()
        errors = manager.validate_config(self.sample_config)
        
        assert len(errors) == 0
    
    def test_validate_config_invalid(self):
        """Test configuration validation with invalid config."""
        manager = ConfigManager()
        
        # Test with non-dict config
        errors = manager.validate_config("not a dict")
        assert "Configuration must be a dictionary" in errors
        
        # Test with missing required fields
        invalid_config = {"version": "1.0"}  # Missing required sections
        errors = manager.validate_config(invalid_config)
        assert any("missing required section" in error for error in errors)
        
        # Test with invalid logging config
        invalid_logging_config = {
            "version": "1.0",
            "logging": "not a dict",
            "aws": {},
            "azure": {},
            "gcp": {},
            "security": {}
        }
        errors = manager.validate_config(invalid_logging_config)
        assert "Logging configuration must be a dictionary" in errors
    
    def test_save_config_yaml(self):
        """Test saving configuration to YAML file."""
        manager = ConfigManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_file = f.name
        
        try:
            manager.save_config(temp_file, self.sample_config)
            
            # Verify file was created and contains correct data
            with open(temp_file, 'r') as f:
                saved_config = yaml.safe_load(f)
            
            assert saved_config == self.sample_config
        finally:
            os.unlink(temp_file)
    
    def test_save_config_json(self):
        """Test saving configuration to JSON file."""
        manager = ConfigManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            manager.save_config(temp_file, self.sample_config)
            
            # Verify file was created and contains correct data
            with open(temp_file, 'r') as f:
                saved_config = json.load(f)
            
            assert saved_config == self.sample_config
        finally:
            os.unlink(temp_file)
    
    def test_backup_config(self):
        """Test configuration backup functionality."""
        manager = ConfigManager()
        
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            temp_file = f.name
        
        try:
            backup_path = manager.backup_config(temp_file)
            
            assert backup_path is not None
            assert backup_path.exists()
            
            # Verify backup contains original data
            with open(backup_path, 'r') as f:
                backup_config = yaml.safe_load(f)
            
            assert backup_config == self.sample_config
            
            # Cleanup backup
            backup_path.unlink()
        finally:
            os.unlink(temp_file)
    
    def test_safe_update_config(self):
        """Test safe configuration update with backup."""
        manager = ConfigManager(security_manager=self.security_manager)
        
        # Create initial config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            temp_file = f.name
        
        try:
            # Update config
            updated_config = self.sample_config.copy()
            updated_config['logging']['console_level'] = 'DEBUG'
            
            success = manager.safe_update_config(temp_file, updated_config)
            
            assert success is True
            
            # Verify updated config
            with open(temp_file, 'r') as f:
                saved_config = yaml.safe_load(f)
            
            assert saved_config['logging']['console_level'] == 'DEBUG'
        finally:
            os.unlink(temp_file)
    
    def test_safe_update_config_with_security_issues(self):
        """Test safe configuration update with security validation failure."""
        manager = ConfigManager(security_manager=self.security_manager)
        
        # Create initial config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            temp_file = f.name
        
        try:
            # Create config with security issues
            insecure_config = self.sample_config.copy()
            insecure_config['aws']['secret_key'] = 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
            
            with patch.object(manager.security_manager, 'validate_config_security') as mock_validate:
                mock_validate.return_value = ['Critical: secret found in config']
                
                success = manager.safe_update_config(temp_file, insecure_config)
                
                # Should fail due to security issues
                assert success is False
        finally:
            os.unlink(temp_file)
    
    @patch('pathlib.Path.glob')
    def test_cleanup_old_backups(self, mock_glob):
        """Test cleanup of old backup files."""
        manager = ConfigManager()
        
        # Mock backup files
        mock_files = []
        for i in range(15):  # More than max_backups (10)
            mock_file = Mock()
            mock_file.stat.return_value.st_mtime = 1000000 + i  # Different timestamps
            mock_files.append(mock_file)
        
        mock_glob.return_value = mock_files
        
        manager.cleanup_old_backups(max_backups=10)
        
        # Verify oldest files were removed (first 5 files)
        for i in range(5):
            mock_files[i].unlink.assert_called_once()
        
        # Verify newer files were not removed
        for i in range(5, 15):
            mock_files[i].unlink.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__])