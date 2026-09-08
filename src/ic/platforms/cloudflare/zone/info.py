#!/usr/bin/env python3
"""
CloudFlare Zone Information Service

Displays CloudFlare zone information including zone ID, name, status, license type, and nameservers.
Supports filtering by account and zone name through CLI arguments or configuration.
Zones are grouped by account for clear organization.
"""

import argparse
from typing import Dict, Any, List

from rich.table import Table
from rich import box

# Import CloudFlare client and config
try:
    from ..client import CloudFlareClient, CloudFlareConfig
    from ..client import AuthenticationError, RateLimitError, NetworkError, CloudFlareAPIError
except ImportError:
    from ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig
    from ic.platforms.cloudflare.client import AuthenticationError, RateLimitError, NetworkError, CloudFlareAPIError

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


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add CLI arguments for zone info command.
    
    Args:
        parser: ArgumentParser instance to add arguments to
    """
    parser.add_argument(
        "-a", "--account",
        help="Filter by account name (case-insensitive substring match, overrides config)"
    )
    parser.add_argument(
        "-z", "--zone",
        help="Filter by zone name (case-insensitive substring match, overrides config)"
    )


def format_nameservers(zone: Dict[str, Any]) -> str:
    """
    Format nameservers for display.
    
    Args:
        zone: Zone dictionary from CloudFlare API
        
    Returns:
        Formatted nameservers string
    """
    nameservers = zone.get("name_servers", [])
    if not nameservers:
        return "N/A"
    
    # Return first nameserver, or comma-separated if multiple
    if len(nameservers) == 1:
        return nameservers[0]
    else:
        return ", ".join(nameservers[:2])  # Show first 2 to keep table readable


def get_license_type(zone: Dict[str, Any]) -> str:
    """
    Get the license type for a zone.
    
    Args:
        zone: Zone dictionary from CloudFlare API
        
    Returns:
        License type string (Enterprise, Pro, Business, Free)
    """
    plan = zone.get("plan", {})
    plan_name = plan.get("name", "").lower()
    
    if "enterprise" in plan_name:
        return "Enterprise"
    elif "pro" in plan_name:
        return "Pro"
    elif "business" in plan_name:
        return "Business"
    else:
        return "Free"


def display_zones_by_account(zones_by_account: Dict[str, Dict[str, Any]]) -> None:
    """
    Display zones grouped by account in Rich table format.
    
    Args:
        zones_by_account: Dictionary mapping account names to their zones and metadata
    """
    if not zones_by_account:
        console.print("[bold yellow]No CloudFlare zones found matching the filters.[/bold yellow]")
        return
    
    total_zones = 0
    
    # Display a table for each account
    for account_name, account_data in zones_by_account.items():
        zones = account_data["zones"]
        
        if not zones:
            continue
        
        total_zones += len(zones)
        
        # Create Rich table for this account
        table = Table(
            title=f"[bold cyan]{account_name}[/bold cyan]",
            show_lines=True,
            box=box.HORIZONTALS,
            title_justify="left"
        )
        
        # Add columns
        table.add_column("Zone ID", style="blue", no_wrap=True)
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("License", style="yellow")
        table.add_column("Nameservers", style="white")
        
        # Add rows
        for zone in zones:
            zone_id = zone.get("id", "")
            name = zone.get("name", "")
            status = zone.get("status", "unknown")
            license_type = get_license_type(zone)
            nameservers = format_nameservers(zone)
            
            # Color code status
            if status == "active":
                status_display = f"[green]{status}[/green]"
            elif status == "pending":
                status_display = f"[yellow]{status}[/yellow]"
            else:
                status_display = f"[red]{status}[/red]"
            
            table.add_row(
                zone_id,
                name,
                status_display,
                license_type,
                nameservers
            )
        
        # Display table
        console.print()
        console.print(table)
    
    console.print()
    
    # Display summary
    account_count = len(zones_by_account)
    console.print(f"[bold green]✓[/bold green] Retrieved {total_zones} zone(s) across {account_count} account(s)")


from ic.core.interfaces import BaseCommand, CommandResult


class CloudflareZoneInfoCommand(BaseCommand):
    """CloudFlare Zone information command."""

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument(
            "-a", "--account",
            help="Filter by account name (case-insensitive substring match, overrides config)"
        )
        parser.add_argument(
            "-z", "--zone",
            help="Filter by zone name (case-insensitive substring match, overrides config)"
        )

    def execute(self, args, config=None) -> CommandResult:
        try:
            config_manager = ConfigManager()
            cf_config = CloudFlareConfig.from_config_manager(config_manager)

            if not cf_config.email or not cf_config.api_token:
                console.print("[bold red]❌ CloudFlare credentials not configured[/bold red]")
                console.print("Please configure email and api_token in ~/.ic/config/secrets.yaml")
                return CommandResult(data={}, success=False, error="Missing credentials")

            client = CloudFlareClient(cf_config)
            account_filter = [args.account] if getattr(args, "account", None) else cf_config.accounts
            zone_filter = [args.zone] if getattr(args, "zone", None) else cf_config.zones

            zones_by_account = {}

            with ManualProgress("Processing CloudFlare zones") as progress:
                progress.set_description("Fetching CloudFlare accounts")
                accounts = client.get_accounts(name_filter=account_filter)

                if not accounts:
                    console.print("[bold yellow]No CloudFlare accounts found matching the filters.[/bold yellow]")
                    return CommandResult(data={}, success=True)

                for idx, account in enumerate(accounts, 1):
                    account_id = account.get("id", "")
                    account_name = account.get("name", "Unknown Account")

                    progress.set_description(f"Processing account {idx}/{len(accounts)}: {account_name}")
                    zones = client.get_zones(account_id, name_filter=zone_filter)

                    if zones:
                        zones_by_account[account_name] = {
                            "account_id": account_id,
                            "zones": zones
                        }

            total_zones = sum(len(acc_info.get("zones", [])) for acc_info in zones_by_account.values())
            return CommandResult(
                data={
                    "zones_by_account": zones_by_account,
                    "total_zones": total_zones,
                    "total_accounts": len(zones_by_account),
                },
                table_renderer=lambda data, verbose=False: display_zones_by_account(
                    data.get("zones_by_account", data) if isinstance(data, dict) else data
                ),
            )

        except AuthenticationError as e:
            console.print("[bold red]❌ CloudFlare authentication failed[/bold red]")
            return CommandResult(data={}, success=False, error="Authentication failed")
        except RateLimitError as e:
            console.print(f"[bold yellow]⚠️  Rate limit exceeded. Retry after {e.retry_after}s[/bold yellow]")
            return CommandResult(data={}, success=False, error="Rate limit exceeded")
        except NetworkError as e:
            console.print("[bold red]❌ Network error connecting to CloudFlare API[/bold red]")
            return CommandResult(data={}, success=False, error="Network error")
        except Exception as e:
            console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
            return CommandResult(data={}, success=False, error=str(e))


def main(args, config=None):
    return CloudflareZoneInfoCommand().run(args, config)



def add_arguments(parser: argparse.ArgumentParser) -> None:
    CloudflareZoneInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CloudFlare Zone Information")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)

