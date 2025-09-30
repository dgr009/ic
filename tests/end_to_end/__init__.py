"""
End-to-End Functionality Tests

This package contains comprehensive end-to-end tests that validate complete
command workflows, multi-platform functionality, and authentication systems.

Test Categories:
- Complete Workflows: Full command execution from start to finish
- Multi-Platform Integration: Cross-platform operations and consistency
- Authentication Systems: Credential loading, validation, and security

Requirements: 5.1-5.5
"""

__version__ = "1.0.0"
__author__ = "IC CLI Development Team"

# Test suite organization
TEST_CATEGORIES = {
    'workflows': 'Complete command workflow tests',
    'integration': 'Multi-platform integration tests',
    'authentication': 'Authentication and security tests'
}

# Test execution order (for comprehensive validation)
TEST_EXECUTION_ORDER = [
    'test_complete_workflows',
    'test_multi_platform_integration', 
    'test_authentication_systems'
]