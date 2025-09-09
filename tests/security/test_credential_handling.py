"""
Security-focused tests for credential handling and secure storage.

Tests credential management, secure storage, and access patterns.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ic.config.security import SecurityManager
from ic.core.session import AWSSessionManager
from ic.core.mcp_manager import MCPManager


class TestCredentialHandling:
    """Security tests for credential handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
    
    def test_aws_credential_security_patterns(self):
        """Test AWS credential security patterns."""
        # Test various AWS credential formats
        aws_credentials = [
            'AKIA1234567890ABCDEF',  # Access key
            'ASIA1234567890ABCDEF',  # Temporary access key
            'AROA1234567890ABCDEF',  # Role access key
            'AIDA1234567890ABCDEF',  # User access key
            'AGPA1234567890ABCDEF',  # Group access key
            'AIPA1234567890ABCDEF',  # Instance profile access key
            'ANPA1234567890ABCDEF',  # Managed policy access key
            'ANVA1234567890ABCDEF',  # Version access key
            'APKA1234567890ABCDEF'   # Public key access key
        ]
        
        for credential in aws_credentials:
            assert self.security_manager._looks_like_secret(credential), f"AWS credential '{credential}' should be detected"
    
    def test_github_token_security_patterns(self):
        """Test GitHub token security patterns."""
        github_tokens = [
            'ghp_1234567890abcdefghijklmnopqrstuvwxyz',  # Personal access token
            'gho_1234567890abcdefghijklmnopqrstuvwxyz',  # OAuth token
            'ghu_1234567890abcdefghijklmnopqrstuvwxyz',  # User token
            'ghs_1234567890abcdefghijklmnopqrstuvwxyz',  # Server token
            'ghr_1234567890abcdefghijklmnopqrstuvwxyz',  # Refresh token
            'github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz'  # New format
        ]
        
        for token in github_tokens:
            assert self.security_manager._looks_like_secret(token), f"GitHub token '{token}' should be detected"
    
    def test_api_key_security_patterns(self):
        """Test various API key security patterns."""
        api_keys = [
            'sk-1234567890abcdefghijklmnopqrstuvwxyz',  # OpenAI style
            'sk-proj-1234567890abcdefghijklmnopqrstuvwxyz',  # OpenAI project key
            'rk_live_1234567890abcdefghijklmnopqrstuvwxyz',  # Stripe live key
            'rk_test_1234567890abcdefghijklmnopqrstuvwxyz',  # Stripe test key
            'pk_live_1234567890abcdefghijklmnopqrstuvwxyz',  # Stripe publishable key
            'xoxb-1234567890-abcdefghijklmnopqrstuvwxyz',  # Slack bot token
            'xoxp-1234567890-abcdefghijklmnopqrstuvwxyz',  # Slack user token
            'AIza1234567890abcdefghijklmnopqrstuvwxyz'      # Google API key
        ]
        
        for key in api_keys:
            assert self.security_manager._looks_like_secret(key), f"API key '{key}' should be detected" 
   
    def test_jwt_token_security_patterns(self):
        """Test JWT token security patterns."""
        jwt_tokens = [
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c',
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiYWJjZGVmZ2hpamtsbW5vcCIsImlhdCI6MTYwOTQ1OTIwMCwiZXhwIjoxNjA5NDYyODAwfQ.signature'
        ]
        
        for token in jwt_tokens:
            assert self.security_manager._looks_like_secret(token), f"JWT token should be detected"
    
    def test_database_connection_string_security(self):
        """Test database connection string security."""
        connection_strings = [
            'postgresql://user:password@localhost:5432/database',
            'mysql://root:secret123@db.example.com:3306/mydb',
            'mongodb://admin:pass123@mongo.example.com:27017/mydb',
            'redis://user:password@redis.example.com:6379/0',
            'sqlite:///path/to/database.db?password=secret'
        ]
        
        for conn_str in connection_strings:
            # Connection strings with passwords should be detected
            if 'password' in conn_str or ':secret' in conn_str or ':pass' in conn_str:
                warnings = self.security_manager.validate_config_security({'db_url': conn_str})
                assert len(warnings) > 0, f"Connection string '{conn_str}' should trigger security warning"
    
    def test_aws_session_credential_handling(self):
        """Test AWS session manager credential handling."""
        config = Mock()
        config.session_duration = 3600
        config.max_workers = 5
        
        session_manager = AWSSessionManager(config)
        
        # Test that credentials are not logged in profile processing
        with patch('src.ic.core.session.logger') as mock_logger:
            # Mock AWS config content with credentials
            aws_config_content = """
[default]
aws_access_key_id = AKIA1234567890ABCDEF
aws_secret_access_key = secret123456789012345678901234567890
region = us-east-1

[profile assume-role]
role_arn = arn:aws:iam::123456789012:role/TestRole
source_profile = default
"""
            
            with patch('os.path.expanduser') as mock_expand:
                with patch('os.path.exists', return_value=True):
                    with patch('configparser.ConfigParser.read'):
                        with patch('builtins.open', mock_open(read_data=aws_config_content)):
                            # This should not log sensitive credential data
                            profiles = session_manager.get_profiles()
            
            # Verify no sensitive data was logged
            if mock_logger.log_info_file_only.called:
                log_calls = [call[0][0] for call in mock_logger.log_info_file_only.call_args_list]
                for log_message in log_calls:
                    assert 'AKIA1234567890ABCDEF' not in log_message
                    assert 'secret123456789012345678901234567890' not in log_message
    
    def test_mcp_server_credential_masking(self):
        """Test MCP server credential masking."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add server with various credential types
        from ic.core.mcp_manager import MCPServerConfig
        
        manager.servers['test-server'] = MCPServerConfig(
            name='test-server',
            command='test',
            args=[],
            env={
                'GITHUB_TOKEN': 'ghp_1234567890abcdefghijklmnopqrstuvwxyz',
                'AWS_ACCESS_KEY_ID': 'AKIA1234567890ABCDEF',
                'AWS_SECRET_ACCESS_KEY': 'secret123456789012345678901234567890',
                'OPENAI_API_KEY': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
                'SLACK_BOT_TOKEN': 'xoxb-1234567890-abcdefghijklmnopqrstuvwxyz',
                'DATABASE_URL': 'postgresql://user:password@localhost/db',
                'NORMAL_CONFIG': 'safe-value'
            },
            disabled=False,
            auto_approve=[]
        )
        
        # Test masked retrieval
        masked_config = manager.get_server_config('test-server', mask_sensitive=True)
        
        # All credential-like environment variables should be masked
        assert masked_config['env']['GITHUB_TOKEN'] == '***MASKED***'
        assert masked_config['env']['AWS_ACCESS_KEY_ID'] == '***MASKED***'
        assert masked_config['env']['AWS_SECRET_ACCESS_KEY'] == '***MASKED***'
        assert masked_config['env']['OPENAI_API_KEY'] == '***MASKED***'
        assert masked_config['env']['SLACK_BOT_TOKEN'] == '***MASKED***'
        assert masked_config['env']['DATABASE_URL'] == '***MASKED***'
        
        # Non-sensitive values should be preserved
        assert masked_config['env']['NORMAL_CONFIG'] == 'safe-value'
    
    def test_credential_in_command_arguments(self):
        """Test detection of credentials in command arguments."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add server with credentials in command arguments
        from ic.core.mcp_manager import MCPServerConfig
        
        manager.servers['insecure-server'] = MCPServerConfig(
            name='insecure-server',
            command='curl',
            args=[
                '-H', 'Authorization: Bearer sk-1234567890abcdefghijklmnopqrstuvwxyz',
                '-H', 'X-API-Key: AKIA1234567890ABCDEF',
                'https://api.example.com'
            ],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        # Security validation should detect credentials in arguments
        warnings = manager.validate_server_security('insecure-server')
        
        assert len(warnings) > 0
        assert any('args' in warning for warning in warnings)
    
    def test_environment_variable_credential_detection(self):
        """Test detection of credentials in environment variables."""
        # Test various environment variable patterns
        env_vars_with_credentials = {
            'PASSWORD': 'secret123',
            'API_KEY': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
            'GITHUB_TOKEN': 'ghp_1234567890abcdefghijklmnopqrstuvwxyz',
            'AWS_SECRET_ACCESS_KEY': 'secret123456789012345678901234567890',
            'DATABASE_PASSWORD': 'dbsecret123',
            'WEBHOOK_SECRET': 'webhook-secret-456',
            'PRIVATE_KEY': '-----BEGIN PRIVATE KEY-----',
            'CLIENT_SECRET': 'client-secret-789',
            'NORMAL_VAR': 'safe-value'
        }
        
        # Test each environment variable
        for env_var, value in env_vars_with_credentials.items():
            config_data = {env_var.lower(): value}
            warnings = self.security_manager.validate_config_security(config_data)
            
            if env_var != 'NORMAL_VAR':
                assert len(warnings) > 0, f"Environment variable {env_var} should trigger security warning"
            else:
                assert len(warnings) == 0, f"Environment variable {env_var} should not trigger security warning"
    
    def test_credential_file_patterns(self):
        """Test detection of credential file patterns."""
        credential_files = [
            'credentials.json',
            'service-account.json',
            'service-account-key.json',
            'gcp-service-account.json',
            'aws-credentials.json',
            'private-key.pem',
            'certificate.p12',
            'keystore.pfx',
            'id_rsa',
            'id_rsa.pub',
            'ssh_host_rsa_key',
            '.env',
            '.env.local',
            '.env.production',
            'config.yaml',  # If it contains sensitive data
            'secrets.yaml'
        ]
        
        gitignore_entries = self.security_manager.create_gitignore_entries()
        gitignore_text = '\n'.join(gitignore_entries)
        
        # Most credential file patterns should be in gitignore
        sensitive_patterns = [
            'credentials.json',
            'service-account*.json',
            '*.key',
            '*.pem',
            '*.p12',
            '*.pfx',
            'id_rsa*',
            '.env',
            'config.yaml'
        ]
        
        for pattern in sensitive_patterns:
            assert pattern in gitignore_text, f"Pattern '{pattern}' should be in .gitignore"
    
    def test_secure_credential_storage_recommendations(self):
        """Test recommendations for secure credential storage."""
        # Test that security manager recommends environment variables
        config_with_hardcoded_creds = {
            'database': {
                'password': 'hardcoded-password-123'
            },
            'api': {
                'token': 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
            }
        }
        
        warnings = self.security_manager.validate_config_security(config_with_hardcoded_creds)
        
        # Warnings should recommend using environment variables
        warning_text = ' '.join(warnings)
        assert 'environment variables' in warning_text.lower()
    
    def test_credential_rotation_patterns(self):
        """Test detection of credentials that should be rotated."""
        # Test old/expired credential patterns
        potentially_old_credentials = [
            'sk-1234567890abcdefghijklmnopqrstuvwxyz',  # OpenAI key
            'ghp_1234567890abcdefghijklmnopqrstuvwxyz',  # GitHub token
            'AKIA1234567890ABCDEF',  # AWS access key
            'xoxb-1234567890-abcdefghijklmnopqrstuvwxyz'  # Slack token
        ]
        
        for credential in potentially_old_credentials:
            # All should be detected as secrets requiring protection
            assert self.security_manager._looks_like_secret(credential)
            
            # Should be masked when found in configuration
            masked = self.security_manager.mask_sensitive_data({'cred': credential})
            assert masked['cred'] == '***MASKED***'


if __name__ == '__main__':
    pytest.main([__file__])