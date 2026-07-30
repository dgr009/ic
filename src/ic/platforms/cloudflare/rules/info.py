"""CloudFlare Page Rules service.

This module provides page rules display for CloudFlare zones,
with hierarchical tree structure and color-coded rule status.
"""

import argparse
from typing import Dict, Any, List

from rich.tree import Tree
from rich.text import Text

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


def get_status_color(status: str) -> str:
    """
    Get color for rule status.
    
    Args:
        status: Rule status (active, disabled, etc.)
        
    Returns:
        Color string for Rich formatting
    """
    status_colors = {
        'active': 'bright_green',
        'disabled': 'dim red',
        'paused': 'dim yellow'
    }
    
    return status_colors.get(status.lower(), 'white')


def get_status_indicator(status: str) -> str:
    """
    Get visual indicator for rule status.
    
    Args:
        status: Rule status (active, disabled, etc.)
        
    Returns:
        Status indicator string with color
    """
    if status.lower() == 'active':
        return '[green]✓[/green]'
    else:
        return '[red]✗[/red]'


def format_action_value(action_id: str, value: Any) -> str:
    """
    Format action value for display.
    
    Args:
        action_id: Action identifier
        value: Action value
        
    Returns:
        Formatted string
    """
    # Handle different action types
    if action_id == 'forwarding_url':
        if isinstance(value, dict):
            url = value.get('url', '')
            status_code = value.get('status_code', '')
            return f"{status_code} to {url}"
        return str(value)
    
    elif action_id in ['cache_level', 'security_level', 'ssl']:
        return str(value)
    
    elif action_id in ['edge_cache_ttl', 'browser_cache_ttl']:
        # Convert seconds to human-readable format
        seconds = int(value) if isinstance(value, (int, str)) else 0
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"
    
    elif isinstance(value, bool):
        return 'on' if value else 'off'
    
    else:
        return str(value)


def display_page_rules_tree(
    account_name: str,
    zone_name: str,
    rules: List[Dict[str, Any]]
) -> None:
    """
    Display page rules for a zone in Rich tree format.
    
    Args:
        account_name: Account name
        zone_name: Zone name
        rules: List of page rule dictionaries
    """
    # Create main tree with account and zone header
    console.print()
    console.print(f"[bold cyan]{account_name} - {zone_name}[/bold cyan]")
    console.print()
    
    if not rules:
        console.print("[dim]No page rules configured[/dim]")
        return
    
    # Sort rules by priority (ascending)
    sorted_rules = sorted(rules, key=lambda r: r.get('priority', 999999))
    
    # Create tree for page rules
    tree = Tree("[bold]Page Rules[/bold]")
    
    for rule in sorted_rules:
        rule_id = rule.get('id', 'unknown')
        priority = rule.get('priority', 'N/A')
        status = rule.get('status', 'unknown')
        
        # Get targets (URL patterns)
        targets = rule.get('targets', [])
        url_pattern = 'No URL pattern'
        if targets:
            target = targets[0]
            url_pattern = target.get('constraint', {}).get('value', 'No URL pattern')
        
        # Get actions
        actions = rule.get('actions', [])
        
        # Create a descriptive label from first action if available
        description = "Page Rule"
        if actions:
            first_action = actions[0]
            action_id = first_action.get('id', '')
            # Create a friendly description
            action_descriptions = {
                'forwarding_url': 'Redirect',
                'always_use_https': 'Force HTTPS',
                'cache_level': 'Cache Everything',
                'edge_cache_ttl': 'Edge Cache TTL',
                'browser_cache_ttl': 'Browser Cache TTL',
                'security_level': 'Security Level',
                'ssl': 'SSL Mode',
                'automatic_https_rewrites': 'Auto HTTPS Rewrites',
                'opportunistic_encryption': 'Opportunistic Encryption',
                'cache_deception_armor': 'Cache Deception Armor',
                'waf': 'WAF',
                'rocket_loader': 'Rocket Loader',
                'mirage': 'Mirage',
                'polish': 'Polish'
            }
            description = action_descriptions.get(action_id, action_id.replace('_', ' ').title())
        
        # Create rule node with status indicator and description
        status_indicator = get_status_indicator(status)
        status_text = status.upper()
        status_color = get_status_color(status)
        
        rule_label = Text()
        rule_label.append(f"{status_indicator} ", style="")
        rule_label.append(f"[{status_text}] ", style=status_color)
        rule_label.append(f"{description}", style=status_color)
        rule_label.append(f" (Priority: {priority})", style="dim")
        
        rule_node = tree.add(rule_label)
        
        # Add URL pattern
        rule_node.add(Text(f"URL Pattern: {url_pattern}", style="cyan"))
        
        # Add actions as a sub-tree
        if actions:
            actions_node = rule_node.add(Text("Actions:", style="bold"))
            
            for action in actions:
                action_id = action.get('id', 'unknown')
                action_value = action.get('value')
                
                # Format action name
                action_name = action_id.replace('_', ' ').title()
                
                # Format action value
                formatted_value = format_action_value(action_id, action_value)
                
                actions_node.add(Text(f"{action_name}: {formatted_value}", style=""))
        
        # Add status
        rule_node.add(Text(f"Status: {status}", style=status_color))
    
    # Display the tree
    console.print(tree)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add CLI arguments for page rules command.
    
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


def main(args, config=None) -> Dict[str, Any]:
    """
    Main entry point for page rules command.
    
    Args:
        args: Parsed command-line arguments
        config: Optional configuration (not used, for compatibility)
        
    Returns:
        dict: Result dictionary with success status
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
        log_info("Initializing CloudFlare client for page rules")
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
        with ManualProgress("Processing CloudFlare page rules") as progress:
            # Fetch accounts
            progress.set_description("Fetching CloudFlare accounts")
            accounts = client.get_accounts(name_filter=account_filter)
            log_info(f"Retrieved {len(accounts)} account(s)")
            
            if not accounts:
                console.print("[bold yellow]No CloudFlare accounts found matching the filters.[/bold yellow]")
                return {"success": True, "data": {"zones_processed": 0}}
            
            # Display header
            console.print()
            console.print("[bold cyan]CloudFlare Page Rules[/bold cyan]")
            
            total_zones = 0
            total_rules = 0
            rules_data = []
            
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
                        f"Fetching page rules for zone {zone_idx}/{len(zones)}: {zone_name}"
                    )
                    
                    try:
                        # Fetch page rules for this zone
                        rules = client.get_page_rules(zone_id)
                        
                        log_info(
                            f"Retrieved {len(rules)} page rule(s) for {zone_name}"
                        )
                        
                        # Display page rules tree
                        display_page_rules_tree(
                            account_name,
                            zone_name,
                            rules
                        )
                        
                        rules_data.append({
                            "account": account_name,
                            "zone": zone_name,
                            "rules_count": len(rules),
                            "rules": rules
                        })
                        
                        total_zones += 1
                        total_rules += len(rules)
                        
                    except Exception as e:
                        log_error(f"Failed to fetch page rules for zone {zone_name}: {e}")
                        console.print(
                            f"[bold yellow]⚠️  Failed to fetch page rules for {zone_name}: {str(e)}[/bold yellow]"
                        )
                        # Continue processing other zones
                        continue
            
            progress.set_description(f"Completed processing {total_zones} zone(s)")
        
        # Display summary
        console.print()
        console.print(
            f"[bold green]✓[/bold green] Retrieved {total_rules} page rule(s) "
            f"from {total_zones} zone(s)"
        )
        
        log_info(f"Successfully retrieved {total_rules} page rule(s) from {total_zones} zone(s)")
        
        return {
            "success": True,
            "data": {
                "zones_processed": total_zones,
                "total_rules": total_rules,
                "rules_data": rules_data
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
    parser = argparse.ArgumentParser(description="CloudFlare Page Rules")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
