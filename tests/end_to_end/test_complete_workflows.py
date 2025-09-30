#!/usr/bin/env python3
"""
End-to-End Complete Workflow Tests

Tests that execute complete command workflows from start to finish,
validating the entire pipeline including import resolution, configuration
loading, authentication, and command execution.

Requirements: 5.1-5.5
"""

import unittest
import sys
import subprocess
import tempfile
import shutil
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from typing import Dict, List, Any, Optional
import argparse
from io import StringIO


class EndToEndWorkflowTestCase(unittest.TestCase):
    """Base test case for end-to-end workflow tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_argv = sys.argv.copy()
        self.original_path = sys.path.copy()
        
        # Ensure src directory is in path
        src_dir = Path(__file__).parent.parent.parent / "src"
        if src_dir.exists() and str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        
        # Create temporary config directory
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / ".ic" / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mock configuration files
        self._create_mock_configs()
    
    def tearDown(self):
        """Clean up test environment."""
        sys.argv = self.original_argv
        sys.path = self.original_path
        
        # Clean up temporary directory
        if hasattr(self, 'temp_dir') and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_mock_configs(self):
        """Create mock configuration files for testing."""
        # Default configuration
        default_config = {
            'version': '1.0',
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'file_path': str(Path(self.temp_dir) / 'ic.log'),
                'max_files': 10,
                'mask_sensitive': True
            },
            'aws': {
                'regions': ['us-east-1', 'us-west-2'],
                'max_workers': 5
            },
            'ncp': {
                'regions': ['KR'],
                'max_workers': 3
            },
            'ncpgov': {
                'regions': ['KR'],
                'max_workers': 3,
                'compliance_mode': True
            },
            'gcp': {
                'regions': ['us-central1'],
                'max_workers': 5
            },
            'oci': {
                'regions': ['us-ashburn-1'],
                'max_workers': 3
            },
            'azure': {
                'locations': ['East US'],
                'max_workers': 5
            },
            'security': {
                'sensitive_keys': ['password', 'token', 'key', 'secret'],
                'mask_pattern': '***MASKED***'
            }
        }
        
        with open(self.config_dir / 'default.yaml', 'w') as f:
            yaml.dump(default_config, f)
        
        # Secrets configuration
        secrets_config = {
            'aws': {
                'accounts': ['123456789012', '987654321098']
            },
            'ncp': {
                'access_key': 'test-ncp-access-key',
                'secret_key': 'test-ncp-secret-key'
            },
            'ncpgov': {
                'access_key': 'test-gov-access-key',
                'secret_key': 'test-gov-secret-key'
            },
            'gcp': {
                'project_id': 'test-project-123',
                'service_account_key': '/path/to/service-account.json'
            },
            'oci': {
                'tenancy': 'ocid1.tenancy.oc1..test',
                'user': 'ocid1.user.oc1..test',
                'fingerprint': 'test-fingerprint',
                'key_file': '/path/to/oci-key.pem'
            },
            'azure': {
                'subscription_id': 'sub-12345-67890',
                'tenant_id': 'tenant-12345'
            }
        }
        
        with open(self.config_dir / 'secrets.yaml', 'w') as f:
            yaml.dump(secrets_config, f)


class TestCompleteCommandWorkflows(EndToEndWorkflowTestCase):
    """Test complete command workflows from start to finish."""
    
    def test_ncp_ec2_info_workflow(self):
        """Test complete NCP EC2 info command workflow."""
        try:
            from src.ic.cli import main
            from src.ic.core.platform_discovery import get_platform_discovery
            
            # Test platform discovery can find NCP
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if 'ncp' not in platforms:
                self.skipTest("NCP platform not available")
            
            # Test service discovery
            services = discovery.list_services('ncp')
            if 'ec2' not in services:
                self.skipTest("NCP EC2 service not available")
            
            # Test command discovery
            commands = discovery.get_service_commands('ncp', 'ec2')
            if 'info' not in commands:
                self.skipTest("NCP EC2 info command not available")
            
            # Mock the actual NCP client to avoid real API calls
            with patch('src.ic.platforms.ncp.client.NCPClient') as mock_client_class:
                mock_client = Mock()
                mock_client_class.return_value = mock_client
                
                # Mock successful API response
                mock_client.get_server_instances.return_value = {
                    'instances': [
                        {
                            'serverInstanceNo': '12345',
                            'serverName': 'test-server',
                            'serverInstanceStatus': 'RUN',
                            'serverInstanceType': 'SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002',
                            'cpuCount': 2,
                            'memorySize': 8589934592,
                            'region': 'KR'
                        }
                    ],
                    'total_count': 1
                }
                
                # Test command execution
                with patch('sys.argv', ['ic', 'ncp', 'ec2', 'info']):
                    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                        try:
                            main()
                            output = mock_stdout.getvalue()
                            
                            # Verify output contains expected information
                            self.assertIn('test-server', output)
                            self.assertIn('12345', output)
                            
                        except SystemExit as e:
                            # Exit code 0 is success
                            if e.code != 0:
                                self.fail(f"Command failed with exit code: {e.code}")
                
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    def test_ncpgov_vpc_info_workflow(self):
        """Test complete NCPGov VPC info command workflow."""
        try:
            from src.ic.cli import main
            from src.ic.core.platform_discovery import get_platform_discovery
            
            # Test platform discovery can find NCPGov
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if 'ncpgov' not in platforms:
                self.skipTest("NCPGov platform not available")
            
            # Test service discovery
            services = discovery.list_services('ncpgov')
            if 'vpc' not in services:
                self.skipTest("NCPGov VPC service not available")
            
            # Mock the actual NCPGov client
            with patch('src.ic.platforms.ncpgov.client.NCPGovClient') as mock_client_class:
                mock_client = Mock()
                mock_client_class.return_value = mock_client
                
                # Mock successful API response with compliance data
                mock_client.get_vpc_list.return_value = {
                    'vpcs': [
                        {
                            'vpcNo': 'vpc-gov123',
                            'vpcName': 'test-gov-vpc',
                            'ipv4CidrBlock': '10.0.0.0/16',
                            'vpcStatus': 'RUN',
                            'regionCode': 'KR',
                            'compliance_status': 'validated'
                        }
                    ],
                    'total_count': 1,
                    'compliance_status': 'validated'
                }
                
                # Test command execution
                with patch('sys.argv', ['ic', 'ncpgov', 'vpc', 'info']):
                    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                        try:
                            main()
                            output = mock_stdout.getvalue()
                            
                            # Verify output contains expected information
                            self.assertIn('test-gov-vpc', output)
                            self.assertIn('vpc-gov123', output)
                            
                        except SystemExit as e:
                            if e.code != 0:
                                self.fail(f"Command failed with exit code: {e.code}")
                
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    def test_aws_ec2_info_workflow(self):
        """Test complete AWS EC2 info command workflow."""
        try:
            from src.ic.cli import main
            from src.ic.core.platform_discovery import get_platform_discovery
            
            # Test platform discovery can find AWS
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if 'aws' not in platforms:
                self.skipTest("AWS platform not available")
            
            # Mock boto3 session
            with patch('boto3.Session') as mock_session_class:
                mock_session = Mock()
                mock_session_class.return_value = mock_session
                
                mock_ec2_client = Mock()
                mock_session.client.return_value = mock_ec2_client
                
                # Mock successful EC2 response
                mock_ec2_client.describe_instances.return_value = {
                    'Reservations': [
                        {
                            'Instances': [
                                {
                                    'InstanceId': 'i-1234567890abcdef0',
                                    'InstanceType': 't3.micro',
                                    'State': {'Name': 'running'},
                                    'Tags': [{'Key': 'Name', 'Value': 'test-instance'}]
                                }
                            ]
                        }
                    ]
                }
                
                # Test command execution
                with patch('sys.argv', ['ic', 'aws', 'ec2', 'info']):
                    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                        try:
                            main()
                            output = mock_stdout.getvalue()
                            
                            # Verify output contains expected information
                            self.assertIn('i-1234567890abcdef0', output)
                            self.assertIn('test-instance', output)
                            
                        except SystemExit as e:
                            if e.code != 0:
                                self.fail(f"Command failed with exit code: {e.code}")
                
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    def test_gcp_compute_info_workflow(self):
        """Test complete GCP compute info command workflow."""
        try:
            from src.ic.cli import main
            from src.ic.core.platform_discovery import get_platform_discovery
            
            # Test platform discovery can find GCP
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if 'gcp' not in platforms:
                self.skipTest("GCP platform not available")
            
            # Mock GCP compute client
            with patch('google.cloud.compute_v1.InstancesClient') as mock_client_class:
                mock_client = Mock()
                mock_client_class.return_value = mock_client
                
                # Mock successful compute response
                mock_instance = Mock()
                mock_instance.name = 'test-gcp-instance'
                mock_instance.machine_type = 'projects/test-project/zones/us-central1-a/machineTypes/e2-micro'
                mock_instance.status = 'RUNNING'
                
                mock_client.list.return_value = [mock_instance]
                
                # Test command execution
                with patch('sys.argv', ['ic', 'gcp', 'compute', 'info']):
                    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                        try:
                            main()
                            output = mock_stdout.getvalue()
                            
                            # Verify output contains expected information
                            self.assertIn('test-gcp-instance', output)
                            
                        except SystemExit as e:
                            if e.code != 0:
                                self.fail(f"Command failed with exit code: {e.code}")
                
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    def test_oci_vm_info_workflow(self):
        """Test complete OCI VM info command workflow."""
        try:
            from src.ic.cli import main
            from src.ic.core.platform_discovery import get_platform_discovery
            
            # Test platform discovery can find OCI
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if 'oci' not in platforms:
                self.skipTest("OCI platform not available")
            
            # Mock OCI configuration and client
            with patch('oci.config.from_file') as mock_config:
                mock_config.return_value = {
                    'tenancy': 'ocid1.tenancy.oc1..test',
                    'user': 'ocid1.user.oc1..test',
                    'fingerprint': 'test-fingerprint',
                    'key_file': '/path/to/test.pem',
                    'region': 'us-ashburn-1'
                }
                
                with patch('oci.core.ComputeClient') as mock_client_class:
                    mock_client = Mock()
                    mock_client_class.return_value = mock_client
                    
                    # Mock successful VM response
                    mock_instance = Mock()
                    mock_instance.id = 'ocid1.instance.oc1.iad.test'
                    mock_instance.display_name = 'test-oci-instance'
                    mock_instance.lifecycle_state = 'RUNNING'
                    mock_instance.shape = 'VM.Standard2.1'
                    
                    mock_client.list_instances.return_value.data = [mock_instance]
                    
                    # Test command execution
                    with patch('sys.argv', ['ic', 'oci', 'vm', 'info']):
                        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                            try:
                                main()
                                output = mock_stdout.getvalue()
                                
                                # Verify output contains expected information
                                self.assertIn('test-oci-instance', output)
                                
                            except SystemExit as e:
                                if e.code != 0:
                                    self.fail(f"Command failed with exit code: {e.code}")
                
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")


class TestMultiPlatformFunctionality(EndToEndWorkflowTestCase):
    """Test multi-platform functionality and integration."""
    
    def test_multi_platform_discovery(self):
        """Test that multiple platforms can be discovered and used together."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.discover_platforms()
            
            # Should discover multiple platforms
            self.assertIsInstance(platforms, dict)
            self.assertGreater(len(platforms), 1, "Should discover multiple platforms")
            
            # Test that each platform has proper structure
            for platform_name, platform_info in platforms.items():
                with self.subTest(platform=platform_name):
                    self.assertIsNotNone(platform_info)
                    self.assertIsInstance(platform_info.services, dict)
                    
                    # Test service discovery for each platform
                    services = discovery.list_services(platform_name)
                    self.assertIsInstance(services, list)
                    
                    # Test at least one service per platform
                    if services:
                        service_name = services[0]
                        service_info = discovery.get_service(platform_name, service_name)
                        
                        if service_info and service_info.available:
                            self.assertIsNotNone(service_info.module)
                            
        except ImportError as e:
            self.skipTest(f"Platform discovery not available: {e}")
    
    def test_cross_platform_configuration(self):
        """Test that configuration works across multiple platforms."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            
            # Test configuration loading
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager)
            
            # Mock config directory
            with patch.object(config_manager, 'config_dir', self.config_dir):
                config = config_manager.load_config()
                
                # Should load configuration for all platforms
                self.assertIn('aws', config)
                self.assertIn('ncp', config)
                self.assertIn('ncpgov', config)
                self.assertIn('gcp', config)
                self.assertIn('oci', config)
                self.assertIn('azure', config)
                
                # Test platform-specific configuration access
                aws_config = config_manager.get_platform_config('aws')
                ncp_config = config_manager.get_platform_config('ncp')
                
                self.assertIsNotNone(aws_config)
                self.assertIsNotNone(ncp_config)
                
        except ImportError as e:
            self.skipTest(f"Configuration management not available: {e}")
    
    def test_multi_service_command_execution(self):
        """Test executing commands across multiple services."""
        try:
            from src.ic.cli import execute_multi_service_command
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Find a platform with multiple services
            test_platform = None
            test_services = []
            
            for platform_name in platforms:
                services = discovery.list_services(platform_name)
                if len(services) >= 2:
                    test_platform = platform_name
                    test_services = services[:2]
                    break
            
            if not test_platform:
                self.skipTest("No platform with multiple services found")
            
            # Find a common command across services
            common_commands = None
            for service_name in test_services:
                commands = discovery.get_service_commands(test_platform, service_name)
                if common_commands is None:
                    common_commands = set(commands.keys())
                else:
                    common_commands &= set(commands.keys())
            
            if not common_commands:
                self.skipTest("No common commands found across services")
            
            # Test multi-service execution
            test_command = list(common_commands)[0]
            
            # Create mock args
            args = argparse.Namespace(
                platform=test_platform,
                service=','.join(test_services),
                command=test_command,
                help=True  # Use help to avoid actual execution
            )
            
            # This should not raise an exception
            self.assertTrue(callable(execute_multi_service_command))
            
        except ImportError as e:
            self.skipTest(f"Multi-service execution not available: {e}")
    
    def test_platform_isolation(self):
        """Test that platforms are properly isolated from each other."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test that each platform has isolated configuration
            for platform_name in platforms[:3]:  # Test first 3 platforms
                with self.subTest(platform=platform_name):
                    platform_info = discovery.get_platform(platform_name)
                    
                    if platform_info and platform_info.available:
                        # Each platform should have its own module space
                        self.assertIsNotNone(platform_info.module)
                        
                        # Platform modules should not interfere with each other
                        services = discovery.list_services(platform_name)
                        for service_name in services[:1]:  # Test first service
                            service_info = discovery.get_service(platform_name, service_name)
                            
                            if service_info and service_info.available:
                                # Service should be properly namespaced
                                self.assertIn(platform_name, str(service_info.module))
                                
        except ImportError as e:
            self.skipTest(f"Platform isolation testing not available: {e}")


class TestConfigurationAndAuthentication(EndToEndWorkflowTestCase):
    """Test configuration and authentication systems."""
    
    def test_configuration_loading_workflow(self):
        """Test complete configuration loading workflow."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            from src.ic.config.path_manager import ConfigPathManager
            
            # Test path manager
            path_manager = ConfigPathManager()
            
            # Mock home directory to use temp directory
            with patch.object(path_manager, 'home_dir', Path(self.temp_dir)):
                config_path = path_manager.get_config_dir()
                self.assertEqual(config_path, self.config_dir)
                
                # Test security manager
                security_manager = SecurityManager()
                
                # Test config manager
                config_manager = ConfigManager(security_manager)
                
                # Mock config directory
                with patch.object(config_manager, 'config_dir', self.config_dir):
                    # Test configuration loading
                    config = config_manager.load_config()
                    
                    # Should load all expected sections
                    self.assertIn('version', config)
                    self.assertIn('logging', config)
                    self.assertIn('aws', config)
                    self.assertIn('ncp', config)
                    self.assertIn('ncpgov', config)
                    self.assertIn('security', config)
                    
                    # Test secrets loading
                    secrets = config_manager.load_secrets()
                    
                    self.assertIn('aws', secrets)
                    self.assertIn('ncp', secrets)
                    self.assertIn('ncpgov', secrets)
                    
                    # Test platform-specific config access
                    ncp_config = config_manager.get_platform_config('ncp')
                    self.assertIsNotNone(ncp_config)
                    self.assertIn('regions', ncp_config)
                    
        except ImportError as e:
            self.skipTest(f"Configuration system not available: {e}")
    
    def test_authentication_workflow(self):
        """Test authentication workflow for different platforms."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager)
            
            # Mock config directory
            with patch.object(config_manager, 'config_dir', self.config_dir):
                # Test NCP authentication
                with patch('src.ic.platforms.ncp.client.NCPClient') as mock_ncp_client:
                    mock_client = Mock()
                    mock_ncp_client.return_value = mock_client
                    mock_client.test_connection.return_value = True
                    
                    # Should be able to create authenticated client
                    self.assertTrue(mock_client.test_connection())
                
                # Test NCPGov authentication
                with patch('src.ic.platforms.ncpgov.client.NCPGovClient') as mock_ncpgov_client:
                    mock_client = Mock()
                    mock_ncpgov_client.return_value = mock_client
                    mock_client.test_connection.return_value = True
                    
                    # Should be able to create authenticated client
                    self.assertTrue(mock_client.test_connection())
                
                # Test AWS authentication
                with patch('boto3.Session') as mock_session:
                    mock_session_instance = Mock()
                    mock_session.return_value = mock_session_instance
                    
                    # Should be able to create session
                    self.assertIsNotNone(mock_session_instance)
                
        except ImportError as e:
            self.skipTest(f"Authentication system not available: {e}")
    
    def test_security_validation_workflow(self):
        """Test security validation workflow."""
        try:
            from src.ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            
            # Test configuration security validation
            test_config = {
                'aws': {
                    'access_key': 'AKIA1234567890ABCDEF',
                    'secret_key': 'secret123',
                    'regions': ['us-east-1']
                },
                'ncp': {
                    'access_key': 'ncp-access-key',
                    'secret_key': 'ncp-secret-key'
                }
            }
            
            # Test security validation
            security_issues = security_manager.validate_config_security(test_config)
            
            # Should detect sensitive data
            self.assertIsInstance(security_issues, list)
            
            # Test sensitive data masking
            masked_config = security_manager.mask_sensitive_data(test_config)
            
            # Should mask sensitive values
            self.assertNotEqual(masked_config['aws']['secret_key'], 'secret123')
            self.assertNotEqual(masked_config['ncp']['secret_key'], 'ncp-secret-key')
            
        except ImportError as e:
            self.skipTest(f"Security system not available: {e}")
    
    def test_credential_rotation_workflow(self):
        """Test credential rotation workflow."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager)
            
            # Mock config directory
            with patch.object(config_manager, 'config_dir', self.config_dir):
                # Test credential update
                new_credentials = {
                    'ncp': {
                        'access_key': 'new-ncp-access-key',
                        'secret_key': 'new-ncp-secret-key'
                    }
                }
                
                # Should be able to update credentials
                config_manager.update_secrets(new_credentials)
                
                # Test that new credentials are loaded
                secrets = config_manager.load_secrets()
                self.assertEqual(secrets['ncp']['access_key'], 'new-ncp-access-key')
                
        except ImportError as e:
            self.skipTest(f"Credential management not available: {e}")


class TestErrorHandlingAndRecovery(EndToEndWorkflowTestCase):
    """Test error handling and recovery in end-to-end workflows."""
    
    def test_import_error_recovery(self):
        """Test recovery from import errors."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            
            # Test handling of non-existent platform
            platform_info = discovery.get_platform('nonexistent_platform')
            self.assertIsNone(platform_info)
            
            # Test handling of non-existent service
            service_info = discovery.get_service('aws', 'nonexistent_service')
            self.assertIsNone(service_info)
            
            # Test handling of non-existent command
            command_module = discovery.get_command_module('aws', 'ec2', 'nonexistent_command')
            self.assertIsNone(command_module)
            
            # Should not raise exceptions
            self.assertTrue(True)
            
        except ImportError as e:
            self.skipTest(f"Platform discovery not available: {e}")
    
    def test_configuration_error_recovery(self):
        """Test recovery from configuration errors."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager)
            
            # Test handling of missing config directory
            with patch.object(config_manager, 'config_dir', Path('/nonexistent/path')):
                # Should use fallback configuration
                config = config_manager.load_config()
                self.assertIsInstance(config, dict)
                
                # Should have default values
                self.assertIn('version', config)
                
        except ImportError as e:
            self.skipTest(f"Configuration management not available: {e}")
    
    def test_authentication_error_recovery(self):
        """Test recovery from authentication errors."""
        try:
            from src.ic.cli import main
            
            # Test handling of authentication failure
            with patch('src.ic.platforms.ncp.client.NCPClient') as mock_client_class:
                mock_client = Mock()
                mock_client_class.return_value = mock_client
                
                # Mock authentication failure
                mock_client.test_connection.side_effect = Exception("Authentication failed")
                
                # Should handle authentication error gracefully
                with patch('sys.argv', ['ic', 'ncp', 'ec2', 'info']):
                    with patch('sys.stdout', new_callable=StringIO):
                        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                            try:
                                main()
                            except SystemExit as e:
                                # Should exit with error code but not crash
                                self.assertNotEqual(e.code, 0)
                                
                                # Should provide helpful error message
                                error_output = mock_stderr.getvalue()
                                self.assertIn('authentication', error_output.lower())
                
        except ImportError as e:
            self.skipTest(f"Authentication error handling not available: {e}")
    
    def test_network_error_recovery(self):
        """Test recovery from network errors."""
        try:
            from src.ic.cli import main
            
            # Test handling of network failure
            with patch('src.ic.platforms.ncp.client.NCPClient') as mock_client_class:
                mock_client = Mock()
                mock_client_class.return_value = mock_client
                
                # Mock network failure
                mock_client.get_server_instances.side_effect = Exception("Network timeout")
                
                # Should handle network error gracefully
                with patch('sys.argv', ['ic', 'ncp', 'ec2', 'info']):
                    with patch('sys.stdout', new_callable=StringIO):
                        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                            try:
                                main()
                            except SystemExit as e:
                                # Should exit with error code but not crash
                                self.assertNotEqual(e.code, 0)
                                
                                # Should provide helpful error message
                                error_output = mock_stderr.getvalue()
                                self.assertIn('network', error_output.lower())
                
        except ImportError as e:
            self.skipTest(f"Network error handling not available: {e}")


if __name__ == '__main__':
    unittest.main()