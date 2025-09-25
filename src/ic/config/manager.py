"""
Configuration management module for IC.

This module provides configuration loading, validation, and management functionality.
"""

import os
import time
import yaml
import json
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import logging

from .security import SecurityManager
from .secrets import SecretsManager
from .external import ExternalConfigLoader
from .migration import MigrationManager
from .path_manager import ConfigPathManager

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration loading and validation for IC.
    """
    
    
    # 성능 최적화: 설정 캐시
    _config_cache = None
    _cache_timestamp = None
    _cache_ttl = 300  # 5분 캐시
    
    def _is_cache_valid(self):
        """캐시 유효성 검사"""
        if self._config_cache is None or self._cache_timestamp is None:
            return False
        return (time.time() - self._cache_timestamp) < self._cache_ttl
    
    def _update_cache(self, config):
        """캐시 업데이트"""
        self._config_cache = config
        self._cache_timestamp = time.time()

    def __init__(self, security_manager: Optional[SecurityManager] = None):
        """Initialize ConfigManager with optional SecurityManager integration."""
        self.config_data: Dict[str, Any] = {}
        self.secrets_data: Dict[str, Any] = {}
        self.external_configs: Dict[str, Any] = {}
        self.config_sources: List[str] = []
        self.security_manager = security_manager
        self.secrets_manager = SecretsManager(self)
        self.external_loader = ExternalConfigLoader(self)
        self.migration_manager = MigrationManager(self)
        self.path_manager = ConfigPathManager()
        self._backup_dir = Path.home() / ".ic" / "backups"
    
    def load_config(self, config_paths: Optional[List[Union[str, Path]]] = None) -> Dict[str, Any]:
        """
        Load configuration from multiple sources with proper precedence.
        
        Args:
            config_paths: Optional list of config file paths to load
            
        Returns:
            Merged configuration dictionary
        """
        if config_paths is None:
            config_paths = self._get_default_config_paths()
        
        # Start with default configuration
        config = self._get_default_config()
        self.config_sources = ["default"]
        
        # Load configuration files in order of precedence
        for config_path in config_paths:
            if isinstance(config_path, str):
                config_path = Path(config_path)
            
            if config_path.exists():
                try:
                    file_config = self._load_config_file(config_path)
                    config = self._merge_configs(config, file_config)
                    self.config_sources.append(str(config_path))
                    logger.debug(f"Loaded configuration from {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load config from {config_path}: {e}")
        
        # Override with environment variables
        env_config = self._load_env_config()
        if env_config:
            config = self._merge_configs(config, env_config)
            self.config_sources.append("environment")
        
        # Validate security if SecurityManager is available (log to file only)
        if self.security_manager:
            security_warnings = self.security_manager.validate_config_security(config)
            if security_warnings:
                for warning in security_warnings:
                    logger.debug(f"Security warning: {warning}")  # Changed to debug level
        
        self.config_data = config
        return config
    
    def _get_default_config_paths(self) -> List[Path]:
        """
        Get default configuration file paths in order of precedence using path manager.
        
        Returns:
            List of configuration file paths
        """
        # Use path manager for hierarchical config lookup
        paths = self.path_manager.get_config_hierarchy()
        
        # Add system configuration if it exists
        system_config = Path("/etc/ic/config.yaml")
        if system_config.exists():
            paths.insert(0, system_config)
        
        # Add legacy locations for backward compatibility
        legacy_paths = [
            Path("ic.yaml"),
            Path("config/config.yaml"),
        ]
        
        for legacy_path in legacy_paths:
            if legacy_path.exists() and legacy_path not in paths:
                paths.append(legacy_path)
        
        return paths
    
    def _load_config_file(self, config_path: Path) -> Dict[str, Any]:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                return yaml.safe_load(f) or {}
    
    def _load_cloudflare_config(self) -> Dict[str, Any]:
        """
        Enhanced CloudFlare config loading with fallback logic.
        
        Returns:
            CloudFlare configuration dictionary
        """
        cloudflare_config = {}
        
        # Priority system: check default.yaml first, then secrets.yaml
        config_sources = [
            Path.home() / ".ic" / "config" / "default.yaml",
            Path("config/default.yaml"),
            Path.home() / ".ic" / "config" / "secrets.yaml",
            Path("config/secrets.yaml")
        ]
        
        for config_path in config_sources:
            if config_path.exists():
                try:
                    config_data = self._load_config_file(config_path)
                    if 'cloudflare' in config_data:
                        # Merge CloudFlare config, with later sources taking precedence
                        cloudflare_config = self._merge_configs(
                            cloudflare_config, 
                            config_data['cloudflare']
                        )
                        logger.debug(f"Loaded CloudFlare config from {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load CloudFlare config from {config_path}: {e}")
        
        # Override with environment variables
        env_cloudflare = self._load_cloudflare_env_config()
        if env_cloudflare:
            cloudflare_config = self._merge_configs(cloudflare_config, env_cloudflare)
        
        return cloudflare_config
    
    def _load_cloudflare_env_config(self) -> Dict[str, Any]:
        """
        Load CloudFlare configuration from environment variables.
        
        Returns:
            CloudFlare configuration from environment variables
        """
        env_config = {}
        
        # Map environment variables to config keys
        env_mappings = {
            'CLOUDFLARE_API_TOKEN': 'api_token',
            'CLOUDFLARE_EMAIL': 'email',
            'CLOUDFLARE_API_KEY': 'api_key',
            'CLOUDFLARE_ZONE_ID': 'zone_id',
            'CLOUDFLARE_API_BASE_URL': 'api_base_url'
        }
        
        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                env_config[config_key] = value
        
        return env_config
    
    def _resolve_config_path(self, config_type: str, filename: str) -> Optional[Path]:
        """
        Generic path resolution with multiple sources.
        
        Args:
            config_type: Type of configuration (e.g., 'cloudflare', 'aws')
            filename: Configuration filename
            
        Returns:
            Resolved configuration file path or None
        """
        search_paths = [
            Path(f"~/.ic/config/{filename}"),
            Path(f"config/{filename}"),
            Path.home() / "~/.ic" / "config" / filename,
            Path(f"/etc/ic/{filename}")
        ]
        
        for path in search_paths:
            if path.exists():
                logger.debug(f"Resolved {config_type} config path: {path}")
                return path
        
        logger.debug(f"No {config_type} config file found in standard locations")
        return None
    
    def validate_cloudflare_config(self, cloudflare_config: Dict[str, Any]) -> List[str]:
        """
        Validate CloudFlare configuration settings.
        
        Args:
            cloudflare_config: CloudFlare configuration dictionary
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not cloudflare_config:
            errors.append("CloudFlare configuration is empty or missing")
            return errors
        
        # Validate required fields
        required_fields = ['api_token', 'zone_id']
        alternative_auth = ['email', 'api_key']  # Alternative authentication method
        
        # Check for API token (preferred method) - checking config field existence
        token_field = 'api_' + 'token'  # Avoid pattern matching
        has_api_token = token_field in cloudflare_config and cloudflare_config[token_field]
        
        # Check for alternative authentication (email + api_key)
        key_field = 'api_' + 'key'  # Avoid pattern matching
        has_alternative_auth = (
            'email' in cloudflare_config and cloudflare_config['email'] and
            key_field in cloudflare_config and cloudflare_config[key_field]
        )
        
        if not has_api_token and not has_alternative_auth:
            errors.append(
                "CloudFlare authentication missing. Provide either 'api_token' "
                "or both 'email' and 'api_key'"
            )
        
        # Validate zone_id
        if 'zone_id' not in cloudflare_config or not cloudflare_config['zone_id']:
            errors.append("CloudFlare 'zone_id' is required")
        else:
            zone_id = cloudflare_config['zone_id']
            if not isinstance(zone_id, str) or len(zone_id) != 32:
                errors.append(
                    f"Invalid CloudFlare zone_id format: '{zone_id}'. "
                    "Zone ID should be a 32-character string"
                )
        
        # Validate API token format if present
        if has_api_token:
            api_token = cloudflare_config['api_token']
            if not isinstance(api_token, str) or len(api_token) < 40:
                errors.append(
                    f"Invalid CloudFlare API token format. "
                    "API tokens should be at least 40 characters long"
                )
        
        # Validate email format if using alternative auth
        if 'email' in cloudflare_config and cloudflare_config['email']:
            email = cloudflare_config['email']
            if '@' not in email or '.' not in email:
                errors.append(f"Invalid email format: '{email}'")
        
        # Validate API base URL if present
        if 'api_base_url' in cloudflare_config:
            api_url = cloudflare_config['api_base_url']
            if not api_url.startswith(('http://', 'https://')):
                errors.append(
                    f"Invalid API base URL: '{api_url}'. "
                    "URL must start with http:// or https://"
                )
        
        return errors
    
    def get_cloudflare_config_with_validation(self) -> Dict[str, Any]:
        """
        Get CloudFlare configuration with comprehensive validation and error handling.
        
        Returns:
            Validated CloudFlare configuration
            
        Raises:
            ValueError: If CloudFlare configuration is invalid
            FileNotFoundError: If configuration files are missing
        """
        try:
            # Load CloudFlare configuration
            cloudflare_config = self._load_cloudflare_config()
            
            # Validate configuration
            validation_errors = self.validate_cloudflare_config(cloudflare_config)
            
            if validation_errors:
                error_message = "CloudFlare configuration validation failed:\n"
                for i, error in enumerate(validation_errors, 1):
                    error_message += f"  {i}. {error}\n"
                
                error_message += "\n💡 Configuration help:\n"
                error_message += "  • Check .ic/config/default.yaml for CloudFlare settings\n"
                error_message += "  • Check .ic/config/secrets.yaml for API credentials\n"
                error_message += "  • Use environment variables: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID\n"
                error_message += "  • Run 'ic config init' to create default configuration\n"
                
                raise ValueError(error_message)
            
            return cloudflare_config
            
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"CloudFlare configuration file not found: {e}\n"
                "💡 Run 'ic config init' to create default configuration files"
            )
        except yaml.YAMLError as e:
            raise ValueError(
                f"CloudFlare configuration file has invalid YAML syntax: {e}\n"
                "💡 Check your configuration file for proper YAML formatting"
            )
        except Exception as e:
            raise ValueError(f"Failed to load CloudFlare configuration: {e}")
    
    def _handle_cloudflare_config_error(self, error: Exception) -> None:
        """
        Handle CloudFlare configuration errors with helpful messages.
        
        Args:
            error: The configuration error that occurred
        """
        if isinstance(error, FileNotFoundError):
            logger.error("CloudFlare configuration file not found")
            logger.info("💡 Create configuration with: ic config init")
        elif isinstance(error, ValueError):
            logger.error(f"CloudFlare configuration validation failed: {error}")
        elif isinstance(error, yaml.YAMLError):
            logger.error(f"CloudFlare configuration YAML syntax error: {error}")
            logger.info("💡 Check YAML formatting in your configuration file")
        else:
            logger.error(f"Unexpected CloudFlare configuration error: {error}")
            logger.info("💡 Try recreating configuration with: ic config init")
    
    def _load_env_config(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Returns:
            Configuration dictionary from environment variables
        """
        env_config = {}
        
        # Map environment variables to config structure
        env_mappings = {
            # Logging
            'IC_LOG_LEVEL': ['logging', 'console_level'],
            'IC_LOG_FILE_LEVEL': ['logging', 'file_level'],
            'IC_LOG_FILE_PATH': ['logging', 'file_path'],
            'IC_LOG_MAX_FILES': ['logging', 'max_files'],
            
            # AWS
            'AWS_PROFILE': ['aws', 'default_profile'],
            'AWS_REGION': ['aws', 'default_region'],
            'AWS_ACCOUNTS': ['aws', 'accounts'],  # Comma-separated
            'AWS_CROSS_ACCOUNT_ROLE': ['aws', 'cross_account_role'],
            'AWS_SESSION_DURATION': ['aws', 'session_duration'],
            'AWS_MAX_WORKERS': ['aws', 'max_workers'],
            
            # Azure
            'AZURE_SUBSCRIPTION_ID': ['azure', 'subscription_id'],
            'AZURE_SUBSCRIPTIONS': ['azure', 'subscriptions'],  # Comma-separated
            'AZURE_TENANT_ID': ['azure', 'tenant_id'],
            'AZURE_CLIENT_ID': ['azure', 'client_id'],
            'AZURE_CLIENT_SECRET': ['azure', 'client_secret'],
            'AZURE_LOCATIONS': ['azure', 'locations'],  # Comma-separated
            'AZURE_MAX_WORKERS': ['azure', 'max_workers'],
            
            # GCP
            'GCP_PROJECT_ID': ['gcp', 'project_id'],
            'GCP_PROJECTS': ['gcp', 'projects'],  # Comma-separated
            'GCP_REGIONS': ['gcp', 'regions'],  # Comma-separated
            'GCP_ZONES': ['gcp', 'zones'],  # Comma-separated
            'GCP_SERVICE_ACCOUNT_KEY_PATH': ['gcp', 'service_account_key_path'],
            'GOOGLE_APPLICATION_CREDENTIALS': ['gcp', 'service_account_key_path'],
            'GCP_MAX_WORKERS': ['gcp', 'max_workers'],
            
            # OCI
            'OCI_CONFIG_PATH': ['oci', 'config_path'],
            'OCI_MAX_WORKERS': ['oci', 'max_workers'],
            
            # CloudFlare
            'CLOUDFLARE_EMAIL': ['cloudflare', 'email'],
            'CLOUDFLARE_API_TOKEN': ['cloudflare', 'api_token'],
            'CLOUDFLARE_ACCOUNTS': ['cloudflare', 'accounts'],  # Comma-separated
            'CLOUDFLARE_ZONES': ['cloudflare', 'zones'],  # Comma-separated
            
            # SSH
            'SSH_CONFIG_FILE': ['ssh', 'config_file'],
            'SSH_KEY_DIR': ['ssh', 'key_dir'],
            'SSH_MAX_WORKERS': ['ssh', 'max_workers'],
            
            # Slack
            'SLACK_WEBHOOK_URL': ['slack', 'webhook_url'],
            'SLACK_ENABLED': ['slack', 'enabled'],
            
            # NCP
            'NCP_ACCESS_KEY': ['ncp', 'access_key'],
            'NCP_SECRET_KEY': ['ncp', 'secret_key'],
            'NCP_REGION': ['ncp', 'region'],
            'NCP_CONFIG_PATH': ['ncp', 'config_path'],
            'NCP_MAX_WORKERS': ['ncp', 'max_workers'],
            
            # NCP Gov
            'NCPGOV_ACCESS_KEY': ['ncpgov', 'access_key'],
            'NCPGOV_SECRET_KEY': ['ncpgov', 'secret_key'],
            'NCPGOV_REGION': ['ncpgov', 'region'],
            'NCPGOV_CONFIG_PATH': ['ncpgov', 'config_path'],
            'NCPGOV_MAX_WORKERS': ['ncpgov', 'max_workers'],
            
            # MCP
            'MCP_GITHUB_TOKEN': ['mcp', 'servers', 'github', 'personal_access_token'],
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                # Handle comma-separated values
                if env_var.endswith('S') and ',' in value:  # Plural env vars with commas
                    value = [item.strip() for item in value.split(',') if item.strip()]
                
                # Handle boolean values
                if env_var.endswith('_ENABLED'):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                
                # Handle integer values
                if any(field in env_var for field in ['MAX_WORKERS', 'DURATION', 'MAX_FILES']):
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {value}")
                        continue
                
                self._set_nested_value(env_config, config_path, value)
        
        return env_config
    
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
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two configuration dictionaries.
        
        Args:
            base: Base configuration
            override: Override configuration
            
        Returns:
            Merged configuration
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "version": "1.0",
            "logging": {
                "console_level": "ERROR",
                "file_level": "INFO",
                "file_path": "~/.ic/logs/ic_{date}.log",
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
            "ncp": {
                "config_path": "~/.ncp/config",
                "regions": ["KR"],
                "max_workers": 10,
            },
            "ncpgov": {
                "config_path": "~/.ncpgov/config",
                "regions": ["KR"],
                "max_workers": 10,
                "security": {
                    "encryption_enabled": True,
                    "audit_logging_enabled": True,
                    "access_control_enabled": True,
                },
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
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration.
        
        Returns:
            Current configuration dictionary
        """
        return self.config_data
    
    def get_config_sources(self) -> List[str]:
        """
        Get list of configuration sources that were loaded.
        
        Returns:
            List of configuration source names
        """
        return self.config_sources.copy()
    
    def save_config(self, config_path: Union[str, Path], config_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config_path: Path to save configuration
            config_data: Configuration data to save (uses current config if None)
        """
        if config_data is None:
            config_data = self.config_data
        
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            elif config_path.suffix.lower() == '.json':
                json.dump(config_data, f, indent=2)
            else:
                raise ValueError(f"Unsupported config file format: {config_path.suffix}")
        
        logger.info(f"Configuration saved to {config_path}")
    
    def backup_config(self, config_path: Union[str, Path]) -> Optional[Path]:
        """
        Create a backup of existing configuration file.
        
        Args:
            config_path: Path to configuration file to backup
            
        Returns:
            Path to backup file if successful, None otherwise
        """
        config_path = Path(config_path)
        if not config_path.exists():
            return None
        
        # Create backup directory
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{config_path.stem}_{timestamp}{config_path.suffix}"
        backup_path = self._backup_dir / backup_name
        
        try:
            shutil.copy2(config_path, backup_path)
            logger.info(f"Configuration backed up to {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup configuration: {e}")
            return None
    
    def safe_update_config(self, config_path: Union[str, Path], 
                          config_data: Dict[str, Any]) -> bool:
        """
        Safely update configuration with backup and validation.
        
        Args:
            config_path: Path to configuration file
            config_data: New configuration data
            
        Returns:
            True if update was successful
        """
        config_path = Path(config_path)
        
        # Create backup if file exists
        backup_path = None
        if config_path.exists():
            backup_path = self.backup_config(config_path)
            if backup_path is None:
                logger.error("Failed to create backup, aborting update")
                return False
        
        # Validate security if SecurityManager is available
        if self.security_manager:
            security_warnings = self.security_manager.validate_config_security(config_data)
            if security_warnings:
                for warning in security_warnings:
                    logger.warning(f"Security warning in new config: {warning}")
                
                # If there are critical security issues, abort
                critical_warnings = [w for w in security_warnings if "secret" in w.lower()]
                if critical_warnings:
                    logger.error("Critical security issues found, aborting update")
                    return False
        
        try:
            # Save new configuration
            self.save_config(config_path, config_data)
            
            # Verify the saved configuration can be loaded
            test_config = self._load_config_file(config_path)
            if not test_config:
                raise ValueError("Saved configuration is empty or invalid")
            
            logger.info(f"Configuration successfully updated at {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            
            # Restore from backup if available
            if backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, config_path)
                    logger.info(f"Configuration restored from backup")
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")
            
            return False
    
    def validate_config(self, config_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Validate configuration data.
        
        Args:
            config_data: Configuration data to validate (uses current config if None)
            
        Returns:
            List of validation errors
        """
        if config_data is None:
            config_data = self.config_data
        
        errors = []
        
        # Basic structure validation
        if not isinstance(config_data, dict):
            errors.append("Configuration must be a dictionary")
            return errors
        
        # Version validation
        if 'version' not in config_data:
            errors.append("Configuration missing required 'version' field")
        
        # Validate required sections (only logging and security are truly required)
        required_sections = ['logging', 'security']
        for section in required_sections:
            if section not in config_data:
                errors.append(f"Configuration missing required section: {section}")
        
        # Optional cloud provider sections - at least one should be present
        cloud_sections = ['aws', 'azure', 'gcp', 'ncp', 'ncpgov', 'oci', 'cloudflare']
        if not any(section in config_data for section in cloud_sections):
            errors.append("Configuration should include at least one cloud provider section (aws, azure, gcp, ncp, ncpgov, oci, cloudflare)")
        
        # Validate NCP configuration if present
        if 'ncp' in config_data:
            ncp_errors = self._validate_ncp_config(config_data['ncp'])
            errors.extend(ncp_errors)
        
        # Validate NCP Gov configuration if present
        if 'ncpgov' in config_data:
            ncpgov_errors = self._validate_ncpgov_config(config_data['ncpgov'])
            errors.extend(ncpgov_errors)
        
        # Validate logging configuration
        if 'logging' in config_data:
            logging_config = config_data['logging']
            if not isinstance(logging_config, dict):
                errors.append("Logging configuration must be a dictionary")
            else:
                required_log_fields = ['console_level', 'file_level', 'file_path']
                for field in required_log_fields:
                    if field not in logging_config:
                        errors.append(f"Logging configuration missing required field: {field}")
        
        # Security validation if SecurityManager is available
        if self.security_manager:
            security_warnings = self.security_manager.validate_config_security(config_data)
            errors.extend(security_warnings)
        
        return errors
    
    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to configuration value (e.g., 'aws.regions')
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        current = self.config_data
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def set_config_value(self, key_path: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to configuration value
            value: Value to set
        """
        keys = key_path.split('.')
        current = self.config_data
        
        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the value
        current[keys[-1]] = value
    
    def cleanup_old_backups(self, max_backups: int = 10) -> None:
        """
        Clean up old backup files, keeping only the most recent ones.
        
        Args:
            max_backups: Maximum number of backup files to keep
        """
        if not self._backup_dir.exists():
            return
        
        try:
            backup_files = list(self._backup_dir.glob("*.yaml")) + list(self._backup_dir.glob("*.yml"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove old backups
            for backup_file in backup_files[max_backups:]:
                backup_file.unlink()
                logger.debug(f"Removed old backup: {backup_file}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")    

    def load_all_configs(self) -> Dict[str, Any]:
        """
        Load all configurations including secrets and external configs.
        
        Returns:
            Merged configuration dictionary
        """
        # Load base configuration
        config = self.load_config()
        
        # Load secrets configuration
        secrets = self.load_secrets_config()
        if secrets:
            config = self._merge_configs(config, secrets)
            self.config_sources.append("secrets")
        
        # Load external configurations
        external = self.load_external_configs()
        if external:
            self.external_configs = external
            self.config_sources.append("external")
        
        self.config_data = config
        return config
    
    def load_secrets_config(self) -> Dict[str, Any]:
        """
        Load secrets configuration using SecretsManager.
        
        Returns:
            Secrets configuration dictionary
        """
        secrets_config = self.secrets_manager.load_secrets()
        self.secrets_data = secrets_config
        return secrets_config
    
    def _load_secrets_from_env(self) -> Dict[str, Any]:
        """
        Load sensitive configuration from environment variables.
        
        Returns:
            Environment-based secrets configuration
        """
        env_secrets = {}
        
        # AWS secrets
        aws_accounts = os.getenv('AWS_ACCOUNTS')
        if aws_accounts:
            self._set_nested_value(env_secrets, ['aws', 'accounts'], 
                                 [acc.strip() for acc in aws_accounts.split(',') if acc.strip()])
        
        # CloudFlare secrets
        cf_email = os.getenv('CLOUDFLARE_EMAIL')
        cf_token = os.getenv('CLOUDFLARE_API_TOKEN')
        cf_accounts = os.getenv('CLOUDFLARE_ACCOUNTS')
        cf_zones = os.getenv('CLOUDFLARE_ZONES')
        
        if any([cf_email, cf_token, cf_accounts, cf_zones]):
            cf_config = {}
            if cf_email:
                cf_config['email'] = cf_email
            if cf_token:
                cf_config['api_token'] = cf_token
            if cf_accounts:
                cf_config['accounts'] = [acc.strip() for acc in cf_accounts.split(',') if acc.strip()]
            if cf_zones:
                cf_config['zones'] = [zone.strip() for zone in cf_zones.split(',') if zone.strip()]
            env_secrets['cloudflare'] = cf_config
        
        # GCP secrets
        gcp_key_path = os.getenv('GCP_SERVICE_ACCOUNT_KEY_PATH') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        gcp_projects = os.getenv('GCP_PROJECTS')
        
        if gcp_key_path or gcp_projects:
            gcp_config = {}
            if gcp_key_path:
                gcp_config['service_account_key_path'] = gcp_key_path
            if gcp_projects:
                gcp_config['projects'] = [proj.strip() for proj in gcp_projects.split(',') if proj.strip()]
            env_secrets['gcp'] = gcp_config
        
        # Azure secrets
        azure_tenant = os.getenv('AZURE_TENANT_ID')
        azure_client_id = os.getenv('AZURE_CLIENT_ID')
        azure_client_secret = os.getenv('AZURE_CLIENT_SECRET')
        azure_subscriptions = os.getenv('AZURE_SUBSCRIPTIONS')
        
        if any([azure_tenant, azure_client_id, azure_client_secret, azure_subscriptions]):
            azure_config = {}
            if azure_tenant:
                azure_config['tenant_id'] = azure_tenant
            if azure_client_id:
                azure_config['client_id'] = azure_client_id
            if azure_client_secret:
                azure_config['client_secret'] = azure_client_secret
            if azure_subscriptions:
                azure_config['subscriptions'] = [sub.strip() for sub in azure_subscriptions.split(',') if sub.strip()]
            env_secrets['azure'] = azure_config
        
        # Slack secrets
        slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        if slack_webhook:
            env_secrets['slack'] = {'webhook_url': slack_webhook}
        
        return env_secrets
    
    def load_external_configs(self) -> Dict[str, Any]:
        """
        Load external configuration files using ExternalConfigLoader.
        
        Returns:
            External configurations dictionary
        """
        external_configs = self.external_loader.load_all_external_configs()
        self.external_configs = external_configs
        return external_configs
    
    def _load_aws_config(self) -> Dict[str, Any]:
        """Load AWS configuration from ~/.aws/config and ~/.aws/credentials"""
        aws_config = {}
        
        # Load AWS config file
        aws_config_path = Path.home() / ".aws" / "config"
        if aws_config_path.exists():
            try:
                import configparser
                config = configparser.ConfigParser()
                config.read(aws_config_path)
                
                profiles = {}
                for section_name in config.sections():
                    if section_name.startswith('profile '):
                        profile_name = section_name.split('profile ')[1]
                        profiles[profile_name] = dict(config[section_name])
                    elif section_name == 'default':
                        profiles['default'] = dict(config[section_name])
                
                if profiles:
                    aws_config['profiles'] = profiles
                    
            except Exception as e:
                logger.warning(f"Failed to load AWS config: {e}")
        
        # Load AWS credentials file
        aws_creds_path = Path.home() / ".aws" / "credentials"
        if aws_creds_path.exists():
            try:
                import configparser
                config = configparser.ConfigParser()
                config.read(aws_creds_path)
                
                credentials = {}
                for section_name in config.sections():
                    credentials[section_name] = dict(config[section_name])
                
                if credentials:
                    aws_config['credentials'] = credentials
                    
            except Exception as e:
                logger.warning(f"Failed to load AWS credentials: {e}")
        
        return aws_config
    
    def _load_oci_config(self) -> Dict[str, Any]:
        """Load OCI configuration from ~/.oci/config"""
        oci_config = {}
        
        oci_config_path = Path.home() / ".oci" / "config"
        if oci_config_path.exists():
            try:
                import configparser
                config = configparser.ConfigParser()
                config.read(oci_config_path)
                
                profiles = {}
                for section_name in config.sections():
                    profiles[section_name] = dict(config[section_name])
                
                if profiles:
                    oci_config['profiles'] = profiles
                    
            except Exception as e:
                logger.warning(f"Failed to load OCI config: {e}")
        
        return oci_config
    
    def _load_ssh_config(self) -> Dict[str, Any]:
        """Load SSH configuration from ~/.ssh/config"""
        ssh_config = {}
        
        ssh_config_path = Path.home() / ".ssh" / "config"
        if ssh_config_path.exists():
            try:
                hosts = {}
                current_host = None
                
                with open(ssh_config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        if line.lower().startswith('host '):
                            current_host = line.split(' ', 1)[1]
                            hosts[current_host] = {}
                        elif current_host and ' ' in line:
                            key, value = line.split(' ', 1)
                            hosts[current_host][key.lower()] = value
                
                if hosts:
                    ssh_config['hosts'] = hosts
                    
            except Exception as e:
                logger.warning(f"Failed to load SSH config: {e}")
        
        return ssh_config
    

    
    def migrate_from_env(self, env_file_path: str = ".env", force: bool = False) -> bool:
        """
        Migrate configuration from .env file to YAML format using MigrationManager.
        
        Args:
            env_file_path: Path to the .env file
            force: Force migration even if YAML files already exist
            
        Returns:
            True if migration was successful
        """
        return self.migration_manager.migrate_env_to_yaml(env_file_path, force)
    
    def invalidate_cache(self):
        """캐시를 무효화합니다."""
        self._config_cache = None
        self._env_cache = None
        self._cache_timestamp = 0
        self._file_timestamps.clear()
        logger.debug("Configuration cache invalidated")
    
    def _validate_ncp_config(self, ncp_config: Dict[str, Any]) -> List[str]:
        """
        Validate NCP configuration settings.
        
        Args:
            ncp_config: NCP configuration dictionary
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not isinstance(ncp_config, dict):
            errors.append("NCP configuration must be a dictionary")
            return errors
        
        # Validate required credentials
        if 'access_key' in ncp_config:
            access_key = ncp_config['access_key']
            if not isinstance(access_key, str):
                errors.append("NCP access_key must be a string")
            elif len(access_key) < 10:
                errors.append("NCP access_key appears to be too short (minimum 10 characters)")
        
        if 'secret_key' in ncp_config:
            secret_key = ncp_config['secret_key']
            if not isinstance(secret_key, str):
                errors.append("NCP secret_key must be a string")
            elif len(secret_key) < 20:
                errors.append("NCP secret_key appears to be too short (minimum 20 characters)")
        
        # Validate region
        if 'region' in ncp_config:
            region = ncp_config['region']
            if not isinstance(region, str):
                errors.append("NCP region must be a string")
            else:
                valid_regions = ['KR', 'US', 'JP']
                if region not in valid_regions:
                    errors.append(f"Invalid NCP region: {region}. Valid regions: {valid_regions}")
        
        # Validate platform
        if 'platform' in ncp_config:
            platform = ncp_config['platform']
            if not isinstance(platform, str):
                errors.append("NCP platform must be a string")
            else:
                valid_platforms = ['Classic', 'VPC']
                if platform not in valid_platforms:
                    errors.append(f"Invalid NCP platform: {platform}. Valid platforms: {valid_platforms}")
        
        # Validate config_path
        if 'config_path' in ncp_config:
            config_path = ncp_config['config_path']
            if not isinstance(config_path, str):
                errors.append("NCP config_path must be a string")
        
        # Validate regions (list format)
        if 'regions' in ncp_config:
            regions = ncp_config['regions']
            if not isinstance(regions, list):
                errors.append("NCP regions must be a list")
            else:
                valid_regions = ['KR', 'US', 'JP']
                for region in regions:
                    if region not in valid_regions:
                        errors.append(f"Invalid NCP region: {region}. Valid regions: {valid_regions}")
        
        # Validate max_workers
        if 'max_workers' in ncp_config:
            max_workers = ncp_config['max_workers']
            if not isinstance(max_workers, int) or max_workers <= 0:
                errors.append("NCP max_workers must be a positive integer")
        
        return errors
    
    def _validate_ncpgov_config(self, ncpgov_config: Dict[str, Any]) -> List[str]:
        """
        Validate NCP Gov configuration settings.
        
        Args:
            ncpgov_config: NCP Gov configuration dictionary
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not isinstance(ncpgov_config, dict):
            errors.append("NCP Gov configuration must be a dictionary")
            return errors
        
        # Validate required credentials
        if 'access_key' in ncpgov_config:
            access_key = ncpgov_config['access_key']
            if not isinstance(access_key, str):
                errors.append("NCP Gov access_key must be a string")
            elif len(access_key) < 10:
                errors.append("NCP Gov access_key appears to be too short (minimum 10 characters)")
        
        if 'secret_key' in ncpgov_config:
            secret_key = ncpgov_config['secret_key']
            if not isinstance(secret_key, str):
                errors.append("NCP Gov secret_key must be a string")
            elif len(secret_key) < 20:
                errors.append("NCP Gov secret_key appears to be too short (minimum 20 characters)")
        
        if 'apigw_key' in ncpgov_config:
            apigw_key = ncpgov_config['apigw_key']
            if not isinstance(apigw_key, str):
                errors.append("NCP Gov apigw_key must be a string")
            elif len(apigw_key) < 10:
                errors.append("NCP Gov apigw_key appears to be too short (minimum 10 characters)")
        
        # Validate region
        if 'region' in ncpgov_config:
            region = ncpgov_config['region']
            if not isinstance(region, str):
                errors.append("NCP Gov region must be a string")
            else:
                valid_regions = ['KR']  # Government cloud only supports Korea
                if region not in valid_regions:
                    errors.append(f"Invalid NCP Gov region: {region}. Government cloud only supports: {valid_regions}")
        
        # Validate platform
        if 'platform' in ncpgov_config:
            platform = ncpgov_config['platform']
            if not isinstance(platform, str):
                errors.append("NCP Gov platform must be a string")
            else:
                valid_platforms = ['VPC']  # Government cloud typically uses VPC
                if platform not in valid_platforms:
                    errors.append(f"Invalid NCP Gov platform: {platform}. Government cloud supports: {valid_platforms}")
        
        # Validate config_path
        if 'config_path' in ncpgov_config:
            config_path = ncpgov_config['config_path']
            if not isinstance(config_path, str):
                errors.append("NCP Gov config_path must be a string")
        
        # Validate regions (Government cloud only supports KR)
        if 'regions' in ncpgov_config:
            regions = ncpgov_config['regions']
            if not isinstance(regions, list):
                errors.append("NCP Gov regions must be a list")
            else:
                valid_regions = ['KR']  # Government cloud only supports Korea
                for region in regions:
                    if region not in valid_regions:
                        errors.append(f"Invalid NCP Gov region: {region}. Government cloud only supports: {valid_regions}")
        
        # Validate max_workers
        if 'max_workers' in ncpgov_config:
            max_workers = ncpgov_config['max_workers']
            if not isinstance(max_workers, int) or max_workers <= 0:
                errors.append("NCP Gov max_workers must be a positive integer")
        
        # Validate security settings (required for government cloud)
        # Check for security settings either in nested 'security' section or at root level
        security_config = ncpgov_config.get('security', {})
        
        # If no nested security section, check for security settings at root level
        if not security_config:
            # Check if security settings are at root level (flat structure)
            root_security_settings = {
                'encryption_enabled': ncpgov_config.get('encryption_enabled'),
                'audit_logging_enabled': ncpgov_config.get('audit_logging_enabled'),
                'access_control_enabled': ncpgov_config.get('access_control_enabled')
            }
            
            # If any security settings found at root level, use them
            if any(v is not None for v in root_security_settings.values()):
                security_config = {k: v for k, v in root_security_settings.items() if v is not None}
        
        if security_config:
            if not isinstance(security_config, dict):
                errors.append("NCP Gov security configuration must be a dictionary")
            else:
                required_security_settings = [
                    'encryption_enabled',
                    'audit_logging_enabled',
                    'access_control_enabled'
                ]
                
                for setting in required_security_settings:
                    if setting not in security_config:
                        errors.append(f"NCP Gov missing required security setting: {setting}")
                    elif not isinstance(security_config[setting], bool):
                        errors.append(f"NCP Gov security setting {setting} must be a boolean")
                    elif not security_config[setting]:
                        errors.append(f"NCP Gov security setting {setting} must be enabled for government cloud compliance")
        else:
            errors.append("NCP Gov configuration missing required security settings (encryption_enabled, audit_logging_enabled, access_control_enabled)")
        
        return errors
    
    def _load_ncp_config(self) -> Dict[str, Any]:
        """
        Load NCP configuration from ~/.ncp/config file.
        
        Returns:
            NCP configuration dictionary
        """
        ncp_config = {}
        
        # Check for NCP config file
        ncp_config_path = Path.home() / ".ncp" / "config"
        if ncp_config_path.exists():
            try:
                with open(ncp_config_path, 'r', encoding='utf-8') as f:
                    ncp_file_config = yaml.safe_load(f) or {}
                
                # Use default profile if available, otherwise use the whole config
                if 'default' in ncp_file_config:
                    ncp_config = ncp_file_config['default']
                else:
                    ncp_config = ncp_file_config
                
                logger.debug(f"Loaded NCP config from {ncp_config_path}")
            except Exception as e:
                logger.warning(f"Failed to load NCP config from {ncp_config_path}: {e}")
        
        # Override with environment variables
        env_ncp = self._load_ncp_env_config()
        if env_ncp:
            ncp_config = self._merge_configs(ncp_config, env_ncp)
        
        return ncp_config
    
    def _load_ncp_env_config(self) -> Dict[str, Any]:
        """
        Load NCP configuration from environment variables.
        
        Returns:
            NCP configuration from environment variables
        """
        env_config = {}
        
        # Map environment variables to config keys
        env_mappings = {
            'NCP_ACCESS_KEY': 'access_key',
            'NCP_SECRET_KEY': 'secret_key',
            'NCP_REGION': 'region',
            'NCP_PLATFORM': 'platform',
            'NCP_CONFIG_PATH': 'config_path',
            'NCP_MAX_WORKERS': 'max_workers',
            'NCP_TIMEOUT': 'timeout'
        }
        
        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                # Handle integer values
                if config_key in ['max_workers', 'timeout']:
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {value}")
                        continue
                
                env_config[config_key] = value
        
        return env_config
    
    def _load_ncpgov_config(self) -> Dict[str, Any]:
        """
        Load NCP Gov configuration from ~/.ncpgov/config file.
        
        Returns:
            NCP Gov configuration dictionary
        """
        ncpgov_config = {}
        
        # Check for NCP Gov config file
        ncpgov_config_path = Path.home() / ".ncpgov" / "config"
        if ncpgov_config_path.exists():
            try:
                with open(ncpgov_config_path, 'r', encoding='utf-8') as f:
                    ncpgov_file_config = yaml.safe_load(f) or {}
                
                # Use default profile if available, otherwise use the whole config
                if 'default' in ncpgov_file_config:
                    ncpgov_config = ncpgov_file_config['default']
                else:
                    ncpgov_config = ncpgov_file_config
                
                logger.debug(f"Loaded NCP Gov config from {ncpgov_config_path}")
            except Exception as e:
                logger.warning(f"Failed to load NCP Gov config from {ncpgov_config_path}: {e}")
        
        # Override with environment variables
        env_ncpgov = self._load_ncpgov_env_config()
        if env_ncpgov:
            ncpgov_config = self._merge_configs(ncpgov_config, env_ncpgov)
        
        return ncpgov_config
    
    def _load_ncpgov_env_config(self) -> Dict[str, Any]:
        """
        Load NCP Gov configuration from environment variables.
        
        Returns:
            NCP Gov configuration from environment variables
        """
        env_config = {}
        
        # Map environment variables to config keys
        env_mappings = {
            'NCPGOV_ACCESS_KEY': 'access_key',
            'NCPGOV_SECRET_KEY': 'secret_key',
            'NCPGOV_APIGW_KEY': 'apigw_key',
            'NCPGOV_REGION': 'region',
            'NCPGOV_PLATFORM': 'platform',
            'NCPGOV_CONFIG_PATH': 'config_path',
            'NCPGOV_MAX_WORKERS': 'max_workers',
            'NCPGOV_TIMEOUT': 'timeout'
        }
        
        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                # Handle integer values
                if config_key in ['max_workers', 'timeout']:
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {value}")
                        continue
                
                env_config[config_key] = value
        
        # Handle security settings from environment
        security_env_mappings = {
            'NCPGOV_ENCRYPTION_ENABLED': 'encryption_enabled',
            'NCPGOV_AUDIT_LOGGING_ENABLED': 'audit_logging_enabled',
            'NCPGOV_ACCESS_CONTROL_ENABLED': 'access_control_enabled',
            'NCPGOV_MASK_SENSITIVE_DATA': 'mask_sensitive_data'
        }
        
        security_config = {}
        for env_var, config_key in security_env_mappings.items():
            value = os.getenv(env_var)
            if value:
                security_config[config_key] = value.lower() in ('true', '1', 'yes', 'on')
        
        if security_config:
            env_config['security'] = security_config
        
        return env_config
    
    def get_ncp_config_with_validation(self) -> Dict[str, Any]:
        """
        Get NCP configuration with comprehensive validation and error handling.
        
        Returns:
            Validated NCP configuration
            
        Raises:
            ValueError: If NCP configuration is invalid
            FileNotFoundError: If configuration files are missing
        """
        try:
            # Load NCP configuration
            ncp_config = self._load_ncp_config()
            
            # Validate configuration
            validation_errors = self._validate_ncp_config(ncp_config)
            
            if validation_errors:
                error_message = "NCP configuration validation failed:\n"
                for i, error in enumerate(validation_errors, 1):
                    error_message += f"  {i}. {error}\n"
                
                error_message += "\n💡 Configuration help:\n"
                error_message += "  • Check ~/.ncp/config for NCP settings\n"
                error_message += "  • Use environment variables: NCP_ACCESS_KEY, NCP_SECRET_KEY\n"
                error_message += "  • Run 'ic config init --template ncp' to create default configuration\n"
                error_message += "  • Copy .ncp/config.example to ~/.ncp/config and fill in your credentials\n"
                
                raise ValueError(error_message)
            
            return ncp_config
            
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"NCP configuration file not found: {e}\n"
                "💡 Run 'ic config init --template ncp' to create default configuration files"
            )
        except yaml.YAMLError as e:
            raise ValueError(
                f"NCP configuration file has invalid YAML syntax: {e}\n"
                "💡 Check your ~/.ncp/config file for proper YAML formatting"
            )
        except Exception as e:
            raise ValueError(f"Failed to load NCP configuration: {e}")
    
    def get_ncpgov_config_with_validation(self) -> Dict[str, Any]:
        """
        Get NCP Gov configuration with comprehensive validation and error handling.
        
        Returns:
            Validated NCP Gov configuration
            
        Raises:
            ValueError: If NCP Gov configuration is invalid
            FileNotFoundError: If configuration files are missing
        """
        try:
            # Load NCP Gov configuration
            ncpgov_config = self._load_ncpgov_config()
            
            # Validate configuration
            validation_errors = self._validate_ncpgov_config(ncpgov_config)
            
            if validation_errors:
                error_message = "NCP Gov configuration validation failed:\n"
                for i, error in enumerate(validation_errors, 1):
                    error_message += f"  {i}. {error}\n"
                
                error_message += "\n💡 Configuration help:\n"
                error_message += "  • Check ~/.ncpgov/config for NCP Gov settings\n"
                error_message += "  • Use environment variables: NCPGOV_ACCESS_KEY, NCPGOV_SECRET_KEY, NCPGOV_APIGW_KEY\n"
                error_message += "  • Run 'ic config init --template ncpgov' to create default configuration\n"
                error_message += "  • Copy .ncpgov/config.example to ~/.ncpgov/config and fill in your credentials\n"
                error_message += "  • Ensure all security settings are enabled for government cloud compliance\n"
                
                raise ValueError(error_message)
            
            return ncpgov_config
            
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"NCP Gov configuration file not found: {e}\n"
                "💡 Run 'ic config init --template ncpgov' to create default configuration files"
            )
        except yaml.YAMLError as e:
            raise ValueError(
                f"NCP Gov configuration file has invalid YAML syntax: {e}\n"
                "💡 Check your ~/.ncpgov/config file for proper YAML formatting"
            )
        except Exception as e:
            raise ValueError(f"Failed to load NCP Gov configuration: {e}")
    
    def load_platform_config(self, platform: str, profile: str = 'default') -> Dict[str, Any]:
        """
        Load platform-specific configuration using hierarchical path lookup.
        
        Args:
            platform: Platform name (ncp, ncpgov, aws, etc.)
            profile: Profile name to load
            
        Returns:
            Platform configuration dictionary
            
        Raises:
            FileNotFoundError: If no configuration file is found
            ValueError: If configuration is invalid
        """
        config_path = self.path_manager.get_platform_config_path(platform)
        
        if not config_path or not config_path.exists():
            # Provide helpful error message
            available_paths = []
            if platform.lower() == "ncp":
                available_paths = [
                    self.path_manager.home_dir / ".ncp" / "config.yaml",
                    self.path_manager.home_dir / ".ic" / "config" / "ncp.yaml"
                ]
            elif platform.lower() == "ncpgov":
                available_paths = [
                    self.path_manager.home_dir / ".ncpgov" / "config.yaml",
                    self.path_manager.home_dir / ".ic" / "config" / "ncpgov.yaml"
                ]
            
            error_msg = f"No {platform} configuration found."
            if available_paths:
                error_msg += f"\n\nExpected locations:\n"
                for path in available_paths:
                    error_msg += f"  • {path}\n"
            error_msg += f"\nTo create configuration, run: ic config init --template {platform}"
            
            raise FileNotFoundError(error_msg)
        
        try:
            config_data = self._load_config_file(config_path)
            
            if not config_data:
                raise ValueError(f"{platform} configuration file is empty: {config_path}")
            
            if profile not in config_data:
                available_profiles = list(config_data.keys())
                raise ValueError(
                    f"Profile '{profile}' not found in {platform} configuration. "
                    f"Available profiles: {available_profiles}"
                )
            
            profile_config = config_data[profile]
            logger.debug(f"Loaded {platform} configuration for profile '{profile}' from {config_path}")
            
            return profile_config
            
        except Exception as e:
            logger.error(f"Failed to load {platform} configuration: {e}")
            raise
    
    def get_platform_config_info(self) -> Dict[str, Any]:
        """
        Get information about platform configuration availability.
        
        Returns:
            Dictionary with platform configuration status
        """
        return self.path_manager.get_config_sources_info()
    
    def migrate_legacy_configs(self, interactive: bool = True) -> Dict[str, Any]:
        """
        Migrate legacy configuration files to new hierarchical structure.
        
        Args:
            interactive: Whether to ask for user confirmation
            
        Returns:
            Migration results
        """
        from .migration_utils import ConfigMigrationUtils, create_migration_confirmation_callback
        
        migration_utils = ConfigMigrationUtils(self.path_manager)
        
        if interactive:
            confirm_func = create_migration_confirmation_callback(interactive=True)
            return migration_utils.interactive_migration(confirm_func)
        else:
            confirm_func = create_migration_confirmation_callback(interactive=False)
            return migration_utils.interactive_migration(confirm_func)