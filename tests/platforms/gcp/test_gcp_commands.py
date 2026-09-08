#!/usr/bin/env python3
"""
Unit tests for GCP commands modernization (BaseCommand, CommandResult, Mock support).
"""

import argparse
import unittest
from unittest.mock import patch
import io
import sys

from ic.core.interfaces import BaseCommand, CommandResult, OutputFormatter
from ic.platforms.gcp.compute.info import GcpComputeInfoCommand
from ic.platforms.gcp.storage.info import GcpStorageInfoCommand
from ic.platforms.gcp.vpc.info import GcpVpcInfoCommand
from ic.platforms.gcp.gke.info import GcpGkeInfoCommand
from ic.platforms.gcp.firewall.info import GcpFirewallInfoCommand
from ic.platforms.gcp.lb.info import GcpLbInfoCommand
from ic.platforms.gcp.sql.info import GcpSqlInfoCommand
from ic.platforms.gcp.run.info import GcpRunInfoCommand
from ic.platforms.gcp.functions.info import GcpFunctionsInfoCommand
from ic.platforms.gcp.billing.info import GcpBillingInfoCommand


class TestGCPCommands(unittest.TestCase):
    """Test suite for all 10 GCP command implementations."""

    COMMANDS = [
        ("compute", GcpComputeInfoCommand),
        ("storage", GcpStorageInfoCommand),
        ("vpc", GcpVpcInfoCommand),
        ("gke", GcpGkeInfoCommand),
        ("firewall", GcpFirewallInfoCommand),
        ("lb", GcpLbInfoCommand),
        ("sql", GcpSqlInfoCommand),
        ("run", GcpRunInfoCommand),
        ("functions", GcpFunctionsInfoCommand),
        ("billing", GcpBillingInfoCommand),
    ]

    def test_base_command_inheritance(self):
        """Verify all GCP commands inherit from BaseCommand."""
        for name, cmd_cls in self.COMMANDS:
            with self.subTest(command=name):
                self.assertTrue(
                    issubclass(cmd_cls, BaseCommand),
                    f"{name} does not subclass BaseCommand"
                )

    def test_add_arguments(self):
        """Verify add_arguments adds standard and service-specific options."""
        for name, cmd_cls in self.COMMANDS:
            with self.subTest(command=name):
                parser = argparse.ArgumentParser()
                cmd_cls.add_arguments(parser)
                actions = {opt for a in parser._actions for opt in a.option_strings}
                self.assertIn("--output", actions)
                self.assertIn("-o", actions)
                self.assertIn("--mock", actions)

    def test_execute_mock_returns_command_result(self):
        """Verify executing with --mock returns valid CommandResult with data."""
        for name, cmd_cls in self.COMMANDS:
            with self.subTest(command=name):
                parser = argparse.ArgumentParser()
                cmd_cls.add_arguments(parser)
                args = parser.parse_args(["--mock"])
                
                cmd = cmd_cls()
                result = cmd.execute(args)
                self.assertIsInstance(result, CommandResult)
                self.assertTrue(result.success)
                self.assertIsInstance(result.data, list)
                self.assertGreater(len(result.data), 0, f"{name} mock data is empty")
                self.assertIsNotNone(result.table_renderer)

    def test_output_formats_with_mock(self):
        """Verify running with json/yaml/tree/table output formats works cleanly."""
        for name, cmd_cls in self.COMMANDS:
            with self.subTest(command=name):
                cmd = cmd_cls()
                parser = argparse.ArgumentParser()
                cmd_cls.add_arguments(parser)

                # Test JSON format
                args_json = parser.parse_args(["--mock", "-o", "json"])
                stdout_capture = io.StringIO()
                with patch("sys.stdout", stdout_capture):
                    cmd.run(args_json)
                json_output = stdout_capture.getvalue()
                self.assertTrue(json_output.strip().startswith("[") or json_output.strip().startswith("{"))

                # Test YAML format
                args_yaml = parser.parse_args(["--mock", "-o", "yaml"])
                stdout_capture = io.StringIO()
                with patch("sys.stdout", stdout_capture):
                    cmd.run(args_yaml)
                yaml_output = stdout_capture.getvalue()
                self.assertGreater(len(yaml_output.strip()), 0)

                # Test Tree format
                args_tree = parser.parse_args(["--mock", "-o", "tree"])
                try:
                    cmd.run(args_tree)
                except Exception as e:
                    self.fail(f"{name} failed on tree format: {e}")


if __name__ == "__main__":
    unittest.main()
