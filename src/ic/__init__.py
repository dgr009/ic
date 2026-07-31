"""
IC (Infra Resource Management CLI) - A comprehensive tool for managing cloud infrastructure resources.

This package provides CLI tools and libraries for managing AWS, GCP, OCI, CloudFlare, and SSH resources.
"""

__version__ = "1.2.8"
__author__ = "SangYun"
__email__ = "cruiser594@gmail.com"

# Core components
try:
    from .config.security import SecurityManager
    from .config.manager import ConfigManager
    from .core.logging import ICLogger
    from .core.session import AWSSessionManager
except ImportError:
    from ic.config.security import SecurityManager
    from ic.config.manager import ConfigManager
    from ic.core.logging import ICLogger
    from ic.core.session import AWSSessionManager

__all__ = [
    "__version__", 
    "__author__", 
    "__email__",
    "SecurityManager",
    "ConfigManager",
    "ICLogger",
    "AWSSessionManager"
]