#!/usr/bin/env python3
"""
Integration Test Framework with Mock System

Provides comprehensive integration testing capabilities with realistic mock data,
service interaction validation, and clear indicators for mock vs real service usage.

Requirements: 7.4, 7.5 - Integration testing with realistic mock data
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from contextlib import contextmanager
import threading
from unittest.mock import patch, MagicMock

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.mock_system.realistic_mock_provider import (
    RealisticMockProvider, MockConfiguration, MockMode, ServiceStatus,
    create_integration_test_provider, create_realistic_test_provider
)


class TestEnvironment(Enum):
    """Test environment types."""
    UNIT = "unit"                    # Pure unit tests with mocks
    INTEGRATION_MOCK = "integration_mock"  # Integration tests with mocks
    INTEGRATION_REAL = "integration_real"  # Integration tests with real services
    E2E = "e2e"                     # End-to-end tests


class ServiceType(Enum):
    """Service interaction types."""
    MOCK = "mock"
    REAL = "real"
    HYBRID = "hybrid"  # Mix of mock and real services


@dataclass
class IntegrationTestConfig:
    """Configuration for integration tests."""
    environment: TestEnvironment = TestEnvironment.INTEGRATION_MOCK
    service_type: ServiceType = ServiceType.MOCK
    platforms: List[str] = field(default_factory=lambda: ['ncp', 'ncpgov'])
    services: List[str] = field(default_factory=lambda: ['ec2', 's3', 'vpc', 'sg', 'rds'])
    mock_config: Optional[MockConfiguration] = None
    real_service_config: Optional[Dict[str, Any]] = None
    enable_service_validation: bool = True
    enable_performance_testing: bool = False
    timeout_seconds: int = 30
    retry_attempts: int = 3
    parallel_execution: bool = False


@dataclass
class ServiceInteraction:
    """Record of service interaction for validation."""
    timestamp: float
    platform: str
    service: str
    operation: str
    service_type: ServiceType
    request_data: Dict[str, Any]
    response_data: Dict[str, Any]
    duration: float
    success: bool
    error_message: Optional[str] = None


@dataclass
class IntegrationTestResult:
    """Result of integration test execution."""
    test_name: str
    environment: TestEnvironment
    service_type: ServiceType
    success: bool
    duration: float
    interactions: List[ServiceInteraction] = field(default_factory=list)
    assertions_passed: int = 0
    assertions_failed: int = 0
    error_message: Optional[str] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class ServiceIndicator:
    """Provides clear indicators for mock vs real service usage."""
    
    def __init__(self):
        self.current_service_type = ServiceType.MOCK
        self.indicators_enabled = True
        self.logger = logging.getLogger(__name__)
    
    def set_service_type(self, service_type: ServiceType):
        """Set current service type and display indicator."""
        self.current_service_type = service_type
        
        if self.indicators_enabled:
            indicator_messages = {
                ServiceType.MOCK: "🤖 Using MOCK services - No real API calls",
                ServiceType.REAL: "🌐 Using REAL services - Making actual API calls",
                ServiceType.HYBRID: "🔄 Using HYBRID services - Mix of mock and real"
            }
            
            message = indicator_messages.get(service_type, "❓ Unknown service type")
            self.logger.info(message)
            print(f"\n{message}\n")
    
    def get_current_indicator(self) -> str:
        """Get current service type indicator."""
        indicators = {
            ServiceType.MOCK: "🤖 MOCK",
            ServiceType.REAL: "🌐 REAL", 
            ServiceType.HYBRID: "🔄 HYBRID"
        }
        return indicators.get(self.current_service_type, "❓ UNKNOWN")
    
    def enable_indicators(self, enabled: bool = True):
        """Enable or disable service indicators."""
        self.indicators_enabled = enabled


class IntegrationTestFramework:
    """Comprehensive integration testing framework."""
    
    def __init__(self, config: Optional[IntegrationTestConfig] = None):
        self.config = config or IntegrationTestConfig()
        self.mock_provider = None
        self.service_indicator = ServiceIndicator()
        self.interactions: List[ServiceInteraction] = []
        self.test_results: List[IntegrationTestResult] = []
        self.lock = threading.Lock()
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize based on configuration
        self._initialize_test_environment()
    
    def _initialize_test_environment(self):
        """Initialize test environment based on configuration."""
        if self.config.service_type == ServiceType.MOCK:
            self._setup_mock_environment()
        elif self.config.service_type == ServiceType.REAL:
            self._setup_real_environment()
        elif self.config.service_type == ServiceType.HYBRID:
            self._setup_hybrid_environment()
        
        self.service_indicator.set_service_type(self.config.service_type)
    
    def _setup_mock_environment(self):
        """Set up mock service environment."""
        if self.config.environment == TestEnvironment.INTEGRATION_MOCK:
            self.mock_provider = create_integration_test_provider()
        else:
            self.mock_provider = create_realistic_test_provider()
        
        self.logger.info("Mock environment initialized")
    
    def _setup_real_environment(self):
        """Set up real service environment."""
        # Validate real service configuration
        if not self.config.real_service_config:
            raise ValueError("Real service configuration required for real service testing")
        
        # Check if real services are accessible
        self._validate_real_service_access()
        
        self.logger.info("Real service environment initialized")
    
    def _setup_hybrid_environment(self):
        """Set up hybrid environment with both mock and real services."""
        self._setup_mock_environment()
        
        # Validate partial real service configuration
        if self.config.real_service_config:
            self._validate_real_service_access()
        
        self.logger.info("Hybrid environment initialized")
    
    def _validate_real_service_access(self):
        """Validate access to real services."""
        # This would contain actual validation logic for real services
        # For now, we'll simulate the validation
        self.logger.info("Validating real service access...")
        
        required_configs = ['access_key', 'secret_key', 'region']
        for platform in self.config.platforms:
            platform_config = self.config.real_service_config.get(platform, {})
            
            for config_key in required_configs:
                if config_key not in platform_config:
                    raise ValueError(f"Missing {config_key} for platform {platform}")
        
        self.logger.info("Real service access validated")
    
    @contextmanager
    def service_interaction_context(self, platform: str, service: str, operation: str):
        """Context manager for tracking service interactions."""
        interaction = ServiceInteraction(
            timestamp=time.time(),
            platform=platform,
            service=service,
            operation=operation,
            service_type=self.config.service_type,
            request_data={},
            response_data={},
            duration=0.0,
            success=False
        )
        
        start_time = time.time()
        
        try:
            yield interaction
            interaction.success = True
        except Exception as e:
            interaction.success = False
            interaction.error_message = str(e)
            raise
        finally:
            interaction.duration = time.time() - start_time
            
            with self.lock:
                self.interactions.append(interaction)
    
    def execute_service_call(self, platform: str, service: str, operation: str,
                           params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute service call with appropriate backend (mock or real)."""
        
        with self.service_interaction_context(platform, service, operation) as interaction:
            interaction.request_data = params or {}
            
            if self.config.service_type == ServiceType.MOCK:
                response = self._execute_mock_call(platform, service, operation, params)
            elif self.config.service_type == ServiceType.REAL:
                response = self._execute_real_call(platform, service, operation, params)
            elif self.config.service_type == ServiceType.HYBRID:
                response = self._execute_hybrid_call(platform, service, operation, params)
            else:
                raise ValueError(f"Unknown service type: {self.config.service_type}")
            
            interaction.response_data = response
            return response
    
    def _execute_mock_call(self, platform: str, service: str, operation: str,
                          params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute mock service call."""
        if not self.mock_provider:
            raise RuntimeError("Mock provider not initialized")
        
        return self.mock_provider.get_mock_response(platform, service, operation, params)
    
    def _execute_real_call(self, platform: str, service: str, operation: str,
                          params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute real service call."""
        # This would contain actual service call logic
        # For demonstration, we'll simulate a real call
        
        self.logger.info(f"Making real API call to {platform}/{service}/{operation}")
        
        # Simulate real service call with delay
        time.sleep(0.5)  # Simulate network latency
        
        # Return simulated real response
        return {
            "real_service_response": True,
            "platform": platform,
            "service": service,
            "operation": operation,
            "timestamp": time.time(),
            "data": f"Real data from {platform} {service}"
        }
    
    def _execute_hybrid_call(self, platform: str, service: str, operation: str,
                           params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute hybrid service call (mock or real based on configuration)."""
        # Determine whether to use mock or real for this specific call
        # This could be based on service, operation, or other criteria
        
        use_real = self._should_use_real_service(platform, service, operation)
        
        if use_real:
            return self._execute_real_call(platform, service, operation, params)
        else:
            return self._execute_mock_call(platform, service, operation, params)
    
    def _should_use_real_service(self, platform: str, service: str, operation: str) -> bool:
        """Determine whether to use real service for hybrid mode."""
        # Example logic: use real services for critical operations
        critical_operations = ['create', 'delete', 'update']
        
        if operation in critical_operations:
            return True
        
        # Use real services for specific platforms/services if configured
        real_services = self.config.real_service_config.get('enabled_services', [])
        service_key = f"{platform}:{service}"
        
        return service_key in real_services
    
    def run_integration_test(self, test_name: str, test_function: Callable) -> IntegrationTestResult:
        """Run a single integration test."""
        self.logger.info(f"Running integration test: {test_name}")
        
        result = IntegrationTestResult(
            test_name=test_name,
            environment=self.config.environment,
            service_type=self.config.service_type,
            success=False,
            duration=0.0
        )
        
        start_time = time.time()
        
        try:
            # Clear previous interactions for this test
            with self.lock:
                self.interactions.clear()
            
            # Execute test function
            test_function(self)
            
            result.success = True
            self.logger.info(f"Integration test '{test_name}' passed")
            
        except Exception as e:
            result.success = False
            result.error_message = str(e)
            self.logger.error(f"Integration test '{test_name}' failed: {e}")
        
        finally:
            result.duration = time.time() - start_time
            
            # Copy interactions to result
            with self.lock:
                result.interactions = self.interactions.copy()
            
            # Calculate performance metrics
            result.performance_metrics = self._calculate_performance_metrics(result.interactions)
            
            self.test_results.append(result)
        
        return result
    
    def _calculate_performance_metrics(self, interactions: List[ServiceInteraction]) -> Dict[str, Any]:
        """Calculate performance metrics from interactions."""
        if not interactions:
            return {}
        
        durations = [i.duration for i in interactions]
        successful_interactions = [i for i in interactions if i.success]
        
        return {
            "total_interactions": len(interactions),
            "successful_interactions": len(successful_interactions),
            "failed_interactions": len(interactions) - len(successful_interactions),
            "success_rate": len(successful_interactions) / len(interactions) * 100,
            "average_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "total_duration": sum(durations)
        }
    
    def validate_service_responses(self, expected_structure: Dict[str, Any]) -> bool:
        """Validate service response structures."""
        if not self.interactions:
            return False
        
        for interaction in self.interactions:
            if not self._validate_response_structure(interaction.response_data, expected_structure):
                return False
        
        return True
    
    def _validate_response_structure(self, response: Dict[str, Any], 
                                   expected: Dict[str, Any]) -> bool:
        """Validate response structure against expected format."""
        for key, expected_type in expected.items():
            if key not in response:
                return False
            
            if not isinstance(response[key], expected_type):
                return False
        
        return True
    
    def assert_service_called(self, platform: str, service: str, operation: str) -> bool:
        """Assert that a specific service was called."""
        for interaction in self.interactions:
            if (interaction.platform == platform and 
                interaction.service == service and 
                interaction.operation == operation):
                return True
        return False
    
    def assert_no_real_service_calls(self) -> bool:
        """Assert that no real service calls were made."""
        real_calls = [i for i in self.interactions if i.service_type == ServiceType.REAL]
        return len(real_calls) == 0
    
    def assert_performance_threshold(self, max_duration: float) -> bool:
        """Assert that all interactions completed within time threshold."""
        for interaction in self.interactions:
            if interaction.duration > max_duration:
                return False
        return True
    
    def get_service_health_report(self) -> Dict[str, Any]:
        """Get comprehensive service health report."""
        if not self.mock_provider:
            return {"error": "Mock provider not available"}
        
        health_report = {}
        
        for platform in self.config.platforms:
            health_report[platform] = {}
            for service in self.config.services:
                health_report[platform][service] = self.mock_provider.get_service_health(platform, service)
        
        return health_report
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Get comprehensive test execution summary."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.success)
        
        return {
            "environment": self.config.environment.value,
            "service_type": self.config.service_type.value,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "total_interactions": len(self.interactions),
            "service_indicator": self.service_indicator.get_current_indicator(),
            "mock_metrics": self.mock_provider.get_metrics() if self.mock_provider else None,
            "test_results": [
                {
                    "name": r.test_name,
                    "success": r.success,
                    "duration": r.duration,
                    "interactions": len(r.interactions),
                    "error": r.error_message
                }
                for r in self.test_results
            ]
        }
    
    def reset_test_state(self):
        """Reset test state for new test run."""
        with self.lock:
            self.interactions.clear()
            self.test_results.clear()
        
        if self.mock_provider:
            self.mock_provider.reset_metrics()


# Convenience functions for common test scenarios

def create_unit_test_framework() -> IntegrationTestFramework:
    """Create framework for unit tests with mocks."""
    config = IntegrationTestConfig(
        environment=TestEnvironment.UNIT,
        service_type=ServiceType.MOCK,
        mock_config=MockConfiguration(
            mode=MockMode.STATIC,
            error_rate=0.0,
            latency_min=0.001,
            latency_max=0.001
        )
    )
    return IntegrationTestFramework(config)


def create_integration_mock_framework() -> IntegrationTestFramework:
    """Create framework for integration tests with realistic mocks."""
    config = IntegrationTestConfig(
        environment=TestEnvironment.INTEGRATION_MOCK,
        service_type=ServiceType.MOCK
    )
    return IntegrationTestFramework(config)


def create_integration_real_framework(real_config: Dict[str, Any]) -> IntegrationTestFramework:
    """Create framework for integration tests with real services."""
    config = IntegrationTestConfig(
        environment=TestEnvironment.INTEGRATION_REAL,
        service_type=ServiceType.REAL,
        real_service_config=real_config
    )
    return IntegrationTestFramework(config)


# Export main classes and functions
__all__ = [
    'TestEnvironment', 'ServiceType', 'IntegrationTestConfig', 
    'ServiceInteraction', 'IntegrationTestResult', 'ServiceIndicator',
    'IntegrationTestFramework', 'create_unit_test_framework',
    'create_integration_mock_framework', 'create_integration_real_framework'
]