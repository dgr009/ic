#!/usr/bin/env python3
"""
Configuration for GCP integration tests.

This module provides configuration management for integration tests
that run against real GCP APIs.
"""

import os
import json
from typing import Dict, List, Optional
from pathlib import Path


class IntegrationTestConfig:
    """Configuration manager for integration tests."""
    
    def __init__(self):
        """Initialize integration test configuration."""
        self.project_id = os.getenv('GCP_INTEGRATION_TEST_PROJECT')
        self.region = os.getenv('GCP_INTEGRATION_TEST_REGION', 'us-central1')
        self.zone = os.getenv('GCP_INTEGRATION_TEST_ZONE', 'us-central1-a')
        self.billing_account = os.getenv('GCP_INTEGRATION_TEST_BILLING_ACCOUNT')
        
        # Test execution settings
        self.enabled = os.getenv('RUN_GCP_INTEGRATION_TESTS', 'false').lower() == 'true'
        self.cleanup_resources = os.getenv('GCP_INTEGRATION_CLEANUP', 'true').lower() == 'true'
        self.max_test_duration = int(os.getenv('GCP_INTEGRATION_MAX_DURATION', '1800'))  # 30 minutes
        
        # Service-specific settings
        self.test_compute = os.getenv('GCP_TEST_COMPUTE', 'true').lower() == 'true'
        self.test_vpc = os.getenv('GCP_TEST_VPC', 'true').lower() == 'true'
        self.test_gke = os.getenv('GCP_TEST_GKE', 'true').lower() == 'true'
        self.test_sql = os.getenv('GCP_TEST_SQL', 'true').lower() == 'true'
        self.test_storage = os.getenv('GCP_TEST_STORAGE', 'true').lower() == 'true'
        self.test_functions = os.getenv('GCP_TEST_FUNCTIONS', 'true').lower() == 'true'
        self.test_run = os.getenv('GCP_TEST_RUN', 'true').lower() == 'true'
        
        # Performance test settings
        self.performance_thresholds = {
            'api_response_time': float(os.getenv('GCP_API_RESPONSE_THRESHOLD', '30.0')),
            'data_collection_time': float(os.getenv('GCP_DATA_COLLECTION_THRESHOLD', '60.0')),
            'parallel_speedup_min': float(os.getenv('GCP_PARALLEL_SPEEDUP_MIN', '1.2'))
        }
        
        # Load additional configuration from file if available
        self._load_config_file()
    
    def _load_config_file(self):
        """Load additional configuration from file."""
        config_file = Path(__file__).parent / 'integration_test_config.json'
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                
                # Override with file configuration
                for key, value in file_config.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
                        
            except Exception as e:
                print(f"Warning: Failed to load integration test config file: {e}")
    
    def is_configured(self) -> bool:
        """Check if integration tests are properly configured."""
        return (
            self.enabled and
            self.project_id is not None and
            len(self.project_id.strip()) > 0
        )
    
    def get_test_services(self) -> List[str]:
        """Get list of services to test."""
        services = []
        
        if self.test_compute:
            services.append('compute')
        if self.test_vpc:
            services.append('vpc')
        if self.test_gke:
            services.append('gke')
        if self.test_sql:
            services.append('sql')
        if self.test_storage:
            services.append('storage')
        if self.test_functions:
            services.append('functions')
        if self.test_run:
            services.append('run')
        
        return services
    
    def get_test_resources_config(self) -> Dict:
        """Get configuration for test resources that may be created."""
        return {
            'compute_instance': {
                'machine_type': 'e2-micro',
                'image_family': 'ubuntu-2004-lts',
                'image_project': 'ubuntu-os-cloud',
                'disk_size_gb': 10,
                'tags': ['integration-test'],
                'labels': {
                    'test-type': 'integration',
                    'created-by': 'gcp-integration-tests'
                }
            },
            'vpc_network': {
                'name_prefix': 'integration-test',
                'subnet_cidr': '10.10.0.0/24',
                'labels': {
                    'test-type': 'integration',
                    'created-by': 'gcp-integration-tests'
                }
            },
            'gke_cluster': {
                'name_prefix': 'integration-test',
                'node_count': 1,
                'machine_type': 'e2-micro',
                'disk_size_gb': 10,
                'labels': {
                    'test-type': 'integration',
                    'created-by': 'gcp-integration-tests'
                }
            },
            'sql_instance': {
                'name_prefix': 'integration-test',
                'tier': 'db-f1-micro',
                'database_version': 'POSTGRES_14',
                'labels': {
                    'test-type': 'integration',
                    'created-by': 'gcp-integration-tests'
                }
            },
            'storage_bucket': {
                'name_prefix': 'integration-test',
                'location': 'US',
                'storage_class': 'STANDARD',
                'labels': {
                    'test-type': 'integration',
                    'created-by': 'gcp-integration-tests'
                }
            }
        }
    
    def get_cleanup_config(self) -> Dict:
        """Get configuration for resource cleanup."""
        return {
            'enabled': self.cleanup_resources,
            'max_age_hours': 24,  # Clean up resources older than 24 hours
            'label_filters': {
                'test-type': 'integration',
                'created-by': 'gcp-integration-tests'
            },
            'force_cleanup': os.getenv('GCP_FORCE_CLEANUP', 'false').lower() == 'true'
        }
    
    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        if not self.enabled:
            issues.append("Integration tests are disabled")
        
        if not self.project_id:
            issues.append("GCP_INTEGRATION_TEST_PROJECT not set")
        
        if not self.region:
            issues.append("GCP_INTEGRATION_TEST_REGION not set")
        
        if not self.zone:
            issues.append("GCP_INTEGRATION_TEST_ZONE not set")
        
        # Validate zone is in region
        if self.region and self.zone and not self.zone.startswith(self.region):
            issues.append(f"Zone {self.zone} is not in region {self.region}")
        
        # Check if any services are enabled for testing
        if not any([self.test_compute, self.test_vpc, self.test_gke, 
                   self.test_sql, self.test_storage, self.test_functions, self.test_run]):
            issues.append("No services enabled for testing")
        
        return issues
    
    def print_configuration(self):
        """Print current configuration."""
        print("GCP Integration Test Configuration:")
        print(f"  Enabled: {self.enabled}")
        print(f"  Project ID: {self.project_id}")
        print(f"  Region: {self.region}")
        print(f"  Zone: {self.zone}")
        print(f"  Cleanup Resources: {self.cleanup_resources}")
        print(f"  Max Test Duration: {self.max_test_duration}s")
        
        print("\nServices to test:")
        for service in self.get_test_services():
            print(f"  - {service}")
        
        print("\nPerformance thresholds:")
        for metric, threshold in self.performance_thresholds.items():
            print(f"  {metric}: {threshold}")
        
        # Validate and show issues
        issues = self.validate_configuration()
        if issues:
            print("\nConfiguration issues:")
            for issue in issues:
                print(f"  ⚠️  {issue}")
        else:
            print("\n✅ Configuration is valid")


# Global configuration instance
integration_config = IntegrationTestConfig()


def create_sample_config_file():
    """Create a sample configuration file."""
    sample_config = {
        "project_id": "your-test-project-id",
        "region": "us-central1",
        "zone": "us-central1-a",
        "billing_account": "012345-678901-ABCDEF",
        "enabled": False,
        "cleanup_resources": True,
        "max_test_duration": 1800,
        "test_compute": True,
        "test_vpc": True,
        "test_gke": False,
        "test_sql": False,
        "test_storage": True,
        "test_functions": True,
        "test_run": True,
        "performance_thresholds": {
            "api_response_time": 30.0,
            "data_collection_time": 60.0,
            "parallel_speedup_min": 1.2
        }
    }
    
    config_file = Path(__file__).parent / 'integration_test_config.json.sample'
    
    with open(config_file, 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    print(f"Sample configuration file created: {config_file}")
    print("Copy this to integration_test_config.json and customize for your environment")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='GCP Integration Test Configuration')
    parser.add_argument('--show', action='store_true', help='Show current configuration')
    parser.add_argument('--validate', action='store_true', help='Validate configuration')
    parser.add_argument('--create-sample', action='store_true', help='Create sample config file')
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_config_file()
    elif args.validate:
        issues = integration_config.validate_configuration()
        if issues:
            print("Configuration issues found:")
            for issue in issues:
                print(f"  ❌ {issue}")
            exit(1)
        else:
            print("✅ Configuration is valid")
    else:
        integration_config.print_configuration()