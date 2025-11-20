#!/usr/bin/env python3
"""
CloudFlare Account Information Service

Displays CloudFlare account information including account ID, name, type, and settings.
Supports filtering by account name through CLI arguments or configuration.
"""

import argparse
from typing import Dict, Any, Optional

from rich.table import Table
from rich import box

# Import CloudFlare client and config
try:
    from ..client import CloudFlareClient, CloudFlareConfig
    from ..client import AuthenticationError, RateLimitError, NetworkError, CloudFlareAPIError
except ImportError:
    from src.ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig
    from src.ic.platforms.cloudflare.client import AuthenticationError, RateLimitError, NetworkError, CloudFlareAPIError

# Import config manager
try:
    from src.ic.config.manager import ConfigManager
except ImportError:
    try:
        from ic.config.manager import ConfigManager
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
        from ic.config.manager import ConfigManager

# Import common utilities
try:
    from src.common.log import log_info, log_error, log_exception, console
except ImportError:
    from common.log import log_info, log_error, log_exception, console

try:
    from src.common.progress_decorator import ManualProgress
except ImportError:
    from common.progress_decorator import ManualProgress


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add CLI arguments for account info command.
    
    Args:
        parser: ArgumentParser instance to add arguments to
    """
    parser.add_argument(
        "-a", "--account",
        help="Filter accounts by name (case-insensitive substring match, overrides config)"
    )


def format_account_settings(account: Dict[str, Any]) -> str:
    """
    Format account settings for display.
    
    Args:
        account: Account dictionary from CloudFlare API
        
    Returns:
        Formatted settings string
    """
    settings = account.get("settings", {})
    
    # Check for 2FA enforcement
    enforce_twofactor = settings.get("enforce_twofactor", False)
    twofactor_status = "✓" if enforce_twofactor else "✗"
    
    return f"2FA: {twofactor_status}"


def display_accounts_table(accounts: list) -> None:
    """
    Display accounts in a Rich table format.
    
    Args:
        accounts: List of account dictionaries
    """
    if not accounts:
        console.print("[bold yellow]No CloudFlare accounts found matching the filters.[/bold yellow]")
        return
    
    # Create Rich table
    table = Table(
        title="[bold cyan]CloudFlare Accounts[/bold cyan]",
        show_lines=True,
        box=box.HORIZONTALS,
        title_justify="left"
    )
    
    # Add columns
    table.add_column("Account ID", style="blue", no_wrap=True)
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Settings", style="white")
    
    # Add rows
    for account in accounts:
        account_id = account.get("id", "")
        name = account.get("name", "")
        account_type = account.get("type", "standard")
        settings = format_account_settings(account)
        
        table.add_row(
            account_id,
            name,
            account_type.capitalize(),
            settings
        )
    
    # Display table
    console.print()
    console.print(table)
    console.print()
    
    # Display summary
    console.print(f"[bold green]✓[/bold green] Retrieved {len(accounts)} account(s)")


def main(args, config=None) -> Dict[str, Any]:
    """
    Main entry point for CloudFlare account info command.
    
    Args:
        args: Parsed command-line arguments
        config: Optional configuration (not used, for compatibility)
        
    Returns:
        Result dictionary with success status and data or error message
    """
    try:
        # Load configuration
        config_manager = ConfigManager()
        cf_config = CloudFlareConfig.from_config_manager(config_manager)
        
        # Validate credentials
        if not cf_config.email or not cf_config.api_token:
            console.print("[bold red]❌ CloudFlare credentials not configured[/bold red]")
            console.print("Please configure email and api_token in ~/.ic/config/secrets.yaml")
            log_error("CloudFlare credentials not configured")
            return {"success": False, "error": "Missing credentials"}
        
        # Initialize CloudFlare client
        log_info("Initializing CloudFlare client for account info")
        client = CloudFlareClient(cf_config)
        
        # Determine account filter
        # CLI argument takes precedence over configuration
        if args.account:
            account_filter = [args.account]
            log_info(f"Using CLI account filter: {account_filter}")
        elif cf_config.accounts:
            account_filter = cf_config.accounts
            log_info(f"Using config account filter: {account_filter}")
        else:
            account_filter = None
            log_info("No account filter specified, retrieving all accounts")
        
        # Fetch accounts with progress indicator
        with ManualProgress("Processing CloudFlare accounts") as progress:
            progress.set_description("Fetching CloudFlare accounts")
            accounts = client.get_accounts(name_filter=account_filter)
            
            progress.set_description(f"Retrieved {len(accounts)} account(s)")
        
        # Display results
        display_accounts_table(accounts)
        
        # Log summary
        log_info(f"Successfully retrieved {len(accounts)} CloudFlare account(s)")
        
        return {
            "success": True,
            "data": {
                "accounts": accounts,
                "count": len(accounts)
            }
        }
        
    except AuthenticationError as e:
        log_error(f"Authentication failed: {e}")
        console.print("[bold red]❌ CloudFlare authentication failed[/bold red]")
        console.print("Please check your credentials in ~/.ic/config/secrets.yaml")
        return {"success": False, "error": "Authentication failed"}
    
    except RateLimitError as e:
        log_error(f"Rate limit exceeded: {e}")
        console.print(f"[bold yellow]⚠️  Rate limit exceeded. Retry after {e.retry_after}s[/bold yellow]")
        return {"success": False, "error": "Rate limit exceeded"}
    
    except NetworkError as e:
        log_error(f"Network error: {e}")
        console.print("[bold red]❌ Network error connecting to CloudFlare API[/bold red]")
        console.print("Please check your internet connection.")
        return {"success": False, "error": "Network error"}
    
    except CloudFlareAPIError as e:
        log_error(f"CloudFlare API error: {e}")
        console.print(f"[bold red]❌ CloudFlare API error: {str(e)}[/bold red]")
        return {"success": False, "error": str(e)}
    
    except Exception as e:
        log_exception(e)
        console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    """
    Standalone execution for local testing.
    """
    parser = argparse.ArgumentParser(description="CloudFlare Account Information")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
