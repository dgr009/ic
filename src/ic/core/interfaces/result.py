"""
Command result container for IC CLI.
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class CommandResult:
    """
    Standard result returned by all IC commands.
    
    Attributes:
        data: List of resource dictionaries collected from cloud providers.
        table_renderer: Platform-specific TUI table rendering function (e.g., print_ec2_table).
        paste_renderer: Optional spreadsheet paste formatting function (e.g., print_paste_format).
        metadata: Optional metadata about the operation (account, region, execution time, etc.).
    """
    data: List[Dict[str, Any]] = field(default_factory=list)
    table_renderer: Optional[Callable[..., Any]] = None
    paste_renderer: Optional[Callable[..., Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return len(self.data) == 0

    def render_table(self, verbose: bool = False) -> None:
        """Call the preserved platform-specific table renderer."""
        if self.table_renderer:
            import inspect
            try:
                sig = inspect.signature(self.table_renderer)
                # Check if it takes varargs
                has_varargs = any(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in sig.parameters.values())
                if has_varargs:
                    self.table_renderer(self.data, verbose)
                    return
                pos_params = [p for p in sig.parameters.values() if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
                if len(pos_params) == 0:
                    self.table_renderer()
                elif len(pos_params) == 1:
                    # Could be (data) or (verbose)
                    param_name = pos_params[0].name.lower()
                    if "verb" in param_name:
                        self.table_renderer(verbose)
                    else:
                        self.table_renderer(self.data)
                else:
                    self.table_renderer(self.data, verbose)
            except Exception:
                # Fallback: try (data, verbose) then (data) then ()
                try:
                    self.table_renderer(self.data, verbose)
                except TypeError:
                    try:
                        self.table_renderer(self.data)
                    except TypeError:
                        self.table_renderer()

    def render_paste(self) -> None:
        """Call the spreadsheet paste renderer if provided."""
        if self.paste_renderer:
            import inspect
            try:
                sig = inspect.signature(self.paste_renderer)
                has_varargs = any(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in sig.parameters.values())
                if has_varargs:
                    self.paste_renderer(self.data)
                    return
                pos_params = [p for p in sig.parameters.values() if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
                if len(pos_params) == 0:
                    self.paste_renderer()
                else:
                    self.paste_renderer(self.data)
            except Exception:
                try:
                    self.paste_renderer(self.data)
                except TypeError:
                    self.paste_renderer()
