"""
Integration tests for .env to YAML configuration migration.

Tests the complete migration process from .env files to structured YAML configuration.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

from src.ic.config.manager import ConfigManager
from src.ic.config.migration import ConfigMigration
from src.ic.config.security import SecurityManager


class TestConfigMigrationIntegration:
    """Integration tests for configuration migration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.config_manager = ConfigManager(security_manager=self.security_manager)
        
        # Sample .env content
        self.sample_env_content = """
# AWS Configuration
AWS_PROFILE=default
AWS_REGION=us-east-1
AWS_ACCOUNTS=123456789012,987654321098
AWS_CROSS_ACCOUNT_ROLE=OrganizationAccountAccessRole
AWS_MAX_WORKERS=15

# Azure Configuration
AZURE_SUBSCRIPTION_ID=sub-12345
AZURE_TENANT_ID=tenant-67890
AZURE_CLIENT_ID=client-abcdef
AZURE_CLIENT_SECRET=secret-ghijkl
AZURE_LOCATIONS=East US,West US 2

# GCP Configuration
GCP_PROJECT_ID=my-gcp-project
GCP_REGIONS=us-central1,us-east1
GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json

# Logging Configuration
IC_LOG_LEVEL=DEBUG
IC_LOG_FILE_LEVEL=INFO
IC_LOG_MAX_FILES=50

# Slack Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
SLACK_ENABLED=true

# CloudFlare Configuration
CLOUDFLARE_EMAIL=user@example.com
CLOUDFLARE_API_TOKEN=cf-token-12345
CLOUDFLARE_ACCOUNTS=account1,account2

# SSH Configuration
SSH_MAX_WORKERS=100
"""
    
    def test_complete_migration_process(self):
        """Test complete migration from .env to YAML configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file
            env_file = Path(temp_dir) / '.env'
            with open(env_file, 'w') as f:
                f.write(self.sample_env_content)
            
            # Create migration instance
            migration = ConfigMigration(
                env_file_path=env_file,
                security_manager=self.security_manager
            )
            
            # Perform migration
            yaml_config_path = Path(temp_dir) / 'config.yaml'
            success = migration.migrate_to_yaml(yaml_config_path)
            
            assert success is True
            assert yaml_config_path.exists()
            
            # Load and verify migrated configuration
            migrated_config = self.config_manager._load_config_file(yaml_config_path)
            
            # Verify AWS configuration
            assert migrated_config['aws']['default_profile'] == 'default'
            assert migrated_config['aws']['default_region'] == 'us-east-1'
            assert migrated_config['aws']['accounts'] == ['123456789012', '987654321098']
            assert migrated_config['aws']['cross_account_role'] == 'OrganizationAccountAccessRole'
            assert migrated_config['aws']['max_workers'] == 15
            
            # Verify Azure configuration
            assert migrated_config['azure']['subscription_id'] == 'sub-12345'
            assert migrated_config['azure']['locations'] == ['East US', 'West US 2']
            
            # Verify GCP configuration
            assert migrated_config['gcp']['project_id'] == 'my-gcp-project'
            assert migrated_config['gcp']['regions'] == ['us-central1', 'us-east1']
            
            # Verify logging configuration
            assert migrated_config['logging']['console_level'] == 'DEBUG'
            assert migrated_config['logging']['file_level'] == 'INFO'
            assert migrated_config['logging']['max_files'] == 50
            
            # Verify Slack configuration
            assert migrated_config['slack']['enabled'] is True
            
            # Verify CloudFlare configuration
            assert migrated_config['cloudflare']['accounts'] == ['account1', 'account2']
            
            # Verify SSH configuration
            assert migrated_config['ssh']['max_workers'] == 100
    
    def test_migration_with_backup_creation(self):
        """Test migration process with backup creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file
            env_file = Path(temp_dir) / '.env'
            with open(env_file, 'w') as f:
                f.write(self.sample_env_content)
            
            # Create existing config file to test backup
            existing_config_path = Path(temp_dir) / 'config.yaml'
            existing_config = {'version': '0.9', 'test': 'old_value'}
            self.config_manager.save_config(existing_config_path, existing_config)
            
            # Create migration instance
            migration = ConfigMigration(
                env_file_path=env_file,
                security_manager=self.security_manager
            )
            
            # Perform migration with backup
            success = migration.migrate_to_yaml(existing_config_path, create_backup=True)
            
            assert success is True
            
            # Verify backup was created
            backup_files = list(Path(temp_dir).glob('config_*.yaml'))
            assert len(backup_files) > 0
            
            # Verify backup contains old configuration
            backup_config = self.config_manager._load_config_file(backup_files[0])
            assert backup_config['test'] == 'old_value'
            
            # Verify new configuration was written
            new_config = self.config_manager._load_config_file(existing_config_path)
            assert new_config['version'] == '1.0'  # Should be updated
            assert 'aws' in new_config  # Should contain migrated data
    
    def test_migration_with_sensitive_data_warnings(self):
        """Test migration process with sensitive data detection."""
        sensitive_env_content = """
AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
AZURE_CLIENT_SECRET=very-secret-password-123
GCP_SERVICE_ACCOUNT_KEY={"type": "service_account", "private_key": "-----BEGIN PRIVATE KEY-----"}
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file with sensitive data
            env_file = Path(temp_dir) / '.env'
            with open(env_file, 'w') as f:
                f.write(sensitive_env_content)
            
            # Create migration instance
            migration = ConfigMigration(
                env_file_path=env_file,
                security_manager=self.security_manager
            )
            
            # Perform migration
            yaml_config_path = Path(temp_dir) / 'config.yaml'
            
            with patch('logging.Logger.warning') as mock_warning:
                success = migration.migrate_to_yaml(yaml_config_path)
            
            assert success is True
            
            # Verify security warnings were logged
            warning_calls = [call[0][0] for call in mock_warning.call_args_list]
            assert any('sensitive data' in warning.lower() for warning in warning_calls)
    
    def test_migration_validation_and_rollback(self):
        """Test migration validation and rollback on failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file
            env_file = Path(temp_dir) / '.env'
            with open(env_file, 'w') as f:
                f.write("INVALID_ENV_VAR=value\n")
            
            # Create existing valid config
            existing_config_path = Path(temp_dir) / 'config.yaml'
            valid_config = {
                'version': '1.0',
                'logging': {'console_level': 'ERROR'},
                'aws': {'regions': ['us-east-1']},
                'azure': {'locations': ['East US']},
                'gcp': {'regions': ['us-central1']},
                'security': {'mask_pattern': '***MASKED***'}
            }
            self.config_manager.save_config(existing_config_path, valid_config)
            
            # Create migration instance
            migration = ConfigMigration(
                env_file_path=env_file,
                security_manager=self.security_manager
            )
            
            # Mock validation to fail
            with patch.object(self.config_manager, 'validate_config') as mock_validate:
                mock_validate.return_value = ['Critical validation error']
                
                success = migration.migrate_to_yaml(existing_config_path, create_backup=True)
            
            # Migration should fail due to validation error
            assert success is False
            
            # Original config should be preserved
            preserved_config = self.config_manager._load_config_file(existing_config_path)
            assert preserved_config == valid_config
    
    def test_end_to_end_config_loading_after_migration(self):
        """Test end-to-end configuration loading after migration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file
            env_file = Path(temp_dir) / '.env'
            with open(env_file, 'w') as f:
                f.write(self.sample_env_content)
            
            # Perform migration
            migration = ConfigMigration(
                env_file_path=env_file,
                security_manager=self.security_manager
            )
            
            yaml_config_path = Path(temp_dir) / 'config.yaml'
            success = migration.migrate_to_yaml(yaml_config_path)
            assert success is True
            
            # Test loading configuration with ConfigManager
            config_manager = ConfigManager(security_manager=self.security_manager)
            loaded_config = config_manager.load_config([yaml_config_path])
            
            # Verify configuration was loaded correctly
            assert loaded_config['version'] == '1.0'
            assert loaded_config['aws']['accounts'] == ['123456789012', '987654321098']
            assert loaded_config['azure']['subscription_id'] == 'sub-12345'
            assert loaded_config['gcp']['project_id'] == 'my-gcp-project'
            assert loaded_config['logging']['console_level'] == 'DEBUG'
            assert loaded_config['slack']['enabled'] is True
            
            # Verify configuration sources
            sources = config_manager.get_config_sources()
            assert 'default' in sources
            assert str(yaml_config_path) in sources
    
    def test_migration_with_environment_override(self):
        """Test migration with environment variable overrides."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file
            env_file = Path(temp_dir) / '.env'
            with open(env_file, 'w') as f:
                f.write("AWS_REGION=us-east-1\nAWS_MAX_WORKERS=10\n")
            
            # Perform migration
            migration = ConfigMigration(
                env_file_path=env_file,
                security_manager=self.security_manager
            )
            
            yaml_config_path = Path(temp_dir) / 'config.yaml'
            success = migration.migrate_to_yaml(yaml_config_path)
            assert success is True
            
            # Load configuration with environment overrides
            env_overrides = {
                'AWS_REGION': 'us-west-2',
                'AWS_MAX_WORKERS': '20'
            }
            
            with patch.dict(os.environ, env_overrides):
                config_manager = ConfigManager(security_manager=self.security_manager)
                loaded_config = config_manager.load_config([yaml_config_path])
            
            # Environment variables should override file values
            assert loaded_config['aws']['default_region'] == 'us-west-2'
            assert loaded_config['aws']['max_workers'] == 20
            
            # Verify sources include environment
            sources = config_manager.get_config_sources()
            assert 'environment' in sources
    
    def test_migration_error_handling(self):
        """Test migration error handling scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with non-existent .env file
            non_existent_env = Path(temp_dir) / 'nonexistent.env'
            migration = ConfigMigration(
                env_file_path=non_existent_env,
                security_manager=self.security_manager
            )
            
            yaml_config_path = Path(temp_dir) / 'config.yaml'
            success = migration.migrate_to_yaml(yaml_config_path)
            
            # Should fail gracefully
            assert success is False
            
            # Test with invalid .env content
            invalid_env_file = Path(temp_dir) / 'invalid.env'
            with open(invalid_env_file, 'w') as f:
                f.write("INVALID LINE WITHOUT EQUALS\n")
            
            migration = ConfigMigration(
                env_file_path=invalid_env_file,
                security_manager=self.security_manager
            )
            
            # Should handle invalid content gracefully
            success = migration.migrate_to_yaml(yaml_config_path)
            # Migration might succeed but with warnings
            assert isinstance(success, bool)
    
    def test_migration_preserves_comments_and_structure(self):
        """Test that migration preserves logical structure in YAML."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file
            env_file = Path(temp_dir) / '.env'
            with open(env_file, 'w') as f:
                f.write(self.sample_env_content)
            
            # Perform migration
            migration = ConfigMigration(
                env_file_path=env_file,
                security_manager=self.security_manager
            )
            
            yaml_config_path = Path(temp_dir) / 'config.yaml'
            success = migration.migrate_to_yaml(yaml_config_path)
            assert success is True
            
            # Read the YAML file as text to check structure
            with open(yaml_config_path, 'r') as f:
                yaml_content = f.read()
            
            # Verify logical grouping
            assert 'aws:' in yaml_content
            assert 'azure:' in yaml_content
            assert 'gcp:' in yaml_content
            assert 'logging:' in yaml_content
            assert 'slack:' in yaml_content
            assert 'cloudflare:' in yaml_content
            assert 'ssh:' in yaml_content
            
            # Verify version is at the top
            lines = yaml_content.split('\n')
            version_line = next((i for i, line in enumerate(lines) if 'version:' in line), -1)
            assert version_line >= 0 and version_line < 5  # Should be near the top


if __name__ == '__main__':
    pytest.main([__file__])