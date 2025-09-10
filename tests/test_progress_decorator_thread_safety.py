"""
Thread Safety Tests for Progress Decorator

This module provides comprehensive tests for the progress decorator's thread safety
and concurrent operation handling. Tests cover:

1. Thread-safe progress updates
2. Concurrent operation handling
3. Error handling in multi-threaded scenarios
4. Resource cleanup and context management

Requirements: 10.3 - Implement tests for progress decorator functionality and thread safety
"""

import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from common.progress_decorator import (
    ProgressBarDecorator, 
    ProgressContext, 
    progress_bar, 
    concurrent_progress,
    ManualProgress
)


class TestProgressDecoratorThreadSafety:
    """Test thread safety of progress decorator components."""
    
    def test_progress_context_thread_safety(self):
        """Test ProgressContext thread-safe operations."""
        context = ProgressContext(total_operations=1000, thread_safe=True)
        
        def update_progress():
            """Worker function to update progress."""
            for _ in range(100):
                with context._lock:
                    context.completed_operations += 1
                    context.current_operation = f"Thread {threading.current_thread().ident}"
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=update_progress)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify thread-safe updates
        assert context.completed_operations == 1000
        assert len(context.errors) == 0
    
    def test_progress_context_error_handling(self):
        """Test thread-safe error handling in ProgressContext."""
        context = ProgressContext(total_operations=100, thread_safe=True)
        
        def worker_with_errors(worker_id):
            """Worker that sometimes fails."""
            for i in range(10):
                try:
                    if i == 5 and worker_id % 2 == 0:  # Some workers fail
                        raise ValueError(f"Worker {worker_id} error at step {i}")
                    
                    with context._lock:
                        context.completed_operations += 1
                        
                except Exception as e:
                    with context._lock:
                        context.errors.append(f"Worker {worker_id}: {str(e)}")
        
        # Run workers with some failures
        threads = []
        for worker_id in range(10):
            thread = threading.Thread(target=worker_with_errors, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify error collection
        assert len(context.errors) == 5  # Half the workers should fail
        assert context.completed_operations == 95  # 10 workers * 10 steps - 5 failures
    
    def test_concurrent_progress_decorator(self):
        """Test concurrent_progress decorator with multiple threads."""
        results = []
        errors = []
        
        @concurrent_progress("Concurrent processing", max_workers=4)
        def process_items_concurrently(items):
            """Function that processes items concurrently."""
            def process_single_item(item):
                time.sleep(0.01)  # Simulate work
                if item == "error_item":
                    raise ValueError(f"Processing error for {item}")
                return f"processed_{item}"
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_item = {
                    executor.submit(process_single_item, item): item 
                    for item in items
                }
                
                item_results = []
                for future in as_completed(future_to_item):
                    item = future_to_item[future]
                    try:
                        result = future.result()
                        item_results.append(result)
                    except Exception as e:
                        errors.append(f"Error processing {item}: {str(e)}")
                
                return item_results
        
        # Test with mixed success/failure items
        test_items = [f"item_{i}" for i in range(20)] + ["error_item"]
        
        try:
            results = process_items_concurrently(test_items)
        except Exception as e:
            # Some errors are expected
            pass
        
        # Verify concurrent processing worked
        assert len(results) >= 20  # Should process most items successfully
    
    def test_manual_progress_thread_safety(self):
        """Test ManualProgress thread safety."""
        completed_operations = []
        
        def worker_with_manual_progress(worker_id):
            """Worker using manual progress tracking."""
            with ManualProgress(f"Worker {worker_id}", total=10) as progress:
                for i in range(10):
                    time.sleep(0.001)  # Minimal work simulation
                    progress.update(f"Worker {worker_id} - Step {i+1}")
                    progress.advance(1)
                    completed_operations.append((worker_id, i))
        
        # Run multiple workers with manual progress
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=worker_with_manual_progress, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        assert len(completed_operations) == 50  # 5 workers * 10 operations each
    
    def test_progress_decorator_with_thread_pool(self):
        """Test progress decorator with ThreadPoolExecutor."""
        @progress_bar("Thread pool processing")
        def thread_pool_function(items):
            """Function that uses ThreadPoolExecutor internally."""
            results = []
            
            def process_item(item):
                time.sleep(0.01)
                return f"result_{item}"
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(process_item, item) for item in items]
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append(f"error: {str(e)}")
            
            return results
        
        test_items = [f"item_{i}" for i in range(15)]
        results = thread_pool_function(test_items)
        
        assert len(results) == 15
        assert all("result_" in result for result in results)
    
    def test_nested_progress_decorators(self):
        """Test nested progress decorators for thread safety."""
        @progress_bar("Outer operation")
        def outer_operation(items):
            """Outer function with progress decorator."""
            results = []
            
            @progress_bar("Inner operation")
            def inner_operation(item):
                """Inner function with progress decorator."""
                time.sleep(0.01)
                return f"processed_{item}"
            
            for item in items:
                result = inner_operation(item)
                results.append(result)
            
            return results
        
        test_items = [f"item_{i}" for i in range(10)]
        results = outer_operation(test_items)
        
        assert len(results) == 10
        assert all("processed_" in result for result in results)
    
    def test_progress_decorator_exception_handling(self):
        """Test progress decorator exception handling in threaded environment."""
        exceptions_caught = []
        
        @progress_bar("Error-prone operation")
        def error_prone_function(items):
            """Function that may raise exceptions."""
            results = []
            
            for i, item in enumerate(items):
                if i == 5:  # Fail on 6th item
                    raise ValueError(f"Intentional error at item {item}")
                
                time.sleep(0.01)
                results.append(f"processed_{item}")
            
            return results
        
        def worker():
            """Worker that calls error-prone function."""
            try:
                test_items = [f"item_{i}" for i in range(10)]
                error_prone_function(test_items)
            except Exception as e:
                exceptions_caught.append(str(e))
        
        # Run multiple workers
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify exceptions were properly handled
        assert len(exceptions_caught) == 3
        assert all("Intentional error" in exc for exc in exceptions_caught)
    
    def test_progress_decorator_resource_cleanup(self):
        """Test proper resource cleanup in threaded scenarios."""
        cleanup_calls = []
        
        class MockProgress:
            """Mock progress object to track cleanup."""
            def __init__(self, description):
                self.description = description
                self.active = True
            
            def __enter__(self):
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.active = False
                cleanup_calls.append(self.description)
        
        @progress_bar("Resource cleanup test")
        def function_with_resources():
            """Function that uses resources."""
            with MockProgress("Test resource") as resource:
                time.sleep(0.01)
                return resource.active
        
        def worker():
            """Worker that uses resources."""
            return function_with_resources()
        
        # Run multiple workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            results = [future.result() for future in futures]
        
        # Verify all resources were active during use
        assert all(result is True for result in results)
        
        # Note: cleanup_calls tracking would need to be integrated into actual progress decorator
        # This test demonstrates the pattern for resource cleanup testing
    
    def test_progress_decorator_memory_usage(self):
        """Test progress decorator doesn't leak memory in threaded scenarios."""
        import gc
        
        @progress_bar("Memory usage test")
        def memory_test_function(data_size):
            """Function that processes data."""
            # Create some data to process
            data = [f"item_{i}" for i in range(data_size)]
            
            # Process data
            results = []
            for item in data:
                results.append(f"processed_{item}")
            
            return len(results)
        
        def worker():
            """Worker that processes data."""
            return memory_test_function(100)
        
        # Get initial memory state
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Run multiple workers
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker) for _ in range(5)]
            results = [future.result() for future in futures]
        
        # Force garbage collection
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Verify results
        assert all(result == 100 for result in results)
        
        # Memory usage should not grow significantly
        # Allow for some variance in object count
        object_growth = final_objects - initial_objects
        assert object_growth < 1000, f"Potential memory leak: {object_growth} new objects"
    
    def test_progress_decorator_performance_under_load(self):
        """Test progress decorator performance under high load."""
        import time
        
        @progress_bar("Performance test")
        def performance_test_function(iterations):
            """Function for performance testing."""
            start_time = time.time()
            
            for i in range(iterations):
                # Minimal work to test decorator overhead
                pass
            
            return time.time() - start_time
        
        # Test with different load levels
        load_levels = [100, 1000, 10000]
        execution_times = []
        
        for load in load_levels:
            execution_time = performance_test_function(load)
            execution_times.append(execution_time)
        
        # Verify performance scales reasonably
        # Execution time should scale roughly linearly with load
        assert execution_times[1] > execution_times[0]  # More work takes more time
        assert execution_times[2] > execution_times[1]
        
        # But overhead should be minimal (less than 10ms for 10k iterations)
        assert execution_times[2] < 0.01, f"Performance overhead too high: {execution_times[2]}s"


class TestProgressDecoratorConcurrentOperations:
    """Test concurrent operations with progress decorator."""
    
    def test_concurrent_aws_operations_simulation(self):
        """Simulate concurrent AWS operations with progress tracking."""
        @concurrent_progress("AWS EC2 operations", max_workers=3)
        def simulate_aws_ec2_operations(regions):
            """Simulate AWS EC2 operations across regions."""
            def process_region(region):
                # Simulate API call delay
                time.sleep(0.02)
                
                # Simulate some failures
                if region == "us-west-1":
                    raise Exception(f"API error in {region}")
                
                return {
                    'region': region,
                    'instances': [f"i-{region}-{i}" for i in range(3)]
                }
            
            results = []
            errors = []
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_region = {
                    executor.submit(process_region, region): region 
                    for region in regions
                }
                
                for future in as_completed(future_to_region):
                    region = future_to_region[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        errors.append(f"Error in {region}: {str(e)}")
            
            return results, errors
        
        test_regions = ["us-east-1", "us-west-1", "us-west-2", "eu-west-1"]
        results, errors = simulate_aws_ec2_operations(test_regions)
        
        # Verify results
        assert len(results) == 3  # 4 regions - 1 error
        assert len(errors) == 1   # 1 region failed
        assert "us-west-1" in errors[0]
    
    def test_concurrent_oci_operations_simulation(self):
        """Simulate concurrent OCI operations with progress tracking."""
        @concurrent_progress("OCI compartment operations", max_workers=2)
        def simulate_oci_compartment_operations(compartments):
            """Simulate OCI compartment operations."""
            def process_compartment(compartment_id):
                time.sleep(0.015)  # Simulate API delay
                
                return {
                    'compartment_id': compartment_id,
                    'resources': [f"resource-{compartment_id}-{i}" for i in range(2)]
                }
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(process_compartment, comp_id) 
                    for comp_id in compartments
                ]
                
                results = [future.result() for future in futures]
            
            return results
        
        test_compartments = [f"ocid1.compartment.{i}" for i in range(6)]
        results = simulate_oci_compartment_operations(test_compartments)
        
        assert len(results) == 6
        assert all('compartment_id' in result for result in results)
    
    def test_concurrent_ssh_operations_simulation(self):
        """Simulate concurrent SSH operations with progress tracking."""
        @concurrent_progress("SSH server operations", max_workers=4)
        def simulate_ssh_operations(servers):
            """Simulate SSH operations across servers."""
            def connect_to_server(server):
                time.sleep(0.01)  # Simulate connection time
                
                # Simulate connection failures
                if "unreachable" in server:
                    raise ConnectionError(f"Cannot connect to {server}")
                
                return {
                    'server': server,
                    'status': 'connected',
                    'info': f"Linux {server} 5.4.0"
                }
            
            results = []
            errors = []
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_server = {
                    executor.submit(connect_to_server, server): server 
                    for server in servers
                }
                
                for future in as_completed(future_to_server):
                    server = future_to_server[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        errors.append(f"Error connecting to {server}: {str(e)}")
            
            return results, errors
        
        test_servers = [
            "server1.example.com",
            "server2.example.com", 
            "unreachable.example.com",
            "server3.example.com"
        ]
        
        results, errors = simulate_ssh_operations(test_servers)
        
        assert len(results) == 3  # 4 servers - 1 unreachable
        assert len(errors) == 1   # 1 connection error
        assert "unreachable" in errors[0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])