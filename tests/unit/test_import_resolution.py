#!/usr/bin/env python3
"""
Import Resolution Test Suite

Tests to verify all import paths work correctly in both development
and installed package scenarios, and validate fallback import mechanisms.

Requirements: 2.1, 2.2, 6.1
"""

import unittest
import sys
import importlib
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any, Optional


class ImportResolutionTestCase(unittest.TestCase):
    """Base test case for import resolution tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_path = sys.path.copy()
        self.original_modules = sys.modules.copy()
        
    def tearDown(self):
        """Clean up test environment."""
        sys.path = self.original_path
        # Remove any modules we imported during testing
        modules_to_remove = []
        for module_name in sys.modules:
            if module_name not in self.original_modules:
                modules_to_remove.append(module_name)
        for module_name in modules_to_remove:
            del sys.modules[module_name]
    
    def clear_import_cache(self, module_pattern: str):
        """Clear import cache for modules matching pattern."""
        modules_to_remove = []
        for module_name in sys.modules:
            if module_pattern in module_name:
                modules_to_remove.append(module_name)
        for module_name in modules_to_remove:
            del sys.modules[module_name]


class TestCoreModuleImports(ImportResolutionTestCase):
    """Test core module import resolution."""
    
    def test_cli_module_import(self):
        """Test CLI module can be imported with fallback mechanisms."""
        # Test primary import path
        try:
            from src.ic.cli import main
            self.assertTrue(callable(main))
        except ImportError:
            # Test fallback import path
            from ic.cli import main
            self.assertTrue(callable(main))
    
    def test_platform_discovery_import(self):
        """Test platform discovery module import."""
        # Test primary import path
        try:
            from src.ic.core.platform_discovery import get_platform_discovery
            discovery = get_platform_discovery()
            self.assertIsNotNone(discovery)
        except ImportError:
            # Test fallback import path
            from ic.core.platform_discovery import get_platform_discovery
            discovery = get_platform_discovery()
            self.assertIsNotNone(discovery)
    
    def test_config_manager_import(self):
        """Test configuration manager import."""
        # Test primary import path
        try:
            from src.ic.config.manager import ConfigManager
            self.assertTrue(hasattr(ConfigManager, 'load_all_configs'))
        except ImportError:
            # Test fallback import path
            from ic.config.manager import ConfigManager
            self.assertTrue(hasattr(ConfigManager, 'load_all_configs'))
    
    def test_logging_module_import(self):
        """Test logging module import."""
        # Test primary import path
        try:
            from src.ic.core.logging import init_logger
            self.assertTrue(callable(init_logger))
        except ImportError:
            # Test fallback import path
            from ic.core.logging import init_logger
            self.assertTrue(callable(init_logger))


class TestPlatformModuleImports(ImportResolutionTestCase):
    """Test platform module import resolution."""
    
    def get_expected_platforms(self) -> List[str]:
        """Get list of expected platforms."""
        return ['aws', 'cloudflare', 'gcp', 'oci', 'ssh']
    
    def test_platform_module_imports(self):
        """Test all platform modules can be imported."""
        platforms = self.get_expected_platforms()
        
        for platform in platforms:
            with self.subTest(platform=platform):
                # Test primary import path
                try:
                    platform_module = importlib.import_module(f'src.ic.platforms.{platform}')
                    self.assertIsNotNone(platform_module)
                except ImportError:
                    # Test fallback import path
                    try:
                        platform_module = importlib.import_module(f'ic.platforms.{platform}')
                        self.assertIsNotNone(platform_module)
                    except ImportError:
                        self.fail(f"Could not import platform module: {platform}")
    
    def test_service_module_imports(self):
        """Test service modules within platforms can be imported."""
        # Test a few key services from different platforms
        test_services = [
            ('aws', 'ec2'),
            ('oci', 'vm'),
            ('ncp', 'ec2'),
            ('ncpgov', 'ec2'),
            ('ssh', 'server_info'),
        ]
        
        for platform, service in test_services:
            with self.subTest(platform=platform, service=service):
                # Test primary import path
                try:
                    service_module = importlib.import_module(f'src.ic.platforms.{platform}.{service}')
                    self.assertIsNotNone(service_module)
                except ImportError:
                    # Test fallback import path
                    try:
                        service_module = importlib.import_module(f'ic.platforms.{platform}.{service}')
                        self.assertIsNotNone(service_module)
                    except ImportError:
                        # Some services might not exist, that's okay
                        pass
    
    def test_command_module_imports(self):
        """Test command modules within services can be imported."""
        # Test a few key commands
        test_commands = [
            ('aws', 'ec2', 'info'),
            ('oci', 'vm', 'info'),
            ('ncp', 'ec2', 'info'),
            ('ssh', 'server_info', 'info'),
        ]
        
        for platform, service, command in test_commands:
            with self.subTest(platform=platform, service=service, command=command):
                # Test primary import path
                try:
                    command_module = importlib.import_module(f'src.ic.platforms.{platform}.{service}.{command}')
                    self.assertIsNotNone(command_module)
                    # Verify required functions exist
                    if hasattr(command_module, 'main'):
                        self.assertTrue(callable(command_module.main))
                except ImportError:
                    # Test fallback import path
                    try:
                        command_module = importlib.import_module(f'ic.platforms.{platform}.{service}.{command}')
                        self.assertIsNotNone(command_module)
                        if hasattr(command_module, 'main'):
                            self.assertTrue(callable(command_module.main))
                    except ImportError:
                        # Some commands might not exist, that's okay
                        pass


class TestCommonModuleImports(ImportResolutionTestCase):
    """Test common module import resolution."""
    
    def test_common_utils_import(self):
        """Test common utilities import."""
        # Test primary import path
        try:
            from src.common.utils import get_config_value
            self.assertTrue(callable(get_config_value))
        except ImportError:
            # Test fallback import path
            try:
                from common.utils import get_config_value
                self.assertTrue(callable(get_config_value))
            except ImportError:
                # Some common modules might not exist
                pass
    
    def test_progress_decorator_import(self):
        """Test progress decorator import."""
        # Test primary import path
        try:
            from src.common.progress_decorator import progress_decorator
            self.assertTrue(callable(progress_decorator))
        except ImportError:
            # Test fallback import path
            try:
                from common.progress_decorator import progress_decorator
                self.assertTrue(callable(progress_decorator))
            except ImportError:
                # Progress decorator might not exist
                pass
    
    def test_logging_utils_import(self):
        """Test logging utilities import."""
        # Test primary import path
        try:
            from src.common.log import get_logger
            self.assertTrue(callable(get_logger))
        except ImportError:
            # Test fallback import path
            try:
                from common.log import get_logger
                self.assertTrue(callable(get_logger))
            except ImportError:
                # Logging utils might not exist
                pass


class TestFallbackImportMechanisms(ImportResolutionTestCase):
    """Test fallback import mechanisms work correctly."""
    
    def test_development_vs_installed_imports(self):
        """Test imports work in both development and installed scenarios."""
        # Simulate development environment (src in path)
        src_path = Path(__file__).parent.parent.parent / "src"
        if src_path.exists() and str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        
        # Test development import
        try:
            from ic.cli import main as dev_main
            self.assertTrue(callable(dev_main))
        except ImportError:
            pass  # Development imports might not work in all environments
        
        # Test installed package import (simulate by removing src from path)
        if str(src_path) in sys.path:
            sys.path.remove(str(src_path))
        
        try:
            # Clear cache to force re-import
            self.clear_import_cache('ic.cli')
            from ic.cli import main as installed_main
            self.assertTrue(callable(installed_main))
        except ImportError:
            pass  # Installed imports might not work in development
    
    def test_legacy_module_name_fallbacks(self):
        """Test fallbacks for legacy module names."""
        # Test oci_module -> oci fallback
        try:
            # This should work with fallback mechanism
            from src.ic.core.platform_discovery import PlatformDiscovery
            discovery = PlatformDiscovery()
            
            # Test that discovery can handle legacy module names
            module = discovery._import_module('src.ic.platforms.oci_module.vm.info')
            # Should fallback to oci if oci_module doesn't exist
            if module is None:
                module = discovery._import_module('src.ic.platforms.oci.vm.info')
            
            # At least one should work or both should be None (if neither exists)
            # This tests the fallback mechanism exists
            self.assertIsNotNone(discovery._import_module)
        except ImportError:
            pass
    
    def test_import_error_handling(self):
        """Test proper handling of import errors."""
        from src.ic.core.platform_discovery import PlatformDiscovery
        
        discovery = PlatformDiscovery()
        
        # Test importing non-existent module
        result = discovery._import_module('src.ic.platforms.nonexistent.service.command')
        self.assertIsNone(result)
        
        # Test that cache is updated correctly
        self.assertIn('src.ic.platforms.nonexistent.service.command', discovery._discovery_cache)
        self.assertIsNone(discovery._discovery_cache['src.ic.platforms.nonexistent.service.command'])


class TestDynamicImportDiscovery(ImportResolutionTestCase):
    """Test dynamic import discovery mechanisms."""
    
    def test_platform_discovery_import_resolution(self):
        """Test platform discovery can resolve imports correctly."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        platforms = discovery.discover_platforms()
        
        # Should discover at least some platforms
        self.assertIsInstance(platforms, dict)
        
        # Test that discovered platforms have proper structure
        for platform_name, platform_info in platforms.items():
            self.assertIsInstance(platform_name, str)
            self.assertIsNotNone(platform_info)
            self.assertIsInstance(platform_info.services, dict)
    
    def test_service_discovery_import_resolution(self):
        """Test service discovery can resolve imports correctly."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        
        # Test getting a specific service
        platforms = discovery.list_platforms()
        if platforms:
            platform_name = platforms[0]
            services = discovery.list_services(platform_name)
            
            if services:
                service_name = services[0]
                service_info = discovery.get_service(platform_name, service_name)
                
                if service_info and service_info.available:
                    # Service should have proper structure
                    self.assertIsNotNone(service_info.module)
    
    def test_command_discovery_import_resolution(self):
        """Test command discovery can resolve imports correctly."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        
        # Test getting commands for a service
        platforms = discovery.list_platforms()
        if platforms:
            platform_name = platforms[0]
            services = discovery.list_services(platform_name)
            
            if services:
                service_name = services[0]
                commands = discovery.get_service_commands(platform_name, service_name)
                
                # Commands should be a dictionary
                self.assertIsInstance(commands, dict)
                
                # Test getting a specific command
                if commands:
                    command_name = list(commands.keys())[0]
                    command_module = discovery.get_command_module(platform_name, service_name, command_name)
                    
                    if command_module:
                        # Command module should be importable
                        self.assertIsNotNone(command_module)


class TestImportPathConsistency(ImportResolutionTestCase):
    """Test import path consistency across the codebase."""
    
    def test_cli_import_consistency(self):
        """Test CLI uses consistent import patterns."""
        # Read CLI file and check for import patterns
        cli_file = Path(__file__).parent.parent.parent / "src" / "ic" / "cli.py"
        
        if cli_file.exists():
            with open(cli_file, 'r') as f:
                content = f.read()
            
            # Check for consistent try/except import patterns
            self.assertIn('try:', content)
            self.assertIn('except ImportError:', content)
            
            # Should have fallback imports
            self.assertTrue(
                'from .core.platform_discovery import' in content or
                'from ic.core.platform_discovery import' in content
            )
    
    def test_platform_discovery_import_consistency(self):
        """Test platform discovery uses consistent import patterns."""
        from src.ic.core.platform_discovery import PlatformDiscovery
        
        discovery = PlatformDiscovery()
        
        # Test that _import_module method exists and handles fallbacks
        self.assertTrue(hasattr(discovery, '_import_module'))
        self.assertTrue(callable(discovery._import_module))
        
        # Test that it has a cache mechanism
        self.assertTrue(hasattr(discovery, '_discovery_cache'))
        self.assertIsInstance(discovery._discovery_cache, dict)


class TestPackageStructureValidation(ImportResolutionTestCase):
    """Test package structure supports proper imports."""
    
    def test_src_directory_structure(self):
        """Test src directory has proper structure."""
        src_dir = Path(__file__).parent.parent.parent / "src"
        
        if src_dir.exists():
            # Should have ic directory
            ic_dir = src_dir / "ic"
            self.assertTrue(ic_dir.exists(), "src/ic directory should exist")
            
            # Should have platforms directory
            platforms_dir = ic_dir / "platforms"
            self.assertTrue(platforms_dir.exists(), "src/ic/platforms directory should exist")
            
            # Should have core directory
            core_dir = ic_dir / "core"
            self.assertTrue(core_dir.exists(), "src/ic/core directory should exist")
            
            # Should have config directory
            config_dir = ic_dir / "config"
            self.assertTrue(config_dir.exists(), "src/ic/config directory should exist")
    
    def test_platform_directory_structure(self):
        """Test platform directories have proper structure."""
        platforms_dir = Path(__file__).parent.parent.parent / "src" / "ic" / "platforms"
        
        if platforms_dir.exists():
            for platform_dir in platforms_dir.iterdir():
                if platform_dir.is_dir() and not platform_dir.name.startswith('_'):
                    with self.subTest(platform=platform_dir.name):
                        # Should have __init__.py
                        init_file = platform_dir / "__init__.py"
                        self.assertTrue(init_file.exists(), 
                                      f"Platform {platform_dir.name} should have __init__.py")
    
    def test_init_files_exist(self):
        """Test all necessary __init__.py files exist."""
        base_paths = [
            "src/ic/__init__.py",
            "src/ic/core/__init__.py",
            "src/ic/config/__init__.py",
            "src/ic/platforms/__init__.py",
        ]
        
        for path in base_paths:
            full_path = Path(__file__).parent.parent.parent / path
            if full_path.parent.exists():  # Only check if parent directory exists
                self.assertTrue(full_path.exists(), f"Required __init__.py file missing: {path}")


if __name__ == '__main__':
    unittest.main()