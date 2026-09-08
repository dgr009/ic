"""
Base Command interface for IC CLI.
Provides standard argument handling and output formatting.
"""

import abc
import argparse
import os
from typing import Any, Optional

from .formatter import OutputFormatter
from .result import CommandResult


class BaseCommand(abc.ABC):
    """
    Abstract base class for all IC CLI commands.
    Ensures consistent argument registration, execution, and rendering.
    """

    @classmethod
    def add_common_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add standard arguments like --output to the parser if not already present."""
        # Check if -o / --output already exists
        existing_actions = [opt for action in parser._actions for opt in action.option_strings]
        if "--output" not in existing_actions and "-o" not in existing_actions:
            parser.add_argument(
                "-o", "--output",
                choices=["table", "json", "yaml"],
                default="table",
                help="출력 형식 선택 (table, json, yaml). 기본값: table"
            )

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Override to add command-specific CLI arguments."""
        cls.add_common_arguments(parser)

    @abc.abstractmethod
    def execute(self, args: argparse.Namespace, config: Optional[Any] = None) -> CommandResult:
        """
        Perform data collection and return a CommandResult with data and render callbacks.
        Must be implemented by concrete commands.
        """
        raise NotImplementedError

    def run(self, args: argparse.Namespace, config: Optional[Any] = None) -> None:
        """
        Execute the command and print formatted output.
        Automatically suppresses progress bars for machine-readable formats (JSON/YAML).
        """
        output_format = getattr(args, "output", "table") or "table"
        verbose = getattr(args, "verbose", False) or False
        paste_mode = getattr(args, "paste", False) or False

        # If JSON or YAML output is requested, suppress progress bars so stdout is clean
        if output_format in ("json", "yaml"):
            os.environ["IC_DISABLE_PROGRESS_BARS"] = "true"

        result = self.execute(args, config)
        OutputFormatter.format_and_print(
            result=result,
            output_format=output_format,
            verbose=verbose,
            paste_mode=paste_mode,
        )

    def __call__(self, args: argparse.Namespace, config: Optional[Any] = None) -> None:
        self.run(args, config)
