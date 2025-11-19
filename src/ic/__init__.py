"""
IC (Infra Resource Management CLI) - A comprehensive tool for managing cloud infrastructure resources.

This package provides CLI tools and libraries for managing AWS, Azure, GCP, OCI, and CloudFlare resources.
"""

__version__ = "1.2.2"
__author__ = "SangYun"
__email__ = "cruiser594@gmail.com"

# Core components
try:
    from .core.mcp_manager import MCPManager, MCPQueryResult, create_default_mcp_config
    from .config.security import SecurityManager
    from .config.manager import ConfigManager
    from .core.logging import ICLogger
    from .core.session import AWSSessionManager
except ImportError:
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