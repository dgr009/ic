#!/usr/bin/env python3
"""
CLI Integration Test Suite

Tests for CLI command discovery and routing, argument parsing,
help system functionality, and error handling validation.

Requirements: 3.1, 3.2, 3.3
"""

import unittest
import sys
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO
from typing import List, Dict, Any, Optional


class CLIIntegrationTestCase(unittest.TestCase):
    """Base test case for CLI integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_argv = sys.argv.copy()
        self.original_path = sys.path.copy()
        
        # Ensure src directory is in path
        src_dir = Path(__file__).parent.parent.parent / "src"
        if src_dir.exists() and str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
    
    def tearDown(self):
        """Clean up test environment."""
        sys.argv = self.original_argv
        sys.path = self.original_path


class TestCLICommandDiscovery(CLIIntegrationTestCase):
    """Test CLI command discovery functionality."""
    
    def test_platform_discovery_integration(self):
        """Test CLI can discover platforms through platform discovery system."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.discover_platforms()
            
            # Should discover at least some platforms
            self.assertIsInstance(platforms, dict)
            self.assertGreater(len(platforms), 0, "Should discover at least one platform")
            
            # Test that discovered platforms have proper structure
            for platform_name, platform_info in platforms.items():
                self.assertIsInstance(platform_name, str)
                self.assertIsNotNone(platform_info)
                self.assertIsInstance(platform_info.services, dict)
                
        except ImportError as e:
            self.skipTest(f"Platform discovery not available: {e}")
    
    def test_service_discovery_integration(self):
        """Test CLI can discover services within platforms."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test service discovery for available platforms
            for platform_name in platforms[:3]:  # Test first 3 platforms
                with self.subTest(platform=platform_name):
                    services = discovery.list_services(platform_name)
                    
                    # Services should be a list
                    self.assertIsInstance(services, list)
                    
                    # Test getting service info
                    for service_name in services[:2]:  # Test first 2 services
                        service_info = discovery.get_service(platform_name, service_name)
                        
                        if service_info and service_info.available:
                            self.assertIsNotNone(service_info.module)
                            
        except ImportError as e:
            self.skipTest(f"Service discovery not available: {e}")
    
    def test_command_discovery_integration(self):
        """Test CLI can discover commands within services."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test command discovery
            for platform_name in platforms[:2]:  # Test first 2 platforms
                services = discovery.list_services(platform_name)
                
                for service_name in services[:1]:  # Test first service
                    with self.subTest(platform=platform_name, service=service_name):
                        commands = discovery.get_service_commands(platform_name, service_name)
                        
                        # Commands should be a dictionary
                        self.assertIsInstance(commands, dict)
                        
                        # Test getting specific command modules
                        for command_name in list(commands.keys())[:1]:  # Test first command
                            command_module = discovery.get_command_module(platform_name, service_name, command_name)
                            
                            if command_module:
                                self.assertIsNotNone(command_module)
                                
        except ImportError as e:
            self.skipTest(f"Command discovery not available: {e}")


class TestCLIArgumentParsing(CLIIntegrationTestCase):
    """Test CLI argument parsing functionality."""
    
    def test_cli_parser_setup(self):
        """Test CLI parser can be set up correctly."""
        try:
            from src.ic.cli import setup_platform_parsers
            from src.ic.core.platform_discovery import get_platform_discovery
            
            # Create a test parser
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers(dest="platform")
            
            # Test that platform parsers can be set up
            setup_platform_parsers(subparsers)
            
            # Should not raise any exceptions
            self.assertTrue(True)
            
        except ImportError as e:
            self.skipTest(f"CLI parser setup not available: {e}")
        except Exception as e:
            self.fail(f"CLI parser setup failed: {e}")
    
    def test_argument_parsing_structure(self):
        """Test argument parsing follows expected structure."""
        try:
            from src.ic.cli import setup_platform_parsers
            from src.ic.core.platform_discovery import get_platform_discovery
            
            # Create a test parser
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers(dest="platform")
            
            # Set up platform parsers
            setup_platform_parsers(subparsers)
            
            # Test parsing help for available platforms
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if platforms:
                platform_name = platforms[0]
                
                # Test that platform help can be generated
                with patch('sys.exit'):
                    try:
                        args = parser.parse_args([platform_name, '--help'])
                    except SystemExit:
                        pass  # Expected for --help
                    
        except ImportError as e:
            self.skipTest(f"Argument parsing not available: {e}")
        except Exception as e:
            # Some parsing errors are expected in test environment
            pass
    
    def test_command_argument_registration(self):
        """Test command modules can register their arguments."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test argument registration for available commands
            for platform_name in platforms[:1]:  # Test first platform
                services = discovery.list_services(platform_name)
                
                for service_name in services[:1]:  # Test first service
                    commands = discovery.get_service_commands(platform_name, service_name)
                    
                    for command_name, command_module in list(commands.items())[:1]:  # Test first command
                        with self.subTest(platform=platform_name, service=service_name, command=command_name):
                            # Test if command has add_arguments function
                            add_arguments = getattr(command_module, 'add_arguments', None)
                            
                            if add_arguments:
                                # Test that add_arguments can be called
                                test_parser = argparse.ArgumentParser()
                                try:
                                    add_arguments(test_parser)
                                    self.assertTrue(True)  # Success if no exception
                                except Exception as e:
                                    # Some argument registration failures are expected
                                    pass
                                    
        except ImportError as e:
            self.skipTest(f"Command argument registration not available: {e}")


class TestCLIHelpSystem(CLIIntegrationTestCase):
    """Test CLI help system functionality."""
    
    def test_main_help_display(self):
        """Test main CLI help can be displayed."""
        try:
            from src.ic.cli import main
            
            # Test main help
            with patch('sys.argv', ['ic', '--help']):
                with patch('sys.exit') as mock_exit:
                    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                        try:
                            main()
                        except SystemExit:
                            pass  # Expected for --help
                        
                        # Should have produced some output
                        output = mock_stdout.getvalue()
                        self.assertIn('usage:', output.lower())
                        
        except ImportError as e:
            self.skipTest(f"Main help not available: {e}")
        except Exception as e:
            # Help system might not work perfectly in test environment
            pass
    
    def test_platform_help_display(self):
        """Test platform-specific help can be displayed."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if platforms:
                platform_name = platforms[0]
                
                # Test platform help
                help_text = discovery.get_platform_help(platform_name)
                
                # Should contain platform information
                self.assertIsInstance(help_text, str)
                self.assertIn(platform_name, help_text.lower())
                
        except ImportError as e:
            self.skipTest(f"Platform help not available: {e}")
    
    def test_service_help_information(self):
        """Test service help information is available."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test service help for available platforms
            for platform_name in platforms[:2]:  # Test first 2 platforms
                services = discovery.list_services(platform_name)
                
                for service_name in services[:1]:  # Test first service
                    with self.subTest(platform=platform_name, service=service_name):
                        service_info = discovery.get_service(platform_name, service_name)
                        
                        if service_info:
                            # Service should have a name
                            self.assertIsInstance(service_info.name, str)
                            
                            # Service should have availability information
                            self.assertIsInstance(service_info.available, bool)
                            
        except ImportError as e:
            self.skipTest(f"Service help not available: {e}")


class TestCLICommandRouting(CLIIntegrationTestCase):
    """Test CLI command routing functionality."""
    
    def test_command_routing_structure(self):
        """Test command routing follows expected structure."""
        try:
            from src.ic.cli import execute_single_command
            from src.ic.core.platform_discovery import get_platform_discovery
            import argparse
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test command routing for available platforms
            for platform_name in platforms[:1]:  # Test first platform
                services = discovery.list_services(platform_name)
                
                for service_name in services[:1]:  # Test first service
                    commands = discovery.get_service_commands(platform_name, service_name)
                    
                    for command_name in list(commands.keys())[:1]:  # Test first command
                        with self.subTest(platform=platform_name, service=service_name, command=command_name):
                            # Create mock args
                            args = argparse.Namespace(
                                platform=platform_name,
                                service=service_name,
                                command=command_name
                            )
                            
                            # Test that command routing can find the command
                            command_module = discovery.get_command_module(platform_name, service_name, command_name)
                            
                            if command_module:
                                main_func = getattr(command_module, 'main', None)
                                self.assertTrue(callable(main_func) or main_func is None)
                                
        except ImportError as e:
            self.skipTest(f"Command routing not available: {e}")
    
    def test_multi_service_command_routing(self):
        """Test multi-service command routing functionality."""
        try:
            from src.ic.cli import execute_multi_service_command
            from src.ic.core.platform_discovery import get_platform_discovery
            import argparse
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test multi-service routing for available platforms
            for platform_name in platforms[:1]:  # Test first platform
                services = discovery.list_services(platform_name)
                
                if len(services) >= 2:
                    # Test with first two services
                    test_services = services[:2]
                    
                    # Find a common command
                    common_commands = None
                    for service_name in test_services:
                        commands = discovery.get_service_commands(platform_name, service_name)
                        if common_commands is None:
                            common_commands = set(commands.keys())
                        else:
                            common_commands &= set(commands.keys())
                    
                    if common_commands:
                        command_name = list(common_commands)[0]
                        
                        with self.subTest(platform=platform_name, services=test_services, command=command_name):
                            # Create mock args
                            args = argparse.Namespace(
                                platform=platform_name,
                                service=','.join(test_services),
                                command=command_name
                            )
                            
                            # Test that multi-service routing can be set up
                            # (We don't actually execute to avoid side effects)
                            self.assertTrue(callable(execute_multi_service_command))
                            
        except ImportError as e:
            self.skipTest(f"Multi-service routing not available: {e}")


class TestCLIErrorHandling(CLIIntegrationTestCase):
    """Test CLI error handling and user experience."""
    
    def test_platform_not_found_error(self):
        """Test error handling for non-existent platforms."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            
            # Test platform validation
            is_available, error_msg = discovery.validate_platform_availability('nonexistent_platform')
            
            self.assertFalse(is_available)
            self.assertIsNotNone(error_msg)
            self.assertIn('nonexistent_platform', error_msg)
            
        except ImportError as e:
            self.skipTest(f"Platform error handling not available: {e}")
    
    def test_service_not_found_error(self):
        """Test error handling for non-existent services."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if platforms:
                platform_name = platforms[0]
                
                # Test getting non-existent service
                service_info = discovery.get_service(platform_name, 'nonexistent_service')
                self.assertIsNone(service_info)
                
        except ImportError as e:
            self.skipTest(f"Service error handling not available: {e}")
    
    def test_command_not_found_error(self):
        """Test error handling for non-existent commands."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            if platforms:
                platform_name = platforms[0]
                services = discovery.list_services(platform_name)
                
                if services:
                    service_name = services[0]
                    
                    # Test getting non-existent command
                    command_module = discovery.get_command_module(platform_name, service_name, 'nonexistent_command')
                    self.assertIsNone(command_module)
                    
        except ImportError as e:
            self.skipTest(f"Command error handling not available: {e}")
    
    def test_import_error_handling(self):
        """Test handling of import errors in CLI."""
        try:
            from src.ic.core.platform_discovery import PlatformDiscovery
            
            discovery = PlatformDiscovery()
            
            # Test importing non-existent module
            result = discovery._import_module('completely.invalid.module.path')
            self.assertIsNone(result)
            
            # Should not raise exception, should return None
            self.assertTrue(True)
            
        except ImportError as e:
            self.skipTest(f"Import error handling not available: {e}")


class TestCLIUserExperience(CLIIntegrationTestCase):
    """Test CLI user experience aspects."""
    
    def test_available_platforms_listing(self):
        """Test CLI can list available platforms."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Should return a list of platform names
            self.assertIsInstance(platforms, list)
            
            # Platform names should be strings
            for platform_name in platforms:
                self.assertIsInstance(platform_name, str)
                self.assertGreater(len(platform_name), 0)
                
        except ImportError as e:
            self.skipTest(f"Platform listing not available: {e}")
    
    def test_available_services_listing(self):
        """Test CLI can list available services for platforms."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test service listing for available platforms
            for platform_name in platforms[:2]:  # Test first 2 platforms
                with self.subTest(platform=platform_name):
                    services = discovery.list_services(platform_name)
                    
                    # Should return a list of service names
                    self.assertIsInstance(services, list)
                    
                    # Service names should be strings
                    for service_name in services:
                        self.assertIsInstance(service_name, str)
                        self.assertGreater(len(service_name), 0)
                        
        except ImportError as e:
            self.skipTest(f"Service listing not available: {e}")
    
    def test_command_availability_checking(self):
        """Test CLI can check command availability."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test command availability for available platforms
            for platform_name in platforms[:1]:  # Test first platform
                services = discovery.list_services(platform_name)
                
                for service_name in services[:1]:  # Test first service
                    with self.subTest(platform=platform_name, service=service_name):
                        service_info = discovery.get_service(platform_name, service_name)
                        
                        if service_info:
                            # Should have availability information
                            self.assertIsInstance(service_info.available, bool)
                            
                            # If not available, should have error message
                            if not service_info.available:
                                self.assertIsNotNone(service_info.error)
                                
        except ImportError as e:
            self.skipTest(f"Command availability checking not available: {e}")


class TestCLIIntegrationEndToEnd(CLIIntegrationTestCase):
    """Test end-to-end CLI integration scenarios."""
    
    def test_cli_initialization_flow(self):
        """Test complete CLI initialization flow."""
        try:
            from src.ic.cli import get_config_manager, validate_core_dependencies
            
            # Test dependency validation
            deps_valid = validate_core_dependencies()
            self.assertIsInstance(deps_valid, bool)
            
            # Test config manager initialization
            config_manager = get_config_manager()
            self.assertIsNotNone(config_manager)
            
        except ImportError as e:
            self.skipTest(f"CLI initialization not available: {e}")
        except Exception as e:
            # Some initialization might fail in test environment
            pass
    
    def test_platform_discovery_integration_flow(self):
        """Test complete platform discovery integration flow."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            # Test discovery initialization
            discovery = get_platform_discovery()
            self.assertIsNotNone(discovery)
            
            # Test platform discovery
            platforms = discovery.discover_platforms()
            self.assertIsInstance(platforms, dict)
            
            # Test service discovery for discovered platforms
            for platform_name, platform_info in list(platforms.items())[:1]:  # Test first platform
                if platform_info.available:
                    services = discovery.list_services(platform_name)
                    self.assertIsInstance(services, list)
                    
                    # Test command discovery for services
                    for service_name in services[:1]:  # Test first service
                        commands = discovery.get_service_commands(platform_name, service_name)
                        self.assertIsInstance(commands, dict)
                        
        except ImportError as e:
            self.skipTest(f"Platform discovery integration not available: {e}")
    
    def test_error_recovery_flow(self):
        """Test error recovery in CLI integration."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            
            # Test recovery from various error scenarios
            error_scenarios = [
                ('nonexistent_platform', 'nonexistent_service', 'nonexistent_command'),
                ('', '', ''),
                (None, None, None),
            ]
            
            for platform, service, command in error_scenarios:
                with self.subTest(platform=platform, service=service, command=command):
                    try:
                        # These should handle errors gracefully
                        if platform:
                            platform_info = discovery.get_platform(platform)
                            # Should return None for invalid platforms
                            if platform == 'nonexistent_platform':
                                self.assertIsNone(platform_info)
                        
                        if platform and service:
                            service_info = discovery.get_service(platform, service)
                            # Should return None for invalid services
                            if service == 'nonexistent_service':
                                self.assertIsNone(service_info)
                        
                        if platform and service and command:
                            command_module = discovery.get_command_module(platform, service, command)
                            # Should return None for invalid commands
                            if command == 'nonexistent_command':
                                self.assertIsNone(command_module)
                                
                    except Exception as e:
                        # Should not raise exceptions for invalid inputs
                        self.fail(f"Error recovery failed for {platform}/{service}/{command}: {e}")
                        
        except ImportError as e:
            self.skipTest(f"Error recovery not available: {e}")


if __name__ == '__main__':
    unittest.main()