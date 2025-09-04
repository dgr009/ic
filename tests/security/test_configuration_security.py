"""
Security-focused tests for configuration security warnings and validation.

Tests configuration security validation, warnings, and safe handling.
"""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.ic.config.security import SecurityManager
from src.ic.config.manager import ConfigManager


class TestConfigurationSecurity:
    """Security tests for configuration handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.config_manager = ConfigManager(security_manager=self.security_manager)
    
    def test_sensitive_data_detection_in_config(self):
        """Test detection of sensitive data in configuration files."""
        # Configuration with various types of sensitive data
        sensitive_config = {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'username': 'dbuser',
                'password': 'secret123456',  # Sensitive
                'connection_string': 'postgresql://user:secret@localhost/db'  # Contains password
            },
            'api': {
                'endpoint': 'https://api.example.com',
                'timeout': 30,
                'api_key': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',  # Sensitive
                'token': 'ghp_1234567890abcdefghijklmnopqrstuvwxyz',  # Sensitive
                'webhook_secret': 'webhook-secret-123'  # Sensitive
            },
            'aws': {
                'region': 'us-east-1',
                'access_key': 'AKIA1234567890ABCDEF',  # Sensitive
                'secret_key': 'secret123456789012345678901234567890',  # Sensitive
                'session_token': 'session-token-123'  # Sensitive
            },
            'azure': {
                'subscription_id': 'sub-12345',
                'tenant_id': 'tenant-67890',
                'client_id': 'client-abcdef',
                'client_secret': 'client-secret-ghijkl'  # Sensitive
            },
            'gcp': {
                'project_id': 'my-project',
                'region': 'us-central1',
                'service_account_key': '{"type": "service_account", "private_key": "-----BEGIN PRIVATE KEY-----"}'  # Sensitive
            },
            'github': {
                'username': 'testuser',
                'personal_access_token': 'ghp_personal_token_12345'  # Sensitive
            },
            'slack': {
                'channel': '#general',
                'webhook_url': 'https://hooks.slack.com/services/T00/B00/secret'  # Sensitive
            },
            'normal_config': {
                'timeout': 30,
                'retries': 3,
                'debug': False,
                'log_level': 'INFO'
            }
        }
        
        warnings = self.security_manager.validate_config_security(sensitive_config)
        
        # Should detect multiple sensitive data issues
        assert len(warnings) >= 8  # At least 8 sensitive fields
        
        # Check specific warnings
        warning_text = ' '.join(warnings)
        assert 'database.password' in warning_text
        assert 'api.api_key' in warning_text
        assert 'api.token' in warning_text
        assert 'api.webhook_secret' in warning_text
        assert 'aws.access_key' in warning_text
        assert 'aws.secret_key' in warning_text
        assert 'azure.client_secret' in warning_text
        assert 'gcp.service_account_key' in warning_text
        assert 'github.personal_access_token' in warning_text
        assert 'slack.webhook_url' in warning_text
    
    def test_placeholder_value_detection(self):
        """Test detection and handling of placeholder values."""
        # Configuration with placeholder values (should not trigger warnings)
        placeholder_config = {
            'database': {
                'password': 'your-password-here',
                'host': 'localhost'
            },
            'api': {
                'token': '<your-api-token>',
                'endpoint': 'https://api.example.com'
            },
            'aws': {
                'access_key': '[REPLACE_WITH_ACCESS_KEY]',
                'secret_key': 'TODO: add your secret key'
            },
            'github': {
                'token': 'CHANGE_THIS_TOKEN'
            },
            'slack': {
                'webhook_url': 'example-webhook-url'
            }
        }
        
        warnings = self.security_manager.validate_config_security(placeholder_config)
        
        # Should not generate warnings for placeholder values
        assert len(warnings) == 0
        
        # Test individual placeholder detection
        placeholder_values = [
            'your-password-here',
            '<your-token>',
            '[REPLACE_ME]',
            'TODO: add password',
            'CHANGE_THIS_PASSWORD',
            'example-key',
            'placeholder-value'
        ]
        
        for value in placeholder_values:
            assert self.security_manager._is_placeholder_value(value), f"'{value}' should be detected as placeholder"
        
        # Test real values (should not be detected as placeholders)
        real_values = [
            'sk-1234567890abcdefghijklmnopqrstuvwxyz',
            'ghp_1234567890abcdefghijklmnopqrstuvwxyz',
            'real-password-123',
            'AKIA1234567890ABCDEF'
        ]
        
        for value in real_values:
            assert not self.security_manager._is_placeholder_value(value), f"'{value}' should not be detected as placeholder"
    
    def test_nested_configuration_security_validation(self):
        """Test security validation in deeply nested configurations."""
        nested_config = {
            'level1': {
                'level2': {
                    'level3': {
                        'database_password': 'secret123',  # Sensitive
                        'normal_setting': 'value'
                    },
                    'api_config': {
                        'endpoints': {
                            'primary': {
                                'url': 'https://api.example.com',
                                'api_key': 'sk-1234567890abcdefghijklmnopqrstuvwxyz'  # Sensitive
                            },
                            'secondary': {
                                'url': 'https://api2.example.com',
                                'timeout': 30
                            }
                        }
                    }
                },
                'services': [
                    {
                        'name': 'service1',
                        'config': {
                            'token': 'service1-token-123',  # Sensitive
                            'host': 'service1.example.com'
                        }
                    },
                    {
                        'name': 'service2',
                        'config': {
                            'webhook_secret': 'webhook-secret-456',  # Sensitive
                            'port': 8080
                        }
                    }
                ]
            }
        }
        
        warnings = self.security_manager.validate_config_security(nested_config)
        
        # Should detect sensitive data at all nesting levels
        assert len(warnings) >= 4
        
        warning_text = ' '.join(warnings)
        assert 'level1.level2.level3.database_password' in warning_text
        assert 'level1.level2.api_config.endpoints.primary.api_key' in warning_text
        assert 'level1.services[0].config.token' in warning_text
        assert 'level1.services[1].config.webhook_secret' in warning_text
    
    def test_configuration_security_with_arrays(self):
        """Test security validation with arrays and lists."""
        array_config = {
            'databases': [
                {
                    'name': 'primary',
                    'host': 'db1.example.com',
                    'password': 'db1-secret'  # Sensitive
                },
                {
                    'name': 'secondary',
                    'host': 'db2.example.com',
                    'password': 'db2-secret'  # Sensitive
                }
            ],
            'api_keys': [
                'sk-1234567890abcdefghijklmnopqrstuvwxyz',  # Sensitive string in array
                'normal-config-value'
            ],
            'services': {
                'auth': {
                    'tokens': [
                        'ghp_1234567890abcdefghijklmnopqrstuvwxyz',  # Sensitive
                        'normal-token-name'
                    ]
                }
            }
        }
        
        warnings = self.security_manager.validate_config_security(array_config)
        
        # Should detect sensitive data in arrays
        assert len(warnings) >= 4
        
        warning_text = ' '.join(warnings)
        assert 'databases[0].password' in warning_text
        assert 'databases[1].password' in warning_text
        assert 'api_keys[0]' in warning_text
        assert 'services.auth.tokens[0]' in warning_text
    
    def test_safe_configuration_update_with_security_validation(self):
        """Test safe configuration update with security validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'config.yaml'
            
            # Create initial safe configuration
            safe_config = {
                'version': '1.0',
                'database': {
                    'host': 'localhost',
                    'port': 5432
                },
                'api': {
                    'endpoint': 'https://api.example.com',
                    'timeout': 30
                }
            }
            
            # Save initial configuration
            success = self.config_manager.safe_update_config(config_file, safe_config)
            assert success is True
            
            # Try to update with sensitive data
            unsafe_config = safe_config.copy()
            unsafe_config['database']['password'] = 'secret123456'
            unsafe_config['api']['token'] = 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
            
            # Mock security validation to return critical warnings
            with patch.object(self.security_manager, 'validate_config_security') as mock_validate:
                mock_validate.return_value = [
                    'Critical: sensitive data found in config at database.password',
                    'Critical: sensitive data found in config at api.token'
                ]
                
                # Update should fail due to security issues
                success = self.config_manager.safe_update_config(config_file, unsafe_config)
                assert success is False
            
            # Original configuration should be preserved
            preserved_config = self.config_manager._load_config_file(config_file)
            assert 'password' not in preserved_config['database']
            assert 'token' not in preserved_config['api']
    
    def test_configuration_backup_on_security_failure(self):
        """Test that configuration backup is created on security validation failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'config.yaml'
            
            # Create initial configuration
            initial_config = {
                'version': '1.0',
                'safe_setting': 'safe_value'
            }
            
            self.config_manager.save_config(config_file, initial_config)
            
            # Try to update with sensitive data
            unsafe_config = {
                'version': '1.0',
                'safe_setting': 'safe_value',
                'password': 'secret123456'
            }
            
            # Should create backup and fail update
            success = self.config_manager.safe_update_config(config_file, unsafe_config)
            assert success is False
            
            # Check that backup was created
            backup_files = list(Path(temp_dir).glob('config_*.yaml'))
            assert len(backup_files) > 0
            
            # Verify backup contains original configuration
            backup_config = self.config_manager._load_config_file(backup_files[0])
            assert backup_config == initial_config
            
            # Verify original file is unchanged
            current_config = self.config_manager._load_config_file(config_file)
            assert current_config == initial_config
    
    def test_environment_variable_security_validation(self):
        """Test security validation of environment variables in configuration."""
        # Test environment variable mapping with sensitive data
        sensitive_env_vars = {
            'DATABASE_PASSWORD': 'db-secret-123',
            'API_TOKEN': 'sk-1234567890abcdefghijklmnopqrstuvwxyz',
            'AWS_SECRET_ACCESS_KEY': 'aws-secret-key-456',
            'GITHUB_TOKEN': 'ghp_1234567890abcdefghijklmnopqrstuvwxyz',
            'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/services/T00/B00/secret',
            'NORMAL_CONFIG': 'safe-value'
        }
        
        with patch.dict('os.environ', sensitive_env_vars):
            # Load configuration with environment variables
            with patch('logging.Logger.warning') as mock_warning:
                config = self.config_manager.load_config([])
                
                # Should log warnings about sensitive environment variables
                warning_calls = [call[0][0] for call in mock_warning.call_args_list]
                security_warnings = [w for w in warning_calls if 'sensitive data' in w.lower()]
                
                # Should detect sensitive environment variables
                assert len(security_warnings) > 0
    
    def test_configuration_masking_preserves_structure(self):
        """Test that configuration masking preserves data structure."""
        complex_config = {
            'version': '1.0',
            'databases': {
                'primary': {
                    'host': 'db1.example.com',
                    'port': 5432,
                    'credentials': {
                        'username': 'dbuser',
                        'password': 'secret123'  # Sensitive
                    },
                    'ssl': {
                        'enabled': True,
                        'cert_path': '/path/to/cert.pem',
                        'key_path': '/path/to/key.pem',
                        'private_key': '-----BEGIN PRIVATE KEY-----'  # Sensitive
                    }
                },
                'secondary': {
                    'host': 'db2.example.com',
                    'port': 5433,
                    'credentials': {
                        'username': 'dbuser2',
                        'password': 'secret456'  # Sensitive
                    }
                }
            },
            'apis': [
                {
                    'name': 'api1',
                    'endpoint': 'https://api1.example.com',
                    'auth': {
                        'type': 'bearer',
                        'token': 'sk-1234567890abcdefghijklmnopqrstuvwxyz'  # Sensitive
                    }
                },
                {
                    'name': 'api2',
                    'endpoint': 'https://api2.example.com',
                    'auth': {
                        'type': 'basic',
                        'username': 'apiuser',
                        'password': 'apipass123'  # Sensitive
                    }
                }
            ],
            'settings': {
                'timeout': 30,
                'retries': 3,
                'debug': False
            }
        }
        
        masked_config = self.security_manager.mask_sensitive_data(complex_config)
        
        # Verify structure is preserved
        assert masked_config['version'] == '1.0'
        assert 'databases' in masked_config
        assert 'primary' in masked_config['databases']
        assert 'secondary' in masked_config['databases']
        assert 'apis' in masked_config
        assert len(masked_config['apis']) == 2
        assert 'settings' in masked_config
        
        # Verify sensitive data is masked
        assert masked_config['databases']['primary']['credentials']['password'] == '***MASKED***'
        assert masked_config['databases']['primary']['ssl']['private_key'] == '***MASKED***'
        assert masked_config['databases']['secondary']['credentials']['password'] == '***MASKED***'
        assert masked_config['apis'][0]['auth']['token'] == '***MASKED***'
        assert masked_config['apis'][1]['auth']['password'] == '***MASKED***'
        
        # Verify non-sensitive data is preserved
        assert masked_config['databases']['primary']['host'] == 'db1.example.com'
        assert masked_config['databases']['primary']['port'] == 5432
        assert masked_config['databases']['primary']['credentials']['username'] == 'dbuser'
        assert masked_config['apis'][0]['name'] == 'api1'
        assert masked_config['apis'][0]['endpoint'] == 'https://api1.example.com'
        assert masked_config['settings']['timeout'] == 30
    
    def test_security_validation_performance(self):
        """Test performance of security validation with large configurations."""
        import time
        
        # Create large configuration with mixed sensitive and safe data
        large_config = {'version': '1.0'}
        
        # Add many safe configuration entries
        for i in range(500):
            large_config[f'service_{i}'] = {
                'name': f'service-{i}',
                'host': f'host-{i}.example.com',
                'port': 8080 + i,
                'timeout': 30,
                'retries': 3,
                'enabled': i % 2 == 0,
                'metadata': {
                    'version': f'1.{i}.0',
                    'description': f'Service {i} description',
                    'tags': [f'tag-{j}' for j in range(3)]
                }
            }
        
        # Add some sensitive entries scattered throughout
        for i in range(0, 500, 50):  # Every 50th entry
            large_config[f'service_{i}']['password'] = f'secret-{i}'
            large_config[f'service_{i}']['api_token'] = f'sk-{i:032d}'
            large_config[f'service_{i}']['metadata']['secret_key'] = f'key-{i}'
        
        # Measure validation performance
        start_time = time.time()
        
        warnings = self.security_manager.validate_config_security(large_config)
        
        validation_time = time.time() - start_time
        
        # Should complete validation quickly (less than 2 seconds)
        assert validation_time < 2.0, f"Validation took {validation_time:.2f}s, which is too slow"
        
        # Should detect all sensitive data (3 sensitive fields × 10 services = 30 warnings)
        assert len(warnings) == 30
        
        # Verify specific warnings
        warning_text = ' '.join(warnings)
        assert 'service_0.password' in warning_text
        assert 'service_0.api_token' in warning_text
        assert 'service_0.metadata.secret_key' in warning_text
    
    def test_configuration_security_with_different_data_types(self):
        """Test security validation with different data types."""
        mixed_type_config = {
            'string_password': 'secret123',  # String - sensitive
            'number_port': 5432,  # Number - not sensitive
            'boolean_debug': True,  # Boolean - not sensitive
            'null_value': None,  # Null - not sensitive
            'list_with_secrets': [
                'normal-value',
                'sk-1234567890abcdefghijklmnopqrstuvwxyz',  # String in list - sensitive
                123,  # Number in list - not sensitive
                True  # Boolean in list - not sensitive
            ],
            'nested_object': {
                'api_key': 'ghp_1234567890abcdefghijklmnopqrstuvwxyz',  # Sensitive
                'timeout': 30,  # Not sensitive
                'enabled': False  # Not sensitive
            }
        }
        
        warnings = self.security_manager.validate_config_security(mixed_type_config)
        
        # Should detect sensitive strings only
        assert len(warnings) >= 3  # string_password, list item, nested api_key
        
        warning_text = ' '.join(warnings)
        assert 'string_password' in warning_text
        assert 'list_with_secrets[1]' in warning_text
        assert 'nested_object.api_key' in warning_text
        
        # Should not warn about non-string values
        assert 'number_port' not in warning_text
        assert 'boolean_debug' not in warning_text
        assert 'null_value' not in warning_text
    
    def test_gitignore_security_entries(self):
        """Test that .gitignore entries cover comprehensive security patterns."""
        gitignore_entries = self.security_manager.create_gitignore_entries()
        
        # Should include configuration files
        assert 'config.yaml' in gitignore_entries
        assert 'config.yml' in gitignore_entries
        assert '.env' in gitignore_entries
        assert '.env.*' in gitignore_entries
        
        # Should include key files
        assert '*.key' in gitignore_entries
        assert '*.pem' in gitignore_entries
        assert '*.pfx' in gitignore_entries
        assert '*.p12' in gitignore_entries
        
        # Should include credential files
        assert '**/credentials.json' in gitignore_entries
        assert '**/service-account*.json' in gitignore_entries
        assert 'service-account*.json' in gitignore_entries
        assert '*-key.json' in gitignore_entries
        
        # Should include cloud provider specific patterns
        assert '.aws/credentials' in gitignore_entries
        assert 'aws-key/' in gitignore_entries
        assert 'gcp-key/' in gitignore_entries
        assert '.azure/' in gitignore_entries
        assert '.oci/config' in gitignore_entries
        assert '.oci/sessions/' in gitignore_entries
        assert '.cloudflare/' in gitignore_entries
        
        # Should include SSH keys
        assert 'id_rsa*' in gitignore_entries
        assert '*.ppk' in gitignore_entries
        
        # Should include logs and temporary files
        assert 'logs/' in gitignore_entries
        assert '*.tmp' in gitignore_entries
        assert '*.temp' in gitignore_entries
        assert '*.bak' in gitignore_entries
        assert '.DS_Store' in gitignore_entries


if __name__ == '__main__':
    pytest.main([__file__])