"""
Test Reliability and Issue Tracking System

Provides comprehensive test reliability tracking, flaky test detection, and issue
management with detailed reporting and recommendations for improvement.

Requirements: 7.7 - Test reliability and issue tracking system

Components:
- TestReliabilityTracker: Core reliability tracking and metrics
- ReliabilityReporter: Comprehensive reporting and visualization
- Issue tracking and classification system
- Flaky test detection and analysis

Usage:
    from tests.reliability import get_reliability_tracker, ReliabilityReporter
    
    # Track test execution
    tracker = get_reliability_tracker()
    execution = TestExecution(
        test_id="ncp/ec2/unit/test_instance_list",
        timestamp=time.time(),
        duration=1.5,
        status="passed",
        platform="ncp",
        service="ec2",
        test_category="unit"
    )
    tracker.record_test_execution(execution)
    
    # Generate reliability report
    reporter = ReliabilityReporter(tracker)
    reporter.generate_console_report(detailed=True)
    
    # Get flaky tests
    flaky_tests = tracker.get_flaky_tests()
    
    # Get active issues
    active_issues = tracker.get_active_issues()
"""

from .test_reliability_tracker import (
    TestReliabilityStatus,
    IssueType,
    IssueSeverity,
    TestExecution,
    TestReliabilityMetrics,
    TestIssue,
    ReliabilityReport,
    TestReliabilityTracker,
    get_reliability_tracker
)

from .reliability_reporter import ReliabilityReporter

__version__ = "1.0.0"

__all__ = [
    # Core enums and data structures
    'TestReliabilityStatus',
    'IssueType',
    'IssueSeverity',
    'TestExecution',
    'TestReliabilityMetrics',
    'TestIssue',
    'ReliabilityReport',
    
    # Core components
    'TestReliabilityTracker',
    'get_reliability_tracker',
    'ReliabilityReporter'
]