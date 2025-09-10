"""
CI/CD Configuration Tests

Tests specifically designed for CI/CD environments that don't require:
- Live cloud credentials
- ~/.ic/config files
- External network access
- Specific file system permissions

These tests focus on configuration handling, parsing, and basic functionality
that can be verified in isolated CI environments.

Requirements: 9.4, 10.1, 10.2 - CI/CD testing infrastructure
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add project root for common modules
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestCIConfigurationHandling:
    """Test configuration handling in CI environments."""
    
    def test_config_manager_with_no_files(self, ci_environment):
        """Test ConfigManager works when no config files exist."""
        from ic.config.manager import ConfigManager
        from ic.config.security import SecurityManager
        
        security_manager = SecurityManager()
        config_manager = ConfigManager(security_manager=security_manager)
        
        # Load config with empty file list
        config = config_manager.load_config([])
        
        # Should return valid default configuration
        assert config is not None
        assert config['version'] == '1.0'
        assert 'logging' in config
        assert 'aws' in config
        assert 'azure' in config
        assert 'gcp' in config
        assert 'security' in config
        
        # Verify default values
        assert config['logging']['console_level'] == 'ERROR'
        assert config['aws']['regions'] == ['ap-northeast-2']
        assert config['security']['mask_pattern'] == '***MASKED***'
    
    def test_config_manager_with_nonexistent_files(self, ci_environment):
        """Test ConfigManager gracefully handles non-existent files."""
        from ic.config.manager import ConfigManager
        from ic.config.security import SecurityManager
        
        security_manager = SecurityManager()
        config_manager = ConfigManager(security_manager=security_manager)
        
        # Try to load non-existent files
        non_existent_files = [
            Path('/nonexistent/config1.yaml'),
            Path('/nonexistent/config2.yaml'),
            Path('/home/user/.ic/config/default.yaml')
        ]
        
        config = config_manager.load_config(non_existent_files)
        
        # Should still return valid configuration
        assert config is not None
        assert config['version'] == '1.0'
    
    def test_environment_variable_configuration(self, ci_environment):
        """Test configuration from environment variables only."""
        from ic.config.manager import ConfigManager
        from ic.config.security import SecurityManager
        
        # Set up environment variables
        env_vars = {
            'IC_LOG_LEVEL': 'DEBUG',
            'AWS_REGION': 'us-west-2',
            'AWS_ACCOUNTS': '111111111111,222222222222',
            'AWS_MAX_WORKERS': '20',
            'AZURE_SUBSCRIPTIONS': 'sub1,sub2',
            'GCP_PROJECTS': 'project1,project2'
        }
        
        with patch.dict(os.environ, env_vars):
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager=security_manager)
            
            config = config_manager.load_config([])
            
            # Verify environment variables were loaded
            assert config['logging']['console_level'] == 'DEBUG'
            assert config['aws']['default_region'] == 'us-west-2'
            assert config['aws']['accounts'] == ['111111111111', '222222222222']
            assert config['aws']['max_workers'] == 20
            assert config['azure']['subscriptions'] == ['sub1', 'sub2']
            assert config['gcp']['projects'] == ['project1', 'project2']
    
    def test_config_validation_without_files(self, ci_environment):
        """Test configuration validation works without files."""
        from ic.config.manager import ConfigManager
        
        config_manager = ConfigManager()
        
        # Test valid configuration
        valid_config = {
            'version': '1.0',
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'file_path': 'logs/ic.log'
            },
            'aws': {'regions': ['us-east-1']},
            'azure': {'locations': ['East US']},
            'gcp': {'regions': ['us-central1']},
            'security': {'mask_pattern': '***MASKED***'}
        }
        
        errors = config_manager.validate_config(valid_config)
        assert len(errors) == 0
        
        # Test invalid configuration
        invalid_config = {'version': '1.0'}  # Missing required sections
        errors = config_manager.validate_config(invalid_config)
        assert len(errors) > 0
    
    def test_security_manager_without_config(self, ci_environment):
        """Test SecurityManager works without configuration files."""
        from ic.config.security import SecurityManager
        
        security_manager = SecurityManager()
        
        # Test sensitive data detection
        test_config = {
            'aws': {
                'secret_access_key': 'AKIAIOSFODNN7EXAMPLE',
                'accounts': ['123456789012']
            },
            'database': {
                'password': 'secret123',
                'host': 'localhost'
            }
        }
        
        warnings = security_manager.validate_config_security(test_config)
        
        # Should detect sensitive data
        assert len(warnings) > 0
        assert any('secret' in warning.lower() for warning in warnings)
    
    def test_logger_initialization_without_config(self, ci_environment):
        """Test logger can be initialized without config files."""
        from ic.core.logging import ICLogger
        import tempfile
        import os
        
        # Create minimal config for logger with temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            log_config = {
                'logging': {
                    'console_level': 'ERROR',
                    'file_level': 'INFO',
                    'file_path': os.path.join(temp_dir, 'test.log'),
                    'max_files': 5,
                    'mask_sensitive': True
                },
                'security': {
                    'sensitive_keys': ['password', 'token'],
                    'mask_pattern': '***MASKED***'
                }
            }
            
            logger = ICLogger(log_config)
            assert logger is not None
            
            # Test logging functionality
            logger.log_info_file_only("Test message")
            logger.log_error("Test error")
            
            # Verify log file was created
            log_file = os.path.join(temp_dir, 'test.log')
            assert os.path.exists(log_file)
            
            # Verify log content
            with open(log_file, 'r') as f:
                content = f.read()
            
            assert "Test message" in content
            assert "Test error" in content


class TestCLIParsingWithoutConfig:
    """Test CLI parsing functionality without configuration files."""
    
    def test_basic_cli_parsing(self, ci_environment):
        """Test basic CLI argument parsing."""
        import argparse
        
        # Test that we can create a basic parser like the CLI does
        parser = argparse.ArgumentParser(description="Test CLI")
        subparsers = parser.add_subparsers(dest="platform", required=True)
        
        # Add config subcommand
        config_parser = subparsers.add_parser("config", help="Config commands")
        config_subparsers = config_parser.add_subparsers(dest="command", required=True)
        show_parser = config_subparsers.add_parser("show", help="Show config")
        show_parser.add_argument('--aws', action='store_true', help="Show AWS config")
        
        assert parser is not None
        
        # Test config commands
        args = parser.parse_args(['config', 'show'])
        assert args.command == 'show'
        
        args = parser.parse_args(['config', 'show', '--aws'])
        assert args.command == 'show'
        assert args.aws is True
    
    def test_aws_command_parsing(self, ci_environment):
        """Test AWS command parsing."""
        import argparse
        
        # Test that we can create a basic parser like the CLI does
        parser = argparse.ArgumentParser(description="Test CLI")
        subparsers = parser.add_subparsers(dest="platform", required=True)
        
        # Add AWS subcommand
        aws_parser = subparsers.add_parser("aws", help="AWS commands")
        aws_subparsers = aws_parser.add_subparsers(dest="service", required=True)
        
        # Add profile subcommand
        profile_parser = aws_subparsers.add_parser("profile", help="Profile commands")
        profile_subparsers = profile_parser.add_subparsers(dest="command", required=True)
        info_parser = profile_subparsers.add_parser("info", help="Profile info")
        
        # Add EC2 subcommand
        ec2_parser = aws_subparsers.add_parser("ec2", help="EC2 commands")
        ec2_subparsers = ec2_parser.add_subparsers(dest="command", required=True)
        ec2_info_parser = ec2_subparsers.add_parser("info", help="EC2 info")
        ec2_info_parser.add_argument('--profile', help="AWS profile")
        ec2_info_parser.add_argument('--regions', nargs='+', help="AWS regions")
        
        # Test AWS profile command
        args = parser.parse_args(['aws', 'profile', 'info'])
        assert args.platform == 'aws'
        assert args.service == 'profile'
        assert args.command == 'info'
        
        # Test AWS EC2 command with options
        args = parser.parse_args(['aws', 'ec2', 'info', '--profile', 'test', '--regions', 'us-east-1', 'us-west-2'])
        assert args.platform == 'aws'
        assert args.service == 'ec2'
        assert args.command == 'info'
        assert args.profile == 'test'
        assert args.regions == ['us-east-1', 'us-west-2']
    
    def test_oci_command_parsing(self, ci_environment):
        """Test OCI command parsing."""
        import argparse
        
        # Test that we can create a basic parser like the CLI does
        parser = argparse.ArgumentParser(description="Test CLI")
        subparsers = parser.add_subparsers(dest="platform", required=True)
        
        # Add OCI subcommand
        oci_parser = subparsers.add_parser("oci", help="OCI commands")
        oci_subparsers = oci_parser.add_subparsers(dest="service", required=True)
        
        # Add compartment subcommand
        compartment_parser = oci_subparsers.add_parser("compartment", help="Compartment commands")
        compartment_subparsers = compartment_parser.add_subparsers(dest="command", required=True)
        tree_parser = compartment_subparsers.add_parser("tree", help="Compartment tree")
        
        # Add VM subcommand
        vm_parser = oci_subparsers.add_parser("vm", help="VM commands")
        vm_subparsers = vm_parser.add_subparsers(dest="command", required=True)
        vm_info_parser = vm_subparsers.add_parser("info", help="VM info")
        vm_info_parser.add_argument('--profile', help="OCI profile")
        
        # Test OCI compartment command
        args = parser.parse_args(['oci', 'compartment', 'tree'])
        assert args.platform == 'oci'
        assert args.service == 'compartment'
        assert args.command == 'tree'
        
        # Test with profile option
        args = parser.parse_args(['oci', 'vm', 'info', '--profile', 'CUSTOM'])
        assert args.platform == 'oci'
        assert args.service == 'vm'
        assert args.command == 'info'
        assert args.profile == 'CUSTOM'
    
    def test_ssh_command_parsing(self, ci_environment):
        """Test SSH command parsing."""
        import argparse
        
        # Test that we can create a basic parser like the CLI does
        parser = argparse.ArgumentParser(description="Test CLI")
        subparsers = parser.add_subparsers(dest="platform", required=True)
        
        # Add SSH subcommand
        ssh_parser = subparsers.add_parser("ssh", help="SSH commands")
        ssh_subparsers = ssh_parser.add_subparsers(dest="command", required=True)
        info_parser = ssh_subparsers.add_parser("info", help="SSH info")
        
        # Test SSH info command
        args = parser.parse_args(['ssh', 'info'])
        assert args.platform == 'ssh'
        assert args.command == 'info'
    
    def test_cloudflare_command_parsing(self, ci_environment):
        """Test CloudFlare command parsing."""
        import argparse
        
        # Test that we can create a basic parser like the CLI does
        parser = argparse.ArgumentParser(description="Test CLI")
        subparsers = parser.add_subparsers(dest="platform", required=True)
        
        # Add CloudFlare subcommand
        cf_parser = subparsers.add_parser("cf", help="CloudFlare commands")
        cf_subparsers = cf_parser.add_subparsers(dest="service", required=True)
        
        # Add DNS subcommand
        dns_parser = cf_subparsers.add_parser("dns", help="DNS commands")
        dns_subparsers = dns_parser.add_subparsers(dest="command", required=True)
        list_parser = dns_subparsers.add_parser("list", help="List DNS records")
        
        # Test CloudFlare DNS command
        args = parser.parse_args(['cf', 'dns', 'list'])
        assert args.platform == 'cf'
        assert args.service == 'dns'
        assert args.command == 'list'


class TestMockCloudOperations:
    """Test cloud operations with mock data (no real credentials needed)."""
    
    def test_mock_aws_session_creation(self, ci_environment, mock_aws_session):
        """Test AWS operations with mock session."""
        # Test that we can create mock AWS operations
        assert mock_aws_session is not None
        
        # Test mock EC2 client
        ec2_client = mock_aws_session.client('ec2')
        response = ec2_client.describe_instances()
        
        assert 'Reservations' in response
        assert len(response['Reservations']) > 0
    
    def test_mock_oci_operations(self, ci_environment, mock_oci_config):
        """Test OCI operations with mock configuration."""
        assert mock_oci_config is not None
        assert 'tenancy' in mock_oci_config
        assert 'region' in mock_oci_config
    
    def test_mock_cloudflare_operations(self, ci_environment, mock_cloudflare_api):
        """Test CloudFlare operations with mock API."""
        assert mock_cloudflare_api is not None
        
        response_data = mock_cloudflare_api.json()
        assert response_data['success'] is True
        assert 'result' in response_data
    
    def test_mock_ssh_operations(self, ci_environment, mock_ssh_client):
        """Test SSH operations with mock client."""
        assert mock_ssh_client is not None
        
        # Test mock command execution
        stdin, stdout, stderr = mock_ssh_client.exec_command('uname -a')
        output = stdout.read()
        
        assert b'Linux' in output


class TestProgressDecoratorInCI:
    """Test progress decorator functionality in CI environment."""
    
    def test_progress_decorator_without_rich(self, ci_environment, no_rich_environment):
        """Test progress decorator fallback when Rich is not available."""
        from common.progress_decorator import progress_bar
        
        @progress_bar("CI test operation")
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_progress_decorator_with_rich(self, ci_environment):
        """Test progress decorator with Rich available."""
        from common.progress_decorator import progress_bar, spinner
        
        @progress_bar("CI progress test")
        def progress_function():
            import time
            time.sleep(0.01)  # Minimal delay
            return "progress_success"
        
        @spinner("CI spinner test")
        def spinner_function():
            import time
            time.sleep(0.01)  # Minimal delay
            return "spinner_success"
        
        progress_result = progress_function()
        spinner_result = spinner_function()
        
        assert progress_result == "progress_success"
        assert spinner_result == "spinner_success"
    
    def test_manual_progress_in_ci(self, ci_environment):
        """Test manual progress management in CI."""
        from common.progress_decorator import ManualProgress
        
        with ManualProgress("CI manual progress", total=3) as progress:
            for i in range(3):
                progress.update(f"Step {i+1}")
                progress.advance(1)
        
        # Should complete without errors


class TestDependencyHandling:
    """Test handling of optional and required dependencies."""
    
    def test_required_dependencies_available(self, ci_environment):
        """Test that all required dependencies are available."""
        required_modules = [
            'yaml',
            'pathlib', 
            'logging',
            'threading',
            'concurrent.futures',
            'dataclasses',
            'functools',
            'inspect',
            'tempfile',
            'unittest.mock'
        ]
        
        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Required module {module_name} not available: {e}")
    
    def test_optional_dependencies_handling(self, ci_environment):
        """Test graceful handling of optional dependencies."""
        # Test Rich dependency
        try:
            import rich
            rich_available = True
        except ImportError:
            rich_available = False
        
        # Progress decorator should work regardless
        from common.progress_decorator import ProgressBarDecorator
        
        decorator = ProgressBarDecorator()
        assert decorator is not None
        
        # Test boto3 dependency handling
        try:
            import boto3
            boto3_available = True
        except ImportError:
            boto3_available = False
        
        # Should not fail if boto3 is missing (will be mocked in tests)
        
        # Test paramiko dependency handling
        try:
            import paramiko
            paramiko_available = True
        except ImportError:
            paramiko_available = False
        
        # Should not fail if paramiko is missing (will be mocked in tests)
    
    def test_python_version_compatibility(self, ci_environment):
        """Test Python version compatibility."""
        import sys
        
        python_version = sys.version_info
        
        # Should support Python 3.9+
        assert python_version >= (3, 9), f"Python {python_version} not supported"
        
        # Test dataclasses (Python 3.7+)
        from dataclasses import dataclass
        
        @dataclass
        class TestClass:
            value: str = "test"
        
        test_obj = TestClass()
        assert test_obj.value == "test"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])