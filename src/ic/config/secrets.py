"""
Secrets management module for IC.

This module provides secure handling of sensitive configuration data.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Manages sensitive configuration data with security validation.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize SecretsManager.
        
        Args:
            config_manager: Reference to ConfigManager instance
        """
        self.config_manager = config_manager
        self.secrets_data: Dict[str, Any] = {}
        
        # Define sensitive key patterns
        self.sensitive_patterns = [
            r'.*password.*',
            r'.*passwd.*',
            r'.*pwd.*',
            r'.*token.*',
            r'.*key.*',
            r'.*secret.*',
            r'.*credential.*',
            r'.*webhook.*',
            r'.*api_key.*',
            r'.*access_key.*',
            r'.*private_key.*',
            r'.*client_secret.*',
            r'.*tenant_id.*',
            r'.*client_id.*',
        ]
        
        # Compile patterns for performance
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.sensitive_patterns]
    
    def load_secrets(self) -> Dict[str, Any]:
        """
        Load secrets from config/secrets.yaml with environment variable fallback.
        
        Returns:
            Dictionary containing sensitive configuration data
        """
        secrets = {}
        
        # Try to load from secrets.yaml file with new path structure
        secrets_paths = [
            Path.home() / ".ic" / "config" / "secrets.yaml",  # New preferred location
            Path("config/secrets.yaml")  # Legacy location for backward compatibility
        ]
        
        secrets = {}
        for secrets_path in secrets_paths:
            if secrets_path.exists():
                try:
                    secrets = self._load_secrets_file(secrets_path)
                    logger.debug(f"Loaded secrets from {secrets_path}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load secrets from {secrets_path}: {e}")
        
        # Fallback to environment variables
        env_secrets = self._load_secrets_from_env()
        if env_secrets:
            secrets = self._merge_secrets(secrets, env_secrets)
            logger.debug("Merged secrets from environment variables")
        
        # Validate that secrets are properly separated (log to file only)
        validation_warnings = self.validate_secrets_separation(secrets)
        if validation_warnings:
            for warning in validation_warnings:
                logger.debug(f"Secrets validation: {warning}")  # Changed to debug level
        
        self.secrets_data = secrets
        return secrets
    
    def _load_secrets_file(self, secrets_path: Path) -> Dict[str, Any]:
        """
        Load secrets from YAML file.
        
        Args:
            secrets_path: Path to secrets.yaml file
            
        Returns:
            Dictionary containing secrets
        """
        import yaml
        
        with open(secrets_path, 'r', encoding='utf-8') as f:
            secrets = yaml.safe_load(f) or {}
        
        # Validate file permissions
        try:
            file_mode = secrets_path.stat().st_mode & 0o777
            if file_mode != 0o600:
                logger.warning(f"Secrets file {secrets_path} has insecure permissions {oct(file_mode)}. "
                             f"Consider setting permissions to 600 (owner read/write only)")
        except Exception as e:
            logger.debug(f"Could not check file permissions: {e}")
        
        return secrets
    
    def _load_secrets_from_env(self) -> Dict[str, Any]:
        """
        Load sensitive configuration from environment variables.
        
        Returns:
            Dictionary containing environment-based secrets
        """
        env_secrets = {}
        
        # AWS secrets
        aws_accounts = os.getenv('AWS_ACCOUNTS')
        if aws_accounts:
            env_secrets.setdefault('aws', {})['accounts'] = [
                acc.strip() for acc in aws_accounts.split(',') if acc.strip()
            ]
        
        # CloudFlare secrets
        cf_secrets = {}
        cf_email = os.getenv('CLOUDFLARE_EMAIL')
        cf_token = os.getenv('CLOUDFLARE_API_TOKEN')
        cf_accounts = os.getenv('CLOUDFLARE_ACCOUNTS')
        cf_zones = os.getenv('CLOUDFLARE_ZONES')
        
        if cf_email:
            cf_secrets['email'] = cf_email
        if cf_token:
            cf_secrets['api_token'] = cf_token
        if cf_accounts:
            cf_secrets['accounts'] = [acc.strip() for acc in cf_accounts.split(',') if acc.strip()]
        if cf_zones:
            cf_secrets['zones'] = [zone.strip() for zone in cf_zones.split(',') if zone.strip()]
        
        if cf_secrets:
            env_secrets['cloudflare'] = cf_secrets
        
        # GCP secrets
        gcp_secrets = {}
        gcp_key_path = os.getenv('GCP_SERVICE_ACCOUNT_KEY_PATH') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        gcp_projects = os.getenv('GCP_PROJECTS')
        
        if gcp_key_path:
            gcp_secrets['service_account_key_path'] = gcp_key_path
        if gcp_projects:
            gcp_secrets['projects'] = [proj.strip() for proj in gcp_projects.split(',') if proj.strip()]
        
        if gcp_secrets:
            env_secrets['gcp'] = gcp_secrets
        
        # Azure secrets
        azure_secrets = {}
        azure_tenant = os.getenv('AZURE_TENANT_ID')
        azure_client_id = os.getenv('AZURE_CLIENT_ID')
        azure_client_secret = os.getenv('AZURE_CLIENT_SECRET')
        azure_subscriptions = os.getenv('AZURE_SUBSCRIPTIONS')
        
        if azure_tenant:
            azure_secrets['tenant_id'] = azure_tenant
        if azure_client_id:
            azure_secrets['client_id'] = azure_client_id
        if azure_client_secret:
            azure_secrets['client_secret'] = azure_client_secret
        if azure_subscriptions:
            azure_secrets['subscriptions'] = [sub.strip() for sub in azure_subscriptions.split(',') if sub.strip()]
        
        if azure_secrets:
            env_secrets['azure'] = azure_secrets
        
        # Slack secrets
        slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        if slack_webhook:
            env_secrets['slack'] = {'webhook_url': slack_webhook}
        
        return env_secrets
    
    def _merge_secrets(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two secrets dictionaries.
        
        Args:
            base: Base secrets dictionary
            override: Override secrets dictionary
            
        Returns:
            Merged secrets dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_secrets(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def validate_secrets_separation(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate that sensitive information is properly separated from general config.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation warnings
        """
        warnings = []
        
        # Check if any sensitive data appears in the general config
        sensitive_keys_found = self._find_sensitive_keys(config)
        
        for key_path in sensitive_keys_found:
            warnings.append(f"Potentially sensitive key '{key_path}' found in general configuration. "
                          f"Consider moving to secrets.yaml")
        
        return warnings
    
    def _find_sensitive_keys(self, data: Any, path: str = "") -> List[str]:
        """
        Recursively find keys that match sensitive patterns.
        
        Args:
            data: Data to search
            path: Current path in the data structure
            
        Returns:
            List of paths to sensitive keys
        """
        sensitive_keys = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                
                # Check if key matches sensitive patterns
                if self._is_sensitive_key(key):
                    sensitive_keys.append(current_path)
                
                # Recursively check nested structures
                sensitive_keys.extend(self._find_sensitive_keys(value, current_path))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]" if path else f"[{i}]"
                sensitive_keys.extend(self._find_sensitive_keys(item, current_path))
        
        return sensitive_keys
    
    def _is_sensitive_key(self, key: str) -> bool:
        """
        Check if a key matches sensitive patterns.
        
        Args:
            key: Key to check
            
        Returns:
            True if key is potentially sensitive
        """
        return any(pattern.match(key) for pattern in self.compiled_patterns)
    
    def mask_sensitive_values(self, data: Any) -> Any:
        """
        Recursively mask sensitive values in data structure.
        
        Args:
            data: Data structure to mask
            
        Returns:
            Data structure with sensitive values masked
        """
        if isinstance(data, dict):
            masked_data = {}
            for key, value in data.items():
                if self._is_sensitive_key(key) and isinstance(value, str) and value:
                    # Mask the value but show first and last few characters for identification
                    if len(value) > 8:
                        masked_data[key] = f"{value[:3]}***{value[-3:]}"
                    else:
                        masked_data[key] = "***MASKED***"
                else:
                    masked_data[key] = self.mask_sensitive_values(value)
            return masked_data
        
        elif isinstance(data, list):
            return [self.mask_sensitive_values(item) for item in data]
        
        else:
            return data
    
    def get_secret_value(self, key_path: str, default: Any = None) -> Any:
        """
        Get a secret value using dot notation.
        
        Args:
            key_path: Dot-separated path to secret value (e.g., 'aws.accounts')
            default: Default value if key is not found
            
        Returns:
            Secret value or default
        """
        keys = key_path.split('.')
        current = self.secrets_data
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def has_secret(self, key_path: str) -> bool:
        """
        Check if a secret exists and has a non-empty value.
        
        Args:
            key_path: Dot-separated path to secret value
            
        Returns:
            True if secret exists and is not empty
        """
        value = self.get_secret_value(key_path)
        return value is not None and value != "" and value != []
    
    def create_secrets_template(self, output_path: Union[str, Path] = ".ic/config/secrets.yaml.template") -> bool:
        """
        Create a template secrets file with empty values.
        
        Args:
            output_path: Path where to create the template
            
        Returns:
            True if template was created successfully
        """
        template_content = '''# IC Secrets Configuration Template
# Copy this file to secrets.yaml and fill in your sensitive values
# File permissions should be set to 600 (readable only by owner)

version: "2.0"

# AWS sensitive configuration
aws:
  accounts: []  # Add your AWS account IDs here, e.g., ["123456789012", "987654321098"]

# CloudFlare sensitive configuration
cloudflare:
  email: ""  # Your CloudFlare email
  api_token: ""  # Your CloudFlare API token
  accounts: []  # Your CloudFlare account names
  zones: []  # Your CloudFlare zone names

# GCP sensitive configuration
gcp:
  service_account_key_path: ""  # Path to your GCP service account key
  projects: []  # Your GCP project IDs

# Azure sensitive configuration
azure:
  tenant_id: ""  # Your Azure tenant ID
  client_id: ""  # Your Azure client ID
  client_secret: ""  # Your Azure client secret
  subscriptions: []  # Your Azure subscription IDs

# Slack integration
slack:
  webhook_url: ""  # Your Slack webhook URL

# Note: If this file doesn't exist or values are empty,
# the system will fall back to environment variables
'''
        
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            logger.info(f"Created secrets template at {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create secrets template: {e}")
            return False
    
    def validate_secrets_file_security(self, secrets_path: Union[str, Path]) -> List[str]:
        """
        Validate security aspects of secrets file.
        
        Args:
            secrets_path: Path to secrets file
            
        Returns:
            List of security warnings
        """
        warnings = []
        secrets_path = Path(secrets_path)
        
        if not secrets_path.exists():
            return warnings
        
        try:
            # Check file permissions
            file_mode = secrets_path.stat().st_mode & 0o777
            if file_mode & 0o077:  # Check if group or others have any permissions
                warnings.append(f"Secrets file {secrets_path} is readable by group/others. "
                              f"Current permissions: {oct(file_mode)}. "
                              f"Recommended: 600 (owner read/write only)")
            
            # Check if file is in version control (basic check for .git directory)
            git_dir = secrets_path.parent
            while git_dir != git_dir.parent:
                if (git_dir / ".git").exists():
                    gitignore_path = git_dir / ".gitignore"
                    if gitignore_path.exists():
                        with open(gitignore_path, 'r') as f:
                            gitignore_content = f.read()
                        if "secrets.yaml" not in gitignore_content:
                            warnings.append("secrets.yaml should be added to .gitignore to prevent "
                                          "accidental commit of sensitive data")
                    else:
                        warnings.append("Consider creating .gitignore and adding secrets.yaml to it")
                    break
                git_dir = git_dir.parent
            
        except Exception as e:
            logger.debug(f"Could not validate secrets file security: {e}")
        
        return warnings