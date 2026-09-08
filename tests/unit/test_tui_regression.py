"""
TUI Zero-Regression tests:
Verify that BaseCommand and OutputFormatter render tables with 100% style and ANSI byte-level equivalence.
"""

import unittest
from rich.console import Console

from ic.core.interfaces import CommandResult, OutputFormatter
from ic.platforms.tencent.clb.info import print_clb_table
from ic.platforms.tencent.cvm.info import print_paste_format as cvm_print_paste, print_cvm_table
from ic.platforms.aws.ec2.info import print_paste_format as ec2_print_paste, print_ec2_table


class TestTUIZeroRegression(unittest.TestCase):
    """Test that OutputFormatter preserves TUI table styles byte-for-byte."""

    def setUp(self):
        self.sample_clb_rows = [
            {
                "account": "test-acct",
                "region": "ap-seoul",
                "lb_name": "sample-lb",
                "lb_id": "lb-12345",
                "type": "[bold green]Public[/bold green]",
                "vips": "203.0.113.10",
                "dns": "sample.clb.com",
                "status": "[bold green]Active[/bold green]",
                "vpc_id": "vpc-123",
                "listener": "TCP:8980",
                "domain_url": "-",
                "hc_path": "-",
                "targets": "sample-svr (10.0.1.10:8980)",
                "target_health": "[bold green]Healthy[/bold green]",
                "charge_type": "POSTPAID",
                "create_time": "2026-08-01",
            }
        ]

        self.sample_cvm_rows = [
            {
                "account": "test-acct",
                "region": "ap-seoul",
                "name": "cvm-instance-1",
                "instance_id": "ins-99999",
                "state": "[bold green]Running[/bold green]",
                "private_ip": "10.0.1.5",
                "public_ip": "203.0.113.5",
                "itype": "S5.MEDIUM4",
                "vcpu": 2,
                "memory": 4,
                "disk": 50,
                "vpc_id": "vpc-123",
                "subnet_id": "subnet-1",
                "sgs": "sg-1",
                "charge_type": "POSTPAID",
                "created_time": "2026-08-01",
            }
        ]

    def test_clb_table_tui_byte_equivalence(self):
        """Direct call vs OutputFormatter call must produce identical ANSI styled text."""
        # 1. Direct call
        c1 = Console(record=True, width=200, color_system="truecolor")
        with unittest.mock.patch("ic.platforms.tencent.clb.info.console", c1):
            print_clb_table(self.sample_clb_rows, verbose=True)
        direct_output = c1.export_text(styles=True)

        # 2. Via OutputFormatter
        c2 = Console(record=True, width=200, color_system="truecolor")
        res = CommandResult(data=self.sample_clb_rows, table_renderer=print_clb_table)
        with unittest.mock.patch("ic.platforms.tencent.clb.info.console", c2):
            OutputFormatter.format_and_print(res, output_format="table", verbose=True)
        formatted_output = c2.export_text(styles=True)

        # 100% byte and style equivalence check
        self.assertEqual(direct_output, formatted_output)

    def test_cvm_table_tui_byte_equivalence(self):
        """CVM direct call vs OutputFormatter must produce identical ANSI styled text."""
        c1 = Console(record=True, width=200, color_system="truecolor")
        with unittest.mock.patch("ic.platforms.tencent.cvm.info.console", c1):
            print_cvm_table(self.sample_cvm_rows, verbose=True)
        direct_output = c1.export_text(styles=True)

        c2 = Console(record=True, width=200, color_system="truecolor")
        res = CommandResult(data=self.sample_cvm_rows, table_renderer=print_cvm_table, paste_renderer=cvm_print_paste)
        with unittest.mock.patch("ic.platforms.tencent.cvm.info.console", c2):
            OutputFormatter.format_and_print(res, output_format="table", verbose=True)
        formatted_output = c2.export_text(styles=True)

        self.assertEqual(direct_output, formatted_output)


if __name__ == "__main__":
    unittest.main()
