"""
Unit tests for security validation and compliance checks.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from ic.config.security import (
    SecurityManager, 
    NCPSecurityValidator, 
    NCPComplianceChecker,
    GitSecurityChecker
)


class TestSecurityManager:
    """Test SecurityManager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
    
    def test_mask_sensitive_data_dict(self):
        """Test masking sensitive data in dictionaries."""
        data = {
            "username": "test_user",
            "password": "secret123",
            "api_key": "abc123def456",
            "normal_field": "normal_value"
        }
        
        masked = self.security_manager.mask_sensitive_data(data)
        
        assert masked["username"] == "test_user"
        assert masked["password"] == "***MASKED***"
        assert masked["api_key"] == "***MASKED***"
        assert masked["normal_field"] == "normal_value"
    
    def test_mask_sensitive_data_nested(self):
        """Test masking sensitive data in nested structures."""
        data = {
            "config": {
                "database": {
                    "host": "localhost",
                    "password": "db_secret"
                },
                "api": {
                    "key": "api_secret_key",
                    "endpoint": "https://api.example.com"
                }
            }
        }
        
        masked = self.security_manager.mask_sensitive_data(data)
        
        assert masked["config"]["database"]["host"] == "localhost"
        assert masked["config"]["database"]["password"] == "***MASKED***"
        assert masked["config"]["api"]["key"] == "***MASKED***"
        assert masked["config"]["api"]["endpoint"] == "https://api.example.com"
    
    def test_mask_sensitive_data_list(self):
        """Test masking sensitive data in lists."""
        data = [
            {"name": "user1", "token": "token123"},
            {"name": "user2", "secret": "secret456"}
        ]
        
        masked = self.security_manager.mask_sensitive_data(data)
        
        assert masked[0]["name"] == "user1"
        assert masked[0]["token"] == "***MASKED***"
        assert masked[1]["name"] == "user2"
        assert masked[1]["secret"] == "***MASKED***"
    
    def test_validate_config_security(self):
        """Test configuration security validation."""
        config_data = {
            "safe_setting": "value",
            "password": "actual_password",
            "api_key": "real_api_key"
        }
        
        warnings = self.security_manager.validate_config_security(config_data)
        
        assert len(warnings) >= 2  # Should warn about password and api_key
        assert any("password" in warning.lower() for warning in warnings)
        assert any("api_key" in warning.lower() for warning in warnings)
    
    def test_mask_log_message(self):
        """Test log message masking."""
        log_message = "User login with password=secret123 and token=abc456def"
        
        masked = self.security_manager.mask_log_message(log_message)
        
        assert "secret123" not in masked
        assert "abc456def" not in masked
        assert "***MASKED***" in masked


class TestNCPSecurityValidator:
    """Test NCP-specific security validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.ncp_validator = NCPSecurityValidator(self.security_manager)
    
    def test_scan_for_hardcoded_credentials_file_content(self):
        """Test scanning file content for hardcoded credentials."""
        test_content = '''
        # Configuration file
        ncp_access_key = "AKIA1234567890ABCDEF"
        ncp_secret_key = "abcdef1234567890abcdef1234567890abcdef12"
        normal_config = "safe_value"
        '''
        
        with patch('builtins.open', mock_open(read_data=test_content)):
            with patch('os.walk') as mock_walk:
                mock_walk.return_value = [
                    ('.', [], ['config.py'])
                ]
                
                violations = self.ncp_validator.scan_for_hardcoded_credentials('.')
                
                assert len(violations) >= 2  # Should find both access_key and secret_key
                assert any("Access Key" in violation for violation in violations)
                assert any("Secret Key" in violation for violation in violations)
    
    def test_validate_config_file_permissions(self):
        """Test configuration file permission validation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test config")
            temp_file_path = temp_file.name
        
        try:
            # Set insecure permissions (if not on Windows)
            if os.name != 'nt':
                os.chmod(temp_file_path, 0o644)  # World readable
                
                violations = self.ncp_validator.validate_config_file_permissions([temp_file_path])
                
                assert len(violations) > 0
                assert "Insecure file permissions" in violations[0]
        finally:
            os.unlink(temp_file_path)
    
    def test_validate_government_compliance(self):
        """Test government compliance validation."""
        # Non-compliant configuration
        config_data = {
            "encryption_enabled": False,
            "audit_logging_enabled": False
        }
        
        results = self.ncp_validator.validate_government_compliance(config_data)
        
        assert not results["compliant"]
        assert len(results["violations"]) > 0
        assert any("encryption" in violation.lower() for violation in results["violations"])
        
        # Compliant configuration
        compliant_config = {
            "encryption_enabled": True,
            "audit_logging_enabled": True,
            "access_control_enabled": True,
            "network_security_enabled": True
        }
        
        compliant_results = self.ncp_validator.validate_government_compliance(compliant_config)
        
        assert compliant_results["compliant"]
        assert len(compliant_results["violations"]) == 0
    
    def test_mask_sensitive_data_in_logs(self):
        """Test NCP-specific log masking."""
        log_message = "Connecting to VPC vpc-123456 with private IP 10.0.1.100"
        
        masked = self.ncp_validator.mask_sensitive_data_in_logs(log_message)
        
        # VPC ID should be masked
        assert "vpc-123456" not in masked
        assert "***VPC_MASKED***" in masked
        
        # IP address should be masked
        assert "10.0.1.100" not in masked
        assert "***IP_MASKED***" in masked
    
    def test_is_placeholder_credential(self):
        """Test placeholder credential detection."""
        # Should be detected as placeholders
        assert self.ncp_validator._is_placeholder_credential("your-access-key-here")
        assert self.ncp_validator._is_placeholder_credential("<your-secret-key>")
        assert self.ncp_validator._is_placeholder_credential("[REPLACE_WITH_KEY]")
        assert self.ncp_validator._is_placeholder_credential("example_key")
        
        # Should NOT be detected as placeholders
        assert not self.ncp_validator._is_placeholder_credential("AKIA1234567890ABCDEF")
        assert not self.ncp_validator._is_placeholder_credential("real_secret_key_value")


class TestNCPComplianceChecker:
    """Test NCP compliance checking functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.compliance_checker = NCPComplianceChecker()
    
    def test_check_government_compliance_pass(self):
        """Test government compliance check - passing case."""
        config_data = {
            "data_encryption": True,
            "audit_logging": True,
            "access_control": True,
            "network_security": True,
            "data_residency": True,
            "security_monitoring": True,
            "encryption_enabled": True,
            "audit_logging_enabled": True,
            "access_control_enabled": True,
            "network_security_enabled": True,
            "data_residency_compliant": True,
            "security_monitoring_enabled": True
        }
        
        results = self.compliance_checker.check_compliance(config_data, 'government')
        
        assert results["compliant"]
        assert results["score"] == 100.0
        assert len(results["failed_requirements"]) == 0
    
    def test_check_government_compliance_fail(self):
        """Test government compliance check - failing case."""
        config_data = {
            "encryption_enabled": False,
            "audit_logging_enabled": False
        }
        
        results = self.compliance_checker.check_compliance(config_data, 'government')
        
        assert not results["compliant"]
        assert results["score"] < 100.0
        assert len(results["failed_requirements"]) > 0
    
    def test_check_financial_compliance(self):
        """Test financial compliance check."""
        config_data = {
            "encryption_enabled": True,
            "audit_logging_enabled": True,
            "access_control_enabled": True,
            "transaction_monitoring_enabled": True,
            "fraud_detection_enabled": True
        }
        
        results = self.compliance_checker.check_compliance(config_data, 'financial')
        
        assert results["framework"] == "Financial Services Compliance"
        assert results["compliant"]
    
    def test_unknown_framework(self):
        """Test handling of unknown compliance framework."""
        with pytest.raises(ValueError, match="Unknown compliance framework"):
            self.compliance_checker.check_compliance({}, 'unknown_framework')
    
    def test_get_requirement_recommendation(self):
        """Test requirement recommendation generation."""
        recommendation = self.compliance_checker._get_requirement_recommendation('data_encryption')
        
        assert recommendation is not None
        assert "encryption" in recommendation.lower()


class TestGitSecurityChecker:
    """Test Git security checking functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.git_checker = GitSecurityChecker(self.security_manager)
    
    def test_should_check_file(self):
        """Test file checking logic."""
        # Should check these files
        assert self.git_checker._should_check_file("config.py")
        assert self.git_checker._should_check_file("script.sh")
        assert self.git_checker._should_check_file("config.yaml")
        
        # Should NOT check these files
        assert not self.git_checker._should_check_file("image.jpg")
        assert not self.git_checker._should_check_file("binary.so")
        assert not self.git_checker._should_check_file("requirements.txt")
    
    def test_contains_secrets(self):
        """Test secret detection in content."""
        # Content with secrets
        secret_content = '''
        password = "secret123password"
        api_key = "AKIA1234567890ABCDEF"
        '''
        
        assert self.git_checker._contains_secrets(secret_content)
        
        # Content without secrets
        safe_content = '''
        username = "test_user"
        endpoint = "https://api.example.com"
        '''
        
        assert not self.git_checker._contains_secrets(safe_content)
    
    @patch('subprocess.run')
    def test_check_staged_files(self, mock_run):
        """Test checking staged files for secrets."""
        # Mock git diff output
        mock_run.return_value.stdout = "config.py\nscript.sh\n"
        mock_run.return_value.returncode = 0
        
        with patch.object(self.git_checker, '_check_file_content') as mock_check:
            mock_check.return_value = ["Secret found in config.py"]
            
            warnings = self.git_checker.check_staged_files()
            
            assert len(warnings) > 0
            assert "config.py" in warnings[0]
    
    def test_generate_pre_commit_hook(self):
        """Test pre-commit hook generation."""
        hook_content = self.git_checker._generate_pre_commit_hook()
        
        assert "#!/bin/bash" in hook_content
        assert "IC Security Pre-commit Hook" in hook_content
        assert "grep -E" in hook_content


class TestSecurityIntegration:
    """Integration tests for security features."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.ncp_validator = NCPSecurityValidator(self.security_manager)
        self.compliance_checker = NCPComplianceChecker()
    
    def test_comprehensive_security_scan(self):
        """Test comprehensive security scanning."""
        # Create temporary directory with test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file with hardcoded credentials
            test_file = Path(temp_dir) / "config.py"
            test_file.write_text('''
            # Test configuration
            ncp_access_key = "AKIA1234567890ABCDEF"
            database_password = "secret123"
            normal_setting = "safe_value"
            ''')
            
            # Scan for credentials
            violations = self.ncp_validator.scan_for_hardcoded_credentials(temp_dir)
            
            assert len(violations) >= 2  # Should find access_key and password
    
    def test_end_to_end_compliance_check(self):
        """Test end-to-end compliance checking."""
        # Test configuration with mixed compliance
        config_data = {
            "encryption_enabled": True,
            "audit_logging_enabled": False,  # This will fail
            "access_control_enabled": True,
            "network_security_enabled": True,
            "data_residency_compliant": False,  # This will fail
            "security_monitoring_enabled": True
        }
        
        # Check compliance
        results = self.compliance_checker.check_compliance(config_data, 'government')
        
        # Should not be fully compliant
        assert not results["compliant"]
        assert 0 < results["score"] < 100
        assert len(results["failed_requirements"]) > 0
        assert len(results["recommendations"]) > 0
        
        # Verify specific failures
        failed_reqs = results["failed_requirements"]
        assert "audit_logging" in failed_reqs
        assert "data_residency" in failed_reqs


if __name__ == '__main__':
    pytest.main([__file__])