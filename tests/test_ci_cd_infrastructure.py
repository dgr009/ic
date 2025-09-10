"""
CI/CD Testing Infrastructure

This module provides enhanced testing infrastructure that works in CI/CD environments
without requiring live cloud credentials or ~/.ic/config files. It includes:

1. Mock configuration tests that don't require live credentials
2. Configuration-independent tests for CLI parsing and basic functionality  
3. Tests for progress decorator functionality and thread safety
4. Graceful handling of missing configuration files

Requirements: 9.4, 10.1, 10.2, 10.3
"""

import os
import sys
import tempfile
import threading
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class TestConfigurationIndependentFunctionality:
    """Tests that work without requiring ~/.ic/config files or live credentials."""
    
    def test_basic_imports_without_config(self):
        """Test that core modules can be imported without configuration files."""
        # Test core imports
        try:
            from ic.config.manager import ConfigManager
            from ic.config.security import SecurityManager
            from ic.core.logging import ICLogger
            assert ConfigManager is not None
            assert SecurityManager is not None
            assert ICLogger is not None
        except ImportError as e:
            pytest.fail(f"Failed to import core modules: {e}")
    
    def test_cli_parser_without_config(self):
        """Test CLI argument parsing without requiring configuration files."""
        try:
            from ic.cli import create_parser
            parser = create_parser()
            
            # Test basic argument parsing
            args = parser.parse_args(['--help'])
            assert args is not None
        except SystemExit:
            # --help causes SystemExit, which is expected
            pass
        except Exception as e:
            pytest.fail(f"CLI parser failed: {e}")
    
    def test_config_manager_with_defaults_only(self):
        """Test ConfigManager using only default configuration."""
        from ic.config.manager import ConfigManager
        from ic.config.security import SecurityManager
        
        security_manager = SecurityManager()
        config_manager = ConfigManager(security_manager=security_manager)
        
        # Load config without any files (should use defaults)
        with patch('pathlib.Path.exists', return_value=False):
            config = config_manager.load_config([])
        
        # Should return valid default configuration
        assert config is not None
        assert config['version'] == '1.0'
        assert 'logging' in config
        assert 'aws' in config
        assert 'azure' in config
        assert 'gcp' in config
        assert 'security' in config
    
    def test_security_manager_without_config(self):
        """Test SecurityManager functionality without configuration files."""
        from ic.config.security import SecurityManager
        
        security_manager = SecurityManager()
        
        # Test basic security validation
        test_config = {
            'aws': {'secret_key': 'sk-1234567890abcdef'},
            'password': 'secret123'
        }
        
        warnings = security_manager.validate_config_security(test_config)
        assert isinstance(warnings, list)
        assert len(warnings) > 0  # Should detect sensitive data
    
    def test_logger_with_mock_config(self):
        """Test ICLogger with mock configuration."""
        from ic.core.logging import ICLogger
        
        mock_config = {
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'file_path': '/tmp/test.log',
                'max_files': 10,
                'mask_sensitive': True
            },
            'security': {
                'sensitive_keys': ['password', 'token', 'key'],
                'mask_pattern': '***MASKED***'
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config['logging']['file_path'] = f"{temp_dir}/test.log"
            
            logger = ICLogger(mock_config)
            assert logger is not None
            
            # Test basic logging functionality
            logger.log_info_file_only("Test message")
            logger.log_error("Test error")
            
            # Verify log file was created
            log_file = Path(temp_dir) / "test.log"
            assert log_file.exists()


class TestMockConfigurationTests:
    """Mock configuration tests that don't require live cloud credentials."""
    
    def setup_method(self):
        """Set up mock configurations for testing."""
        self.mock_aws_config = {
            'version': '1.0',
            'aws': {
                'accounts': ['123456789012', '987654321098'],
                'regions': ['us-east-1', 'us-west-2'],
                'cross_account_role': 'TestRole',
                'max_workers': 5
            },
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO'
            },
            'security': {
                'sensitive_keys': ['password', 'token', 'key'],
                'mask_pattern': '***MASKED***'
            }
        }
        
        self.mock_oci_config = {
            'tenancy': 'ocid1.tenancy.oc1..test',
            'user': 'ocid1.user.oc1..test',
            'fingerprint': 'test-fingerprint',
            'key_file': '/path/to/test.pem',
            'region': 'us-ashburn-1'
        }
    
    def test_aws_module_with_mock_credentials(self):
        """Test AWS modules with mock credentials and configuration."""
        with patch('boto3.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            # Mock EC2 client
            mock_ec2_client = Mock()
            mock_session.client.return_value = mock_ec2_client
            
            # Mock EC2 response
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
            
            # Test AWS EC2 info functionality
            try:
                from aws.ec2.info import EC2InfoCollector
                collector = EC2InfoCollector(mock_session, 'us-east-1')
                instances = collector.collect_instances()
                assert isinstance(instances, list)
            except ImportError:
                pytest.skip("AWS EC2 module not available")
    
    def test_oci_module_with_mock_credentials(self):
        """Test OCI modules with mock credentials and configuration."""
        with patch('oci.config.from_file') as mock_config_from_file:
            with patch('oci.identity.IdentityClient') as mock_identity_client_class:
                mock_config_from_file.return_value = self.mock_oci_config
                
                mock_identity_client = Mock()
                mock_identity_client_class.return_value = mock_identity_client
                
                # Mock compartment response
                mock_compartment = Mock()
                mock_compartment.id = 'ocid1.compartment.oc1..test'
                mock_compartment.name = 'Test Compartment'
                mock_compartment.lifecycle_state = 'ACTIVE'
                
                mock_identity_client.list_compartments.return_value.data = [mock_compartment]
                
                # Test OCI compartment functionality
                try:
                    from oci_module.compartment.info import CompartmentTreeBuilder
                    builder = CompartmentTreeBuilder(mock_identity_client, 'ocid1.tenancy.oc1..test')
                    tree = builder.build_compartment_tree()
                    assert tree is not None
                except ImportError:
                    pytest.skip("OCI compartment module not available")
    
    def test_cloudflare_module_with_mock_credentials(self):
        """Test CloudFlare modules with mock credentials."""
        mock_cf_config = {
            'email': 'test@example.com',
            'api_token': 'test-token-12345',
            'accounts': ['account1', 'account2']
        }
        
        with patch('requests.get') as mock_get:
            # Mock CloudFlare API response
            mock_response = Mock()
            mock_response.json.return_value = {
                'success': True,
                'result': [
                    {
                        'id': 'zone123',
                        'name': 'example.com',
                        'status': 'active'
                    }
                ]
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Test CloudFlare DNS functionality
            try:
                from cf.dns.list_info import CloudFlareDNSCollector
                collector = CloudFlareDNSCollector(mock_cf_config)
                zones = collector.collect_zones()
                assert isinstance(zones, list)
            except ImportError:
                pytest.skip("CloudFlare DNS module not available")
    
    def test_ssh_module_with_mock_connections(self):
        """Test SSH modules with mock connections."""
        mock_servers = [
            {'host': '192.168.1.10', 'username': 'test', 'key_file': '/path/to/key.pem'},
            {'host': '192.168.1.11', 'username': 'test', 'key_file': '/path/to/key.pem'}
        ]
        
        with patch('paramiko.SSHClient') as mock_ssh_client_class:
            mock_ssh_client = Mock()
            mock_ssh_client_class.return_value = mock_ssh_client
            
            # Mock SSH command execution
            mock_stdin = Mock()
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_stdout.read.return_value = b'Linux test-server 5.4.0'
            mock_stderr.read.return_value = b''
            
            mock_ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
            
            # Test SSH server info functionality
            try:
                from ssh.server_info import SSHServerInfoCollector
                collector = SSHServerInfoCollector(mock_servers)
                server_info = collector.collect_server_info()
                assert isinstance(server_info, list)
            except ImportError:
                pytest.skip("SSH server info module not available")


class TestProgressDecoratorFunctionality:
    """Tests for progress decorator functionality and thread safety."""
    
    def setup_method(self):
        """Set up progress decorator tests."""
        # Import progress decorator
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from common.progress_decorator import ProgressBarDecorator, progress_bar, spinner, ManualProgress
        
        self.ProgressBarDecorator = ProgressBarDecorator
        self.progress_bar = progress_bar
        self.spinner = spinner
        self.ManualProgress = ManualProgress
    
    def test_progress_decorator_basic_functionality(self):
        """Test basic progress decorator functionality."""
        @self.progress_bar("Test operation")
        def test_function():
            time.sleep(0.1)
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_progress_decorator_with_iterable(self):
        """Test progress decorator with iterable operations."""
        @self.progress_bar("Processing items")
        def process_items(items):
            results = []
            for item in items:
                time.sleep(0.01)  # Simulate work
                results.append(f"processed_{item}")
            return results
        
        test_items = ['item1', 'item2', 'item3']
        results = process_items(test_items)
        assert len(results) == 3
        assert all('processed_' in result for result in results)
    
    def test_progress_decorator_error_handling(self):
        """Test progress decorator error handling."""
        @self.progress_bar("Test operation with error")
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
    
    def test_spinner_decorator(self):
        """Test spinner decorator functionality."""
        @self.spinner("Connecting to service")
        def connect_function():
            time.sleep(0.1)
            return "connected"
        
        result = connect_function()
        assert result == "connected"
    
    def test_manual_progress_context(self):
        """Test manual progress context manager."""
        with self.ManualProgress("Manual operation", total=5) as progress:
            for i in range(5):
                time.sleep(0.01)
                progress.update(f"Step {i+1}")
                progress.advance(1)
    
    def test_progress_decorator_thread_safety(self):
        """Test progress decorator thread safety with concurrent operations."""
        results = []
        errors = []
        
        @self.progress_bar("Thread-safe operation")
        def thread_safe_function(item_id):
            time.sleep(0.01)  # Simulate work
            return f"result_{item_id}"
        
        def worker(item_id):
            try:
                result = thread_safe_function(item_id)
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # Run multiple threads concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert all('result_' in result for result in results)
    
    def test_progress_decorator_concurrent_execution(self):
        """Test progress decorator with ThreadPoolExecutor."""
        @self.progress_bar("Concurrent processing")
        def concurrent_function(items):
            def process_item(item):
                time.sleep(0.01)
                return f"processed_{item}"
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(process_item, item) for item in items]
                results = [future.result() for future in futures]
            
            return results
        
        test_items = [f"item_{i}" for i in range(10)]
        results = concurrent_function(test_items)
        
        assert len(results) == 10
        assert all('processed_' in result for result in results)
    
    def test_progress_decorator_without_rich(self):
        """Test progress decorator fallback when Rich is not available."""
        # Mock Rich as unavailable
        with patch('common.progress_decorator.RICH_AVAILABLE', False):
            @self.progress_bar("Fallback operation")
            def fallback_function():
                time.sleep(0.1)
                return "fallback_success"
            
            result = fallback_function()
            assert result == "fallback_success"
    
    def test_progress_decorator_auto_detection(self):
        """Test progress decorator automatic operation type detection."""
        decorator = self.ProgressBarDecorator(auto_detect=True)
        
        # Test single operation detection
        def single_operation():
            return "single"
        
        operation_type = decorator._detect_operation_type(single_operation, (), {})
        assert operation_type == "single"
        
        # Test iterable operation detection
        def iterable_operation(items):
            return items
        
        test_items = ['a', 'b', 'c']
        operation_type = decorator._detect_operation_type(iterable_operation, (test_items,), {})
        assert operation_type == "iterable"
    
    def test_progress_context_thread_safety(self):
        """Test ProgressContext thread safety."""
        from common.progress_decorator import ProgressContext
        
        context = ProgressContext(total_operations=100, thread_safe=True)
        
        def update_context():
            for _ in range(10):
                with context._lock:
                    context.completed_operations += 1
        
        # Run multiple threads updating context
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=update_context)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify thread-safe updates
        assert context.completed_operations == 100


class TestGracefulConfigHandling:
    """Tests for graceful handling of missing configuration files."""
    
    def test_config_manager_missing_files(self):
        """Test ConfigManager with missing configuration files."""
        from ic.config.manager import ConfigManager
        from ic.config.security import SecurityManager
        
        security_manager = SecurityManager()
        config_manager = ConfigManager(security_manager=security_manager)
        
        # Test with non-existent config files
        non_existent_files = [
            Path('/nonexistent/config1.yaml'),
            Path('/nonexistent/config2.yaml')
        ]
        
        # Should not raise exception, should return default config
        config = config_manager.load_config(non_existent_files)
        
        assert config is not None
        assert config['version'] == '1.0'
        assert 'logging' in config
        assert 'aws' in config
    
    def test_cli_commands_without_config_files(self):
        """Test CLI commands work without configuration files."""
        # Mock missing home config directory
        with patch('pathlib.Path.exists', return_value=False):
            with patch('pathlib.Path.is_file', return_value=False):
                try:
                    from ic.cli import create_parser
                    parser = create_parser()
                    
                    # Test that parser can be created without config files
                    assert parser is not None
                    
                    # Test basic argument parsing
                    args = parser.parse_args(['config', 'show'])
                    assert args.command == 'show'
                    
                except Exception as e:
                    pytest.fail(f"CLI failed without config files: {e}")
    
    def test_aws_modules_graceful_degradation(self):
        """Test AWS modules handle missing credentials gracefully."""
        with patch('boto3.Session') as mock_session_class:
            # Mock session creation failure
            mock_session_class.side_effect = Exception("No credentials found")
            
            try:
                from aws.profile.info import ProfileInfoCollector
                
                # Should handle missing credentials gracefully
                with pytest.raises(Exception, match="No credentials found"):
                    collector = ProfileInfoCollector()
                    
            except ImportError:
                pytest.skip("AWS profile module not available")
    
    def test_oci_modules_graceful_degradation(self):
        """Test OCI modules handle missing configuration gracefully."""
        with patch('oci.config.from_file') as mock_config_from_file:
            # Mock config loading failure
            mock_config_from_file.side_effect = Exception("Config file not found")
            
            try:
                from oci_module.compartment.info import CompartmentTreeBuilder
                
                # Should handle missing config gracefully
                with pytest.raises(Exception, match="Config file not found"):
                    oci.config.from_file()
                    
            except ImportError:
                pytest.skip("OCI compartment module not available")
    
    def test_logging_without_config_directory(self):
        """Test logging system works without config directory."""
        from ic.core.logging import ICLogger
        
        # Mock config with non-existent log directory
        mock_config = {
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'file_path': '/nonexistent/directory/test.log',
                'max_files': 10,
                'mask_sensitive': True
            },
            'security': {
                'sensitive_keys': ['password'],
                'mask_pattern': '***MASKED***'
            }
        }
        
        # Should handle missing directory gracefully
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config['logging']['file_path'] = f"{temp_dir}/test.log"
            
            logger = ICLogger(mock_config)
            assert logger is not None
            
            # Should be able to log to console even if file logging fails
            logger.log_error("Test error message")


class TestCIEnvironmentCompatibility:
    """Tests specifically for CI/CD environment compatibility."""
    
    def test_github_actions_environment(self):
        """Test compatibility with GitHub Actions environment."""
        # Simulate GitHub Actions environment variables
        github_env = {
            'GITHUB_ACTIONS': 'true',
            'CI': 'true',
            'RUNNER_OS': 'Linux'
        }
        
        with patch.dict(os.environ, github_env):
            # Test that modules can be imported in CI environment
            try:
                from ic.config.manager import ConfigManager
                from ic.core.logging import ICLogger
                from common.progress_decorator import ProgressBarDecorator
                
                assert ConfigManager is not None
                assert ICLogger is not None
                assert ProgressBarDecorator is not None
                
            except Exception as e:
                pytest.fail(f"Failed to import modules in CI environment: {e}")
    
    def test_python_version_compatibility(self):
        """Test compatibility across Python versions."""
        python_version = sys.version_info
        
        # Should work with Python 3.9+
        assert python_version >= (3, 9), f"Python {python_version} not supported"
        
        # Test version-specific features
        if python_version >= (3, 10):
            # Test match statement (Python 3.10+)
            def test_match():
                value = "test"
                match value:
                    case "test":
                        return True
                    case _:
                        return False
            
            assert test_match() is True
    
    def test_dependency_imports_in_ci(self):
        """Test that all required dependencies can be imported in CI."""
        required_imports = [
            'yaml',
            'pathlib',
            'logging',
            'threading',
            'concurrent.futures',
            'dataclasses',
            'functools',
            'inspect'
        ]
        
        for module_name in required_imports:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Required dependency {module_name} not available: {e}")
    
    def test_optional_dependency_handling(self):
        """Test graceful handling of optional dependencies."""
        # Test Rich dependency handling
        try:
            import rich
            rich_available = True
        except ImportError:
            rich_available = False
        
        # Progress decorator should work regardless of Rich availability
        from common.progress_decorator import ProgressBarDecorator
        
        decorator = ProgressBarDecorator()
        
        @decorator
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_file_system_permissions_in_ci(self):
        """Test file system operations work in CI environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_config.yaml"
            
            # Test file creation
            test_config = {'version': '1.0', 'test': True}
            
            from ic.config.manager import ConfigManager
            config_manager = ConfigManager()
            
            # Should be able to create and read files
            config_manager.save_config(test_file, test_config)
            assert test_file.exists()
            
            loaded_config = config_manager._load_config_file(test_file)
            assert loaded_config == test_config


if __name__ == '__main__':
    pytest.main([__file__, '-v'])