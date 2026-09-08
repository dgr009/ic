#!/usr/bin/env python3
"""
CloudFlare DNS Information Service

Displays DNS records for CloudFlare zones with filtering support.
Refactored to use CloudFlareClient for consistent API interaction.
"""

import argparse
from datetime import datetime
from typing import List, Dict, Any

try:
    from ic.config.manager import ConfigManager
    from ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig
    from ic.platforms.cloudflare.client import AuthenticationError, RateLimitError, NetworkError
except ImportError:
    try:
        from ic.config.manager import ConfigManager
        from ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig
        from ic.platforms.cloudflare.client import AuthenticationError, RateLimitError, NetworkError
    except ImportError:
        # Legacy fallback for development
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        from ic.config.manager import ConfigManager
        from ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig
        from ic.platforms.cloudflare.client import AuthenticationError, RateLimitError, NetworkError

from rich.table import Table
from rich import box

# Common modules
try:
    from src.common.log import log_error, log_info, log_exception, console
except ImportError:
    from common.log import log_error, log_info, log_exception, console

try:
    from src.common.progress_decorator import ManualProgress
except ImportError:
    from common.progress_decorator import ManualProgress


def add_arguments(parser: argparse.ArgumentParser):
    """
    Add CLI arguments for DNS info command.
    
    Args:
        parser: ArgumentParser instance to add arguments to
    """
    parser.add_argument(
        "-a", "--account",
        help="Filter accounts by name (case-insensitive substring)"
    )
    parser.add_argument(
        "-z", "--zone",
        help="Filter zones by name (case-insensitive substring)"
    )


def type_color(record_type: str) -> str:
    """
    Get color tag for DNS record type.
    
    Args:
        record_type: DNS record type (A, CNAME, etc.)
        
    Returns:
        Color name for Rich formatting
    """
    colors = {
        "A": "cyan",
        "CNAME": "green",
        "MX": "yellow",
        "TXT": "magenta",
        "AAAA": "blue",
        "NS": "bright_black",
        "SRV": "bright_magenta",
    }
    return colors.get(record_type, "white")


def proxy_color(proxied: bool) -> str:
    """
    Get color tag for proxy status.
    
    Args:
        proxied: Whether the record is proxied through CloudFlare
        
    Returns:
        Color name for Rich formatting
    """
    return "bright_green" if proxied else "bright_red"


def simplify_name(name: str, zone_name: str) -> str:
    """
    Simplify DNS record name by removing zone suffix.
    
    Args:
        name: Full DNS record name
        zone_name: Zone name to remove from the end
        
    Returns:
        Simplified name without zone suffix
    """
    if name == zone_name:
        return name
    if name.endswith(f".{zone_name}"):
        return name.replace(f".{zone_name}", "")
    return name


def format_time(time_str: str) -> str:
    """
    Format ISO timestamp to readable format.
    
    Args:
        time_str: ISO 8601 timestamp string
        
    Returns:
        Formatted time string (YYYY-MM-DD HH:MM)
    """
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return time_str


def display_dns_table(account_name: str, zone_name: str, records: List[Dict[str, Any]]):
    """
    Display DNS records in a Rich table.
    
    Args:
        account_name: CloudFlare account name
        zone_name: Zone name
        records: List of DNS record dictionaries
    """
    table = Table(
        title=f"[bold blue]{account_name}[/bold blue] - [bold yellow]{zone_name}[/bold yellow]",
        show_lines=True,
        box=box.HORIZONTALS,
        title_justify="left"
    )
    
    columns = ["Type", "Name", "Content", "Priority", "Proxy", "TTL", "Created", "Modified", "Comment"]
    for col in columns:
        table.add_column(col, style="white")

    for record in records:
        rtype = record.get("type", "")
        proxied = record.get("proxied", False)
        priority = record.get("priority", "-")
        comment = record.get("comment", "")

        table.add_row(
            f"[{type_color(rtype)}]{rtype}[/{type_color(rtype)}]",
            f"{simplify_name(record.get('name', ''), zone_name)}",
            f"[blue]{record.get('content', '')}[/blue]",
            str(priority),
            f"[{proxy_color(proxied)}]{proxied}[/{proxy_color(proxied)}]",
            str(record.get("ttl", "")),
            f"[bright_black]{format_time(record.get('created_on', ''))}[/bright_black]",
            f"[bright_black]{format_time(record.get('modified_on', ''))}[/bright_black]",
            comment
        )

    console.print(table)
    console.print("")  # Empty line for spacing


from ic.core.interfaces import BaseCommand, CommandResult


class CloudflareDnsInfoCommand(BaseCommand):
    """CloudFlare DNS information command."""

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser):
        cls.add_common_arguments(parser)
        parser.add_argument(
            "-a", "--account",
            help="Filter accounts by name (case-insensitive substring)"
        )
        parser.add_argument(
            "-z", "--zone",
            help="Filter zones by name (case-insensitive substring)"
        )

    def execute(self, args, config=None) -> CommandResult:
        try:
            config_manager = ConfigManager()
            cf_config = CloudFlareConfig.from_config_manager(config_manager)

            if not cf_config.email or not cf_config.api_token:
                console.print("[bold red]❌ CloudFlare credentials not configured[/bold red]")
                console.print("Please configure email and api_token in ~/.ic/config/secrets.yaml")
                return CommandResult(data=[], success=False, error="Missing credentials")

            client = CloudFlareClient(cf_config)
            account_filter = [args.account] if getattr(args, "account", None) else cf_config.accounts
            zone_filter = [args.zone] if getattr(args, "zone", None) else cf_config.zones

            with ManualProgress("Processing CloudFlare DNS information") as progress:
                progress.set_description("Fetching CloudFlare accounts")
                accounts = client.get_accounts(name_filter=account_filter if account_filter else None)

                if not accounts:
                    console.print("[bold red]No CloudFlare accounts found.[/bold red]")
                    return CommandResult(data=[], success=True)

                progress.set_description(f"Processing {len(accounts)} CloudFlare accounts")
                all_zone_data = []

                for acct_idx, acct in enumerate(accounts, 1):
                    account_name = acct.get("name", "")
                    account_id = acct.get("id", "")

                    progress.set_description(f"Processing account {acct_idx}/{len(accounts)}: {account_name}")
                    zones = client.get_zones(account_id, name_filter=zone_filter if zone_filter else None)

                    for zone_idx, zone in enumerate(zones, 1):
                        zone_name = zone.get("name", "")
                        zone_id = zone.get("id", "")

                        progress.set_description(
                            f"Processing zone {zone_idx}/{len(zones)} in {account_name}: {zone_name}"
                        )
                        records = client.get_dns_records(zone_id)
                        all_zone_data.append({
                            "account": account_name,
                            "zone": zone_name,
                            "records": records,
                        })

            def render_tables(data, verbose=False):
                zone_list = data.get("details", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                for item in zone_list:
                    display_dns_table(item["account"], item["zone"], item.get("records", []))

            return CommandResult(
                data={
                    "accounts": len(accounts),
                    "zones": len(all_zone_data),
                    "details": all_zone_data,
                },
                table_renderer=render_tables,
                success=True,
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
    return CloudflareDnsInfoCommand().run(args, config)



def add_arguments(parser: argparse.ArgumentParser):
    CloudflareDnsInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CloudFlare DNS Info")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)

