"""
Unit tests for Tencent CLB desc command.
"""

import argparse
from unittest.mock import MagicMock, patch
import pytest

from ic.platforms.tencent.clb.desc import TencentClbDescCommand


@pytest.fixture
def mock_clb_resources():
    return [
        {
            "LoadBalancerId": "lb-12345678",
            "LoadBalancerName": "demo-clb-1",
            "LoadBalancerType": "OPEN",
            "Domain": "demo.clb.mycloud.com",
            "VpcId": "vpc-12345",
            "Listeners": [
                {
                    "ListenerId": "lbl-1234",
                    "Protocol": "TCP",
                    "Port": 3306,
                    "HealthCheck": {
                        "HealthSwitch": 1,
                        "IntervalTime": 5,
                        "TimeOut": 2,
                        "HealthNum": 3,
                    },
                }
            ],
            "HealthCheck": {
                "HealthSwitch": 1,
                "IntervalTime": 5,
                "TimeOut": 2,
                "HealthNum": 3,
            }
        }
    ]


def test_tencent_clb_desc_full(mock_clb_resources):
    cmd = TencentClbDescCommand()
    args = argparse.Namespace(
        account="demo-account",
        regions="ap-seoul",
        name=None,
        keys=None,
        list_keys=False,
        output="yaml"
    )

    with patch("ic.platforms.tencent.clb.desc.check_sdk_available"):
        with patch("ic.platforms.tencent.clb.desc.get_accounts", return_value=[{"id": "1001", "name": "demo-account"}]):
            with patch("ic.platforms.tencent.clb.desc.get_tencent_regions", return_value=["ap-seoul"]):
                with patch("ic.platforms.tencent.clb.desc.fetch_raw_clb_one_account_region", return_value=mock_clb_resources):
                    result = cmd.execute(args)
                    assert len(result.data) == 1
                    assert result.data[0]["LoadBalancerId"] == "lb-12345678"


def test_tencent_clb_desc_with_keys(mock_clb_resources):
    cmd = TencentClbDescCommand()
    args = argparse.Namespace(
        account="demo-account",
        regions="ap-seoul",
        name=None,
        keys="HealthCheck.IntervalTime,HealthCheck.TimeOut,Domain",
        list_keys=False,
        output="json"
    )

    with patch("ic.platforms.tencent.clb.desc.check_sdk_available"):
        with patch("ic.platforms.tencent.clb.desc.get_accounts", return_value=[{"id": "1001", "name": "demo-account"}]):
            with patch("ic.platforms.tencent.clb.desc.get_tencent_regions", return_value=["ap-seoul"]):
                with patch("ic.platforms.tencent.clb.desc.fetch_raw_clb_one_account_region", return_value=mock_clb_resources):
                    result = cmd.execute(args)
                    assert len(result.data) == 1
                    item = result.data[0]
                    assert item["HealthCheck.IntervalTime"] == 5
                    assert item["HealthCheck.TimeOut"] == 2
                    assert item["Domain"] == "demo.clb.mycloud.com"
