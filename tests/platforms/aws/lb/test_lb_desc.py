"""
Unit tests for AWS Load Balancer (ALB/NLB) desc command.
"""

import argparse
from unittest.mock import MagicMock, patch
import pytest

from ic.platforms.aws.lb.desc import AwsLbDescCommand


@pytest.fixture
def mock_aws_lbs():
    return [
        {
            "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-2:123456789012:loadbalancer/app/demo-alb/50dc6c495c0c9188",
            "LoadBalancerName": "demo-alb-1",
            "DNSName": "demo-alb-1-1234567890.ap-northeast-2.elb.amazonaws.com",
            "Type": "application",
            "Scheme": "internet-facing",
            "VpcId": "vpc-0123456789abcdef0",
            "State": {"Code": "active"},
            "Listeners": [
                {
                    "ListenerArn": "arn:aws:elasticloadbalancing:ap-northeast-2:123456789012:listener/app/demo-alb/111",
                    "Port": 80,
                    "Protocol": "HTTP",
                }
            ],
            "TargetGroups": [
                {
                    "TargetGroupArn": "arn:aws:elasticloadbalancing:ap-northeast-2:123456789012:targetgroup/demo-tg/222",
                    "TargetGroupName": "demo-tg-1",
                    "HealthCheckProtocol": "HTTP",
                    "HealthCheckPort": "traffic-port",
                    "HealthCheckPath": "/healthz",
                    "HealthCheckIntervalSeconds": 15,
                    "HealthCheckTimeoutSeconds": 5,
                }
            ],
            "HealthCheck": {
                "TargetGroupName": "demo-tg-1",
                "HealthCheckPath": "/healthz",
                "HealthCheckIntervalSeconds": 15,
                "HealthCheckTimeoutSeconds": 5,
            }
        }
    ]


def test_aws_lb_desc_full(mock_aws_lbs):
    cmd = AwsLbDescCommand()
    args = argparse.Namespace(
        account="demo-account",
        regions="ap-northeast-2",
        name=None,
        keys=None,
        list_keys=False,
        output="yaml"
    )

    with patch("ic.platforms.aws.lb.desc.fetch_raw_lb_one_account_region", return_value=mock_aws_lbs):
        with patch("ic.platforms.aws.lb.desc.get_env_accounts", return_value=["demo-account"]):
            with patch("ic.platforms.aws.lb.desc.get_profiles", return_value={"demo-account": "default"}):
                result = cmd.execute(args)
                assert len(result.data) == 1
                assert result.data[0]["LoadBalancerName"] == "demo-alb-1"


def test_aws_lb_desc_with_keys(mock_aws_lbs):
    cmd = AwsLbDescCommand()
    args = argparse.Namespace(
        account="demo-account",
        regions="ap-northeast-2",
        name=None,
        keys="DNSName,Type,HealthCheck.HealthCheckPath,HealthCheck.HealthCheckIntervalSeconds",
        list_keys=False,
        output="json"
    )

    with patch("ic.platforms.aws.lb.desc.fetch_raw_lb_one_account_region", return_value=mock_aws_lbs):
        with patch("ic.platforms.aws.lb.desc.get_env_accounts", return_value=["demo-account"]):
            with patch("ic.platforms.aws.lb.desc.get_profiles", return_value={"demo-account": "default"}):
                result = cmd.execute(args)
                assert len(result.data) == 1
                item = result.data[0]
                assert item["DNSName"] == "demo-alb-1-1234567890.ap-northeast-2.elb.amazonaws.com"
                assert item["Type"] == "application"
                assert item["HealthCheck.HealthCheckPath"] == "/healthz"
                assert item["HealthCheck.HealthCheckIntervalSeconds"] == 15
