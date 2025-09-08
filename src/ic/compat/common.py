"""
Backward compatibility layer for common module imports.

This module provides compatibility shims for the common.* imports that are
used throughout the existing codebase.
"""

import warnings
from typing import Any, Dict, Optional
import sys
from pathlib import Path

# Import the compatibility layer
from . import warn_deprecated, get_logger, compat_config

# Add root directory to path for legacy imports
root_path = Path(__file__).parent.parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))


def log_error(message: str, **kwargs) -> None:
    """
    Backward compatibility function for log_error.
    
    Args:
        message: Error message to log
        **kwargs: Additional keyword arguments (ignored for compatibility)
    """
    warn_deprecated(
        "common.log.log_error",
        "ICLogger.log_error or logger.error",
        "2.0.0"
    )
    logger = get_logger()
    logger.log_error(message)


def log_env_short(env_dict=None, **kwargs) -> None:
    """
    Backward compatibility function for log_env_short.
    
    Args:
        env_dict: Environment variables dictionary (optional)
        **kwargs: Additional keyword arguments (ignored for compatibility)
    """
    warn_deprecated(
        "common.log.log_env_short",
        "ICLogger.log_info_file_only",
        "2.0.0"
    )
    logger = get_logger()
    if env_dict:
        logger.log_info_file_only(f"Environment variables loaded: {len(env_dict)} variables")
    else:
        logger.log_info_file_only("Environment variables loaded")


def log_args_short(args: Any) -> None:
    """
    Backward compatibility function for log_args_short.
    
    Args:
        args: Arguments object to log
    """
    warn_deprecated(
        "common.log.log_args_short", 
        "ICLogger.log_args",
        "2.0.0"
    )
    logger = get_logger()
    logger.log_args(args)


def gather_env_for_command(platform: str, service: str = None, command: str = None) -> Dict[str, Any]:
    """
    Backward compatibility function for gather_env_for_command.
    
    Args:
        platform: Platform name (aws, gcp, azure, etc.)
        service: Service name (optional)
        command: Command name (optional)
        
    Returns:
        Environment configuration dictionary
    """
    warn_deprecated(
        "common.gather_env.gather_env_for_command",
        "ConfigManager.get_config",
        "2.0.0"
    )
    
    # Import the original function for backward compatibility
    try:
        from common.gather_env import gather_env_for_command as original_gather_env
        return original_gather_env(platform, service, command)
    except ImportError:
        # Fallback to config manager
        return compat_config.get_all()


# Legacy log module compatibility
class LogCompat:
    """Compatibility class for common.log module."""
    
    @staticmethod
    def log_error(message: str, **kwargs) -> None:
        """Log error message."""
        log_error(message, **kwargs)
    
    @staticmethod
    def log_env_short(env_dict=None, **kwargs) -> None:
        """Log environment variables."""
        log_env_short(env_dict, **kwargs)
    
    @staticmethod
    def log_args_short(args: Any) -> None:
        """Log command arguments."""
        log_args_short(args)


# Legacy gather_env module compatibility
class GatherEnvCompat:
    """Compatibility class for common.gather_env module."""
    
    @staticmethod
    def gather_env_for_command(platform: str, service: str = None, command: str = None) -> Dict[str, Any]:
        """Gather environment for command."""
        return gather_env_for_command(platform, service, command)


# Create module-like objects for backward compatibility
log_compat = LogCompat()
gather_env_compat = GatherEnvCompat()


# Utility functions for AWS session compatibility
def get_aws_session_compat(account_id: str, region: str = None):
    """
    Backward compatibility function for AWS session creation.
    
    Args:
        account_id: AWS account ID
        region: AWS region
        
    Returns:
        AWS session object
    """
    warn_deprecated(
        "manual AWS session creation",
        "AWSSessionManager.create_session",
        "2.0.0"
    )
    from . import get_aws_session_manager
    
    session_manager = get_aws_session_manager()
    if region is None:
        region = compat_config.get('aws.regions', ['ap-northeast-2'])[0]
    
    return session_manager.create_session(account_id, region)


def get_aws_profiles_compat():
    """
    Backward compatibility function for AWS profiles.
    
    Returns:
        Dictionary of AWS profiles
    """
    warn_deprecated(
        "manual AWS profile parsing",
        "AWSSessionManager.get_profiles",
        "2.0.0"
    )
    from . import get_aws_session_manager
    
    session_manager = get_aws_session_manager()
    return session_manager.get_profiles()


# Azure compatibility functions
def get_azure_client_compat(service_type: str):
    """
    Backward compatibility function for Azure client creation.
    
    Args:
        service_type: Type of Azure service client
        
    Returns:
        Azure client object
    """
    warn_deprecated(
        "manual Azure client creation",
        "Azure service modules with new configuration",
        "2.0.0"
    )
    
    # Import Azure utilities if available
    try:
        from common.azure_utils import get_azure_client
        return get_azure_client(service_type)
    except ImportError:
        raise ImportError("Azure utilities not available. Please install azure dependencies.")


# GCP compatibility functions  
def get_gcp_client_compat(service_type: str):
    """
    Backward compatibility function for GCP client creation.
    
    Args:
        service_type: Type of GCP service client
        
    Returns:
        GCP client object
    """
    warn_deprecated(
        "manual GCP client creation", 
        "GCP service modules with new configuration",
        "2.0.0"
    )
    
    # Import GCP utilities if available
    try:
        from common.gcp_utils import get_gcp_client
        return get_gcp_client(service_type)
    except ImportError:
        raise ImportError("GCP utilities not available. Please install google-cloud dependencies.")


# Export compatibility functions
__all__ = [
    'log_error',
    'log_env_short', 
    'log_args_short',
    'gather_env_for_command',
    'log_compat',
    'gather_env_compat',
    'get_aws_session_compat',
    'get_aws_profiles_compat',
    'get_azure_client_compat',
    'get_gcp_client_compat',
]