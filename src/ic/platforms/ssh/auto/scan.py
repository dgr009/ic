#!/usr/bin/env python3
"""SSH Auto Scan Service - CLI Integration Module"""

import os
import socket
import ipaddress
import netifaces
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import paramiko
from paramiko.config import SSHConfig
from tqdm import tqdm

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

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from pathlib import Path
import logging

# Import the main functionality from the original auto_ssh module
try:
    from ..auto_ssh import (
        scan_open_hosts, get_local_ip, get_existing_hosts, is_port_open,
        generate_ip_range, get_hostname_via_ssh, update_ssh_config,
        check_ssh_connections, select_cidr, guess_local_cidr,
        select_ssh_user, select_key_file, prompt_port,
        SSH_MAX_WORKER, PORT_OPEN_TIMEOUT, SSH_TIMEOUT, DEFAULT_KEY_DIR
    )
except ImportError:
    # Fallback import for development
    from src.ic.platforms.ssh.auto_ssh import (
        scan_open_hosts, get_local_ip, get_existing_hosts, is_port_open,
        generate_ip_range, get_hostname_via_ssh, update_ssh_config,
        check_ssh_connections, select_cidr, guess_local_cidr,
        select_ssh_user, select_key_file, prompt_port,
        SSH_MAX_WORKER, PORT_OPEN_TIMEOUT, SSH_TIMEOUT, DEFAULT_KEY_DIR
    )

console = Console()

def add_arguments(parser):
    """Add SSH auto scan command arguments to the parser."""
    parser.add_argument(
        'cidr', 
        nargs='?', 
        help='CIDR range to scan (e.g., 192.168.0.0/24). If not provided, will be auto-detected or prompted.'
    )
    parser.add_argument(
        '--check', 
        action='store_true', 
        help='Check connectivity to all configured SSH hosts'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=SSH_MAX_WORKER,
        help=f'Maximum number of concurrent workers (default: {SSH_MAX_WORKER})'
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=SSH_TIMEOUT,
        help=f'SSH connection timeout in seconds (default: {SSH_TIMEOUT})'
    )
    parser.add_argument(
        '--port-timeout',
        type=float,
        default=PORT_OPEN_TIMEOUT,
        help=f'Port scan timeout in seconds (default: {PORT_OPEN_TIMEOUT})'
    )

def main(args, config=None):
    """Execute SSH auto scan command."""
    # Initialize configuration
    config_manager = ConfigManager()
    ic_logger = ICLogger(config_manager.load_all_configs())
    logger = ic_logger.get_logger()
    
    logger.info("SSH auto scan command started")

    # Check connectivity mode
    if args.check:
        logger.info("Checking SSH host connectivity")
        check_ssh_connections()
        return

    # Determine CIDR to scan
    cidr = args.cidr or select_cidr()
    if not cidr:
        console.print("[red]No CIDR specified or detected.[/red]")
        return

    logger.info(f"Scanning CIDR: {cidr}")
    
    # Get local IP to exclude from results
    local_ip = get_local_ip()
    
    # Scan for open hosts
    console.print(f"[cyan]Scanning {cidr} for SSH hosts...[/cyan]")
    open_hosts = [ip for ip in scan_open_hosts(cidr) if ip != local_ip]

    if not open_hosts:
        console.print("[yellow]No open SSH hosts found.[/yellow]")
        return

    results = []

    console.print("[red]Port Open IP LIST:[/red]")
    for ip in open_hosts:
        console.print(f"[green]{ip}[/green]")

    # Process each open host
    for ip in open_hosts:
        console.rule(f"[bold green]💻 Host Configuration: {ip}[/bold green]")
        console.print("[yellow]Do you want to register this IP?[/yellow]")
        console.print("[cyan]1.[/cyan] Register")
        console.print("[cyan]0.[/cyan] Skip")
        
        confirm = Prompt.ask("Choice", choices=["0", "1"], default="0")
        if confirm == "0":
            continue
            
        # Get host configuration
        hostname = Prompt.ask("Hostname for this host", default=f"host-{ip.replace('.', '-')}")
        user = select_ssh_user()
        port = prompt_port()
        key_path = select_key_file(DEFAULT_KEY_DIR)
        
        if key_path:
            # Update SSH config
            update_ssh_config(ip, hostname, key_path, user, port)
            results.append({"IP": ip, "Hostname": hostname})
            logger.info(f"Registered SSH host: {hostname} ({ip})")

    # Display results
    if results:
        table = Table(title="Registered SSH Hosts")
        table.add_column("IP", style="cyan")
        table.add_column("Hostname", style="green")
        for r in results:
            table.add_row(r["IP"], r["Hostname"])
        console.print(table)
        logger.info(f"Successfully registered {len(results)} SSH hosts")
    else:
        console.print("[yellow]No hosts were registered.[/yellow]")

    logger.info("SSH auto scan command completed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SSH Auto Scanner")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)