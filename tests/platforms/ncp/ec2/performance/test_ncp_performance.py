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

# Import NCP components - updated to use consolidated modules
from ic.platforms.ncp.client import NCPClient, NCPAPIError
from ic.platforms.ncpgov.client import NCPGovClient
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
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not available")
        
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
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not available")
        
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