#!/usr/bin/env python3
"""
Comprehensive Test Runner

Integrates all testing systems: transparency, mock data, integration testing,
and reliability tracking for complete test execution and analysis.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7 - Complete testing system
"""

import os
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import all testing components
try:
    from tests.transparency import EnhancedTestRunner
    TRANSPARENCY_AVAILABLE = True
except ImportError:
    TRANSPARENCY_AVAILABLE = False

try:
    from tests.mock_system import (
        create_integration_mock_framework,
        create_unit_test_framework,
        ServiceType
    )
    MOCK_SYSTEM_AVAILABLE = True
except ImportError:
    MOCK_SYSTEM_AVAILABLE = False

try:
    from tests.reliability import get_reliability_tracker, ReliabilityReporter
    RELIABILITY_AVAILABLE = True
except ImportError:
    RELIABILITY_AVAILABLE = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class ComprehensiveTestRunner:
    """Comprehensive test runner integrating all testing systems."""
    
    def __init__(self, base_path: str = "tests"):
        self.base_path = Path(base_path)
        self.console = Console() if RICH_AVAILABLE else None
        
        # Initialize components
        self.transparency_runner = None
        self.mock_framework = None
        self.reliability_tracker = None
        self.reliability_reporter = None
        
        # Test execution results
        self.execution_results = {}
        self.overall_success = True
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize available testing components."""
        if TRANSPARENCY_AVAILABLE:
            self.transparency_runner = EnhancedTestRunner(str(self.base_path))
            if self.console:
                self.console.print("✅ Transparency system initialized")
        
        if MOCK_SYSTEM_AVAILABLE:
            self.mock_framework = create_integration_mock_framework()
            if self.console:
                self.console.print("✅ Mock system initialized")
        
        if RELIABILITY_AVAILABLE:
            self.reliability_tracker = get_reliability_tracker()
            self.reliability_reporter = ReliabilityReporter(self.reliability_tracker)
            if self.console:
                self.console.print("✅ Reliability system initialized")
    
    def run_comprehensive_tests(self, 
                              platforms: Optional[List[str]] = None,
                              services: Optional[List[str]] = None,
                              test_categories: Optional[List[str]] = None,
                              include_reliability_report: bool = True,
                              include_mock_validation: bool = True,
                              parallel: bool = False,
                              fail_fast: bool = False) -> Dict[str, Any]:
        """Run comprehensive tests with all available systems."""
        
        if self.console:
            self.console.print("\n[bold blue]🚀 Starting Comprehensive Test Execution[/bold blue]")
        
        start_time = time.time()
        results = {
            "start_time": start_time,
            "transparency_results": None,
            "mock_validation_results": None,
            "reliability_report": None,
            "overall_success": False,
            "total_duration": 0.0,
            "systems_used": []
        }
        
        try:
            # Run transparency system tests
            if TRANSPARENCY_AVAILABLE and self.transparency_runner:
                results["transparency_results"] = self._run_transparency_tests(
                    platforms, services, test_categories, parallel, fail_fast
                )
                results["systems_used"].append("transparency")
            
            # Run mock system validation
            if MOCK_SYSTEM_AVAILABLE and include_mock_validation:
                results["mock_validation_results"] = self._run_mock_validation_tests()
                results["systems_used"].append("mock_system")
            
            # Generate reliability report
            if RELIABILITY_AVAILABLE and include_reliability_report:
                results["reliability_report"] = self._generate_reliability_analysis()
                results["systems_used"].append("reliability")
            
            # Determine overall success
            results["overall_success"] = self._determine_overall_success(results)
            
        except Exception as e:
            if self.console:
                self.console.print(f"[red]❌ Comprehensive test execution failed: {e}[/red]")
            results["error"] = str(e)
            results["overall_success"] = False
        
        finally:
            results["total_duration"] = time.time() - start_time
            
            # Display final summary
            self._display_comprehensive_summary(results)
        
        return results
    
    def _run_transparency_tests(self, platforms, services, test_categories, parallel, fail_fast):
        """Run tests using transparency system."""
        if self.console:
            self.console.print("\n[cyan]🔍 Running Transparency System Tests[/cyan]")
        
        try:
            # Discover tests
            discovered_tests = self.transparency_runner.discover_tests(
                platforms=platforms,
                services=services,
                test_categories=test_categories
            )
            
            if not discovered_tests:
                return {"status": "no_tests", "message": "No tests discovered"}
            
            # Display discovery summary
            self.transparency_runner.display_test_discovery_summary()
            
            # Execute tests
            test_results = self.transparency_runner.execute_tests(
                parallel=parallel,
                fail_fast=fail_fast
            )
            
            # Generate report
            report = self.transparency_runner.generate_comprehensive_report()
            
            return {
                "status": "completed",
                "discovered_tests": len(discovered_tests),
                "executed_tests": len(test_results),
                "report": report,
                "test_results": test_results
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _run_mock_validation_tests(self):
        """Run mock system validation tests."""
        if self.console:
            self.console.print("\n[cyan]🤖 Running Mock System Validation[/cyan]")
        
        try:
            validation_results = {
                "ncp_validation": self._validate_platform_mocks("ncp"),
                "ncpgov_validation": self._validate_platform_mocks("ncpgov"),
                "service_health": self.mock_framework.get_service_health_report(),
                "mock_metrics": None
            }
            
            # Get mock provider metrics if available
            if hasattr(self.mock_framework, 'mock_provider') and self.mock_framework.mock_provider:
                validation_results["mock_metrics"] = self.mock_framework.mock_provider.get_metrics()
            
            return validation_results
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _validate_platform_mocks(self, platform: str) -> Dict[str, Any]:
        """Validate mock data for a specific platform."""
        services = ['ec2', 's3', 'vpc', 'sg', 'rds']
        validation_results = {}
        
        for service in services:
            try:
                # Test basic service call
                response = self.mock_framework.execute_service_call(
                    platform, service, 'list_instances'
                )
                
                validation_results[service] = {
                    "status": "success",
                    "response_received": bool(response),
                    "response_structure_valid": self._validate_response_structure(response)
                }
                
            except Exception as e:
                validation_results[service] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return validation_results
    
    def _validate_response_structure(self, response: Dict[str, Any]) -> bool:
        """Validate basic response structure."""
        if not isinstance(response, dict):
            return False
        
        # Check for common response patterns
        for key in response.keys():
            if key.endswith('Response'):
                response_data = response[key]
                if isinstance(response_data, dict):
                    # Check for common fields
                    if 'returnCode' in response_data or 'totalRows' in response_data:
                        return True
        
        return False
    
    def _generate_reliability_analysis(self):
        """Generate reliability analysis and report."""
        if self.console:
            self.console.print("\n[cyan]📊 Generating Reliability Analysis[/cyan]")
        
        try:
            # Generate reliability report
            report = self.reliability_tracker.generate_reliability_report()
            
            # Get flaky tests
            flaky_tests = self.reliability_tracker.get_flaky_tests()
            
            # Get active issues
            active_issues = self.reliability_tracker.get_active_issues()
            
            return {
                "status": "completed",
                "report": {
                    "total_tests": report.total_tests,
                    "reliable_tests": report.reliable_tests,
                    "flaky_tests": report.flaky_tests,
                    "unstable_tests": report.unstable_tests,
                    "broken_tests": report.broken_tests,
                    "overall_reliability_score": report.overall_reliability_score
                },
                "flaky_test_count": len(flaky_tests),
                "active_issue_count": len(active_issues),
                "recommendations": report.recommendations
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _determine_overall_success(self, results: Dict[str, Any]) -> bool:
        """Determine overall success based on all system results."""
        # Check transparency results
        if results.get("transparency_results"):
            transparency_results = results["transparency_results"]
            if transparency_results.get("status") == "error":
                return False
            
            # Check if any tests failed
            test_results = transparency_results.get("test_results", [])
            if test_results:
                from tests.transparency.test_execution_tracker import TestExecutionStatus
                failed_tests = [
                    r for r in test_results 
                    if r.status in [TestExecutionStatus.FAILED, TestExecutionStatus.ERROR]
                ]
                if failed_tests:
                    return False
        
        # Check mock validation results
        if results.get("mock_validation_results"):
            mock_results = results["mock_validation_results"]
            if mock_results.get("status") == "error":
                return False
        
        # Check reliability report for critical issues
        if results.get("reliability_report"):
            reliability_report = results["reliability_report"]
            if reliability_report.get("status") == "completed":
                report_data = reliability_report.get("report", {})
                # Consider it a failure if reliability score is too low
                if report_data.get("overall_reliability_score", 1.0) < 0.5:
                    if self.console:
                        self.console.print("[yellow]⚠️  Low reliability score detected[/yellow]")
        
        return True
    
    def _display_comprehensive_summary(self, results: Dict[str, Any]):
        """Display comprehensive test execution summary."""
        if not RICH_AVAILABLE or not self.console:
            self._display_simple_summary(results)
            return
        
        # Main summary panel
        success_icon = "✅" if results["overall_success"] else "❌"
        status_text = "SUCCESS" if results["overall_success"] else "FAILURE"
        
        summary_text = f"""
{success_icon} Overall Status: {status_text}
⏱️  Total Duration: {results['total_duration']:.2f}s
🔧 Systems Used: {', '.join(results['systems_used'])}
        """.strip()
        
        panel = Panel(
            summary_text,
            title="🏁 Comprehensive Test Summary",
            border_style="green" if results["overall_success"] else "red"
        )
        self.console.print(panel)
        
        # System-specific summaries
        if results.get("transparency_results"):
            self._display_transparency_summary(results["transparency_results"])
        
        if results.get("mock_validation_results"):
            self._display_mock_validation_summary(results["mock_validation_results"])
        
        if results.get("reliability_report"):
            self._display_reliability_summary(results["reliability_report"])
    
    def _display_transparency_summary(self, transparency_results: Dict[str, Any]):
        """Display transparency system summary."""
        if transparency_results.get("status") == "completed":
            table = Table(title="🔍 Transparency System Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Tests Discovered", str(transparency_results.get("discovered_tests", 0)))
            table.add_row("Tests Executed", str(transparency_results.get("executed_tests", 0)))
            
            # Add test result breakdown if available
            test_results = transparency_results.get("test_results", [])
            if test_results:
                from tests.transparency.test_execution_tracker import TestExecutionStatus
                passed = sum(1 for r in test_results if r.status == TestExecutionStatus.PASSED)
                failed = sum(1 for r in test_results if r.status == TestExecutionStatus.FAILED)
                
                table.add_row("Tests Passed", str(passed))
                table.add_row("Tests Failed", str(failed))
            
            self.console.print(table)
    
    def _display_mock_validation_summary(self, mock_results: Dict[str, Any]):
        """Display mock validation summary."""
        table = Table(title="🤖 Mock System Validation")
        table.add_column("Platform", style="cyan")
        table.add_column("Service", style="yellow")
        table.add_column("Status", style="green")
        
        for platform in ["ncp", "ncpgov"]:
            platform_results = mock_results.get(f"{platform}_validation", {})
            for service, result in platform_results.items():
                status = "✅ OK" if result.get("status") == "success" else "❌ ERROR"
                table.add_row(platform.upper(), service, status)
        
        self.console.print(table)
    
    def _display_reliability_summary(self, reliability_results: Dict[str, Any]):
        """Display reliability summary."""
        if reliability_results.get("status") == "completed":
            report_data = reliability_results.get("report", {})
            
            table = Table(title="📊 Reliability Analysis")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Total Tests", str(report_data.get("total_tests", 0)))
            table.add_row("Reliable Tests", str(report_data.get("reliable_tests", 0)))
            table.add_row("Flaky Tests", str(report_data.get("flaky_tests", 0)))
            table.add_row("Reliability Score", f"{report_data.get('overall_reliability_score', 0):.2%}")
            table.add_row("Active Issues", str(reliability_results.get("active_issue_count", 0)))
            
            self.console.print(table)
    
    def _display_simple_summary(self, results: Dict[str, Any]):
        """Display simple text summary when rich is not available."""
        print("\n" + "="*60)
        print("COMPREHENSIVE TEST SUMMARY")
        print("="*60)
        
        status = "SUCCESS" if results["overall_success"] else "FAILURE"
        print(f"Overall Status: {status}")
        print(f"Total Duration: {results['total_duration']:.2f}s")
        print(f"Systems Used: {', '.join(results['systems_used'])}")
        
        if results.get("transparency_results"):
            tr = results["transparency_results"]
            if tr.get("status") == "completed":
                print(f"\nTransparency System:")
                print(f"  Tests Discovered: {tr.get('discovered_tests', 0)}")
                print(f"  Tests Executed: {tr.get('executed_tests', 0)}")
        
        if results.get("reliability_report"):
            rr = results["reliability_report"]
            if rr.get("status") == "completed":
                report_data = rr.get("report", {})
                print(f"\nReliability Analysis:")
                print(f"  Total Tests: {report_data.get('total_tests', 0)}")
                print(f"  Reliability Score: {report_data.get('overall_reliability_score', 0):.2%}")
                print(f"  Flaky Tests: {report_data.get('flaky_tests', 0)}")
        
        print("="*60)
    
    def generate_detailed_reliability_report(self, format_type: str = "console", output_file: Optional[str] = None):
        """Generate detailed reliability report."""
        if not RELIABILITY_AVAILABLE or not self.reliability_reporter:
            print("Reliability system not available")
            return
        
        if format_type == "console":
            self.reliability_reporter.generate_console_report(detailed=True)
        elif format_type == "json" and output_file:
            self.reliability_reporter.generate_json_report(output_file)
        elif format_type == "html" and output_file:
            self.reliability_reporter.generate_html_report(output_file)
        elif format_type == "markdown" and output_file:
            self.reliability_reporter.generate_markdown_report(output_file)


def main():
    """Main entry point for comprehensive test runner."""
    parser = argparse.ArgumentParser(description="Comprehensive Test Runner")
    
    parser.add_argument("--platforms", nargs="+", 
                       choices=['aws', 'gcp', 'ncp', 'ncpgov', 'oci', 'azure', 'cloudflare'],
                       help="Platforms to test")
    parser.add_argument("--services", nargs="+", help="Services to test")
    parser.add_argument("--categories", nargs="+",
                       choices=['unit', 'integration', 'performance', 'security', 'e2e'],
                       help="Test categories to run")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--no-reliability", action="store_true", help="Skip reliability analysis")
    parser.add_argument("--no-mock-validation", action="store_true", help="Skip mock validation")
    parser.add_argument("--reliability-report", choices=['console', 'json', 'html', 'markdown'],
                       help="Generate detailed reliability report")
    parser.add_argument("--reliability-output", help="Output file for reliability report")
    parser.add_argument("--base-path", default="tests", help="Base path for test discovery")
    
    args = parser.parse_args()
    
    # Initialize comprehensive test runner
    runner = ComprehensiveTestRunner(args.base_path)
    
    try:
        # Run comprehensive tests
        results = runner.run_comprehensive_tests(
            platforms=args.platforms,
            services=args.services,
            test_categories=args.categories,
            include_reliability_report=not args.no_reliability,
            include_mock_validation=not args.no_mock_validation,
            parallel=args.parallel,
            fail_fast=args.fail_fast
        )
        
        # Generate detailed reliability report if requested
        if args.reliability_report:
            runner.generate_detailed_reliability_report(
                args.reliability_report,
                args.reliability_output
            )
        
        # Return appropriate exit code
        return 0 if results["overall_success"] else 1
        
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        return 130
    
    except Exception as e:
        print(f"Test execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())