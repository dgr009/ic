"""
Test Execution Transparency System

This module provides comprehensive test execution transparency with detailed progress
indicators, comprehensive result reporting, and actionable debugging information.

Requirements: 7.1, 7.2, 7.3, 7.6 - Test execution transparency and error reporting

Components:
- TestExecutionTracker: Core tracking and progress monitoring
- EnhancedTestRunner: Integrated test runner with transparency
- TestErrorAnalyzer: Failure analysis and debugging assistance
- TestReportGenerator: Comprehensive reporting and visualization

Usage:
    from tests.transparency import EnhancedTestRunner
    
    runner = EnhancedTestRunner()
    tests = runner.discover_tests(platforms=['ncp', 'ncpgov'])
    results = runner.execute_tests()
    runner.generate_comprehensive_report()
"""

from .test_execution_tracker import (
    TestExecutionStatus,
    TestCategory,
    TestMetrics,
    TestFailureInfo,
    TestExecutionContext,
    TestResult,
    TestProgressTracker,
    TestErrorAnalyzer,
    TestReportGenerator
)

from .enhanced_test_runner import EnhancedTestRunner

__version__ = "1.0.0"

__all__ = [
    # Core data structures
    'TestExecutionStatus',
    'TestCategory', 
    'TestMetrics',
    'TestFailureInfo',
    'TestExecutionContext',
    'TestResult',
    
    # Core components
    'TestProgressTracker',
    'TestErrorAnalyzer', 
    'TestReportGenerator',
    'EnhancedTestRunner'
]