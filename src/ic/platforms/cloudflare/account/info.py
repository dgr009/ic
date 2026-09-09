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

from ic.platforms.cloudflare.client import (
    CloudFlareClient, CloudFlareConfig,
    AuthenticationError, RateLimitError, NetworkError, CloudFlareAPIError
)

# Import config manager
try:
    from ic.config.manager import ConfigManager
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


from ic.core.interfaces import BaseCommand, CommandResult


class CloudflareAccountInfoCommand(BaseCommand):
    """CloudFlare Account information command."""

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument(
            "-a", "--account",
            help="Filter accounts by name (case-insensitive substring match, overrides config)"
        )

    def execute(self, args, config=None) -> CommandResult:
        try:
            config_manager = ConfigManager()
            cf_config = CloudFlareConfig.from_config_manager(config_manager)

            if not cf_config.email or not cf_config.api_token:
                console.print("[bold red]❌ CloudFlare credentials not configured[/bold red]")
                console.print("Please configure email and api_token in ~/.ic/config/secrets.yaml")
                return CommandResult(data={"accounts": [], "count": 0}, success=False, error="Missing credentials")

            log_info("Initializing CloudFlare client for account info")
            client = CloudFlareClient(cf_config)
            account_filter = [args.account] if getattr(args, "account", None) else cf_config.accounts

            with ManualProgress("Processing CloudFlare accounts") as progress:
                progress.set_description("Fetching CloudFlare accounts")
                accounts = client.get_accounts(name_filter=account_filter)
                progress.set_description(f"Retrieved {len(accounts)} account(s)")

            log_info(f"Successfully retrieved {len(accounts)} CloudFlare account(s)")

            return CommandResult(
                data={"accounts": accounts, "count": len(accounts)},
                table_renderer=lambda data, verbose=False: display_accounts_table(accounts),
                success=True,
            )
        except AuthenticationError as e:
            console.print("[bold red]❌ CloudFlare authentication failed[/bold red]")
            return CommandResult(data={"accounts": [], "count": 0}, success=False, error="Authentication failed")
        except RateLimitError as e:
            console.print(f"[bold yellow]⚠️  Rate limit exceeded. Retry after {e.retry_after}s[/bold yellow]")
            return CommandResult(data={"accounts": [], "count": 0}, success=False, error="Rate limit exceeded")
        except NetworkError as e:
            console.print("[bold red]❌ Network error connecting to CloudFlare API[/bold red]")
            return CommandResult(data={"accounts": [], "count": 0}, success=False, error="Network error")
        except Exception as e:
            console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
            return CommandResult(data={"accounts": [], "count": 0}, success=False, error=str(e))



def main(args, config=None):
    return CloudflareAccountInfoCommand().run(args, config)



def add_arguments(parser: argparse.ArgumentParser) -> None:
    CloudflareAccountInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CloudFlare Account Information")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
