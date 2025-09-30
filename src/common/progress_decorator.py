"""
Progress Bar Decorator Infrastructure

This module provides a comprehensive progress bar decorator system for the IC CLI tool.
It offers thread-safe progress tracking with Rich display components including spinners,
progress bars, and task progress columns.

Features:
- Automatic operation type detection (single vs multi-threaded)
- Thread-safe progress updates
- Error handling that preserves progress display integrity
- Execution time tracking
- Customizable progress descriptions
- Graceful degradation for non-Rich terminals
"""

import functools
import inspect
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union, Iterator
from contextlib import contextmanager

try:
    from rich.console import Console
    from rich.progress import (
        Progress, 
        SpinnerColumn, 
        TextColumn, 
        BarColumn, 
        TaskProgressColumn,
        TimeElapsedColumn,
        MofNCompleteColumn
    )
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class ProgressContext:
    """Context information for progress tracking."""
    total_operations: int
    completed_operations: int = 0
    current_operation: str = ""
    start_time: float = field(default_factory=time.time)
    errors: List[str] = field(default_factory=list)
    thread_safe: bool = True
    _lock: threading.Lock = field(default_factory=threading.Lock)


class ProgressBarDecorator:
    """
    Decorator for adding progress bars to long-running functions.
    
    This decorator automatically detects operation types and provides appropriate
    progress feedback using Rich components. It handles both single and multi-threaded
    operations with thread-safe progress updates.
    
    Args:
        description: Custom description for the progress bar
        show_time: Whether to show elapsed time
        show_spinner: Whether to show a spinner
        auto_detect: Whether to automatically detect iterable operations
        max_workers: Maximum number of threads for concurrent operations
    """
    
    def __init__(
        self,
        description: Optional[str] = None,
        show_time: bool = True,
        show_spinner: bool = True,
        auto_detect: bool = True,
        max_workers: Optional[int] = None
    ):
        self.description = description
        self.show_time = show_time
        self.show_spinner = show_spinner
        self.auto_detect = auto_detect
        self.max_workers = max_workers or 4
        self.console = Console() if RICH_AVAILABLE else None
        
    def __call__(self, func: Callable) -> Callable:
        """Apply the progress bar decorator to a function."""
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract function name for default description
            func_name = getattr(func, '__name__', 'Operation')
            display_name = self.description or f"Running {func_name.replace('_', ' ').title()}"
            
            # Check if we should use progress bars
            if not RICH_AVAILABLE:
                return self._fallback_execution(func, display_name, *args, **kwargs)
            
            # Detect operation type
            operation_type = self._detect_operation_type(func, args, kwargs)
            
            if operation_type == 'iterable':
                return self._handle_iterable_operation(func, display_name, *args, **kwargs)
            elif operation_type == 'concurrent':
                return self._handle_concurrent_operation(func, display_name, *args, **kwargs)
            else:
                return self._handle_single_operation(func, display_name, *args, **kwargs)
                
        return wrapper
    
    def _detect_operation_type(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """
        Detect the type of operation based on function signature and arguments.
        
        Returns:
            'iterable': Function processes a collection of items
            'concurrent': Function should run with concurrent execution
            'single': Single operation function
        """
        if not self.auto_detect:
            return 'single'
            
        # Check function signature for hints
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        # Look for common iterable parameter names
        iterable_hints = ['items', 'resources', 'servers', 'instances', 'regions', 'accounts']
        for param_name in param_names:
            if any(hint in param_name.lower() for hint in iterable_hints):
                # Check if corresponding argument is iterable
                try:
                    param_index = param_names.index(param_name)
                    if param_index < len(args):
                        arg_value = args[param_index]
                        if hasattr(arg_value, '__iter__') and not isinstance(arg_value, (str, bytes)):
                            return 'iterable'
                except (ValueError, IndexError):
                    pass
        
        # Check kwargs for iterable values
        for key, value in kwargs.items():
            if any(hint in key.lower() for hint in iterable_hints):
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    return 'iterable'
        
        # Check for concurrent execution hints
        concurrent_hints = ['parallel', 'concurrent', 'multi_thread', 'async']
        func_name_lower = func.__name__.lower()
        if any(hint in func_name_lower for hint in concurrent_hints):
            return 'concurrent'
            
        return 'single'
    
    def _handle_single_operation(self, func: Callable, description: str, *args, **kwargs) -> Any:
        """Handle single operation with spinner progress."""
        with self._create_progress_context(description, show_progress=False) as (progress, task_id):
            try:
                progress.update(task_id, description=f"[cyan]{description}[/cyan]")
                result = func(*args, **kwargs)
                progress.update(task_id, description=f"[green]✓ {description} completed[/green]")
                return result
            except Exception as e:
                progress.update(task_id, description=f"[red]✗ {description} failed[/red]")
                raise
    
    def _handle_iterable_operation(self, func: Callable, description: str, *args, **kwargs) -> Any:
        """Handle iterable operation with progress bar."""
        # Try to extract iterable from arguments
        iterable = self._extract_iterable(func, args, kwargs)
        
        if iterable is None:
            return self._handle_single_operation(func, description, *args, **kwargs)
        
        total_items = len(iterable) if hasattr(iterable, '__len__') else None
        
        with self._create_progress_context(description, total=total_items) as (progress, task_id):
            try:
                # Create a wrapper that updates progress
                def progress_wrapper(item, index):
                    progress.update(task_id, 
                                  description=f"[cyan]{description}[/cyan] ({index + 1}/{total_items or '?'})",
                                  advance=1)
                    return item
                
                # Modify the function to track progress
                result = self._execute_with_progress(func, iterable, progress_wrapper, *args, **kwargs)
                
                progress.update(task_id, description=f"[green]✓ {description} completed[/green]")
                return result
                
            except Exception as e:
                progress.update(task_id, description=f"[red]✗ {description} failed[/red]")
                raise
    
    def _handle_concurrent_operation(self, func: Callable, description: str, *args, **kwargs) -> Any:
        """Handle concurrent operation with thread-safe progress updates."""
        iterable = self._extract_iterable(func, args, kwargs)
        
        if iterable is None:
            return self._handle_single_operation(func, description, *args, **kwargs)
        
        total_items = len(iterable) if hasattr(iterable, '__len__') else None
        context = ProgressContext(total_operations=total_items or 0, thread_safe=True)
        
        with self._create_progress_context(description, total=total_items) as (progress, task_id):
            try:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all tasks
                    future_to_item = {}
                    for i, item in enumerate(iterable):
                        future = executor.submit(self._execute_single_item, func, item, i, context)
                        future_to_item[future] = (item, i)
                    
                    # Process completed tasks
                    results = []
                    for future in as_completed(future_to_item):
                        item, index = future_to_item[future]
                        try:
                            result = future.result()
                            results.append((index, result))
                            
                            with context._lock:
                                context.completed_operations += 1
                                progress.update(task_id,
                                              description=f"[cyan]{description}[/cyan] ({context.completed_operations}/{total_items or '?'})",
                                              advance=1)
                        except Exception as e:
                            with context._lock:
                                context.errors.append(f"Item {index}: {str(e)}")
                                context.completed_operations += 1
                                progress.update(task_id, advance=1)
                
                # Sort results by original index
                results.sort(key=lambda x: x[0])
                final_results = [result for _, result in results]
                
                if context.errors:
                    error_summary = f"Completed with {len(context.errors)} errors"
                    progress.update(task_id, description=f"[yellow]⚠ {description} - {error_summary}[/yellow]")
                else:
                    progress.update(task_id, description=f"[green]✓ {description} completed[/green]")
                
                return final_results
                
            except Exception as e:
                progress.update(task_id, description=f"[red]✗ {description} failed[/red]")
                raise
    
    def _execute_single_item(self, func: Callable, item: Any, index: int, context: ProgressContext) -> Any:
        """Execute function on a single item with error handling."""
        try:
            # This is a simplified version - in practice, you'd need to adapt
            # the function call based on the specific function signature
            return func(item)
        except Exception as e:
            with context._lock:
                context.errors.append(f"Item {index}: {str(e)}")
            raise
    
    def _extract_iterable(self, func: Callable, args: tuple, kwargs: dict) -> Optional[Any]:
        """Extract iterable from function arguments."""
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        # Look for iterable parameters
        iterable_hints = ['items', 'resources', 'servers', 'instances', 'regions', 'accounts']
        
        # Check positional arguments
        for i, param_name in enumerate(param_names):
            if i < len(args) and any(hint in param_name.lower() for hint in iterable_hints):
                arg_value = args[i]
                if hasattr(arg_value, '__iter__') and not isinstance(arg_value, (str, bytes)):
                    return arg_value
        
        # Check keyword arguments
        for key, value in kwargs.items():
            if any(hint in key.lower() for hint in iterable_hints):
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    return value
        
        return None
    
    def _execute_with_progress(self, func: Callable, iterable: Any, progress_wrapper: Callable, *args, **kwargs) -> Any:
        """Execute function with progress tracking for iterable operations."""
        # For iterable operations, we need to call the original function once
        # and let it handle the iterable, while we track progress
        
        # Update progress as we go through the iterable
        for i, item in enumerate(iterable):
            progress_wrapper(item, i)
        
        # Call the original function with the original arguments
        result = func(*args, **kwargs)
        return result
    
    @contextmanager
    def _create_progress_context(self, description: str, total: Optional[int] = None, show_progress: bool = True):
        """Create a Rich progress context with appropriate columns."""
        if not RICH_AVAILABLE:
            yield None, None
            return
        
        columns = []
        
        if self.show_spinner:
            columns.append(SpinnerColumn())
        
        columns.append(TextColumn("[progress.description]{task.description}"))
        
        if show_progress and total is not None:
            columns.extend([
                BarColumn(),
                MofNCompleteColumn(),
                TaskProgressColumn()
            ])
        
        if self.show_time:
            columns.append(TimeElapsedColumn())
        
        progress = Progress(*columns, console=self.console)
        
        with progress:
            task_id = progress.add_task(description, total=total)
            yield progress, task_id
    
    def _fallback_execution(self, func: Callable, description: str, *args, **kwargs) -> Any:
        """Fallback execution when Rich is not available."""
        print(f"Starting: {description}")
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            print(f"Completed: {description} (took {elapsed:.2f}s)")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"Failed: {description} (took {elapsed:.2f}s) - {str(e)}")
            raise


# Convenience decorators for common use cases
def progress_bar(description: Optional[str] = None, **kwargs) -> Callable:
    """
    Simple progress bar decorator.
    
    Args:
        description: Custom description for the progress bar
        **kwargs: Additional arguments passed to ProgressBarDecorator
    
    Example:
        @progress_bar("Processing servers")
        def process_servers(servers):
            # Function implementation
            pass
    """
    return ProgressBarDecorator(description=description, **kwargs)


def spinner(description: Optional[str] = None, **kwargs) -> Callable:
    """
    Spinner-only decorator for operations without known progress.
    
    Args:
        description: Custom description for the spinner
        **kwargs: Additional arguments passed to ProgressBarDecorator
    
    Example:
        @spinner("Connecting to API")
        def connect_to_api():
            # Function implementation
            pass
    """
    kwargs.setdefault('auto_detect', False)
    return ProgressBarDecorator(description=description, **kwargs)


def concurrent_progress(description: Optional[str] = None, max_workers: int = 4, **kwargs) -> Callable:
    """
    Progress bar decorator optimized for concurrent operations.
    
    Args:
        description: Custom description for the progress bar
        max_workers: Maximum number of concurrent threads
        **kwargs: Additional arguments passed to ProgressBarDecorator
    
    Example:
        @concurrent_progress("Processing regions", max_workers=8)
        def process_regions(regions):
            # Function implementation
            pass
    """
    return ProgressBarDecorator(
        description=description, 
        max_workers=max_workers,
        **kwargs
    )


# Utility functions for manual progress management
class ManualProgress:
    """
    Manual progress management for complex operations.
    
    Use this when you need fine-grained control over progress updates.
    
    Example:
        with ManualProgress("Complex operation", total=100) as progress:
            for i in range(100):
                # Do work
                progress.update(f"Step {i+1}")
                progress.advance(1)
    """
    
    def __init__(self, description: str, total: Optional[int] = None, **kwargs):
        self.description = description
        self.total = total
        self.kwargs = kwargs
        self.progress = None
        self.task_id = None
        self.console = Console() if RICH_AVAILABLE else None
    
    def __enter__(self):
        if RICH_AVAILABLE:
            columns = [
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
            ]
            
            if self.total is not None:
                columns.extend([
                    BarColumn(),
                    MofNCompleteColumn(),
                    TaskProgressColumn()
                ])
            
            columns.append(TimeElapsedColumn())
            
            self.progress = Progress(*columns, console=self.console)
            self.progress.__enter__()
            self.task_id = self.progress.add_task(self.description, total=self.total)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            if exc_type is None:
                self.progress.update(self.task_id, description=f"[green]✓ {self.description} completed[/green]")
            else:
                self.progress.update(self.task_id, description=f"[red]✗ {self.description} failed[/red]")
            self.progress.__exit__(exc_type, exc_val, exc_tb)
    
    def update(self, description: Optional[str] = None, advance: Optional[int] = None):
        """Update progress with new description and/or advance count."""
        if self.progress and self.task_id is not None:
            update_kwargs = {}
            if description:
                update_kwargs['description'] = f"[cyan]{description}[/cyan]"
            if advance is not None:
                update_kwargs['advance'] = advance
            
            if update_kwargs:
                self.progress.update(self.task_id, **update_kwargs)
        elif not RICH_AVAILABLE and description:
            print(f"Progress: {description}")
    
    def advance(self, amount: int = 1):
        """Advance progress by specified amount."""
        self.update(advance=amount)
    
    def set_description(self, description: str):
        """Set new description for the progress bar."""
        self.update(description=description)