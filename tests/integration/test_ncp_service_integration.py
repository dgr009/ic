#!/usr/bin/env python3
"""
NCP Service Integration Tests

Demonstrates integration testing with realistic mock data and service validation.
Shows clear indicators for mock vs real service usage.

Requirements: 7.4, 7.5 - Integration testing with realistic mock data
"""

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.mock_system import (
    create_integration_mock_framework,
    create_unit_test_framework,
    TestEnvironment,
    ServiceType
)


class TestNCPServiceIntegration:
    """Integration tests for NCP services."""
    
    def setup_method(self):
        """Set up test framework for each test."""
        self.framework = create_integration_mock_framework()
    
    def test_ncp_ec2_list_instances_integration(self):
        """Test NCP EC2 instance listing with integration framework."""
        
        def integration_test(framework):
            # Execute service call
            response = framework.execute_service_call('ncp', 'ec2', 'list_instances')
            
            # Validate response structure
            assert 'getServerInstanceListResponse' in response
            assert 'totalRows' in response['getServerInstanceListResponse']
            assert 'serverInstanceList' in response['getServerInstanceListResponse']
            
            # Validate response data
            server_list = response['getServerInstanceListResponse']['serverInstanceList']
            if server_list:  # If instances exist
                instance = server_list[0]
                assert 'serverInstanceNo' in instance
                assert 'serverName' in instance
                assert 'serverInstanceStatus' in instance
            
            # Validate service was called correctly
            assert framework.assert_service_called('ncp', 'ec2', 'list_instances')
            
            # Validate no real service calls were made
            assert framework.assert_no_real_service_calls()
        
        # Run the integration test
        result = self.framework.run_integration_test(
            'test_ncp_ec2_list_instances', 
            integration_test
        )
        
        # Validate test result
        assert result.success
        assert result.service_type == ServiceType.MOCK
        assert len(result.interactions) > 0
        
        # Check performance
        assert result.duration < 5.0  # Should complete within 5 seconds
        assert self.framework.assert_performance_threshold(2.0)  # Each call < 2 seconds
    
    def test_ncp_vpc_list_integration(self):
        """Test NCP VPC listing with validation."""
        
        def integration_test(framework):
            response = framework.execute_service_call('ncp', 'vpc', 'list_vpcs')
            
            # Validate VPC response structure
            assert 'getVpcListResponse' in response
            vpc_response = response['getVpcListResponse']
            assert 'totalRows' in vpc_response
            assert 'vpcList' in vpc_response
            
            # Validate VPC data if present
            vpc_list = vpc_response['vpcList']
            if vpc_list:
                vpc = vpc_list[0]
                assert 'vpcNo' in vpc
                assert 'vpcName' in vpc
                assert 'ipv4CidrBlock' in vpc
                assert 'vpcStatus' in vpc
        
        result = self.framework.run_integration_test(
            'test_ncp_vpc_list',
            integration_test
        )
        
        assert result.success
        assert len(result.interactions) == 1
        assert result.interactions[0].platform == 'ncp'
        assert result.interactions[0].service == 'vpc'
    
    def test_ncp_s3_storage_integration(self):
        """Test NCP S3 storage listing with mock validation."""
        
        def integration_test(framework):
            response = framework.execute_service_call('ncp', 's3', 'list_storage')
            
            # Validate storage response
            assert 'getStorageInstanceListResponse' in response
            storage_response = response['getStorageInstanceListResponse']
            assert 'totalRows' in storage_response
            assert 'storageInstanceList' in storage_response
            
            # Validate storage instance data
            storage_list = storage_response['storageInstanceList']
            if storage_list:
                storage = storage_list[0]
                assert 'storageInstanceNo' in storage
                assert 'storageInstanceName' in storage
                assert 'storageSize' in storage
        
        result = self.framework.run_integration_test(
            'test_ncp_s3_storage',
            integration_test
        )
        
        assert result.success
    
    def test_ncp_security_groups_integration(self):
        """Test NCP security groups with comprehensive validation."""
        
        def integration_test(framework):
            # Test security group listing
            sg_response = framework.execute_service_call('ncp', 'sg', 'list_security_groups')
            
            assert 'getAccessControlGroupListResponse' in sg_response
            sg_list_response = sg_response['getAccessControlGroupListResponse']
            assert 'accessControlGroupList' in sg_list_response
            
            # Test security group rules if groups exist
            sg_list = sg_list_response['accessControlGroupList']
            if sg_list:
                # Test rules for first security group
                rules_response = framework.execute_service_call('ncp', 'sg', 'list_rules')
                
                if 'getAccessControlGroupRuleListResponse' in rules_response:
                    rules_list_response = rules_response['getAccessControlGroupRuleListResponse']
                    assert 'accessControlGroupRuleList' in rules_list_response
        
        result = self.framework.run_integration_test(
            'test_ncp_security_groups',
            integration_test
        )
        
        assert result.success
        # Should have at least one interaction (security groups list)
        assert len(result.interactions) >= 1
    
    def test_ncp_rds_database_integration(self):
        """Test NCP RDS database listing with validation."""
        
        def integration_test(framework):
            response = framework.execute_service_call('ncp', 'rds', 'list_databases')
            
            # Validate RDS response
            assert 'getCloudDBInstanceListResponse' in response
            rds_response = response['getCloudDBInstanceListResponse']
            assert 'totalRows' in rds_response
            assert 'cloudDBInstanceList' in rds_response
            
            # Validate database instance data
            db_list = rds_response['cloudDBInstanceList']
            if db_list:
                db_instance = db_list[0]
                assert 'cloudDBInstanceNo' in db_instance
                assert 'cloudDBServiceName' in db_instance
                assert 'engineVersion' in db_instance
        
        result = self.framework.run_integration_test(
            'test_ncp_rds_database',
            integration_test
        )
        
        assert result.success
    
    def test_multiple_service_calls_integration(self):
        """Test multiple service calls in sequence."""
        
        def integration_test(framework):
            # Call multiple services
            ec2_response = framework.execute_service_call('ncp', 'ec2', 'list_instances')
            vpc_response = framework.execute_service_call('ncp', 'vpc', 'list_vpcs')
            s3_response = framework.execute_service_call('ncp', 's3', 'list_storage')
            
            # Validate all responses
            assert 'getServerInstanceListResponse' in ec2_response
            assert 'getVpcListResponse' in vpc_response
            assert 'getStorageInstanceListResponse' in s3_response
            
            # Validate all services were called
            assert framework.assert_service_called('ncp', 'ec2', 'list_instances')
            assert framework.assert_service_called('ncp', 'vpc', 'list_vpcs')
            assert framework.assert_service_called('ncp', 's3', 'list_storage')
        
        result = self.framework.run_integration_test(
            'test_multiple_service_calls',
            integration_test
        )
        
        assert result.success
        assert len(result.interactions) == 3
        
        # Validate performance metrics
        metrics = result.performance_metrics
        assert metrics['total_interactions'] == 3
        assert metrics['successful_interactions'] == 3
        assert metrics['success_rate'] == 100.0
    
    def test_service_health_monitoring(self):
        """Test service health monitoring capabilities."""
        # Get service health report
        health_report = self.framework.get_service_health_report()
        
        assert 'ncp' in health_report
        assert 'ec2' in health_report['ncp']
        assert 'vpc' in health_report['ncp']
        assert 's3' in health_report['ncp']
        
        # Validate health status structure
        ec2_health = health_report['ncp']['ec2']
        assert 'status' in ec2_health
        assert 'instances' in ec2_health
        assert 'last_update' in ec2_health
    
    def test_mock_service_indicators(self):
        """Test that mock service indicators are working."""
        # Verify service type indicator
        indicator = self.framework.service_indicator.get_current_indicator()
        assert "🤖 MOCK" in indicator
        
        # Verify service type is mock
        assert self.framework.config.service_type == ServiceType.MOCK
        
        # Execute a service call and verify it's marked as mock
        def integration_test(framework):
            framework.execute_service_call('ncp', 'ec2', 'list_instances')
        
        result = self.framework.run_integration_test(
            'test_mock_indicators',
            integration_test
        )
        
        assert result.success
        assert result.service_type == ServiceType.MOCK
        assert result.interactions[0].service_type == ServiceType.MOCK


class TestNCPGovServiceIntegration:
    """Integration tests for NCPGOV services."""
    
    def setup_method(self):
        """Set up test framework for NCPGOV tests."""
        self.framework = create_integration_mock_framework()
    
    def test_ncpgov_ec2_integration(self):
        """Test NCPGOV EC2 service integration."""
        
        def integration_test(framework):
            response = framework.execute_service_call('ncpgov', 'ec2', 'list_instances')
            
            # Validate NCPGOV response structure
            assert 'getServerInstanceListResponse' in response
            server_response = response['getServerInstanceListResponse']
            assert 'serverInstanceList' in server_response
            
            # Validate government-specific features if present
            server_list = server_response['serverInstanceList']
            if server_list:
                instance = server_list[0]
                # NCPGOV instances should have enhanced security features
                assert 'serverInstanceNo' in instance
                assert 'serverName' in instance
        
        result = self.framework.run_integration_test(
            'test_ncpgov_ec2',
            integration_test
        )
        
        assert result.success
        assert result.interactions[0].platform == 'ncpgov'
    
    def test_ncpgov_security_enhanced_integration(self):
        """Test NCPGOV enhanced security features."""
        
        def integration_test(framework):
            # Test security groups with government requirements
            sg_response = framework.execute_service_call('ncpgov', 'sg', 'list_security_groups')
            
            assert 'getAccessControlGroupListResponse' in sg_response
            sg_response_data = sg_response['getAccessControlGroupListResponse']
            assert 'accessControlGroupList' in sg_response_data
            
            # Test VPC with government compliance
            vpc_response = framework.execute_service_call('ncpgov', 'vpc', 'list_vpcs')
            assert 'getVpcListResponse' in vpc_response
        
        result = self.framework.run_integration_test(
            'test_ncpgov_security',
            integration_test
        )
        
        assert result.success
        assert len(result.interactions) == 2


class TestCrossServiceIntegration:
    """Cross-service integration tests."""
    
    def setup_method(self):
        """Set up framework for cross-service tests."""
        self.framework = create_integration_mock_framework()
    
    def test_ncp_and_ncpgov_comparison(self):
        """Test comparing NCP and NCPGOV service responses."""
        
        def integration_test(framework):
            # Get responses from both platforms
            ncp_response = framework.execute_service_call('ncp', 'ec2', 'list_instances')
            ncpgov_response = framework.execute_service_call('ncpgov', 'ec2', 'list_instances')
            
            # Both should have similar structure
            assert 'getServerInstanceListResponse' in ncp_response
            assert 'getServerInstanceListResponse' in ncpgov_response
            
            # Validate both platforms were called
            assert framework.assert_service_called('ncp', 'ec2', 'list_instances')
            assert framework.assert_service_called('ncpgov', 'ec2', 'list_instances')
        
        result = self.framework.run_integration_test(
            'test_cross_platform_comparison',
            integration_test
        )
        
        assert result.success
        assert len(result.interactions) == 2
        
        # Verify different platforms were called
        platforms = {interaction.platform for interaction in result.interactions}
        assert 'ncp' in platforms
        assert 'ncpgov' in platforms


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])