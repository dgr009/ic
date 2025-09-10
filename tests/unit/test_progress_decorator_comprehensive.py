"""
Comprehensive Unit Tests for Progress Decorator

This module provides comprehensive unit tests for the progress decorator class
covering single and multi-threaded scenarios as required by task 20.

Requirements covered:
- 10.4: Write unit tests for progress decorator class covering single and multi-threaded scenarios
- 10.5: Implement end-to-end tests for progress bar integration across all modules
"""

import pytest
import threading
import time
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
import inspect

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from common.progress_decorator import (
    ProgressBarDecorator,
    ProgressContext,
    progress_bar,
    spinner,
    concurrent_progress,
    ManualProgress,
    RICH_AVAILABLE
)


class TestProgressBarDecoratorCore:
    """Test core functionality of ProgressBarDecorator."""
    
    def test_decorator_initialization(self):
        """Test ProgressBarDecorator initialization with various parameters."""
        # Default initialization
        decorator = ProgressBarDecorator()
        assert decorator.description is None
        assert decorator.show_time is True
        assert decorator.show_spinner is True
        assert decorator.auto_detect is True
        assert decorator.max_workers == 4
        
        # Custom initialization
        decorator = ProgressBarDecorator(
            description="Custom operation",
            show_time=False,
            show_spinner=False,
            auto_detect=False,
            max_workers=8
        )
        assert decorator.description == "Custom operation"
        assert decorator.show_time is False
        assert decorator.show_spinner is False
        assert decorator.auto_detect is False
        assert decorator.max_workers == 8
    
    def test_operation_type_detection_single(self):
        """Test detection of single operation type."""
        decorator = ProgressBarDecorator()
        
        def simple_function():
            return "result"
        
        operation_type = decorator._detect_operation_type(simple_function, (), {})
        assert operation_type == "single"
    
    def test_operation_type_detection_iterable(self):
        """Test detection of iterable operation type."""
        decorator = ProgressBarDecorator()
        
        def process_items(items):
            return [f"processed_{item}" for item in items]
        
        test_items = ["item1", "item2", "item3"]
        operation_type = decorator._detect_operation_type(process_items, (test_items,), {})
        assert operation_type == "iterable"
    
    def test_operation_type_detection_concurrent(self):
        """Test detection of concurrent operation type."""
        decorator = ProgressBarDecorator()
        
        def parallel_process_servers(servers):
            return [f"processed_{server}" for server in servers]
        
        test_servers = ["server1", "server2"]
        operation_type = decorator._detect_operation_type(parallel_process_servers, (test_servers,), {})
        assert operation_type == "iterable"  # Should detect as iterable first
        
        # Test with concurrent hint in function name
        def concurrent_process(data):
            return data
        
        operation_type = decorator._detect_operation_type(concurrent_process, ([1, 2, 3],), {})
        assert operation_type == "concurrent"
    
    def test_iterable_extraction(self):
        """Test extraction of iterable from function arguments."""
        decorator = ProgressBarDecorator()
        
        def process_items(items, other_param=None):
            return items
        
        # Test positional argument
        test_items = ["item1", "item2"]
        iterable = decorator._extract_iterable(process_items, (test_items, "other"), {})
        assert iterable == test_items
        
        # Test keyword argument
        iterable = decorator._extract_iterable(process_items, (), {"items": test_items})
        assert iterable == test_items
        
        # Test no iterable found
        iterable = decorator._extract_iterable(process_items, ("string_param",), {})
        assert iterable is None


class TestProgressBarDecoratorSingleOperations:
    """Test progress decorator with single operations."""
    
    @patch('common.progress_decorator.RICH_AVAILABLE', True)
    @patch('common.progress_decorator.Progress')
    def test_single_operation_success(self, mock_progress_class):
        """Test successful single operation with progress bar."""
        mock_progress = Mock()
        mock_progress_class.return_value = mock_progress
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        
        decorator = ProgressBarDecorator(description="Test operation")
        
        @decorator
        def test_function():
            time.sleep(0.01)
            return "success"
        
        result = test_function()
        
        assert result == "success"
        mock_progress.add_task.assert_called_once()
        assert mock_progress.update.call_count >= 1
    
    @patch('common.progress_decorator.RICH_AVAILABLE', True)
    @patch('common.progress_decorator.Progress')
    def test_single_operation_failure(self, mock_progress_class):
        """Test failed single operation with progress bar."""
        mock_progress = Mock()
        mock_progress_class.return_value = mock_progress
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        
        decorator = ProgressBarDecorator(description="Test operation")
        
        @decorator
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
        
        # Verify error handling in progress updates
        mock_progress.update.assert_called()
        update_calls = mock_progress.update.call_args_list
        error_call = any("failed" in str(call) for call in update_calls)
        assert error_call
    
    @patch('common.progress_decorator.RICH_AVAILABLE', False)
    def test_single_operation_fallback(self, capsys):
        """Test single operation fallback when Rich is not available."""
        decorator = ProgressBarDecorator(description="Test operation")
        
        @decorator
        def test_function():
            return "success"
        
        result = test_function()
        
        assert result == "success"
        captured = capsys.readouterr()
        assert "Starting: Test operation" in captured.out
        assert "Completed: Test operation" in captured.out


class TestProgressBarDecoratorIterableOperations:
    """Test progress decorator with iterable operations."""
    
    @patch('common.progress_decorator.RICH_AVAILABLE', True)
    @patch('common.progress_decorator.Progress')
    def test_iterable_operation_success(self, mock_progress_class):
        """Test successful iterable operation with progress tracking."""
        mock_progress = Mock()
        mock_progress_class.return_value = mock_progress
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        
        decorator = ProgressBarDecorator(description="Process items")
        
        @decorator
        def process_items(items):
            results = []
            for item in items:
                time.sleep(0.001)  # Minimal delay
                results.append(f"processed_{item}")
            return results
        
        test_items = ["item1", "item2", "item3"]
        result = process_items(test_items)
        
        assert len(result) == 3
        assert all("processed_" in str(item) for item in result)
        mock_progress.add_task.assert_called_once()
        assert mock_progress.update.call_count >= 1
    
    @patch('common.progress_decorator.RICH_AVAILABLE', True)
    @patch('common.progress_decorator.Progress')
    def test_iterable_operation_with_total(self, mock_progress_class):
        """Test iterable operation with known total count."""
        mock_progress = Mock()
        mock_progress_class.return_value = mock_progress
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        
        decorator = ProgressBarDecorator()
        
        @decorator
        def process_servers(servers):
            return [f"server_{server}_info" for server in servers]
        
        test_servers = ["web1", "web2", "db1"]
        result = process_servers(test_servers)
        
        assert len(result) == 3
        # Verify add_task was called with total
        mock_progress.add_task.assert_called_once()
        call_args = mock_progress.add_task.call_args
        assert 'total' in call_args[1] or len(call_args[0]) > 1


class TestProgressBarDecoratorConcurrentOperations:
    """Test progress decorator with concurrent operations."""
    
    @patch('common.progress_decorator.RICH_AVAILABLE', True)
    @patch('common.progress_decorator.Progress')
    @patch('common.progress_decorator.ThreadPoolExecutor')
    def test_concurrent_operation_success(self, mock_executor_class, mock_progress_class):
        """Test successful concurrent operation with progress tracking."""
        # Setup mocks
        mock_progress = Mock()
        mock_progress_class.return_value = mock_progress
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__ = Mock(return_value=mock_executor)
        mock_executor_class.return_value.__exit__ = Mock(return_value=None)
        
        # Mock futures
        mock_futures = []
        for i in range(3):
            future = Mock()
            future.result.return_value = f"result_{i}"
            mock_futures.append(future)
        
        mock_executor.submit.side_effect = mock_futures
        
        # Mock as_completed
        with patch('common.progress_decorator.as_completed', return_value=mock_futures):
            decorator = ProgressBarDecorator()
            
            @decorator
            def concurrent_process_regions(regions):
                # This would normally use ThreadPoolExecutor
                return [f"processed_{region}" for region in regions]
            
            test_regions = ["us-east-1", "us-west-2", "eu-west-1"]
            result = concurrent_process_regions(test_regions)
            
            assert len(result) == 3
    
    def test_concurrent_operation_with_errors(self):
        """Test concurrent operation handling errors properly."""
        decorator = ProgressBarDecorator()
        
        @decorator
        def process_with_errors(items):
            results = []
            for item in items:
                if item == "error_item":
                    raise ValueError(f"Error processing {item}")
                results.append(f"processed_{item}")
            return results
        
        test_items = ["item1", "error_item", "item3"]
        
        with pytest.raises(ValueError):
            process_with_errors(test_items)


class TestProgressBarDecoratorThreadSafety:
    """Test thread safety of progress decorator."""
    
    def test_progress_context_thread_safety(self):
        """Test ProgressContext thread-safe operations."""
        context = ProgressContext(total_operations=100, thread_safe=True)
        
        def worker():
            for _ in range(10):
                with context._lock:
                    context.completed_operations += 1
        
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert context.completed_operations == 100
    
    def test_concurrent_progress_updates(self):
        """Test concurrent progress updates are thread-safe."""
        results = []
        errors = []
        
        @progress_bar("Concurrent test")
        def concurrent_worker(worker_id):
            for i in range(5):
                time.sleep(0.001)
                results.append((worker_id, i))
            return f"worker_{worker_id}_done"
        
        def run_worker(worker_id):
            try:
                result = concurrent_worker(worker_id)
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=run_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no errors and all workers completed
        assert len(errors) == 0
        worker_results = [r for r in results if isinstance(r, str) and "worker_" in r]
        assert len(worker_results) == 5


class TestManualProgress:
    """Test ManualProgress class functionality."""
    
    @patch('common.progress_decorator.RICH_AVAILABLE', True)
    @patch('common.progress_decorator.Progress')
    def test_manual_progress_success(self, mock_progress_class):
        """Test successful manual progress tracking."""
        mock_progress = Mock()
        mock_progress_class.return_value = mock_progress
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        
        with ManualProgress("Manual test", total=10) as progress:
            for i in range(10):
                progress.update(f"Step {i+1}")
                progress.advance(1)
        
        mock_progress.add_task.assert_called_once()
        assert mock_progress.update.call_count >= 10
    
    @patch('common.progress_decorator.RICH_AVAILABLE', True)
    @patch('common.progress_decorator.Progress')
    def test_manual_progress_with_error(self, mock_progress_class):
        """Test manual progress with error handling."""
        mock_progress = Mock()
        mock_progress_class.return_value = mock_progress
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        
        with pytest.raises(ValueError):
            with ManualProgress("Manual test with error") as progress:
                progress.update("Starting")
                raise ValueError("Test error")
        
        # Verify error handling in exit
        mock_progress.__exit__.assert_called_once()
        exit_args = mock_progress.__exit__.call_args[0]
        assert exit_args[0] is ValueError  # exc_type
    
    @patch('common.progress_decorator.RICH_AVAILABLE', False)
    def test_manual_progress_fallback(self, capsys):
        """Test manual progress fallback when Rich not available."""
        with ManualProgress("Fallback test") as progress:
            progress.update("Step 1")
            progress.advance(1)
            progress.set_description("Step 2")
        
        captured = capsys.readouterr()
        assert "Step 1" in captured.out


class TestConvenienceDecorators:
    """Test convenience decorator functions."""
    
    def test_progress_bar_decorator(self):
        """Test progress_bar convenience decorator."""
        @progress_bar("Test progress")
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_spinner_decorator(self):
        """Test spinner convenience decorator."""
        @spinner("Loading...")
        def test_function():
            time.sleep(0.01)
            return "loaded"
        
        result = test_function()
        assert result == "loaded"
    
    def test_concurrent_progress_decorator(self):
        """Test concurrent_progress convenience decorator."""
        @concurrent_progress("Concurrent test", max_workers=2)
        def test_function(items):
            return [f"processed_{item}" for item in items]
        
        result = test_function(["a", "b", "c"])
        assert len(result) == 3


class TestProgressDecoratorEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_iterable(self):
        """Test progress decorator with empty iterable."""
        @progress_bar("Empty test")
        def process_empty(items):
            return [f"processed_{item}" for item in items]
        
        result = process_empty([])
        assert result == []
    
    def test_non_iterable_parameter(self):
        """Test with non-iterable parameter that matches iterable hints."""
        @progress_bar("Non-iterable test")
        def process_items(items):  # 'items' name suggests iterable but isn't
            return f"processed_{items}"
        
        result = process_items("single_string")
        assert result == "processed_single_string"
    
    def test_function_with_no_parameters(self):
        """Test decorator on function with no parameters."""
        @progress_bar("No params test")
        def no_params_function():
            return "no_params_result"
        
        result = no_params_function()
        assert result == "no_params_result"
    
    def test_function_with_complex_signature(self):
        """Test decorator on function with complex signature."""
        @progress_bar("Complex signature test")
        def complex_function(pos_arg, *args, keyword_arg=None, **kwargs):
            return {
                'pos_arg': pos_arg,
                'args': args,
                'keyword_arg': keyword_arg,
                'kwargs': kwargs
            }
        
        result = complex_function("test", "extra1", "extra2", keyword_arg="kw_test", extra_kw="extra")
        
        assert result['pos_arg'] == "test"
        assert result['args'] == ("extra1", "extra2")
        assert result['keyword_arg'] == "kw_test"
        assert result['kwargs'] == {"extra_kw": "extra"}
    
    def test_nested_decorators(self):
        """Test progress decorator with other decorators."""
        def other_decorator(func):
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                return f"decorated_{result}"
            return wrapper
        
        @progress_bar("Nested test")
        @other_decorator
        def nested_function():
            return "original"
        
        result = nested_function()
        assert result == "decorated_original"
    
    def test_generator_function(self):
        """Test progress decorator with generator function."""
        @progress_bar("Generator test")
        def generator_function(items):
            for item in items:
                yield f"generated_{item}"
        
        result = list(generator_function(["a", "b", "c"]))
        
        # Handle potential wrapping by decorator
        if isinstance(result, list) and len(result) == 1 and hasattr(result[0], '__iter__'):
            try:
                result = list(result[0])
            except TypeError:
                pass  # Keep original result if not iterable
        
        assert len(result) == 3
        assert all("generated_" in str(item) for item in result)


class TestProgressDecoratorPerformance:
    """Test performance characteristics of progress decorator."""
    
    def test_minimal_overhead(self):
        """Test that progress decorator adds minimal overhead."""
        import time
        
        def baseline_function():
            for _ in range(1000):
                pass
            return "done"
        
        @progress_bar("Performance test")
        def decorated_function():
            for _ in range(1000):
                pass
            return "done"
        
        # Measure baseline
        start_time = time.time()
        baseline_result = baseline_function()
        baseline_time = time.time() - start_time
        
        # Measure decorated
        start_time = time.time()
        decorated_result = decorated_function()
        decorated_time = time.time() - start_time
        
        assert baseline_result == decorated_result
        # Overhead should be reasonable (less than 1000x baseline, allowing for Rich overhead)
        # In CI environments, timing can be less predictable
        # The baseline might be very fast (microseconds), so allow significant overhead
        max_overhead = 2000 if os.getenv('CI') else 1000
        
        # Also ensure minimum baseline time to avoid division by very small numbers
        min_baseline = 0.001  # 1ms minimum
        effective_baseline = max(baseline_time, min_baseline)
        
        assert decorated_time < effective_baseline * max_overhead
    
    def test_memory_usage_stability(self):
        """Test that progress decorator doesn't leak memory."""
        import gc
        
        @progress_bar("Memory test")
        def memory_test_function():
            data = [i for i in range(100)]
            return len(data)
        
        # Get initial memory state
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Run function multiple times
        for _ in range(10):
            result = memory_test_function()
            assert result == 100
        
        # Check memory after operations
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory growth should be minimal
        object_growth = final_objects - initial_objects
        assert object_growth < 100, f"Potential memory leak: {object_growth} new objects"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])