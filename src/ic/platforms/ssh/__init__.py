"""SSH Platform Module

This module provides SSH-related services for the IC CLI tool.

Available services:
- server: SSH server information and management
- auto: Automatic SSH host discovery and configuration
"""

__version__ = "1.0.0"
__author__ = "IC CLI Team"

# Service exports
from . import server
from . import auto

__all__ = ['server', 'auto']