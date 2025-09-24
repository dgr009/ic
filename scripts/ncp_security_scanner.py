#!/usr/bin/env python3
"""
NCP Security Scanner

This script performs comprehensive security validation for NCP services integration,
including hardcoded credential scanning, file permission validation, government
compliance checks, and sensitive data masking validation.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ic.config.security import SecurityManager, NCPSecurityValidator, NCPComplianceChecker

console = Console()


class NCPSecurityScanner:
    """
    Comprehensive NCP security scanner for validating NCP services integration.
    """
    
    def __init__(self):
        """Initialize the security scanner."""
        self.security_manager = SecurityManager()
        self.ncp_validator = NCPSecurityValidator(self.security_manager)
        self.compliance_checker = NCPComplianceChecker()
        self.scan_results = {
            'hardcoded_credentials': [],
            'file_permissions': [],
            'compliance_violations': [],
            'sensitive_data_leaks': [],
            'pypi_safety_issues': []
        }
    
    def scan_hardcoded_credentials(self, directory: str = ".") -> List[str]:
        """
        Scan for hardcoded NCP credentials in source code.
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of credential violations found
        """
        console.print("[blue]🔍 Scanning for hardcoded credentials...[/blue]")
        
        violations = []
        ncp_patterns = [
            # NCP Access Keys (typically 20 characters)
            (r'(?i)(ncp[_-]?access[_-]?key|access[_-]?key)\s*[=:]\s*["\']?([A-Za-z0-9]{20,})["\']?', 'NCP Access Key'),
            # NCP Secret Keys (typically 40+ characters, base64-like)
            (r'(?i)(ncp[_-]?secret[_-]?key|secret[_-]?key)\s*[=:]\s*["\']?([A-Za-z0-9+/]{40,}={0,2})["\']?', 'NCP Secret Key'),
            # NCP Gov API Gateway Keys
            (r'(?i)(apigw[_-]?key|api[_-]?gateway[_-]?key)\s*[=:]\s*["\']?([A-Za-z0-9+/]{32,})["\']?', 'NCP Gov API Gateway Key'),
            # General API keys that might be NCP-related
            (r'(?i)(api[_-]?key)\s*[=:]\s*["\']?([A-Za-z0-9+/]{20,})["\']?', 'API Key'),
            # Private IPs (potentially sensitive in government cloud)
            (r'(?i)(private[_-]?ip|internal[_-]?ip)\s*[=:]\s*["\']?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})["\']?', 'Private IP Address'),
            # VPC/Subnet IDs
            (r'(?i)(vpc[_-]?id|subnet[_-]?id)\s*[=:]\s*["\']?([a-zA-Z0-9-]{8,})["\']?', 'VPC/Subnet ID'),
        ]
        
        try:
            for root, dirs, files in os.walk(directory):
                # Skip certain directories
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.pytest_cache', 'logs', 'backup', 'tests'}]
                
                for file in files:
                    if self._should_scan_file(file):
                        file_path = os.path.join(root, file)
                        # Skip files in test directories
                        if '/tests/' in file_path or '\\tests\\' in file_path:
                            continue
                        file_violations = self._scan_file_for_ncp_credentials(file_path, ncp_patterns)
                        violations.extend(file_violations)
        
        except Exception as e:
            console.print(f"[red]Error scanning for credentials: {e}[/red]")
        
        self.scan_results['hardcoded_credentials'] = violations
        return violations
    
    def _should_scan_file(self, filename: str) -> bool:
        """Determine if file should be scanned for credentials."""
        scan_extensions = {'.py', '.js', '.ts', '.yaml', '.yml', '.json', '.env', '.sh', '.bash', '.md'}
        skip_files = {
            'requirements.txt', 'package.json', 'setup.py', 'pyproject.toml',
            'CHANGELOG.md', 'README.md', 'LICENSE', 'MANIFEST.in'
        }
        
        # Skip test files and mock data files
        skip_patterns = ['test_', 'mock_', '_test.', '_mock.', 'conftest.py']
        
        if filename in skip_files:
            return False
        
        # Skip test and mock files
        if any(pattern in filename.lower() for pattern in skip_patterns):
            return False
        
        return any(filename.endswith(ext) for ext in scan_extensions)
    
    def _scan_file_for_ncp_credentials(self, file_path: str, patterns: List[tuple]) -> List[str]:
        """Scan individual file for NCP credentials."""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            for pattern, credential_type in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    credential_value = match.group(2) if len(match.groups()) >= 2 else match.group(1)
                    if not self._is_placeholder_credential(credential_value):
                        line_number = self._get_line_number(content, match.start())
                        violations.append(
                            f"Hardcoded {credential_type} found in {file_path}:{line_number} - Value: {credential_value[:8]}..."
                        )
        
        except Exception as e:
            console.print(f"[dim]Could not scan file {file_path}: {e}[/dim]")
        
        return violations
    
    def _is_placeholder_credential(self, value: str) -> bool:
        """Check if credential value is a placeholder."""
        placeholder_patterns = [
            r'^your[_-].*[_-]here$',
            r'^<.*>$',
            r'^\[.*\]$',
            r'^example.*',
            r'^test.*',
            r'^dummy.*',
            r'^placeholder.*',
            r'^xxx+$',
            r'^000+$',
            r'^abc+$',
            r'^123+$',
        ]
        
        value_lower = value.lower()
        return any(re.match(pattern, value_lower) for pattern in placeholder_patterns)
    
    def _get_line_number(self, content: str, position: int) -> int:
        """Get line number for a position in content."""
        return content[:position].count('\n') + 1
    
    def validate_file_permissions(self, config_paths: List[str] = None) -> List[str]:
        """
        Validate NCP configuration file permissions.
        
        Args:
            config_paths: List of configuration file paths to check
            
        Returns:
            List of permission violations
        """
        console.print("[blue]🔒 Validating file permissions...[/blue]")
        
        if config_paths is None:
            config_paths = [
                "~/.ncp/config",
                "~/.ncpgov/config",
                ".ncp/config.example",
                ".ncpgov/config.example",
                ".env",
                "config.yaml",
                "config.yml"
            ]
        
        violations = []
        
        for config_path in config_paths:
            path = Path(config_path).expanduser()
            
            if not path.exists():
                continue
            
            try:
                # Check file permissions (Unix systems only)
                if os.name != 'nt':
                    file_mode = oct(path.stat().st_mode)[-3:]
                    if file_mode not in ['600', '644']:  # 644 allowed for example files
                        if 'example' not in str(path) and file_mode != '600':
                            violations.append(
                                f"Insecure file permissions for {path}: {file_mode} (should be 600 for config files)"
                            )
                        elif 'example' in str(path) and file_mode not in ['644', '600']:
                            violations.append(
                                f"Insecure file permissions for {path}: {file_mode} (should be 644 or 600 for example files)"
                            )
                
                # Check directory permissions
                parent_dir = path.parent
                if parent_dir.exists() and os.name != 'nt':
                    dir_mode = oct(parent_dir.stat().st_mode)[-3:]
                    if dir_mode not in ['700', '755']:
                        violations.append(
                            f"Insecure directory permissions for {parent_dir}: {dir_mode} (should be 700 or 755)"
                        )
            
            except Exception as e:
                console.print(f"[dim]Could not check permissions for {path}: {e}[/dim]")
        
        self.scan_results['file_permissions'] = violations
        return violations
    
    def validate_government_compliance(self, config_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate government cloud compliance for NCP Gov.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            Compliance validation results
        """
        console.print("[blue]🏛️ Validating government compliance...[/blue]")
        
        if config_data is None:
            # Try to load from default NCP Gov config
            try:
                from common.ncpgov_utils import load_ncpgov_config
                config_data = load_ncpgov_config()
            except:
                config_data = {}
        
        compliance_results = {
            "compliant": True,
            "violations": [],
            "warnings": [],
            "recommendations": [],
            "score": 0
        }
        
        # Required security settings for government compliance
        required_security_settings = {
            'encryption_enabled': 'Data encryption must be enabled for government cloud',
            'audit_logging_enabled': 'Audit logging must be enabled for compliance',
            'access_control_enabled': 'Access control must be enabled for security',
            'apigw_key': 'API Gateway key must be configured for NCP Gov'
        }
        
        passed_requirements = 0
        total_requirements = len(required_security_settings)
        
        # Check required security settings
        for setting, description in required_security_settings.items():
            if setting == 'apigw_key':
                # Check if API Gateway key is present and not empty
                if not config_data.get(setting) or config_data.get(setting) in ['', 'your-ncpgov-apigw-key']:
                    compliance_results["violations"].append(f"{setting}: {description}")
                    compliance_results["compliant"] = False
                else:
                    passed_requirements += 1
            else:
                if not config_data.get(setting, False):
                    compliance_results["violations"].append(f"{setting}: {description}")
                    compliance_results["compliant"] = False
                else:
                    passed_requirements += 1
        
        # Check for government-specific requirements
        gov_requirements = {
            'region': 'Region must be set to KR for government cloud',
            'platform': 'Platform should be VPC for enhanced security'
        }
        
        for requirement, description in gov_requirements.items():
            value = config_data.get(requirement)
            if requirement == 'region' and value != 'KR':
                compliance_results["warnings"].append(f"{requirement}: {description} (current: {value})")
            elif requirement == 'platform' and value != 'VPC':
                compliance_results["warnings"].append(f"{requirement}: {description} (current: {value})")
        
        # Additional recommendations
        recommendations = []
        if not config_data.get('multi_factor_auth', False):
            recommendations.append("Enable multi-factor authentication for enhanced security")
        
        if not config_data.get('session_timeout'):
            recommendations.append("Configure session timeout for security compliance")
        
        if not config_data.get('network_security_enabled', False):
            recommendations.append("Enable network security monitoring")
        
        compliance_results["recommendations"] = recommendations
        compliance_results["score"] = (passed_requirements / total_requirements) * 100
        
        self.scan_results['compliance_violations'] = compliance_results["violations"]
        return compliance_results
    
    def scan_sensitive_data_leaks(self, directory: str = ".") -> List[str]:
        """
        Scan for potential sensitive data leaks in logs and outputs.
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of sensitive data leak issues
        """
        console.print("[blue]🎭 Scanning for sensitive data leaks...[/blue]")
        
        leaks = []
        sensitive_patterns = [
            # IP addresses in logs
            (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'IP Address'),
            # VPC/Subnet IDs in logs
            (r'\b(vpc|subnet)-[a-zA-Z0-9]+\b', 'VPC/Subnet ID'),
            # Potential access keys in logs
            (r'\bAKIA[A-Z0-9]{16}\b', 'AWS-style Access Key'),
            # Base64-encoded data that might be sensitive
            (r'\b[A-Za-z0-9+/]{40,}={0,2}\b', 'Base64 Data'),
        ]
        
        try:
            for root, dirs, files in os.walk(directory):
                # Focus on log files and output files
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules'}]
                
                for file in files:
                    if self._is_log_or_output_file(file):
                        file_path = os.path.join(root, file)
                        file_leaks = self._scan_file_for_sensitive_data(file_path, sensitive_patterns)
                        leaks.extend(file_leaks)
        
        except Exception as e:
            console.print(f"[red]Error scanning for sensitive data leaks: {e}[/red]")
        
        self.scan_results['sensitive_data_leaks'] = leaks
        return leaks
    
    def _is_log_or_output_file(self, filename: str) -> bool:
        """Check if file is a log or output file that might contain sensitive data."""
        log_extensions = {'.log', '.out', '.txt', '.json'}
        log_patterns = ['log', 'output', 'result', 'response', 'debug']
        
        if any(filename.endswith(ext) for ext in log_extensions):
            return True
        
        filename_lower = filename.lower()
        return any(pattern in filename_lower for pattern in log_patterns)
    
    def _scan_file_for_sensitive_data(self, file_path: str, patterns: List[tuple]) -> List[str]:
        """Scan file for sensitive data patterns."""
        leaks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            for pattern, data_type in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Skip if it looks like a placeholder or example
                    matched_value = match.group(0)
                    if not self._is_placeholder_credential(matched_value):
                        line_number = self._get_line_number(content, match.start())
                        leaks.append(
                            f"Potential {data_type} leak in {file_path}:{line_number} - {matched_value[:20]}..."
                        )
        
        except Exception as e:
            console.print(f"[dim]Could not scan file {file_path}: {e}[/dim]")
        
        return leaks
    
    def validate_pypi_package_safety(self, directory: str = ".") -> List[str]:
        """
        Validate that no sensitive information will be included in PyPI package.
        
        Args:
            directory: Directory to validate
            
        Returns:
            List of PyPI safety issues
        """
        console.print("[blue]📦 Validating PyPI package safety...[/blue]")
        
        issues = []
        
        # Files that should not be in PyPI package
        sensitive_files = [
            '.env', '.env.*',
            'config.yaml', 'config.yml',
            '*.key', '*.pem', '*.p12', '*.pfx',
            'credentials.json', 'service-account*.json',
            '.aws/credentials', '.gcp/*.json', '.ncp/config', '.ncpgov/config'
        ]
        
        # Check if .gitignore exists and contains appropriate entries
        gitignore_path = Path(directory) / '.gitignore'
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r') as f:
                    gitignore_content = f.read()
                
                missing_patterns = []
                for pattern in sensitive_files:
                    if pattern not in gitignore_content:
                        missing_patterns.append(pattern)
                
                if missing_patterns:
                    issues.append(f"Missing .gitignore patterns: {', '.join(missing_patterns[:5])}")
            
            except Exception as e:
                issues.append(f"Could not read .gitignore: {e}")
        else:
            issues.append("No .gitignore file found - sensitive files may be included in package")
        
        # Check MANIFEST.in for exclusions
        manifest_path = Path(directory) / 'MANIFEST.in'
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest_content = f.read()
                
                # Check for exclude patterns
                if 'exclude' not in manifest_content.lower():
                    issues.append("MANIFEST.in should include exclude patterns for sensitive files")
            
            except Exception as e:
                issues.append(f"Could not read MANIFEST.in: {e}")
        
        # Scan for actual sensitive files that might be included
        try:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__'}]
                
                for file in files:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(directory)
                    
                    # Check if file matches sensitive patterns
                    if self._is_sensitive_file(str(relative_path)):
                        issues.append(f"Sensitive file found: {relative_path}")
        
        except Exception as e:
            console.print(f"[red]Error validating PyPI safety: {e}[/red]")
        
        self.scan_results['pypi_safety_issues'] = issues
        return issues
    
    def _is_sensitive_file(self, file_path: str) -> bool:
        """Check if file is sensitive and should not be in PyPI package."""
        sensitive_patterns = [
            r'\.env(\.|$)',
            r'config\.(yaml|yml)$',
            r'\.(key|pem|p12|pfx)$',
            r'credentials\.json$',
            r'service-account.*\.json$',
            r'\.ncp/config$',
            r'\.ncpgov/config$',
        ]
        
        return any(re.search(pattern, file_path) for pattern in sensitive_patterns)
    
    def generate_security_report(self, output_format: str = 'table') -> Dict[str, Any]:
        """
        Generate comprehensive security report.
        
        Args:
            output_format: Output format ('table', 'json')
            
        Returns:
            Security report data
        """
        report = {
            'scan_summary': {
                'hardcoded_credentials': len(self.scan_results['hardcoded_credentials']),
                'file_permissions': len(self.scan_results['file_permissions']),
                'compliance_violations': len(self.scan_results['compliance_violations']),
                'sensitive_data_leaks': len(self.scan_results['sensitive_data_leaks']),
                'pypi_safety_issues': len(self.scan_results['pypi_safety_issues'])
            },
            'details': self.scan_results,
            'overall_secure': self._is_overall_secure(),
            'recommendations': self._generate_recommendations()
        }
        
        if output_format == 'table':
            self._print_security_report_table(report)
        elif output_format == 'json':
            console.print(json.dumps(report, indent=2))
        
        return report
    
    def _is_overall_secure(self) -> bool:
        """Determine if overall security status is acceptable."""
        critical_issues = (
            len(self.scan_results['hardcoded_credentials']) +
            len(self.scan_results['compliance_violations'])
        )
        return critical_issues == 0
    
    def _generate_recommendations(self) -> List[str]:
        """Generate security recommendations based on scan results."""
        recommendations = []
        
        if self.scan_results['hardcoded_credentials']:
            recommendations.append("Remove hardcoded credentials and use environment variables or secure config files")
        
        if self.scan_results['file_permissions']:
            recommendations.append("Fix file permissions: chmod 600 for config files, chmod 700 for config directories")
        
        if self.scan_results['compliance_violations']:
            recommendations.append("Address government compliance violations for NCP Gov services")
        
        if self.scan_results['sensitive_data_leaks']:
            recommendations.append("Implement sensitive data masking in logs and outputs")
        
        if self.scan_results['pypi_safety_issues']:
            recommendations.append("Update .gitignore and MANIFEST.in to exclude sensitive files from PyPI package")
        
        return recommendations
    
    def _print_security_report_table(self, report: Dict[str, Any]):
        """Print security report in table format."""
        # Overall status
        status_color = "green" if report['overall_secure'] else "red"
        status_text = "✅ SECURE" if report['overall_secure'] else "❌ SECURITY ISSUES FOUND"
        
        summary_panel = Panel(
            f"[{status_color}]{status_text}[/{status_color}]\n\n"
            f"Hardcoded Credentials: {report['scan_summary']['hardcoded_credentials']}\n"
            f"File Permission Issues: {report['scan_summary']['file_permissions']}\n"
            f"Compliance Violations: {report['scan_summary']['compliance_violations']}\n"
            f"Sensitive Data Leaks: {report['scan_summary']['sensitive_data_leaks']}\n"
            f"PyPI Safety Issues: {report['scan_summary']['pypi_safety_issues']}",
            title="🛡️ NCP Security Scan Summary",
            border_style=status_color
        )
        console.print(summary_panel)
        
        # Detailed issues
        if report['details']['hardcoded_credentials']:
            console.print("\n[red]🚨 Hardcoded Credentials:[/red]")
            for issue in report['details']['hardcoded_credentials']:
                console.print(f"[red]  • {issue}[/red]")
        
        if report['details']['file_permissions']:
            console.print("\n[yellow]🔓 File Permission Issues:[/yellow]")
            for issue in report['details']['file_permissions']:
                console.print(f"[yellow]  • {issue}[/yellow]")
        
        if report['details']['compliance_violations']:
            console.print("\n[red]🏛️ Compliance Violations:[/red]")
            for issue in report['details']['compliance_violations']:
                console.print(f"[red]  • {issue}[/red]")
        
        if report['details']['sensitive_data_leaks']:
            console.print("\n[magenta]🎭 Sensitive Data Leaks:[/magenta]")
            for issue in report['details']['sensitive_data_leaks']:
                console.print(f"[magenta]  • {issue}[/magenta]")
        
        if report['details']['pypi_safety_issues']:
            console.print("\n[cyan]📦 PyPI Safety Issues:[/cyan]")
            for issue in report['details']['pypi_safety_issues']:
                console.print(f"[cyan]  • {issue}[/cyan]")
        
        # Recommendations
        if report['recommendations']:
            console.print("\n[blue]💡 Security Recommendations:[/blue]")
            for rec in report['recommendations']:
                console.print(f"[blue]  • {rec}[/blue]")


def main():
    """Main function for NCP security scanner."""
    parser = argparse.ArgumentParser(description="NCP Security Scanner")
    parser.add_argument('--directory', '-d', default='.', help='Directory to scan')
    parser.add_argument('--config-paths', '-c', action='append', help='Additional config paths to check')
    parser.add_argument('--format', choices=['table', 'json'], default='table', help='Output format')
    parser.add_argument('--full-scan', action='store_true', help='Perform comprehensive security scan')
    
    args = parser.parse_args()
    
    scanner = NCPSecurityScanner()
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            if args.full_scan:
                # Comprehensive scan
                task = progress.add_task("Running comprehensive security scan...", total=5)
                
                progress.update(task, advance=1, description="Scanning for hardcoded credentials...")
                scanner.scan_hardcoded_credentials(args.directory)
                
                progress.update(task, advance=1, description="Validating file permissions...")
                scanner.validate_file_permissions(args.config_paths)
                
                progress.update(task, advance=1, description="Checking government compliance...")
                scanner.validate_government_compliance()
                
                progress.update(task, advance=1, description="Scanning for sensitive data leaks...")
                scanner.scan_sensitive_data_leaks(args.directory)
                
                progress.update(task, advance=1, description="Validating PyPI package safety...")
                scanner.validate_pypi_package_safety(args.directory)
                
                progress.update(task, description="Generating security report...")
            else:
                # Quick scan - just credentials and permissions
                task = progress.add_task("Running quick security scan...", total=2)
                
                progress.update(task, advance=1, description="Scanning for hardcoded credentials...")
                scanner.scan_hardcoded_credentials(args.directory)
                
                progress.update(task, advance=1, description="Validating file permissions...")
                scanner.validate_file_permissions(args.config_paths)
        
        # Generate and display report
        console.print()
        report = scanner.generate_security_report(args.format)
        
        # Exit with error code if security issues found
        if not report['overall_secure']:
            sys.exit(1)
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Security scan interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Security scan failed: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()