#!/usr/bin/env python3
"""
Multi-Platform Integration Tests

Tests that validate multi-platform functionality, cross-platform operations,
and integration between different cloud platforms and services.

Requirements: 5.1-5.5
"""

import unittest
import sys
import tempfile
import shutil
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from typing import Dict, List, Any, Optional
import argparse
from io import StringIO
import concurrent.futures
import threading
import time


class MultiPlatformIntegrationTestCase(unittest.TestCase):
    """Base test case for multi-platform integration tests."""
    
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
        
        # Create comprehensive mock configuration
        self._create_comprehensive_configs()
    
    def tearDown(self):
        """Clean up test environment."""
        sys.argv = self.original_argv
        sys.path = self.original_path
        
        # Clean up temporary directory
        if hasattr(self, 'temp_dir') and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_comprehensive_configs(self):
        """Create comprehensive configuration files for all platforms."""
        # Default configuration with all platforms
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
                'regions': ['us-east-1', 'us-west-2', 'eu-west-1'],
                'max_workers': 5,
                'timeout': 30,
                'retry_attempts': 3
            },
            'ncp': {
                'regions': ['KR'],
                'max_workers': 3,
                'timeout': 30,
                'retry_attempts': 3,
                'api_version': 'v2'
            },
            'ncpgov': {
                'regions': ['KR'],
                'max_workers': 3,
                'timeout': 30,
                'retry_attempts': 3,
                'compliance_mode': True,
                'audit_logging': True,
                'api_version': 'v2'
            },
            'gcp': {
                'regions': ['us-central1', 'europe-west1'],
                'max_workers': 5,
                'timeout': 30,
                'retry_attempts': 3
            },
            'oci': {
                'regions': ['us-ashburn-1', 'uk-london-1'],
                'max_workers': 3,
                'timeout': 30,
                'retry_attempts': 3
            },
            'azure': {
                'locations': ['East US', 'West Europe'],
                'max_workers': 5,
                'timeout': 30,
                'retry_attempts': 3
            },
            'cloudflare': {
                'timeout': 30,
                'retry_attempts': 3,
                'max_workers': 3
            },
            'ssh': {
                'timeout': 30,
                'max_workers': 5,
                'key_types': ['rsa', 'ed25519']
            },
            'security': {
                'sensitive_keys': ['password', 'token', 'key', 'secret', 'credential'],
                'mask_pattern': '***MASKED***',
                'audit_commands': True,
                'require_mfa': False
            },
            'performance': {
                'concurrent_operations': True,
                'max_concurrent_platforms': 3,
                'operation_timeout': 300
            }
        }
        
        with open(self.config_dir / 'default.yaml', 'w') as f:
            yaml.dump(default_config, f)
        
        # Comprehensive secrets configuration
        secrets_config = {
            'aws': {
                'accounts': ['123456789012', '987654321098', '555666777888'],
                'profiles': ['default', 'production', 'development']
            },
            'ncp': {
                'access_key': 'test-ncp-access-key',
                'secret_key': 'test-ncp-secret-key',
                'environments': ['default', 'production']
            },
            'ncpgov': {
                'access_key': 'test-gov-access-key',
                'secret_key': 'test-gov-secret-key',
                'environments': ['default', 'production'],
                'compliance_token': 'test-compliance-token'
            },
            'gcp': {
                'project_id': 'test-project-123',
                'service_account_key': '/path/to/service-account.json',
                'projects': ['test-project-123', 'prod-project-456']
            },
            'oci': {
                'tenancy': 'ocid1.tenancy.oc1..test',
                'user': 'ocid1.user.oc1..test',
                'fingerprint': 'test-fingerprint',
                'key_file': '/path/to/oci-key.pem',
                'compartments': ['root', 'development', 'production']
            },
            'azure': {
                'subscription_id': 'sub-12345-67890',
                'tenant_id': 'tenant-12345',
                'client_id': 'client-12345',
                'client_secret': 'client-secret-12345'
            },
            'cloudflare': {
                'api_token': 'cf-api-token-12345',
                'email': 'test@example.com',
                'zones': ['example.com', 'test.com']
            },
            'ssh': {
                'default_key': '~/.ssh/id_rsa',
                'known_hosts': '~/.ssh/known_hosts',
                'servers': {
                    'web-server': {
                        'host': '192.168.1.100',
                        'user': 'admin',
                        'key': '~/.ssh/web-server-key'
                    },
                    'db-server': {
                        'host': '192.168.1.101',
                        'user': 'admin',
                        'key': '~/.ssh/db-server-key'
                    }
                }
            }
        }
        
        with open(self.config_dir / 'secrets.yaml', 'w') as f:
            yaml.dump(secrets_config, f)


class TestCrossPlatformOperations(MultiPlatformIntegrationTestCase):
    """Test operations that span multiple platforms."""
    
    def test_multi_platform_resource_discovery(self):
        """Test discovering resources across multiple platforms simultaneously."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Should discover multiple platforms
            self.assertGreaterEqual(len(platforms), 3, "Should discover at least 3 platforms")
            
            # Test concurrent platform operations
            results = {}
            
            def discover_platform_resources(platform_name):
                """Discover resources for a single platform."""
                try:
                    services = discovery.list_services(platform_name)
                    platform_info = discovery.get_platform(platform_name)
                    
                    return {
                        'platform': platform_name,
                        'services': services,
                        'available': platform_info.available if platform_info else False,
                        'service_count': len(services)
                    }
                except Exception as e:
                    return {
                        'platform': platform_name,
                        'error': str(e),
                        'available': False,
                        'service_count': 0
                    }
            
            # Test concurrent discovery
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_platform = {
                    executor.submit(discover_platform_resources, platform): platform
                    for platform in platforms[:5]  # Test first 5 platforms
                }
                
                for future in concurrent.futures.as_completed(future_to_platform):
                    platform = future_to_platform[future]
                    try:
                        result = future.result(timeout=30)
                        results[platform] = result
                    except Exception as e:
                        results[platform] = {
                            'platform': platform,
                            'error': str(e),
                            'available': False
                        }
            
            # Verify results
            self.assertGreater(len(results), 0, "Should have discovered some platforms")
            
            # At least some platforms should be available
            available_platforms = [r for r in results.values() if r.get('available', False)]
            self.assertGreater(len(available_platforms), 0, "At least one platform should be available")
            
        except ImportError as e:
            self.skipTest(f"Platform discovery not available: {e}")
    
    def test_cross_platform_configuration_consistency(self):
        """Test that configuration is consistent across platforms."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager)
            
            # Mock config directory
            with patch.object(config_manager, 'config_dir', self.config_dir):
                config = config_manager.load_config()
                
                # Test that all expected platforms have configuration
                expected_platforms = ['aws', 'ncp', 'ncpgov', 'gcp', 'oci', 'azure']
                
                for platform in expected_platforms:
                    with self.subTest(platform=platform):
                        self.assertIn(platform, config, f"{platform} should have configuration")
                        
                        platform_config = config[platform]
                        self.assertIsInstance(platform_config, dict)
                        
                        # Common configuration elements
                        if 'max_workers' in platform_config:
                            self.assertIsInstance(platform_config['max_workers'], int)
                            self.assertGreater(platform_config['max_workers'], 0)
                        
                        if 'timeout' in platform_config:
                            self.assertIsInstance(platform_config['timeout'], int)
                            self.assertGreater(platform_config['timeout'], 0)
                
                # Test secrets consistency
                secrets = config_manager.load_secrets()
                
                for platform in expected_platforms:
                    with self.subTest(platform=f"{platform}_secrets"):
                        if platform in secrets:
                            platform_secrets = secrets[platform]
                            self.assertIsInstance(platform_secrets, dict)
                            
                            # Should have some form of authentication
                            auth_keys = ['access_key', 'api_token', 'subscription_id', 'project_id']
                            has_auth = any(key in platform_secrets for key in auth_keys)
                            
                            if platform_secrets:  # Only check if secrets exist
                                self.assertTrue(has_auth, f"{platform} should have authentication configuration")
                
        except ImportError as e:
            self.skipTest(f"Configuration management not available: {e}")
    
    def test_multi_platform_command_execution(self):
        """Test executing commands across multiple platforms."""
        try:
            from src.ic.cli import main
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test commands across multiple platforms
            test_commands = [
                ('aws', 'ec2', 'info'),
                ('ncp', 'ec2', 'info'),
                ('ncpgov', 'ec2', 'info'),
                ('gcp', 'compute', 'info'),
                ('oci', 'vm', 'info')
            ]
            
            results = {}
            
            for platform, service, command in test_commands:
                if platform not in platforms:
                    continue
                
                services = discovery.list_services(platform)
                if service not in services:
                    continue
                
                with self.subTest(platform=platform, service=service, command=command):
                    # Mock platform-specific clients
                    client_patches = self._get_platform_client_patches(platform)
                    
                    with client_patches:
                        # Test command execution
                        with patch('sys.argv', ['ic', platform, service, command, '--help']):
                            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                                    try:
                                        main()
                                        
                                        output = mock_stdout.getvalue()
                                        error = mock_stderr.getvalue()
                                        
                                        results[f"{platform}_{service}_{command}"] = {
                                            'success': True,
                                            'output': output,
                                            'error': error
                                        }
                                        
                                        # Should produce help output
                                        self.assertTrue(
                                            'usage:' in output.lower() or 'usage:' in error.lower(),
                                            f"Command should produce usage information"
                                        )
                                        
                                    except SystemExit as e:
                                        # Help commands typically exit with code 0
                                        results[f"{platform}_{service}_{command}"] = {
                                            'success': e.code == 0,
                                            'exit_code': e.code,
                                            'output': mock_stdout.getvalue(),
                                            'error': mock_stderr.getvalue()
                                        }
                                        
                                        if e.code != 0:
                                            self.fail(f"Command failed with exit code: {e.code}")
            
            # Should have executed at least some commands
            self.assertGreater(len(results), 0, "Should have executed some commands")
            
            # Most commands should succeed
            successful_commands = [r for r in results.values() if r.get('success', False)]
            success_rate = len(successful_commands) / len(results) if results else 0
            self.assertGreaterEqual(success_rate, 0.5, "At least 50% of commands should succeed")
            
        except ImportError as e:
            self.skipTest(f"Multi-platform command execution not available: {e}")
    
    def _get_platform_client_patches(self, platform):
        """Get appropriate client patches for a platform."""
        if platform == 'aws':
            return patch('boto3.Session')
        elif platform == 'ncp':
            return patch('src.ic.platforms.ncp.client.NCPClient')
        elif platform == 'ncpgov':
            return patch('src.ic.platforms.ncpgov.client.NCPGovClient')
        elif platform == 'gcp':
            return patch('google.cloud.compute_v1.InstancesClient')
        elif platform == 'oci':
            return patch('oci.core.ComputeClient')
        elif platform == 'azure':
            return patch('azure.mgmt.compute.ComputeManagementClient')
        else:
            # Return a no-op context manager
            from contextlib import nullcontext
            return nullcontext()


class TestConcurrentPlatformOperations(MultiPlatformIntegrationTestCase):
    """Test concurrent operations across multiple platforms."""
    
    def test_concurrent_platform_discovery(self):
        """Test concurrent platform discovery operations."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            
            # Test concurrent platform discovery
            def discover_platform_info(platform_name):
                """Discover information for a single platform."""
                try:
                    platform_info = discovery.get_platform(platform_name)
                    services = discovery.list_services(platform_name)
                    
                    service_details = {}
                    for service_name in services[:2]:  # Test first 2 services
                        service_info = discovery.get_service(platform_name, service_name)
                        service_details[service_name] = {
                            'available': service_info.available if service_info else False,
                            'commands': list(discovery.get_service_commands(platform_name, service_name).keys())
                        }
                    
                    return {
                        'platform': platform_name,
                        'available': platform_info.available if platform_info else False,
                        'services': services,
                        'service_details': service_details,
                        'thread_id': threading.current_thread().ident
                    }
                except Exception as e:
                    return {
                        'platform': platform_name,
                        'error': str(e),
                        'thread_id': threading.current_thread().ident
                    }
            
            platforms = discovery.list_platforms()
            test_platforms = platforms[:4]  # Test first 4 platforms
            
            # Execute concurrent discovery
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(discover_platform_info, platform)
                    for platform in test_platforms
                ]
                
                results = []
                for future in concurrent.futures.as_completed(futures, timeout=60):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append({'error': str(e)})
            
            # Verify concurrent execution
            self.assertEqual(len(results), len(test_platforms), "Should have results for all platforms")
            
            # Verify different threads were used
            thread_ids = [r.get('thread_id') for r in results if 'thread_id' in r]
            unique_threads = set(thread_ids)
            self.assertGreater(len(unique_threads), 1, "Should use multiple threads")
            
            # Verify no data corruption from concurrent access
            for result in results:
                if 'platform' in result:
                    self.assertIn(result['platform'], test_platforms)
                    
                    if 'services' in result:
                        self.assertIsInstance(result['services'], list)
                        
                    if 'service_details' in result:
                        self.assertIsInstance(result['service_details'], dict)
            
        except ImportError as e:
            self.skipTest(f"Concurrent platform discovery not available: {e}")
    
    def test_concurrent_configuration_access(self):
        """Test concurrent access to configuration system."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager)
            
            # Mock config directory
            with patch.object(config_manager, 'config_dir', self.config_dir):
                
                def access_platform_config(platform_name):
                    """Access configuration for a specific platform."""
                    try:
                        config = config_manager.load_config()
                        platform_config = config_manager.get_platform_config(platform_name)
                        secrets = config_manager.load_secrets()
                        platform_secrets = secrets.get(platform_name, {})
                        
                        return {
                            'platform': platform_name,
                            'config_loaded': config is not None,
                            'platform_config_loaded': platform_config is not None,
                            'secrets_loaded': len(platform_secrets) > 0,
                            'thread_id': threading.current_thread().ident
                        }
                    except Exception as e:
                        return {
                            'platform': platform_name,
                            'error': str(e),
                            'thread_id': threading.current_thread().ident
                        }
                
                test_platforms = ['aws', 'ncp', 'ncpgov', 'gcp', 'oci']
                
                # Execute concurrent configuration access
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [
                        executor.submit(access_platform_config, platform)
                        for platform in test_platforms
                    ]
                    
                    results = []
                    for future in concurrent.futures.as_completed(futures, timeout=30):
                        try:
                            result = future.result()
                            results.append(result)
                        except Exception as e:
                            results.append({'error': str(e)})
                
                # Verify concurrent access worked
                self.assertEqual(len(results), len(test_platforms))
                
                # Verify different threads were used
                thread_ids = [r.get('thread_id') for r in results if 'thread_id' in r]
                unique_threads = set(thread_ids)
                self.assertGreater(len(unique_threads), 1, "Should use multiple threads")
                
                # Verify configuration was loaded successfully
                successful_loads = [r for r in results if r.get('config_loaded', False)]
                self.assertGreater(len(successful_loads), 0, "Should successfully load configuration")
                
        except ImportError as e:
            self.skipTest(f"Concurrent configuration access not available: {e}")
    
    def test_concurrent_command_execution(self):
        """Test concurrent command execution across platforms."""
        try:
            from src.ic.cli import main
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Define test commands for concurrent execution
            test_commands = []
            for platform in platforms[:3]:  # Test first 3 platforms
                services = discovery.list_services(platform)
                if services:
                    test_commands.append((platform, services[0], 'info'))
            
            if not test_commands:
                self.skipTest("No commands available for testing")
            
            def execute_command(platform, service, command):
                """Execute a single command."""
                try:
                    # Mock platform-specific clients
                    client_patches = self._get_platform_client_patches(platform)
                    
                    with client_patches:
                        # Capture original argv
                        original_argv = sys.argv.copy()
                        
                        try:
                            sys.argv = ['ic', platform, service, command, '--help']
                            
                            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                                    try:
                                        main()
                                        return {
                                            'platform': platform,
                                            'service': service,
                                            'command': command,
                                            'success': True,
                                            'output': mock_stdout.getvalue(),
                                            'thread_id': threading.current_thread().ident
                                        }
                                    except SystemExit as e:
                                        return {
                                            'platform': platform,
                                            'service': service,
                                            'command': command,
                                            'success': e.code == 0,
                                            'exit_code': e.code,
                                            'output': mock_stdout.getvalue(),
                                            'error': mock_stderr.getvalue(),
                                            'thread_id': threading.current_thread().ident
                                        }
                        finally:
                            sys.argv = original_argv
                            
                except Exception as e:
                    return {
                        'platform': platform,
                        'service': service,
                        'command': command,
                        'error': str(e),
                        'thread_id': threading.current_thread().ident
                    }
            
            # Execute commands concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(execute_command, platform, service, command)
                    for platform, service, command in test_commands
                ]
                
                results = []
                for future in concurrent.futures.as_completed(futures, timeout=60):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append({'error': str(e)})
            
            # Verify concurrent execution
            self.assertEqual(len(results), len(test_commands))
            
            # Verify different threads were used
            thread_ids = [r.get('thread_id') for r in results if 'thread_id' in r]
            unique_threads = set(thread_ids)
            self.assertGreater(len(unique_threads), 1, "Should use multiple threads")
            
            # Verify commands executed successfully
            successful_commands = [r for r in results if r.get('success', False)]
            success_rate = len(successful_commands) / len(results) if results else 0
            self.assertGreaterEqual(success_rate, 0.5, "At least 50% of concurrent commands should succeed")
            
        except ImportError as e:
            self.skipTest(f"Concurrent command execution not available: {e}")


class TestPlatformInteroperability(MultiPlatformIntegrationTestCase):
    """Test interoperability between different platforms."""
    
    def test_cross_platform_data_consistency(self):
        """Test data consistency across platforms."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test that platform data structures are consistent
            platform_data = {}
            
            for platform_name in platforms[:4]:  # Test first 4 platforms
                platform_info = discovery.get_platform(platform_name)
                services = discovery.list_services(platform_name)
                
                platform_data[platform_name] = {
                    'available': platform_info.available if platform_info else False,
                    'services': services,
                    'service_count': len(services)
                }
                
                # Test service data consistency
                for service_name in services[:2]:  # Test first 2 services
                    service_info = discovery.get_service(platform_name, service_name)
                    commands = discovery.get_service_commands(platform_name, service_name)
                    
                    platform_data[platform_name][f'{service_name}_commands'] = list(commands.keys())
                    platform_data[platform_name][f'{service_name}_available'] = (
                        service_info.available if service_info else False
                    )
            
            # Verify data consistency
            for platform_name, data in platform_data.items():
                with self.subTest(platform=platform_name):
                    # Basic structure consistency
                    self.assertIn('available', data)
                    self.assertIn('services', data)
                    self.assertIn('service_count', data)
                    
                    # Data type consistency
                    self.assertIsInstance(data['available'], bool)
                    self.assertIsInstance(data['services'], list)
                    self.assertIsInstance(data['service_count'], int)
                    
                    # Logical consistency
                    self.assertEqual(len(data['services']), data['service_count'])
            
        except ImportError as e:
            self.skipTest(f"Platform interoperability testing not available: {e}")
    
    def test_unified_error_handling(self):
        """Test that error handling is consistent across platforms."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test consistent error handling across platforms
            error_scenarios = [
                ('nonexistent_service', 'info'),
                ('ec2', 'nonexistent_command'),
                ('', ''),
                (None, None)
            ]
            
            for platform_name in platforms[:3]:  # Test first 3 platforms
                for service_name, command_name in error_scenarios:
                    with self.subTest(platform=platform_name, service=service_name, command=command_name):
                        try:
                            # Test service error handling
                            if service_name:
                                service_info = discovery.get_service(platform_name, service_name)
                                if service_name == 'nonexistent_service':
                                    self.assertIsNone(service_info, "Should return None for nonexistent service")
                            
                            # Test command error handling
                            if service_name and command_name:
                                command_module = discovery.get_command_module(platform_name, service_name, command_name)
                                if command_name == 'nonexistent_command':
                                    self.assertIsNone(command_module, "Should return None for nonexistent command")
                            
                            # Should not raise exceptions
                            self.assertTrue(True)
                            
                        except Exception as e:
                            self.fail(f"Error handling failed for {platform_name}/{service_name}/{command_name}: {e}")
            
        except ImportError as e:
            self.skipTest(f"Unified error handling testing not available: {e}")
    
    def test_cross_platform_configuration_validation(self):
        """Test configuration validation across platforms."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager)
            
            # Mock config directory
            with patch.object(config_manager, 'config_dir', self.config_dir):
                config = config_manager.load_config()
                
                # Test configuration validation across platforms
                validation_results = {}
                
                for platform_name in ['aws', 'ncp', 'ncpgov', 'gcp', 'oci', 'azure']:
                    if platform_name in config:
                        platform_config = config[platform_name]
                        
                        validation_results[platform_name] = {
                            'has_config': True,
                            'has_regions_or_locations': (
                                'regions' in platform_config or 
                                'locations' in platform_config
                            ),
                            'has_max_workers': 'max_workers' in platform_config,
                            'has_timeout': 'timeout' in platform_config,
                            'config_keys': list(platform_config.keys())
                        }
                    else:
                        validation_results[platform_name] = {
                            'has_config': False
                        }
                
                # Verify configuration consistency
                configured_platforms = [p for p, r in validation_results.items() if r['has_config']]
                self.assertGreater(len(configured_platforms), 0, "Should have some configured platforms")
                
                # Test common configuration patterns
                for platform_name in configured_platforms:
                    result = validation_results[platform_name]
                    
                    with self.subTest(platform=platform_name):
                        # Most platforms should have region/location configuration
                        if platform_name != 'cloudflare':  # CloudFlare doesn't use regions
                            self.assertTrue(
                                result['has_regions_or_locations'],
                                f"{platform_name} should have regions or locations configured"
                            )
                        
                        # All platforms should have worker configuration
                        self.assertTrue(
                            result['has_max_workers'],
                            f"{platform_name} should have max_workers configured"
                        )
                
        except ImportError as e:
            self.skipTest(f"Cross-platform configuration validation not available: {e}")


if __name__ == '__main__':
    unittest.main()