"""
Integration tests for security validation and Git pre-commit hooks.

Tests end-to-end security validation workflows and Git integration.
"""

import os
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.ic.config.security import SecurityManager, GitSecurityChecker
from src.ic.config.manager import ConfigManager


class TestSecurityValidationIntegration:
    """Integration tests for security validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.git_checker = GitSecurityChecker(self.security_manager)
        self.config_manager = ConfigManager(security_manager=self.security_manager)
    
    def create_temp_git_repo(self):
        """Create temporary Git repository for testing."""
        temp_dir = tempfile.mkdtemp()
        
        # Initialize git repository
        subprocess.run(['git', 'init'], cwd=temp_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_dir, capture_output=True)
        
        return temp_dir
    
    def test_git_security_validation_integration(self):
        """Test Git security validation with real repository."""
        temp_repo = self.create_temp_git_repo()
        
        try:
            # Create files with and without sensitive data
            safe_file = Path(temp_repo) / 'safe_config.py'
            with open(safe_file, 'w') as f:
                f.write("""
# Safe configuration file
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DEBUG = True
""")
            
            sensitive_file = Path(temp_repo) / 'sensitive_config.py'
            with open(sensitive_file, 'w') as f:
                f.write("""
# Configuration with sensitive data
DATABASE_PASSWORD = "secret123456"
API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
""")
            
            # Add files to git
            subprocess.run(['git', 'add', 'safe_config.py'], cwd=temp_repo, capture_output=True)
            subprocess.run(['git', 'add', 'sensitive_config.py'], cwd=temp_repo, capture_output=True)
            
            # Change to repo directory for git operations
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                # Check staged files
                warnings = self.git_checker.check_staged_files()
                
                # Should detect sensitive data in sensitive_config.py
                assert len(warnings) > 0
                assert any('sensitive_config.py' in warning for warning in warnings)
                
                # Should not warn about safe_config.py
                assert not any('safe_config.py' in warning for warning in warnings)
                
            finally:
                os.chdir(original_cwd)
                
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(temp_repo)
    
    def test_pre_commit_hook_installation_integration(self):
        """Test pre-commit hook installation and execution."""
        temp_repo = self.create_temp_git_repo()
        
        try:
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                # Install pre-commit hook
                success = self.git_checker.install_pre_commit_hook()
                assert success is True
                
                # Verify hook file was created
                hook_file = Path(temp_repo) / '.git' / 'hooks' / 'pre-commit'
                assert hook_file.exists()
                
                # Verify hook is executable
                assert os.access(hook_file, os.X_OK)
                
                # Verify hook content
                with open(hook_file, 'r') as f:
                    hook_content = f.read()
                
                assert '#!/bin/bash' in hook_content
                assert 'IC Security Pre-commit Hook' in hook_content
                assert 'git diff --cached --name-only' in hook_content
                
            finally:
                os.chdir(original_cwd)
                
        finally:
            import shutil
            shutil.rmtree(temp_repo)
    
    def test_configuration_security_validation_integration(self):
        """Test configuration security validation end-to-end."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create configuration with sensitive data
            sensitive_config = {
                "version": "1.0",
                "database": {
                    "host": "localhost",
                    "password": "secret123456",
                    "port": 5432
                },
                "api": {
                    "endpoint": "https://api.example.com",
                    "token": "sk-1234567890abcdefghijklmnopqrstuvwxyz"
                },
                "aws": {
                    "access_key": "AKIA1234567890ABCDEF",
                    "secret_key": "secret123456789012345678901234567890"
                },
                "github": {
                    "token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
                }
            }
            
            config_file = Path(temp_dir) / 'config.yaml'
            self.config_manager.save_config(config_file, sensitive_config)
            
            # Load configuration with security validation
            with patch('logging.Logger.warning') as mock_warning:
                config = self.config_manager.load_config([config_file])
                
                # Verify security warnings were logged
                warning_calls = [call[0][0] for call in mock_warning.call_args_list]
                security_warnings = [w for w in warning_calls if 'sensitive data' in w.lower()]
                
                assert len(security_warnings) > 0
                
                # Should warn about multiple sensitive fields
                assert any('database.password' in warning for warning in security_warnings)
                assert any('api.token' in warning for warning in security_warnings)
                assert any('aws.access_key' in warning for warning in security_warnings)
                assert any('github.token' in warning for warning in security_warnings)
    
    def test_safe_config_update_with_security_validation(self):
        """Test safe configuration update with security validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create initial safe configuration
            safe_config = {
                "version": "1.0",
                "database": {
                    "host": "localhost",
                    "port": 5432
                },
                "api": {
                    "endpoint": "https://api.example.com"
                }
            }
            
            config_file = Path(temp_dir) / 'config.yaml'
            self.config_manager.save_config(config_file, safe_config)
            
            # Try to update with sensitive data
            unsafe_config = safe_config.copy()
            unsafe_config['database']['password'] = 'secret123456'
            unsafe_config['api']['token'] = 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
            
            # Safe update should detect security issues
            with patch('logging.Logger.error') as mock_error:
                success = self.config_manager.safe_update_config(config_file, unsafe_config)
                
                # Update should fail due to security issues
                assert success is False
                
                # Should log security errors
                error_calls = [call[0][0] for call in mock_error.call_args_list]
                assert any('security issues' in error.lower() for error in error_calls)
            
            # Original safe configuration should be preserved
            preserved_config = self.config_manager._load_config_file(config_file)
            assert 'password' not in preserved_config['database']
            assert 'token' not in preserved_config['api']
    
    def test_gitignore_generation_integration(self):
        """Test .gitignore generation for security."""
        gitignore_entries = self.security_manager.create_gitignore_entries()
        
        # Verify comprehensive security entries
        assert '# IC Configuration - Security' in gitignore_entries
        assert 'config.yaml' in gitignore_entries
        assert '.env' in gitignore_entries
        assert '*.key' in gitignore_entries
        assert '*.pem' in gitignore_entries
        assert '.aws/credentials' in gitignore_entries
        assert 'gcp-key/' in gitignore_entries
        assert '.azure/' in gitignore_entries
        assert 'logs/' in gitignore_entries
        
        # Test creating actual .gitignore file
        with tempfile.TemporaryDirectory() as temp_dir:
            gitignore_file = Path(temp_dir) / '.gitignore'
            
            with open(gitignore_file, 'w') as f:
                for entry in gitignore_entries:
                    f.write(f"{entry}\n")
            
            # Verify file was created
            assert gitignore_file.exists()
            
            # Verify content
            with open(gitignore_file, 'r') as f:
                content = f.read()
            
            assert 'config.yaml' in content
            assert '.env' in content
            assert '*.key' in content
    
    def test_sensitive_data_masking_integration(self):
        """Test sensitive data masking in various contexts."""
        # Test configuration masking
        sensitive_data = {
            'user': 'testuser',
            'password': 'secret123',
            'api_token': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
            'config': {
                'database_password': 'dbsecret',
                'github_token': 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'
            },
            'list_with_secrets': [
                'normal_value',
                'sk-1234567890abcdefghijklmnopqrstuvwxyz',
                {'nested_secret': 'secret456'}
            ]
        }
        
        masked_data = self.security_manager.mask_sensitive_data(sensitive_data)
        
        # Verify masking
        assert masked_data['user'] == 'testuser'  # Not sensitive
        assert masked_data['password'] == '***MASKED***'
        assert masked_data['api_token'] == '***MASKED***'
        assert masked_data['config']['database_password'] == '***MASKED***'
        assert masked_data['config']['github_token'] == '***MASKED***'
        assert masked_data['list_with_secrets'][0] == 'normal_value'
        assert masked_data['list_with_secrets'][1] == '***MASKED***'
        assert masked_data['list_with_secrets'][2]['nested_secret'] == '***MASKED***'
        
        # Test log message masking
        log_message = "Connecting with password=secret123 and token=sk-abcdef123456"
        masked_message = self.security_manager.mask_log_message(log_message)
        
        assert 'password=***MASKED***' in masked_message
        assert 'token=***MASKED***' in masked_message
        assert 'secret123' not in masked_message
        assert 'sk-abcdef123456' not in masked_message
    
    def test_security_validation_with_placeholders(self):
        """Test security validation with placeholder values."""
        # Configuration with placeholder values (should not trigger warnings)
        placeholder_config = {
            "database": {
                "password": "your-password-here",
                "host": "localhost"
            },
            "api": {
                "token": "<your-api-token>",
                "endpoint": "https://api.example.com"
            },
            "github": {
                "token": "[REPLACE_WITH_TOKEN]"
            },
            "aws": {
                "access_key": "TODO: add your access key"
            }
        }
        
        warnings = self.security_manager.validate_config_security(placeholder_config)
        
        # Should not generate warnings for placeholder values
        assert len(warnings) == 0
        
        # Configuration with real sensitive values (should trigger warnings)
        real_sensitive_config = {
            "database": {
                "password": "real-secret-password-123",
                "host": "localhost"
            },
            "api": {
                "token": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
                "endpoint": "https://api.example.com"
            }
        }
        
        warnings = self.security_manager.validate_config_security(real_sensitive_config)
        
        # Should generate warnings for real sensitive values
        assert len(warnings) > 0
        assert any('database.password' in warning for warning in warnings)
        assert any('api.token' in warning for warning in warnings)
    
    def test_end_to_end_security_workflow(self):
        """Test complete security workflow from configuration to Git."""
        temp_repo = self.create_temp_git_repo()
        
        try:
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                # 1. Create configuration with security validation
                config_data = {
                    "version": "1.0",
                    "database": {
                        "host": "localhost",
                        "password": "your-password-here"  # Placeholder
                    },
                    "api": {
                        "endpoint": "https://api.example.com",
                        "token": "<your-token>"  # Placeholder
                    }
                }
                
                config_file = Path(temp_repo) / 'config.yaml'
                
                # Should succeed with placeholders
                success = self.config_manager.safe_update_config(config_file, config_data)
                assert success is True
                
                # 2. Install Git security hooks
                success = self.git_checker.install_pre_commit_hook()
                assert success is True
                
                # 3. Create .gitignore with security entries
                gitignore_entries = self.security_manager.create_gitignore_entries()
                gitignore_file = Path(temp_repo) / '.gitignore'
                
                with open(gitignore_file, 'w') as f:
                    for entry in gitignore_entries:
                        f.write(f"{entry}\n")
                
                # 4. Try to commit safe configuration
                subprocess.run(['git', 'add', 'config.yaml'], capture_output=True)
                subprocess.run(['git', 'add', '.gitignore'], capture_output=True)
                
                # Check staged files (should be safe)
                warnings = self.git_checker.check_staged_files()
                assert len(warnings) == 0  # No warnings for placeholder values
                
                # 5. Try to add file with sensitive data
                sensitive_file = Path(temp_repo) / 'secrets.py'
                with open(sensitive_file, 'w') as f:
                    f.write('API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"\n')
                
                subprocess.run(['git', 'add', 'secrets.py'], capture_output=True)
                
                # Check staged files (should detect sensitive data)
                warnings = self.git_checker.check_staged_files()
                assert len(warnings) > 0
                assert any('secrets.py' in warning for warning in warnings)
                
            finally:
                os.chdir(original_cwd)
                
        finally:
            import shutil
            shutil.rmtree(temp_repo)
    
    def test_security_performance_integration(self):
        """Test security validation performance with large configurations."""
        import time
        
        # Create large configuration with mixed sensitive and safe data
        large_config = {"version": "1.0"}
        
        # Add many safe configuration entries
        for i in range(1000):
            large_config[f"service_{i}"] = {
                "host": f"host-{i}.example.com",
                "port": 8080 + i,
                "enabled": i % 2 == 0
            }
        
        # Add some sensitive entries
        large_config["database"] = {
            "password": "secret123456",
            "host": "db.example.com"
        }
        large_config["api"] = {
            "token": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "endpoint": "https://api.example.com"
        }
        
        # Measure validation performance
        start_time = time.time()
        
        warnings = self.security_manager.validate_config_security(large_config)
        
        validation_time = time.time() - start_time
        
        # Should complete validation quickly (less than 1 second)
        assert validation_time < 1.0
        
        # Should still detect sensitive data
        assert len(warnings) >= 2  # At least password and token
        assert any('database.password' in warning for warning in warnings)
        assert any('api.token' in warning for warning in warnings)
        
        # Measure masking performance
        start_time = time.time()
        
        masked_config = self.security_manager.mask_sensitive_data(large_config)
        
        masking_time = time.time() - start_time
        
        # Should complete masking quickly
        assert masking_time < 1.0
        
        # Should mask sensitive data
        assert masked_config["database"]["password"] == "***MASKED***"
        assert masked_config["api"]["token"] == "***MASKED***"
        
        # Should preserve safe data
        assert masked_config["service_0"]["host"] == "host-0.example.com"
        assert masked_config["service_999"]["port"] == 8080 + 999


if __name__ == '__main__':
    pytest.main([__file__])