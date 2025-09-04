"""
Configuration migration module for IC.

This module provides utilities for migrating from .env files to YAML configuration.
"""

import os
import re
import yaml
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging

from .security import SecurityManager

logger = logging.getLogger(__name__)


class ConfigMigration:
    """
    Handles migration from .env files to YAML configuration.
    """
    
    def __init__(self, security_manager: Optional[SecurityManager] = None):
        """
        Initialize ConfigMigration.
        
        Args:
            security_manager: SecurityManager instance for validation
        """
        self.security_manager = security_manager
        self.migration_log: List[str] = []
        self.backup_dir = Path.home() / ".ic" / "migration_backups"
        
        # Mapping from .env variables to YAML structure
        self.env_to_yaml_mapping = {
            # Logging
            'IC_LOG_LEVEL': ['logging', 'console_level'],
            'IC_LOG_FILE_LEVEL': ['logging', 'file_level'],
            'IC_LOG_FILE_PATH': ['logging', 'file_path'],
            'IC_LOG_MAX_FILES': ['logging', 'max_files'],
            'IC_LOG_FORMAT': ['logging', 'format'],
            'IC_LOG_MASK_SENSITIVE': ['logging', 'mask_sensitive'],
            
            # AWS
            'AWS_ACCOUNTS': ['aws', 'accounts'],
            'AWS_REGIONS': ['aws', 'regions'],
            'AWS_CROSS_ACCOUNT_ROLE': ['aws', 'cross_account_role'],
            'AWS_SESSION_DURATION': ['aws', 'session_duration'],
            'AWS_MAX_WORKERS': ['aws', 'max_workers'],
            'AWS_DEFAULT_PROFILE': ['aws', 'default_profile'],
            'AWS_DEFAULT_REGION': ['aws', 'default_region'],
            
            # Azure
            'AZURE_SUBSCRIPTIONS': ['azure', 'subscriptions'],
            'AZURE_LOCATIONS': ['azure', 'locations'],
            'AZURE_MAX_WORKERS': ['azure', 'max_workers'],
            'AZURE_SUBSCRIPTION_ID': ['azure', 'subscription_id'],
            
            # GCP
            'GCP_PROJECTS': ['gcp', 'projects'],
            'GCP_REGIONS': ['gcp', 'regions'],
            'GCP_ZONES': ['gcp', 'zones'],
            'GCP_MAX_WORKERS': ['gcp', 'max_workers'],
            'GCP_PROJECT_ID': ['gcp', 'project_id'],
            'GCP_MCP_ENABLED': ['gcp', 'mcp', 'enabled'],
            'GCP_MCP_ENDPOINT': ['gcp', 'mcp', 'endpoint'],
            'GCP_MCP_AUTH_METHOD': ['gcp', 'mcp', 'auth_method'],
            'GCP_MCP_PREFER_MCP': ['gcp', 'mcp', 'prefer_mcp'],
            
            # OCI
            'OCI_CONFIG_PATH': ['oci', 'config_path'],
            'OCI_MAX_WORKERS': ['oci', 'max_workers'],
            
            # CloudFlare
            'CLOUDFLARE_ACCOUNTS': ['cloudflare', 'accounts'],
            'CLOUDFLARE_ZONES': ['cloudflare', 'zones'],
            
            # SSH
            'SSH_CONFIG_FILE': ['ssh', 'config_file'],
            'SSH_KEY_DIR': ['ssh', 'key_dir'],
            'SSH_MAX_WORKERS': ['ssh', 'max_workers'],
            'SSH_PORT_SCAN_TIMEOUT': ['ssh', 'timeouts', 'port_scan'],
            'SSH_CONNECT_TIMEOUT': ['ssh', 'timeouts', 'ssh_connect'],
            
            # Slack
            'SLACK_ENABLED': ['slack', 'enabled'],
            
            # MCP
            'MCP_GITHUB_ENABLED': ['mcp', 'servers', 'github', 'enabled'],
            'MCP_TERRAFORM_ENABLED': ['mcp', 'servers', 'terraform', 'enabled'],
            'MCP_AWS_DOCS_ENABLED': ['mcp', 'servers', 'aws_docs', 'enabled'],
            'MCP_AZURE_ENABLED': ['mcp', 'servers', 'azure', 'enabled'],
        }
        
        # Sensitive variables that should remain in environment
        self.sensitive_env_vars = {
            'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
            'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET',
            'GCP_SERVICE_ACCOUNT_KEY_PATH', 'GOOGLE_APPLICATION_CREDENTIALS',
            'CLOUDFLARE_EMAIL', 'CLOUDFLARE_API_TOKEN',
            'SLACK_WEBHOOK_URL',
            'MCP_GITHUB_TOKEN',
        }
    
    def migrate_env_to_yaml(self, env_file_path: str = '.env', 
                           output_path: str = 'config.yaml',
                           backup: bool = True) -> Dict[str, Any]:
        """
        Migrate .env file to YAML configuration.
        
        Args:
            env_file_path: Path to .env file
            output_path: Path for output YAML file
            backup: Whether to create backup of existing files
            
        Returns:
            Migration result with status and details
        """
        result = {
            'success': False,
            'config_created': False,
            'backup_created': False,
            'sensitive_vars_found': [],
            'migrated_vars': [],
            'errors': [],
            'warnings': []
        }
        
        try:
            env_path = Path(env_file_path)
            output_path = Path(output_path)
            
            # Check if .env file exists
            if not env_path.exists():
                result['errors'].append(f".env file not found: {env_file_path}")
                return result
            
            # Create backup if requested
            if backup:
                backup_success = self._create_backup(env_path, output_path)
                result['backup_created'] = backup_success
                if not backup_success:
                    result['warnings'].append("Failed to create backup, continuing anyway")
            
            # Load .env file
            env_vars = self._load_env_file(env_path)
            if not env_vars:
                result['errors'].append("No variables found in .env file")
                return result
            
            # Separate sensitive and non-sensitive variables
            sensitive_vars, config_vars = self._separate_variables(env_vars)
            result['sensitive_vars_found'] = list(sensitive_vars.keys())
            
            # Convert to YAML structure
            yaml_config = self._convert_to_yaml_structure(config_vars)
            result['migrated_vars'] = list(config_vars.keys())
            
            # Add default configuration structure
            yaml_config = self._merge_with_defaults(yaml_config)
            
            # Validate security if SecurityManager is available
            if self.security_manager:
                security_warnings = self.security_manager.validate_config_security(yaml_config)
                result['warnings'].extend(security_warnings)
            
            # Save YAML configuration
            self._save_yaml_config(yaml_config, output_path)
            result['config_created'] = True
            
            # Create environment variables documentation
            self._create_env_documentation(sensitive_vars, output_path.parent)
            
            # Log migration details
            self._log_migration_results(result, env_vars, sensitive_vars, config_vars)
            
            result['success'] = True
            
        except Exception as e:
            result['errors'].append(f"Migration failed: {e}")
            logger.error(f"Migration error: {e}")
        
        return result
    
    def _load_env_file(self, env_path: Path) -> Dict[str, str]:
        """
        Load variables from .env file.
        
        Args:
            env_path: Path to .env file
            
        Returns:
            Dictionary of environment variables
        """
        env_vars = {}
        
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse variable assignment
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        env_vars[key] = value
                    else:
                        logger.warning(f"Invalid line {line_num} in {env_path}: {line}")
        
        except Exception as e:
            logger.error(f"Failed to load .env file {env_path}: {e}")
        
        return env_vars
    
    def _separate_variables(self, env_vars: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Separate sensitive and non-sensitive environment variables.
        
        Args:
            env_vars: All environment variables
            
        Returns:
            Tuple of (sensitive_vars, config_vars)
        """
        sensitive_vars = {}
        config_vars = {}
        
        for key, value in env_vars.items():
            if key in self.sensitive_env_vars:
                sensitive_vars[key] = value
            elif key in self.env_to_yaml_mapping:
                config_vars[key] = value
            else:
                # Check if it looks sensitive
                if self.security_manager and self.security_manager._is_sensitive_key(key):
                    sensitive_vars[key] = value
                else:
                    # Unknown variable, add to config with warning
                    config_vars[key] = value
                    logger.warning(f"Unknown environment variable: {key}")
        
        return sensitive_vars, config_vars
    
    def _convert_to_yaml_structure(self, config_vars: Dict[str, str]) -> Dict[str, Any]:
        """
        Convert environment variables to YAML structure.
        
        Args:
            config_vars: Configuration variables to convert
            
        Returns:
            YAML configuration structure
        """
        yaml_config = {}
        
        for env_var, value in config_vars.items():
            if env_var in self.env_to_yaml_mapping:
                yaml_path = self.env_to_yaml_mapping[env_var]
                converted_value = self._convert_value(env_var, value)
                self._set_nested_value(yaml_config, yaml_path, converted_value)
            else:
                # Handle unknown variables by putting them in a custom section
                if 'custom' not in yaml_config:
                    yaml_config['custom'] = {}
                yaml_config['custom'][env_var] = self._convert_value(env_var, value)
        
        return yaml_config
    
    def _convert_value(self, env_var: str, value: str) -> Any:
        """
        Convert string value to appropriate type.
        
        Args:
            env_var: Environment variable name
            value: String value
            
        Returns:
            Converted value
        """
        # Handle comma-separated lists
        if any(env_var.endswith(suffix) for suffix in ['_ACCOUNTS', '_REGIONS', '_ZONES', '_LOCATIONS', '_SUBSCRIPTIONS', '_PROJECTS']):
            return [item.strip() for item in value.split(',') if item.strip()]
        
        # Handle boolean values
        if any(env_var.endswith(suffix) for suffix in ['_ENABLED', '_MASK_SENSITIVE', '_PREFER_MCP']):
            return value.lower() in ('true', '1', 'yes', 'on')
        
        # Handle integer values
        if any(field in env_var for field in ['MAX_WORKERS', 'DURATION', 'MAX_FILES', 'TIMEOUT']):
            try:
                return int(value)
            except ValueError:
                logger.warning(f"Invalid integer value for {env_var}: {value}")
                return value
        
        # Handle float values
        if 'TIMEOUT' in env_var and '.' in value:
            try:
                return float(value)
            except ValueError:
                logger.warning(f"Invalid float value for {env_var}: {value}")
                return value
        
        return value
    
    def _set_nested_value(self, config: Dict[str, Any], path: List[str], value: Any) -> None:
        """
        Set a nested value in configuration dictionary.
        
        Args:
            config: Configuration dictionary
            path: List of keys representing the path
            value: Value to set
        """
        current = config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value
    
    def _merge_with_defaults(self, yaml_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge migrated config with default configuration structure.
        
        Args:
            yaml_config: Migrated configuration
            
        Returns:
            Complete configuration with defaults
        """
        # Get default configuration structure
        default_config = {
            "version": "1.0",
            "logging": {
                "console_level": "ERROR",
                "file_level": "INFO",
                "file_path": "logs/ic_{date}.log",
                "max_files": 30,
                "format": "%(asctime)s [%(levelname)s] - %(message)s",
                "mask_sensitive": True,
            },
            "aws": {
                "accounts": [],
                "regions": ["ap-northeast-2"],
                "cross_account_role": "OrganizationAccountAccessRole",
                "session_duration": 3600,
                "max_workers": 10,
                "tags": {
                    "required": ["User", "Team", "Environment"],
                    "optional": ["Service", "Application"],
                    "rules": {
                        "User": "^.+$",
                        "Team": "^\\d+$",
                        "Environment": "^(PROD|STG|DEV|TEST|QA)$",
                    },
                },
            },
            "azure": {
                "subscriptions": [],
                "locations": ["Korea Central"],
                "max_workers": 10,
            },
            "gcp": {
                "mcp": {
                    "enabled": True,
                    "endpoint": "http://localhost:8080/gcp",
                    "auth_method": "service_account",
                    "prefer_mcp": True,
                },
                "projects": [],
                "regions": ["asia-northeast3"],
                "zones": ["asia-northeast3-a"],
                "max_workers": 10,
            },
            "oci": {
                "config_path": "~/.oci/config",
                "max_workers": 10,
            },
            "cloudflare": {
                "accounts": [],
                "zones": [],
            },
            "ssh": {
                "config_file": "~/.ssh/config",
                "key_dir": "~/aws-key",
                "max_workers": 70,
                "timeouts": {
                    "port_scan": 0.5,
                    "ssh_connect": 5,
                },
            },
            "mcp": {
                "servers": {
                    "github": {
                        "enabled": True,
                        "auto_approve": [],
                    },
                    "terraform": {
                        "enabled": True,
                        "auto_approve": [],
                    },
                    "aws_docs": {
                        "enabled": True,
                        "auto_approve": ["read_documentation", "search_documentation"],
                    },
                    "azure": {
                        "enabled": True,
                        "auto_approve": ["documentation"],
                    },
                },
            },
            "slack": {
                "enabled": False,
            },
            "security": {
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
            },
        }
        
        return self._deep_merge(default_config, yaml_config)
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _save_yaml_config(self, yaml_config: Dict[str, Any], output_path: Path) -> None:
        """
        Save YAML configuration to file.
        
        Args:
            yaml_config: Configuration to save
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Add header comment
            f.write("# IC Configuration\n")
            f.write("# Generated from .env migration\n")
            f.write(f"# Migration date: {datetime.now().isoformat()}\n")
            f.write("# \n")
            f.write("# This file contains non-sensitive configuration values.\n")
            f.write("# Sensitive values should be provided via environment variables.\n")
            f.write("# See .env.example for required environment variables.\n")
            f.write("\n")
            
            yaml.dump(yaml_config, f, default_flow_style=False, indent=2, sort_keys=False)
    
    def _create_env_documentation(self, sensitive_vars: Dict[str, str], output_dir: Path) -> None:
        """
        Create documentation for required environment variables.
        
        Args:
            sensitive_vars: Sensitive variables that should remain in environment
            output_dir: Directory to create documentation
        """
        env_example_path = output_dir / ".env.example"
        
        with open(env_example_path, 'w', encoding='utf-8') as f:
            f.write("# IC Environment Variables\n")
            f.write("# These sensitive variables should be set in your environment\n")
            f.write("# DO NOT commit actual values to version control\n")
            f.write("\n")
            
            # Group variables by service
            aws_vars = [k for k in sensitive_vars.keys() if k.startswith('AWS_')]
            azure_vars = [k for k in sensitive_vars.keys() if k.startswith('AZURE_')]
            gcp_vars = [k for k in sensitive_vars.keys() if k.startswith('GCP_') or k.startswith('GOOGLE_')]
            cf_vars = [k for k in sensitive_vars.keys() if k.startswith('CLOUDFLARE_')]
            slack_vars = [k for k in sensitive_vars.keys() if k.startswith('SLACK_')]
            mcp_vars = [k for k in sensitive_vars.keys() if k.startswith('MCP_')]
            
            if aws_vars:
                f.write("# AWS Credentials\n")
                for var in aws_vars:
                    f.write(f"{var}=your-{var.lower().replace('_', '-')}-here\n")
                f.write("\n")
            
            if azure_vars:
                f.write("# Azure Credentials\n")
                for var in azure_vars:
                    f.write(f"{var}=your-{var.lower().replace('_', '-')}-here\n")
                f.write("\n")
            
            if gcp_vars:
                f.write("# GCP Credentials\n")
                for var in gcp_vars:
                    f.write(f"{var}=your-{var.lower().replace('_', '-')}-here\n")
                f.write("\n")
            
            if cf_vars:
                f.write("# CloudFlare Credentials\n")
                for var in cf_vars:
                    f.write(f"{var}=your-{var.lower().replace('_', '-')}-here\n")
                f.write("\n")
            
            if slack_vars:
                f.write("# Slack Integration\n")
                for var in slack_vars:
                    f.write(f"{var}=your-{var.lower().replace('_', '-')}-here\n")
                f.write("\n")
            
            if mcp_vars:
                f.write("# MCP Server Credentials\n")
                for var in mcp_vars:
                    f.write(f"{var}=your-{var.lower().replace('_', '-')}-here\n")
                f.write("\n")
    
    def _create_backup(self, env_path: Path, output_path: Path) -> bool:
        """
        Create backup of existing files.
        
        Args:
            env_path: Path to .env file
            output_path: Path to output YAML file
            
        Returns:
            True if backup was successful
        """
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup .env file
            if env_path.exists():
                backup_env = self.backup_dir / f"{env_path.name}_{timestamp}"
                shutil.copy2(env_path, backup_env)
                logger.info(f"Backed up {env_path} to {backup_env}")
            
            # Backup existing YAML config if it exists
            if output_path.exists():
                backup_yaml = self.backup_dir / f"{output_path.name}_{timestamp}"
                shutil.copy2(output_path, backup_yaml)
                logger.info(f"Backed up {output_path} to {backup_yaml}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False
    
    def _log_migration_results(self, result: Dict[str, Any], env_vars: Dict[str, str],
                              sensitive_vars: Dict[str, str], config_vars: Dict[str, str]) -> None:
        """
        Log migration results.
        
        Args:
            result: Migration result
            env_vars: All environment variables
            sensitive_vars: Sensitive variables
            config_vars: Configuration variables
        """
        logger.info("=== Migration Summary ===")
        logger.info(f"Total variables processed: {len(env_vars)}")
        logger.info(f"Variables migrated to config: {len(config_vars)}")
        logger.info(f"Sensitive variables kept in environment: {len(sensitive_vars)}")
        
        if result['errors']:
            logger.error("Migration errors:")
            for error in result['errors']:
                logger.error(f"  - {error}")
        
        if result['warnings']:
            logger.warning("Migration warnings:")
            for warning in result['warnings']:
                logger.warning(f"  - {warning}")
        
        if result['success']:
            logger.info("Migration completed successfully!")
        else:
            logger.error("Migration failed!")
    
    def rollback_migration(self, backup_timestamp: str) -> bool:
        """
        Rollback migration using backup files.
        
        Args:
            backup_timestamp: Timestamp of backup to restore
            
        Returns:
            True if rollback was successful
        """
        try:
            # Find backup files with the given timestamp
            backup_files = list(self.backup_dir.glob(f"*_{backup_timestamp}"))
            
            if not backup_files:
                logger.error(f"No backup files found for timestamp: {backup_timestamp}")
                return False
            
            for backup_file in backup_files:
                # Determine original file path
                original_name = backup_file.name.replace(f"_{backup_timestamp}", "")
                original_path = Path(original_name)
                
                # Restore file
                shutil.copy2(backup_file, original_path)
                logger.info(f"Restored {original_path} from {backup_file}")
            
            logger.info("Migration rollback completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List available backup files.
        
        Returns:
            List of backup information
        """
        backups = []
        
        if not self.backup_dir.exists():
            return backups
        
        backup_files = list(self.backup_dir.glob("*_*"))
        
        # Group by timestamp
        timestamp_groups = {}
        for backup_file in backup_files:
            parts = backup_file.name.split('_')
            if len(parts) >= 2:
                timestamp = '_'.join(parts[-2:])  # Get last two parts as timestamp
                if timestamp not in timestamp_groups:
                    timestamp_groups[timestamp] = []
                timestamp_groups[timestamp].append(backup_file)
        
        for timestamp, files in timestamp_groups.items():
            try:
                # Parse timestamp
                dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                backups.append({
                    'timestamp': timestamp,
                    'date': dt.isoformat(),
                    'files': [f.name for f in files],
                    'file_count': len(files)
                })
            except ValueError:
                # Skip invalid timestamps
                continue
        
        # Sort by date (newest first)
        backups.sort(key=lambda x: x['date'], reverse=True)
        
        return backups


def create_migration_status_file(migration_result: Dict[str, Any], 
                                output_dir: Path = Path('.')) -> None:
    """
    Create a migration status file with results.
    
    Args:
        migration_result: Result from migration
        output_dir: Directory to create status file
    """
    status_file = output_dir / ".ic_migration_status.yaml"
    
    status_data = {
        'migration_date': datetime.now().isoformat(),
        'success': migration_result['success'],
        'migrated_variables': migration_result.get('migrated_vars', []),
        'sensitive_variables': migration_result.get('sensitive_vars_found', []),
        'errors': migration_result.get('errors', []),
        'warnings': migration_result.get('warnings', []),
    }
    
    with open(status_file, 'w', encoding='utf-8') as f:
        yaml.dump(status_data, f, default_flow_style=False, indent=2)
    
    logger.info(f"Migration status saved to {status_file}")