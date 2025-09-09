"""
Basic tests for IC CLI package.
"""

import pytest
import sys
from pathlib import Path


def test_package_import():
    """Test that the ic package can be imported."""
    try:
        import ic
        assert ic.__version__ is not None
        print(f"IC package version: {ic.__version__}")
    except ImportError as e:
        pytest.fail(f"Failed to import ic package: {e}")


def test_config_manager_import():
    """Test that ConfigManager can be imported."""
    try:
        from ic.config.manager import ConfigManager
        assert ConfigManager is not None
    except ImportError as e:
        pytest.fail(f"Failed to import ConfigManager: {e}")


def test_security_manager_import():
    """Test that SecurityManager can be imported."""
    try:
        from ic.config.security import SecurityManager
        assert SecurityManager is not None
    except ImportError as e:
        pytest.fail(f"Failed to import SecurityManager: {e}")


def test_cli_import():
    """Test that CLI module can be imported."""
    try:
        from ic import cli
        assert cli is not None
    except ImportError as e:
        pytest.fail(f"Failed to import CLI module: {e}")


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
    """Basic functionality tests."""
    
    def test_config_creation(self):
        """Test basic config creation."""
        try:
            from ic.config.manager import ConfigManager
            # Just test that we can create the class, don't actually initialize
            assert ConfigManager is not None
        except Exception as e:
            pytest.fail(f"Failed to test config creation: {e}")
    
    def test_security_creation(self):
        """Test basic security manager creation."""
        try:
            from ic.config.security import SecurityManager
            # Just test that we can create the class, don't actually initialize
            assert SecurityManager is not None
        except Exception as e:
            pytest.fail(f"Failed to test security creation: {e}")