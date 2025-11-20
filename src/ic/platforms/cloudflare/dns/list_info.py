#!/usr/bin/env python3
"""
CloudFlare DNS Information Service (DEPRECATED)

⚠️  DEPRECATED: This module is deprecated. Use 'info' command instead.

This file provides backward compatibility by redirecting to the new info.py module.
The 'list_info' command will be removed in a future version.
"""

import warnings

# Import from the new info module
try:
    from .info import main, add_arguments
except ImportError:
    try:
        from info import main, add_arguments
    except ImportError:
        # Fallback for development
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from info import main, add_arguments

try:
    from src.common.log import console
except ImportError:
    from common.log import console


# Issue deprecation warning
warnings.warn(
    "The 'list_info' command is deprecated. Use 'info' instead.",
    DeprecationWarning,
    stacklevel=2
)


# Display user-friendly deprecation message
def _show_deprecation_message():
    """Display deprecation message to console."""
    console.print("[bold yellow]⚠️  The 'list_info' command is deprecated. Use 'info' instead.[/bold yellow]")
    console.print("[dim]This command will be removed in a future version.[/dim]")
    console.print("")


# Wrap main to show deprecation message
_original_main = main


def main(args):
    """
    Main entry point with deprecation warning.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Result from info.main()
    """
    _show_deprecation_message()
    return _original_main(args)


# For backward compatibility with direct function calls
def info(args):
    """
    Legacy function name for backward compatibility.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Result from main()
    """
    return main(args)


if __name__ == "__main__":
    """
    Standalone execution for local testing.
    """
    import argparse
    parser = argparse.ArgumentParser(description="CloudFlare DNS Info (Deprecated)")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)