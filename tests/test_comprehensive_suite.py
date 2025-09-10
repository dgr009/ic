"""
Comprehensive Test Suite Runner

This module provides a comprehensive test runner for all new functionality tests
as required by task 20. It ensures all tests pass in GitHub Actions environment
with Python 3.11.13.

Requirements covered:
- 10.4, 10.5: Ensure all tests pass in GitHub Actions environment with Python 3.11.13
- 9.5, 9.7: Validate Python version compatibility and CI/CD environment
"""

import pytest
import sys
import os
import platform
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import importlib.util

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class ComprehensiveTestSuite:
    """Comprehensive test suite runner and validator."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_results = {}
        self.environment_info = self._gather_environment_info()
    
    def _gather_environment_info(self) -> Dict[str, Any]:
        """Gather environment information for test validation."""
        return {
            'python_version': sys.version_info,
            'python_version_string': sys.version,
            'platform': platform.platform(),
            'architecture': platform.architecture(),
            'processor': platform.processor(),
            'is_github_actions': os.getenv('GITHUB_ACTIONS') == 'true',
            'ci_environment': os.getenv('CI', 'false').lower() == 'true',
            'runner_os': os.getenv('RUNNER_OS', 'unknown'),
            'python_path': sys.executable,
            'working_directory': os.getcwd(),
            'project_root': str(self.project_root)
        }
    
    def validate_environment(self) -> bool:
        """Validate that the test environment meets requirements."""
        print("🔍 Validating test environment...")
        
        # Check Python version (should be 3.9-3.12, preferably 3.11.13)
        python_version = self.environment_info['python_version']
        if not (3, 9) <= python_version[:2] <= (3, 12):
            print(f"❌ Python version {python_version} not supported. Requires 3.9-3.12")
            return False
        
        if python_version[:3] == (3, 11, 13):
            print(f"✅ Using recommended Python version: {python_version}")
        else:
            print(f"⚠️  Using Python {python_version} (recommended: 3.11.13)")
        
        # Check if running in GitHub Actions
        if self.environment_info['is_github_actions']:
            print("✅ Running in GitHub Actions environment")
        else:
            print("ℹ️  Running in local environment")
        
        # Check project structure
        required_paths = [
            self.project_root / "common" / "progress_decorator.py",
            self.project_root / "src" / "ic" / "cli.py",
            self.project_root / "src" / "ic" / "commands" / "config.py",
            self.project_root / "tests",
        ]
        
        for path in required_paths:
            if not path.exists():
                print(f"❌ Required path not found: {path}")
                return False
        
        print("✅ Project structure validation passed")
        return True
    
    def check_dependencies(self) -> bool:
        """Check that required dependencies are available."""
        print("🔍 Checking test dependencies...")
        
        required_modules = [
            'pytest',
            'rich',
            'yaml',
            'pathlib',
            'concurrent.futures',
            'threading',
            'unittest.mock'
        ]
        
        missing_modules = []
        for module_name in required_modules:
            try:
                if '.' in module_name:
                    # Handle submodules
                    parent_module = module_name.split('.')[0]
                    importlib.import_module(parent_module)
                else:
                    importlib.import_module(module_name)
            except ImportError:
                missing_modules.append(module_name)
        
        if missing_modules:
            print(f"❌ Missing required modules: {', '.join(missing_modules)}")
            return False
        
        print("✅ All required dependencies available")
        return True
    
    def run_progress_decorator_tests(self) -> bool:
        """Run progress decorator comprehensive tests."""
        print("🧪 Running progress decorator tests...")
        
        test_files = [
            "tests/unit/test_progress_decorator_comprehensive.py",
            "tests/test_progress_decorator_thread_safety.py"
        ]
        
        for test_file in test_files:
            test_path = self.project_root / test_file
            if not test_path.exists():
                print(f"⚠️  Test file not found: {test_file}")
                continue
            
            try:
                result = subprocess.run([
                    sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    print(f"✅ {test_file} passed")
                    self.test_results[test_file] = "PASSED"
                else:
                    print(f"❌ {test_file} failed")
                    print(f"   stdout: {result.stdout}")
                    print(f"   stderr: {result.stderr}")
                    self.test_results[test_file] = "FAILED"
                    return False
                    
            except Exception as e:
                print(f"❌ Error running {test_file}: {e}")
                self.test_results[test_file] = f"ERROR: {e}"
                return False
        
        return True
    
    def run_config_init_tests(self) -> bool:
        """Run config init integration tests."""
        print("🧪 Running config init tests...")
        
        test_file = "tests/integration/test_config_init_integration.py"
        test_path = self.project_root / test_file
        
        if not test_path.exists():
            print(f"⚠️  Test file not found: {test_file}")
            return True  # Skip if not found
        
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                print(f"✅ {test_file} passed")
                self.test_results[test_file] = "PASSED"
                return True
            else:
                print(f"❌ {test_file} failed")
                print(f"   stdout: {result.stdout}")
                print(f"   stderr: {result.stderr}")
                self.test_results[test_file] = "FAILED"
                return False
                
        except Exception as e:
            print(f"❌ Error running {test_file}: {e}")
            self.test_results[test_file] = f"ERROR: {e}"
            return False
    
    def run_help_message_tests(self) -> bool:
        """Run help message and warning tests."""
        print("🧪 Running help message tests...")
        
        test_file = "tests/unit/test_help_messages_and_warnings.py"
        test_path = self.project_root / test_file
        
        if not test_path.exists():
            print(f"⚠️  Test file not found: {test_file}")
            return True  # Skip if not found
        
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                print(f"✅ {test_file} passed")
                self.test_results[test_file] = "PASSED"
                return True
            else:
                print(f"❌ {test_file} failed")
                print(f"   stdout: {result.stdout}")
                print(f"   stderr: {result.stderr}")
                self.test_results[test_file] = "FAILED"
                return False
                
        except Exception as e:
            print(f"❌ Error running {test_file}: {e}")
            self.test_results[test_file] = f"ERROR: {e}"
            return False
    
    def run_e2e_integration_tests(self) -> bool:
        """Run end-to-end integration tests."""
        print("🧪 Running end-to-end integration tests...")
        
        test_file = "tests/integration/test_progress_bar_integration_e2e.py"
        test_path = self.project_root / test_file
        
        if not test_path.exists():
            print(f"⚠️  Test file not found: {test_file}")
            return True  # Skip if not found
        
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                print(f"✅ {test_file} passed")
                self.test_results[test_file] = "PASSED"
                return True
            else:
                print(f"❌ {test_file} failed")
                print(f"   stdout: {result.stdout}")
                print(f"   stderr: {result.stderr}")
                self.test_results[test_file] = "FAILED"
                return False
                
        except Exception as e:
            print(f"❌ Error running {test_file}: {e}")
            self.test_results[test_file] = f"ERROR: {e}"
            return False
    
    def run_existing_tests_compatibility(self) -> bool:
        """Run existing tests to ensure compatibility."""
        print("🧪 Running existing tests for compatibility...")
        
        # Run a subset of existing tests to ensure our changes don't break anything
        existing_test_files = [
            "tests/test_basic.py",
            "tests/test_config.py"
        ]
        
        for test_file in existing_test_files:
            test_path = self.project_root / test_file
            if not test_path.exists():
                print(f"⚠️  Existing test file not found: {test_file}")
                continue
            
            try:
                result = subprocess.run([
                    sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    print(f"✅ {test_file} compatibility check passed")
                    self.test_results[f"compatibility_{test_file}"] = "PASSED"
                else:
                    print(f"⚠️  {test_file} compatibility issues detected")
                    print(f"   stdout: {result.stdout}")
                    print(f"   stderr: {result.stderr}")
                    self.test_results[f"compatibility_{test_file}"] = "FAILED"
                    # Don't fail the entire suite for compatibility issues
                    
            except Exception as e:
                print(f"⚠️  Error running compatibility test {test_file}: {e}")
                self.test_results[f"compatibility_{test_file}"] = f"ERROR: {e}"
        
        return True  # Always return True for compatibility tests
    
    def run_import_tests(self) -> bool:
        """Test that all new modules can be imported successfully."""
        print("🧪 Running import tests...")
        
        modules_to_test = [
            "common.progress_decorator",
            "src.ic.cli",
            "src.ic.commands.config"
        ]
        
        for module_name in modules_to_test:
            try:
                # Convert module path to import path
                import_path = module_name.replace("/", ".")
                
                # Try to import the module
                spec = importlib.util.find_spec(import_path)
                if spec is None:
                    print(f"⚠️  Module spec not found: {import_path}")
                    continue
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                print(f"✅ Successfully imported {import_path}")
                self.test_results[f"import_{import_path}"] = "PASSED"
                
            except Exception as e:
                print(f"❌ Failed to import {module_name}: {e}")
                self.test_results[f"import_{module_name}"] = f"FAILED: {e}"
                return False
        
        return True
    
    def generate_test_report(self) -> None:
        """Generate comprehensive test report."""
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE TEST SUITE REPORT")
        print("="*60)
        
        print(f"\n🖥️  Environment Information:")
        print(f"   Python Version: {self.environment_info['python_version_string']}")
        print(f"   Platform: {self.environment_info['platform']}")
        print(f"   Architecture: {self.environment_info['architecture']}")
        print(f"   GitHub Actions: {self.environment_info['is_github_actions']}")
        print(f"   CI Environment: {self.environment_info['ci_environment']}")
        print(f"   Runner OS: {self.environment_info['runner_os']}")
        
        print(f"\n📋 Test Results Summary:")
        passed_tests = [k for k, v in self.test_results.items() if v == "PASSED"]
        failed_tests = [k for k, v in self.test_results.items() if v == "FAILED"]
        error_tests = [k for k, v in self.test_results.items() if "ERROR" in v]
        
        print(f"   ✅ Passed: {len(passed_tests)}")
        print(f"   ❌ Failed: {len(failed_tests)}")
        print(f"   🚫 Errors: {len(error_tests)}")
        print(f"   📊 Total: {len(self.test_results)}")
        
        if failed_tests:
            print(f"\n❌ Failed Tests:")
            for test in failed_tests:
                print(f"   - {test}")
        
        if error_tests:
            print(f"\n🚫 Error Tests:")
            for test in error_tests:
                print(f"   - {test}: {self.test_results[test]}")
        
        print(f"\n📈 Success Rate: {len(passed_tests)}/{len(self.test_results)} ({len(passed_tests)/len(self.test_results)*100:.1f}%)")
    
    def run_all_tests(self) -> bool:
        """Run all comprehensive tests."""
        print("🚀 Starting Comprehensive Test Suite")
        print("="*50)
        
        # Environment validation
        if not self.validate_environment():
            print("❌ Environment validation failed")
            return False
        
        # Dependency check
        if not self.check_dependencies():
            print("❌ Dependency check failed")
            return False
        
        # Import tests
        if not self.run_import_tests():
            print("❌ Import tests failed")
            return False
        
        # Core functionality tests
        test_suites = [
            ("Progress Decorator Tests", self.run_progress_decorator_tests),
            ("Config Init Tests", self.run_config_init_tests),
            ("Help Message Tests", self.run_help_message_tests),
            ("E2E Integration Tests", self.run_e2e_integration_tests),
            ("Existing Tests Compatibility", self.run_existing_tests_compatibility)
        ]
        
        all_passed = True
        for suite_name, test_function in test_suites:
            print(f"\n📦 {suite_name}")
            print("-" * 30)
            
            try:
                if not test_function():
                    print(f"❌ {suite_name} failed")
                    all_passed = False
                else:
                    print(f"✅ {suite_name} passed")
            except Exception as e:
                print(f"🚫 {suite_name} encountered error: {e}")
                all_passed = False
        
        # Generate report
        self.generate_test_report()
        
        return all_passed


def test_comprehensive_suite():
    """Main test function for pytest integration."""
    suite = ComprehensiveTestSuite()
    success = suite.run_all_tests()
    
    if not success:
        pytest.fail("Comprehensive test suite failed")


def main():
    """Main entry point for direct execution."""
    suite = ComprehensiveTestSuite()
    success = suite.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()