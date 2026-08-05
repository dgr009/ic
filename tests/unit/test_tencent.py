"""
Unit tests for Tencent Cloud integration in IC CLI.
"""

import unittest
from unittest.mock import MagicMock, patch

from ic.platforms.tencent.cvm.info import color_state


class TestTencentCVMInfo(unittest.TestCase):
    """Test Tencent CVM helper functions."""

    def test_color_state_running(self):
        result = color_state("RUNNING")
        self.assertIn("RUNNING", result)
        self.assertIn("green", result)

    def test_color_state_stopped(self):
        result = color_state("STOPPED")
        self.assertIn("STOPPED", result)
        self.assertIn("yellow", result)

    def test_color_state_unknown(self):
        result = color_state("UNKNOWN")
        self.assertEqual(result, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
