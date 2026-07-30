"""CloudFlare WAF Rules service.

This module provides WAF/firewall security rules display for CloudFlare zones,
with hierarchical tree structure and color-coded rule actions.
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


def get_action_color(action: str, enabled: bool) -> str:
    """
    Get color for rule action.
    
    Args:
        action: Rule action (block, challenge, allow, log, etc.)
        enabled: Whether the rule is enabled
        
    Returns:
        Color string for Rich formatting
    """
    # Base colors for actions
    action_colors = {
        'block': 'red',
        'challenge': 'yellow',
        'js_challenge': 'yellow',
        'managed_challenge': 'yellow',
        'allow': 'green',
        'log': 'blue',
        'bypass': 'cyan'
    }
    
    # Get base color
    base_color = action_colors.get(action.lower(), 'white')
    
    # Use bright colors for enabled rules, dim for disabled
    if enabled:
        return f'bright_{base_color}' if base_color != 'white' else 'white'
    else:
        return f'dim {base_color}'


def get_status_indicator(enabled: bool) -> str:
    """
    Get visual indicator for rule status.
    
    Args:
        enabled: Whether the rule is enabled
        
    Returns:
        Status indicator string with color
    """
    if enabled:
        return '[green]✓[/green]'
    else:
        return '[red]✗[/red]'


def display_waf_rules_tree(
    account_name: str,
    zone_name: str,
    rules: List[Dict[str, Any]]
) -> None:
    """
    Display WAF rules for a zone in Rich tree format.
    
    Args:
        account_name: Account name
        zone_name: Zone name
        rules: List of firewall rule dictionaries
    """
    # Create main tree with account and zone header
    console.print()
    console.print(f"[bold cyan]{account_name} - {zone_name}[/bold cyan]")
    console.print()
    
    if not rules:
        console.print("[dim]No WAF rules configured[/dim]")
        return
    
    # Sort rules by priority (ascending)
    sorted_rules = sorted(rules, key=lambda r: r.get('priority', 999999))
    
    # Create tree for WAF rules
    tree = Tree("[bold]WAF Security Rules[/bold]")
    
    for rule in sorted_rules:
        rule_id = rule.get('id', 'unknown')
        description = rule.get('description', 'No description')
        action = rule.get('action', 'unknown')
        priority = rule.get('priority', 'N/A')
        paused = rule.get('paused', False)
        enabled = not paused
        
        # Get filter expression
        filter_obj = rule.get('filter', {})
        expression = filter_obj.get('expression', 'No expression')
        
        # Create rule node with status indicator and description
        status = get_status_indicator(enabled)
        status_text = "ENABLED" if enabled else "DISABLED"
        action_color = get_action_color(action, enabled)
        
        rule_label = Text()
        rule_label.append(f"{status} ", style="")
        rule_label.append(f"[{status_text}] ", style=action_color)
        rule_label.append(f"{description}", style=action_color)
        rule_label.append(f" (Priority: {priority})", style="dim")
        
        rule_node = tree.add(rule_label)
        
        # Add rule details as child nodes
        rule_node.add(Text(f"Action: {action}", style=action_color))
        
        # Add expression (truncate if too long)
        if len(expression) > 100:
            expression_display = expression[:97] + "..."
        else:
            expression_display = expression
        rule_node.add(Text(f"Expression: {expression_display}", style="dim"))
        
        # Add rule ID
        rule_node.add(Text(f"Rule ID: {rule_id}", style="dim"))
    
    # Display the tree
    console.print(tree)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add CLI arguments for WAF rules command.
    
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
    Main entry point for WAF rules command.
    
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
        log_info("Initializing CloudFlare client for WAF rules")
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
        with ManualProgress("Processing CloudFlare WAF rules") as progress:
            # Fetch accounts
            progress.set_description("Fetching CloudFlare accounts")
            accounts = client.get_accounts(name_filter=account_filter)
            log_info(f"Retrieved {len(accounts)} account(s)")
            
            if not accounts:
                console.print("[bold yellow]No CloudFlare accounts found matching the filters.[/bold yellow]")
                return {"success": True, "data": {"zones_processed": 0}}
            
            # Display header
            console.print()
            console.print("[bold cyan]CloudFlare WAF Security Rules[/bold cyan]")
            
            total_zones = 0
            total_rules = 0
            waf_data = []
            
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
                        f"Fetching WAF rules for zone {zone_idx}/{len(zones)}: {zone_name}"
                    )
                    
                    try:
                        # Fetch firewall rules for this zone
                        rules = client.get_firewall_rules(zone_id)
                        
                        log_info(
                            f"Retrieved {len(rules)} WAF rule(s) for {zone_name}"
                        )
                        
                        # Display WAF rules tree
                        display_waf_rules_tree(
                            account_name,
                            zone_name,
                            rules
                        )
                        
                        waf_data.append({
                            "account": account_name,
                            "zone": zone_name,
                            "rules_count": len(rules),
                            "rules": rules
                        })
                        
                        total_zones += 1
                        total_rules += len(rules)
                        
                    except Exception as e:
                        log_error(f"Failed to fetch WAF rules for zone {zone_name}: {e}")
                        console.print(
                            f"[bold yellow]⚠️  Failed to fetch WAF rules for {zone_name}: {str(e)}[/bold yellow]"
                        )
                        # Continue processing other zones
                        continue
            
            progress.set_description(f"Completed processing {total_zones} zone(s)")
        
        # Display summary
        console.print()
        console.print(
            f"[bold green]✓[/bold green] Retrieved {total_rules} WAF rule(s) "
            f"from {total_zones} zone(s)"
        )
        
        log_info(f"Successfully retrieved {total_rules} WAF rule(s) from {total_zones} zone(s)")
        
        return {
            "success": True,
            "data": {
                "zones_processed": total_zones,
                "total_rules": total_rules,
                "waf_data": waf_data
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
    parser = argparse.ArgumentParser(description="CloudFlare WAF Security Rules")
    add_arguments(parser)
    parsed_args = parser.parse_args()
    main(parsed_args)
