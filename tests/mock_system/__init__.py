"""
Mock System for Realistic Testing

Provides comprehensive mock data and integration testing capabilities with realistic
service behavior, error conditions, and clear indicators for mock vs real service usage.

Requirements: 7.4, 7.5 - Realistic mock data and integration testing

Components:
- RealisticMockProvider: Comprehensive mock data with realistic behavior
- IntegrationTestFramework: Integration testing with mock/real service support
- ServiceIndicator: Clear indicators for service type usage

Usage:
    # For unit tests with static mocks
    from tests.mock_system import create_unit_test_framework
    framework = create_unit_test_framework()
    
    # For integration tests with realistic mocks
    from tests.mock_system import create_integration_mock_framework
    framework = create_integration_mock_framework()
    
    # For integration tests with real services
    from tests.mock_system import create_integration_real_framework
    real_config = {'ncp': {'access_key': '...', 'secret_key': '...', 'region': 'KR'}}
    framework = create_integration_real_framework(real_config)
    
    # Execute service calls
    response = framework.execute_service_call('ncp', 'ec2', 'list_instances')
    
    # Run integration tests
    def test_ncp_ec2_integration(framework):
        response = framework.execute_service_call('ncp', 'ec2', 'list_instances')
        assert 'getServerInstanceListResponse' in response
    
    result = framework.run_integration_test('test_ncp_ec2', test_ncp_ec2_integration)
"""

from .realistic_mock_provider import (
    MockMode,
    ServiceStatus,
    MockConfiguration,
    MockMetrics,
    RealisticMockProvider,
    get_mock_provider,
    create_integration_test_provider,
    create_realistic_test_provider
)

from .integration_test_framework import (
    TestEnvironment,
    ServiceType,
    IntegrationTestConfig,
    ServiceInteraction,
    IntegrationTestResult,
    ServiceIndicator,
    IntegrationTestFramework,
    create_unit_test_framework,
    create_integration_mock_framework,
    create_integration_real_framework
)

__version__ = "1.0.0"

__all__ = [
    # Mock Provider
    'MockMode',
    'ServiceStatus', 
    'MockConfiguration',
    'MockMetrics',
    'RealisticMockProvider',
    'get_mock_provider',
    'create_integration_test_provider',
    'create_realistic_test_provider',
    
    # Integration Framework
    'TestEnvironment',
    'ServiceType',
    'IntegrationTestConfig',
    'ServiceInteraction', 
    'IntegrationTestResult',
    'ServiceIndicator',
    'IntegrationTestFramework',
    'create_unit_test_framework',
    'create_integration_mock_framework',
    'create_integration_real_framework'
]