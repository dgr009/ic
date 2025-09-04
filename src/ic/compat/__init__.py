"""
Backward compatibility layer for IC package.

This module provides compatibility shims for existing import paths and functionality
to ensure smooth migration from the old structure to the new src/ layout.
"""

import warnings
from typing import Any, Dict, Optional
import os
from pathlib import Path

# Import new modules
from ..config.manager import ConfigManager
from ..config.security import SecurityManager
from ..core.logging import ICLogger
from ..core.session import AWSSessionManager
from ..core.mcp_manager import MCPManager

# Global compatibility instances
_config_manager: Optional[ConfigManager] = None
_logger: Optional[ICLogger] = None
_aws_session_manager: Optional[AWSSessionManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create global ConfigManager instance."""
    global _config_manager
    if _config_manager is None:
        security_manager = SecurityManager()
        _config_manager = ConfigManager(security_manager=security_manager)
        # Load configuration with .env fallback
        _config_manager.load_config()
    return _config_manager


def get_logger() -> ICLogger:
    """Get or create global ICLogger instance."""
    global _logger
    if _logger is None:
        config_manager = get_config_manager()
        config = config_manager.get_config()
        _logger = ICLogger(config)
    return _logger


def get_aws_session_manager() -> AWSSessionManager:
    """Get or create global AWSSessionManager instance."""
    global _aws_session_manager
    if _aws_session_manager is None:
        config_manager = get_config_manager()
        config = config_manager.get_config()
        _aws_session_manager = AWSSessionManager(config)
    return _aws_session_manager


def warn_deprecated(old_path: str, new_path: str, version: str = "2.0.0") -> None:
    """Issue deprecation warning for old import paths."""
    warnings.warn(
        f"'{old_path}' is deprecated and will be removed in version {version}. "
        f"Please use '{new_path}' instead.",
        DeprecationWarning,
        stacklevel=3
    )


class CompatibilityConfig:
    """
    Compatibility wrapper for configuration access.
    
    Provides backward compatibility for .env file access while encouraging
    migration to the new YAML-based configuration system.
    """
    
    def __init__(self):
        self._config_manager = get_config_manager()
        self._env_loaded = False
        self._load_env_if_needed()
    
    def _load_env_if_needed(self):
        """Load .env file if it exists and hasn't been loaded yet."""
        if not self._env_loaded:
            env_file = Path('.env')
            if env_file.exists():
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                    self._env_loaded = True
                    
                    # Issue deprecation warning
                    warn_deprecated(
                        ".env file usage",
                        "YAML configuration files (config.yaml)",
                        "2.0.0"
                    )
                except ImportError:
                    pass
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with .env fallback.
        
        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        # Try new config system first
        value = self._config_manager.get_config_value(key, None)
        if value is not None:
            return value
        
        # Fallback to environment variable
        env_key = key.upper().replace('.', '_')
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value
        
        # Legacy environment variable mappings
        legacy_mappings = {
            'aws.accounts': 'AWS_ACCOUNTS',
            'aws.regions': 'AWS_REGIONS',
            'aws.cross_account_role': 'AWS_CROSS_ACCOUNT_ROLE',
            'azure.subscription_id': 'AZURE_SUBSCRIPTION_ID',
            'azure.tenant_id': 'AZURE_TENANT_ID',
            'azure.client_id': 'AZURE_CLIENT_ID',
            'azure.client_secret': 'AZURE_CLIENT_SECRET',
            'gcp.project_id': 'GCP_PROJECT_ID',
            'gcp.service_account_key_path': 'GCP_SERVICE_ACCOUNT_KEY_PATH',
            'cloudflare.email': 'CLOUDFLARE_EMAIL',
            'cloudflare.api_token': 'CLOUDFLARE_API_TOKEN',
            'slack.webhook_url': 'SLACK_WEBHOOK_URL',
        }
        
        legacy_env_key = legacy_mappings.get(key)
        if legacy_env_key:
            legacy_value = os.getenv(legacy_env_key)
            if legacy_value is not None:
                return legacy_value
        
        return default
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration as dictionary."""
        return self._config_manager.get_config()
    
    def reload(self) -> None:
        """Reload configuration from all sources."""
        self._config_manager.load_config()
        self._env_loaded = False
        self._load_env_if_needed()


# Global compatibility config instance
compat_config = CompatibilityConfig()


def get_env_value(key: str, default: Any = None) -> Any:
    """
    Backward compatibility function for environment variable access.
    
    Args:
        key: Environment variable key
        default: Default value if not found
        
    Returns:
        Environment variable value or default
    """
    warn_deprecated(
        f"get_env_value('{key}')",
        f"compat_config.get('{key.lower().replace('_', '.')}')",
        "2.0.0"
    )
    return os.getenv(key, default)


def load_dotenv_compat():
    """
    Backward compatibility function for loading .env files.
    """
    warn_deprecated(
        "load_dotenv_compat()",
        "ConfigManager.load_config() with YAML files",
        "2.0.0"
    )
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


# Compatibility aliases for common functions
def get_aws_accounts() -> list:
    """Get AWS accounts from configuration."""
    accounts = compat_config.get('aws.accounts', [])
    if isinstance(accounts, str):
        return [acc.strip() for acc in accounts.split(',') if acc.strip()]
    return accounts or []


def get_aws_regions() -> list:
    """Get AWS regions from configuration."""
    regions = compat_config.get('aws.regions', ['ap-northeast-2'])
    if isinstance(regions, str):
        return [reg.strip() for reg in regions.split(',') if reg.strip()]
    return regions


def get_azure_subscription_id() -> Optional[str]:
    """Get Azure subscription ID from configuration."""
    return compat_config.get('azure.subscription_id')


def get_gcp_project_id() -> Optional[str]:
    """Get GCP project ID from configuration."""
    return compat_config.get('gcp.project_id')


def get_slack_webhook_url() -> Optional[str]:
    """Get Slack webhook URL from configuration."""
    return compat_config.get('slack.webhook_url')


# Export compatibility functions
__all__ = [
    'get_config_manager',
    'get_logger', 
    'get_aws_session_manager',
    'compat_config',
    'get_env_value',
    'load_dotenv_compat',
    'get_aws_accounts',
    'get_aws_regions',
    'get_azure_subscription_id',
    'get_gcp_project_id',
    'get_slack_webhook_url',
    'warn_deprecated',
]