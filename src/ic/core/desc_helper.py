"""
Shared helper utilities for 'desc' (detailed resource describe) commands.
Provides dot-notation key extraction, case-insensitive path lookup,
available key discovery, and unified formatting for table/json/yaml.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, Union
from rich.console import Console
from rich.table import Table
from rich import box
import yaml  # type: ignore
import json


def _normalize_key(key: str) -> str:
    """Normalize a key for case-insensitive matching."""
    return key.strip().lower().replace("_", "").replace("-", "")


def extract_nested_value(obj: Any, path: str) -> Any:
    """
    Extract a value from a nested dict/list structure using dot-notation path.
    Supports case-insensitive key lookup.
    If traversing a list of dictionaries, collects all non-None values into a list.
    
    Examples:
        extract_nested_value({"State": {"Name": "running"}}, "state.name") -> "running"
        extract_nested_value({"Tags": [{"Key": "Name", "Value": "demo"}]}, "Tags.Value") -> ["demo"]
    """
    if obj is None or not path:
        return None

    parts = path.split(".", 1)
    current_key = parts[0].strip()
    remaining_path = parts[1].strip() if len(parts) > 1 else None

    # Handle dictionary traversal
    if isinstance(obj, dict):
        norm_target = _normalize_key(current_key)
        matched_val = None
        found = False

        # Exact match first
        if current_key in obj:
            matched_val = obj[current_key]
            found = True
        else:
            # Case-insensitive & normalized match
            for k, v in obj.items():
                if _normalize_key(k) == norm_target:
                    matched_val = v
                    found = True
                    break

        if not found:
            return None

        if remaining_path is not None:
            return extract_nested_value(matched_val, remaining_path)
        return matched_val

    # Handle list traversal
    elif isinstance(obj, (list, tuple)):
        results = []
        for item in obj:
            res = extract_nested_value(item, path)
            if res is not None:
                if isinstance(res, list):
                    results.extend(res)
                else:
                    results.append(res)
        return results if results else None

    return None


def extract_filtered_attributes(resource_dict: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """
    Extract only specified dot-notation keys from a resource dictionary.
    Returns a dictionary of {key_name: extracted_value}.
    """
    filtered = {}
    for key in keys:
        clean_key = key.strip()
        if clean_key:
            val = extract_nested_value(resource_dict, clean_key)
            filtered[clean_key] = val
    return filtered


def get_available_keys(obj: Any, prefix: str = "", max_depth: int = 6, current_depth: int = 1) -> List[str]:
    """
    Recursively discover all queryable dot-notation keys from a nested dict/list.
    Explores down to max_depth=6 so all sub-keys (e.g., Listeners.Rules.HealthCheck.IntervalTime) are visible.
    """
    if current_depth > max_depth or obj is None:
        return []

    keys: List[str] = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            full_key = f"{prefix}.{k}" if prefix else str(k)
            keys.append(full_key)
            if isinstance(v, dict):
                keys.extend(get_available_keys(v, full_key, max_depth, current_depth + 1))
            elif isinstance(v, (list, tuple)) and v:
                for item in v:
                    if isinstance(item, dict):
                        keys.extend(get_available_keys(item, full_key, max_depth, current_depth + 1))

    return sorted(list(dict.fromkeys(keys)))


def render_keys_list(
    resources: List[Dict[str, Any]],
    resource_type: str = "Resource",
    key_filter: Optional[Union[str, bool]] = None
) -> None:
    """
    Render a clean Rich table listing all available queryable keys from the resources.
    """
    console = Console()
    all_keys: Set[str] = set()
    for res in resources:
        for k in get_available_keys(res, max_depth=6):
            all_keys.add(k)

    sorted_keys = sorted(all_keys)

    # Optional keyword filter (e.g. -l health)
    if key_filter and isinstance(key_filter, str) and key_filter not in ("True", "true"):
        filter_lower = key_filter.lower()
        sorted_keys = [k for k in sorted_keys if filter_lower in k.lower()]

    title = f"📋 Available Queryable Keys for {resource_type} (Total: {len(sorted_keys)})"
    if key_filter and isinstance(key_filter, str) and key_filter not in ("True", "true"):
        title += f" [Filter: '{key_filter}']"

    table = Table(
        title=title,
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False
    )
    table.add_column("Key Path (Dot-notation)", style="bold green", no_wrap=True)
    table.add_column("Example Value", style="white", overflow="fold")

    for k in sorted_keys:
        sample_val = None
        for res in resources:
            val = extract_nested_value(res, k)
            if val is not None:
                if isinstance(val, dict):
                    sample_val = f"[dim]<dict: {len(val)} sub-keys>[/dim]"
                elif isinstance(val, list):
                    if val and isinstance(val[0], dict):
                        sample_val = f"[dim]<list of {len(val)} objects>[/dim]"
                    elif val and all(isinstance(x, (dict, list)) for x in val):
                        sample_val = f"[dim]<list: {len(val)} items>[/dim]"
                    else:
                        unique_vals = list(dict.fromkeys(str(x) for x in val if x is not None))
                        if len(unique_vals) <= 3:
                            sample_val = ", ".join(unique_vals)
                        else:
                            sample_val = ", ".join(unique_vals[:3]) + f" (+{len(unique_vals) - 3} more)"
                else:
                    sample_val = str(val)
                break
        table.add_row(k, sample_val or "-")

    console.print(table)
    if sorted_keys:
        example_key = next((k for k in sorted_keys if "." in k), sorted_keys[0])
        console.print(f"\n[dim]💡 Tip: Use '-k {example_key}' or '-k {example_key},{sorted_keys[0]}' to filter specific attributes.[/dim]\n")


def render_filtered_table(
    resources: List[Dict[str, Any]],
    keys: List[str],
    name_field: str = "Name",
    id_field: str = "Id"
) -> None:
    """
    Render filtered resource attributes as a clean Rich table.
    """
    console = Console()
    clean_keys = [k.strip() for k in keys if k.strip()]

    table = Table(
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=True
    )
    table.add_column("Resource", style="bold green")
    table.add_column("Account", style="white")
    table.add_column("Region", style="cyan")

    for k in clean_keys:
        table.add_column(k, style="yellow", overflow="fold")

    for res in resources:
        res_name = res.get(name_field) or res.get(id_field) or res.get("InstanceName") or res.get("LoadBalancerName") or "-"
        account = res.get("_account_name") or res.get("Account") or "-"
        region = res.get("_region") or res.get("Region") or "-"

        row = [str(res_name), str(account), str(region)]
        for k in clean_keys:
            val = extract_nested_value(res, k)
            if val is None:
                row.append("[dim]-[/dim]")
            elif isinstance(val, (dict, list)):
                row.append(json.dumps(val, ensure_ascii=False))
            else:
                row.append(str(val))

        table.add_row(*row)

    console.print(table)
