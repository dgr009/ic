"""
Output formatters for IC CLI.
Supports table (TUI), json, yaml, and paste formats.
"""

import datetime
import decimal
import json
import sys
from typing import Any, Dict, List
import yaml

from .result import CommandResult


def safe_serialize(obj: Any) -> Any:
    """
    Safely serialize objects to JSON/YAML compatible types.
    Handles datetime, Decimal, SDK models, and arbitrary objects without throwing TypeError.
    """
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return obj.dict()
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


class OutputFormatter:
    """
    Formats CommandResult into table (TUI), json, yaml, or paste output.
    """

    SUPPORTED_FORMATS = ("table", "tree", "json", "yaml", "paste")

    @classmethod
    def format_and_print(
        cls,
        result: CommandResult,
        output_format: str = "table",
        verbose: bool = False,
        paste_mode: bool = False,
    ) -> None:
        """
        Render and print the CommandResult based on chosen output format and options.
        
        Args:
            result: The CommandResult instance to display.
            output_format: One of ('table', 'tree', 'json', 'yaml', 'paste'). Default: 'table'.
            verbose: Verbose output flag (-v).
            paste_mode: Paste mode flag (-p). If True and format is 'table', uses paste renderer.
        """
        fmt = (output_format or "table").lower()

        # Handle -p (paste) mode precedence when format is table
        if paste_mode or fmt == "paste":
            if result.paste_renderer:
                result.render_paste()
            else:
                # Fallback to table if no paste renderer
                result.render_table(verbose=verbose)
            return

        if fmt == "json":
            cls.print_json(result.data)
        elif fmt == "yaml":
            cls.print_yaml(result.data)
        elif fmt == "tree":
            result.render_tree()
        else:
            # Default: Table format (100% preserves existing platform TUI)
            result.render_table(verbose=verbose)

    @classmethod
    def print_json(cls, data: List[Dict[str, Any]]) -> None:
        """Output data as clean JSON to stdout."""
        serialized = json.dumps(data, indent=2, ensure_ascii=False, default=safe_serialize)
        sys.stdout.write(serialized + "\n")
        sys.stdout.flush()

    @classmethod
    def print_yaml(cls, data: List[Dict[str, Any]]) -> None:
        """Output data as clean YAML to stdout."""
        # Convert any custom objects via safe_serialize before dumping to yaml
        clean_data = json.loads(json.dumps(data, default=safe_serialize))
        yaml_str = yaml.dump(clean_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        sys.stdout.write(yaml_str)
        sys.stdout.flush()
