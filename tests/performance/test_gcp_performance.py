#!/usr/bin/env python3
"""
Performance and load tests for GCP services integration.

These tests validate performance characteristics, parallel processing,
memory usage, and API rate limiting behavior.
"""

import unittest
import time
import threading
import psutil
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Callable
from unittest.mock import patch, Mock
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.gcp_utils import GCPAuthManager, GCPProjectManager, GCPResourceCollector
from mcp.gcp_connector import MCPGCPConnector
from tests.test_config import TestPerformanceMetrics, TEST_CONFIG
from tests.test_gcp_mock_data import GCPMockDataGenerator


class PerformanceTestBase(unittest.TestCase):
    """Base class for performance tests."""
    
    def setUp(self):
        """Set up performance test environment."""
        self.metrics = TestPerformanceMetrics()
        self.thresholds = TEST_CONFIG["performance_thresholds"]
        self.mock_data_generator = GCPMockDataGenerator()
        
        # Mock project configuration
        self.test_projects = ["test-project-1", "test-project-2", "test-project-3"]
        self.test_regions = ["us-central1", "us-east1", "europe-west1"]
        
    def measure_memory_usage(self, func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """Measure memory usage during function execution."""
        process = psutil.Process()
        
        # Get initial memory usage
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Execute function
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        return {
            'result': result,
            'duration': end_time - start_time,
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'memory_delta_mb': final_memory - initial_memory
        }
    
    def simulate_large_dataset(self, resource_type: str, count: int) -> List[Dict[str, Any]]:
        """Generate large dataset for performance testing."""
        data = []
        
        for i in range(count):
            if resource_type == 'compute':
                data.append(self.mock_data_generator.generate_compute_instance(
                    name=f"instance-{i}",
                    project_id=f"project-{i % 3}",
                    zone=f"us-central1-{chr(97 + i % 3)}"  # a, b, c
                ))
            elif resource_type == 'vpc':
                data.append(self.mock_data_generator.generate_vpc_network(
                    name=f"network-{i}",
                    project_id=f"project-{i % 3}"
                ))
            elif resource_type == 'gke':
                data.append(self.mock_data_generator.generate_gke_cluster(
                    name=f"cluster-{i}",
                    project_id=f"project-{i % 3}",
                    location=f"us-central1-{chr(97 + i % 3)}"
                ))
        
        return data


class TestAuthenticationPerformance(PerformanceTestBase):
    """Test authentication performance."""
    
    @patch('common.gcp_utils.service_account.Credentials.from_service_account_info')
    def test_authentication_speed(self, mock_from_info):
        """Test authentication speed."""
        mock_credentials = Mock()
        mock_from_info.return_value = mock_credentials
        
        def authenticate():
            auth_manager = GCPAuthManager()
            return auth_manager.get_credentials()
        
        # Measure authentication time
        self.metrics.start_timer("authentication")
        credentials = authenticate()
        self.metrics.end_timer("authentication")
        
        # Verify authentication succeeded
        self.assertIsNotNone(credentials)
        
        # Check performance threshold
        duration = self.metrics.get_duration("authentication")
        self.assertLess(duration, self.thresholds["api_call"], 
                       f"Authentication took {duration:.2f}s, exceeding threshold")
    
    @patch('common.gcp_utils.service_account.Credentials.from_service_account_info')
    def test_concurrent_authentication(self, mock_from_info):
        """Test concurrent authentication performance."""
        mock_credentials = Mock()
        mock_from_info.return_value = mock_credentials
        
        def authenticate():
            auth_manager = GCPAuthManager()
            return auth_manager.get_credentials()
        
        # Test concurrent authentication
        num_threads = 10
        results = []
        
        self.metrics.start_timer("concurrent_auth")
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(authenticate) for _ in range(num_threads)]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        self.metrics.end_timer("concurrent_auth")
        
        # Verify all authentications succeeded
        self.assertEqual(len(results), num_threads)
        self.assertTrue(all(r is not None for r in results))
        
        # Check performance
        duration = self.metrics.get_duration("concurrent_auth")
        self.assertLess(duration, self.thresholds["api_call"] * 2, 
                       f"Concurrent authentication took {duration:.2f}s")


class TestDataCollectionPerformance(PerformanceTestBase):
    """Test data collection performance."""
    
    def test_large_dataset_processing(self):
        """Test processing large datasets."""
        # Generate large dataset
        large_dataset = self.simulate_large_dataset('compute', 1000)
        
        def process_dataset(data):
            # Simulate data processing operations
            filtered_data = [item for item in data if item['status'] == 'RUNNING']
            sorted_data = sorted(filtered_data, key=lambda x: x['name'])
            return sorted_data
        
        # Measure processing performance
        memory_stats = self.measure_memory_usage(process_dataset, large_dataset)
        
        # Verify processing completed
        self.assertIsInstance(memory_stats['result'], list)
        
        # Check performance thresholds
        self.assertLess(memory_stats['duration'], self.thresholds["data_collection"],
                       f"Large dataset processing took {memory_stats['duration']:.2f}s")
        
        # Check memory usage (should not exceed 100MB for 1000 items)
        self.assertLess(memory_stats['memory_delta_mb'], 100,
                       f"Memory usage increased by {memory_stats['memory_delta_mb']:.2f}MB")
    
    def test_parallel_data_collection(self):
        """Test parallel data collection performance."""
        def collect_service_data(service_name, project_id):
            # Simulate API call delay
            time.sleep(0.1)
            return self.simulate_large_dataset(service_name, 50)
        
        services = ['compute', 'vpc', 'gke']
        projects = self.test_projects
        
        # Sequential collection
        self.metrics.start_timer("sequential_collection")
        sequential_results = []
        for project in projects:
            for service in services:
                result = collect_service_data(service, project)
                sequential_results.append(result)
        self.metrics.end_timer("sequential_collection")
        
        # Parallel collection
        self.metrics.start_timer("parallel_collection")
        parallel_results = []
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            for project in projects:
                for service in services:
                    future = executor.submit(collect_service_data, service, project)
                    futures.append(future)
            
            for future in as_completed(futures):
                result = future.result()
                parallel_results.append(result)
        
        self.metrics.end_timer("parallel_collection")
        
        # Verify results
        self.assertEqual(len(sequential_results), len(parallel_results))
        
        # Calculate speedup
        sequential_time = self.metrics.get_duration("sequential_collection")
        parallel_time = self.metrics.get_duration("parallel_collection")
        speedup = sequential_time / parallel_time
        
        print(f"Sequential: {sequential_time:.2f}s, Parallel: {parallel_time:.2f}s, Speedup: {speedup:.2f}x")
        
        # Parallel should be significantly faster
        self.assertGreater(speedup, 2.0, f"Parallel processing speedup was only {speedup:.2f}x")
    
    def test_memory_efficiency_large_datasets(self):
        """Test memory efficiency with large datasets."""
        def process_incrementally(dataset_size):
            # Process data in chunks to test memory efficiency
            chunk_size = 100
            results = []
            
            for i in range(0, dataset_size, chunk_size):
                chunk = self.simulate_large_dataset('compute', min(chunk_size, dataset_size - i))
                processed_chunk = [item for item in chunk if item['status'] == 'RUNNING']
                results.extend(processed_chunk)
                
                # Simulate cleanup
                del chunk
                del processed_chunk
            
            return results
        
        # Test with different dataset sizes
        sizes = [100, 500, 1000, 2000]
        memory_usage = []
        
        for size in sizes:
            stats = self.measure_memory_usage(process_incrementally, size)
            memory_usage.append({
                'size': size,
                'memory_delta': stats['memory_delta_mb'],
                'duration': stats['duration']
            })
        
        # Memory usage should scale reasonably with dataset size
        for i, stats in enumerate(memory_usage):
            print(f"Size {stats['size']}: {stats['memory_delta']:.2f}MB, {stats['duration']:.2f}s")
            
            # Memory usage should not exceed 50MB per 1000 items
            max_memory = (stats['size'] / 1000) * 50
            self.assertLess(stats['memory_delta'], max_memory,
                           f"Memory usage {stats['memory_delta']:.2f}MB exceeds threshold for {stats['size']} items")


class TestMCPPerformance(PerformanceTestBase):
    """Test MCP connector performance."""
    
    def test_mcp_vs_direct_api_performance(self):
        """Compare MCP vs direct API performance."""
        mock_connector = Mock()
        
        # Mock MCP responses
        def mock_mcp_response(*args, **kwargs):
            time.sleep(0.05)  # Simulate network delay
            from mcp.gcp_connector import MCPResponse
            return MCPResponse(success=True, data={"instances": self.simulate_large_dataset('compute', 10)})
        
        mock_connector.execute_gcp_query.side_effect = mock_mcp_response
        mock_connector.is_available.return_value = True
        
        def mock_direct_api(*args, **kwargs):
            time.sleep(0.1)  # Simulate API call
            return self.simulate_large_dataset('compute', 10)
        
        # Test MCP performance
        self.metrics.start_timer("mcp_call")
        mcp_result = mock_mcp_response()
        self.metrics.end_timer("mcp_call")
        
        # Test direct API performance
        self.metrics.start_timer("direct_api_call")
        direct_result = mock_direct_api()
        self.metrics.end_timer("direct_api_call")
        
        # Compare performance
        mcp_time = self.metrics.get_duration("mcp_call")
        direct_time = self.metrics.get_duration("direct_api_call")
        
        print(f"MCP: {mcp_time:.3f}s, Direct API: {direct_time:.3f}s")
        
        # Both should be reasonably fast
        self.assertLess(mcp_time, 1.0, "MCP call should complete within 1 second")
        self.assertLess(direct_time, 1.0, "Direct API call should complete within 1 second")
    
    def test_mcp_connection_pooling(self):
        """Test MCP connection pooling performance."""
        mock_connector = Mock()
        mock_connector.is_available.return_value = True
        
        def make_mcp_call():
            time.sleep(0.01)  # Simulate small delay
            return {"status": "success"}
        
        mock_connector.execute_gcp_query.side_effect = lambda *args, **kwargs: make_mcp_call()
        
        # Test multiple concurrent connections
        num_calls = 50
        
        self.metrics.start_timer("mcp_concurrent_calls")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_mcp_call) for _ in range(num_calls)]
            results = [future.result() for future in as_completed(futures)]
        
        self.metrics.end_timer("mcp_concurrent_calls")
        
        # Verify all calls succeeded
        self.assertEqual(len(results), num_calls)
        
        # Check performance
        duration = self.metrics.get_duration("mcp_concurrent_calls")
        avg_time_per_call = duration / num_calls
        
        print(f"Concurrent MCP calls: {duration:.2f}s total, {avg_time_per_call:.3f}s per call")
        
        # Should handle concurrent calls efficiently
        self.assertLess(avg_time_per_call, 0.1, "Average MCP call time should be under 100ms")


class TestOutputFormattingPerformance(PerformanceTestBase):
    """Test output formatting performance."""
    
    def test_json_formatting_performance(self):
        """Test JSON formatting performance with large datasets."""
        from gcp.compute.info import format_output
        
        # Test with different dataset sizes
        sizes = [100, 500, 1000, 2000]
        
        for size in sizes:
            dataset = self.simulate_large_dataset('compute', size)
            
            self.metrics.start_timer(f"json_format_{size}")
            json_output = format_output(dataset, 'json')
            self.metrics.end_timer(f"json_format_{size}")
            
            # Verify output
            self.assertIsInstance(json_output, str)
            self.assertGreater(len(json_output), 0)
            
            # Check performance
            duration = self.metrics.get_duration(f"json_format_{size}")
            print(f"JSON formatting {size} items: {duration:.3f}s")
            
            # Should format within reasonable time
            max_time = (size / 1000) * self.thresholds["output_formatting"]
            self.assertLess(duration, max_time,
                           f"JSON formatting {size} items took {duration:.3f}s")
    
    def test_table_formatting_performance(self):
        """Test table formatting performance."""
        from gcp.compute.info import format_table_output
        
        # Test with large dataset
        dataset = self.simulate_large_dataset('compute', 500)
        
        # Measure table formatting performance
        memory_stats = self.measure_memory_usage(format_table_output, dataset)
        
        # Check performance
        self.assertLess(memory_stats['duration'], self.thresholds["output_formatting"],
                       f"Table formatting took {memory_stats['duration']:.3f}s")
        
        # Memory usage should be reasonable
        self.assertLess(memory_stats['memory_delta_mb'], 50,
                       f"Table formatting used {memory_stats['memory_delta_mb']:.2f}MB")
    
    def test_concurrent_formatting(self):
        """Test concurrent output formatting."""
        from gcp.compute.info import format_output
        
        dataset = self.simulate_large_dataset('compute', 200)
        formats = ['json', 'yaml', 'table', 'tree']
        
        def format_data(format_type):
            return format_output(dataset, format_type)
        
        # Test concurrent formatting
        self.metrics.start_timer("concurrent_formatting")
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(format_data, fmt) for fmt in formats]
            results = [future.result() for future in as_completed(futures)]
        
        self.metrics.end_timer("concurrent_formatting")
        
        # Verify all formats completed
        self.assertEqual(len(results), len(formats))
        
        # Check performance
        duration = self.metrics.get_duration("concurrent_formatting")
        self.assertLess(duration, self.thresholds["output_formatting"] * 2,
                       f"Concurrent formatting took {duration:.3f}s")


class TestRateLimitingAndRetry(PerformanceTestBase):
    """Test rate limiting and retry behavior."""
    
    def test_retry_logic_performance(self):
        """Test retry logic performance."""
        from common.gcp_utils import GCPResourceCollector
        
        # Mock auth manager
        mock_auth = Mock()
        collector = GCPResourceCollector(mock_auth)
        
        call_count = 0
        
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        # Test retry with exponential backoff
        self.metrics.start_timer("retry_logic")
        
        try:
            result = collector.handle_api_errors(failing_function)
            self.metrics.end_timer("retry_logic")
            
            # Verify retry succeeded
            self.assertEqual(result, "success")
            self.assertEqual(call_count, 3)
            
            # Check retry timing
            duration = self.metrics.get_duration("retry_logic")
            print(f"Retry logic took {duration:.3f}s for 3 attempts")
            
            # Should complete within reasonable time (including backoff)
            self.assertLess(duration, 10.0, "Retry logic should complete within 10 seconds")
            
        except Exception as e:
            self.fail(f"Retry logic failed: {e}")
    
    def test_rate_limiting_behavior(self):
        """Test rate limiting behavior simulation."""
        import random
        
        def simulate_rate_limited_api():
            # Simulate rate limiting with random delays
            if random.random() < 0.3:  # 30% chance of rate limiting
                time.sleep(0.5)  # Simulate rate limit delay
                raise Exception("Rate limited")
            
            time.sleep(0.01)  # Normal API delay
            return {"data": "success"}
        
        # Test multiple API calls with rate limiting
        num_calls = 20
        successful_calls = 0
        total_retries = 0
        
        self.metrics.start_timer("rate_limited_calls")
        
        for i in range(num_calls):
            retries = 0
            while retries < 3:
                try:
                    result = simulate_rate_limited_api()
                    successful_calls += 1
                    break
                except Exception:
                    retries += 1
                    total_retries += 1
                    time.sleep(0.1 * (2 ** retries))  # Exponential backoff
        
        self.metrics.end_timer("rate_limited_calls")
        
        # Verify most calls succeeded
        success_rate = successful_calls / num_calls
        self.assertGreater(success_rate, 0.8, f"Success rate was only {success_rate:.2f}")
        
        # Check performance
        duration = self.metrics.get_duration("rate_limited_calls")
        avg_time = duration / num_calls
        
        print(f"Rate limited calls: {duration:.2f}s total, {avg_time:.3f}s per call")
        print(f"Success rate: {success_rate:.2f}, Total retries: {total_retries}")


class TestStressAndLoad(PerformanceTestBase):
    """Stress and load testing."""
    
    def test_high_concurrency_stress(self):
        """Test high concurrency stress."""
        def cpu_intensive_task():
            # Simulate CPU-intensive data processing
            data = self.simulate_large_dataset('compute', 50)
            result = []
            for item in data:
                # Simulate processing
                processed = {
                    'name': item['name'].upper(),
                    'status': item['status'].lower(),
                    'processed_at': time.time()
                }
                result.append(processed)
            return len(result)
        
        # Test with high concurrency
        num_threads = 20
        
        self.metrics.start_timer("high_concurrency_stress")
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(cpu_intensive_task) for _ in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]
        
        self.metrics.end_timer("high_concurrency_stress")
        
        # Verify all tasks completed
        self.assertEqual(len(results), num_threads)
        self.assertTrue(all(r > 0 for r in results))
        
        # Check performance
        duration = self.metrics.get_duration("high_concurrency_stress")
        print(f"High concurrency stress test: {duration:.2f}s with {num_threads} threads")
        
        # Should handle high concurrency reasonably
        self.assertLess(duration, 30.0, "High concurrency test should complete within 30 seconds")
    
    def test_memory_stress(self):
        """Test memory stress with large datasets."""
        def memory_intensive_task(size):
            # Create large dataset
            data = self.simulate_large_dataset('compute', size)
            
            # Perform memory-intensive operations
            duplicated = data * 2  # Double the data
            filtered = [item for item in duplicated if 'test' in item['name']]
            sorted_data = sorted(filtered, key=lambda x: x['name'])
            
            return len(sorted_data)
        
        # Test with increasing memory load
        sizes = [100, 200, 500, 1000]
        memory_usage = []
        
        for size in sizes:
            stats = self.measure_memory_usage(memory_intensive_task, size)
            memory_usage.append({
                'size': size,
                'memory_delta': stats['memory_delta_mb'],
                'duration': stats['duration']
            })
            
            print(f"Memory stress {size} items: {stats['memory_delta_mb']:.2f}MB, {stats['duration']:.2f}s")
        
        # Memory usage should scale predictably
        for stats in memory_usage:
            # Should not use excessive memory
            max_memory = (stats['size'] / 100) * 20  # 20MB per 100 items
            self.assertLess(stats['memory_delta'], max_memory,
                           f"Memory usage {stats['memory_delta']:.2f}MB too high for {stats['size']} items")


def run_performance_tests():
    """Run all performance tests."""
    print("🚀 Running GCP Services Performance Tests")
    print("=" * 60)
    
    # Load and run performance tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all performance test classes
    test_classes = [
        TestAuthenticationPerformance,
        TestDataCollectionPerformance,
        TestMCPPerformance,
        TestOutputFormattingPerformance,
        TestRateLimitingAndRetry,
        TestStressAndLoad
    ]
    
    for test_class in test_classes:
        suite.addTest(loader.loadTestsFromTestCase(test_class))
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_performance_tests()
    exit(0 if success else 1)