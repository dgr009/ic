#!/usr/bin/env python3
"""
Realistic Mock Data Provider System

Provides comprehensive mock data that accurately represents real NCP/NCPGOV service
responses with realistic edge cases, error conditions, and integration testing support.

Requirements: 7.4, 7.5 - Realistic mock data and integration testing
"""

import os
import json
import time
import random
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import threading
from collections import defaultdict


class MockMode(Enum):
    """Mock operation modes."""
    STATIC = "static"           # Return static predefined responses
    DYNAMIC = "dynamic"         # Generate dynamic responses with variations
    REALISTIC = "realistic"     # Include realistic delays and error conditions
    INTEGRATION = "integration" # Support integration testing scenarios


class ServiceStatus(Enum):
    """Service status for mock responses."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    MAINTENANCE = "maintenance"


@dataclass
class MockConfiguration:
    """Configuration for mock data provider."""
    mode: MockMode = MockMode.REALISTIC
    service_status: ServiceStatus = ServiceStatus.HEALTHY
    error_rate: float = 0.05  # 5% error rate
    latency_min: float = 0.1  # Minimum response time in seconds
    latency_max: float = 2.0  # Maximum response time in seconds
    enable_rate_limiting: bool = True
    rate_limit_requests: int = 100  # Requests per minute
    enable_authentication: bool = True
    enable_logging: bool = True
    data_variation: bool = True  # Enable data variations
    include_edge_cases: bool = True


@dataclass
class MockMetrics:
    """Metrics for mock service usage."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency: float = 0.0
    error_types: Dict[str, int] = field(default_factory=dict)
    request_history: List[Dict[str, Any]] = field(default_factory=list)


class RealisticMockProvider:
    """Provides realistic mock data with comprehensive testing support."""
    
    def __init__(self, config: Optional[MockConfiguration] = None):
        self.config = config or MockConfiguration()
        self.metrics = MockMetrics()
        self.request_counts = defaultdict(int)
        self.last_reset_time = time.time()
        self.lock = threading.Lock()
        
        # Load base mock data
        self.base_data = self._load_base_mock_data()
        
        # Initialize service states
        self.service_states = {
            'ncp': {
                'ec2': {'status': 'running', 'instances': 3, 'last_update': time.time()},
                's3': {'status': 'running', 'buckets': 5, 'last_update': time.time()},
                'vpc': {'status': 'running', 'vpcs': 2, 'last_update': time.time()},
                'sg': {'status': 'running', 'groups': 4, 'last_update': time.time()},
                'rds': {'status': 'running', 'instances': 2, 'last_update': time.time()}
            },
            'ncpgov': {
                'ec2': {'status': 'running', 'instances': 3, 'last_update': time.time()},
                's3': {'status': 'running', 'buckets': 3, 'last_update': time.time()},
                'vpc': {'status': 'running', 'vpcs': 2, 'last_update': time.time()},
                'sg': {'status': 'running', 'groups': 4, 'last_update': time.time()},
                'rds': {'status': 'running', 'instances': 2, 'last_update': time.time()}
            }
        }
    
    def _load_base_mock_data(self) -> Dict[str, Any]:
        """Load base mock data from existing providers."""
        try:
            # Import existing mock data providers
            from tests.ci.mock_data.ncp_mock_data import NCPMockDataProvider
            from tests.ci.mock_data.ncpgov_mock_data import NCPGovMockDataProvider
            
            ncp_provider = NCPMockDataProvider()
            ncpgov_provider = NCPGovMockDataProvider()
            
            return {
                'ncp': {
                    'ec2': ncp_provider.get_server_instance_list_response(),
                    'vpc': ncp_provider.get_vpc_list_response(),
                    's3': ncp_provider.get_storage_instance_list_response(),
                    'sg': ncp_provider.get_access_control_group_list_response(),
                    'rds': ncp_provider.get_cloud_db_instance_list_response()
                },
                'ncpgov': {
                    'ec2': ncpgov_provider.get_server_instance_list_response(),
                    'vpc': ncpgov_provider.get_vpc_list_response(),
                    's3': ncpgov_provider.get_storage_instance_list_response(),
                    'sg': ncpgov_provider.get_access_control_group_list_response(),
                    'rds': ncpgov_provider.get_cloud_db_instance_list_response()
                }
            }
        except ImportError:
            # Fallback to minimal mock data
            return self._create_minimal_mock_data()
    
    def _create_minimal_mock_data(self) -> Dict[str, Any]:
        """Create minimal mock data as fallback."""
        return {
            'ncp': {
                'ec2': {'getServerInstanceListResponse': {'totalRows': 0, 'serverInstanceList': []}},
                'vpc': {'getVpcListResponse': {'totalRows': 0, 'vpcList': []}},
                's3': {'getStorageInstanceListResponse': {'totalRows': 0, 'storageInstanceList': []}},
                'sg': {'getAccessControlGroupListResponse': {'totalRows': 0, 'accessControlGroupList': []}},
                'rds': {'getCloudDBInstanceListResponse': {'totalRows': 0, 'cloudDBInstanceList': []}}
            },
            'ncpgov': {
                'ec2': {'getServerInstanceListResponse': {'totalRows': 0, 'serverInstanceList': []}},
                'vpc': {'getVpcListResponse': {'totalRows': 0, 'vpcList': []}},
                's3': {'getStorageInstanceListResponse': {'totalRows': 0, 'storageInstanceList': []}},
                'sg': {'getAccessControlGroupListResponse': {'totalRows': 0, 'accessControlGroupList': []}},
                'rds': {'getCloudDBInstanceListResponse': {'totalRows': 0, 'cloudDBInstanceList': []}}
            }
        }
    
    def get_mock_response(self, platform: str, service: str, operation: str, 
                         params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get mock response with realistic behavior.
        
        Args:
            platform: Platform name (ncp, ncpgov)
            service: Service name (ec2, s3, vpc, sg, rds)
            operation: Operation name (list, get, create, etc.)
            params: Optional parameters for the operation
            
        Returns:
            Mock response data
        """
        with self.lock:
            self.metrics.total_requests += 1
            request_start = time.time()
            
            # Record request
            request_info = {
                'timestamp': request_start,
                'platform': platform,
                'service': service,
                'operation': operation,
                'params': params or {}
            }
            
            try:
                # Check rate limiting
                if self.config.enable_rate_limiting:
                    self._check_rate_limit(platform, service)
                
                # Check authentication
                if self.config.enable_authentication:
                    self._check_authentication(params)
                
                # Simulate realistic latency
                if self.config.mode in [MockMode.REALISTIC, MockMode.INTEGRATION]:
                    self._simulate_latency()
                
                # Check for service errors
                if self._should_return_error():
                    return self._generate_error_response(platform, service, operation)
                
                # Get base response
                response = self._get_base_response(platform, service, operation)
                
                # Apply variations if enabled
                if self.config.data_variation:
                    response = self._apply_data_variations(response, platform, service)
                
                # Add realistic metadata
                response = self._add_realistic_metadata(response, request_info)
                
                # Record successful request
                self.metrics.successful_requests += 1
                request_info['status'] = 'success'
                request_info['duration'] = time.time() - request_start
                
                return response
                
            except Exception as e:
                # Record failed request
                self.metrics.failed_requests += 1
                error_type = type(e).__name__
                self.metrics.error_types[error_type] = self.metrics.error_types.get(error_type, 0) + 1
                
                request_info['status'] = 'error'
                request_info['error'] = str(e)
                request_info['duration'] = time.time() - request_start
                
                return self._generate_error_response(platform, service, operation, str(e))
            
            finally:
                self.metrics.request_history.append(request_info)
                
                # Update average latency
                total_duration = sum(r.get('duration', 0) for r in self.metrics.request_history[-100:])
                self.metrics.average_latency = total_duration / min(len(self.metrics.request_history), 100)
    
    def _check_rate_limit(self, platform: str, service: str):
        """Check rate limiting constraints."""
        current_time = time.time()
        
        # Reset counters every minute
        if current_time - self.last_reset_time > 60:
            self.request_counts.clear()
            self.last_reset_time = current_time
        
        # Check rate limit
        key = f"{platform}:{service}"
        self.request_counts[key] += 1
        
        if self.request_counts[key] > self.config.rate_limit_requests:
            raise Exception(f"Rate limit exceeded for {platform}/{service}")
    
    def _check_authentication(self, params: Optional[Dict[str, Any]]):
        """Check authentication requirements."""
        if not params or 'access_key' not in params:
            if random.random() < 0.1:  # 10% chance of auth error
                raise Exception("Authentication required: Missing access_key")
    
    def _simulate_latency(self):
        """Simulate realistic network latency."""
        latency = random.uniform(self.config.latency_min, self.config.latency_max)
        
        # Add occasional high latency spikes
        if random.random() < 0.05:  # 5% chance of high latency
            latency *= random.uniform(2, 5)
        
        time.sleep(latency)
    
    def _should_return_error(self) -> bool:
        """Determine if an error should be returned."""
        if self.config.service_status == ServiceStatus.UNAVAILABLE:
            return True
        elif self.config.service_status == ServiceStatus.DEGRADED:
            return random.random() < (self.config.error_rate * 2)
        elif self.config.service_status == ServiceStatus.MAINTENANCE:
            return random.random() < 0.5
        else:
            return random.random() < self.config.error_rate
    
    def _get_base_response(self, platform: str, service: str, operation: str) -> Dict[str, Any]:
        """Get base response from mock data."""
        try:
            service_data = self.base_data.get(platform, {}).get(service, {})
            
            # Map operations to response keys
            operation_mapping = {
                'list_instances': 'getServerInstanceListResponse',
                'list_vpcs': 'getVpcListResponse',
                'list_storage': 'getStorageInstanceListResponse',
                'list_security_groups': 'getAccessControlGroupListResponse',
                'list_databases': 'getCloudDBInstanceListResponse'
            }
            
            # Try to find matching response
            for key, response in service_data.items():
                if operation in key.lower() or key in operation_mapping.values():
                    return response.copy()
            
            # Return first available response as fallback
            if service_data:
                return list(service_data.values())[0].copy()
            
            # Generate empty response
            return self._generate_empty_response(platform, service, operation)
            
        except Exception:
            return self._generate_empty_response(platform, service, operation)
    
    def _generate_empty_response(self, platform: str, service: str, operation: str) -> Dict[str, Any]:
        """Generate empty response for unknown operations."""
        return {
            f"get{service.title()}ListResponse": {
                "requestId": f"mock-{platform}-{service}-{int(time.time())}",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 0,
                f"{service}List": []
            }
        }
    
    def _apply_data_variations(self, response: Dict[str, Any], platform: str, service: str) -> Dict[str, Any]:
        """Apply realistic data variations to responses."""
        if not self.config.data_variation:
            return response
        
        # Update timestamps to current time
        current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")
        self._update_timestamps(response, current_time)
        
        # Vary instance counts slightly
        self._vary_instance_counts(response, platform, service)
        
        # Add realistic status variations
        self._add_status_variations(response, service)
        
        # Update service state
        self._update_service_state(platform, service, response)
        
        return response
    
    def _update_timestamps(self, data: Any, current_time: str):
        """Recursively update timestamps in response data."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['createDate', 'uptime', 'lastModified', 'timestamp']:
                    # Vary timestamps slightly
                    base_time = datetime.now()
                    variation = timedelta(minutes=random.randint(-60, 0))
                    data[key] = (base_time + variation).strftime("%Y-%m-%dT%H:%M:%S+0900")
                else:
                    self._update_timestamps(value, current_time)
        elif isinstance(data, list):
            for item in data:
                self._update_timestamps(item, current_time)
    
    def _vary_instance_counts(self, response: Dict[str, Any], platform: str, service: str):
        """Add realistic variations to instance counts."""
        # Find list keys in response
        for key, value in response.items():
            if isinstance(value, dict) and 'totalRows' in value:
                # Vary total count slightly
                current_count = value.get('totalRows', 0)
                if current_count > 0:
                    variation = random.randint(-1, 2)  # -1 to +2 variation
                    new_count = max(0, current_count + variation)
                    value['totalRows'] = new_count
                    
                    # Adjust list length if needed
                    list_keys = [k for k in value.keys() if k.endswith('List')]
                    for list_key in list_keys:
                        if isinstance(value[list_key], list):
                            current_list = value[list_key]
                            if len(current_list) != new_count:
                                if new_count > len(current_list):
                                    # Duplicate some items
                                    while len(current_list) < new_count:
                                        if current_list:
                                            item = current_list[0].copy()
                                            # Modify some identifiers
                                            self._modify_item_identifiers(item)
                                            current_list.append(item)
                                elif new_count < len(current_list):
                                    # Remove some items
                                    value[list_key] = current_list[:new_count]
    
    def _modify_item_identifiers(self, item: Dict[str, Any]):
        """Modify identifiers in duplicated items."""
        for key, value in item.items():
            if key.endswith('No') or key.endswith('Id'):
                if isinstance(value, str) and value.isdigit():
                    item[key] = str(int(value) + random.randint(1000, 9999))
            elif key.endswith('Name'):
                if isinstance(value, str):
                    item[key] = f"{value}-{random.randint(10, 99)}"
    
    def _add_status_variations(self, response: Dict[str, Any], service: str):
        """Add realistic status variations to response items."""
        def update_status(data):
            if isinstance(data, dict):
                # Update instance status occasionally
                if 'Status' in str(data.keys()) and random.random() < 0.1:
                    status_keys = [k for k in data.keys() if 'Status' in k]
                    for status_key in status_keys:
                        if isinstance(data[status_key], dict) and 'code' in data[status_key]:
                            # Occasionally show different statuses
                            if random.random() < 0.05:
                                if service == 'ec2':
                                    data[status_key]['code'] = random.choice(['RUN', 'STOP', 'INIT'])
                                elif service == 'rds':
                                    data[status_key]['code'] = random.choice(['RUN', 'STOP', 'BACKUP'])
                
                for value in data.values():
                    update_status(value)
            elif isinstance(data, list):
                for item in data:
                    update_status(item)
        
        update_status(response)
    
    def _update_service_state(self, platform: str, service: str, response: Dict[str, Any]):
        """Update internal service state based on response."""
        if platform in self.service_states and service in self.service_states[platform]:
            state = self.service_states[platform][service]
            state['last_update'] = time.time()
            
            # Extract instance count from response
            for key, value in response.items():
                if isinstance(value, dict) and 'totalRows' in value:
                    state['instances'] = value['totalRows']
                    break
    
    def _add_realistic_metadata(self, response: Dict[str, Any], request_info: Dict[str, Any]) -> Dict[str, Any]:
        """Add realistic metadata to responses."""
        # Add request ID if not present
        for key, value in response.items():
            if isinstance(value, dict) and 'requestId' not in value:
                value['requestId'] = f"mock-{request_info['platform']}-{int(time.time())}-{random.randint(1000, 9999)}"
        
        return response
    
    def _generate_error_response(self, platform: str, service: str, operation: str, 
                                error_msg: Optional[str] = None) -> Dict[str, Any]:
        """Generate realistic error responses."""
        error_types = [
            ("AUTH_ERROR", "Authentication failed", "401"),
            ("RATE_LIMIT", "Rate limit exceeded", "429"),
            ("SERVICE_UNAVAILABLE", "Service temporarily unavailable", "503"),
            ("INVALID_PARAMETER", "Invalid parameter provided", "400"),
            ("RESOURCE_NOT_FOUND", "Requested resource not found", "404"),
            ("INTERNAL_ERROR", "Internal server error", "500")
        ]
        
        if self.config.service_status == ServiceStatus.UNAVAILABLE:
            error_code, error_message, http_code = error_types[2]  # Service unavailable
        elif self.config.service_status == ServiceStatus.MAINTENANCE:
            error_code, error_message, http_code = ("MAINTENANCE", "Service under maintenance", "503")
        else:
            error_code, error_message, http_code = random.choice(error_types)
        
        if error_msg:
            error_message = error_msg
        
        return {
            f"get{service.title()}ListResponse": {
                "requestId": f"mock-error-{platform}-{service}-{int(time.time())}",
                "returnCode": http_code,
                "returnMessage": error_message,
                "errorCode": error_code,
                "errorMessage": error_message
            }
        }
    
    def get_service_health(self, platform: str, service: str) -> Dict[str, Any]:
        """Get service health information."""
        if platform not in self.service_states or service not in self.service_states[platform]:
            return {"status": "unknown", "message": "Service not found"}
        
        state = self.service_states[platform][service]
        last_update = state['last_update']
        current_time = time.time()
        
        # Determine health based on last update time
        if current_time - last_update > 300:  # 5 minutes
            health_status = "stale"
        elif self.config.service_status == ServiceStatus.HEALTHY:
            health_status = "healthy"
        else:
            health_status = self.config.service_status.value
        
        return {
            "status": health_status,
            "instances": state.get('instances', 0),
            "last_update": datetime.fromtimestamp(last_update).isoformat(),
            "uptime": current_time - last_update,
            "message": f"Service {service} on {platform} is {health_status}"
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get mock service metrics."""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": (self.metrics.successful_requests / max(self.metrics.total_requests, 1)) * 100,
            "average_latency": self.metrics.average_latency,
            "error_types": dict(self.metrics.error_types),
            "request_rate": len([r for r in self.metrics.request_history 
                               if time.time() - r['timestamp'] < 60]),  # Requests per minute
            "service_status": self.config.service_status.value,
            "configuration": {
                "mode": self.config.mode.value,
                "error_rate": self.config.error_rate,
                "latency_range": f"{self.config.latency_min}-{self.config.latency_max}s",
                "rate_limiting": self.config.enable_rate_limiting
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics."""
        with self.lock:
            self.metrics = MockMetrics()
            self.request_counts.clear()
            self.last_reset_time = time.time()
    
    def set_service_status(self, status: ServiceStatus):
        """Set global service status."""
        self.config.service_status = status
    
    def set_error_rate(self, error_rate: float):
        """Set error rate (0.0 to 1.0)."""
        self.config.error_rate = max(0.0, min(1.0, error_rate))
    
    def enable_integration_mode(self):
        """Enable integration testing mode with predictable responses."""
        self.config.mode = MockMode.INTEGRATION
        self.config.data_variation = False
        self.config.error_rate = 0.0
        self.config.latency_min = 0.01
        self.config.latency_max = 0.05


# Global mock provider instance
_mock_provider = None


def get_mock_provider(config: Optional[MockConfiguration] = None) -> RealisticMockProvider:
    """Get global mock provider instance."""
    global _mock_provider
    if _mock_provider is None or config is not None:
        _mock_provider = RealisticMockProvider(config)
    return _mock_provider


def create_integration_test_provider() -> RealisticMockProvider:
    """Create a mock provider optimized for integration testing."""
    config = MockConfiguration(
        mode=MockMode.INTEGRATION,
        service_status=ServiceStatus.HEALTHY,
        error_rate=0.0,
        latency_min=0.01,
        latency_max=0.05,
        enable_rate_limiting=False,
        data_variation=False,
        include_edge_cases=False
    )
    return RealisticMockProvider(config)


def create_realistic_test_provider() -> RealisticMockProvider:
    """Create a mock provider with realistic behavior for testing."""
    config = MockConfiguration(
        mode=MockMode.REALISTIC,
        service_status=ServiceStatus.HEALTHY,
        error_rate=0.05,
        latency_min=0.1,
        latency_max=1.0,
        enable_rate_limiting=True,
        data_variation=True,
        include_edge_cases=True
    )
    return RealisticMockProvider(config)


# Export main classes and functions
__all__ = [
    'MockMode', 'ServiceStatus', 'MockConfiguration', 'MockMetrics',
    'RealisticMockProvider', 'get_mock_provider', 'create_integration_test_provider',
    'create_realistic_test_provider'
]