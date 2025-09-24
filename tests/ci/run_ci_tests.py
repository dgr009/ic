#!/usr/bin/env python3
"""
CI Test Execution Script

Specialized test runner for CI environments with enhanced error reporting,
platform-specific test execution, and clear failure diagnostics.

Requirements: 3.4, 3.6 - CI-specific test execution scripts and error reporting

Usage:
    python tests/ci/run_ci_tests.py --platform ncp --test-type unit
    python tests/ci/run_ci_tests.py --all-platforms --test-type integration
    python tests/ci/run_ci_tests.py --validate-only
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json
import time
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.ci.environment import is_ci_environment, get_ci_info
from tests.ci.env_support import setup_ci_environment_variables, get_env_summary
from tests.ci.mock_configs import get_mock_config, get_mock_client


class CITestRunner:
    """Specialized test runner for CI environments."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.start_time = time.time()
        self.test_results: Dict[str, Any] = {}
        
        # Configure logging
        log_level = logging.INFO if verbose else logging.WARNING
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/tmp/ci_test_runner.log', mode='w')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_ci_environment(self) -> bool:
        """Set up CI environment and validate configuration."""
        self.logger.info("Setting up CI test environment...")
        
        try:
            # Set up environment variables
            env_vars = setup_ci_environment_variables()
            self.logger.info(f"Set up {len(env_vars)} environment variables")
            
            # Validate CI detection
            if not is_ci_environment():
                self.logger.warning("CI environment not detected, forcing CI mode")
                os.environ['CI'] = 'true'
                os.environ['IC_CI_MODE'] = 'true'
            
            # Get CI info
            ci_info = get_ci_info()
            self.logger.info(f"CI Provider: {ci_info.get('provider', 'Unknown')}")
            self.logger.info(f"Python Version: {ci_info.get('python_version', 'Unknown')}")
            
            # Validate environment
            env_summary = get_env_summary()
            self.logger.info(f"Environment summary: {env_summary}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set up CI environment: {e}")
            return False
    
    def validate_platform_config(self, platform: str) -> Tuple[bool, List[str]]:
        """Validate platform configuration and mock data."""
        self.logger.info(f"Validating {platform} configuration...")
        
        issues = []
        
        try:
            # Test mock configuration
            config = get_mock_config(platform)
            if not config:
                issues.append(f"No mock configuration available for {platform}")
            else:
                self.logger.info(f"✅ Mock configuration loaded for {platform}")
            
            # Test mock client
            client = get_mock_client(platform)
            if not client:
                issues.append(f"No mock client available for {platform}")
            else:
                self.logger.info(f"✅ Mock client created for {platform}")
            
        except Exception as e:
            issues.append(f"Platform validation failed: {str(e)}")
            self.logger.error(f"❌ {platform} validation failed: {e}")
        
        return len(issues) == 0, issues
    
    def discover_tests(self, platform: str, test_type: str) -> List[Path]:
        """Discover test files for specified platform and test type."""
        test_paths = []
        
        # Platform-specific test paths
        platform_test_dir = Path(f"tests/platforms/{platform}")
        
        if test_type == "all":
            # Find all test files for the platform
            if platform_test_dir.exists():
                test_paths.extend(platform_test_dir.rglob("test_*.py"))
        else:
            # Find specific test type
            test_type_dirs = platform_test_dir.rglob(f"*/{test_type}/")
            for test_dir in test_type_dirs:
                if test_dir.is_dir():
                    test_paths.extend(test_dir.glob("test_*.py"))
        
        # Also check for legacy test files
        legacy_patterns = [
            f"tests/test_{platform}_*.py",
            f"tests/test_*_{platform}.py",
            f"tests/**/test_{platform}_*.py"
        ]
        
        for pattern in legacy_patterns:
            test_paths.extend(Path("tests").glob(pattern))
        
        # Remove duplicates and sort
        unique_paths = list(set(test_paths))
        unique_paths.sort()
        
        self.logger.info(f"Discovered {len(unique_paths)} test files for {platform}/{test_type}")
        return unique_paths
    
    def run_pytest(self, test_paths: List[Path], platform: str, test_type: str) -> Tuple[bool, Dict[str, Any]]:
        """Run pytest with CI-optimized settings."""
        if not test_paths:
            self.logger.warning(f"No test files found for {platform}/{test_type}")
            return True, {"status": "skipped", "reason": "no_tests_found"}
        
        # Prepare pytest command
        cmd = [
            sys.executable, "-m", "pytest",
            "--verbose",
            "--tb=short",
            "--maxfail=5",
            "--durations=10",
            "--strict-markers",
            "--strict-config",
            f"--junitxml=test-results-{platform}-{test_type}.xml",
            f"--cov=src",
            f"--cov-report=xml:coverage-{platform}-{test_type}.xml",
            "--cov-report=term-missing",
            "-m", "not slow"  # Skip slow tests in CI
        ]
        
        # Add test paths
        cmd.extend([str(path) for path in test_paths])
        
        # Set environment variables for the test run
        env = os.environ.copy()
        env.update({
            'IC_TEST_PLATFORM': platform,
            'IC_TEST_TYPE': test_type,
            'PYTHONPATH': f"{project_root}/src:{project_root}",
            'PYTEST_CURRENT_TEST': f"{platform}-{test_type}"
        })
        
        self.logger.info(f"Running pytest for {platform}/{test_type}...")
        self.logger.debug(f"Command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per test suite
            )
            
            duration = time.time() - start_time
            
            # Parse results
            test_result = {
                "status": "passed" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": ' '.join(cmd)
            }
            
            if result.returncode == 0:
                self.logger.info(f"✅ {platform}/{test_type} tests passed ({duration:.2f}s)")
            else:
                self.logger.error(f"❌ {platform}/{test_type} tests failed ({duration:.2f}s)")
                if self.verbose:
                    self.logger.error(f"STDOUT:\n{result.stdout}")
                    self.logger.error(f"STDERR:\n{result.stderr}")
            
            return result.returncode == 0, test_result
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ {platform}/{test_type} tests timed out after 5 minutes")
            return False, {
                "status": "timeout",
                "duration": 300,
                "error": "Test execution timed out"
            }
        
        except Exception as e:
            self.logger.error(f"❌ {platform}/{test_type} test execution failed: {e}")
            return False, {
                "status": "error",
                "error": str(e)
            }
    
    def run_platform_tests(self, platform: str, test_type: str = "all") -> bool:
        """Run tests for a specific platform."""
        self.logger.info(f"Running {test_type} tests for {platform}...")
        
        # Validate platform configuration
        config_valid, config_issues = self.validate_platform_config(platform)
        if not config_valid:
            self.logger.error(f"Platform {platform} configuration validation failed:")
            for issue in config_issues:
                self.logger.error(f"  - {issue}")
            
            self.test_results[f"{platform}_{test_type}"] = {
                "status": "failed",
                "reason": "config_validation_failed",
                "issues": config_issues
            }
            return False
        
        # Discover and run tests
        test_paths = self.discover_tests(platform, test_type)
        
        if not test_paths:
            self.logger.warning(f"No tests found for {platform}/{test_type}")
            self.test_results[f"{platform}_{test_type}"] = {
                "status": "skipped",
                "reason": "no_tests_found"
            }
            return True
        
        # Run pytest
        success, result = self.run_pytest(test_paths, platform, test_type)
        self.test_results[f"{platform}_{test_type}"] = result
        
        return success
    
    def run_all_platform_tests(self, platforms: List[str], test_type: str = "all") -> Dict[str, bool]:
        """Run tests for all specified platforms."""
        results = {}
        
        for platform in platforms:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Testing platform: {platform.upper()}")
            self.logger.info(f"{'='*60}")
            
            try:
                success = self.run_platform_tests(platform, test_type)
                results[platform] = success
            except Exception as e:
                self.logger.error(f"Failed to test platform {platform}: {e}")
                results[platform] = False
                self.test_results[f"{platform}_{test_type}"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_duration = time.time() - self.start_time
        
        # Count results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results.values() 
                          if r.get("status") == "passed")
        failed_tests = sum(1 for r in self.test_results.values() 
                          if r.get("status") == "failed")
        skipped_tests = sum(1 for r in self.test_results.values() 
                           if r.get("status") == "skipped")
        error_tests = sum(1 for r in self.test_results.values() 
                         if r.get("status") == "error")
        
        report = {
            "summary": {
                "total_duration": total_duration,
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "skipped": skipped_tests,
                "errors": error_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            "ci_info": get_ci_info(),
            "environment": get_env_summary(),
            "test_results": self.test_results,
            "timestamp": datetime.now().isoformat()
        }
        
        return report
    
    def print_summary(self, results: Dict[str, bool]):
        """Print test execution summary."""
        total_duration = time.time() - self.start_time
        
        print(f"\n{'='*80}")
        print("CI TEST EXECUTION SUMMARY")
        print(f"{'='*80}")
        
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"CI Environment: {get_ci_info().get('provider', 'Unknown')}")
        print(f"Python Version: {get_ci_info().get('python_version', 'Unknown')}")
        
        print(f"\nPlatform Results:")
        for platform, success in results.items():
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"  {platform:15} {status}")
        
        # Overall statistics
        total_platforms = len(results)
        passed_platforms = sum(1 for success in results.values() if success)
        failed_platforms = total_platforms - passed_platforms
        
        print(f"\nOverall Statistics:")
        print(f"  Total Platforms: {total_platforms}")
        print(f"  Passed: {passed_platforms}")
        print(f"  Failed: {failed_platforms}")
        print(f"  Success Rate: {(passed_platforms/total_platforms*100):.1f}%")
        
        # Detailed failures
        if failed_platforms > 0:
            print(f"\nFailure Details:")
            for platform, success in results.items():
                if not success:
                    test_key = f"{platform}_all"  # Default test type
                    if test_key in self.test_results:
                        result = self.test_results[test_key]
                        print(f"  {platform}:")
                        if "error" in result:
                            print(f"    Error: {result['error']}")
                        if "issues" in result:
                            for issue in result["issues"]:
                                print(f"    Issue: {issue}")
        
        print(f"\n{'='*80}")


def main():
    """Main entry point for CI test runner."""
    parser = argparse.ArgumentParser(description='Run IC CLI tests in CI environment')
    parser.add_argument('--platform', choices=['aws', 'azure', 'gcp', 'oci', 'ncp', 'ncpgov', 'cloudflare'],
                       help='Platform to test')
    parser.add_argument('--all-platforms', action='store_true',
                       help='Test all platforms')
    parser.add_argument('--test-type', choices=['unit', 'integration', 'performance', 'all'],
                       default='all', help='Type of tests to run')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate configurations without running tests')
    parser.add_argument('--quiet', action='store_true',
                       help='Reduce output verbosity')
    parser.add_argument('--report-file', help='Save test report to file')
    
    args = parser.parse_args()
    
    # Create test runner
    runner = CITestRunner(verbose=not args.quiet)
    
    try:
        # Set up CI environment
        if not runner.setup_ci_environment():
            print("❌ Failed to set up CI environment")
            return 1
        
        # Determine platforms to test
        if args.all_platforms:
            platforms = ['aws', 'azure', 'gcp', 'oci', 'ncp', 'ncpgov', 'cloudflare']
        elif args.platform:
            platforms = [args.platform]
        else:
            # Default to NCP platforms for quick validation
            platforms = ['ncp', 'ncpgov']
        
        # Validation only mode
        if args.validate_only:
            print("🔍 Validating platform configurations...")
            all_valid = True
            
            for platform in platforms:
                valid, issues = runner.validate_platform_config(platform)
                if valid:
                    print(f"✅ {platform.upper()} configuration is valid")
                else:
                    print(f"❌ {platform.upper()} configuration issues:")
                    for issue in issues:
                        print(f"   - {issue}")
                    all_valid = False
            
            return 0 if all_valid else 1
        
        # Run tests
        print(f"🚀 Running {args.test_type} tests for platforms: {', '.join(platforms)}")
        results = runner.run_all_platform_tests(platforms, args.test_type)
        
        # Generate and save report
        report = runner.generate_test_report()
        if args.report_file:
            with open(args.report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"📊 Test report saved to {args.report_file}")
        
        # Print summary
        runner.print_summary(results)
        
        # Return appropriate exit code
        all_passed = all(results.values())
        return 0 if all_passed else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        return 130
    
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        runner.logger.exception("Test execution failed with exception")
        return 1


if __name__ == '__main__':
    sys.exit(main())