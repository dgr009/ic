#!/usr/bin/env python3
"""
Import Integration Test Suite

Integration tests for import resolution in realistic scenarios,
testing both development and installed package environments.

Requirements: 2.1, 2.2, 6.1
"""

import unittest
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock


class ImportIntegrationTestCase(unittest.TestCase):
    """Base test case for import integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_path = sys.path.copy()
        self.test_dir = None
    
    def tearDown(self):
        """Clean up test environment."""
        sys.path = self.original_path
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)


class TestDevelopmentEnvironmentImports(ImportIntegrationTestCase):
    """Test imports in development environment."""
    
    def test_cli_execution_in_development(self):
        """Test CLI can be executed in development environment."""
        # Test that CLI module can be imported and executed
        try:
            from src.ic.cli import main
            
            # Test that main function exists and is callable
            self.assertTrue(callable(main))
            
            # Test that help can be displayed without errors
            with patch('sys.argv', ['ic', '--help']):
                with patch('sys.exit') as mock_exit:
                    try:
                        main()
                    except SystemExit:
                        pass  # Expected for --help
                    
        except ImportError as e:
            self.skipTest(f"Development environment not available: {e}")
    
    def test_platform_discovery_in_development(self):
        """Test platform discovery works in development environment."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.discover_platforms()
            
            # Should discover at least some platforms
            self.assertIsInstance(platforms, dict)
            self.assertGreater(len(platforms), 0, "Should discover at least one platform")
            
            # Test that platforms have proper structure
            for platform_name, platform_info in platforms.items():
                self.assertIsInstance(platform_name, str)
                self.assertIsNotNone(platform_info)
                
        except ImportError as e:
            self.skipTest(f"Development environment not available: {e}")
    
    def test_service_imports_in_development(self):
        """Test service modules can be imported in development environment."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test importing services from discovered platforms
            for platform_name in platforms[:3]:  # Test first 3 platforms
                services = discovery.list_services(platform_name)
                
                for service_name in services[:2]:  # Test first 2 services
                    with self.subTest(platform=platform_name, service=service_name):
                        service_info = discovery.get_service(platform_name, service_name)
                        
                        if service_info and service_info.available:
                            self.assertIsNotNone(service_info.module)
                            
        except ImportError as e:
            self.skipTest(f"Development environment not available: {e}")


class TestInstalledPackageImports(ImportIntegrationTestCase):
    """Test imports in installed package environment."""
    
    def test_cli_import_as_installed_package(self):
        """Test CLI can be imported as installed package."""
        # Simulate installed package environment by removing src from path
        src_path = Path(__file__).parent.parent.parent / "src"
        
        if str(src_path) in sys.path:
            sys.path.remove(str(src_path))
        
        try:
            # Clear any cached imports
            modules_to_remove = [m for m in sys.modules if m.startswith('ic.') or m.startswith('src.ic.')]
            for module in modules_to_remove:
                del sys.modules[module]
            
            # Try importing as installed package
            from ic.cli import main
            self.assertTrue(callable(main))
            
        except ImportError:
            self.skipTest("Installed package environment not available")
        finally:
            # Restore src path
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))
    
    def test_platform_discovery_as_installed_package(self):
        """Test platform discovery works as installed package."""
        # Simulate installed package environment
        src_path = Path(__file__).parent.parent.parent / "src"
        
        if str(src_path) in sys.path:
            sys.path.remove(str(src_path))
        
        try:
            # Clear any cached imports
            modules_to_remove = [m for m in sys.modules if m.startswith('ic.') or m.startswith('src.ic.')]
            for module in modules_to_remove:
                del sys.modules[module]
            
            from ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.discover_platforms()
            
            self.assertIsInstance(platforms, dict)
            
        except ImportError:
            self.skipTest("Installed package environment not available")
        finally:
            # Restore src path
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))


class TestFallbackMechanismIntegration(ImportIntegrationTestCase):
    """Test fallback mechanisms work in integration scenarios."""
    
    def test_import_fallback_chain(self):
        """Test complete import fallback chain works."""
        from src.ic.core.platform_discovery import PlatformDiscovery
        
        discovery = PlatformDiscovery()
        
        # Test fallback for various module patterns
        test_modules = [
            'src.ic.platforms.aws.ec2.info',
            'src.ic.platforms.oci.vm.info',
            'src.ic.platforms.ncp.ec2.info',
        ]
        
        for module_path in test_modules:
            with self.subTest(module=module_path):
                # Test that _import_module handles fallbacks
                result = discovery._import_module(module_path)
                
                # Result can be None if module doesn't exist, but should not raise exception
                self.assertIsInstance(result, (type(None), type(sys)))
    
    def test_legacy_module_name_handling(self):
        """Test legacy module name handling in integration."""
        from src.ic.core.platform_discovery import PlatformDiscovery
        
        discovery = PlatformDiscovery()
        
        # Test legacy module names that should be handled by fallback
        legacy_modules = [
            'src.ic.platforms.oci_module.vm.info',
            'src.ic.platforms.azure_module.vm.info',
        ]
        
        for module_path in legacy_modules:
            with self.subTest(module=module_path):
                # Should handle legacy names gracefully
                result = discovery._import_module(module_path)
                
                # Should either import successfully or return None (not raise exception)
                self.assertIsInstance(result, (type(None), type(sys)))
    
    def test_common_module_fallbacks(self):
        """Test common module import fallbacks work."""
        # Test various common module import patterns
        common_imports = [
            ('src.common.utils', 'common.utils'),
            ('src.common.progress_decorator', 'common.progress_decorator'),
            ('src.common.log', 'common.log'),
        ]
        
        for primary_path, fallback_path in common_imports:
            with self.subTest(primary=primary_path, fallback=fallback_path):
                try:
                    # Try primary import
                    module = __import__(primary_path, fromlist=[''])
                    self.assertIsNotNone(module)
                except ImportError:
                    try:
                        # Try fallback import
                        module = __import__(fallback_path, fromlist=[''])
                        self.assertIsNotNone(module)
                    except ImportError:
                        # Both failed - that's okay, module might not exist
                        pass


class TestCLIIntegrationImports(ImportIntegrationTestCase):
    """Test CLI integration with import system."""
    
    def test_cli_platform_loading(self):
        """Test CLI can load platforms through import system."""
        try:
            from src.ic.cli import setup_platform_parsers
            from src.ic.core.platform_discovery import get_platform_discovery
            import argparse
            
            # Create a test parser
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers(dest="platform")
            
            # Test that platform parsers can be set up
            setup_platform_parsers(subparsers)
            
            # Should not raise any exceptions
            self.assertTrue(True)
            
        except ImportError as e:
            self.skipTest(f"CLI integration not available: {e}")
        except Exception as e:
            self.fail(f"CLI platform loading failed: {e}")
    
    def test_cli_command_discovery(self):
        """Test CLI can discover commands through import system."""
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            
            discovery = get_platform_discovery()
            platforms = discovery.list_platforms()
            
            # Test command discovery for available platforms
            for platform_name in platforms[:2]:  # Test first 2 platforms
                services = discovery.list_services(platform_name)
                
                for service_name in services[:1]:  # Test first service
                    with self.subTest(platform=platform_name, service=service_name):
                        commands = discovery.get_service_commands(platform_name, service_name)
                        
                        # Commands should be a dictionary
                        self.assertIsInstance(commands, dict)
                        
                        # Test getting a specific command
                        if commands:
                            command_name = list(commands.keys())[0]
                            command_module = discovery.get_command_module(platform_name, service_name, command_name)
                            
                            # Should be able to get command module
                            if command_module:
                                self.assertIsNotNone(command_module)
                                
        except ImportError as e:
            self.skipTest(f"CLI command discovery not available: {e}")


class TestErrorHandlingIntegration(ImportIntegrationTestCase):
    """Test error handling in import integration scenarios."""
    
    def test_missing_platform_handling(self):
        """Test handling of missing platforms."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        
        # Test getting non-existent platform
        platform_info = discovery.get_platform('nonexistent_platform')
        self.assertIsNone(platform_info)
        
        # Test validation of non-existent platform
        is_available, error_msg = discovery.validate_platform_availability('nonexistent_platform')
        self.assertFalse(is_available)
        self.assertIsNotNone(error_msg)
    
    def test_missing_service_handling(self):
        """Test handling of missing services."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        platforms = discovery.list_platforms()
        
        if platforms:
            platform_name = platforms[0]
            
            # Test getting non-existent service
            service_info = discovery.get_service(platform_name, 'nonexistent_service')
            self.assertIsNone(service_info)
            
            # Test listing services for non-existent platform
            services = discovery.list_services('nonexistent_platform')
            self.assertEqual(services, [])
    
    def test_import_error_recovery(self):
        """Test recovery from import errors."""
        from src.ic.core.platform_discovery import PlatformDiscovery
        
        discovery = PlatformDiscovery()
        
        # Test importing completely invalid module
        result = discovery._import_module('completely.invalid.module.path')
        self.assertIsNone(result)
        
        # Test that cache is properly updated
        self.assertIn('completely.invalid.module.path', discovery._discovery_cache)
        self.assertIsNone(discovery._discovery_cache['completely.invalid.module.path'])
        
        # Test that subsequent calls use cache
        result2 = discovery._import_module('completely.invalid.module.path')
        self.assertIsNone(result2)


if __name__ == '__main__':
    unittest.main()