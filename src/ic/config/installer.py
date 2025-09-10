"""
Configuration installer module for default configuration setup.

This module provides functionality to install default configuration files
during package installation or initialization.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class ConfigInstaller:
    """Handles default configuration file installation."""
    
    def __init__(self):
        self.default_config_dir = "~/.ic/config"
        self.config_generator = DefaultConfigGenerator()
    
    def install_default_configs(self, target_dir: Optional[str] = None) -> bool:
        """
        Install default configuration files if they don't exist.
        
        Args:
            target_dir: Target directory for configuration files (default: .ic/config)
            
        Returns:
            True if installation was successful, False otherwise
        """
        if target_dir is None:
            target_dir = self.default_config_dir
        
        target_path = Path(target_dir)
        
        try:
            # Check if configuration directory already exists
            existing_configs = self.check_existing_configs(str(target_path))
            
            # Only install if directory doesn't exist or is empty
            if target_path.exists() and any(existing_configs.values()):
                print(f"⚠️  Configuration directory {target_path} already contains files. Skipping installation.")
                return False
            
            # Create configuration directory
            self.create_config_directory(str(target_path))
            
            # Generate and save default configuration files
            self._install_default_yaml(target_path)
            self._install_secrets_example(target_path)
            
            print(f"✅ Default configuration files installed in {target_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to install default configuration: {e}")
            return False
    
    def check_existing_configs(self, target_dir: str) -> Dict[str, bool]:
        """
        Check for existing configuration files.
        
        Args:
            target_dir: Directory to check for configuration files
            
        Returns:
            Dictionary indicating which configuration files exist
        """
        target_path = Path(target_dir)
        
        return {
            'default.yaml': (target_path / 'default.yaml').exists(),
            'secrets.yaml': (target_path / 'secrets.yaml').exists(),
            'secrets.yaml.example': (target_path / 'secrets.yaml.example').exists(),
            'directory_exists': target_path.exists()
        }
    
    def create_config_directory(self, target_dir: str) -> None:
        """
        Create configuration directory with proper permissions.
        
        Args:
            target_dir: Directory path to create
        """
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Set appropriate permissions (readable/writable by owner only)
        if os.name != 'nt':  # Not Windows
            os.chmod(target_path, 0o700)
    
    def _install_default_yaml(self, target_path: Path) -> None:
        """Install default.yaml configuration file."""
        default_config = self.config_generator.generate_default_yaml()
        default_file = target_path / 'default.yaml'
        
        with open(default_file, 'w') as f:
            f.write(default_config)
        
        # Set file permissions
        if os.name != 'nt':  # Not Windows
            os.chmod(default_file, 0o600)
    
    def _install_secrets_example(self, target_path: Path) -> None:
        """Install secrets.yaml.example file."""
        secrets_example = self.config_generator.generate_secrets_example()
        secrets_file = target_path / 'secrets.yaml.example'
        
        with open(secrets_file, 'w') as f:
            f.write(secrets_example)
        
        # Set file permissions
        if os.name != 'nt':  # Not Windows
            os.chmod(secrets_file, 0o644)


class DefaultConfigGenerator:
    """Generates default configuration templates."""
    
    def generate_default_yaml(self) -> str:
        """
        Generate default YAML configuration content.
        
        Returns:
            Default configuration as YAML string
        """
        config = {
            'version': '2.0',
            'metadata': {
                'created': datetime.now().isoformat(),
                'description': 'IC (Infrastructure CLI) default configuration'
            },
            'logging': {
                'level': 'INFO',
                'file_level': 'DEBUG',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file_path': '~/.ic/logs/ic_{date}.log'
            },
            'security': {
                'mask_sensitive_data': True,
                'secure_file_permissions': True,
                'validate_ssl_certificates': True
            },
            'aws': {
                'regions': ['ap-northeast-2'],
                'accounts': [],
                'cross_account_role': 'OrganizationAccountAccessRole',
                'session_duration': 3600,
                'retry_config': {
                    'max_attempts': 3,
                    'mode': 'adaptive'
                }
            },
            'azure': {
                'subscription_id': '',
                'tenant_id': '',
                'resource_groups': [],
                'locations': ['koreacentral', 'koreasouth']
            },
            'gcp': {
                'project_id': '',
                'regions': ['asia-northeast3'],
                'zones': ['asia-northeast3-a', 'asia-northeast3-b']
            },
            'oci': {
                'tenancy_ocid': '',
                'user_ocid': '',
                'region': 'ap-seoul-1',
                'compartment_ocid': ''
            },
            'cloudflare': {
                'zone_id': '',
                'api_base_url': 'https://api.cloudflare.com/client/v4'
            }
        }
        
        # Add comprehensive comments
        yaml_content = self._add_yaml_comments()
        
        return yaml_content
    
    def generate_secrets_example(self) -> str:
        """
        Generate secrets.yaml.example content.
        
        Returns:
            Example secrets configuration as YAML string
        """
        secrets_example = {
            'aws': {
                'profile': 'your-aws-profile-name',
                'access_key_id': 'AKIA...',
                'secret_access_key': 'your-secret-access-key',
                'session_token': 'optional-session-token'
            },
            'azure': {
                'client_id': 'your-azure-client-id',
                'client_secret': 'your-azure-client-secret',
                'tenant_id': 'your-azure-tenant-id'
            },
            'gcp': {
                'service_account_key_path': '/path/to/service-account.json',
                'application_credentials': '/path/to/credentials.json'
            },
            'oci': {
                'key_file': '/path/to/oci-private-key.pem',
                'fingerprint': 'your-key-fingerprint'
            },
            'cloudflare': {
                'api_token': 'your-cloudflare-api-token',
                'email': 'your-cloudflare-email'
            },
            'slack': {
                'webhook_url': 'https://hooks.slack.com/services/...'
            },
            'github': {
                'token': 'your-github-token'
            }
        }
        
        # Add comprehensive comments for secrets
        yaml_content = self._add_secrets_comments()
        
        return yaml_content
    
    def _add_yaml_comments(self) -> str:
        """Add comprehensive comments to default YAML configuration."""
        return """# IC (Infrastructure CLI) Configuration File
# This file contains the main configuration settings for IC
# 
# IMPORTANT: Do not store sensitive information like passwords, API keys, 
# or tokens in this file. Use secrets.yaml for sensitive data.

version: '2.0'

metadata:
  created: '{created}'
  description: 'IC (Infrastructure CLI) default configuration'

# Logging configuration
logging:
  level: INFO              # Console log level: DEBUG, INFO, WARNING, ERROR
  file_level: DEBUG        # File log level (more detailed than console)
  format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  file_path: '~/.ic/logs/ic_{date}.log' # Log file location

# Security settings
security:
  mask_sensitive_data: true        # Mask sensitive data in output
  secure_file_permissions: true    # Set secure file permissions
  validate_ssl_certificates: true  # Validate SSL certificates

# AWS Configuration
aws:
  regions:
    - ap-northeast-2              # Primary AWS region (Seoul)
  accounts: []                    # List of AWS account IDs to manage
  cross_account_role: 'OrganizationAccountAccessRole'  # Role for cross-account access
  session_duration: 3600          # Session duration in seconds
  retry_config:
    max_attempts: 3               # Maximum retry attempts for API calls
    mode: 'adaptive'              # Retry mode: standard, adaptive

# Azure Configuration
azure:
  subscription_id: ''             # Azure subscription ID
  tenant_id: ''                   # Azure tenant ID
  resource_groups: []             # List of resource groups to manage
  locations:
    - koreacentral                # Primary Azure region
    - koreasouth                  # Secondary Azure region

# Google Cloud Platform Configuration
gcp:
  project_id: ''                  # GCP project ID
  regions:
    - asia-northeast3             # Primary GCP region (Seoul)
  zones:
    - asia-northeast3-a           # Primary zone
    - asia-northeast3-b           # Secondary zone

# Oracle Cloud Infrastructure Configuration
oci:
  tenancy_ocid: ''                # OCI tenancy OCID
  user_ocid: ''                   # OCI user OCID
  region: 'ap-seoul-1'            # OCI region
  compartment_ocid: ''            # Default compartment OCID

# CloudFlare Configuration
cloudflare:
  zone_id: ''                     # CloudFlare zone ID
  api_base_url: 'https://api.cloudflare.com/client/v4'
""".format(created=datetime.now().isoformat())
    
    def _add_secrets_comments(self) -> str:
        """Add comprehensive comments to secrets example."""
        return """# IC (Infrastructure CLI) Secrets Configuration Example
# 
# IMPORTANT SECURITY NOTES:
# 1. Copy this file to 'secrets.yaml' and fill in your actual values
# 2. NEVER commit secrets.yaml to version control
# 3. Ensure secrets.yaml has restrictive permissions (600)
# 4. Use environment variables or credential files when possible
#
# This file should contain sensitive information like API keys, tokens,
# and passwords that should not be stored in the main configuration file.

# AWS Credentials
# Option 1: Use AWS profile (recommended)
aws:
  profile: 'your-aws-profile-name'

# Option 2: Use direct credentials (not recommended for production)
# aws:
#   access_key_id: 'AKIA...'
#   secret_access_key: 'your-secret-access-key'
#   session_token: 'optional-session-token'  # For temporary credentials

# Azure Credentials
azure:
  client_id: 'your-azure-client-id'
  client_secret: 'your-azure-client-secret'
  tenant_id: 'your-azure-tenant-id'

# Google Cloud Platform Credentials
gcp:
  service_account_key_path: '/path/to/service-account.json'
  # Alternative: Set GOOGLE_APPLICATION_CREDENTIALS environment variable
  application_credentials: '/path/to/credentials.json'

# Oracle Cloud Infrastructure Credentials
oci:
  key_file: '/path/to/oci-private-key.pem'
  fingerprint: 'your-key-fingerprint'

# CloudFlare API Credentials
cloudflare:
  api_token: 'your-cloudflare-api-token'  # Preferred method
  # Alternative: Use email + global API key
  # email: 'your-cloudflare-email'
  # api_key: 'your-global-api-key'

# Optional: Slack Integration
slack:
  webhook_url: 'https://hooks.slack.com/services/...'

# Optional: GitHub Integration
github:
  token: 'your-github-token'

# Environment Variables Reference:
# You can also use environment variables instead of this file:
# 
# AWS: AWS_PROFILE, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# Azure: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
# GCP: GOOGLE_APPLICATION_CREDENTIALS
# OCI: OCI_CONFIG_FILE, OCI_CONFIG_PROFILE
# CloudFlare: CLOUDFLARE_API_TOKEN, CLOUDFLARE_EMAIL
"""