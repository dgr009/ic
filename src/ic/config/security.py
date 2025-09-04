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
        
        def check_node(data: Any, path: str = "") -> None:
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
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
            elif isinstance(data, str) and self._looks_like_secret(data):
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
            
            # Make hook executable
            os.chmod(pre_commit_hook, 0o755)
            
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
        ],
        "mask_pattern": "***MASKED***",
        "warn_on_sensitive_in_config": True,
        "git_hooks_enabled": True,
    }