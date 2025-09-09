"""
Migration manager module for IC.

This module provides migration functionality from .env files to YAML configuration.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Manages migration from .env files to YAML configuration system.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize MigrationManager.
        
        Args:
            config_manager: Reference to ConfigManager instance
        """
        self.config_manager = config_manager
        self.backup_dir = Path("backup")
        self.migration_history: List[Dict[str, Any]] = []
    
    def migrate_env_to_yaml(self, env_file_path: str = ".env", 
                           force: bool = False) -> bool:
        """
        Migrate configuration from .env file to YAML format.
        
        Args:
            env_file_path: Path to the .env file
            force: Force migration even if YAML files already exist
            
        Returns:
            True if migration was successful
        """
        env_path = Path(env_file_path)
        if not env_path.exists():
            logger.warning(f"No .env file found at {env_path}")
            return False
        
        # Check if YAML files already exist
        config_dir = Path("config")
        default_yaml = config_dir / "default.yaml"
        secrets_yaml = config_dir / "secrets.yaml"
        
        if not force and (default_yaml.exists() or secrets_yaml.exists()):
            logger.warning("YAML configuration files already exist. Use force=True to overwrite.")
            return False
        
        try:
            # Parse .env file
            env_vars = self._parse_env_file(env_path)
            
            # Separate sensitive and non-sensitive data
            default_config, secrets_config = self._categorize_env_vars(env_vars)
            
            # Create config directory
            config_dir.mkdir(exist_ok=True)
            
            # Backup existing files if they exist
            if default_yaml.exists():
                self._backup_file(default_yaml)
            if secrets_yaml.exists():
                self._backup_file(secrets_yaml)
            
            # Save configurations
            success = True
            
            # Save default configuration
            if default_config:
                success &= self._save_yaml_config(default_yaml, default_config)
            
            # Save secrets configuration
            if secrets_config:
                success &= self._save_yaml_config(secrets_yaml, secrets_config)
                
                # Set restrictive permissions on secrets file
                try:
                    secrets_yaml.chmod(0o600)
                except Exception as e:
                    logger.warning(f"Failed to set restrictive permissions on secrets file: {e}")
            
            if success:
                # Backup original .env file
                self._backup_file(env_path)
                
                # Record migration
                self._record_migration(env_path, default_yaml, secrets_yaml)
                
                logger.info("Successfully migrated .env file to YAML configuration")
                return True
            else:
                logger.error("Failed to save YAML configuration files")
                return False
                
        except Exception as e:
            logger.error(f"Failed to migrate .env file: {e}")
            return False
    
    def _parse_env_file(self, env_path: Path) -> Dict[str, str]:
        """
        Parse .env file and extract key-value pairs.
        
        Args:
            env_path: Path to .env file
            
        Returns:
            Dictionary of environment variables
        """
        env_vars = {}
        
        with open(env_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Handle lines with equals sign
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
                    logger.warning(f"Skipping invalid line {line_num} in {env_path}: {line}")
        
        return env_vars
    
    def _categorize_env_vars(self, env_vars: Dict[str, str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Categorize environment variables into default config and secrets.
        
        Args:
            env_vars: Dictionary of environment variables
            
        Returns:
            Tuple of (default_config, secrets_config)
        """
        # Start with base default configuration
        default_config = self._get_base_default_config()
        secrets_config = {"version": "2.0"}
        
        # Define sensitive keys
        sensitive_keys = {
            'SLACK_WEBHOOK_URL', 'CLOUDFLARE_EMAIL', 'CLOUDFLARE_API_TOKEN',
            'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET',
            'GCP_SERVICE_ACCOUNT_KEY_PATH', 'GOOGLE_APPLICATION_CREDENTIALS',
            'AWS_ACCOUNTS'  # Account IDs are considered sensitive
        }
        
        # Categorize each environment variable
        for key, value in env_vars.items():
            if key in sensitive_keys or self._is_sensitive_key(key):
                self._add_to_secrets_config(secrets_config, key, value)
            else:
                self._add_to_default_config(default_config, key, value)
        
        return default_config, secrets_config
    
    def _is_sensitive_key(self, key: str) -> bool:
        """
        Check if a key is potentially sensitive.
        
        Args:
            key: Environment variable key
            
        Returns:
            True if key is potentially sensitive
        """
        sensitive_patterns = [
            'token', 'key', 'secret', 'password', 'passwd', 'pwd',
            'credential', 'webhook', 'api_key', 'access_key', 'private_key'
        ]
        
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in sensitive_patterns)
    
    def _add_to_secrets_config(self, secrets_config: Dict[str, Any], key: str, value: str):
        """Add environment variable to secrets configuration."""
        if key == 'AWS_ACCOUNTS':
            self._set_nested_value(secrets_config, ['aws', 'accounts'], 
                                 [acc.strip() for acc in value.split(',') if acc.strip()])
        elif key == 'CLOUDFLARE_EMAIL':
            self._set_nested_value(secrets_config, ['cloudflare', 'email'], value)
        elif key == 'CLOUDFLARE_API_TOKEN':
            self._set_nested_value(secrets_config, ['cloudflare', 'api_token'], value)
        elif key == 'CLOUDFLARE_ACCOUNTS':
            self._set_nested_value(secrets_config, ['cloudflare', 'accounts'], 
                                 [acc.strip() for acc in value.split(',') if acc.strip()])
        elif key == 'CLOUDFLARE_ZONES':
            self._set_nested_value(secrets_config, ['cloudflare', 'zones'], 
                                 [zone.strip() for zone in value.split(',') if zone.strip()])
        elif key == 'SLACK_WEBHOOK_URL':
            self._set_nested_value(secrets_config, ['slack', 'webhook_url'], value)
        elif key == 'GCP_SERVICE_ACCOUNT_KEY_PATH' or key == 'GOOGLE_APPLICATION_CREDENTIALS':
            self._set_nested_value(secrets_config, ['gcp', 'service_account_key_path'], value)
        elif key == 'GCP_PROJECTS':
            self._set_nested_value(secrets_config, ['gcp', 'projects'], 
                                 [proj.strip() for proj in value.split(',') if proj.strip()])
        elif key == 'AZURE_TENANT_ID':
            self._set_nested_value(secrets_config, ['azure', 'tenant_id'], value)
        elif key == 'AZURE_CLIENT_ID':
            self._set_nested_value(secrets_config, ['azure', 'client_id'], value)
        elif key == 'AZURE_CLIENT_SECRET':
            self._set_nested_value(secrets_config, ['azure', 'client_secret'], value)
        elif key == 'AZURE_SUBSCRIPTIONS':
            self._set_nested_value(secrets_config, ['azure', 'subscriptions'], 
                                 [sub.strip() for sub in value.split(',') if sub.strip()])
        else:
            # Generic sensitive key handling
            logger.warning(f"Unknown sensitive key '{key}', storing in secrets under 'other'")
            self._set_nested_value(secrets_config, ['other', key.lower()], value)
    
    def _add_to_default_config(self, default_config: Dict[str, Any], key: str, value: str):
        """Add environment variable to default configuration."""
        if key == 'REGIONS':
            self._set_nested_value(default_config, ['aws', 'regions'], 
                                 [reg.strip() for reg in value.split(',') if reg.strip()])
        elif key == 'REQUIRED_TAGS':
            self._set_nested_value(default_config, ['aws', 'tags', 'required'], 
                                 [tag.strip() for tag in value.split(',') if tag.strip()])
        elif key == 'OPTIONAL_TAGS':
            self._set_nested_value(default_config, ['aws', 'tags', 'optional'], 
                                 [tag.strip() for tag in value.split(',') if tag.strip()])
        elif key.startswith('RULE_'):
            rule_name = key[5:].lower()  # Remove 'RULE_' prefix
            self._set_nested_value(default_config, ['aws', 'tags', 'rules', rule_name.title()], value)
        elif key == 'SSH_MAX_WORKER':
            self._set_nested_value(default_config, ['ssh', 'max_workers'], int(value))
        elif key == 'SSH_SKIP_PREFIXES':
            self._set_nested_value(default_config, ['ssh', 'skip_prefixes'], 
                                 [prefix.strip() for prefix in value.split(',') if prefix.strip()])
        elif key == 'PORT_OPEN_TIMEOUT':
            self._set_nested_value(default_config, ['ssh', 'timeouts', 'port_scan'], float(value))
        elif key == 'SSH_TIMEOUT':
            self._set_nested_value(default_config, ['ssh', 'timeouts', 'ssh_connect'], int(value))
        elif key == 'SSH_KEY_DIR':
            self._set_nested_value(default_config, ['ssh', 'key_dir'], value)
        elif key == 'SSH_CONFIG_FILE':
            self._set_nested_value(default_config, ['ssh', 'config_file'], value)
        elif key == 'LOG_LEVEL':
            self._set_nested_value(default_config, ['logging', 'console_level'], value.upper())
        elif key == 'OCI_CONFIG_PATH':
            self._set_nested_value(default_config, ['oci', 'config_path'], value)
        elif key == 'GCP_REGIONS':
            self._set_nested_value(default_config, ['gcp', 'regions'], 
                                 [reg.strip() for reg in value.split(',') if reg.strip()])
        elif key == 'GCP_ZONES':
            self._set_nested_value(default_config, ['gcp', 'zones'], 
                                 [zone.strip() for zone in value.split(',') if zone.strip()])
        elif key == 'GCP_MAX_WORKERS':
            self._set_nested_value(default_config, ['gcp', 'max_workers'], int(value))
        elif key == 'AZURE_LOCATIONS':
            self._set_nested_value(default_config, ['azure', 'locations'], 
                                 [loc.strip() for loc in value.split(',') if loc.strip()])
        elif key == 'AZURE_MAX_WORKERS':
            self._set_nested_value(default_config, ['azure', 'max_workers'], int(value))
        else:
            # Generic non-sensitive key handling
            logger.info(f"Unknown non-sensitive key '{key}', storing in default config under 'other'")
            self._set_nested_value(default_config, ['other', key.lower()], value)
    
    def _set_nested_value(self, config: Dict[str, Any], path: List[str], value: Any):
        """Set a nested value in configuration dictionary."""
        current = config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value
    
    def _get_base_default_config(self) -> Dict[str, Any]:
        """Get base default configuration structure."""
        return {
            "version": "2.0",
            "logging": {
                "console_level": "ERROR",
                "file_level": "INFO",
                "file_path": "~/.ic/logs/ic_{date}.log",
                "max_files": 30,
                "format": "%(asctime)s [%(levelname)s] - %(message)s",
                "mask_sensitive": True,
            },
            "aws": {
                "config_path": "~/.aws/config",
                "credentials_path": "~/.aws/credentials",
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
                "config_path": "~/.cloudflare/config",
                "accounts": [],
                "zones": [],
            },
            "ssh": {
                "config_file": "~/.ssh/config",
                "key_dir": "~/aws-key",
                "max_workers": 70,
                "skip_prefixes": ["git", "akrr-portx", "akrr-taas-gw", "agw01", "semaphore"],
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
    
    def _save_yaml_config(self, file_path: Path, config: Dict[str, Any]) -> bool:
        """
        Save configuration to YAML file.
        
        Args:
            file_path: Path to save the file
            config: Configuration dictionary
            
        Returns:
            True if successful
        """
        try:
            import yaml
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2, 
                         allow_unicode=True, sort_keys=False)
            
            logger.info(f"Saved configuration to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration to {file_path}: {e}")
            return False
    
    def _backup_file(self, file_path: Path) -> Optional[Path]:
        """
        Create a backup of a file.
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            Path to backup file if successful
        """
        if not file_path.exists():
            return None
        
        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.backup_dir / backup_name
        
        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"Backed up {file_path} to {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup {file_path}: {e}")
            return None
    
    def _record_migration(self, env_path: Path, default_yaml: Path, secrets_yaml: Path):
        """Record migration details for history."""
        migration_record = {
            "timestamp": datetime.now().isoformat(),
            "source_file": str(env_path),
            "target_files": {
                "default_config": str(default_yaml),
                "secrets_config": str(secrets_yaml) if secrets_yaml.exists() else None
            },
            "backup_location": str(self.backup_dir)
        }
        
        self.migration_history.append(migration_record)
    
    def create_migration_history_document(self) -> bool:
        """
        Create a migration history document.
        
        Returns:
            True if document was created successfully
        """
        try:
            history_content = self._generate_migration_history_content()
            
            history_path = self.backup_dir / "migration_history.md"
            with open(history_path, 'w', encoding='utf-8') as f:
                f.write(history_content)
            
            logger.info(f"Created migration history document at {history_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create migration history document: {e}")
            return False
    
    def _generate_migration_history_content(self) -> str:
        """Generate migration history document content."""
        content = """# IC Configuration Migration History

This document records the migration from .env files to YAML configuration system.

## Migration Overview

The IC configuration system has been migrated from environment variable-based (.env) 
configuration to a structured YAML-based system with the following benefits:

- **Security**: Sensitive data is separated into `config/secrets.yaml`
- **Structure**: Configuration is organized by service and purpose
- **Validation**: Built-in validation and security checks
- **External References**: Direct integration with cloud provider config files
- **Fixed Logging**: Logs are written to a consistent location

## File Structure Changes

### Before Migration
```
.env                    # All configuration in one file
logs/                   # Logs created in current directory
```

### After Migration
```
config/
├── default.yaml        # Non-sensitive configuration
└── secrets.yaml        # Sensitive configuration (600 permissions)

~/.ic/
└── logs/               # Fixed log location

backup/
├── .env_YYYYMMDD_HHMMSS    # Backed up original .env
└── migration_history.md    # This document
```

## Migration Records

"""
        
        if self.migration_history:
            for i, record in enumerate(self.migration_history, 1):
                content += f"### Migration {i}\n\n"
                content += f"- **Date**: {record['timestamp']}\n"
                content += f"- **Source**: {record['source_file']}\n"
                content += f"- **Default Config**: {record['target_files']['default_config']}\n"
                
                if record['target_files']['secrets_config']:
                    content += f"- **Secrets Config**: {record['target_files']['secrets_config']}\n"
                
                content += f"- **Backup Location**: {record['backup_location']}\n\n"
        else:
            content += "No migration records found.\n\n"
        
        content += """## Configuration Categories

### Default Configuration (config/default.yaml)
- Logging settings
- Service endpoints and regions
- Worker thread counts
- Timeout values
- Tag validation rules
- External config file paths

### Secrets Configuration (config/secrets.yaml)
- API tokens and keys
- Account IDs and credentials
- Webhook URLs
- Service account paths
- Subscription IDs

## Security Notes

1. **File Permissions**: `config/secrets.yaml` should have 600 permissions (owner read/write only)
2. **Version Control**: Add `config/secrets.yaml` to `.gitignore`
3. **Environment Fallback**: If secrets.yaml is missing, system falls back to environment variables
4. **Sensitive Data Masking**: All logs automatically mask sensitive information

## Rollback Instructions

If you need to rollback to the .env system:

1. Copy the backed up .env file from the backup directory
2. Remove or rename the config/ directory
3. Restart the application

## Next Steps

1. Review the generated configuration files
2. Update any service-specific settings as needed
3. Ensure secrets.yaml has proper file permissions
4. Add secrets.yaml to .gitignore if using version control
5. Test all services to ensure proper configuration loading

"""
        
        return content
    
    def validate_migration(self) -> Dict[str, List[str]]:
        """
        Validate the migration results.
        
        Returns:
            Dictionary of validation results
        """
        issues = {
            "errors": [],
            "warnings": [],
            "info": []
        }
        
        # Check if config files exist
        config_dir = Path("config")
        default_yaml = config_dir / "default.yaml"
        secrets_yaml = config_dir / "secrets.yaml"
        
        if not default_yaml.exists():
            issues["errors"].append("default.yaml not found in config directory")
        
        if not secrets_yaml.exists():
            issues["warnings"].append("secrets.yaml not found - will use environment variables")
        else:
            # Check file permissions
            try:
                file_mode = secrets_yaml.stat().st_mode & 0o777
                if file_mode != 0o600:
                    issues["warnings"].append(f"secrets.yaml has insecure permissions: {oct(file_mode)}")
            except Exception as e:
                issues["warnings"].append(f"Could not check secrets.yaml permissions: {e}")
        
        # Check if backup was created
        if not self.backup_dir.exists():
            issues["warnings"].append("No backup directory found")
        else:
            backup_files = list(self.backup_dir.glob("*.env*"))
            if not backup_files:
                issues["warnings"].append("No .env backup files found")
            else:
                issues["info"].append(f"Found {len(backup_files)} backup files")
        
        return issues