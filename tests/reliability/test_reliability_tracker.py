#!/usr/bin/env python3
"""
Test Reliability and Issue Tracking System

Implements flaky test detection, issue tracking, and test result consistency validation
across multiple runs to ensure reliable test execution.

Requirements: 7.7 - Test reliability and issue tracking system
"""

import os
import json
import time
import hashlib
import statistics
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import threading
from collections import defaultdict, deque


class TestReliabilityStatus(Enum):
    """Test reliability status levels."""
    RELIABLE = "reliable"           # Consistent results across runs
    FLAKY = "flaky"                # Inconsistent results
    UNSTABLE = "unstable"          # Frequently failing
    BROKEN = "broken"              # Consistently failing
    NEW = "new"                    # Insufficient data
    QUARANTINED = "quarantined"    # Temporarily disabled


class IssueType(Enum):
    """Types of test issues."""
    FLAKY_TEST = "flaky_test"
    TIMEOUT = "timeout"
    ENVIRONMENT_DEPENDENT = "environment_dependent"
    RACE_CONDITION = "race_condition"
    RESOURCE_LEAK = "resource_leak"
    CONFIGURATION_ISSUE = "configuration_issue"
    DEPENDENCY_FAILURE = "dependency_failure"
    ASSERTION_ERROR = "assertion_error"
    UNKNOWN = "unknown"


class IssueSeverity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"    # Blocks testing
    HIGH = "high"           # Significant impact
    MEDIUM = "medium"       # Moderate impact
    LOW = "low"            # Minor impact
    INFO = "info"          # Informational


@dataclass
class TestExecution:
    """Record of a single test execution."""
    test_id: str
    timestamp: float
    duration: float
    status: str  # passed, failed, skipped, error
    platform: str
    service: str
    test_category: str
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    environment: str = "unknown"
    ci_run_id: Optional[str] = None
    commit_hash: Optional[str] = None


@dataclass
class TestReliabilityMetrics:
    """Reliability metrics for a test."""
    test_id: str
    total_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    skipped_runs: int = 0
    error_runs: int = 0
    success_rate: float = 0.0
    average_duration: float = 0.0
    duration_variance: float = 0.0
    flakiness_score: float = 0.0
    reliability_status: TestReliabilityStatus = TestReliabilityStatus.NEW
    last_updated: float = field(default_factory=time.time)
    recent_executions: List[TestExecution] = field(default_factory=list)


@dataclass
class TestIssue:
    """Tracked test issue."""
    issue_id: str
    test_id: str
    issue_type: IssueType
    severity: IssueSeverity
    title: str
    description: str
    first_seen: float
    last_seen: float
    occurrence_count: int = 1
    environments: Set[str] = field(default_factory=set)
    error_patterns: List[str] = field(default_factory=list)
    suggested_fixes: List[str] = field(default_factory=list)
    is_resolved: bool = False
    resolution_notes: Optional[str] = None


@dataclass
class ReliabilityReport:
    """Comprehensive reliability report."""
    generated_at: float
    total_tests: int
    reliable_tests: int
    flaky_tests: int
    unstable_tests: int
    broken_tests: int
    quarantined_tests: int
    overall_reliability_score: float
    test_metrics: Dict[str, TestReliabilityMetrics]
    active_issues: List[TestIssue]
    resolved_issues: List[TestIssue]
    recommendations: List[str]


class TestReliabilityTracker:
    """Tracks test reliability and identifies issues across multiple runs."""
    
    def __init__(self, data_dir: str = "tests/reliability/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.executions_file = self.data_dir / "test_executions.jsonl"
        self.metrics_file = self.data_dir / "test_metrics.json"
        self.issues_file = self.data_dir / "test_issues.json"
        
        # In-memory data structures
        self.test_metrics: Dict[str, TestReliabilityMetrics] = {}
        self.test_issues: Dict[str, TestIssue] = {}
        self.execution_history: deque = deque(maxlen=10000)  # Keep last 10k executions
        
        # Configuration
        self.flaky_threshold = 0.8  # Success rate below this is considered flaky
        self.unstable_threshold = 0.5  # Success rate below this is unstable
        self.broken_threshold = 0.1  # Success rate below this is broken
        self.min_runs_for_reliability = 5  # Minimum runs to assess reliability
        self.max_execution_history = 100  # Max executions to keep per test
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Load existing data
        self._load_data()
    
    def record_test_execution(self, execution: TestExecution):
        """Record a test execution and update reliability metrics."""
        with self.lock:
            # Add to execution history
            self.execution_history.append(execution)
            
            # Update test metrics
            self._update_test_metrics(execution)
            
            # Check for issues
            self._analyze_execution_for_issues(execution)
            
            # Persist data
            self._save_execution(execution)
            self._save_metrics()
            self._save_issues()
    
    def _update_test_metrics(self, execution: TestExecution):
        """Update reliability metrics for a test."""
        test_id = execution.test_id
        
        if test_id not in self.test_metrics:
            self.test_metrics[test_id] = TestReliabilityMetrics(test_id=test_id)
        
        metrics = self.test_metrics[test_id]
        
        # Update execution counts
        metrics.total_runs += 1
        if execution.status == "passed":
            metrics.passed_runs += 1
        elif execution.status == "failed":
            metrics.failed_runs += 1
        elif execution.status == "skipped":
            metrics.skipped_runs += 1
        elif execution.status == "error":
            metrics.error_runs += 1
        
        # Add to recent executions
        metrics.recent_executions.append(execution)
        if len(metrics.recent_executions) > self.max_execution_history:
            metrics.recent_executions = metrics.recent_executions[-self.max_execution_history:]
        
        # Calculate success rate
        if metrics.total_runs > 0:
            metrics.success_rate = metrics.passed_runs / metrics.total_runs
        
        # Calculate duration statistics
        durations = [e.duration for e in metrics.recent_executions if e.duration > 0]
        if durations:
            metrics.average_duration = statistics.mean(durations)
            if len(durations) > 1:
                metrics.duration_variance = statistics.variance(durations)
        
        # Calculate flakiness score
        metrics.flakiness_score = self._calculate_flakiness_score(metrics)
        
        # Determine reliability status
        metrics.reliability_status = self._determine_reliability_status(metrics)
        
        # Update timestamp
        metrics.last_updated = time.time()
    
    def _calculate_flakiness_score(self, metrics: TestReliabilityMetrics) -> float:
        """Calculate flakiness score based on execution patterns."""
        if metrics.total_runs < self.min_runs_for_reliability:
            return 0.0
        
        # Base flakiness on success rate deviation from 0 or 1
        success_rate = metrics.success_rate
        if success_rate <= 0.1 or success_rate >= 0.9:
            # Consistently passing or failing tests are not flaky
            base_flakiness = 0.0
        else:
            # Tests with intermediate success rates are potentially flaky
            base_flakiness = 1.0 - abs(success_rate - 0.5) * 2
        
        # Adjust for recent execution patterns
        recent_results = [e.status for e in metrics.recent_executions[-10:]]
        if len(recent_results) >= 3:
            # Check for alternating patterns
            alternations = 0
            for i in range(1, len(recent_results)):
                if recent_results[i] != recent_results[i-1]:
                    alternations += 1
            
            alternation_ratio = alternations / (len(recent_results) - 1)
            base_flakiness += alternation_ratio * 0.5
        
        # Adjust for duration variance
        if metrics.duration_variance > 0 and metrics.average_duration > 0:
            duration_cv = (metrics.duration_variance ** 0.5) / metrics.average_duration
            if duration_cv > 0.5:  # High coefficient of variation
                base_flakiness += 0.2
        
        return min(1.0, base_flakiness)
    
    def _determine_reliability_status(self, metrics: TestReliabilityMetrics) -> TestReliabilityStatus:
        """Determine reliability status based on metrics."""
        if metrics.total_runs < self.min_runs_for_reliability:
            return TestReliabilityStatus.NEW
        
        success_rate = metrics.success_rate
        flakiness_score = metrics.flakiness_score
        
        # Check if test is quarantined
        if self._is_test_quarantined(metrics.test_id):
            return TestReliabilityStatus.QUARANTINED
        
        # Determine status based on success rate and flakiness
        if success_rate <= self.broken_threshold:
            return TestReliabilityStatus.BROKEN
        elif success_rate <= self.unstable_threshold:
            return TestReliabilityStatus.UNSTABLE
        elif flakiness_score > 0.3 or success_rate < self.flaky_threshold:
            return TestReliabilityStatus.FLAKY
        else:
            return TestReliabilityStatus.RELIABLE
    
    def _analyze_execution_for_issues(self, execution: TestExecution):
        """Analyze execution for potential issues."""
        if execution.status in ["failed", "error"]:
            issue_type = self._classify_issue_type(execution)
            severity = self._determine_issue_severity(execution, issue_type)
            
            # Create or update issue
            issue_id = self._generate_issue_id(execution, issue_type)
            
            if issue_id in self.test_issues:
                # Update existing issue
                issue = self.test_issues[issue_id]
                issue.last_seen = execution.timestamp
                issue.occurrence_count += 1
                issue.environments.add(execution.environment)
                
                # Add error pattern if new
                if execution.error_message and execution.error_message not in issue.error_patterns:
                    issue.error_patterns.append(execution.error_message)
            else:
                # Create new issue
                issue = TestIssue(
                    issue_id=issue_id,
                    test_id=execution.test_id,
                    issue_type=issue_type,
                    severity=severity,
                    title=self._generate_issue_title(execution, issue_type),
                    description=self._generate_issue_description(execution, issue_type),
                    first_seen=execution.timestamp,
                    last_seen=execution.timestamp,
                    environments={execution.environment},
                    error_patterns=[execution.error_message] if execution.error_message else [],
                    suggested_fixes=self._generate_suggested_fixes(execution, issue_type)
                )
                self.test_issues[issue_id] = issue
    
    def _classify_issue_type(self, execution: TestExecution) -> IssueType:
        """Classify the type of issue based on execution details."""
        if not execution.error_message:
            return IssueType.UNKNOWN
        
        error_msg = execution.error_message.lower()
        
        if "timeout" in error_msg or "timed out" in error_msg:
            return IssueType.TIMEOUT
        elif "connection" in error_msg or "network" in error_msg:
            return IssueType.DEPENDENCY_FAILURE
        elif "assertion" in error_msg or "assert" in error_msg:
            return IssueType.ASSERTION_ERROR
        elif "race" in error_msg or "concurrent" in error_msg:
            return IssueType.RACE_CONDITION
        elif "config" in error_msg or "configuration" in error_msg:
            return IssueType.CONFIGURATION_ISSUE
        elif "memory" in error_msg or "resource" in error_msg:
            return IssueType.RESOURCE_LEAK
        elif execution.environment in ["ci", "github_actions"]:
            return IssueType.ENVIRONMENT_DEPENDENT
        else:
            # Check if test shows flaky behavior
            test_metrics = self.test_metrics.get(execution.test_id)
            if test_metrics and test_metrics.flakiness_score > 0.3:
                return IssueType.FLAKY_TEST
            
            return IssueType.UNKNOWN
    
    def _determine_issue_severity(self, execution: TestExecution, issue_type: IssueType) -> IssueSeverity:
        """Determine issue severity."""
        # Check test metrics for frequency
        test_metrics = self.test_metrics.get(execution.test_id)
        
        if issue_type == IssueType.BROKEN:
            return IssueSeverity.CRITICAL
        elif issue_type in [IssueType.TIMEOUT, IssueType.RESOURCE_LEAK]:
            return IssueSeverity.HIGH
        elif issue_type == IssueType.FLAKY_TEST:
            if test_metrics and test_metrics.flakiness_score > 0.7:
                return IssueSeverity.HIGH
            else:
                return IssueSeverity.MEDIUM
        elif issue_type in [IssueType.RACE_CONDITION, IssueType.ENVIRONMENT_DEPENDENT]:
            return IssueSeverity.MEDIUM
        else:
            return IssueSeverity.LOW
    
    def _generate_issue_id(self, execution: TestExecution, issue_type: IssueType) -> str:
        """Generate unique issue ID."""
        # Combine test ID and issue type for grouping similar issues
        content = f"{execution.test_id}:{issue_type.value}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _generate_issue_title(self, execution: TestExecution, issue_type: IssueType) -> str:
        """Generate descriptive issue title."""
        test_name = execution.test_id.split('/')[-1] if '/' in execution.test_id else execution.test_id
        
        titles = {
            IssueType.FLAKY_TEST: f"Flaky test: {test_name}",
            IssueType.TIMEOUT: f"Test timeout: {test_name}",
            IssueType.ENVIRONMENT_DEPENDENT: f"Environment-dependent failure: {test_name}",
            IssueType.RACE_CONDITION: f"Race condition in: {test_name}",
            IssueType.RESOURCE_LEAK: f"Resource leak in: {test_name}",
            IssueType.CONFIGURATION_ISSUE: f"Configuration issue: {test_name}",
            IssueType.DEPENDENCY_FAILURE: f"Dependency failure: {test_name}",
            IssueType.ASSERTION_ERROR: f"Assertion error: {test_name}",
            IssueType.UNKNOWN: f"Unknown issue: {test_name}"
        }
        
        return titles.get(issue_type, f"Test issue: {test_name}")
    
    def _generate_issue_description(self, execution: TestExecution, issue_type: IssueType) -> str:
        """Generate detailed issue description."""
        description = f"Test: {execution.test_id}\n"
        description += f"Platform: {execution.platform}\n"
        description += f"Service: {execution.service}\n"
        description += f"Category: {execution.test_category}\n"
        description += f"Environment: {execution.environment}\n"
        description += f"Issue Type: {issue_type.value}\n"
        
        if execution.error_message:
            description += f"\nError Message:\n{execution.error_message}"
        
        return description
    
    def _generate_suggested_fixes(self, execution: TestExecution, issue_type: IssueType) -> List[str]:
        """Generate suggested fixes based on issue type."""
        fixes = {
            IssueType.FLAKY_TEST: [
                "Add retry logic for transient failures",
                "Increase test timeouts if timing-related",
                "Add proper wait conditions for async operations",
                "Review test isolation and cleanup"
            ],
            IssueType.TIMEOUT: [
                "Increase test timeout values",
                "Optimize test performance",
                "Check for blocking operations",
                "Review network connectivity in test environment"
            ],
            IssueType.ENVIRONMENT_DEPENDENT: [
                "Add environment detection and conditional logic",
                "Use mock services for CI environments",
                "Standardize test environment configuration",
                "Add environment-specific test data"
            ],
            IssueType.RACE_CONDITION: [
                "Add proper synchronization mechanisms",
                "Use deterministic test ordering",
                "Add wait conditions for async operations",
                "Review shared resource access"
            ],
            IssueType.RESOURCE_LEAK: [
                "Add proper resource cleanup in teardown",
                "Use context managers for resource management",
                "Review memory usage patterns",
                "Add resource monitoring to tests"
            ],
            IssueType.CONFIGURATION_ISSUE: [
                "Validate configuration before test execution",
                "Add configuration fallbacks",
                "Document required configuration",
                "Use configuration validation schemas"
            ],
            IssueType.DEPENDENCY_FAILURE: [
                "Add dependency health checks",
                "Use mock services for external dependencies",
                "Add retry logic for network operations",
                "Validate service availability before tests"
            ],
            IssueType.ASSERTION_ERROR: [
                "Review test expectations and assertions",
                "Add more specific assertion messages",
                "Check test data validity",
                "Review business logic changes"
            ]
        }
        
        return fixes.get(issue_type, ["Review test implementation and requirements"])
    
    def _is_test_quarantined(self, test_id: str) -> bool:
        """Check if test is quarantined."""
        # This could be implemented with a quarantine file or database
        quarantine_file = self.data_dir / "quarantined_tests.json"
        if quarantine_file.exists():
            try:
                with open(quarantine_file, 'r') as f:
                    quarantined = json.load(f)
                    return test_id in quarantined
            except (json.JSONDecodeError, IOError):
                pass
        return False
    
    def quarantine_test(self, test_id: str, reason: str):
        """Quarantine a test."""
        quarantine_file = self.data_dir / "quarantined_tests.json"
        
        quarantined = {}
        if quarantine_file.exists():
            try:
                with open(quarantine_file, 'r') as f:
                    quarantined = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        quarantined[test_id] = {
            "reason": reason,
            "quarantined_at": time.time(),
            "quarantined_by": "reliability_tracker"
        }
        
        with open(quarantine_file, 'w') as f:
            json.dump(quarantined, f, indent=2)
        
        # Update test metrics
        if test_id in self.test_metrics:
            self.test_metrics[test_id].reliability_status = TestReliabilityStatus.QUARANTINED
    
    def unquarantine_test(self, test_id: str):
        """Remove test from quarantine."""
        quarantine_file = self.data_dir / "quarantined_tests.json"
        
        if quarantine_file.exists():
            try:
                with open(quarantine_file, 'r') as f:
                    quarantined = json.load(f)
                
                if test_id in quarantined:
                    del quarantined[test_id]
                    
                    with open(quarantine_file, 'w') as f:
                        json.dump(quarantined, f, indent=2)
            except (json.JSONDecodeError, IOError):
                pass
    
    def get_flaky_tests(self, min_flakiness: float = 0.3) -> List[TestReliabilityMetrics]:
        """Get list of flaky tests."""
        return [
            metrics for metrics in self.test_metrics.values()
            if metrics.flakiness_score >= min_flakiness and 
               metrics.total_runs >= self.min_runs_for_reliability
        ]
    
    def get_unreliable_tests(self) -> List[TestReliabilityMetrics]:
        """Get list of unreliable tests."""
        return [
            metrics for metrics in self.test_metrics.values()
            if metrics.reliability_status in [
                TestReliabilityStatus.FLAKY,
                TestReliabilityStatus.UNSTABLE,
                TestReliabilityStatus.BROKEN
            ]
        ]
    
    def get_active_issues(self) -> List[TestIssue]:
        """Get list of active (unresolved) issues."""
        return [issue for issue in self.test_issues.values() if not issue.is_resolved]
    
    def resolve_issue(self, issue_id: str, resolution_notes: str):
        """Mark an issue as resolved."""
        if issue_id in self.test_issues:
            self.test_issues[issue_id].is_resolved = True
            self.test_issues[issue_id].resolution_notes = resolution_notes
            self._save_issues()
    
    def generate_reliability_report(self) -> ReliabilityReport:
        """Generate comprehensive reliability report."""
        total_tests = len(self.test_metrics)
        
        # Count tests by reliability status
        status_counts = defaultdict(int)
        for metrics in self.test_metrics.values():
            status_counts[metrics.reliability_status] += 1
        
        # Calculate overall reliability score
        if total_tests > 0:
            reliable_count = status_counts[TestReliabilityStatus.RELIABLE]
            overall_score = reliable_count / total_tests
        else:
            overall_score = 0.0
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        
        return ReliabilityReport(
            generated_at=time.time(),
            total_tests=total_tests,
            reliable_tests=status_counts[TestReliabilityStatus.RELIABLE],
            flaky_tests=status_counts[TestReliabilityStatus.FLAKY],
            unstable_tests=status_counts[TestReliabilityStatus.UNSTABLE],
            broken_tests=status_counts[TestReliabilityStatus.BROKEN],
            quarantined_tests=status_counts[TestReliabilityStatus.QUARANTINED],
            overall_reliability_score=overall_score,
            test_metrics=dict(self.test_metrics),
            active_issues=self.get_active_issues(),
            resolved_issues=[i for i in self.test_issues.values() if i.is_resolved],
            recommendations=recommendations
        )
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations for improving test reliability."""
        recommendations = []
        
        flaky_tests = self.get_flaky_tests()
        if flaky_tests:
            recommendations.append(
                f"Address {len(flaky_tests)} flaky tests to improve reliability"
            )
        
        active_issues = self.get_active_issues()
        critical_issues = [i for i in active_issues if i.severity == IssueSeverity.CRITICAL]
        if critical_issues:
            recommendations.append(
                f"Resolve {len(critical_issues)} critical issues immediately"
            )
        
        timeout_issues = [i for i in active_issues if i.issue_type == IssueType.TIMEOUT]
        if timeout_issues:
            recommendations.append(
                "Review and optimize test timeouts to reduce timeout failures"
            )
        
        env_issues = [i for i in active_issues if i.issue_type == IssueType.ENVIRONMENT_DEPENDENT]
        if env_issues:
            recommendations.append(
                "Improve test environment consistency and isolation"
            )
        
        return recommendations
    
    def _load_data(self):
        """Load existing data from files."""
        # Load test metrics
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    for test_id, metrics_data in data.items():
                        metrics = TestReliabilityMetrics(**metrics_data)
                        # Convert execution data back to objects
                        metrics.recent_executions = [
                            TestExecution(**exec_data) 
                            for exec_data in metrics_data.get('recent_executions', [])
                        ]
                        self.test_metrics[test_id] = metrics
            except (json.JSONDecodeError, IOError):
                pass
        
        # Load issues
        if self.issues_file.exists():
            try:
                with open(self.issues_file, 'r') as f:
                    data = json.load(f)
                    for issue_id, issue_data in data.items():
                        # Convert sets back from lists
                        if 'environments' in issue_data:
                            issue_data['environments'] = set(issue_data['environments'])
                        issue = TestIssue(**issue_data)
                        self.test_issues[issue_id] = issue
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save_execution(self, execution: TestExecution):
        """Save execution to JSONL file."""
        try:
            with open(self.executions_file, 'a') as f:
                f.write(json.dumps(asdict(execution)) + '\n')
        except IOError:
            pass
    
    def _save_metrics(self):
        """Save test metrics to file."""
        try:
            # Convert to serializable format
            data = {}
            for test_id, metrics in self.test_metrics.items():
                metrics_dict = asdict(metrics)
                # Convert enum to string
                metrics_dict['reliability_status'] = metrics.reliability_status.value
                data[test_id] = metrics_dict
            
            with open(self.metrics_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass
    
    def _save_issues(self):
        """Save issues to file."""
        try:
            data = {}
            for issue_id, issue in self.test_issues.items():
                issue_dict = asdict(issue)
                # Convert enums and sets to serializable format
                issue_dict['issue_type'] = issue.issue_type.value
                issue_dict['severity'] = issue.severity.value
                issue_dict['environments'] = list(issue.environments)
                data[issue_id] = issue_dict
            
            with open(self.issues_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass


# Global tracker instance
_reliability_tracker = None


def get_reliability_tracker() -> TestReliabilityTracker:
    """Get global reliability tracker instance."""
    global _reliability_tracker
    if _reliability_tracker is None:
        _reliability_tracker = TestReliabilityTracker()
    return _reliability_tracker


# Export main classes and functions
__all__ = [
    'TestReliabilityStatus', 'IssueType', 'IssueSeverity',
    'TestExecution', 'TestReliabilityMetrics', 'TestIssue', 'ReliabilityReport',
    'TestReliabilityTracker', 'get_reliability_tracker'
]