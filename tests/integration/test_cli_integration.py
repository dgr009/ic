"""
Integration tests for CLI command execution with new configuration system.

Tests CLI commands with the new YAML configuration system and security features.
"""

import os
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ic.config.manager import ConfigManager
from ic.config.security import SecurityManager
from ic.core.logging import ICLogger


class TestCLIIntegration:
    """Integration tests for CLI functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.config_manager = ConfigManager(security_manager=self.security_manager)
        
        # Sample configuration for testing
        self.test_config = {
            "version": "1.0",
            "logging": {
                "console_level": "ERROR",
                "file_level": "INFO",
                "file_path": "logs/ic_{date}.log",
                "max_files": 10,
                "mask_sensitive": True
            },
            "aws": {
                "accounts": ["123456789012", "987654321098"],
                "regions": ["us-east-1", "us-west-2"],
                "cross_account_role": "OrganizationAccountAccessRole",
                "max_workers": 5,
                "tags": {
                    "required": ["User", "Team", "Environment"],
                    "rules": {
                        "Environment": "^(PROD|STG|DEV|TEST)$"
                    }
                }
            },
            "azure": {
                "subscriptions": ["sub-12345"],
                "locations": ["East US"],
                "max_workers": 5
            },
            "gcp": {
                "projects": ["my-gcp-project"],
                "regions": ["us-central1"],
                "max_workers": 5
            },
            "security": {
                "sensitive_keys": ["password", "token", "key", "secret"],
                "mask_pattern": "***MASKED***",
                "warn_on_sensitive_in_config": True
            }
        }
    
    def create_temp_config_file(self, config_data):
        """Create temporary configuration file."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.config_manager.save_config(temp_file.name, config_data)
        temp_file.close()
        return temp_file.name
    
    @pytest.mark.requires_config
    def test_config_command_integration(self):
        """Test configuration management CLI commands."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'config.yaml'
            
            # Test config initialization
            from ic.commands.config import init_config
            
            with patch('ic.config.manager.ConfigManager') as mock_manager_class:
                mock_manager = Mock()
                mock_manager_class.return_value = mock_manager
                
                result = init_config(config_file)
                
                # Verify config manager was used
                mock_manager_class.assert_called_once()
                mock_manager.save_config.assert_called_once()
    
    def test_config_validation_integration(self):
        """Test configuration validation CLI command."""
        config_file = self.create_temp_config_file(self.test_config)
        
        try:
            from ic.commands.config import validate_config
            
            # Test valid configuration
            errors = validate_config(config_file)
            assert len(errors) == 0
            
            # Test invalid configuration
            invalid_config = {"invalid": "config"}
            invalid_config_file = self.create_temp_config_file(invalid_config)
            
            try:
                errors = validate_config(invalid_config_file)
                assert len(errors) > 0
                assert any("missing required section" in error for error in errors)
            finally:
                os.unlink(invalid_config_file)
                
        finally:
            os.unlink(config_file)
    
    def test_config_migration_integration(self):
        """Test configuration migration CLI command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file
            env_file = Path(temp_dir) / '.env'
            env_content = """
AWS_REGION=us-east-1
AWS_ACCOUNTS=123456789012,987654321098
AZURE_SUBSCRIPTION_ID=sub-12345
GCP_PROJECT_ID=my-gcp-project
IC_LOG_LEVEL=DEBUG
"""
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            # Test migration command
            from ic.commands.config import migrate_config
            
            yaml_config_file = Path(temp_dir) / 'config.yaml'
            
            with patch('src.ic.config.migration.ConfigMigration') as mock_migration_class:
                mock_migration = Mock()
                mock_migration.migrate_to_yaml.return_value = True
                mock_migration_class.return_value = mock_migration
                
                success = migrate_config(env_file, yaml_config_file)
                
                assert success is True
                mock_migration_class.assert_called_once()
                mock_migration.migrate_to_yaml.assert_called_once()
    
    def test_logging_integration_with_cli(self):
        """Test logging system integration with CLI commands."""
        config_file = self.create_temp_config_file(self.test_config)
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Update config to use temp directory for logs
                test_config = self.test_config.copy()
                test_config['logging']['file_path'] = f"{temp_dir}/ic_{{date}}.log"
                
                updated_config_file = self.create_temp_config_file(test_config)
                
                try:
                    # Initialize logger with configuration
                    config_manager = ConfigManager(security_manager=self.security_manager)
                    config = config_manager.load_config([updated_config_file])
                    
                    logger = ICLogger(config)
                    
                    # Test various log levels
                    logger.log_info_file_only("Test info message")
                    logger.log_warning("Test warning message")
                    logger.log_error("Test error message")
                    logger.log_debug("Test debug message")
                    
                    # Test args logging
                    test_args = {'profile': 'test-profile', 'region': 'us-east-1'}
                    logger.log_args(test_args)
                    
                    # Verify log file was created
                    log_files = list(Path(temp_dir).glob('ic_*.log'))
                    assert len(log_files) > 0
                    
                    # Verify log content
                    with open(log_files[0], 'r') as f:
                        log_content = f.read()
                    
                    assert "Test info message" in log_content
                    assert "Test warning message" in log_content
                    assert "Test error message" in log_content
                    assert "Test debug message" in log_content
                    assert "Args:" in log_content
                    
                finally:
                    os.unlink(updated_config_file)
                    
        finally:
            os.unlink(config_file)
    
    def test_security_integration_with_cli(self):
        """Test security features integration with CLI."""
        # Create config with sensitive data
        sensitive_config = self.test_config.copy()
        sensitive_config['test_password'] = 'secret123'
        sensitive_config['api_token'] = 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
        
        config_file = self.create_temp_config_file(sensitive_config)
        
        try:
            # Load configuration with security manager
            config_manager = ConfigManager(security_manager=self.security_manager)
            
            with patch('logging.Logger.warning') as mock_warning:
                config = config_manager.load_config([config_file])
                
                # Verify security warnings were logged
                warning_calls = [call[0][0] for call in mock_warning.call_args_list]
                assert any('sensitive data' in warning.lower() for warning in warning_calls)
            
            # Test sensitive data masking in logging
            logger = ICLogger(config)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Update log path
                logger.log_file_path = f"{temp_dir}/test.log"
                logger.logger.handlers[1].baseFilename = logger.log_file_path
                
                # Log message with sensitive data
                logger.log_info_file_only("Using password=secret123 for authentication")
                
                # Verify sensitive data was masked in log file
                with open(logger.log_file_path, 'r') as f:
                    log_content = f.read()
                
                assert "password=***MASKED***" in log_content
                assert "secret123" not in log_content
                
        finally:
            os.unlink(config_file)
    
    def test_backward_compatibility_integration(self):
        """Test backward compatibility with existing CLI patterns."""
        # Test that old .env file patterns still work
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_content = """
AWS_PROFILE=default
AWS_REGION=us-east-1
AZURE_SUBSCRIPTION_ID=sub-12345
"""
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            # Test loading with environment variables
            env_vars = {
                'AWS_PROFILE': 'default',
                'AWS_REGION': 'us-east-1',
                'AZURE_SUBSCRIPTION_ID': 'sub-12345'
            }
            
            with patch.dict(os.environ, env_vars):
                config_manager = ConfigManager(security_manager=self.security_manager)
                config = config_manager.load_config([])  # No config files, just env vars
                
                # Verify environment variables were loaded
                assert config['aws']['default_profile'] == 'default'
                assert config['aws']['default_region'] == 'us-east-1'
                assert config['azure']['subscription_id'] == 'sub-12345'
    
    def test_cli_error_handling_integration(self):
        """Test CLI error handling with configuration system."""
        # Test with missing configuration file
        non_existent_config = Path('/nonexistent/config.yaml')
        
        config_manager = ConfigManager(security_manager=self.security_manager)
        
        # Should handle missing file gracefully
        config = config_manager.load_config([non_existent_config])
        
        # Should return default configuration
        assert config['version'] == '1.0'
        assert 'logging' in config
        assert 'aws' in config
        
        # Test with invalid configuration file
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_config_file = Path(temp_dir) / 'invalid.yaml'
            with open(invalid_config_file, 'w') as f:
                f.write("invalid: yaml: content: [")
            
            # Should handle invalid YAML gracefully
            with patch('logging.Logger.warning') as mock_warning:
                config = config_manager.load_config([invalid_config_file])
                
                # Should log warning about invalid file
                assert mock_warning.called
                
                # Should still return default configuration
                assert config['version'] == '1.0'
    
    def test_configuration_precedence_integration(self):
        """Test configuration precedence in CLI context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple configuration files
            default_config = {
                'version': '1.0',
                'aws': {'regions': ['us-east-1'], 'max_workers': 10},
                'logging': {'console_level': 'ERROR'}
            }
            
            user_config = {
                'aws': {'regions': ['us-west-2'], 'accounts': ['123456789012']},
                'logging': {'console_level': 'WARNING'}
            }
            
            project_config = {
                'aws': {'max_workers': 20},
                'logging': {'file_level': 'DEBUG'}
            }
            
            # Create config files
            default_config_file = self.create_temp_config_file(default_config)
            user_config_file = self.create_temp_config_file(user_config)
            project_config_file = self.create_temp_config_file(project_config)
            
            try:
                # Load with precedence order
                config_manager = ConfigManager(security_manager=self.security_manager)
                config = config_manager.load_config([
                    default_config_file,
                    user_config_file,
                    project_config_file
                ])
                
                # Verify precedence (later configs override earlier ones)
                assert config['aws']['regions'] == ['us-west-2']  # From user config
                assert config['aws']['accounts'] == ['123456789012']  # From user config
                assert config['aws']['max_workers'] == 20  # From project config
                assert config['logging']['console_level'] == 'WARNING'  # From user config
                assert config['logging']['file_level'] == 'DEBUG'  # From project config
                
                # Test with environment variable override
                env_vars = {
                    'AWS_REGION': 'eu-west-1',
                    'AWS_MAX_WORKERS': '30'
                }
                
                with patch.dict(os.environ, env_vars):
                    config = config_manager.load_config([
                        default_config_file,
                        user_config_file,
                        project_config_file
                    ])
                    
                    # Environment variables should have highest precedence
                    assert config['aws']['default_region'] == 'eu-west-1'
                    assert config['aws']['max_workers'] == 30
                    
            finally:
                os.unlink(default_config_file)
                os.unlink(user_config_file)
                os.unlink(project_config_file)
    
    def test_cli_performance_integration(self):
        """Test CLI performance with configuration system."""
        import time
        
        # Create large configuration for performance testing
        large_config = self.test_config.copy()
        large_config['aws']['accounts'] = [f"{i:012d}" for i in range(100)]
        large_config['aws']['regions'] = [f"region-{i}" for i in range(50)]
        
        config_file = self.create_temp_config_file(large_config)
        
        try:
            # Measure configuration loading time
            start_time = time.time()
            
            config_manager = ConfigManager(security_manager=self.security_manager)
            config = config_manager.load_config([config_file])
            
            load_time = time.time() - start_time
            
            # Should load reasonably quickly (less than 1 second)
            assert load_time < 1.0
            
            # Verify configuration was loaded correctly
            assert len(config['aws']['accounts']) == 100
            assert len(config['aws']['regions']) == 50
            
            # Test logger initialization performance
            start_time = time.time()
            
            logger = ICLogger(config)
            
            logger_init_time = time.time() - start_time
            
            # Logger should initialize quickly
            assert logger_init_time < 0.5
            
        finally:
            os.unlink(config_file)
    
    @pytest.mark.requires_credentials
    def test_aws_profile_command_integration(self):
        """Test AWS profile info command integration."""
        with patch('aws.profile.info.ProfileInfoCollector') as mock_collector_class:
            with patch('aws.profile.info.ProfileTableRenderer') as mock_renderer_class:
                # Mock the collector and renderer
                mock_collector = Mock()
                mock_renderer = Mock()
                mock_collector_class.return_value = mock_collector
                mock_renderer_class.return_value = mock_renderer
                
                # Mock profile data
                mock_profiles = [
                    {
                        'profile_name': 'default',
                        'account_id': '123456789012',
                        'source': '',
                        'role_name': '',
                        'credential': 'active',
                        'region': 'us-east-1'
                    },
                    {
                        'profile_name': 'dev',
                        'account_id': '123456789012',
                        'source': 'default',
                        'role_name': 'DevRole',
                        'credential': 'inactive',
                        'region': 'us-west-2'
                    }
                ]
                mock_collector.collect_profile_info.return_value = mock_profiles
                
                # Test command execution
                from ic.cli import create_parser
                parser = create_parser()
                args = parser.parse_args(['aws', 'profile', 'info'])
                
                # Execute the command function
                try:
                    args.func(args)
                except SystemExit:
                    pass  # Command may exit normally
                
                # Verify collector and renderer were called
                mock_collector.collect_profile_info.assert_called_once()
                mock_renderer.render_profiles.assert_called_once_with(mock_profiles)
    
    @pytest.mark.requires_credentials
    def test_aws_cloudfront_command_integration(self):
        """Test AWS CloudFront info command integration."""
        with patch('aws.cloudfront.info.CloudFrontCollector') as mock_collector_class:
            with patch('aws.cloudfront.info.CloudFrontRenderer') as mock_renderer_class:
                # Mock the collector and renderer
                mock_collector = Mock()
                mock_renderer = Mock()
                mock_collector_class.return_value = mock_collector
                mock_renderer_class.return_value = mock_renderer
                
                # Mock distribution data
                mock_distributions = [
                    {
                        'account': 'default',
                        'ID': 'E1234567890ABC',
                        'Name': 'Test Distribution',
                        '원본(Origin)': 'example.com',
                        '도메인(Domain)': 'd1234567890abc.cloudfront.net',
                        'Class': 'All Edge Locations'
                    }
                ]
                mock_collector.collect_distributions.return_value = mock_distributions
                
                # Test command execution
                from ic.cli import create_parser
                parser = create_parser()
                args = parser.parse_args(['aws', 'cloudfront', 'info'])
                
                # Execute the command function
                try:
                    args.func(args)
                except SystemExit:
                    pass  # Command may exit normally
                
                # Verify collector and renderer were called
                mock_collector.collect_distributions.assert_called_once()
                mock_renderer.render_distributions.assert_called_once_with(mock_distributions)
    
    @pytest.mark.requires_credentials
    def test_oci_compartment_command_integration(self):
        """Test OCI compartment tree command integration."""
        with patch('oci.config.from_file') as mock_config_from_file:
            with patch('oci.identity.IdentityClient') as mock_identity_client_class:
                with patch('oci_module.compartment.info.CompartmentTreeBuilder') as mock_builder_class:
                    with patch('oci_module.compartment.info.CompartmentTreeRenderer') as mock_renderer_class:
                        # Mock OCI configuration
                        mock_config = {
                            'tenancy': 'ocid1.tenancy.oc1..test',
                            'user': 'ocid1.user.oc1..test',
                            'fingerprint': 'test-fingerprint',
                            'key_file': '/path/to/key.pem',
                            'region': 'us-ashburn-1'
                        }
                        mock_config_from_file.return_value = mock_config
                        
                        # Mock identity client
                        mock_identity_client = Mock()
                        mock_identity_client_class.return_value = mock_identity_client
                        
                        # Mock tree builder and renderer
                        mock_builder = Mock()
                        mock_renderer = Mock()
                        mock_builder_class.return_value = mock_builder
                        mock_renderer_class.return_value = mock_renderer
                        
                        # Mock tree data
                        mock_tree_data = {
                            'id': 'ocid1.tenancy.oc1..test',
                            'name': 'Root Compartment (Tenancy)',
                            'children': [
                                {
                                    'id': 'ocid1.compartment.oc1..child1',
                                    'name': 'Development',
                                    'children': []
                                }
                            ]
                        }
                        mock_builder.build_compartment_tree.return_value = mock_tree_data
                        
                        # Test command execution
                        from ic.cli import create_parser
                        parser = create_parser()
                        args = parser.parse_args(['oci', 'compartment', 'tree'])
                        
                        # Execute the command function
                        try:
                            args.func(args)
                        except SystemExit:
                            pass  # Command may exit normally
                        
                        # Verify OCI configuration was loaded
                        mock_config_from_file.assert_called_once()
                        
                        # Verify identity client was created
                        mock_identity_client_class.assert_called_once_with(mock_config)
                        
                        # Verify tree builder and renderer were called
                        mock_builder.build_compartment_tree.assert_called_once()
                        mock_renderer.render_tree.assert_called_once_with(mock_tree_data)
    
    def test_config_show_aws_filter_integration(self):
        """Test config show command with AWS filter integration."""
        config_file = self.create_temp_config_file(self.test_config)
        
        try:
            with patch('src.ic.commands.config.ConfigCommands') as mock_config_commands_class:
                mock_config_commands = Mock()
                mock_config_commands_class.return_value = mock_config_commands
                
                # Test command execution
                from ic.cli import create_parser
                parser = create_parser()
                args = parser.parse_args(['config', 'show', '--aws'])
                
                # Execute the command function
                try:
                    args.func(args)
                except SystemExit:
                    pass  # Command may exit normally
                
                # Verify config commands was called with AWS filter
                mock_config_commands.show_config.assert_called_once()
                call_args = mock_config_commands.show_config.call_args[1]
                assert call_args.get('aws') is True
                
        finally:
            os.unlink(config_file)
    
    def test_cli_error_handling_for_new_commands(self):
        """Test error handling for new CLI commands."""
        # Test AWS profile command with missing credentials
        with patch('aws.profile.info.ProfileInfoCollector') as mock_collector_class:
            mock_collector = Mock()
            mock_collector_class.return_value = mock_collector
            mock_collector.collect_profile_info.side_effect = FileNotFoundError("AWS config not found")
            
            from ic.cli import create_parser
            parser = create_parser()
            args = parser.parse_args(['aws', 'profile', 'info'])
            
            # Should handle error gracefully
            with pytest.raises(SystemExit):
                args.func(args)
        
        # Test OCI compartment command with missing configuration
        with patch('oci.config.from_file') as mock_config_from_file:
            mock_config_from_file.side_effect = Exception("OCI config not found")
            
            parser = create_parser()
            args = parser.parse_args(['oci', 'compartment', 'tree'])
            
            # Should handle error gracefully
            with pytest.raises(SystemExit):
                args.func(args)
    
    def test_cli_argument_parsing_integration(self):
        """Test CLI argument parsing for new commands."""
        from ic.cli import create_parser
        parser = create_parser()
        
        # Test AWS profile command arguments
        args = parser.parse_args(['aws', 'profile', 'info', '--config-path', '/custom/config'])
        assert args.platform == 'aws'
        assert args.service == 'profile'
        assert args.command == 'info'
        assert args.config_path == '/custom/config'
        
        # Test AWS CloudFront command arguments
        args = parser.parse_args(['aws', 'cloudfront', 'info', '--profile', 'prod', '--accounts', 'acc1', 'acc2'])
        assert args.platform == 'aws'
        assert args.service == 'cloudfront'
        assert args.command == 'info'
        assert args.profile == 'prod'
        assert args.accounts == ['acc1', 'acc2']
        
        # Test OCI compartment command arguments
        args = parser.parse_args(['oci', 'compartment', 'tree', '--profile', 'CUSTOM'])
        assert args.platform == 'oci'
        assert args.service == 'compartment'
        assert args.command == 'tree'
        assert args.profile == 'CUSTOM'
        
        # Test config show command arguments
        args = parser.parse_args(['config', 'show', '--aws', '--format', 'json'])
        assert args.command == 'show'
        assert args.aws is True
        assert args.format == 'json'


if __name__ == '__main__':
    pytest.main([__file__])