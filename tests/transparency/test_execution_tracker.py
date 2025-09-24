#!/usr/bin/env python3
"""
Test Execution Transparency System

Provides detailed progress indicators, comprehensive result reporting, and actionable
debugging information for test execution across all platforms and services.

Requirements: 7.1, 7.2, 7.3, 7.6 - Test execution transparency and error reporting
"""

import os
import sys
import time
import json
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime, timedelta
import subprocess
import traceback
from collections import defaultdict

# Rich console imports for enhanced display
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import (
        Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, 
        TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn
    )
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.text import Text
    from rich.live import Live
    from rich.layout import Layout
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


class TestExecutionStatus(Enum):
    """Test execution status enumeration."""
    PENDING = "pending"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class TestCategory(Enum):
    """Test category enumeration."""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"
    E2E = "e2e"


@dataclass
class TestMetrics:
    """Test execution metrics."""
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    assertions_count: int = 0
    setup_time: float = 0.0
    teardown_time: float = 0.0


@dataclass
class TestFailureInfo:
    """Detailed test failure information."""
    error_type: str = ""
    error_message: str = ""
    traceback: str = ""
    line_number: int = 0
    file_path: str = ""
    assertion_details: str = ""
    suggested_fix: str = ""
    related_logs: List[str] = field(default_factory=list)


@dataclass
class TestExecutionContext:
    """Test execution context information."""
    platform: str
    service: str
    test_category: TestCategory
    test_file: str
    test_function: str = ""
    test_class: str = ""
    environment: str = "local"
    ci_provider: str = ""
    python_version: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)


@dataclass
class TestResult:
    """Comprehensive test result with detailed information."""
    context: TestExecutionContext
    status: TestExecutionStatus
    metrics: TestMetrics = field(default_factory=TestMetrics)
    failure_info: Optional[TestFailureInfo] = None
    output: str = ""
    warnings: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)


class TestProgressTracker:
    """Real-time test progress tracking with detailed indicators."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or (Console() if RICH_AVAILABLE else None)
        self.progress_tasks: Dict[str, TaskID] = {}
        self.current_tests: Dict[str, TestResult] = {}
        self.completed_tests: List[TestResult] = []
        self.start_time = time.time()
        self.lock = threading.Lock()
        
    def create_progress_display(self, total_tests: int) -> Optional[Progress]:
        """Create rich progress display."""
        if not RICH_AVAILABLE or not self.console:
            return None
            
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console
        )
    
    def start_test(self, context: TestExecutionContext) -> str:
        """Start tracking a test execution."""
        test_id = f"{context.platform}/{context.service}/{context.test_category.value}/{context.test_file}"
        
        with self.lock:
            result = TestResult(
                context=context,
                status=TestExecutionStatus.INITIALIZING,
                metrics=TestMetrics(start_time=time.time())
            )
            self.current_tests[test_id] = result
        
        if self.console:
            self.console.print(f"🚀 Starting: {test_id}")
        
        return test_id
    
    def update_test_status(self, test_id: str, status: TestExecutionStatus, 
                          details: Optional[str] = None):
        """Update test execution status."""
        with self.lock:
            if test_id in self.current_tests:
                self.current_tests[test_id].status = status
                
                if details and self.console:
                    status_icon = {
                        TestExecutionStatus.INITIALIZING: "🔄",
                        TestExecutionStatus.RUNNING: "⚡",
                        TestExecutionStatus.PASSED: "✅",
                        TestExecutionStatus.FAILED: "❌",
                        TestExecutionStatus.SKIPPED: "⏭️",
                        TestExecutionStatus.ERROR: "💥",
                        TestExecutionStatus.TIMEOUT: "⏰",
                        TestExecutionStatus.CANCELLED: "🚫"
                    }.get(status, "❓")
                    
                    self.console.print(f"{status_icon} {test_id}: {details}")
    
    def complete_test(self, test_id: str, result: TestResult):
        """Mark test as completed and move to completed list."""
        with self.lock:
            if test_id in self.current_tests:
                result.metrics.end_time = time.time()
                result.metrics.duration = result.metrics.end_time - result.metrics.start_time
                
                self.completed_tests.append(result)
                del self.current_tests[test_id]
                
                # Display completion status
                if self.console:
                    status_icon = {
                        TestExecutionStatus.PASSED: "✅",
                        TestExecutionStatus.FAILED: "❌",
                        TestExecutionStatus.SKIPPED: "⏭️",
                        TestExecutionStatus.ERROR: "💥",
                        TestExecutionStatus.TIMEOUT: "⏰"
                    }.get(result.status, "❓")
                    
                    duration_str = f"({result.metrics.duration:.2f}s)"
                    self.console.print(f"{status_icon} Completed: {test_id} {duration_str}")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current execution status summary."""
        with self.lock:
            total_duration = time.time() - self.start_time
            
            return {
                "total_duration": total_duration,
                "running_tests": len(self.current_tests),
                "completed_tests": len(self.completed_tests),
                "current_tests": list(self.current_tests.keys()),
                "status_counts": self._count_statuses()
            }
    
    def _count_statuses(self) -> Dict[str, int]:
        """Count tests by status."""
        counts = defaultdict(int)
        
        for result in self.completed_tests:
            counts[result.status.value] += 1
            
        for result in self.current_tests.values():
            counts[result.status.value] += 1
            
        return dict(counts)


class TestErrorAnalyzer:
    """Analyzes test failures and provides actionable debugging information."""
    
    def __init__(self):
        self.error_patterns = self._load_error_patterns()
        self.fix_suggestions = self._load_fix_suggestions()
    
    def analyze_failure(self, result: TestResult) -> TestFailureInfo:
        """Analyze test failure and provide detailed information."""
        if not result.failure_info:
            result.failure_info = TestFailureInfo()
        
        failure_info = result.failure_info
        
        # Extract error information from output
        self._extract_error_details(result.output, failure_info)
        
        # Generate suggested fixes
        failure_info.suggested_fix = self._generate_fix_suggestion(failure_info, result.context)
        
        # Find related logs
        failure_info.related_logs = self._find_related_logs(result.context, failure_info)
        
        return failure_info
    
    def _extract_error_details(self, output: str, failure_info: TestFailureInfo):
        """Extract detailed error information from test output."""
        lines = output.split('\n')
        
        for i, line in enumerate(lines):
            # Look for common error patterns
            if 'AssertionError' in line:
                failure_info.error_type = 'AssertionError'
                failure_info.error_message = line.strip()
                
                # Look for assertion details in surrounding lines
                for j in range(max(0, i-3), min(len(lines), i+3)):
                    if 'assert' in lines[j].lower():
                        failure_info.assertion_details = lines[j].strip()
                        break
            
            elif 'ImportError' in line or 'ModuleNotFoundError' in line:
                failure_info.error_type = 'ImportError'
                failure_info.error_message = line.strip()
            
            elif 'ConnectionError' in line or 'TimeoutError' in line:
                failure_info.error_type = 'ConnectionError'
                failure_info.error_message = line.strip()
            
            elif 'FileNotFoundError' in line:
                failure_info.error_type = 'FileNotFoundError'
                failure_info.error_message = line.strip()
            
            # Extract file path and line number
            if '.py:' in line and 'line' in line.lower():
                parts = line.split('.py:')
                if len(parts) > 1:
                    failure_info.file_path = parts[0] + '.py'
                    try:
                        failure_info.line_number = int(parts[1].split()[0])
                    except (ValueError, IndexError):
                        pass
    
    def _generate_fix_suggestion(self, failure_info: TestFailureInfo, 
                               context: TestExecutionContext) -> str:
        """Generate actionable fix suggestions based on error type and context."""
        suggestions = []
        
        if failure_info.error_type == 'ImportError':
            suggestions.append("Check if the required module is installed: pip install <module_name>")
            suggestions.append("Verify the module path is correct in PYTHONPATH")
            suggestions.append("Ensure the module exists in the expected location")
        
        elif failure_info.error_type == 'AssertionError':
            suggestions.append("Review the assertion logic and expected vs actual values")
            suggestions.append("Check if test data or mock responses have changed")
            suggestions.append("Verify the test setup and preconditions")
        
        elif failure_info.error_type == 'ConnectionError':
            suggestions.append("Check if the service endpoint is accessible")
            suggestions.append("Verify network connectivity and firewall settings")
            suggestions.append("Ensure mock services are properly configured for CI")
            
            if context.environment == "ci":
                suggestions.append("Verify CI environment has proper mock configurations")
        
        elif failure_info.error_type == 'FileNotFoundError':
            suggestions.append("Check if the required file exists in the expected location")
            suggestions.append("Verify file permissions and access rights")
            suggestions.append("Ensure test data files are included in the repository")
        
        # Platform-specific suggestions
        if context.platform in ['ncp', 'ncpgov']:
            suggestions.append(f"Verify {context.platform.upper()} configuration is properly set up")
            suggestions.append(f"Check ~/.{context.platform}/config.yaml exists and is valid")
            suggestions.append("Ensure mock data is available for CI testing")
        
        return " | ".join(suggestions) if suggestions else "No specific suggestions available"
    
    def _find_related_logs(self, context: TestExecutionContext, 
                          failure_info: TestFailureInfo) -> List[str]:
        """Find related log files that might contain additional information."""
        log_paths = []
        
        # Common log locations
        potential_logs = [
            f"/tmp/{context.platform}_test.log",
            f"/tmp/ic_test_{context.service}.log",
            f"logs/{context.platform}_{context.service}.log",
            "/tmp/pytest.log",
            "/tmp/ci_test_runner.log"
        ]
        
        for log_path in potential_logs:
            if os.path.exists(log_path):
                log_paths.append(log_path)
        
        return log_paths
    
    def _load_error_patterns(self) -> Dict[str, List[str]]:
        """Load common error patterns for recognition."""
        return {
            'import_errors': [
                'ImportError', 'ModuleNotFoundError', 'No module named'
            ],
            'connection_errors': [
                'ConnectionError', 'TimeoutError', 'ConnectTimeout', 'ReadTimeout'
            ],
            'assertion_errors': [
                'AssertionError', 'assert', 'Expected', 'Actual'
            ],
            'file_errors': [
                'FileNotFoundError', 'PermissionError', 'IsADirectoryError'
            ]
        }
    
    def _load_fix_suggestions(self) -> Dict[str, List[str]]:
        """Load fix suggestions for common error types."""
        return {
            'ImportError': [
                "Install missing dependencies",
                "Check PYTHONPATH configuration",
                "Verify module installation"
            ],
            'ConnectionError': [
                "Check network connectivity",
                "Verify service endpoints",
                "Configure mock services for testing"
            ],
            'AssertionError': [
                "Review test logic and expectations",
                "Check test data validity",
                "Verify mock responses"
            ]
        }


class TestReportGenerator:
    """Generates comprehensive test execution reports."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or (Console() if RICH_AVAILABLE else None)
        self.error_analyzer = TestErrorAnalyzer()
    
    def generate_summary_report(self, results: List[TestResult]) -> Dict[str, Any]:
        """Generate comprehensive test execution summary."""
        if not results:
            return {"error": "No test results available"}
        
        # Calculate overall statistics
        total_tests = len(results)
        status_counts = defaultdict(int)
        platform_stats = defaultdict(lambda: defaultdict(int))
        service_stats = defaultdict(lambda: defaultdict(int))
        category_stats = defaultdict(lambda: defaultdict(int))
        
        total_duration = 0.0
        fastest_test = None
        slowest_test = None
        
        for result in results:
            status_counts[result.status.value] += 1
            platform_stats[result.context.platform][result.status.value] += 1
            service_stats[result.context.service][result.status.value] += 1
            category_stats[result.context.test_category.value][result.status.value] += 1
            
            total_duration += result.metrics.duration
            
            if fastest_test is None or result.metrics.duration < fastest_test.metrics.duration:
                fastest_test = result
            if slowest_test is None or result.metrics.duration > slowest_test.metrics.duration:
                slowest_test = result
        
        # Calculate success rate
        passed_tests = status_counts.get('passed', 0)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        return {
            "summary": {
                "total_tests": total_tests,
                "total_duration": total_duration,
                "average_duration": total_duration / total_tests if total_tests > 0 else 0,
                "success_rate": success_rate,
                "status_counts": dict(status_counts)
            },
            "performance": {
                "fastest_test": {
                    "name": f"{fastest_test.context.platform}/{fastest_test.context.service}/{fastest_test.context.test_file}",
                    "duration": fastest_test.metrics.duration
                } if fastest_test else None,
                "slowest_test": {
                    "name": f"{slowest_test.context.platform}/{slowest_test.context.service}/{slowest_test.context.test_file}",
                    "duration": slowest_test.metrics.duration
                } if slowest_test else None
            },
            "breakdowns": {
                "by_platform": dict(platform_stats),
                "by_service": dict(service_stats),
                "by_category": dict(category_stats)
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def display_detailed_summary(self, results: List[TestResult]):
        """Display detailed test execution summary with rich formatting."""
        if not self.console or not RICH_AVAILABLE:
            self._display_simple_summary(results)
            return
        
        report = self.generate_summary_report(results)
        
        # Main summary table
        summary_table = Table(title="🧪 Test Execution Summary", show_header=True)
        summary_table.add_column("Metric", style="cyan", width=20)
        summary_table.add_column("Value", style="magenta", width=15)
        summary_table.add_column("Details", style="green")
        
        summary = report["summary"]
        summary_table.add_row("Total Tests", str(summary["total_tests"]), "")
        summary_table.add_row("Duration", f"{summary['total_duration']:.2f}s", 
                             f"Avg: {summary['average_duration']:.2f}s")
        summary_table.add_row("Success Rate", f"{summary['success_rate']:.1f}%", "")
        
        # Status breakdown
        for status, count in summary["status_counts"].items():
            icon = {
                'passed': '✅', 'failed': '❌', 'skipped': '⏭️', 
                'error': '💥', 'timeout': '⏰'
            }.get(status, '❓')
            summary_table.add_row(f"{icon} {status.title()}", str(count), 
                                 f"{(count/summary['total_tests']*100):.1f}%")
        
        self.console.print(summary_table)
        
        # Platform breakdown
        if report["breakdowns"]["by_platform"]:
            platform_table = Table(title="🏗️ Platform Breakdown", show_header=True)
            platform_table.add_column("Platform", style="cyan")
            platform_table.add_column("Total", style="white")
            platform_table.add_column("✅ Passed", style="green")
            platform_table.add_column("❌ Failed", style="red")
            platform_table.add_column("⏭️ Skipped", style="yellow")
            platform_table.add_column("💥 Errors", style="magenta")
            
            for platform, stats in report["breakdowns"]["by_platform"].items():
                total = sum(stats.values())
                platform_table.add_row(
                    platform.upper(),
                    str(total),
                    str(stats.get('passed', 0)),
                    str(stats.get('failed', 0)),
                    str(stats.get('skipped', 0)),
                    str(stats.get('error', 0))
                )
            
            self.console.print(platform_table)
        
        # Display failures with detailed analysis
        failed_results = [r for r in results if r.status in [
            TestExecutionStatus.FAILED, TestExecutionStatus.ERROR, TestExecutionStatus.TIMEOUT
        ]]
        
        if failed_results:
            self.console.print("\n[red]❌ Detailed Failure Analysis:[/red]")
            
            for result in failed_results:
                failure_info = self.error_analyzer.analyze_failure(result)
                
                failure_panel = Panel(
                    self._format_failure_details(result, failure_info),
                    title=f"❌ {result.context.platform}/{result.context.service}/{result.context.test_file}",
                    border_style="red"
                )
                self.console.print(failure_panel)
    
    def _format_failure_details(self, result: TestResult, failure_info: TestFailureInfo) -> str:
        """Format failure details for display."""
        details = []
        
        if failure_info.error_type:
            details.append(f"Error Type: {failure_info.error_type}")
        
        if failure_info.error_message:
            details.append(f"Message: {failure_info.error_message}")
        
        if failure_info.file_path and failure_info.line_number:
            details.append(f"Location: {failure_info.file_path}:{failure_info.line_number}")
        
        if failure_info.assertion_details:
            details.append(f"Assertion: {failure_info.assertion_details}")
        
        if failure_info.suggested_fix:
            details.append(f"Suggested Fix: {failure_info.suggested_fix}")
        
        if failure_info.related_logs:
            details.append(f"Related Logs: {', '.join(failure_info.related_logs)}")
        
        details.append(f"Duration: {result.metrics.duration:.2f}s")
        
        return "\n".join(details)
    
    def _display_simple_summary(self, results: List[TestResult]):
        """Display simple text-based summary when rich is not available."""
        if not results:
            print("No test results available")
            return
        
        report = self.generate_summary_report(results)
        summary = report["summary"]
        
        print("\n" + "="*60)
        print("TEST EXECUTION SUMMARY")
        print("="*60)
        
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Duration: {summary['total_duration']:.2f}s (avg: {summary['average_duration']:.2f}s)")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        print("\nStatus Breakdown:")
        for status, count in summary["status_counts"].items():
            percentage = (count / summary['total_tests'] * 100) if summary['total_tests'] > 0 else 0
            print(f"  {status.title()}: {count} ({percentage:.1f}%)")
        
        print("\nPlatform Breakdown:")
        for platform, stats in report["breakdowns"]["by_platform"].items():
            total = sum(stats.values())
            passed = stats.get('passed', 0)
            print(f"  {platform.upper()}: {passed}/{total} passed")
        
        # Show failures
        failed_results = [r for r in results if r.status in [
            TestExecutionStatus.FAILED, TestExecutionStatus.ERROR
        ]]
        
        if failed_results:
            print(f"\nFailures ({len(failed_results)}):")
            for result in failed_results:
                print(f"  - {result.context.platform}/{result.context.service}/{result.context.test_file}")
        
        print("="*60)
    
    def save_report(self, results: List[TestResult], output_file: str):
        """Save detailed test report to file."""
        report_data = {
            "summary": self.generate_summary_report(results),
            "detailed_results": []
        }
        
        # Add detailed results with failure analysis
        for result in results:
            result_data = asdict(result)
            
            if result.status in [TestExecutionStatus.FAILED, TestExecutionStatus.ERROR]:
                failure_info = self.error_analyzer.analyze_failure(result)
                result_data["failure_analysis"] = asdict(failure_info)
            
            report_data["detailed_results"].append(result_data)
        
        # Save to file
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        if self.console:
            self.console.print(f"[green]📊 Detailed report saved to {output_file}[/green]")
        else:
            print(f"Report saved to {output_file}")


# Export main classes
__all__ = [
    'TestExecutionStatus', 'TestCategory', 'TestMetrics', 'TestFailureInfo',
    'TestExecutionContext', 'TestResult', 'TestProgressTracker', 
    'TestErrorAnalyzer', 'TestReportGenerator'
]