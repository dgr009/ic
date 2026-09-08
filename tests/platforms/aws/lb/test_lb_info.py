"""
Unit tests for AWS Load Balancer (ALB/NLB) info command.
"""

import argparse
from unittest.mock import MagicMock, patch
import pytest

from ic.platforms.aws.lb.info import AwsLbInfoCommand, print_lb_table


@pytest.fixture
def mock_aws_lb_info_rows():
    return [
        {
            "account": "123456789012",
            "region": "ap-northeast-2",
            "lb_name": "demo-alb-1",
            "lb_arn": "arn:aws:elasticloadbalancing:ap-northeast-2:123456789012:loadbalancer/app/demo-alb-1/1234",
            "type": "application",
            "scheme": "internet-facing",
            "dns": "demo-alb-1-1234.ap-northeast-2.elb.amazonaws.com",
            "status": "active",
            "vpc_id": "vpc-0123456789abcdef0",
            "create_time": "2026-01-01 12:00",
            "listener": "HTTP:80",
            "target_group": "demo-tg-1",
            "hc_path": "/healthz",
            "targets": "demo-instance (10.0.0.1:80)",
            "health": "[bold green]Healthy[/bold green]"
        }
    ]


def test_aws_lb_info_command_basic(mock_aws_lb_info_rows):
    cmd = AwsLbInfoCommand()
    args = argparse.Namespace(
        account="123456789012",
        regions="ap-northeast-2",
        name=None,
        verbose=False,
        output="table"
    )

    with patch("ic.platforms.aws.lb.info.collect_lb_data", return_value=mock_aws_lb_info_rows):
        result = cmd.execute(args)
        assert len(result.data) == 1
        assert result.data[0]["lb_name"] == "demo-alb-1"
        assert result.data[0]["type"] == "application"


def test_aws_lb_info_command_verbose(mock_aws_lb_info_rows):
    cmd = AwsLbInfoCommand()
    args = argparse.Namespace(
        account="123456789012",
        regions="ap-northeast-2",
        name=None,
        verbose=True,
        output="table"
    )

    with patch("ic.platforms.aws.lb.info.collect_lb_data", return_value=mock_aws_lb_info_rows):
        result = cmd.execute(args)
        assert len(result.data) == 1
        assert result.data[0]["status"] == "active"
        assert result.data[0]["vpc_id"] == "vpc-0123456789abcdef0"


def test_print_lb_table_renders(mock_aws_lb_info_rows):
    # Test rendering both normal and verbose without errors
    print_lb_table(mock_aws_lb_info_rows, verbose=False)
    print_lb_table(mock_aws_lb_info_rows, verbose=True)
