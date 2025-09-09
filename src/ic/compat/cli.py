"""
Backward compatibility layer for CLI functionality.

This module ensures that existing CLI commands continue to work while
providing migration path to new configuration system.
"""

import os
import sys
import warnings
from typing import Any, Dict, Optional
from pathlib import Path

# Import compatibility layer
from . import warn_deprecated, compat_config, get_logger


def ensure_env_compatibility():
    """
    Ensure environment variable compatibility for CLI commands.
    
    This function checks for .env files and loads them if the new
    configuration system hasn't been set up yet.
    """
    # Check if new config exists
    config_paths = [
        Path("ic.yaml"),
        Path(".ic/config.yaml"), 
        Path("config/config.yaml"),
        Path.home() / ".ic" / "config.yaml",
    ]
    
    has_new_config = any(path.exists() for path in config_paths)
    
    # If no new config exists, ensure .env is loaded
    if not has_new_config:
        env_file = Path('.env')
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv()
                
                # Issue one-time warning about migration
                if not os.getenv('IC_MIGRATION_WARNING_SHOWN'):
                    logger = get_logger()
                    logger.log_info_file_only(
                        "Using .env file for configuration. "
                        "Consider migrating to YAML configuration with 'ic config migrate'"
                    )
                    os.environ['IC_MIGRATION_WARNING_SHOWN'] = '1'
                    
            except ImportError:
                warnings.warn(
                    "python-dotenv not installed. .env file cannot be loaded. "
                    "Install with: pip install python-dotenv",
                    ImportWarning
                )


def wrap_command_function(original_func):
    """
    Decorator to wrap existing command functions with compatibility layer.
    
    Args:
        original_func: Original command function
        
    Returns:
        Wrapped function with compatibility features
    """
    def wrapper(args):
        # Ensure environment compatibility
        ensure_env_compatibility()
        
        # Add compatibility attributes to args if needed
        if not hasattr(args, '_ic_compat_wrapped'):
            args._ic_compat_wrapped = True
            
            # Add configuration access to args
            args.config = compat_config
            
            # Add logger access to args
            args.logger = get_logger()
        
        # Call original function
        return original_func(args)
    
    return wrapper


def get_legacy_env_vars() -> Dict[str, str]:
    """
    Get legacy environment variables that might be needed for compatibility.
    
    Returns:
        Dictionary of legacy environment variables
    """
    legacy_vars = {}
    
    # AWS legacy variables
    aws_vars = [
        'AWS_PROFILE', 'AWS_REGION', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
        'AWS_SESSION_TOKEN', 'AWS_ACCOUNTS', 'AWS_REGIONS', 'AWS_CROSS_ACCOUNT_ROLE'
    ]
    
    # Azure legacy variables
    azure_vars = [
        'AZURE_SUBSCRIPTION_ID', 'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 
        'AZURE_CLIENT_SECRET', 'AZURE_SUBSCRIPTIONS', 'AZURE_LOCATIONS'
    ]
    
    # GCP legacy variables
    gcp_vars = [
        'GCP_PROJECT_ID', 'GCP_PROJECTS', 'GCP_REGIONS', 'GCP_ZONES',
        'GCP_SERVICE_ACCOUNT_KEY_PATH', 'GOOGLE_APPLICATION_CREDENTIALS'
    ]
    
    # CloudFlare legacy variables
    cf_vars = [
        'CLOUDFLARE_EMAIL', 'CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_ACCOUNTS', 'CLOUDFLARE_ZONES'
    ]
    
    # Other legacy variables
    other_vars = [
        'SLACK_WEBHOOK_URL', 'SSH_CONFIG_FILE', 'SSH_KEY_DIR', 'OCI_CONFIG_PATH'
    ]
    
    all_vars = aws_vars + azure_vars + gcp_vars + cf_vars + other_vars
    
    for var in all_vars:
        value = os.getenv(var)
        if value:
            legacy_vars[var] = value
    
    return legacy_vars


def migrate_env_to_config_hint():
    """
    Provide hint about migrating from .env to config files.
    """
    env_file = Path('.env')
    if env_file.exists():
        config_paths = [
            Path("ic.yaml"),
            Path(".ic/config.yaml"),
            Path("config/config.yaml"),
        ]
        
        has_config = any(path.exists() for path in config_paths)
        
        if not has_config:
            logger = get_logger()
            logger.log_info_file_only(
                "💡 Tip: Migrate from .env to YAML configuration for better security and features. "
                "Run 'ic config migrate' to get started."
            )


def check_deprecated_imports():
    """
    Check for deprecated import patterns in the current execution.
    """
    # This is called during CLI startup to check for deprecated usage
    frame = sys._getframe(1)
    
    # Check if we're being imported from old paths
    if frame and frame.f_code:
        filename = frame.f_code.co_filename
        if 'common/log.py' in filename or 'common/gather_env.py' in filename:
            warn_deprecated(
                "importing from common.* modules",
                "importing from ic.compat or using new configuration system",
                "2.0.0"
            )


def setup_cli_compatibility():
    """
    Set up CLI compatibility features.
    
    This function should be called early in CLI initialization to ensure
    backward compatibility features are available.
    """
    # Ensure environment compatibility
    ensure_env_compatibility()
    
    # Check for deprecated imports
    check_deprecated_imports()
    
    # Provide migration hints
    migrate_env_to_config_hint()
    
    # Set up global compatibility state
    if not hasattr(sys.modules[__name__], '_cli_compat_initialized'):
        sys.modules[__name__]._cli_compat_initialized = True
        
        # Log compatibility mode activation
        logger = get_logger()
        logger.log_info_file_only("CLI compatibility layer activated")


def get_command_config(command_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific command with backward compatibility.
    
    Args:
        command_name: Name of the command
        
    Returns:
        Configuration dictionary for the command
    """
    # Get base configuration
    config = compat_config.get_all()
    
    # Add command-specific compatibility mappings
    if command_name.startswith('aws'):
        # Ensure AWS configuration is available
        if not config.get('aws', {}).get('accounts'):
            accounts_env = os.getenv('AWS_ACCOUNTS')
            if accounts_env:
                if 'aws' not in config:
                    config['aws'] = {}
                config['aws']['accounts'] = [acc.strip() for acc in accounts_env.split(',')]
    
    elif command_name.startswith('azure'):
        # Ensure Azure configuration is available
        if not config.get('azure', {}).get('subscription_id'):
            sub_id = os.getenv('AZURE_SUBSCRIPTION_ID')
            if sub_id:
                if 'azure' not in config:
                    config['azure'] = {}
                config['azure']['subscription_id'] = sub_id
    
    elif command_name.startswith('gcp'):
        # Ensure GCP configuration is available
        if not config.get('gcp', {}).get('project_id'):
            project_id = os.getenv('GCP_PROJECT_ID')
            if project_id:
                if 'gcp' not in config:
                    config['gcp'] = {}
                config['gcp']['project_id'] = project_id
    
    return config


def handle_missing_config(service: str) -> None:
    """
    Handle missing configuration for a service with helpful error messages.
    
    Args:
        service: Name of the service (aws, azure, gcp, etc.)
    """
    logger = get_logger()
    
    error_messages = {
        'aws': (
            "AWS configuration not found. Please either:\n"
            "1. Create a YAML config file with AWS settings, or\n"
            "2. Set AWS_ACCOUNTS environment variable, or\n"
            "3. Run 'ic config init' to set up configuration"
        ),
        'azure': (
            "Azure configuration not found. Please either:\n"
            "1. Create a YAML config file with Azure settings, or\n"
            "2. Set AZURE_SUBSCRIPTION_ID environment variable, or\n"
            "3. Run 'ic config init' to set up configuration"
        ),
        'gcp': (
            "GCP configuration not found. Please either:\n"
            "1. Create a YAML config file with GCP settings, or\n"
            "2. Set GCP_PROJECT_ID environment variable, or\n"
            "3. Run 'ic config init' to set up configuration"
        ),
    }
    
    message = error_messages.get(service, f"{service} configuration not found")
    logger.log_error(message)


# Export compatibility functions
__all__ = [
    'ensure_env_compatibility',
    'wrap_command_function',
    'get_legacy_env_vars',
    'migrate_env_to_config_hint',
    'setup_cli_compatibility',
    'get_command_config',
    'handle_missing_config',
]