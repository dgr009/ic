"""
Unit tests for Core Interfaces (CommandResult, OutputFormatter, BaseCommand).
"""

import argparse
import datetime
import decimal
import json
import os
import unittest
from unittest.mock import MagicMock, patch
import yaml

from ic.core.interfaces.command import BaseCommand
from ic.core.interfaces.formatter import OutputFormatter, safe_serialize
from ic.core.interfaces.result import CommandResult


class CustomModel:
    def __init__(self, name: str, val: int):
        self.name = name
        self.val = val


class DictModel:
    def to_dict(self):
        return {"converted": True, "key": "val"}


class TestCoreInterfaces(unittest.TestCase):
    """Test CommandResult, safe serialization, and OutputFormatter."""

    def test_safe_serialize_types(self):
        # Datetime
        now = datetime.datetime(2026, 9, 7, 12, 0, 0)
        self.assertEqual(safe_serialize(now), "2026-09-07T12:00:00")

        # Decimal
        dec_int = decimal.Decimal("10.0")
        self.assertEqual(safe_serialize(dec_int), 10)
        dec_float = decimal.Decimal("10.5")
        self.assertEqual(safe_serialize(dec_float), 10.5)

        # Custom object with to_dict
        d_obj = DictModel()
        self.assertEqual(safe_serialize(d_obj), {"converted": True, "key": "val"})

        # Custom object with __dict__
        c_obj = CustomModel("test_obj", 42)
        self.assertEqual(safe_serialize(c_obj), {"name": "test_obj", "val": 42})

    def test_output_formatter_json(self):
        sample_data = [
            {
                "name": "srv-1",
                "time": datetime.datetime(2026, 9, 7, 12, 0, 0),
                "ratio": decimal.Decimal("99.9"),
            }
        ]
        result = CommandResult(data=sample_data)

        with patch("sys.stdout.write") as mock_write:
            OutputFormatter.format_and_print(result, output_format="json")
            written = "".join(call.args[0] for call in mock_write.call_args_list)
            parsed = json.loads(written)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0]["name"], "srv-1")
            self.assertEqual(parsed[0]["time"], "2026-09-07T12:00:00")
            self.assertEqual(parsed[0]["ratio"], 99.9)

    def test_output_formatter_yaml(self):
        sample_data = [
            {
                "name": "srv-yaml",
                "count": 5,
            }
        ]
        result = CommandResult(data=sample_data)

        with patch("sys.stdout.write") as mock_write:
            OutputFormatter.format_and_print(result, output_format="yaml")
            written = "".join(call.args[0] for call in mock_write.call_args_list)
            parsed = yaml.safe_load(written)
            self.assertEqual(parsed[0]["name"], "srv-yaml")
            self.assertEqual(parsed[0]["count"], 5)

    def test_output_formatter_table_and_paste_callbacks(self):
        mock_table_renderer = MagicMock()
        mock_paste_renderer = MagicMock()

        sample_data = [{"k": "v"}]
        result = CommandResult(
            data=sample_data,
            table_renderer=mock_table_renderer,
            paste_renderer=mock_paste_renderer,
        )

        # 1. Table format should call table_renderer with verbose=True
        OutputFormatter.format_and_print(result, output_format="table", verbose=True)
        mock_table_renderer.assert_called_once_with(sample_data, True)

        # 2. Paste mode (-p) should call paste_renderer
        OutputFormatter.format_and_print(result, output_format="table", paste_mode=True)
        mock_paste_renderer.assert_called_once_with(sample_data)


class DummyCommand(BaseCommand):
    def execute(self, args, config=None):
        return CommandResult(data=[{"msg": "ok"}], table_renderer=MagicMock())


class TestBaseCommand(unittest.TestCase):
    """Test BaseCommand argument handling and execution."""

    def test_add_common_arguments(self):
        parser = argparse.ArgumentParser()
        DummyCommand.add_arguments(parser)
        args = parser.parse_args(["-o", "json"])
        self.assertEqual(args.output, "json")

    def test_run_suppresses_progress_bars_for_json(self):
        cmd = DummyCommand()
        parser = argparse.ArgumentParser()
        DummyCommand.add_arguments(parser)
        args = parser.parse_args(["-o", "json"])

        os.environ.pop("IC_DISABLE_PROGRESS_BARS", None)
        with patch("sys.stdout.write"):
            cmd.run(args)
        self.assertEqual(os.environ.get("IC_DISABLE_PROGRESS_BARS"), "true")


if __name__ == "__main__":
    unittest.main()
