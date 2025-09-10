#!/usr/bin/env python3
"""
CI/CD Test Runner

This script runs tests specifically designed for CI/CD environments.
It focuses on tests that don't require:
- Live cloud credentials
- ~/.ic/config files  
- External network access
- Specific file system permissions

Usage:
    python tests/run_ci_tests.py
    python tests/run_ci_tests.py --verbose
    python tests/run_ci_tests.py --coverage
"""

import sys
import os
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


def run_ci_tests(verbose=False, coverage=False):
    """Run CI-safe tests."""
    
    # Set CI environment variables
    os.environ['CI'] = 'true'
    os.environ['GITHUB_ACTIONS'] = 'true'
    
    # Test files that are safe to run in CI
    ci_safe_tests = [
        'tests/test_ci_cd_infrastructure.py',
        'tests/test_ci_configuration.py', 
        'tests/test_progress_decorator_thread_safety.py',
        'tests/test_basic.py',
        # New comprehensive test suite (Task 20)
        'tests/unit/test_progress_decorator_comprehensive.py',
        'tests/unit/test_help_messages_and_warnings.py',
        'tests/integration/test_config_init_integration.py',
        'tests/integration/test_progress_bar_integration_e2e.py',
        'tests/test_comprehensive_suite.py',
    ]
    
    # Build pytest command
    cmd = ['python', '-m', 'pytest']
    
    if verbose:
        cmd.append('-v')
    
    if coverage:
        cmd.extend(['--cov=ic', '--cov=common', '--cov-report=term-missing'])
    
    # Add markers to run only CI-safe tests
    cmd.extend(['-m', 'ci_safe or not (requires_config or requires_credentials)'])
    
    # Add test files
    cmd.extend(ci_safe_tests)
    
    # Add additional pytest options
    cmd.extend([
        '--tb=short',  # Shorter traceback format
        '--strict-markers',  # Strict marker checking
        '-x',  # Stop on first failure
    ])
    
    print(f"Running CI tests with command: {' '.join(cmd)}")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    
    # Run tests
    try:
        result = subprocess.run(cmd, check=True, cwd=project_root)
        print("\n✅ All CI tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ CI tests failed with exit code {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("❌ pytest not found. Please install pytest: pip install pytest")
        return 1


def check_dependencies():
    """Check that required dependencies are available."""
    required_packages = [
        'pytest',
        'yaml', 
        'pathlib',
        'dataclasses',
        'concurrent.futures'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Please install missing packages:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All required dependencies are available")
    return True


def check_imports():
    """Check that core modules can be imported."""
    try:
        # Test core imports
        from ic.config.manager import ConfigManager
        from ic.config.security import SecurityManager
        from ic.core.logging import ICLogger
        from common.progress_decorator import ProgressBarDecorator
        
        # Test new functionality imports (Task 20)
        from common.progress_decorator import (
            progress_bar, 
            spinner, 
            concurrent_progress, 
            ManualProgress
        )
        from src.ic.cli import DevelopmentStatusHelpFormatter
        from src.ic.commands.config import ConfigCommands
        
        print("✅ Core modules and new functionality imported successfully")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import core modules: {e}")
        print("This may indicate missing dependencies or incorrect installation")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run CI/CD tests')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Verbose output')
    parser.add_argument('--coverage', '-c', action='store_true',
                       help='Run with coverage reporting')
    parser.add_argument('--check-only', action='store_true',
                       help='Only check dependencies and imports')
    
    args = parser.parse_args()
    
    print("🚀 IC CLI CI/CD Test Runner")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Check imports
    if not check_imports():
        return 1
    
    if args.check_only:
        print("✅ All checks passed!")
        return 0
    
    # Run tests
    return run_ci_tests(verbose=args.verbose, coverage=args.coverage)


if __name__ == '__main__':
    sys.exit(main())