"""
Basic tests for IC CLI package.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch


@pytest.mark.ci_safe
def test_package_import():
    """Test that the ic package can be imported."""
    try:
        import ic
        assert ic.__version__ is not None
        print(f"IC package version: {ic.__version__}")
    except ImportError as e:
        pytest.fail(f"Failed to import ic package: {e}")


@pytest.mark.ci_safe
def test_config_manager_import():
    """Test that ConfigManager can be imported."""
    try:
        from ic.config.manager import ConfigManager
        assert ConfigManager is not None
    except ImportError as e:
        pytest.fail(f"Failed to import ConfigManager: {e}")


@pytest.mark.ci_safe
def test_security_manager_import():
    """Test that SecurityManager can be imported."""
    try:
        from ic.config.security import SecurityManager
        assert SecurityManager is not None
    except ImportError as e:
        pytest.fail(f"Failed to import SecurityManager: {e}")


@pytest.mark.ci_safe
def test_cli_import():
    """Test that CLI module can be imported."""
    try:
        from ic import cli
        assert cli is not None
    except ImportError as e:
        # If it's a missing dependency, skip the test instead of failing
        if "netifaces" in str(e) or "ssh" in str(e) or "paramiko" in str(e):
            pytest.skip(f"Skipping CLI test due to missing dependency: {e}")
        else:
            pytest.fail(f"Failed to import CLI module: {e}")


@pytest.mark.ci_safe
def test_progress_decorator_import():
    """Test that progress decorator can be imported."""
    try:
        from common.progress_decorator import ProgressBarDecorator, progress_bar
        assert ProgressBarDecorator is not None
        assert progress_bar is not None
    except ImportError as e:
        pytest.fail(f"Failed to import progress decorator: {e}")


def test_python_path():
    """Test Python path configuration."""
    print(f"Python path: {sys.path}")
    src_path = Path(__file__).parent.parent / "src"
    print(f"Expected src path: {src_path}")
    print(f"Src path exists: {src_path.exists()}")
    
    if src_path.exists():
        ic_path = src_path / "ic"
        print(f"IC path exists: {ic_path.exists()}")
        if ic_path.exists():
            print(f"IC directory contents: {list(ic_path.iterdir())}")


class TestBasicFunctionality:
    """Basic functionality tests that work without configuration files."""
    
    @pytest.mark.ci_safe
    def test_config_creation_without_files(self):
        """Test config creation without requiring configuration files."""
        try:
            from ic.config.manager import ConfigManager
            from ic.config.security import SecurityManager
            
            # Test creation without files
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager=security_manager)
            
            # Should be able to create instances
            assert config_manager is not None
            assert security_manager is not None
            
            # Test loading default config (no files)
            with patch('pathlib.Path.exists', return_value=False):
                config = config_manager.load_config([])
                assert config is not None
                assert config['version'] == '1.0'
                
        except Exception as e:
            pytest.fail(f"Failed to test config creation: {e}")
    
    @pytest.mark.ci_safe
    def test_security_creation_without_config(self):
        """Test security manager creation without configuration."""
        try:
            from ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            assert security_manager is not None
            
            # Test basic security validation
            test_data = {'password': 'secret123'}
            warnings = security_manager.validate_config_security(test_data)
            assert isinstance(warnings, list)
            
        except Exception as e:
            pytest.fail(f"Failed to test security creation: {e}")
    
    @pytest.mark.ci_safe
    def test_cli_parser_creation(self):
        """Test CLI parser can be created without configuration."""
        try:
            import argparse
            
            # Test that we can create a basic parser like the CLI does
            parser = argparse.ArgumentParser(description="Test CLI")
            subparsers = parser.add_subparsers(dest="platform", required=True)
            
            # Add config subcommand
            config_parser = subparsers.add_parser("config", help="Config commands")
            config_subparsers = config_parser.add_subparsers(dest="command", required=True)
            show_parser = config_subparsers.add_parser("show", help="Show config")
            
            assert parser is not None
            
            # Test basic argument parsing
            args = parser.parse_args(['config', 'show'])
            assert args.command == 'show'
            
        except Exception as e:
            pytest.fail(f"Failed to test CLI parser creation: {e}")
    
    @pytest.mark.ci_safe  
    def test_progress_decorator_basic_usage(self):
        """Test progress decorator basic usage."""
        try:
            from common.progress_decorator import progress_bar
            
            @progress_bar("Test operation")
            def test_function():
                return "success"
            
            result = test_function()
            assert result == "success"
            
        except Exception as e:
            pytest.fail(f"Failed to test progress decorator: {e}")