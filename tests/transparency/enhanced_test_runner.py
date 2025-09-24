#!/usr/bin/env python3
"""
Enhanced Test Runner with Transparency System

Integrates the test execution transparency system with the existing test infrastructure
to provide detailed progress indicators, comprehensive result reporting, and actionable
debugging information.

Requirements: 7.1, 7.2, 7.3, 7.6 - Enhanced test execution with transparency
"""

import os
import sys
import time
import json
import argparse
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.transparency.test_execution_tracker import (
    TestExecutionStatus, TestCategory, TestMetrics, TestFailureInfo,
    TestExecutionContext, TestResult, TestProgressTracker, 
    TestErrorAnalyzer, TestReportGenerator
)

# Import reliability tracking
try:
    from tests.reliability import (
        get_reliability_tracker, TestExecution as ReliabilityExecution
    )
    RELIABILITY_AVAILABLE = True
except ImportError:
    RELIABILITY_AVAILABLE = False

try:
    from rich.console import Console
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class EnhancedTestRunner:
    """Enhanced test runner with comprehensive transparency and reporting."""
    
    def __init__(self, base_path: str = "tests", verbose: bool = True):
        self.base_path = Path(base_path)
        self.verbose = verbose
        self.console = Console() if RICH_AVAILABLE else None
        
        # Initialize transparency components
        self.progress_tracker = TestProgressTracker(self.console)
        self.error_analyzer = TestErrorAnalyzer()
        self.report_generator = TestReportGenerator(self.console)
        
        # Test discovery and execution state
        self.discovered_tests: List[Tuple[str, str, str, Path]] = []
        self.test_results: List[TestResult] = []
        self.execution_start_time = 0.0
        
        # Platform and service mappings
        self.platform_services = {
            'aws': ['ec2', 's3', 'vpc', 'rds', 'cloudfront', 'ecs', 'eks', 'fargate', 'lb', 'msk', 'nat', 'sg', 'vpn'],
            'gcp': ['compute', 'storage', 'vpc', 'gke', 'sql', 'functions', 'run', 'firewall', 'lb', 'billing'],
            'ncp': ['ec2', 's3', 'vpc', 'sg', 'rds'],
            'ncpgov': ['ec2', 's3', 'vpc', 'sg', 'rds'],
            'oci': ['compute', 'storage', 'vcn', 'compartment', 'lb', 'nsg', 'vm', 'volume'],
            'azure': ['vm', 'storage', 'vnet', 'aks', 'aci', 'lb', 'nsg'],
            'cloudflare': ['dns']
        }
    
    def discover_tests(self, 
                      platforms: Optional[List[str]] = None,
                      services: Optional[List[str]] = None,
                      test_categories: Optional[List[str]] = None,
                      include_legacy: bool = True) -> List[Tuple[str, str, str, Path]]:
        """
        Discover test files with enhanced filtering and reporting.
        
        Returns:
            List of tuples: (platform, service, test_category, test_file_path)
        """
        if self.console:
            self.console.print("[bold blue]🔍 Discovering tests...[/bold blue]")
        
        discovered = []
        
        # Default to all platforms if none specified
        if platforms is None:
            platforms = list(self.platform_services.keys())
        
        # Default to all test categories if none specified
        if test_categories is None:
            test_categories = ['unit', 'integration', 'performance', 'security', 'e2e']
        
        # Discover platform-based tests
        for platform in platforms:
            if platform not in self.platform_services:
                if self.console:
                    self.console.print(f"[yellow]⚠️  Unknown platform '{platform}', skipping[/yellow]")
                continue
            
            platform_path = self.base_path / "platforms" / platform
            if not platform_path.exists():
                if self.console:
                    self.console.print(f"[yellow]⚠️  Platform directory '{platform}' not found[/yellow]")
                continue
            
            # Get services for this platform
            platform_services = services if services else self.platform_services[platform]
            
            for service in platform_services:
                if service not in self.platform_services[platform]:
                    continue
                
                service_path = platform_path / service
                if not service_path.exists():
                    continue
                
                for test_category in test_categories:
                    category_path = service_path / test_category
                    if not category_path.exists():
                        continue
                    
                    # Find all Python test files
                    for test_file in category_path.glob("test_*.py"):
                        discovered.append((platform, service, test_category, test_file))
        
        # Discover legacy tests if requested
        if include_legacy:
            legacy_tests = self._discover_legacy_tests(platforms, services)
            discovered.extend(legacy_tests)
        
        self.discovered_tests = discovered
        
        if self.console:
            self.console.print(f"[green]✅ Discovered {len(discovered)} test files[/green]")
        
        return discovered
    
    def _discover_legacy_tests(self, platforms: List[str], services: Optional[List[str]]) -> List[Tuple[str, str, str, Path]]:
        """Discover legacy test files outside the platform structure."""
        legacy_tests = []
        
        # Common legacy test patterns
        legacy_patterns = [
            "test_*.py",
            "test_*_*.py",
            "**/test_*.py"
        ]
        
        for pattern in legacy_patterns:
            for test_file in self.base_path.glob(pattern):
                # Skip if already in platforms directory
                if "platforms" in test_file.parts:
                    continue
                
                # Try to infer platform and service from filename
                platform, service, category = self._infer_test_metadata(test_file, platforms, services)
                if platform:
                    legacy_tests.append((platform, service, category, test_file))
        
        return legacy_tests
    
    def _infer_test_metadata(self, test_file: Path, platforms: List[str], 
                           services: Optional[List[str]]) -> Tuple[str, str, str]:
        """Infer platform, service, and category from test file name/path."""
        filename = test_file.name.lower()
        
        # Try to match platform
        platform = "unknown"
        for p in platforms:
            if p in filename or p in str(test_file).lower():
                platform = p
                break
        
        # Try to match service
        service = "general"
        if services:
            for s in services:
                if s in filename:
                    service = s
                    break
        else:
            # Check against all known services
            for p_services in self.platform_services.values():
                for s in p_services:
                    if s in filename:
                        service = s
                        break
        
        # Infer category from path or filename
        category = "unit"  # Default
        if "integration" in str(test_file).lower():
            category = "integration"
        elif "performance" in str(test_file).lower():
            category = "performance"
        elif "security" in str(test_file).lower():
            category = "security"
        elif "e2e" in str(test_file).lower() or "end_to_end" in str(test_file).lower():
            category = "e2e"
        
        return platform, service, category
    
    def display_test_discovery_summary(self):
        """Display comprehensive test discovery summary."""
        if not self.discovered_tests:
            if self.console:
                self.console.print("[yellow]No tests discovered[/yellow]")
            return
        
        if not RICH_AVAILABLE or not self.console:
            self._display_simple_discovery_summary()
            return
        
        # Group tests for display
        platform_groups = {}
        for platform, service, category, test_file in self.discovered_tests:
            if platform not in platform_groups:
                platform_groups[platform] = {}
            if service not in platform_groups[platform]:
                platform_groups[platform][service] = {}
            if category not in platform_groups[platform][service]:
                platform_groups[platform][service][category] = []
            platform_groups[platform][service][category].append(test_file.name)
        
        # Create summary table
        summary_table = Table(title="📋 Test Discovery Summary", show_header=True)
        summary_table.add_column("Platform", style="cyan", width=12)
        summary_table.add_column("Service", style="magenta", width=12)
        summary_table.add_column("Category", style="green", width=12)
        summary_table.add_column("Files", style="yellow", width=8)
        summary_table.add_column("Test Files", style="white")
        
        for platform, services in sorted(platform_groups.items()):
            for service, categories in sorted(services.items()):
                for category, files in sorted(categories.items()):
                    file_list = ", ".join(files[:3])  # Show first 3 files
                    if len(files) > 3:
                        file_list += f" ... (+{len(files)-3} more)"
                    
                    summary_table.add_row(
                        platform.upper(),
                        service,
                        category,
                        str(len(files)),
                        file_list
                    )
        
        self.console.print(summary_table)
        
        # Overall statistics
        total_platforms = len(platform_groups)
        total_services = sum(len(services) for services in platform_groups.values())
        total_files = len(self.discovered_tests)
        
        stats_panel = Panel(
            f"📊 Total: {total_files} test files across {total_platforms} platforms and {total_services} services",
            title="Discovery Statistics",
            border_style="green"
        )
        self.console.print(stats_panel)
    
    def _display_simple_discovery_summary(self):
        """Display simple text-based discovery summary."""
        platform_counts = {}
        for platform, service, category, test_file in self.discovered_tests:
            if platform not in platform_counts:
                platform_counts[platform] = 0
            platform_counts[platform] += 1
        
        print(f"\nDiscovered {len(self.discovered_tests)} test files:")
        for platform, count in sorted(platform_counts.items()):
            print(f"  {platform.upper()}: {count} files")
    
    def execute_tests(self, 
                     parallel: bool = False,
                     max_workers: int = 4,
                     fail_fast: bool = False,
                     timeout: int = 300) -> List[TestResult]:
        """Execute discovered tests with enhanced progress tracking and reporting."""
        if not self.discovered_tests:
            if self.console:
                self.console.print("[yellow]No tests to execute[/yellow]")
            return []
        
        self.execution_start_time = time.time()
        
        if self.console:
            self.console.print(f"[bold blue]🚀 Executing {len(self.discovered_tests)} tests...[/bold blue]")
        
        if parallel and max_workers > 1:
            return self._execute_tests_parallel(max_workers, fail_fast, timeout)
        else:
            return self._execute_tests_sequential(fail_fast, timeout)
    
    def _execute_tests_sequential(self, fail_fast: bool, timeout: int) -> List[TestResult]:
        """Execute tests sequentially with detailed progress tracking."""
        results = []
        
        if RICH_AVAILABLE and self.console:
            progress = self.progress_tracker.create_progress_display(len(self.discovered_tests))
            
            with progress:
                main_task = progress.add_task("🧪 Running Tests", total=len(self.discovered_tests))
                
                for i, (platform, service, category, test_file) in enumerate(self.discovered_tests):
                    # Update progress
                    progress.update(
                        main_task,
                        description=f"🧪 {platform}/{service}/{category}/{test_file.name}",
                        completed=i
                    )
                    
                    # Execute test
                    result = self._execute_single_test(platform, service, category, test_file, timeout)
                    results.append(result)
                    
                    # Check fail-fast condition
                    if fail_fast and result.status in [TestExecutionStatus.FAILED, TestExecutionStatus.ERROR]:
                        if self.console:
                            self.console.print("[red]🛑 Stopping execution due to failure (fail-fast mode)[/red]")
                        break
                
                progress.update(main_task, completed=len(results))
        else:
            # Simple progress without rich
            for i, (platform, service, category, test_file) in enumerate(self.discovered_tests):
                print(f"Running {i+1}/{len(self.discovered_tests)}: {platform}/{service}/{category}/{test_file.name}")
                
                result = self._execute_single_test(platform, service, category, test_file, timeout)
                results.append(result)
                
                if fail_fast and result.status in [TestExecutionStatus.FAILED, TestExecutionStatus.ERROR]:
                    print("Stopping execution due to failure (fail-fast mode)")
                    break
        
        self.test_results = results
        return results
    
    def _execute_tests_parallel(self, max_workers: int, fail_fast: bool, timeout: int) -> List[TestResult]:
        """Execute tests in parallel with progress tracking."""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all test executions
            future_to_test = {
                executor.submit(self._execute_single_test, platform, service, category, test_file, timeout): 
                (platform, service, category, test_file)
                for platform, service, category, test_file in self.discovered_tests
            }
            
            # Process completed tests
            for future in as_completed(future_to_test):
                platform, service, category, test_file = future_to_test[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Display immediate result
                    status_icon = {
                        TestExecutionStatus.PASSED: "✅",
                        TestExecutionStatus.FAILED: "❌",
                        TestExecutionStatus.SKIPPED: "⏭️",
                        TestExecutionStatus.ERROR: "💥",
                        TestExecutionStatus.TIMEOUT: "⏰"
                    }.get(result.status, "❓")
                    
                    if self.console:
                        self.console.print(
                            f"{status_icon} {platform}/{service}/{category}/{test_file.name} "
                            f"({result.metrics.duration:.2f}s)"
                        )
                    
                    # Check fail-fast condition
                    if fail_fast and result.status in [TestExecutionStatus.FAILED, TestExecutionStatus.ERROR]:
                        # Cancel remaining futures
                        for f in future_to_test:
                            if not f.done():
                                f.cancel()
                        break
                        
                except Exception as e:
                    if self.console:
                        self.console.print(f"[red]💥 Test execution failed: {e}[/red]")
        
        self.test_results = results
        return results
    
    def _execute_single_test(self, platform: str, service: str, category: str, 
                           test_file: Path, timeout: int) -> TestResult:
        """Execute a single test file with comprehensive tracking."""
        # Create test context
        context = TestExecutionContext(
            platform=platform,
            service=service,
            test_category=TestCategory(category) if category in [c.value for c in TestCategory] else TestCategory.UNIT,
            test_file=test_file.name,
            environment="ci" if os.getenv('CI') else "local",
            ci_provider=os.getenv('CI_PROVIDER', ''),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        
        # Start tracking
        test_id = self.progress_tracker.start_test(context)
        
        # Initialize result
        result = TestResult(
            context=context,
            status=TestExecutionStatus.RUNNING,
            metrics=TestMetrics(start_time=time.time())
        )
        
        try:
            # Update status
            self.progress_tracker.update_test_status(test_id, TestExecutionStatus.RUNNING)
            
            # Prepare pytest command
            cmd = [
                sys.executable, "-m", "pytest",
                str(test_file),
                "-v",
                "--tb=short",
                "--capture=no",
                "--json-report",
                f"--json-report-file=/tmp/pytest_report_{platform}_{service}_{category}.json"
            ]
            
            # Set environment variables
            env = os.environ.copy()
            env.update({
                'IC_TEST_PLATFORM': platform,
                'IC_TEST_SERVICE': service,
                'IC_TEST_CATEGORY': category,
                'PYTHONPATH': f"{project_root}/src:{project_root}",
                'IC_CI_MODE': 'true' if context.environment == 'ci' else 'false'
            })
            
            # Execute test
            process_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=project_root
            )
            
            # Update metrics
            result.metrics.end_time = time.time()
            result.metrics.duration = result.metrics.end_time - result.metrics.start_time
            result.output = process_result.stdout + "\n" + process_result.stderr
            
            # Parse results
            if process_result.returncode == 0:
                result.status = TestExecutionStatus.PASSED
            else:
                result.status = TestExecutionStatus.FAILED
                
                # Create failure info
                result.failure_info = TestFailureInfo(
                    error_message=process_result.stderr or "Test failed",
                    traceback=process_result.stdout
                )
            
            # Try to parse pytest JSON report for detailed metrics
            self._parse_pytest_report(result, platform, service, category)
            
        except subprocess.TimeoutExpired:
            result.status = TestExecutionStatus.TIMEOUT
            result.metrics.end_time = time.time()
            result.metrics.duration = timeout
            result.failure_info = TestFailureInfo(
                error_type="TimeoutError",
                error_message=f"Test execution timed out after {timeout} seconds"
            )
            
        except Exception as e:
            result.status = TestExecutionStatus.ERROR
            result.metrics.end_time = time.time()
            result.metrics.duration = time.time() - result.metrics.start_time
            result.failure_info = TestFailureInfo(
                error_type=type(e).__name__,
                error_message=str(e),
                traceback=str(e)
            )
        
        # Complete tracking
        self.progress_tracker.complete_test(test_id, result)
        
        # Record in reliability tracker if available
        if RELIABILITY_AVAILABLE:
            self._record_reliability_execution(result)
        
        return result
    
    def _parse_pytest_report(self, result: TestResult, platform: str, service: str, category: str):
        """Parse pytest JSON report for detailed metrics."""
        report_file = f"/tmp/pytest_report_{platform}_{service}_{category}.json"
        
        try:
            if os.path.exists(report_file):
                with open(report_file, 'r') as f:
                    report = json.load(f)
                
                summary = report.get("summary", {})
                result.metrics.assertions_count = summary.get("total", 0)
                
                # Extract detailed test information
                for test in report.get("tests", []):
                    if test.get("outcome") == "failed":
                        if not result.failure_info:
                            result.failure_info = TestFailureInfo()
                        
                        result.failure_info.error_message = test.get("call", {}).get("longrepr", "")
                        result.failure_info.file_path = test.get("nodeid", "").split("::")[0]
                
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # Ignore parsing errors, basic metrics are already captured
            pass
    
    def generate_comprehensive_report(self, save_to_file: Optional[str] = None) -> Dict[str, Any]:
        """Generate and display comprehensive test execution report."""
        if not self.test_results:
            if self.console:
                self.console.print("[yellow]No test results available for reporting[/yellow]")
            return {}
        
        # Display detailed summary
        self.report_generator.display_detailed_summary(self.test_results)
        
        # Save report if requested
        if save_to_file:
            self.report_generator.save_report(self.test_results, save_to_file)
        
        # Return summary data
        return self.report_generator.generate_summary_report(self.test_results)
    
    def _record_reliability_execution(self, result: TestResult):
        """Record test execution in reliability tracker."""
        try:
            reliability_tracker = get_reliability_tracker()
            
            # Convert TestResult to ReliabilityExecution
            reliability_execution = ReliabilityExecution(
                test_id=f"{result.context.platform}/{result.context.service}/{result.context.test_category.value}/{result.context.test_file}",
                timestamp=result.metrics.start_time,
                duration=result.metrics.duration,
                status=self._convert_status_to_reliability(result.status),
                platform=result.context.platform,
                service=result.context.service,
                test_category=result.context.test_category.value,
                error_message=result.failure_info.error_message if result.failure_info else None,
                error_type=result.failure_info.error_type if result.failure_info else None,
                environment=result.context.environment,
                ci_run_id=os.getenv('GITHUB_RUN_ID'),
                commit_hash=os.getenv('GITHUB_SHA')
            )
            
            reliability_tracker.record_test_execution(reliability_execution)
            
        except Exception as e:
            # Don't fail the test run if reliability tracking fails
            if self.console:
                self.console.print(f"[yellow]Warning: Failed to record reliability data: {e}[/yellow]")
    
    def _convert_status_to_reliability(self, status: TestExecutionStatus) -> str:
        """Convert TestExecutionStatus to reliability tracker status."""
        status_mapping = {
            TestExecutionStatus.PASSED: "passed",
            TestExecutionStatus.FAILED: "failed",
            TestExecutionStatus.SKIPPED: "skipped",
            TestExecutionStatus.ERROR: "error",
            TestExecutionStatus.TIMEOUT: "error"
        }
        return status_mapping.get(status, "error")


def main():
    """Main entry point for enhanced test runner."""
    parser = argparse.ArgumentParser(description="Enhanced Test Runner with Transparency")
    
    parser.add_argument(
        "--platforms",
        nargs="+",
        choices=['aws', 'gcp', 'ncp', 'ncpgov', 'oci', 'azure', 'cloudflare'],
        help="Platforms to test"
    )
    
    parser.add_argument(
        "--services",
        nargs="+",
        help="Services to test"
    )
    
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=['unit', 'integration', 'performance', 'security', 'e2e'],
        help="Test categories to run"
    )
    
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Only discover tests, don't execute them"
    )
    
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel"
    )
    
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of parallel workers"
    )
    
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Test execution timeout in seconds"
    )
    
    parser.add_argument(
        "--report-file",
        help="Save detailed report to file"
    )
    
    parser.add_argument(
        "--base-path",
        default="tests",
        help="Base path for test discovery"
    )
    
    parser.add_argument(
        "--no-legacy",
        action="store_true",
        help="Skip legacy test discovery"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    args = parser.parse_args()
    
    # Initialize enhanced test runner
    runner = EnhancedTestRunner(args.base_path, verbose=not args.quiet)
    
    try:
        # Discover tests
        discovered_tests = runner.discover_tests(
            platforms=args.platforms,
            services=args.services,
            test_categories=args.categories,
            include_legacy=not args.no_legacy
        )
        
        if not discovered_tests:
            print("No tests discovered with the given criteria")
            return 1
        
        # Display discovery summary
        runner.display_test_discovery_summary()
        
        if args.discover_only:
            return 0
        
        # Execute tests
        results = runner.execute_tests(
            parallel=args.parallel,
            max_workers=args.max_workers,
            fail_fast=args.fail_fast,
            timeout=args.timeout
        )
        
        # Generate comprehensive report
        report = runner.generate_comprehensive_report(args.report_file)
        
        # Return appropriate exit code
        failed_count = sum(1 for r in results if r.status in [
            TestExecutionStatus.FAILED, TestExecutionStatus.ERROR, TestExecutionStatus.TIMEOUT
        ])
        
        return 1 if failed_count > 0 else 0
        
    except KeyboardInterrupt:
        if runner.console:
            runner.console.print("\n[yellow]⚠️  Test execution interrupted by user[/yellow]")
        else:
            print("\nTest execution interrupted by user")
        return 130
    
    except Exception as e:
        if runner.console:
            runner.console.print(f"[red]❌ Test execution failed: {e}[/red]")
        else:
            print(f"Test execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())