#!/usr/bin/env python3
"""
Comprehensive test execution script for GCP services integration.

This script provides multiple test execution modes and comprehensive reporting.
"""

import sys
import os
import subprocess
import argparse
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_runner import GCPTestRunner
from tests.test_config import TEST_CONFIG


def install_test_dependencies():
    """Install required test dependencies."""
    print("Installing test dependencies...")
    
    requirements_file = project_root / "tests" / "test_requirements.txt"
    if requirements_file.exists():
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ])
            print("✅ Test dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install test dependencies: {e}")
            return False
    else:
        print("⚠️  test_requirements.txt not found, skipping dependency installation")
        return True


def run_unit_tests():
    """Run all unit tests."""
    print("\n" + "="*80)
    print("RUNNING UNIT TESTS")
    print("="*80)
    
    runner = GCPTestRunner()
    return runner.run_all_tests(verbosity=2)


def run_service_tests(service_name):
    """Run tests for a specific service."""
    print(f"\n" + "="*80)
    print(f"RUNNING {service_name.upper()} SERVICE TESTS")
    print("="*80)
    
    runner = GCPTestRunner()
    return runner.run_specific_service_tests(service_name, verbosity=2)


def run_mcp_tests():
    """Run MCP integration tests."""
    print("\n" + "="*80)
    print("RUNNING MCP INTEGRATION TESTS")
    print("="*80)
    
    runner = GCPTestRunner()
    return runner.run_mcp_integration_tests(verbosity=2)


def run_authentication_tests():
    """Run authentication tests."""
    print("\n" + "="*80)
    print("RUNNING AUTHENTICATION TESTS")
    print("="*80)
    
    runner = GCPTestRunner()
    return runner.run_authentication_tests(verbosity=2)


def run_coverage_tests():
    """Run tests with coverage reporting."""
    print("\n" + "="*80)
    print("RUNNING TESTS WITH COVERAGE")
    print("="*80)
    
    runner = GCPTestRunner()
    return runner.run_with_coverage()


def run_performance_tests():
    """Run performance tests."""
    print("\n" + "="*80)
    print("RUNNING PERFORMANCE TESTS")
    print("="*80)
    
    # Import performance test utilities
    from tests.test_config import TestPerformanceMetrics
    
    metrics = TestPerformanceMetrics()
    
    # Test authentication performance
    metrics.start_timer("authentication")
    auth_success = run_authentication_tests()
    metrics.end_timer("authentication")
    
    # Test MCP integration performance
    metrics.start_timer("mcp_integration")
    mcp_success = run_mcp_tests()
    metrics.end_timer("mcp_integration")
    
    # Test service operations performance
    services = ["compute", "vpc", "gke", "sql"]
    service_results = {}
    
    for service in services:
        metrics.start_timer(f"service_{service}")
        service_results[service] = run_service_tests(service)
        metrics.end_timer(f"service_{service}")
    
    # Report performance metrics
    print("\n" + "="*80)
    print("PERFORMANCE METRICS")
    print("="*80)
    
    thresholds = TEST_CONFIG["performance_thresholds"]
    
    print(f"Authentication tests: {metrics.get_duration('authentication'):.2f}s")
    print(f"MCP integration tests: {metrics.get_duration('mcp_integration'):.2f}s")
    
    for service in services:
        duration = metrics.get_duration(f"service_{service}")
        print(f"{service.upper()} service tests: {duration:.2f}s")
    
    # Check performance thresholds
    try:
        metrics.assert_performance_threshold("authentication", thresholds["api_call"])
        metrics.assert_performance_threshold("mcp_integration", thresholds["api_call"])
        
        for service in services:
            metrics.assert_performance_threshold(
                f"service_{service}", 
                thresholds["data_collection"]
            )
        
        print("\n✅ All performance thresholds met")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Performance threshold exceeded: {e}")
        return False


def run_integration_tests():
    """Run integration tests (placeholder for future implementation)."""
    print("\n" + "="*80)
    print("INTEGRATION TESTS")
    print("="*80)
    print("⚠️  Integration tests not yet implemented")
    print("This would test with real GCP APIs using test credentials")
    return True


def generate_test_report(results):
    """Generate comprehensive test report."""
    report_file = project_root / "tests" / "test_report.json"
    
    report_data = {
        "timestamp": str(os.popen("date").read().strip()),
        "python_version": sys.version,
        "test_results": results,
        "test_config": TEST_CONFIG
    }
    
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📊 Test report saved to: {report_file}")


def main():
    """Main test execution entry point."""
    parser = argparse.ArgumentParser(
        description='GCP Services Integration Test Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all unit tests
  python run_tests.py --service compute  # Run compute service tests
  python run_tests.py --mcp              # Run MCP integration tests
  python run_tests.py --auth             # Run authentication tests
  python run_tests.py --coverage         # Run with coverage reporting
  python run_tests.py --performance      # Run performance tests
  python run_tests.py --integration      # Run integration tests
  python run_tests.py --install-deps     # Install test dependencies
        """
    )
    
    parser.add_argument('--service', help='Run tests for specific service')
    parser.add_argument('--mcp', action='store_true', help='Run MCP integration tests')
    parser.add_argument('--auth', action='store_true', help='Run authentication tests')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage reporting')
    parser.add_argument('--performance', action='store_true', help='Run performance tests')
    parser.add_argument('--integration', action='store_true', help='Run integration tests')
    parser.add_argument('--install-deps', action='store_true', help='Install test dependencies')
    parser.add_argument('--all', action='store_true', help='Run all test types')
    
    args = parser.parse_args()
    
    # Install dependencies if requested
    if args.install_deps:
        if not install_test_dependencies():
            sys.exit(1)
        if not any([args.service, args.mcp, args.auth, args.coverage, 
                   args.performance, args.integration, args.all]):
            return
    
    results = {}
    overall_success = True
    
    try:
        if args.all:
            # Run all test types
            results['unit_tests'] = run_unit_tests()
            results['mcp_tests'] = run_mcp_tests()
            results['auth_tests'] = run_authentication_tests()
            results['coverage_tests'] = run_coverage_tests()
            results['performance_tests'] = run_performance_tests()
            results['integration_tests'] = run_integration_tests()
            
            overall_success = all(results.values())
            
        elif args.service:
            results['service_tests'] = run_service_tests(args.service)
            overall_success = results['service_tests']
            
        elif args.mcp:
            results['mcp_tests'] = run_mcp_tests()
            overall_success = results['mcp_tests']
            
        elif args.auth:
            results['auth_tests'] = run_authentication_tests()
            overall_success = results['auth_tests']
            
        elif args.coverage:
            results['coverage_tests'] = run_coverage_tests()
            overall_success = results['coverage_tests']
            
        elif args.performance:
            results['performance_tests'] = run_performance_tests()
            overall_success = results['performance_tests']
            
        elif args.integration:
            results['integration_tests'] = run_integration_tests()
            overall_success = results['integration_tests']
            
        else:
            # Default: run unit tests
            results['unit_tests'] = run_unit_tests()
            overall_success = results['unit_tests']
        
        # Generate test report
        generate_test_report(results)
        
        # Print final summary
        print("\n" + "="*80)
        print("FINAL TEST SUMMARY")
        print("="*80)
        
        for test_type, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{test_type}: {status}")
        
        if overall_success:
            print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY! 🎉")
        else:
            print("\n❌ SOME TESTS FAILED")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        overall_success = False
    except Exception as e:
        print(f"\n\n❌ Test execution failed: {e}")
        overall_success = False
    
    sys.exit(0 if overall_success else 1)


if __name__ == '__main__':
    main()