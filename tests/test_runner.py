#!/usr/bin/env python3
"""
Comprehensive test runner for GCP services integration.

Runs all unit tests with coverage reporting and detailed output.
"""

import unittest
import sys
import os
import logging
from io import StringIO
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure logging for tests
logging.basicConfig(level=logging.WARNING)

# Import all test modules
from tests.test_gcp_utils import *
from tests.test_mcp_gcp_connector import *
from tests.test_gcp_compute import *
from tests.test_gcp_vpc import *
from tests.test_gcp_gke import *
from tests.test_gcp_sql import *


class GCPTestRunner:
    """Comprehensive test runner for GCP services."""
    
    def __init__(self):
        self.test_modules = [
            'tests.test_gcp_utils',
            'tests.test_mcp_gcp_connector', 
            'tests.test_gcp_compute',
            'tests.test_gcp_vpc',
            'tests.test_gcp_gke',
            'tests.test_gcp_sql'
        ]
        self.results = {}
    
    def run_all_tests(self, verbosity=2):
        """Run all GCP service tests."""
        print("=" * 80)
        print("GCP SERVICES INTEGRATION - COMPREHENSIVE TEST SUITE")
        print("=" * 80)
        
        total_tests = 0
        total_failures = 0
        total_errors = 0
        
        for module_name in self.test_modules:
            print(f"\n{'=' * 60}")
            print(f"Running tests for: {module_name}")
            print(f"{'=' * 60}")
            
            # Load and run tests for this module
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(module_name)
            
            # Capture test output
            stream = StringIO()
            runner = unittest.TextTestRunner(
                stream=stream,
                verbosity=verbosity,
                buffer=True
            )
            
            result = runner.run(suite)
            
            # Store results
            self.results[module_name] = {
                'tests_run': result.testsRun,
                'failures': len(result.failures),
                'errors': len(result.errors),
                'success': result.wasSuccessful()
            }
            
            # Update totals
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
            
            # Print results for this module
            print(f"Tests run: {result.testsRun}")
            print(f"Failures: {len(result.failures)}")
            print(f"Errors: {len(result.errors)}")
            print(f"Success: {result.wasSuccessful()}")
            
            # Print detailed output if there are failures or errors
            if result.failures or result.errors:
                print("\nDetailed Output:")
                print(stream.getvalue())
        
        # Print summary
        self._print_summary(total_tests, total_failures, total_errors)
        
        return total_failures == 0 and total_errors == 0
    
    def run_specific_service_tests(self, service_name, verbosity=2):
        """Run tests for a specific GCP service."""
        module_name = f'tests.test_gcp_{service_name}'
        
        if module_name not in self.test_modules:
            print(f"No tests found for service: {service_name}")
            return False
        
        print(f"Running tests for GCP {service_name.upper()} service...")
        
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(module_name)
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)
        
        return result.wasSuccessful()
    
    def run_mcp_integration_tests(self, verbosity=2):
        """Run MCP integration specific tests."""
        print("Running MCP Integration Tests...")
        
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName('tests.test_mcp_gcp_connector')
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)
        
        return result.wasSuccessful()
    
    def run_authentication_tests(self, verbosity=2):
        """Run authentication specific tests."""
        print("Running Authentication Tests...")
        
        loader = unittest.TestLoader()
        
        # Load specific test classes related to authentication
        from tests.test_gcp_utils import TestGCPAuthManager, TestGCPProjectManager
        
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(TestGCPAuthManager))
        suite.addTest(unittest.makeSuite(TestGCPProjectManager))
        
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)
        
        return result.wasSuccessful()
    
    def _print_summary(self, total_tests, total_failures, total_errors):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        print(f"Total tests run: {total_tests}")
        print(f"Total failures: {total_failures}")
        print(f"Total errors: {total_errors}")
        
        success_rate = ((total_tests - total_failures - total_errors) / total_tests * 100) if total_tests > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")
        
        if total_failures == 0 and total_errors == 0:
            print("\n🎉 ALL TESTS PASSED! 🎉")
        else:
            print(f"\n❌ {total_failures + total_errors} tests failed")
        
        # Print per-module results
        print("\nPer-module results:")
        for module, results in self.results.items():
            status = "✅ PASS" if results['success'] else "❌ FAIL"
            print(f"  {module}: {status} ({results['tests_run']} tests)")
    
    def run_with_coverage(self):
        """Run tests with coverage reporting (if coverage.py is available)."""
        try:
            import coverage
            
            # Start coverage
            cov = coverage.Coverage()
            cov.start()
            
            # Run tests
            success = self.run_all_tests()
            
            # Stop coverage and report
            cov.stop()
            cov.save()
            
            print("\n" + "=" * 80)
            print("COVERAGE REPORT")
            print("=" * 80)
            cov.report()
            
            return success
            
        except ImportError:
            print("Coverage.py not available. Running tests without coverage.")
            return self.run_all_tests()


def main():
    """Main test runner entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='GCP Services Integration Test Runner')
    parser.add_argument('--service', help='Run tests for specific service (compute, vpc, gke, etc.)')
    parser.add_argument('--mcp', action='store_true', help='Run MCP integration tests only')
    parser.add_argument('--auth', action='store_true', help='Run authentication tests only')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage reporting')
    parser.add_argument('--verbose', '-v', action='count', default=1, help='Increase verbosity')
    
    args = parser.parse_args()
    
    runner = GCPTestRunner()
    
    if args.service:
        success = runner.run_specific_service_tests(args.service, args.verbose)
    elif args.mcp:
        success = runner.run_mcp_integration_tests(args.verbose)
    elif args.auth:
        success = runner.run_authentication_tests(args.verbose)
    elif args.coverage:
        success = runner.run_with_coverage()
    else:
        success = runner.run_all_tests(args.verbose)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()