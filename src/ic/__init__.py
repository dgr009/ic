"""
IC (Infra Resource Management CLI) - A comprehensive tool for managing cloud infrastructure resources.

This package provides CLI tools and libraries for managing AWS, Azure, GCP, OCI, and CloudFlare resources.
"""

__version__ = "2.0.0"
__author__ = "SangYun"
__email__ = "cruiser594@gmail.com"

# Core components
from ic.core.mcp_manager import MCPManager, MCPQueryResult, create_default_mcp_config
from ic.config.security import SecurityManager
from ic.config.manager import ConfigManager
from ic.core.logging import ICLogger
from ic.core.session import AWSSessionManager

__all__ = [
    "__version__", 
    "__author__", 
    "__email__",
    "MCPManager",
    "MCPQueryResult", 
    "create_default_mcp_config",
    "SecurityManager",
    "ConfigManager",
    "ICLogger",
    "AWSSessionManager"
]