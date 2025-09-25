"""
Security management module for IC.

This module provides security utilities including sensitive data detection,
masking, and Git security validation.
"""

import re
import os
import json
import subprocess
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class SecurityManager:
    """
    Manages security features including sensitive data detection and masking.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize SecurityManager with configuration.
        
        Args:
            config: Security configuration dictionary
        """
        self.config = config or {}
        self.sensitive_keys = self.config.get('sensitive_keys', [
            "password", "passwd", "pwd",
            "token", "access_token", "refresh_token", "auth_token",
            "key", "api_key", "access_key", "secret_key", "private_key",
            "secret", "client_secret", "webhook_secret",
            "webhook_url", "webhook",
            "credential", "credentials",
            "cert", "certificate",
            "session", "session_token",
        ])
        self.mask_pattern = self.config.get('mask_pattern', '***MASKED***')
        self.warn_on_sensitive = self.config.get('warn_on_sensitive_in_config', True)
    
    def mask_sensitive_data(self, data: Any) -> Any:
        """
        Recursively mask sensitive data in dictionaries, lists, and strings.
        
        Args:
            data: Data to mask (dict, list, str, or other)
            
        Returns:
            Data with sensitive information masked
        """
        if isinstance(data, dict):
            masked = {}
            for key, value in data.items():
                if self._is_sensitive_key(key):
                    masked[key] = self.mask_pattern
                else:
                    masked[key] = self.mask_sensitive_data(value)
            return masked
        elif isinstance(data, list):
            return [self.mask_sensitive_data(item) for item in data]
        elif isinstance(data, str):
            if self._looks_like_secret(data):
                return self.mask_pattern
            else:
                return data
        else:
            return data
    
    def _is_sensitive_key(self, key: str) -> bool:
        """
        Check if a key name indicates sensitive data.
        
        Args:
            key: Key name to check
            
        Returns:
            True if key appears to contain sensitive data
        """
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self.sensitive_keys)
    
    def _looks_like_secret(self, value: str) -> bool:
        """
        Heuristic to detect secret-like strings.
        
        Args:
            value: String value to check
            
        Returns:
            True if value looks like a secret
        """
        if not isinstance(value, str) or len(value) < 10:
            return False
        
        # Check for safe patterns first (these are NOT secrets)
        safe_patterns = [
            r'^[A-Za-z][A-Za-z0-9]*Role$',  # AWS role names like OrganizationAccountAccessRole
            r'^[A-Za-z][A-Za-z0-9]*Profile$',  # Profile names
            r'^[a-z0-9-]+\.[a-z]{2,}$',    # Domain names
            r'^/[a-zA-Z0-9/_-]+$',          # File paths
            r'^~[a-zA-Z0-9/_.-]*$',         # Home directory paths
            r'^[A-Za-z][A-Za-z0-9]*Service$',  # Service names
        ]
        
        # If it matches a safe pattern, it's not a secret
        if any(re.match(pattern, value) for pattern in safe_patterns):
            return False
        
        # Check for common secret patterns
        secret_patterns = [
            r'^[A-Za-z0-9+/]{40,}={0,2}$',  # Base64-like
            r'^[A-Fa-f0-9]{32,}$',          # Hex strings
            r'^[A-Za-z0-9_-]{20,}$',        # API keys
            r'^sk-[A-Za-z0-9]{32,}$',       # OpenAI-style keys
            r'^xoxb-[A-Za-z0-9-]{50,}$',    # Slack bot tokens
            r'^ghp_[A-Za-z0-9]{36}$',       # GitHub personal access tokens
            r'^gho_[A-Za-z0-9]{36}$',       # GitHub OAuth tokens
        ]
        
        return any(re.match(pattern, value) for pattern in secret_patterns)
    
    def validate_config_security(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate configuration for security issues.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            List of security warnings
        """
        warnings = []
        
        # Safe configuration keys that should not trigger warnings
        safe_keys = {
            'cross_account_role', 'role', 'role_name', 'default', 'profile',
            'key_dir', 'config_file', 'service_account_key_path', 'project_id',
            'subscription_id', 'tenant_id', 'client_id', 'compartments',
            'config_path', 'credentials_path', 'file_path', 'log_path',
            'endpoint', 'auth_method', 'session_duration', 'timeout',
            'max_workers', 'workers', 'port_timeout', 'port', 'default_user',
            'console_level', 'file_level', 'max_files', 'format',
            'mask_pattern', 'warn_on_sensitive_in_config', 'git_hooks_enabled',
            'enabled', 'prefer_mcp', 'auto_approve'
        }
        
        def check_node(data: Any, path: str = "") -> None:
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # Skip safe configuration keys
                    if key in safe_keys:
                        check_node(value, current_path)
                        continue
                    
                    if self._is_sensitive_key(key) and isinstance(value, str) and value:
                        if not self._is_placeholder_value(value):
                            warnings.append(
                                f"Sensitive data found in config at '{current_path}'. "
                                f"Consider using environment variables instead."
                            )
                    check_node(value, current_path)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    check_node(item, f"{path}[{i}]")
            elif isinstance(data, str) and self._looks_like_secret(data) and len(data) > 20:
                # Only flag strings that look like actual secrets (longer than 20 chars)
                warnings.append(
                    f"Potential secret found at '{path}'. "
                    f"Consider using environment variables instead."
                )
        
        check_node(config_data)
        return warnings
    
    def _is_placeholder_value(self, value: str) -> bool:
        """
        Check if a value is a placeholder (safe for config files).
        
        Args:
            value: Value to check
            
        Returns:
            True if value appears to be a placeholder
        """
        placeholder_patterns = [
            r'^your-.*-here$',
            r'^<.*>$',
            r'^\[.*\]$',
            r'^REPLACE_.*$',
            r'^TODO:.*$',
            r'^CHANGE_.*$',
            r'^example.*$',
            r'^placeholder.*$',
        ]
        
        value_lower = value.lower()
        return any(re.match(pattern, value_lower) for pattern in placeholder_patterns)
    
    def create_gitignore_entries(self) -> List[str]:
        """
        Generate .gitignore entries for security.
        
        Returns:
            List of .gitignore entries
        """
        return [
            "# IC Configuration - Security",
            "config.yaml",
            "config.yml", 
            ".env",
            ".env.*",
            "*.key",
            "*.pem",
            "**/credentials.json",
            "**/service-account*.json",
            "logs/",
            ".ic/",
            "",
            "# AWS credentials",
            ".aws/credentials",
            "aws-key/",
            "",
            "# GCP credentials", 
            "gcp-key/",
            "**/gcp-*.json",
            "service-account*.json",
            "*-key.json",
            "",
            "# Azure credentials",
            ".azure/",
            "*.pfx",
            "*.p12",
            "",
            "# OCI credentials",
            ".oci/config",
            ".oci/sessions/",
            "",
            "# SSH keys",
            "id_rsa*",
            "*.ppk",
            "",
            "# CloudFlare credentials",
            ".cloudflare/",
            "",
            "# Temporary files",
            "*.tmp",
            "*.temp",
            "*.bak",
            ".DS_Store",
        ]
    
    def mask_log_message(self, message: str) -> str:
        """
        Mask sensitive data in log messages.
        
        Args:
            message: Log message to mask
            
        Returns:
            Masked log message
        """
        # Mask common credential patterns in log messages
        patterns = [
            (r'(password|passwd|pwd)[\s=:]+[^\s]+', r'\1=' + self.mask_pattern),
            (r'(token|key)[\s=:]+[^\s]+', r'\1=' + self.mask_pattern),
            (r'(secret)[\s=:]+[^\s]+', r'\1=' + self.mask_pattern),
            (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', f'Bearer {self.mask_pattern}'),
            (r'Basic\s+[A-Za-z0-9+/]+=*', f'Basic {self.mask_pattern}'),
        ]
        
        masked_message = message
        for pattern, replacement in patterns:
            masked_message = re.sub(pattern, replacement, masked_message, flags=re.IGNORECASE)
        
        return masked_message
    
    def mask_sensitive_in_text(self, text: str) -> str:
        """
        Mask sensitive data in text strings (alias for mask_log_message).
        
        Args:
            text: Text to mask
            
        Returns:
            Text with sensitive information masked
        """
        return self.mask_log_message(text)


class GitSecurityChecker:
    """
    Git security validation and pre-commit hooks.
    """
    
    def __init__(self, security_manager: SecurityManager):
        """
        Initialize GitSecurityChecker.
        
        Args:
            security_manager: SecurityManager instance
        """
        self.security = security_manager
    
    def check_staged_files(self) -> List[str]:
        """
        Check staged files for sensitive data before commit.
        
        Returns:
            List of security warnings
        """
        try:
            # Get staged files
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only'], 
                capture_output=True, text=True, check=True
            )
            staged_files = [f for f in result.stdout.strip().split('\n') if f]
            
            warnings = []
            for file_path in staged_files:
                if file_path and self._should_check_file(file_path):
                    file_warnings = self._check_file_content(file_path)
                    warnings.extend(file_warnings)
            
            return warnings
        except subprocess.CalledProcessError:
            logger.debug("Could not check staged files (not in git repository)")
            return []
        except Exception as e:
            logger.warning(f"Could not check staged files: {e}")
            return []
    
    def _should_check_file(self, file_path: str) -> bool:
        """
        Determine if file should be checked for sensitive data.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file should be checked
        """
        # Skip binary files and certain extensions
        skip_extensions = {'.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe', '.jpg', '.png', '.gif', '.pdf'}
        skip_dirs = {'__pycache__', '.git', 'node_modules', '.pytest_cache', 'logs'}
        skip_files = {'requirements.txt', 'package.json', 'setup.py', 'pyproject.toml'}
        
        # Get just the filename for checking
        filename = os.path.basename(file_path)
        
        if filename in skip_files:
            return False
        if any(file_path.endswith(ext) for ext in skip_extensions):
            return False
        if any(skip_dir in file_path for skip_dir in skip_dirs):
            return False
        
        return True
    
    def _check_file_content(self, file_path: str) -> List[str]:
        """
        Check file content for sensitive data.
        
        Args:
            file_path: Path to file to check
            
        Returns:
            List of warnings for this file
        """
        warnings = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Check for common secret patterns
            if self._contains_secrets(content):
                warnings.append(f"Potential secrets found in {file_path}")
                
        except Exception as e:
            logger.debug(f"Could not check file {file_path}: {e}")
        
        return warnings
    
    def _contains_secrets(self, content: str) -> bool:
        """
        Check if content contains potential secrets.
        
        Args:
            content: File content to check
            
        Returns:
            True if content appears to contain secrets
        """
        secret_patterns = [
            r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?[^"\'\s]{8,}',
            r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[^"\'\s]{20,}',
            r'(?i)(secret|token)\s*[=:]\s*["\']?[^"\'\s]{20,}',
            r'(?i)(access[_-]?key)\s*[=:]\s*["\']?[A-Z0-9]{20}',
            r'(?i)(private[_-]?key)\s*[=:]\s*["\']?[^"\'\s]{40,}',
            r'sk-[A-Za-z0-9]{32,}',  # OpenAI keys
            r'xoxb-[A-Za-z0-9-]{50,}',  # Slack bot tokens
            r'ghp_[A-Za-z0-9]{36}',  # GitHub tokens
            r'AKIA[0-9A-Z]{16}',  # AWS access keys
        ]
        
        return any(re.search(pattern, content) for pattern in secret_patterns)
    
    def install_pre_commit_hook(self) -> bool:
        """
        Install Git pre-commit hook for security validation.
        
        Returns:
            True if hook was installed successfully
        """
        try:
            git_dir = Path('.git')
            if not git_dir.exists():
                logger.warning("Not in a git repository")
                return False
            
            hooks_dir = git_dir / 'hooks'
            hooks_dir.mkdir(exist_ok=True)
            
            pre_commit_hook = hooks_dir / 'pre-commit'
            hook_content = self._generate_pre_commit_hook()
            
            with open(pre_commit_hook, 'w') as f:
                f.write(hook_content)
            
            # Make hook executable (owner only for security)
            os.chmod(pre_commit_hook, 0o700)  # More restrictive permissions
            
            logger.info("Pre-commit security hook installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to install pre-commit hook: {e}")
            return False
    
    def _generate_pre_commit_hook(self) -> str:
        """
        Generate pre-commit hook script content.
        
        Returns:
            Pre-commit hook script content
        """
        return '''#!/bin/bash
# IC Security Pre-commit Hook
# This hook checks for sensitive data before commits

echo "Running IC security checks..."

# Check for sensitive files
if git diff --cached --name-only | grep -E "\\.(key|pem|p12|pfx)$|credentials|service-account"; then
    echo "ERROR: Attempting to commit sensitive files!"
    echo "Please remove these files from the commit:"
    git diff --cached --name-only | grep -E "\\.(key|pem|p12|pfx)$|credentials|service-account"
    exit 1
fi

# Check for common secret patterns in staged content
if git diff --cached | grep -E "(password|token|secret|key)\\s*[=:]\\s*[^\\s]{10,}"; then
    echo "WARNING: Potential secrets found in staged content!"
    echo "Please review your changes and remove any sensitive data."
    echo "Consider using environment variables or secure configuration files."
    # Uncomment the next line to block commits with potential secrets
    # exit 1
fi

echo "Security checks passed."
exit 0
'''


class NCPSecurityValidator:
    """
    NCP-specific security validation and compliance checks.
    """
    
    def __init__(self, security_manager: SecurityManager):
        """
        Initialize NCP security validator.
        
        Args:
            security_manager: SecurityManager instance
        """
        self.security = security_manager
        self.ncp_sensitive_keys = [
            "ncp_access_key", "ncp_secret_key", "access_key", "secret_key",
            "private_ip", "internal_ip", "vpc_id", "subnet_id"
        ]
    
    def scan_for_hardcoded_credentials(self, directory: str = ".") -> List[str]:
        """
        Scan for hardcoded NCP credentials in source code.
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of security violations found
        """
        violations = []
        
        try:
            for root, dirs, files in os.walk(directory):
                # Skip certain directories
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.pytest_cache'}]
                
                for file in files:
                    if self._should_scan_file(file):
                        file_path = os.path.join(root, file)
                        file_violations = self._scan_file_for_credentials(file_path)
                        violations.extend(file_violations)
        
        except Exception as e:
            logger.error(f"Error scanning for hardcoded credentials: {e}")
        
        return violations
    
    def _should_scan_file(self, filename: str) -> bool:
        """
        Determine if file should be scanned for credentials.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if file should be scanned
        """
        scan_extensions = {'.py', '.js', '.ts', '.yaml', '.yml', '.json', '.env', '.sh', '.bash'}
        skip_files = {'requirements.txt', 'package.json', 'setup.py'}
        
        if filename in skip_files:
            return False
        
        return any(filename.endswith(ext) for ext in scan_extensions)
    
    def _scan_file_for_credentials(self, file_path: str) -> List[str]:
        """
        Scan individual file for NCP credentials.
        
        Args:
            file_path: Path to file to scan
            
        Returns:
            List of violations in this file
        """
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # NCP-specific credential patterns
            ncp_patterns = [
                (r'ncp[_-]?access[_-]?key\s*[=:]\s*["\']?([A-Za-z0-9]{20,})["\']?', 'NCP Access Key'),
                (r'ncp[_-]?secret[_-]?key\s*[=:]\s*["\']?([A-Za-z0-9+/]{40,})["\']?', 'NCP Secret Key'),
                (r'access[_-]?key\s*[=:]\s*["\']?([A-Za-z0-9]{20,})["\']?', 'Access Key'),
                (r'secret[_-]?key\s*[=:]\s*["\']?([A-Za-z0-9+/]{40,})["\']?', 'Secret Key'),
            ]
            
            for pattern, credential_type in ncp_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    credential_value = match.group(1)
                    if not self._is_placeholder_credential(credential_value):
                        violations.append(
                            f"Hardcoded {credential_type} found in {file_path}:{self._get_line_number(content, match.start())}"
                        )
        
        except Exception as e:
            logger.debug(f"Could not scan file {file_path}: {e}")
        
        return violations
    
    def _is_placeholder_credential(self, value: str) -> bool:
        """
        Check if credential value is a placeholder.
        
        Args:
            value: Credential value to check
            
        Returns:
            True if value is a placeholder
        """
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
        ]
        
        value_lower = value.lower()
        return any(re.match(pattern, value_lower) for pattern in placeholder_patterns)
    
    def _get_line_number(self, content: str, position: int) -> int:
        """
        Get line number for a position in content.
        
        Args:
            content: File content
            position: Character position
            
        Returns:
            Line number
        """
        return content[:position].count('\n') + 1
    
    def validate_config_file_permissions(self, config_paths: List[str]) -> List[str]:
        """
        Validate NCP configuration file permissions.
        
        Args:
            config_paths: List of configuration file paths to check
            
        Returns:
            List of permission violations
        """
        violations = []
        
        for config_path in config_paths:
            path = Path(config_path).expanduser()
            
            if not path.exists():
                continue
            
            try:
                # Check file permissions (Unix systems only)
                if os.name != 'nt':
                    file_mode = oct(path.stat().st_mode)[-3:]
                    if file_mode != '600':
                        violations.append(
                            f"Insecure file permissions for {path}: {file_mode} (should be 600)"
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
                logger.warning(f"Could not check permissions for {path}: {e}")
        
        return violations
    
    def validate_government_compliance(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate government cloud compliance for NCP Gov.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            Compliance validation results
        """
        compliance_results = {
            "compliant": True,
            "violations": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Required security settings for government compliance
        required_security_settings = {
            'encryption_enabled': 'Data encryption must be enabled',
            'audit_logging_enabled': 'Audit logging must be enabled',
            'access_control_enabled': 'Access control must be enabled',
            'network_security_enabled': 'Network security must be enabled'
        }
        
        # Check required security settings
        for setting, description in required_security_settings.items():
            if not config_data.get(setting, False):
                compliance_results["violations"].append(f"{setting}: {description}")
                compliance_results["compliant"] = False
        
        # Check for government-specific requirements
        gov_requirements = {
            'data_residency': 'Data must remain within government boundaries',
            'security_clearance_level': 'Security clearance level must be specified',
            'compliance_framework': 'Compliance framework must be defined'
        }
        
        for requirement, description in gov_requirements.items():
            if requirement not in config_data:
                compliance_results["warnings"].append(f"{requirement}: {description}")
        
        # Additional recommendations
        if not config_data.get('multi_factor_auth', False):
            compliance_results["recommendations"].append("Enable multi-factor authentication for enhanced security")
        
        if not config_data.get('session_timeout'):
            compliance_results["recommendations"].append("Configure session timeout for security")
        
        return compliance_results
    
    def mask_sensitive_data_in_logs(self, log_message: str) -> str:
        """
        Mask NCP-specific sensitive data in log messages.
        
        Args:
            log_message: Original log message
            
        Returns:
            Log message with sensitive data masked
        """
        # NCP-specific patterns to mask
        ncp_patterns = [
            (r'(ncp[_-]?access[_-]?key[\s=:]+)[^\s]+', r'\1***MASKED***'),
            (r'(ncp[_-]?secret[_-]?key[\s=:]+)[^\s]+', r'\1***MASKED***'),
            (r'(private[_-]?ip[\s=:]+)[^\s]+', r'\1***MASKED***'),
            (r'(vpc[_-]?id[\s=:]+)[^\s]+', r'\1***MASKED***'),
            (r'(subnet[_-]?id[\s=:]+)[^\s]+', r'\1***MASKED***'),
            (r'vpc-[a-zA-Z0-9]+', r'***VPC_MASKED***'),  # VPC IDs
            (r'subnet-[a-zA-Z0-9]+', r'***SUBNET_MASKED***'),  # Subnet IDs
            (r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', r'***IP_MASKED***'),  # IP addresses
        ]
        
        masked_message = log_message
        for pattern, replacement in ncp_patterns:
            masked_message = re.sub(pattern, replacement, masked_message, flags=re.IGNORECASE)
        
        # Use base security manager for additional masking
        masked_message = self.security.mask_log_message(masked_message)
        
        return masked_message


class NCPComplianceChecker:
    """
    NCP Government Cloud compliance checker.
    """
    
    def __init__(self):
        """Initialize compliance checker."""
        self.compliance_frameworks = {
            'government': {
                'name': 'Government Cloud Compliance',
                'requirements': [
                    'data_encryption',
                    'audit_logging',
                    'access_control',
                    'network_security',
                    'data_residency',
                    'security_monitoring'
                ]
            },
            'financial': {
                'name': 'Financial Services Compliance',
                'requirements': [
                    'data_encryption',
                    'audit_logging',
                    'access_control',
                    'transaction_monitoring',
                    'fraud_detection'
                ]
            }
        }
    
    def check_compliance(self, config_data: Dict[str, Any], framework: str = 'government') -> Dict[str, Any]:
        """
        Check compliance against specified framework.
        
        Args:
            config_data: Configuration to check
            framework: Compliance framework to use
            
        Returns:
            Compliance check results
        """
        if framework not in self.compliance_frameworks:
            raise ValueError(f"Unknown compliance framework: {framework}")
        
        framework_info = self.compliance_frameworks[framework]
        results = {
            'framework': framework_info['name'],
            'compliant': True,
            'score': 0,
            'total_requirements': len(framework_info['requirements']),
            'passed_requirements': 0,
            'failed_requirements': [],
            'warnings': [],
            'recommendations': []
        }
        
        # Check each requirement
        for requirement in framework_info['requirements']:
            if self._check_requirement(requirement, config_data):
                results['passed_requirements'] += 1
            else:
                results['failed_requirements'].append(requirement)
                results['compliant'] = False
        
        # Calculate compliance score
        results['score'] = (results['passed_requirements'] / results['total_requirements']) * 100
        
        # Add recommendations based on failed requirements
        for failed_req in results['failed_requirements']:
            recommendation = self._get_requirement_recommendation(failed_req)
            if recommendation:
                results['recommendations'].append(recommendation)
        
        return results
    
    def _check_requirement(self, requirement: str, config_data: Dict[str, Any]) -> bool:
        """
        Check individual compliance requirement.
        
        Args:
            requirement: Requirement to check
            config_data: Configuration data
            
        Returns:
            True if requirement is met
        """
        requirement_checks = {
            'data_encryption': lambda c: c.get('encryption_enabled', False),
            'audit_logging': lambda c: c.get('audit_logging_enabled', False),
            'access_control': lambda c: c.get('access_control_enabled', False),
            'network_security': lambda c: c.get('network_security_enabled', False),
            'data_residency': lambda c: c.get('data_residency_compliant', False),
            'security_monitoring': lambda c: c.get('security_monitoring_enabled', False),
            'transaction_monitoring': lambda c: c.get('transaction_monitoring_enabled', False),
            'fraud_detection': lambda c: c.get('fraud_detection_enabled', False),
        }
        
        check_func = requirement_checks.get(requirement)
        if check_func:
            return check_func(config_data)
        
        return False
    
    def _get_requirement_recommendation(self, requirement: str) -> str:
        """
        Get recommendation for failed requirement.
        
        Args:
            requirement: Failed requirement
            
        Returns:
            Recommendation text
        """
        recommendations = {
            'data_encryption': 'Enable data encryption for all sensitive data at rest and in transit',
            'audit_logging': 'Enable comprehensive audit logging for all system activities',
            'access_control': 'Implement role-based access control with principle of least privilege',
            'network_security': 'Configure network security groups and firewalls properly',
            'data_residency': 'Ensure all data remains within approved geographical boundaries',
            'security_monitoring': 'Enable real-time security monitoring and alerting',
            'transaction_monitoring': 'Implement transaction monitoring for financial compliance',
            'fraud_detection': 'Enable fraud detection mechanisms for financial transactions',
        }
        
        return recommendations.get(requirement, f'Address {requirement} compliance requirement')


def create_security_config() -> Dict[str, Any]:
    """
    Create default security configuration.
    
    Returns:
        Default security configuration
    """
    return {
        "sensitive_keys": [
            "password", "passwd", "pwd",
            "token", "access_token", "refresh_token", "auth_token",
            "key", "api_key", "access_key", "secret_key", "private_key",
            "secret", "client_secret", "webhook_secret",
            "webhook_url", "webhook",
            "credential", "credentials",
            "cert", "certificate",
            "session", "session_token",
            # NCP-specific sensitive keys
            "ncp_access_key", "ncp_secret_key",
            "private_ip", "internal_ip", "vpc_id", "subnet_id"
        ],
        "mask_pattern": "***MASKED***",
        "warn_on_sensitive_in_config": True,
        "git_hooks_enabled": True,
        # NCP-specific security settings
        "ncp_security_enabled": True,
        "government_compliance_enabled": False,
        "credential_scanning_enabled": True,
        "file_permission_validation_enabled": True,
    }