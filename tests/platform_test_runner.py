#!/usr/bin/env python3
"""
Platform-based Test Discovery and Execution System

This module provides a comprehensive test runner that can execute tests by platform,
service, and test type with detailed progress indicators and result reporting.

Enhanced with transparency system integration for improved debugging and reporting.
"""

import os
import sys
import time
import json
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Add project root to Python path for transparency system
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from tests.transparency import EnhancedTestRunner, TestExecutionStatus
    TRANSPARENCY_AVAILABLE = True
except ImportError:
    TRANSPARENCY_AVAILABLE = False

try:
    import pytest
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


class TestType(Enum):
    """Test type enumeration."""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"


class TestStatus(Enum):
    """Test execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Test result data structure."""
    platform: str
    service: str
    test_type: str
    test_file: str
    status: TestStatus
    duration: float
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class TestSummary:
    """Test execution summary."""
    total_tests: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    total_duration: float = 0.0
    platform_results: Dict[str, Dict] = None
    
    def __post_init__(self):
        if self.platform_results is None:
            self.platform_results = {}


class PlatformTestRunner:
    """Platform-based test discovery and execution system."""
    
    def __init__(self, base_path: str = "tests/platforms"):
        """Initialize the test runner."""
        self.base_path = Path(base_path)
        self.console = Console()
        self.results: List[TestResult] = []
        
        # Available platforms and services (only platforms with actual tests)
        self.platforms = {
            'ncp': ['ec2', 's3', 'vpc', 'sg', 'rds'],
            'ncpgov': ['ec2', 's3', 'vpc', 'sg', 'rds']
        }
        
        # Platforms in development (no tests yet)
        self.development_platforms = {
            'aws': ['ec2', 's3', 'vpc', 'rds', 'cloudfront', 'ecs', 'eks'],
            'gcp': ['compute', 'storage', 'vpc', 'gke', 'sql'],
            'oci': ['compute', 'storage', 'vcn', 'compartment'],
            'azure': ['vm', 'storage', 'vnet', 'aks']
        }
    
    def discover_tests(self, 
                      platforms: Optional[List[str]] = None,
                      services: Optional[List[str]] = None,
                      test_types: Optional[List[TestType]] = None) -> List[Tuple[str, str, str, Path]]:
        """
        Discover test files based on criteria.
        
        Returns:
            List of tuples: (platform, service, test_type, test_file_path)
        """
        discovered_tests = []
        
        # Default to all platforms if none specified
        if platforms is None:
            platforms = list(self.platforms.keys())
        
        # Default to all test types if none specified
        if test_types is None:
            test_types = list(TestType)
        
        for platform in platforms:
            if platform not in self.platforms:
                self.console.print(f"[yellow]Warning: Unknown platform '{platform}', skipping[/yellow]")
                continue
                
            platform_path = self.base_path / platform
            if not platform_path.exists():
                self.console.print(f"[yellow]Warning: Platform directory '{platform}' not found[/yellow]")
                continue
            
            # Get services for this platform
            platform_services = services if services else self.platforms[platform]
            
            for service in platform_services:
                if service not in self.platforms[platform]:
                    self.console.print(f"[yellow]Warning: Service '{service}' not available for platform '{platform}'[/yellow]")
                    continue
                    
                service_path = platform_path / service
                if not service_path.exists():
                    continue
                
                for test_type in test_types:
                    test_type_path = service_path / test_type.value
                    if not test_type_path.exists():
                        continue
                    
                    # Find all Python test files
                    for test_file in test_type_path.glob("test_*.py"):
                        discovered_tests.append((platform, service, test_type.value, test_file))
        
        return discovered_tests
    
    def display_test_tree(self, discovered_tests: List[Tuple[str, str, str, Path]]):
        """Display discovered tests in a tree structure."""
        tree = Tree("📋 Discovered Tests")
        
        # Group tests by platform
        platform_groups = {}
        for platform, service, test_type, test_file in discovered_tests:
            if platform not in platform_groups:
                platform_groups[platform] = {}
            if service not in platform_groups[platform]:
                platform_groups[platform][service] = {}
            if test_type not in platform_groups[platform][service]:
                platform_groups[platform][service][test_type] = []
            platform_groups[platform][service][test_type].append(test_file.name)
        
        # Build tree structure
        for platform, services in platform_groups.items():
            platform_node = tree.add(f"🏗️  {platform.upper()}")
            
            for service, test_types in services.items():
                service_node = platform_node.add(f"⚙️  {service}")
                
                for test_type, test_files in test_types.items():
                    test_type_node = service_node.add(f"📝 {test_type} ({len(test_files)} files)")
                    
                    for test_file in test_files:
                        test_type_node.add(f"📄 {test_file}")
        
        self.console.print(tree)
        self.console.print(f"\n[bold green]Total: {len(discovered_tests)} test files discovered[/bold green]\n")
    
    def execute_test_file(self, platform: str, service: str, test_type: str, test_file: Path) -> TestResult:
        """Execute a single test file and return results."""
        start_time = time.time()
        
        # Prepare pytest command
        cmd = [
            sys.executable, "-m", "pytest",
            str(test_file),
            "-v",
            "--tb=short",
            "--json-report",
            "--json-report-file=/tmp/pytest_report.json"
        ]
        
        try:
            # Execute pytest
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per test file
            )
            
            duration = time.time() - start_time
            
            # Parse pytest JSON report if available
            passed, failed, skipped = 0, 0, 0
            errors = []
            
            try:
                with open("/tmp/pytest_report.json", "r") as f:
                    report = json.load(f)
                    summary = report.get("summary", {})
                    passed = summary.get("passed", 0)
                    failed = summary.get("failed", 0)
                    skipped = summary.get("skipped", 0)
                    
                    # Extract error messages
                    for test in report.get("tests", []):
                        if test.get("outcome") == "failed":
                            errors.append(f"{test.get('nodeid', 'Unknown')}: {test.get('call', {}).get('longrepr', 'Unknown error')}")
            except (FileNotFoundError, json.JSONDecodeError):
                # Fallback to parsing stdout/stderr
                if result.returncode == 0:
                    passed = 1
                else:
                    failed = 1
                    errors.append(result.stderr or result.stdout)
            
            # Determine status
            if result.returncode == 0:
                status = TestStatus.PASSED if passed > 0 else TestStatus.SKIPPED
            else:
                status = TestStatus.FAILED if failed > 0 else TestStatus.ERROR
            
            return TestResult(
                platform=platform,
                service=service,
                test_type=test_type,
                test_file=test_file.name,
                status=status,
                duration=duration,
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return TestResult(
                platform=platform,
                service=service,
                test_type=test_type,
                test_file=test_file.name,
                status=TestStatus.ERROR,
                duration=duration,
                errors=["Test execution timed out after 5 minutes"]
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                platform=platform,
                service=service,
                test_type=test_type,
                test_file=test_file.name,
                status=TestStatus.ERROR,
                duration=duration,
                errors=[str(e)]
            )
    
    def execute_tests(self, 
                     discovered_tests: List[Tuple[str, str, str, Path]],
                     parallel: bool = False,
                     fail_fast: bool = False) -> TestSummary:
        """Execute discovered tests with progress tracking."""
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            
            main_task = progress.add_task("🧪 Running Tests", total=len(discovered_tests))
            
            for i, (platform, service, test_type, test_file) in enumerate(discovered_tests):
                # Update progress description
                progress.update(
                    main_task, 
                    description=f"🧪 Running {platform}/{service}/{test_type}/{test_file.name}",
                    completed=i
                )
                
                # Execute test
                result = self.execute_test_file(platform, service, test_type, test_file)
                self.results.append(result)
                
                # Display immediate result
                status_icon = {
                    TestStatus.PASSED: "✅",
                    TestStatus.FAILED: "❌",
                    TestStatus.SKIPPED: "⏭️",
                    TestStatus.ERROR: "💥"
                }.get(result.status, "❓")
                
                self.console.print(
                    f"{status_icon} {platform}/{service}/{test_type}/{test_file.name} "
                    f"({result.duration:.2f}s) - "
                    f"P:{result.passed} F:{result.failed} S:{result.skipped}"
                )
                
                # Fail fast if requested and test failed
                if fail_fast and result.status in [TestStatus.FAILED, TestStatus.ERROR]:
                    self.console.print(f"[red]Stopping execution due to failure (fail-fast mode)[/red]")
                    break
            
            progress.update(main_task, completed=len(discovered_tests))
        
        return self.generate_summary()
    
    def generate_summary(self) -> TestSummary:
        """Generate test execution summary."""
        summary = TestSummary()
        
        for result in self.results:
            summary.total_tests += 1
            summary.total_duration += result.duration
            
            if result.status == TestStatus.PASSED:
                summary.total_passed += 1
            elif result.status == TestStatus.FAILED:
                summary.total_failed += 1
            elif result.status == TestStatus.SKIPPED:
                summary.total_skipped += 1
            elif result.status == TestStatus.ERROR:
                summary.total_errors += 1
            
            # Group by platform
            platform = result.platform
            if platform not in summary.platform_results:
                summary.platform_results[platform] = {
                    'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0, 'duration': 0.0
                }
            
            summary.platform_results[platform]['total'] += 1
            summary.platform_results[platform]['duration'] += result.duration
            
            if result.status == TestStatus.PASSED:
                summary.platform_results[platform]['passed'] += 1
            elif result.status == TestStatus.FAILED:
                summary.platform_results[platform]['failed'] += 1
            elif result.status == TestStatus.SKIPPED:
                summary.platform_results[platform]['skipped'] += 1
            elif result.status == TestStatus.ERROR:
                summary.platform_results[platform]['errors'] += 1
        
        return summary
    
    def display_summary(self, summary: TestSummary):
        """Display test execution summary."""
        # Overall summary table
        summary_table = Table(title="📊 Test Execution Summary")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Count", style="magenta")
        summary_table.add_column("Percentage", style="green")
        
        total = summary.total_tests
        if total > 0:
            summary_table.add_row("Total Tests", str(total), "100%")
            summary_table.add_row("✅ Passed", str(summary.total_passed), f"{(summary.total_passed/total)*100:.1f}%")
            summary_table.add_row("❌ Failed", str(summary.total_failed), f"{(summary.total_failed/total)*100:.1f}%")
            summary_table.add_row("⏭️ Skipped", str(summary.total_skipped), f"{(summary.total_skipped/total)*100:.1f}%")
            summary_table.add_row("💥 Errors", str(summary.total_errors), f"{(summary.total_errors/total)*100:.1f}%")
            summary_table.add_row("⏱️ Duration", f"{summary.total_duration:.2f}s", "-")
        
        self.console.print(summary_table)
        
        # Platform breakdown
        if summary.platform_results:
            platform_table = Table(title="🏗️ Platform Breakdown")
            platform_table.add_column("Platform", style="cyan")
            platform_table.add_column("Total", style="white")
            platform_table.add_column("✅ Passed", style="green")
            platform_table.add_column("❌ Failed", style="red")
            platform_table.add_column("⏭️ Skipped", style="yellow")
            platform_table.add_column("💥 Errors", style="magenta")
            platform_table.add_column("⏱️ Duration", style="blue")
            
            for platform, results in summary.platform_results.items():
                platform_table.add_row(
                    platform.upper(),
                    str(results['total']),
                    str(results['passed']),
                    str(results['failed']),
                    str(results['skipped']),
                    str(results['errors']),
                    f"{results['duration']:.2f}s"
                )
            
            self.console.print(platform_table)
        
        # Display failures and errors
        failures = [r for r in self.results if r.status in [TestStatus.FAILED, TestStatus.ERROR]]
        if failures:
            self.console.print("\n[red]❌ Failures and Errors:[/red]")
            for failure in failures:
                self.console.print(f"\n[red]• {failure.platform}/{failure.service}/{failure.test_type}/{failure.test_file}[/red]")
                for error in failure.errors:
                    self.console.print(f"  {error}")
    
    def save_results(self, output_file: str):
        """Save test results to JSON file."""
        results_data = {
            'summary': asdict(self.generate_summary()),
            'results': [asdict(result) for result in self.results],
            'timestamp': time.time()
        }
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
        
        self.console.print(f"[green]Results saved to {output_file}[/green]")


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(description="Platform-based Test Runner")
    
    parser.add_argument(
        "--platforms", 
        nargs="+", 
        choices=['ncp', 'ncpgov'],
        help="Platforms to test (only platforms with actual tests)"
    )
    
    parser.add_argument(
        "--services",
        nargs="+",
        help="Services to test"
    )
    
    parser.add_argument(
        "--test-types",
        nargs="+",
        choices=['unit', 'integration', 'performance', 'security', 'e2e'],
        help="Test types to run"
    )
    
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Only discover tests, don't execute them"
    )
    
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure"
    )
    
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (requires transparency system)"
    )
    
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum parallel workers"
    )
    
    parser.add_argument(
        "--enhanced",
        action="store_true",
        help="Use enhanced test runner with transparency system"
    )
    
    parser.add_argument(
        "--output",
        help="Output file for results (JSON format)"
    )
    
    parser.add_argument(
        "--base-path",
        default="tests/platforms",
        help="Base path for test discovery"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Test execution timeout in seconds"
    )
    
    args = parser.parse_args()
    
    # Use enhanced runner if available and requested
    if (args.enhanced or args.parallel) and TRANSPARENCY_AVAILABLE:
        return run_enhanced_tests(args)
    else:
        return run_legacy_tests(args)


def run_enhanced_tests(args):
    """Run tests using the enhanced transparency system."""
    from tests.transparency import EnhancedTestRunner
    
    # Initialize enhanced test runner
    runner = EnhancedTestRunner(args.base_path.replace('/platforms', ''))
    
    try:
        # Discover tests
        discovered_tests = runner.discover_tests(
            platforms=args.platforms,
            services=args.services,
            test_categories=args.test_types
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
        report = runner.generate_comprehensive_report(args.output)
        
        # Return appropriate exit code
        failed_count = sum(1 for r in results if r.status in [
            TestExecutionStatus.FAILED, TestExecutionStatus.ERROR, TestExecutionStatus.TIMEOUT
        ])
        
        return 1 if failed_count > 0 else 0
        
    except Exception as e:
        print(f"Enhanced test execution failed: {e}")
        return 1


def run_legacy_tests(args):
    """Run tests using the legacy test runner."""
    # Initialize test runner
    runner = PlatformTestRunner(args.base_path)
    
    # Convert test types to enum
    test_types = None
    if args.test_types:
        test_types = [TestType(t) for t in args.test_types if t in ['unit', 'integration', 'performance']]
    
    # Discover tests
    if runner.console:
        runner.console.print("[bold blue]🔍 Discovering tests...[/bold blue]")
    discovered_tests = runner.discover_tests(
        platforms=args.platforms,
        services=args.services,
        test_types=test_types
    )
    
    if not discovered_tests:
        if runner.console:
            runner.console.print("[yellow]No tests discovered with the given criteria[/yellow]")
        else:
            print("No tests discovered with the given criteria")
        return 1
    
    # Display discovered tests
    runner.display_test_tree(discovered_tests)
    
    if args.discover_only:
        return 0
    
    # Execute tests
    if runner.console:
        runner.console.print("[bold blue]🚀 Executing tests...[/bold blue]")
    summary = runner.execute_tests(
        discovered_tests,
        fail_fast=args.fail_fast
    )
    
    # Display results
    runner.display_summary(summary)
    
    # Save results if requested
    if args.output:
        runner.save_results(args.output)
    
    # Return appropriate exit code
    if summary.total_failed > 0 or summary.total_errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())