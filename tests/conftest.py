"""
Pytest configuration and fixtures for IC CLI tests.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager for testing."""
    with patch('ic.config.manager.ConfigManager') as mock:
        yield mock


@pytest.fixture
def mock_security_manager():
    """Mock SecurityManager for testing."""
    with patch('ic.config.security.SecurityManager') as mock:
        yield mock


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create example config files
    (config_dir / "default.yaml").write_text("""
version: "1.0"
aws:
  regions: ["us-east-1"]
""")
    
    (config_dir / "secrets.yaml").write_text("""
aws:
  accounts: ["123456789012"]
""")
    
    return config_dir


@pytest.fixture
def mock_environment():
    """Mock environment variables for testing."""
    env_vars = {
        'AWS_PROFILE': 'test-profile',
        'AWS_REGION': 'us-east-1',
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars