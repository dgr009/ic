#!/usr/bin/env python3
"""
End-to-End Test Runner

Comprehensive test runner for end-to-end functionality tests that validates
complete command workflows, multi-platform functionality, and authentication
systems across all platforms.

Requirements: 5.1-5.5
"""

import sys
import unittest
import subprocess
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from io import StringIO
import concurrent.futures
import threading

# Add src directory to path
src_dir = Path(__file__).parent.parent.parent / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.live import Live
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


class EndToEndTestRunner:
    """Comprehensive end-to-end test runner."""
    
    def __init__(self, verbose: bool = False, parallel: bool = False):
        self.verbose = verbose
        self.parallel = parallel
        self.console = Console() if RICH_AVAILABLE else None
        self.results = {
            'workflows': {'passed': 0, 'failed': 0, 'errors': [], 'duration': 0},
            'integration': {'passed': 0, 'failed': 0, 'errors': [], 'duration': 0},
            'authentication': {'passed': 0, 'failed': 0, 'errors': [], 'duration': 0}
        }
        
        # Test modules to run
        self.test_modules = [
            ('workflows', 'test_complete_workflows'),
            ('integration', 'test_multi_platform_integration'),
            ('authentication', 'test_authentication_systems')
        ]
    
    def print_message(self, message: str, style: str = "white"):
        """Print message with optional styling."""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)
    
    def run_test_module(self, category: str, module_name: str) -> Dict[str, Any]:
        """Run a single test module."""
        start_time = time.time()
        
        try:
            # Add current directory to path for imports
            current_dir = Path(__file__).parent
            if str(current_dir) not in sys.path:
                sys.path.insert(0, str(current_dir))
            
            # Discover and run tests
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(module_name)
            
            # Run tests with custom result handler
            stream = StringIO()
            runner = unittest.TextTestRunner(
                stream=stream,
                verbosity=2 if self.verbose else 1,
                buffer=True
            )
            
            result = runner.run(suite)
            
            duration = time.time() - start_time
            
            return {
                'category': category,
                'module': module_name,
                'tests_run': result.testsRun,
                'failures': len(result.failures),
                'errors': len(result.errors),
                'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
                'success': result.wasSuccessful(),
                'duration': duration,
                'output': stream.getvalue(),
                'failure_details': result.failures,
                'error_details': result.errors
            }
            
        except Exception as e:
            duration = time.time() - start_time
            return {
                'category': category,
                'module': module_name,
                'tests_run': 0,
                'failures': 0,
                'errors': 1,
                'skipped': 0,
                'success': False,
                'duration': duration,
                'output': '',
                'failure_details': [],
                'error_details': [('Module Load Error', str(e))]
            }
    
    def run_tests_sequential(self) -> Dict[str, Any]:
        """Run tests sequentially."""
        if self.console:
            self.print_message("\n🔄 Running End-to-End Tests (Sequential)", "bold cyan")
        else:
            print("\n🔄 Running End-to-End Tests (Sequential)")
        
        all_results = {}
        
        for category, module_name in self.test_modules:
            if self.console:
                self.print_message(f"\n📋 Running {category.title()} Tests...", "yellow")
            else:
                print(f"\n📋 Running {category.title()} Tests...")
            
            result = self.run_test_module(category, module_name)
            all_results[category] = result
            
            # Update summary results
            self.results[category]['passed'] = result['tests_run'] - result['failures'] - result['errors']
            self.results[category]['failed'] = result['failures'] + result['errors']
            self.results[category]['duration'] = result['duration']
            
            if result['failure_details'] or result['error_details']:
                self.results[category]['errors'].extend(result['failure_details'])
                self.results[category]['errors'].extend(result['error_details'])
            
            # Show immediate results
            if result['success']:
                status = "✅ PASSED"
                style = "green"
            else:
                status = "❌ FAILED"
                style = "red"
            
            if self.console:
                self.print_message(
                    f"  {status} - {result['tests_run']} tests, "
                    f"{result['failures']} failures, {result['errors']} errors "
                    f"({result['duration']:.2f}s)",
                    style
                )
            else:
                print(f"  {status} - {result['tests_run']} tests, "
                      f"{result['failures']} failures, {result['errors']} errors "
                      f"({result['duration']:.2f}s)")
        
        return all_results
    
    def run_tests_parallel(self) -> Dict[str, Any]:
        """Run tests in parallel."""
        if self.console:
            self.print_message("\n🔄 Running End-to-End Tests (Parallel)", "bold cyan")
        else:
            print("\n🔄 Running End-to-End Tests (Parallel)")
        
        all_results = {}
        
        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all test modules
            future_to_category = {
                executor.submit(self.run_test_module, category, module_name): category
                for category, module_name in self.test_modules
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_category):
                category = future_to_category[future]
                
                try:
                    result = future.result()
                    all_results[category] = result
                    
                    # Update summary results
                    self.results[category]['passed'] = result['tests_run'] - result['failures'] - result['errors']
                    self.results[category]['failed'] = result['failures'] + result['errors']
                    self.results[category]['duration'] = result['duration']
                    
                    if result['failure_details'] or result['error_details']:
                        self.results[category]['errors'].extend(result['failure_details'])
                        self.results[category]['errors'].extend(result['error_details'])
                    
                    # Show immediate results
                    if result['success']:
                        status = "✅ PASSED"
                        style = "green"
                    else:
                        status = "❌ FAILED"
                        style = "red"
                    
                    if self.console:
                        self.print_message(
                            f"📋 {category.title()} Tests: {status} - "
                            f"{result['tests_run']} tests, {result['failures']} failures, "
                            f"{result['errors']} errors ({result['duration']:.2f}s)",
                            style
                        )
                    else:
                        print(f"📋 {category.title()} Tests: {status} - "
                              f"{result['tests_run']} tests, {result['failures']} failures, "
                              f"{result['errors']} errors ({result['duration']:.2f}s)")
                        
                except Exception as e:
                    if self.console:
                        self.print_message(f"❌ {category.title()} Tests: ERROR - {str(e)}", "red")
                    else:
                        print(f"❌ {category.title()} Tests: ERROR - {str(e)}")
        
        return all_results
    
    def generate_summary_report(self, all_results: Dict[str, Any]) -> None:
        """Generate comprehensive summary report."""
        if self.console:
            self.print_message("\n" + "="*80, "cyan")
            self.print_message("📊 END-TO-END TEST SUMMARY REPORT", "bold cyan")
            self.print_message("="*80, "cyan")
        else:
            print("\n" + "="*80)
            print("📊 END-TO-END TEST SUMMARY REPORT")
            print("="*80)
        
        # Calculate totals
        total_tests = sum(self.results[cat]['passed'] + self.results[cat]['failed'] for cat in self.results)
        total_passed = sum(self.results[cat]['passed'] for cat in self.results)
        total_failed = sum(self.results[cat]['failed'] for cat in self.results)
        total_duration = sum(self.results[cat]['duration'] for cat in self.results)
        
        # Create summary table
        if self.console:
            table = Table(title="Test Results Summary")
            table.add_column("Category", style="cyan")
            table.add_column("Tests", style="white")
            table.add_column("Passed", style="green")
            table.add_column("Failed", style="red")
            table.add_column("Duration", style="yellow")
            table.add_column("Status", style="bold")
            
            for category in ['workflows', 'integration', 'authentication']:
                result = self.results[category]
                total_cat_tests = result['passed'] + result['failed']
                status = "✅ PASS" if result['failed'] == 0 else "❌ FAIL"
                status_style = "green" if result['failed'] == 0 else "red"
                
                table.add_row(
                    category.title(),
                    str(total_cat_tests),
                    str(result['passed']),
                    str(result['failed']),
                    f"{result['duration']:.2f}s",
                    status
                )
            
            # Add total row
            table.add_row(
                "[bold]TOTAL[/bold]",
                f"[bold]{total_tests}[/bold]",
                f"[bold]{total_passed}[/bold]",
                f"[bold]{total_failed}[/bold]",
                f"[bold]{total_duration:.2f}s[/bold]",
                f"[bold]{'✅ PASS' if total_failed == 0 else '❌ FAIL'}[/bold]"
            )
            
            self.console.print(table)
        else:
            print(f"\n{'Category':<15} {'Tests':<8} {'Passed':<8} {'Failed':<8} {'Duration':<12} {'Status'}")
            print("-" * 70)
            
            for category in ['workflows', 'integration', 'authentication']:
                result = self.results[category]
                total_cat_tests = result['passed'] + result['failed']
                status = "✅ PASS" if result['failed'] == 0 else "❌ FAIL"
                
                print(f"{category.title():<15} {total_cat_tests:<8} {result['passed']:<8} "
                      f"{result['failed']:<8} {result['duration']:<12.2f} {status}")
            
            print("-" * 70)
            print(f"{'TOTAL':<15} {total_tests:<8} {total_passed:<8} {total_failed:<8} "
                  f"{total_duration:<12.2f} {'✅ PASS' if total_failed == 0 else '❌ FAIL'}")
        
        # Show detailed errors if any
        total_errors = sum(len(self.results[cat]['errors']) for cat in self.results)
        if total_errors > 0:
            if self.console:
                self.print_message(f"\n❌ {total_errors} Detailed Errors:", "bold red")
            else:
                print(f"\n❌ {total_errors} Detailed Errors:")
            
            error_count = 0
            for category in self.results:
                for error in self.results[category]['errors'][:5]:  # Show first 5 errors per category
                    error_count += 1
                    if isinstance(error, tuple) and len(error) >= 2:
                        test_name, error_msg = error[0], error[1]
                        if self.console:
                            self.print_message(f"  {error_count}. [{category.title()}] {test_name}", "red")
                            self.print_message(f"     {str(error_msg)[:200]}...", "dim red")
                        else:
                            print(f"  {error_count}. [{category.title()}] {test_name}")
                            print(f"     {str(error_msg)[:200]}...")
                    
                    if error_count >= 10:  # Limit total errors shown
                        break
                
                if error_count >= 10:
                    break
            
            if total_errors > 10:
                if self.console:
                    self.print_message(f"  ... and {total_errors - 10} more errors", "dim red")
                else:
                    print(f"  ... and {total_errors - 10} more errors")
        
        # Overall assessment
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        if success_rate >= 95:
            status_color = "green"
            status_icon = "🎉"
            status_text = "EXCELLENT"
        elif success_rate >= 85:
            status_color = "yellow"
            status_icon = "✅"
            status_text = "GOOD"
        elif success_rate >= 70:
            status_color = "orange"
            status_icon = "⚠️"
            status_text = "NEEDS ATTENTION"
        else:
            status_color = "red"
            status_icon = "❌"
            status_text = "CRITICAL ISSUES"
        
        if self.console:
            result_panel = Panel(
                f"[bold {status_color}]{status_icon} END-TO-END TEST RESULT: {status_text}[/bold {status_color}]\n\n"
                f"Overall Success Rate: [bold]{success_rate:.1f}%[/bold]\n"
                f"Total Tests: {total_tests}\n"
                f"Passed: [green]{total_passed}[/green]\n"
                f"Failed: [red]{total_failed}[/red]\n"
                f"Duration: {total_duration:.2f} seconds",
                title="Final Assessment",
                border_style=status_color
            )
            
            self.console.print(f"\n{result_panel}")
        else:
            print(f"\n{status_icon} END-TO-END TEST RESULT: {status_text}")
            print(f"Overall Success Rate: {success_rate:.1f}%")
            print(f"Total Tests: {total_tests}")
            print(f"Passed: {total_passed}")
            print(f"Failed: {total_failed}")
            print(f"Duration: {total_duration:.2f} seconds")
    
    def run_all_tests(self) -> bool:
        """Run all end-to-end tests."""
        start_time = time.time()
        
        # Show test configuration
        if self.console:
            config_panel = Panel(
                f"[bold cyan]End-to-End Functionality Tests[/bold cyan]\n\n"
                f"Test Categories:\n"
                f"• Complete Workflows: Full command execution validation\n"
                f"• Multi-Platform Integration: Cross-platform operations\n"
                f"• Authentication Systems: Credential and security validation\n\n"
                f"Execution Mode: {'Parallel' if self.parallel else 'Sequential'}\n"
                f"Verbose Output: {'Enabled' if self.verbose else 'Disabled'}\n\n"
                f"[dim]Requirements: 5.1-5.5[/dim]",
                title="🧪 Test Configuration"
            )
            self.console.print(config_panel)
        else:
            print("🧪 End-to-End Functionality Tests")
            print("=" * 50)
            print("Test Categories:")
            print("• Complete Workflows: Full command execution validation")
            print("• Multi-Platform Integration: Cross-platform operations")
            print("• Authentication Systems: Credential and security validation")
            print(f"\nExecution Mode: {'Parallel' if self.parallel else 'Sequential'}")
            print(f"Verbose Output: {'Enabled' if self.verbose else 'Disabled'}")
            print("\nRequirements: 5.1-5.5")
        
        # Run tests
        if self.parallel:
            all_results = self.run_tests_parallel()
        else:
            all_results = self.run_tests_sequential()
        
        # Generate summary report
        self.generate_summary_report(all_results)
        
        # Show execution time
        total_time = time.time() - start_time
        if self.console:
            self.print_message(f"\n⏱️ Total execution time: {total_time:.2f} seconds", "dim")
        else:
            print(f"\n⏱️ Total execution time: {total_time:.2f} seconds")
        
        # Return overall success
        total_failed = sum(self.results[cat]['failed'] for cat in self.results)
        return total_failed == 0


def main():
    """Main entry point for end-to-end test runner."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive end-to-end functionality tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_end_to_end_tests.py                    # Run all tests sequentially
  python run_end_to_end_tests.py --parallel         # Run tests in parallel
  python run_end_to_end_tests.py --verbose          # Run with verbose output
  python run_end_to_end_tests.py --parallel --verbose  # Parallel with verbose output
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose test output'
    )
    
    parser.add_argument(
        '--parallel', '-p',
        action='store_true',
        help='Run tests in parallel (faster but less detailed output)'
    )
    
    parser.add_argument(
        '--category', '-c',
        choices=['workflows', 'integration', 'authentication'],
        help='Run only tests from specific category'
    )
    
    args = parser.parse_args()
    
    try:
        runner = EndToEndTestRunner(verbose=args.verbose, parallel=args.parallel)
        
        # Filter test modules if specific category requested
        if args.category:
            runner.test_modules = [
                (cat, mod) for cat, mod in runner.test_modules 
                if cat == args.category
            ]
        
        success = runner.run_all_tests()
        
        if success:
            print("\n🎉 All end-to-end tests passed! Import migration and service restoration is complete.")
            sys.exit(0)
        else:
            print("\n💥 Some end-to-end tests failed. Please review the errors above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error during test execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()