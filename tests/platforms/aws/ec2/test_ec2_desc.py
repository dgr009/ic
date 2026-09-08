"""
Unit tests for AWS EC2 desc command.
"""

import argparse
from unittest.mock import MagicMock, patch
import pytest

from ic.platforms.aws.ec2.desc import AwsEc2DescCommand


@pytest.fixture
def mock_ec2_instances():
    return [
        {
            "InstanceId": "i-0123456789abcdef0",
            "InstanceType": "t3.medium",
            "ImageId": "ami-0abcdef1234567890",
            "State": {"Name": "running", "Code": 16},
            "Placement": {"AvailabilityZone": "ap-northeast-2a"},
            "PrivateIpAddress": "10.0.1.100",
            "Tags": [{"Key": "Name", "Value": "demo-web-1"}],
        }
    ]


def test_aws_ec2_desc_full(mock_ec2_instances):
    cmd = AwsEc2DescCommand()
    args = argparse.Namespace(
        account="demo-account",
        regions="ap-northeast-2",
        name=None,
        keys=None,
        list_keys=False,
        output="yaml"
    )

    with patch("ic.platforms.aws.ec2.desc.fetch_raw_ec2_instances", return_value=mock_ec2_instances):
        with patch("ic.platforms.aws.ec2.desc.get_env_accounts", return_value=["demo-account"]):
            with patch("ic.platforms.aws.ec2.desc.get_profiles", return_value={"demo-account": "default"}):
                result = cmd.execute(args)
                assert len(result.data) == 1
                assert result.data[0]["InstanceId"] == "i-0123456789abcdef0"


def test_aws_ec2_desc_with_keys(mock_ec2_instances):
    cmd = AwsEc2DescCommand()
    args = argparse.Namespace(
        account="demo-account",
        regions="ap-northeast-2",
        name=None,
        keys="ImageId,State.Name,Placement.AvailabilityZone",
        list_keys=False,
        output="json"
    )

    with patch("ic.platforms.aws.ec2.desc.fetch_raw_ec2_instances", return_value=mock_ec2_instances):
        with patch("ic.platforms.aws.ec2.desc.get_env_accounts", return_value=["demo-account"]):
            with patch("ic.platforms.aws.ec2.desc.get_profiles", return_value={"demo-account": "default"}):
                result = cmd.execute(args)
                assert len(result.data) == 1
                item = result.data[0]
                assert item["ImageId"] == "ami-0abcdef1234567890"
                assert item["State.Name"] == "running"
                assert item["Placement.AvailabilityZone"] == "ap-northeast-2a"
