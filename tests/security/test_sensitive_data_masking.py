"""
Security-focused tests for sensitive data masking in logs and configurations.

Tests comprehensive sensitive data detection and masking across all components.
"""

import pytest
from unittest.mock import Mock, patch

from src.ic.config.security import SecurityManager
from src.ic.core.logging import ICLogger
from src.ic.core.mcp_manager import MCPManager
from src.ic.config.manager import ConfigManager


class TestSensitiveDataMasking:
    """Security tests for sensitive data masking."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_config = {
            'sensitive_keys': [
                'password', 'passwd', 'pwd',
                'token', 'access_token', 'refresh_token', 'auth_token',
                'key', 'api_key', 'access_key', 'secret_key', 'private_key',
                'secret', 'client_secret', 'webhook_secret',
                'webhook_url', 'webhook',
                'credential', 'credentials'
            ],
            'mask_pattern': '***MASKED***'
        }
        self.security_manager = SecurityManager(self.security_config)
    
    def test_comprehensive_secret_pattern_detection(self):
        """Test detection of various secret patterns."""
        test_cases = [
            # OpenAI-style keys
            ('sk-1234567890abcdefghijklmnopqrstuvwxyz', True),
            ('sk-proj-1234567890abcdefghijklmnopqrstuvwxyz', True),
            
            # GitHub tokens
            ('ghp_1234567890abcdefghijklmnopqrstuvwxyz', True),
            ('gho_1234567890abcdefghijklmnopqrstuvwxyz', True),
            ('ghu_1234567890abcdefghijklmnopqrstuvwxyz', True),
            ('ghs_1234567890abcdefghijklmnopqrstuvwxyz', True),
            ('ghr_1234567890abcdefghijklmnopqrstuvwxyz', True),
            
            # Slack tokens
            ('xoxb-1234567890-abcdefghijklmnopqrstuvwxyz', True),
            ('xoxp-1234567890-abcdefghijklmnopqrstuvwxyz', True),
            ('xoxa-1234567890-abcdefghijklmnopqrstuvwxyz', True),
            
            # AWS access keys
            ('AKIA1234567890ABCDEF', True),
            ('ASIA1234567890ABCDEF', True),
            
            # Base64-like strings
            ('YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY3ODkw', True),
            ('dGhpc2lzYXZlcnlsb25nYmFzZTY0ZW5jb2RlZHN0cmluZ3RoYXRsb29rc2xpa2VhcGFzc3dvcmQ=', True),
            
            # Hex strings (long enough to be suspicious)
            ('a1b2c3d4e5f6789012345678901234567890abcdef1234567890', True),
            ('deadbeefcafebabe1234567890abcdef', True),
            
            # JWT tokens
            ('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c', True),
            
            # Regular strings (should not be detected)
            ('regular-string', False),
            ('short', False),
            ('username', False),
            ('localhost', False),
            ('https://example.com', False),
            ('normal-config-value', False),
            ('', False)
        ]
        
        for test_string, should_be_secret in test_cases:
            result = self.security_manager._looks_like_secret(test_string)
            assert result == should_be_secret, f"String '{test_string}' should {'be' if should_be_secret else 'not be'} detected as secret"
    
    def test_sensitive_key_detection_comprehensive(self):
        """Test comprehensive sensitive key detection."""
        sensitive_keys = [
            # Password variations
            'password', 'PASSWORD', 'Password', 'passwd', 'pwd',
            'user_password', 'database_password', 'admin_password',
            'mysql_password', 'postgres_password', 'redis_password',
            
            # Token variations
            'token', 'TOKEN', 'Token', 'access_token', 'refresh_token',
            'auth_token', 'bearer_token', 'jwt_token', 'api_token',
            'github_token', 'slack_token', 'oauth_token',
            
            # Key variations
            'key', 'KEY', 'Key', 'api_key', 'secret_key', 'private_key',
            'public_key', 'encryption_key', 'signing_key', 'access_key',
            'aws_access_key', 'gcp_service_account_key',
            
            # Secret variations
            'secret', 'SECRET', 'Secret', 'client_secret', 'webhook_secret',
            'shared_secret', 'master_secret', 'app_secret',
            
            # Credential variations
            'credential', 'credentials', 'creds', 'auth_creds',
            
            # Webhook variations
            'webhook', 'webhook_url', 'webhook_endpoint',
            
            # Certificate variations
            'cert', 'certificate', 'ssl_cert', 'tls_cert'
        ]
        
        for key in sensitive_keys:
            assert self.security_manager._is_sensitive_key(key), f"Key '{key}' should be detected as sensitive"
        
        # Non-sensitive keys
        non_sensitive_keys = [
            'username', 'email', 'host', 'port', 'database', 'table',
            'region', 'zone', 'project', 'subscription', 'account',
            'timeout', 'retries', 'debug', 'verbose', 'enabled'
        ]
        
        for key in non_sensitive_keys:
            assert not self.security_manager._is_sensitive_key(key), f"Key '{key}' should not be detected as sensitive"
    
    def test_nested_data_structure_masking(self):
        """Test masking in deeply nested data structures."""
        complex_data = {
            'level1': {
                'level2': {
                    'level3': {
                        'password': 'secret123',
                        'config': {
                            'api_token': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
                            'settings': {
                                'webhook_secret': 'webhook-secret-456',
                                'normal_value': 'safe-value'
                            }
                        }
                    },
                    'list_data': [
                        {'secret_key': 'list-secret-1'},
                        {'normal_key': 'list-normal-1'},
                        'sk-1234567890abcdefghijklmnopqrstuvwxyz',
                        'normal-string'
                    ]
                },
                'credentials': [
                    {
                        'username': 'user1',
                        'password': 'pass1',
                        'tokens': ['token1', 'sk-abcdef123456']
                    },
                    {
                        'username': 'user2',
                        'api_key': 'key2'
                    }
                ]
            }
        }
        
        masked_data = self.security_manager.mask_sensitive_data(complex_data)
        
        # Verify deep nesting masking
        assert masked_data['level1']['level2']['level3']['password'] == '***MASKED***'
        assert masked_data['level1']['level2']['level3']['config']['api_token'] == '***MASKED***'
        assert masked_data['level1']['level2']['level3']['config']['settings']['webhook_secret'] == '***MASKED***'
        assert masked_data['level1']['level2']['level3']['config']['settings']['normal_value'] == 'safe-value'
        
        # Verify list masking
        assert masked_data['level1']['level2']['list_data'][0]['secret_key'] == '***MASKED***'
        assert masked_data['level1']['level2']['list_data'][1]['normal_key'] == 'list-normal-1'
        assert masked_data['level1']['level2']['list_data'][2] == '***MASKED***'
        assert masked_data['level1']['level2']['list_data'][3] == 'normal-string'
        
        # Verify credentials list masking
        assert masked_data['level1']['credentials'][0]['username'] == 'user1'
        assert masked_data['level1']['credentials'][0]['password'] == '***MASKED***'
        assert masked_data['level1']['credentials'][0]['tokens'][0] == 'token1'
        assert masked_data['level1']['credentials'][0]['tokens'][1] == '***MASKED***'
        assert masked_data['level1']['credentials'][1]['api_key'] == '***MASKED***'
    
    def test_logging_system_masking_integration(self):
        """Test sensitive data masking in logging system."""
        config = {
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'mask_sensitive': True
            },
            'security': self.security_config
        }
        
        logger = ICLogger(config)
        
        # Mock the underlying logger to capture masked messages
        logger.logger = Mock()
        
        # Test various log methods with sensitive data
        test_cases = [
            ('log_info_file_only', 'Connected with password=secret123 to database'),
            ('log_warning', 'API token sk-1234567890abcdefghijklmnopqrstuvwxyz expired'),
            ('log_error', 'Authentication failed for key=AKIA1234567890ABCDEF'),
            ('log_debug', 'Webhook URL: https://hooks.slack.com/services/T00/B00/secret')
        ]
        
        for method_name, message in test_cases:
            method = getattr(logger, method_name)
            method(message)
            
            # Get the last call to the underlying logger
            last_call = logger.logger.method_calls[-1]
            logged_message = last_call[1][0]  # First argument of the call
            
            # Verify sensitive data was masked
            assert 'password=***MASKED***' in logged_message or 'password=secret123' not in logged_message
            assert 'sk-1234567890abcdefghijklmnopqrstuvwxyz' not in logged_message
            assert 'AKIA1234567890ABCDEF' not in logged_message
            assert 'secret123' not in logged_message
    
    def test_mcp_manager_sensitive_data_masking(self):
        """Test sensitive data masking in MCP manager."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add server with sensitive environment variables
        from src.ic.core.mcp_manager import MCPServerConfig
        
        manager.servers['test-server'] = MCPServerConfig(
            name='test-server',
            command='test-command',
            args=['--token', 'sk-1234567890abcdefghijklmnopqrstuvwxyz'],
            env={
                'API_TOKEN': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
                'GITHUB_TOKEN': 'ghp_1234567890abcdefghijklmnopqrstuvwxyz',
                'WEBHOOK_SECRET': 'webhook-secret-123',
                'DATABASE_PASSWORD': 'db-password-456',
                'NORMAL_CONFIG': 'safe-value'
            },
            disabled=False,
            auto_approve=[]
        )
        
        # Test masked configuration retrieval
        masked_config = manager.get_server_config('test-server', mask_sensitive=True)
        
        assert masked_config['env']['API_TOKEN'] == '***MASKED***'
        assert masked_config['env']['GITHUB_TOKEN'] == '***MASKED***'
        assert masked_config['env']['WEBHOOK_SECRET'] == '***MASKED***'
        assert masked_config['env']['DATABASE_PASSWORD'] == '***MASKED***'
        assert masked_config['env']['NORMAL_CONFIG'] == 'safe-value'
        
        # Test unmasked configuration retrieval
        unmasked_config = manager.get_server_config('test-server', mask_sensitive=False)
        
        assert unmasked_config['env']['API_TOKEN'] == 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
        assert unmasked_config['env']['GITHUB_TOKEN'] == 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'
        assert unmasked_config['env']['WEBHOOK_SECRET'] == 'webhook-secret-123'
        assert unmasked_config['env']['DATABASE_PASSWORD'] == 'db-password-456'
        
        # Test GitHub operations with sensitive parameters
        result = manager.query_github_operations(
            'create_issue',
            'owner/repo',
            token='ghp_sensitive_token_12345',
            webhook_url='https://hooks.example.com/webhook/secret',
            title='Normal Title'
        )
        
        # Sensitive parameters should be masked in result
        assert result.data['parameters']['token'] == '***MASKED***'
        assert result.data['parameters']['webhook_url'] == '***MASKED***'
        assert result.data['parameters']['title'] == 'Normal Title'
    
    def test_configuration_manager_masking(self):
        """Test sensitive data masking in configuration manager."""
        config_manager = ConfigManager(security_manager=self.security_manager)
        
        # Test configuration with sensitive data
        sensitive_config = {
            'database': {
                'host': 'localhost',
                'password': 'db-secret-123',
                'connection_string': 'postgresql://user:secret@localhost/db'
            },
            'api': {
                'endpoint': 'https://api.example.com',
                'token': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
                'webhook_secret': 'webhook-secret-456'
            },
            'aws': {
                'region': 'us-east-1',
                'access_key': 'AKIA1234567890ABCDEF',
                'secret_key': 'secret-key-789'
            },
            'normal_config': {
                'timeout': 30,
                'retries': 3,
                'debug': False
            }
        }
        
        # Test security validation
        warnings = config_manager.validate_config(sensitive_config)
        
        # Should detect multiple sensitive data issues
        sensitive_warnings = [w for w in warnings if 'sensitive data' in w.lower()]
        assert len(sensitive_warnings) >= 4  # password, token, webhook_secret, access_key, secret_key
        
        # Test that masking preserves structure
        masked_config = self.security_manager.mask_sensitive_data(sensitive_config)
        
        # Structure should be preserved
        assert 'database' in masked_config
        assert 'api' in masked_config
        assert 'aws' in masked_config
        assert 'normal_config' in masked_config
        
        # Sensitive values should be masked
        assert masked_config['database']['password'] == '***MASKED***'
        assert masked_config['api']['token'] == '***MASKED***'
        assert masked_config['api']['webhook_secret'] == '***MASKED***'
        assert masked_config['aws']['access_key'] == '***MASKED***'
        assert masked_config['aws']['secret_key'] == '***MASKED***'
        
        # Non-sensitive values should be preserved
        assert masked_config['database']['host'] == 'localhost'
        assert masked_config['api']['endpoint'] == 'https://api.example.com'
        assert masked_config['aws']['region'] == 'us-east-1'
        assert masked_config['normal_config']['timeout'] == 30
    
    def test_log_message_pattern_masking(self):
        """Test comprehensive log message pattern masking."""
        test_messages = [
            # Password patterns
            ('Login with password=secret123 successful', 'password=***MASKED***'),
            ('Database password: secret456', 'password=***MASKED***'),
            ('pwd=mypassword', 'pwd=***MASKED***'),
            
            # Token patterns
            ('Using token sk-1234567890abcdefghijklmnopqrstuvwxyz', 'token=***MASKED***'),
            ('API token: ghp_1234567890abcdefghijklmnopqrstuvwxyz', 'token=***MASKED***'),
            ('Bearer token in header', 'Bearer ***MASKED***'),
            
            # Key patterns
            ('API key AKIA1234567890ABCDEF configured', 'key=***MASKED***'),
            ('Secret key: secret-key-123', 'key=***MASKED***'),
            
            # Authorization headers
            ('Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9', 'Bearer ***MASKED***'),
            ('Authorization: Basic dXNlcjpwYXNzd29yZA==', 'Basic ***MASKED***'),
            
            # Webhook URLs
            ('Webhook: https://hooks.slack.com/services/T00/B00/secret', 'webhook=***MASKED***'),
            
            # Normal messages (should not be changed)
            ('User logged in successfully', 'User logged in successfully'),
            ('Database connection established', 'Database connection established'),
            ('Processing request for user john', 'Processing request for user john')
        ]
        
        for original_message, expected_pattern in test_messages:
            masked_message = self.security_manager.mask_log_message(original_message)
            
            if expected_pattern == original_message:
                # Message should be unchanged
                assert masked_message == original_message
            else:
                # Message should contain the expected masked pattern
                assert expected_pattern in masked_message or '***MASKED***' in masked_message
                
                # Original sensitive data should be removed
                if 'secret123' in original_message:
                    assert 'secret123' not in masked_message
                if 'sk-1234567890abcdefghijklmnopqrstuvwxyz' in original_message:
                    assert 'sk-1234567890abcdefghijklmnopqrstuvwxyz' not in masked_message
    
    def test_edge_cases_and_false_positives(self):
        """Test edge cases and potential false positives in masking."""
        # Test data that might look sensitive but isn't
        edge_cases = {
            'version': '1.2.3',
            'build_number': '20240101123456',
            'commit_hash': 'a1b2c3d4e5f6789012345678901234567890abcd',  # Short hash
            'uuid': '123e4567-e89b-12d3-a456-426614174000',
            'timestamp': '1640995200000',
            'phone_number': '+1-555-123-4567',
            'ip_address': '192.168.1.100',
            'mac_address': '00:1B:44:11:3A:B7',
            'normal_id': 'user-12345',
            'short_code': 'ABC123',
            'normal_url': 'https://example.com/path/to/resource'
        }
        
        masked_data = self.security_manager.mask_sensitive_data(edge_cases)
        
        # None of these should be masked
        for key, value in edge_cases.items():
            assert masked_data[key] == value, f"Value '{value}' for key '{key}' should not be masked"
        
        # Test actual secrets mixed with edge cases
        mixed_data = edge_cases.copy()
        mixed_data.update({
            'real_password': 'secret123456',
            'real_token': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
            'real_key': 'AKIA1234567890ABCDEF'
        })
        
        masked_mixed = self.security_manager.mask_sensitive_data(mixed_data)
        
        # Edge cases should still not be masked
        for key, value in edge_cases.items():
            assert masked_mixed[key] == value
        
        # Real secrets should be masked
        assert masked_mixed['real_password'] == '***MASKED***'
        assert masked_mixed['real_token'] == '***MASKED***'
        assert masked_mixed['real_key'] == '***MASKED***'
    
    def test_performance_with_large_datasets(self):
        """Test masking performance with large datasets."""
        import time
        
        # Create large dataset with mixed sensitive and non-sensitive data
        large_dataset = {}
        
        # Add many non-sensitive entries
        for i in range(1000):
            large_dataset[f'service_{i}'] = {
                'host': f'host-{i}.example.com',
                'port': 8080 + i,
                'timeout': 30,
                'retries': 3,
                'enabled': i % 2 == 0,
                'tags': [f'tag-{j}' for j in range(5)]
            }
        
        # Add some sensitive entries scattered throughout
        for i in range(0, 1000, 100):  # Every 100th entry
            large_dataset[f'service_{i}']['password'] = f'secret-{i}'
            large_dataset[f'service_{i}']['api_token'] = f'sk-{i:032d}'
        
        # Measure masking performance
        start_time = time.time()
        
        masked_dataset = self.security_manager.mask_sensitive_data(large_dataset)
        
        masking_time = time.time() - start_time
        
        # Should complete masking in reasonable time (less than 2 seconds)
        assert masking_time < 2.0, f"Masking took {masking_time:.2f}s, which is too slow"
        
        # Verify masking worked correctly
        for i in range(0, 1000, 100):
            assert masked_dataset[f'service_{i}']['password'] == '***MASKED***'
            assert masked_dataset[f'service_{i}']['api_token'] == '***MASKED***'
        
        # Verify non-sensitive data was preserved
        assert masked_dataset['service_0']['host'] == 'host-0.example.com'
        assert masked_dataset['service_999']['port'] == 8080 + 999


if __name__ == '__main__':
    pytest.main([__file__])