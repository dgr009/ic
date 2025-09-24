"""
CI Testing Module

This module provides utilities and configurations for running tests in CI environments.
"""

from .environment import (
    CIEnvironmentDetector,
    MockConfigurationManager,
    FallbackConfigurationProvider,
    CITestEnvironmentSetup,
    setup_ci_test_environment,
    cleanup_ci_test_environment,
    is_ci_environment,
    get_ci_info
)

__all__ = [
    'CIEnvironmentDetector',
    'MockConfigurationManager', 
    'FallbackConfigurationProvider',
    'CITestEnvironmentSetup',
    'setup_ci_test_environment',
    'cleanup_ci_test_environment',
    'is_ci_environment',
    'get_ci_info'
]