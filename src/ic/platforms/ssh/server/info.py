#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SSH Server Information Service - CLI Integration Module"""

import os
import re
import getpass
import concurrent.futures
import paramiko

try:
    from src.ic.config.manager import ConfigManager
    from src.ic.core.logging import ICLogger
except ImportError:
    try:
        from ic.config.manager import ConfigManager
        from ic.core.logging import ICLogger
    except ImportError:
        # Legacy fallback for development
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        from ic.config.manager import ConfigManager
        from ic.core.logging import ICLogger

from rich.table import Table
from rich.console import Console

try:
    from src.common.progress_decorator import concurrent_progress, ManualProgress
except ImportError:
    try:
        from common.progress_decorator import concurrent_progress, ManualProgress
    except ImportError:
        from ....common.progress_decorator import concurrent_progress, ManualProgress

# Import the main functionality from the original server_info module
try:
    from ..server_info import (
        parse_ssh_config, collect_all_server_info, display_server_info,
        SSH_CONFIG_FILE, SSH_TIMEOUT, MAX_WORKER, SSH_SKIP_PREFIXES
    )
except ImportError:
    # Fallback import for development
    from src.ic.platforms.ssh.server_info import (
        parse_ssh_config, collect_all_server_info, display_server_info,
        SSH_CONFIG_FILE, SSH_TIMEOUT, MAX_WORKER, SSH_SKIP_PREFIXES
    )

console = Console()

def add_arguments(parser):
    """Add SSH server info command arguments to the parser."""
    parser.add_argument(
        '--host', 
        type=str, 
        default='default',
        help='Filter servers by hostname pattern (default: show all servers)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=SSH_TIMEOUT,
        help=f'SSH connection timeout in seconds (default: {SSH_TIMEOUT})'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=MAX_WORKER,
        help=f'Maximum number of concurrent workers (default: {MAX_WORKER})'
    )

def main(args, config=None):
    """Execute SSH server info command."""
    import time
    
    # Initialize configuration
    config_manager = ConfigManager()
    ic_logger = ICLogger(config_manager.load_all_configs())
    logger = ic_logger.get_logger()
    
    logger.info("SSH server info command started")
    
    # Parse SSH configuration
    server_configs = parse_ssh_config()
    if not server_configs:
        logger.error("No server configurations found, exiting")
        console.print("[red]No SSH server configurations found. Please check your SSH config file.[/red]")
        return

    # Apply host filtering if specified
    if hasattr(args, 'host') and args.host and args.host != 'default':
        original_count = len(server_configs)
        server_configs = [
            config for config in server_configs 
            if args.host.lower() in config['servername'].lower()
        ]
        filtered_count = len(server_configs)
        if filtered_count == 0:
            console.print(f"[red]No servers found matching pattern '{args.host}'.[/red]")
            return
        console.print(f"[cyan]Host filter applied:[/cyan] '{args.host}' → {filtered_count}/{original_count} servers selected")

    # Define table headers
    headers = [
        "Server Name",
        "Access IP", 
        "Internal IP",
        "/ Tot",
        "/ %",
        "/app Tot", 
        "/app %",
        "/data Tot",
        "/data %",
        "vCPU",
        "CPU %",
        "Memory",
        "Mem %"
    ]

    total_servers = len(server_configs)
    start_time = time.time()
    
    console.print(f"[cyan]Starting collection from {total_servers} servers...[/cyan]")
    
    try:
        # Collect server information with progress tracking
        results = collect_all_server_info(server_configs)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Count successful vs failed connections
        failed_count = sum(1 for result in results if result[2] == "Connection Fail")
        success_count = total_servers - failed_count
        
        console.print(f"\n[green]✓ Collection completed in {processing_time:.2f}s[/green]")
        console.print(f"[cyan]Results:[/cyan] [green]{success_count} successful[/green], [red]{failed_count} failed[/red]")
        
        # Display results
        display_server_info(results, headers)
        
    except Exception as e:
        logger.exception(f"Error during server information collection: {e}")
        console.print(f"[bold red]Error:[/bold red] Unexpected error occurred during server information collection: {e}")
        return

    logger.info("SSH server info command completed")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SSH Server Information")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)