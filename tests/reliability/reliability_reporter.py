#!/usr/bin/env python3
"""
Test Reliability Reporter

Generates comprehensive reports on test reliability, flaky test detection,
and issue tracking with actionable recommendations.

Requirements: 7.7 - Test reliability reporting and documentation
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
import statistics

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

from tests.reliability.test_reliability_tracker import (
    TestReliabilityTracker, TestReliabilityStatus, IssueType, IssueSeverity,
    ReliabilityReport, get_reliability_tracker
)


class ReliabilityReporter:
    """Generates comprehensive reliability reports and documentation."""
    
    def __init__(self, tracker: Optional[TestReliabilityTracker] = None):
        self.tracker = tracker or get_reliability_tracker()
        self.console = Console() if RICH_AVAILABLE else None
    
    def generate_console_report(self, detailed: bool = False):
        """Generate and display console report."""
        if not RICH_AVAILABLE or not self.console:
            self._generate_simple_report(detailed)
            return
        
        report = self.tracker.generate_reliability_report()
        
        # Main summary
        self._display_summary_panel(report)
        
        # Test reliability breakdown
        self._display_reliability_breakdown(report)
        
        # Active issues
        if report.active_issues:
            self._display_active_issues(report.active_issues)
        
        # Flaky tests
        flaky_tests = [m for m in report.test_metrics.values() 
                      if m.reliability_status == TestReliabilityStatus.FLAKY]
        if flaky_tests:
            self._display_flaky_tests(flaky_tests)
        
        # Recommendations
        if report.recommendations:
            self._display_recommendations(report.recommendations)
        
        if detailed:
            self._display_detailed_metrics(report)
    
    def _display_summary_panel(self, report: ReliabilityReport):
        """Display main summary panel."""
        summary_text = f"""
📊 Total Tests: {report.total_tests}
✅ Reliable: {report.reliable_tests} ({(report.reliable_tests/max(report.total_tests,1)*100):.1f}%)
🔄 Flaky: {report.flaky_tests} ({(report.flaky_tests/max(report.total_tests,1)*100):.1f}%)
⚠️  Unstable: {report.unstable_tests} ({(report.unstable_tests/max(report.total_tests,1)*100):.1f}%)
❌ Broken: {report.broken_tests} ({(report.broken_tests/max(report.total_tests,1)*100):.1f}%)
🚫 Quarantined: {report.quarantined_tests} ({(report.quarantined_tests/max(report.total_tests,1)*100):.1f}%)

🎯 Overall Reliability Score: {report.overall_reliability_score:.2%}
🐛 Active Issues: {len(report.active_issues)}
✅ Resolved Issues: {len(report.resolved_issues)}
        """.strip()
        
        panel = Panel(
            summary_text,
            title="🔍 Test Reliability Summary",
            border_style="blue"
        )
        self.console.print(panel)
    
    def _display_reliability_breakdown(self, report: ReliabilityReport):
        """Display reliability breakdown table."""
        table = Table(title="📈 Reliability Breakdown by Status")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="magenta")
        table.add_column("Percentage", style="green")
        table.add_column("Description", style="white")
        
        total = max(report.total_tests, 1)
        
        status_info = [
            ("✅ Reliable", report.reliable_tests, "Consistently passing tests"),
            ("🔄 Flaky", report.flaky_tests, "Intermittently failing tests"),
            ("⚠️  Unstable", report.unstable_tests, "Frequently failing tests"),
            ("❌ Broken", report.broken_tests, "Consistently failing tests"),
            ("🚫 Quarantined", report.quarantined_tests, "Temporarily disabled tests")
        ]
        
        for status, count, description in status_info:
            percentage = f"{(count/total*100):.1f}%"
            table.add_row(status, str(count), percentage, description)
        
        self.console.print(table)
    
    def _display_active_issues(self, issues: List):
        """Display active issues table."""
        table = Table(title="🐛 Active Issues")
        table.add_column("Issue ID", style="cyan")
        table.add_column("Test", style="white")
        table.add_column("Type", style="yellow")
        table.add_column("Severity", style="red")
        table.add_column("Count", style="magenta")
        table.add_column("Last Seen", style="green")
        
        # Sort by severity and occurrence count
        severity_order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3,
            IssueSeverity.INFO: 4
        }
        
        sorted_issues = sorted(
            issues,
            key=lambda x: (severity_order.get(x.severity, 5), -x.occurrence_count)
        )
        
        for issue in sorted_issues[:20]:  # Show top 20 issues
            test_name = issue.test_id.split('/')[-1] if '/' in issue.test_id else issue.test_id
            last_seen = datetime.fromtimestamp(issue.last_seen).strftime("%m-%d %H:%M")
            
            severity_icon = {
                IssueSeverity.CRITICAL: "🔴",
                IssueSeverity.HIGH: "🟠",
                IssueSeverity.MEDIUM: "🟡",
                IssueSeverity.LOW: "🟢",
                IssueSeverity.INFO: "🔵"
            }.get(issue.severity, "⚪")
            
            table.add_row(
                issue.issue_id[:8],
                test_name[:30],
                issue.issue_type.value,
                f"{severity_icon} {issue.severity.value}",
                str(issue.occurrence_count),
                last_seen
            )
        
        self.console.print(table)
    
    def _display_flaky_tests(self, flaky_tests: List):
        """Display flaky tests table."""
        table = Table(title="🔄 Flaky Tests")
        table.add_column("Test", style="cyan")
        table.add_column("Platform", style="yellow")
        table.add_column("Service", style="green")
        table.add_column("Success Rate", style="magenta")
        table.add_column("Flakiness", style="red")
        table.add_column("Total Runs", style="white")
        
        # Sort by flakiness score
        sorted_tests = sorted(flaky_tests, key=lambda x: x.flakiness_score, reverse=True)
        
        for metrics in sorted_tests[:15]:  # Show top 15 flaky tests
            test_name = metrics.test_id.split('/')[-1] if '/' in metrics.test_id else metrics.test_id
            
            # Extract platform and service from test_id if possible
            parts = metrics.test_id.split('/')
            platform = parts[0] if len(parts) > 0 else "unknown"
            service = parts[1] if len(parts) > 1 else "unknown"
            
            success_rate = f"{metrics.success_rate:.1%}"
            flakiness = f"{metrics.flakiness_score:.2f}"
            
            table.add_row(
                test_name[:40],
                platform,
                service,
                success_rate,
                flakiness,
                str(metrics.total_runs)
            )
        
        self.console.print(table)
    
    def _display_recommendations(self, recommendations: List[str]):
        """Display recommendations panel."""
        rec_text = "\n".join(f"• {rec}" for rec in recommendations)
        
        panel = Panel(
            rec_text,
            title="💡 Recommendations",
            border_style="green"
        )
        self.console.print(panel)
    
    def _display_detailed_metrics(self, report: ReliabilityReport):
        """Display detailed metrics for all tests."""
        table = Table(title="📊 Detailed Test Metrics")
        table.add_column("Test", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Runs", style="magenta")
        table.add_column("Success Rate", style="green")
        table.add_column("Avg Duration", style="yellow")
        table.add_column("Flakiness", style="red")
        
        # Sort by reliability status and success rate
        status_order = {
            TestReliabilityStatus.BROKEN: 0,
            TestReliabilityStatus.UNSTABLE: 1,
            TestReliabilityStatus.FLAKY: 2,
            TestReliabilityStatus.QUARANTINED: 3,
            TestReliabilityStatus.RELIABLE: 4,
            TestReliabilityStatus.NEW: 5
        }
        
        sorted_metrics = sorted(
            report.test_metrics.values(),
            key=lambda x: (status_order.get(x.reliability_status, 6), -x.success_rate)
        )
        
        for metrics in sorted_metrics:
            test_name = metrics.test_id.split('/')[-1] if '/' in metrics.test_id else metrics.test_id
            
            status_icon = {
                TestReliabilityStatus.RELIABLE: "✅",
                TestReliabilityStatus.FLAKY: "🔄",
                TestReliabilityStatus.UNSTABLE: "⚠️",
                TestReliabilityStatus.BROKEN: "❌",
                TestReliabilityStatus.QUARANTINED: "🚫",
                TestReliabilityStatus.NEW: "🆕"
            }.get(metrics.reliability_status, "❓")
            
            table.add_row(
                test_name[:40],
                f"{status_icon} {metrics.reliability_status.value}",
                str(metrics.total_runs),
                f"{metrics.success_rate:.1%}",
                f"{metrics.average_duration:.2f}s",
                f"{metrics.flakiness_score:.2f}"
            )
        
        self.console.print(table)
    
    def _generate_simple_report(self, detailed: bool = False):
        """Generate simple text-based report when rich is not available."""
        report = self.tracker.generate_reliability_report()
        
        print("\n" + "="*60)
        print("TEST RELIABILITY REPORT")
        print("="*60)
        
        print(f"Total Tests: {report.total_tests}")
        print(f"Reliable: {report.reliable_tests} ({(report.reliable_tests/max(report.total_tests,1)*100):.1f}%)")
        print(f"Flaky: {report.flaky_tests} ({(report.flaky_tests/max(report.total_tests,1)*100):.1f}%)")
        print(f"Unstable: {report.unstable_tests} ({(report.unstable_tests/max(report.total_tests,1)*100):.1f}%)")
        print(f"Broken: {report.broken_tests} ({(report.broken_tests/max(report.total_tests,1)*100):.1f}%)")
        print(f"Quarantined: {report.quarantined_tests} ({(report.quarantined_tests/max(report.total_tests,1)*100):.1f}%)")
        print(f"Overall Reliability Score: {report.overall_reliability_score:.2%}")
        
        if report.active_issues:
            print(f"\nActive Issues: {len(report.active_issues)}")
            for issue in report.active_issues[:10]:
                print(f"  - {issue.issue_id[:8]}: {issue.title}")
        
        if report.recommendations:
            print("\nRecommendations:")
            for rec in report.recommendations:
                print(f"  • {rec}")
        
        print("="*60)
    
    def generate_json_report(self, output_file: str):
        """Generate JSON report file."""
        report = self.tracker.generate_reliability_report()
        
        # Convert to serializable format
        report_data = {
            "generated_at": report.generated_at,
            "summary": {
                "total_tests": report.total_tests,
                "reliable_tests": report.reliable_tests,
                "flaky_tests": report.flaky_tests,
                "unstable_tests": report.unstable_tests,
                "broken_tests": report.broken_tests,
                "quarantined_tests": report.quarantined_tests,
                "overall_reliability_score": report.overall_reliability_score
            },
            "test_metrics": {
                test_id: {
                    "test_id": metrics.test_id,
                    "total_runs": metrics.total_runs,
                    "success_rate": metrics.success_rate,
                    "average_duration": metrics.average_duration,
                    "flakiness_score": metrics.flakiness_score,
                    "reliability_status": metrics.reliability_status.value,
                    "last_updated": metrics.last_updated
                }
                for test_id, metrics in report.test_metrics.items()
            },
            "active_issues": [
                {
                    "issue_id": issue.issue_id,
                    "test_id": issue.test_id,
                    "issue_type": issue.issue_type.value,
                    "severity": issue.severity.value,
                    "title": issue.title,
                    "occurrence_count": issue.occurrence_count,
                    "first_seen": issue.first_seen,
                    "last_seen": issue.last_seen,
                    "environments": list(issue.environments),
                    "suggested_fixes": issue.suggested_fixes
                }
                for issue in report.active_issues
            ],
            "recommendations": report.recommendations
        }
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"JSON report saved to {output_file}")
    
    def generate_html_report(self, output_file: str):
        """Generate HTML report file."""
        report = self.tracker.generate_reliability_report()
        
        html_content = self._generate_html_content(report)
        
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"HTML report saved to {output_file}")
    
    def _generate_html_content(self, report: ReliabilityReport) -> str:
        """Generate HTML content for the report."""
        timestamp = datetime.fromtimestamp(report.generated_at).strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Reliability Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f0f8ff; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background: white; border-radius: 3px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .reliable {{ color: green; }}
        .flaky {{ color: orange; }}
        .unstable {{ color: red; }}
        .broken {{ color: darkred; }}
        .quarantined {{ color: gray; }}
        .critical {{ background-color: #ffebee; }}
        .high {{ background-color: #fff3e0; }}
        .medium {{ background-color: #fffde7; }}
        .low {{ background-color: #f1f8e9; }}
    </style>
</head>
<body>
    <h1>🔍 Test Reliability Report</h1>
    <p>Generated: {timestamp}</p>
    
    <div class="summary">
        <h2>📊 Summary</h2>
        <div class="metric">
            <strong>Total Tests:</strong> {report.total_tests}
        </div>
        <div class="metric">
            <strong>Reliability Score:</strong> {report.overall_reliability_score:.2%}
        </div>
        <div class="metric">
            <strong>Active Issues:</strong> {len(report.active_issues)}
        </div>
    </div>
    
    <h2>📈 Reliability Breakdown</h2>
    <table>
        <tr>
            <th>Status</th>
            <th>Count</th>
            <th>Percentage</th>
        </tr>
        <tr class="reliable">
            <td>✅ Reliable</td>
            <td>{report.reliable_tests}</td>
            <td>{(report.reliable_tests/max(report.total_tests,1)*100):.1f}%</td>
        </tr>
        <tr class="flaky">
            <td>🔄 Flaky</td>
            <td>{report.flaky_tests}</td>
            <td>{(report.flaky_tests/max(report.total_tests,1)*100):.1f}%</td>
        </tr>
        <tr class="unstable">
            <td>⚠️ Unstable</td>
            <td>{report.unstable_tests}</td>
            <td>{(report.unstable_tests/max(report.total_tests,1)*100):.1f}%</td>
        </tr>
        <tr class="broken">
            <td>❌ Broken</td>
            <td>{report.broken_tests}</td>
            <td>{(report.broken_tests/max(report.total_tests,1)*100):.1f}%</td>
        </tr>
        <tr class="quarantined">
            <td>🚫 Quarantined</td>
            <td>{report.quarantined_tests}</td>
            <td>{(report.quarantined_tests/max(report.total_tests,1)*100):.1f}%</td>
        </tr>
    </table>
        """
        
        # Add active issues table
        if report.active_issues:
            html += """
    <h2>🐛 Active Issues</h2>
    <table>
        <tr>
            <th>Issue ID</th>
            <th>Test</th>
            <th>Type</th>
            <th>Severity</th>
            <th>Count</th>
            <th>Last Seen</th>
        </tr>
            """
            
            for issue in report.active_issues[:20]:
                test_name = issue.test_id.split('/')[-1] if '/' in issue.test_id else issue.test_id
                last_seen = datetime.fromtimestamp(issue.last_seen).strftime("%m-%d %H:%M")
                severity_class = issue.severity.value
                
                html += f"""
        <tr class="{severity_class}">
            <td>{issue.issue_id[:8]}</td>
            <td>{test_name}</td>
            <td>{issue.issue_type.value}</td>
            <td>{issue.severity.value}</td>
            <td>{issue.occurrence_count}</td>
            <td>{last_seen}</td>
        </tr>
                """
            
            html += "</table>"
        
        # Add recommendations
        if report.recommendations:
            html += """
    <h2>💡 Recommendations</h2>
    <ul>
            """
            for rec in report.recommendations:
                html += f"<li>{rec}</li>"
            
            html += "</ul>"
        
        html += """
</body>
</html>
        """
        
        return html
    
    def generate_markdown_report(self, output_file: str):
        """Generate Markdown report file."""
        report = self.tracker.generate_reliability_report()
        
        timestamp = datetime.fromtimestamp(report.generated_at).strftime("%Y-%m-%d %H:%M:%S")
        
        markdown = f"""# 🔍 Test Reliability Report

Generated: {timestamp}

## 📊 Summary

- **Total Tests:** {report.total_tests}
- **Reliability Score:** {report.overall_reliability_score:.2%}
- **Active Issues:** {len(report.active_issues)}
- **Resolved Issues:** {len(report.resolved_issues)}

## 📈 Reliability Breakdown

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Reliable | {report.reliable_tests} | {(report.reliable_tests/max(report.total_tests,1)*100):.1f}% |
| 🔄 Flaky | {report.flaky_tests} | {(report.flaky_tests/max(report.total_tests,1)*100):.1f}% |
| ⚠️ Unstable | {report.unstable_tests} | {(report.unstable_tests/max(report.total_tests,1)*100):.1f}% |
| ❌ Broken | {report.broken_tests} | {(report.broken_tests/max(report.total_tests,1)*100):.1f}% |
| 🚫 Quarantined | {report.quarantined_tests} | {(report.quarantined_tests/max(report.total_tests,1)*100):.1f}% |

"""
        
        # Add active issues
        if report.active_issues:
            markdown += """## 🐛 Active Issues

| Issue ID | Test | Type | Severity | Count | Last Seen |
|----------|------|------|----------|-------|-----------|
"""
            
            for issue in report.active_issues[:20]:
                test_name = issue.test_id.split('/')[-1] if '/' in issue.test_id else issue.test_id
                last_seen = datetime.fromtimestamp(issue.last_seen).strftime("%m-%d %H:%M")
                
                markdown += f"| {issue.issue_id[:8]} | {test_name} | {issue.issue_type.value} | {issue.severity.value} | {issue.occurrence_count} | {last_seen} |\n"
        
        # Add recommendations
        if report.recommendations:
            markdown += "\n## 💡 Recommendations\n\n"
            for rec in report.recommendations:
                markdown += f"- {rec}\n"
        
        with open(output_file, 'w') as f:
            f.write(markdown)
        
        print(f"Markdown report saved to {output_file}")


def main():
    """Main entry point for reliability reporter."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Reliability Reporter")
    parser.add_argument("--format", choices=["console", "json", "html", "markdown"], 
                       default="console", help="Report format")
    parser.add_argument("--output", help="Output file (for non-console formats)")
    parser.add_argument("--detailed", action="store_true", help="Include detailed metrics")
    
    args = parser.parse_args()
    
    reporter = ReliabilityReporter()
    
    if args.format == "console":
        reporter.generate_console_report(detailed=args.detailed)
    elif args.format == "json":
        output_file = args.output or f"reliability_report_{int(time.time())}.json"
        reporter.generate_json_report(output_file)
    elif args.format == "html":
        output_file = args.output or f"reliability_report_{int(time.time())}.html"
        reporter.generate_html_report(output_file)
    elif args.format == "markdown":
        output_file = args.output or f"reliability_report_{int(time.time())}.md"
        reporter.generate_markdown_report(output_file)


if __name__ == "__main__":
    main()