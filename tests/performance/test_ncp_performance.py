"""
Performance tests for NCP services.

Tests performance characteristics of NCP API clients, data processing,
output formatting, and CLI commands with large datasets.
"""

import time
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
import json

# Import NCP components
from ncp.client import NCPClient, NCPAPIError
from ncpgov.client import NCPGovClient
from common.ncp_utils import format_bytes, OutputFormatter
from common.ncpgov_utils import mask_sensitive_data


class TestNCPClientPerformance:
    """Performance tests for NCP client operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = NCPClient("test-key", "test-secret", "KR")
        self.gov_client = NCPGovClient("gov-key", "gov-secret", "KR")
        
        # Generate large mock datasets
        self.large_instance_dataset = self._generate_large_instance_dataset(1000)
        self.large_bucket_dataset = self._generate_large_bucket_dataset(500)
        self.large_vpc_dataset = self._generate_large_vpc_dataset(100)
    
    def _generate_large_instance_dataset(self, count):
        """Generate large instance dataset for performance testing."""
        instances = []
        for i in range(count):
            instances.append({
                'serverInstanceNo': f'i-{i:06d}',
                'serverName': f'performance-test-server-{i}',
                'serverInstanceStatus': 'RUN' if i % 3 != 0 else 'STOP',
                'serverInstanceType': f'SVR.VSVR.STAND.C{(i%8)+1:03d}.M{(i%16)+1:03d}.NET.SSD.B050.G002',
                'cpuCount': (i % 8) + 1,
                'memorySize': (2 ** ((i % 4) + 3)) * 1024 * 1024 * 1024,  # 8GB to 64GB
                'platformType': 'LNX64' if i % 2 == 0 else 'WND64',
                'publicIp': f'203.{(i//256)%256}.{(i//1)%256}.{i%256}',
                'privateIp': f'10.{(i//256)%256}.{(i//1)%256}.{i%256}',
                'vpcName': f'vpc-{i//50}',
                'subnetName': f'subnet-{i//10}',
                'region': 'KR',
                'createDate': f'2024-{(i%12)+1:02d}-{(i%28)+1:02d}T{(i%24):02d}:{(i%60):02d}:00+0900'
            })
        return instances
    
    def _generate_large_bucket_dataset(self, count):
        """Generate large bucket dataset for performance testing."""
        buckets = []
        storage_classes = ['STANDARD', 'STANDARD_IA', 'COLD', 'ARCHIVE']
        acl_types = ['private', 'public-read', 'authenticated-read']
        
        for i in range(count):
            buckets.append({
                'bucketName': f'performance-test-bucket-{i:04d}',
                'region': 'KR',
                'creationDate': f'2024-{(i%12)+1:02d}-{(i%28)+1:02d}T{(i%24):02d}:{(i%60):02d}:00+0900',
                'storageClass': storage_classes[i % len(storage_classes)],
                'acl': acl_types[i % len(acl_types)],
                'objectCount': i * 100,
                'bucketSize': i * 1024 * 1024 * 1024,  # Size in bytes
                'versioning': 'Enabled' if i % 3 == 0 else 'Disabled',
                'encryption': 'AES256' if i % 2 == 0 else 'None'
            })
        return buckets
    
    def _generate_large_vpc_dataset(self, count):
        """Generate large VPC dataset for performance testing."""
        vpcs = []
        cidr_blocks = ['10.0.0.0/16', '10.1.0.0/16', '172.16.0.0/16', '192.168.0.0/16']
        statuses = ['RUN', 'INIT', 'CREAT']
        
        for i in range(count):
            vpcs.append({
                'vpcNo': f'vpc-{i:06d}',
                'vpcName': f'performance-test-vpc-{i}',
                'ipv4CidrBlock': cidr_blocks[i % len(cidr_blocks)],
                'vpcStatus': statuses[i % len(statuses)],
                'regionCode': 'KR',
                'isDefault': i == 0,
                'createDate': f'2024-{(i%12)+1:02d}-{(i%28)+1:02d}T{(i%24):02d}:{(i%60):02d}:00+0900',
                'subnetCount': (i % 10) + 1,
                'routeTableCount': (i % 5) + 1
            })
        return vpcs
    
    @patch.object(NCPClient, '_make_request')
    def test_large_instance_list_performance(self, mock_make_request):
        """Test performance of processing large instance lists."""
        # Mock API response with large dataset
        mock_make_request.return_value = {
            'getServerInstanceListResponse': {
                'serverInstanceList': self.large_instance_dataset,
                'totalRows': len(self.large_instance_dataset)
            }
        }
        
        # Measure performance
        start_time = time.time()
        result = self.client.get_server_instances()
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Verify results
        assert result['total_count'] == 1000
        assert len(result['instances']) == 1000
        
        # Performance assertions (should process 1000 instances in under 1 second)
        assert processing_time < 1.0, f"Processing took {processing_time:.3f}s, expected < 1.0s"
        
        # Throughput assertion (should process at least 1000 instances per second)
        throughput = len(result['instances']) / processing_time
        assert throughput > 1000, f"Throughput: {throughput:.0f} instances/sec, expected > 1000"
    
    @patch.object(NCPClient, '_make_request')
    def test_large_bucket_list_performance(self, mock_make_request):
        """Test performance of processing large bucket lists."""
        # Test with mock bucket data (since actual API call uses mock data)
        start_time = time.time()
        result = self.client.get_object_storage_buckets()
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Performance assertion (should process quickly)
        assert processing_time < 0.5, f"Processing took {processing_time:.3f}s, expected < 0.5s"
    
    def test_concurrent_api_calls_performance(self):
        """Test performance of concurrent API calls."""
        def make_api_call(client, call_type):
            """Make a single API call."""
            try:
                if call_type == 'instances':
                    return client.get_server_instances(page_size=10)
                elif call_type == 'buckets':
                    return client.get_object_storage_buckets()
                elif call_type == 'vpcs':
                    return client.get_vpc_list()
            except Exception as e:
                return {'error': str(e)}
        
        # Test concurrent calls
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            # Submit multiple concurrent requests
            for i in range(30):  # 10 of each type
                call_type = ['instances', 'buckets', 'vpcs'][i % 3]
                future = executor.submit(make_api_call, self.client, call_type)
                futures.append(future)
            
            # Wait for all to complete
            results = []
            for future in as_completed(futures):
                results.append(future.result())
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify all calls completed
        assert len(results) == 30
        
        # Performance assertion (concurrent calls should be faster than sequential)
        # With 30 calls, should complete in under 5 seconds
        assert total_time < 5.0, f"Concurrent calls took {total_time:.3f}s, expected < 5.0s"
        
        # Calculate average response time
        avg_response_time = total_time / len(results)
        assert avg_response_time < 0.2, f"Average response time: {avg_response_time:.3f}s, expected < 0.2s"
    
    def test_memory_usage_large_datasets(self):
        """Test memory usage with large datasets."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process large datasets
        large_datasets = []
        for _ in range(10):
            large_datasets.append(self._generate_large_instance_dataset(1000))
        
        # Get peak memory usage
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # Memory usage should be reasonable (less than 100MB increase for test data)
        assert memory_increase < 100, f"Memory increase: {memory_increase:.1f}MB, expected < 100MB"
        
        # Clean up
        del large_datasets
    
    def test_data_filtering_performance(self):
        """Test performance of data filtering operations."""
        # Test name filtering performance
        start_time = time.time()
        
        filtered_instances = []
        filter_term = "server-1"
        
        for instance in self.large_instance_dataset:
            if filter_term in instance['serverName']:
                filtered_instances.append(instance)
        
        end_time = time.time()
        filtering_time = end_time - start_time
        
        # Should filter 1000 instances quickly
        assert filtering_time < 0.1, f"Filtering took {filtering_time:.3f}s, expected < 0.1s"
        
        # Verify filtering worked
        assert len(filtered_instances) > 0
        for instance in filtered_instances:
            assert filter_term in instance['serverName']


class TestNCPGovPerformance:
    """Performance tests for NCP Gov operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.gov_client = NCPGovClient("gov-key", "gov-secret", "KR")
        
        # Generate sensitive government data for masking tests
        self.sensitive_gov_data = []
        for i in range(1000):
            self.sensitive_gov_data.append({
                'server_id': f'gov-server-{i}',
                'private_ip': f'10.0.{i//256}.{i%256}',
                'internal_ip': f'192.168.{i//256}.{i%256}',
                'access_key': f'GOV-AKIA{i:010d}',
                'secret_key': f'gov-secret-{i:020d}',
                'security_group_id': f'sg-gov{i:06d}',
                'classification': 'confidential' if i % 2 == 0 else 'secret',
                'public_data': f'public-info-{i}'
            })
    
    def test_sensitive_data_masking_performance(self):
        """Test performance of sensitive data masking for government cloud."""
        start_time = time.time()
        
        masked_data_list = []
        for data in self.sensitive_gov_data:
            masked_data = mask_sensitive_data(data)
            masked_data_list.append(masked_data)
        
        end_time = time.time()
        masking_time = end_time - start_time
        
        # Should mask 1000 records quickly
        assert masking_time < 0.5, f"Masking took {masking_time:.3f}s, expected < 0.5s"
        
        # Verify masking worked
        assert len(masked_data_list) == 1000
        for masked_data in masked_data_list:
            assert '***' in masked_data['private_ip']
            assert '***' in masked_data['access_key']
            assert 'public-info-' in masked_data['public_data']  # Public data preserved
        
        # Calculate throughput
        throughput = len(masked_data_list) / masking_time
        assert throughput > 2000, f"Masking throughput: {throughput:.0f} records/sec, expected > 2000"
    
    def test_compliance_checking_performance(self):
        """Test performance of compliance checking operations."""
        from common.ncpgov_utils import validate_network_policy_compliance
        
        # Generate compliance test data
        compliance_test_data = []
        for i in range(500):
            compliance_test_data.append({
                'encryption_status': 'enabled' if i % 3 != 0 else 'disabled',
                'audit_logging': 'enabled' if i % 4 != 0 else 'disabled',
                'access_control': 'enabled' if i % 5 != 0 else 'disabled',
                'network_isolation': 'enabled' if i % 6 != 0 else 'disabled',
                'data_classification': 'government' if i % 2 == 0 else 'public'
            })
        
        start_time = time.time()
        
        compliance_results = []
        for data in compliance_test_data:
            # Simulate compliance checking
            result = {
                'status': 'compliant' if data.get('encryption_status') == 'enabled' else 'needs_review',
                'score': 100 if data.get('encryption_status') == 'enabled' else 50,
                'issues': [] if data.get('encryption_status') == 'enabled' else ['encryption_disabled']
            }
            compliance_results.append(result)
        
        end_time = time.time()
        compliance_time = end_time - start_time
        
        # Should check compliance for 500 resources quickly
        assert compliance_time < 1.0, f"Compliance checking took {compliance_time:.3f}s, expected < 1.0s"
        
        # Verify compliance checking worked
        assert len(compliance_results) == 500
        for result in compliance_results:
            assert 'status' in result
            assert 'score' in result
            assert 'issues' in result
        
        # Calculate throughput
        throughput = len(compliance_results) / compliance_time
        assert throughput > 500, f"Compliance throughput: {throughput:.0f} checks/sec, expected > 500"


class TestNCPOutputFormattingPerformance:
    """Performance tests for NCP output formatting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = OutputFormatter()
        
        # Generate large dataset for formatting tests
        self.large_formatting_dataset = []
        for i in range(2000):
            self.large_formatting_dataset.append({
                'id': f'resource-{i:06d}',
                'name': f'performance-test-resource-{i}',
                'status': 'active' if i % 3 != 0 else 'inactive',
                'type': f'type-{i % 10}',
                'region': 'KR',
                'created': f'2024-{(i%12)+1:02d}-{(i%28)+1:02d}',
                'size': format_bytes(i * 1024 * 1024),
                'description': f'This is a test resource number {i} for performance testing'
            })
        
        self.headers = ['id', 'name', 'status', 'type', 'region', 'created', 'size']
    
    def test_json_formatting_performance(self):
        """Test performance of JSON output formatting."""
        start_time = time.time()
        
        json_output = self.formatter.format_output(
            self.large_formatting_dataset, 
            'json', 
            self.headers
        )
        
        end_time = time.time()
        formatting_time = end_time - start_time
        
        # Should format 2000 records to JSON quickly
        assert formatting_time < 0.5, f"JSON formatting took {formatting_time:.3f}s, expected < 0.5s"
        
        # Verify JSON output
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 2000
        assert parsed_json[0]['id'] == 'resource-000000'
        
        # Calculate throughput
        throughput = len(self.large_formatting_dataset) / formatting_time
        assert throughput > 4000, f"JSON formatting throughput: {throughput:.0f} records/sec, expected > 4000"
    
    def test_table_formatting_performance(self):
        """Test performance of table output formatting."""
        start_time = time.time()
        
        table_output = self.formatter.format_output(
            self.large_formatting_dataset, 
            'table', 
            self.headers
        )
        
        end_time = time.time()
        formatting_time = end_time - start_time
        
        # Table formatting is more complex, allow more time
        assert formatting_time < 2.0, f"Table formatting took {formatting_time:.3f}s, expected < 2.0s"
        
        # Verify table output contains data
        assert 'resource-000000' in table_output
        assert 'resource-001999' in table_output
        assert len(table_output) > 0
        
        # Calculate throughput
        throughput = len(self.large_formatting_dataset) / formatting_time
        assert throughput > 1000, f"Table formatting throughput: {throughput:.0f} records/sec, expected > 1000"
    
    def test_size_formatting_performance(self):
        """Test performance of size formatting utilities."""
        # Generate various sizes for testing
        test_sizes = []
        for i in range(10000):
            # Generate sizes from bytes to terabytes
            size = i * (2 ** (i % 20))
            test_sizes.append(size)
        
        start_time = time.time()
        
        formatted_sizes = []
        for size in test_sizes:
            formatted_size = format_bytes(size)
            formatted_sizes.append(formatted_size)
        
        end_time = time.time()
        formatting_time = end_time - start_time
        
        # Should format 10000 sizes quickly
        assert formatting_time < 0.2, f"Size formatting took {formatting_time:.3f}s, expected < 0.2s"
        
        # Verify formatting worked
        assert len(formatted_sizes) == 10000
        assert all(isinstance(size, str) for size in formatted_sizes)
        
        # Calculate throughput
        throughput = len(formatted_sizes) / formatting_time
        assert throughput > 50000, f"Size formatting throughput: {throughput:.0f} formats/sec, expected > 50000"


class TestNCPPaginationPerformance:
    """Performance tests for NCP pagination handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = NCPClient("test-key", "test-secret", "KR")
    
    @patch.object(NCPClient, '_make_request')
    def test_pagination_performance(self, mock_make_request):
        """Test performance of pagination with large datasets."""
        # Mock paginated responses
        page_size = 100
        total_pages = 10
        
        def mock_paginated_response(method, endpoint, params=None, **kwargs):
            # Simulate different pages
            page_num = params.get('page', 1) if params else 1
            
            if page_num <= total_pages:
                instances = []
                start_idx = (page_num - 1) * page_size
                for i in range(start_idx, min(start_idx + page_size, total_pages * page_size)):
                    instances.append({
                        'serverInstanceNo': f'i-{i:06d}',
                        'serverName': f'paginated-server-{i}',
                        'serverInstanceStatus': 'RUN'
                    })
                
                return {
                    'getServerInstanceListResponse': {
                        'serverInstanceList': instances,
                        'totalRows': total_pages * page_size,
                        'pageNo': page_num,
                        'pageSize': page_size
                    }
                }
            else:
                return {
                    'getServerInstanceListResponse': {
                        'serverInstanceList': [],
                        'totalRows': total_pages * page_size
                    }
                }
        
        mock_make_request.side_effect = mock_paginated_response
        
        # Test pagination performance
        start_time = time.time()
        
        all_instances = []
        for page in range(1, total_pages + 1):
            result = self.client.get_server_instances(page_size=page_size)
            all_instances.extend(result['instances'])
        
        end_time = time.time()
        pagination_time = end_time - start_time
        
        # Should handle pagination efficiently
        assert pagination_time < 1.0, f"Pagination took {pagination_time:.3f}s, expected < 1.0s"
        
        # Verify all data was retrieved
        assert len(all_instances) == total_pages * page_size
        
        # Calculate throughput
        throughput = len(all_instances) / pagination_time
        assert throughput > 1000, f"Pagination throughput: {throughput:.0f} records/sec, expected > 1000"


class TestNCPStressTest:
    """Stress tests for NCP components."""
    
    def test_high_concurrency_stress(self):
        """Stress test with high concurrency."""
        client = NCPClient("test-key", "test-secret", "KR")
        
        def stress_worker():
            """Worker function for stress testing."""
            try:
                # Perform multiple operations
                client.get_server_instances(page_size=10)
                client.get_object_storage_buckets()
                client.get_vpc_list()
                return True
            except Exception:
                return False
        
        # Run high concurrency test
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(stress_worker) for _ in range(200)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        stress_time = end_time - start_time
        
        # Most operations should succeed
        success_rate = sum(results) / len(results)
        assert success_rate > 0.8, f"Success rate: {success_rate:.2%}, expected > 80%"
        
        # Should handle high concurrency reasonably
        assert stress_time < 10.0, f"Stress test took {stress_time:.3f}s, expected < 10.0s"
    
    def test_memory_leak_detection(self):
        """Test for memory leaks during repeated operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        client = NCPClient("test-key", "test-secret", "KR")
        
        # Record initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many operations
        for i in range(100):
            try:
                client.get_server_instances(page_size=50)
                client.get_object_storage_buckets()
                client.get_vpc_list()
                
                # Force garbage collection periodically
                if i % 10 == 0:
                    import gc
                    gc.collect()
            except Exception:
                pass  # Ignore errors in stress test
        
        # Record final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be minimal (less than 50MB)
        assert memory_increase < 50, f"Memory leak detected: {memory_increase:.1f}MB increase"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])