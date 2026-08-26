"""
Unit tests for EC2 and CVM paste format (-p) and column alignment.
"""

import io
import sys
import unittest
from unittest.mock import patch
from ic.platforms.aws.ec2.info import print_paste_format as aws_paste_format, print_ec2_table
from ic.platforms.tencent.cvm.info import print_paste_format as tencent_paste_format, print_cvm_table


class TestEC2CVMPasteFormat(unittest.TestCase):
    """Test paste format and table column consistency between AWS EC2 and Tencent CVM."""

    def setUp(self):
        self.mock_rows = [
            {
                "account": "test-acct-01",
                "region": "ap-seoul",
                "name": "sample-web-01",
                "instance_id": "ins-abcdef12",
                "state": "RUNNING",
                "private_ip": "10.0.1.10",
                "public_ip": "203.0.113.10",
                "itype": "SA5.2XLARGE16",
                "vcpu": "8",
                "memory": "16",
                "disk": "100",
                "vpc": "test-vpc",
                "subnet": "test-subnet",
                "sgs": "web-sg",
                "created_by": "terraform",
                "charge_type": "POSTPAID_BY_HOUR",
                "created_time": "2026-08-01",
            },
            {
                "account": "test-acct-01",
                "region": "ap-seoul",
                "name": "sample-db-01",
                "instance_id": "ins-98765432",
                "state": "RUNNING",
                "private_ip": "10.0.2.20",
                "public_ip": "-",
                "itype": "SA5.LARGE8",
                "vcpu": "4",
                "memory": "8",
                "disk": "200",
                "vpc": "test-vpc",
                "subnet": "test-subnet",
                "sgs": "db-sg",
                "created_by": "terraform",
                "charge_type": "POSTPAID_BY_HOUR",
                "created_time": "2026-08-01",
            },
        ]

    def test_aws_paste_format(self):
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            aws_paste_format(self.mock_rows)

        output = captured_output.getvalue().strip().split("\n")
        self.assertEqual(len(output), 2)
        # sample-db-01 comes first alphabetically
        self.assertEqual(output[0], "sample-db-01,ins-98765432,10.0.2.20,-,SA5.LARGE8,4,8")
        self.assertEqual(output[1], "sample-web-01,ins-abcdef12,10.0.1.10,203.0.113.10,SA5.2XLARGE16,8,16")

    def test_tencent_paste_format(self):
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            tencent_paste_format(self.mock_rows)

        output = captured_output.getvalue().strip().split("\n")
        self.assertEqual(len(output), 2)
        # Format must match AWS exactly: name,instance_id,private_ip,public_ip,itype,vcpu,memory
        self.assertEqual(output[0], "sample-db-01,ins-98765432,10.0.2.20,-,SA5.LARGE8,4,8")
        self.assertEqual(output[1], "sample-web-01,ins-abcdef12,10.0.1.10,203.0.113.10,SA5.2XLARGE16,8,16")

    def test_tables_run_without_error(self):
        # Test normal and verbose tables for both platforms
        print_ec2_table(self.mock_rows, verbose=False)
        print_ec2_table(self.mock_rows, verbose=True)
        print_cvm_table(self.mock_rows, verbose=False)
        print_cvm_table(self.mock_rows, verbose=True)


if __name__ == "__main__":
    unittest.main()
