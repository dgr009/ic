"""CloudFlare Traffic Analytics service.

This module provides traffic analytics display for CloudFlare zones,
supporting configurable time windows and both Enterprise and Free license types.
"""

import re
import argparse
from datetime import timedelta, datetime, timezone
from typing import Dict, Any

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
    from src.common.log import log_info_non_console as log_info, log_error, log_exception, console
except ImportError:
    from common.log import log_info_non_console as log_info, log_error, log_exception, console

try:
    from src.common.progress_decorator import ManualProgress
except ImportError:
    from common.progress_decorator import ManualProgress


def parse_time_window(time_str: str) -> timedelta:
    """
    Parse time window string to timedelta.
    
    Supported formats:
    - "5m" -> 5 minutes
    - "8h" -> 8 hours  
    - "1d" -> 1 day
    - "24h" -> 24 hours
    
    Args:
        time_str: Time window string in format: <number><unit>
                 where unit is 'm' (minutes), 'h' (hours), or 'd' (days)
    
    Returns:
        timedelta: Parsed time duration
        
    Raises:
        ValueError: If time_str format is invalid
        
    Examples:
        >>> parse_time_window("5m")
        timedelta(minutes=5)
        >>> parse_time_window("8h")
        timedelta(hours=8)
        >>> parse_time_window("1d")
        timedelta(days=1)
    """
    # Support case-insensitive input
    time_str_lower = time_str.lower().strip()
    
    # Match pattern: one or more digits followed by m, h, or d
    match = re.match(r'^(\d+)([mhd])$', time_str_lower)
    
    if not match:
        raise ValueError(
            f"Invalid time format: '{time_str}'. "
            f"Expected format: <number><unit> where unit is 'm' (minutes), 'h' (hours), or 'd' (days). "
            f"Examples: '5m', '8h', '1d'"
        )
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    else:
        # This should never happen due to regex, but included for completeness
        raise ValueError(f"Invalid time unit: '{unit}'. Must be 'm', 'h', or 'd'")


def format_number(num: int) -> str:
    """
    Format large numbers with commas.
    
    Args:
        num: Number to format
        
    Returns:
        Formatted number string (e.g., "1,234,567")
    """
    if num is None:
        return "N/A"
    return f"{num:,}"


def format_bandwidth(bytes_value: int) -> str:
    """
    Format bandwidth in human-readable units.
    
    Args:
        bytes_value: Bandwidth in bytes
        
    Returns:
        Formatted bandwidth string (e.g., "123.4 GB", "5.2 MB")
    """
    if bytes_value is None or bytes_value == 0:
        return "0 B"
    
    # Convert to appropriate unit
    if bytes_value >= 1_000_000_000:  # GB
        return f"{bytes_value / 1_000_000_000:.1f} GB"
    elif bytes_value >= 1_000_000:  # MB
        return f"{bytes_value / 1_000_000:.1f} MB"
    elif bytes_value >= 1_000:  # KB
        return f"{bytes_value / 1_000:.1f} KB"
    else:
        return f"{bytes_value} B"


def format_percentage(ratio: float) -> str:
    """
    Format ratio as percentage.
    
    Args:
        ratio: Ratio value (0.0 to 1.0)
        
    Returns:
        Formatted percentage string (e.g., "87.3%")
    """
    if ratio is None:
        return "N/A"
    return f"{ratio * 100:.1f}%"


def display_analytics_table(
    account_name: str,
    zone_name: str,
    license_type: str,
    analytics: Dict[str, Any],
    time_window_str: str
) -> None:
    """
    Display analytics for a single zone in Rich table format.
    
    Args:
        account_name: Account name
        zone_name: Zone name
        license_type: License type (Enterprise, Free, etc.)
        analytics: Analytics data dictionary
        time_window_str: Time window string for display
    """
    # Create Rich table
    table = Table(
        title=f"[bold cyan]{account_name} - {zone_name}[/bold cyan] [yellow][{license_type}][/yellow]",
        show_lines=True,
        box=box.HORIZONTALS,
        title_justify="left"
    )
    
    # Add columns
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="white", justify="right")
    
    # Add rows with formatted data
    requests = analytics.get("requests", 0)
    bandwidth = analytics.get("bandwidth", 0)
    unique_visitors = analytics.get("unique_visitors")
    cache_hit_ratio = analytics.get("cache_hit_ratio")
    threats_blocked = analytics.get("threats_blocked")
    peak_requests = analytics.get("peak_requests_per_hour")
    
    table.add_row("Total Requests", format_number(requests))
    table.add_row("Bandwidth", format_bandwidth(bandwidth))
    
    # Show N/A or Limited data for unavailable metrics in Free zones
    if license_type == "Free":
        table.add_row("Unique Visitors", "Limited data" if unique_visitors is None else format_number(unique_visitors))
        table.add_row("Cache Hit Ratio", "Limited data" if cache_hit_ratio is None else format_percentage(cache_hit_ratio))
        table.add_row("Threats Blocked", "Limited data" if threats_blocked is None else format_number(threats_blocked))
        table.add_row("Peak Requests/Hour", "Limited data" if peak_requests is None else format_number(peak_requests))
    else:
        table.add_row("Unique Visitors", format_number(unique_visitors) if unique_visitors else "N/A")
        table.add_row("Cache Hit Ratio", format_percentage(cache_hit_ratio) if cache_hit_ratio else "N/A")
        table.add_row("Threats Blocked", format_number(threats_blocked) if threats_blocked else "N/A")
        table.add_row("Peak Requests/Hour", format_number(peak_requests) if peak_requests else "N/A")
    
    # Display table
    console.print()
    console.print(table)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add CLI arguments for traffic analytics command.
    
    Args:
        parser: argparse.ArgumentParser instance
    """
    parser.add_argument(
        '-a', '--account',
        help='Filter by account name (optional, overrides config filter)',
        type=str,
        default=None
    )
    
    parser.add_argument(
        '-z', '--zone',
        help='Filter by zone name (optional, overrides config filter)',
        type=str,
        default=None
    )
    
    parser.add_argument(
        '-t', '--time',
        help='Time window for analytics (default: 8h). Examples: 5m, 8h, 1d, 24h',
        type=str,
        default='8h'
    )


def main(args, config=None) -> Dict[str, Any]:
    """
    Main entry point for traffic analytics command.
    
    Args:
        args: Parsed command-line arguments
        config: Optional configuration (not used, for compatibility)
        
    Returns:
        dict: Result dictionary with success status
    """
    try:
        # Parse time window
        time_window = parse_time_window(args.time)
        log_info(f"Time window: {time_window} ({args.time})")
        
        # Calculate since/until datetime from time window
        until = datetime.now(timezone.utc)
        since = until - time_window
        
        log_info(f"Analytics period: {since.isoformat()} to {until.isoformat()}")
        
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
        log_info("Initializing CloudFlare client for traffic analytics")
        client = CloudFlareClient(cf_config)
        
        # Determine account filter
        if args.account:
            account_filter = [args.account]
            log_info(f"Using CLI account filter: {account_filter}")
        elif cf_config.accounts:
            account_filter = cf_config.accounts
            log_info(f"Using config account filter: {account_filter}")
        else:
            account_filter = None
            log_info("No account filter specified, retrieving all accounts")
        
        # Determine zone filter
        if args.zone:
            zone_filter = [args.zone]
            log_info(f"Using CLI zone filter: {zone_filter}")
        elif cf_config.zones:
            zone_filter = cf_config.zones
            log_info(f"Using config zone filter: {zone_filter}")
        else:
            zone_filter = None
            log_info("No zone filter specified, retrieving all zones")
        
        # Fetch and process data with progress indicator
        with ManualProgress("Processing CloudFlare traffic analytics") as progress:
            # Fetch accounts
            progress.set_description("Fetching CloudFlare accounts")
            accounts = client.get_accounts(name_filter=account_filter)
            log_info(f"Retrieved {len(accounts)} account(s)")
            
            if not accounts:
                console.print("[bold yellow]No CloudFlare accounts found matching the filters.[/bold yellow]")
                return {"success": True, "data": {"zones_processed": 0}}
            
            # Display header
            console.print()
            console.print(f"[bold cyan]Traffic Analytics[/bold cyan] [white](Last {args.time})[/white]")
            
            total_zones = 0
            analytics_data = []
            
            # Process each account
            for account_idx, account in enumerate(accounts, 1):
                account_id = account.get("id", "")
                account_name = account.get("name", "Unknown Account")
                
                progress.set_description(f"Processing account {account_idx}/{len(accounts)}: {account_name}")
                
                # Fetch zones for this account
                zones = client.get_zones(account_id, name_filter=zone_filter)
                log_info(f"Retrieved {len(zones)} zone(s) for account {account_name}")
                
                # Process each zone
                for zone_idx, zone in enumerate(zones, 1):
                    zone_id = zone.get("id", "")
                    zone_name = zone.get("name", "Unknown Zone")
                    
                    progress.set_description(
                        f"Fetching analytics for zone {zone_idx}/{len(zones)}: {zone_name}"
                    )
                    
                    try:
                        # Fetch analytics for this zone
                        analytics = client.get_analytics(zone_id, since, until)
                        license_type = analytics.get("license_type", "Unknown")
                        
                        log_info(
                            f"Retrieved analytics for {zone_name}: "
                            f"{analytics.get('requests', 0)} requests, "
                            f"{analytics.get('bandwidth', 0)} bytes"
                        )
                        
                        # Display analytics table
                        display_analytics_table(
                            account_name,
                            zone_name,
                            license_type,
                            analytics,
                            args.time
                        )
                        
                        analytics_data.append({
                            "account": account_name,
                            "zone": zone_name,
                            "analytics": analytics
                        })
                        
                        total_zones += 1
                        
                    except Exception as e:
                        log_error(f"Failed to fetch analytics for zone {zone_name}: {e}")
                        console.print(
                            f"[bold yellow]⚠️  Failed to fetch analytics for {zone_name}: {str(e)}[/bold yellow]"
                        )
                        # Continue processing other zones
                        continue
            
            progress.set_description(f"Completed processing {total_zones} zone(s)")
        
        # Display summary
        console.print()
        console.print(f"[bold green]✓[/bold green] Retrieved analytics for {total_zones} zone(s)")
        
        log_info(f"Successfully retrieved analytics for {total_zones} zone(s)")
        
        return {
            "success": True,
            "data": {
                "zones_processed": total_zones,
                "time_window": args.time,
                "analytics": analytics_data
            }
        }
        
    except ValueError as e:
        # Time parsing error
        log_error(f"Invalid time format: {e}")
        console.print(f"[bold red]❌ {str(e)}[/bold red]")
        return {"success": False, "error": str(e)}
    
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
    parser = argparse.ArgumentParser(description="CloudFlare Traffic Analytics")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
