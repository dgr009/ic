"""
Unit tests for Tencent CVM desc command.
"""

import argparse
from unittest.mock import MagicMock, patch
import pytest

from ic.platforms.tencent.cvm.desc import TencentCvmDescCommand


@pytest.fixture
def mock_cvm_instances():
    return [
        {
            "InstanceId": "ins-12345678",
            "InstanceName": "demo-server-1",
            "InstanceType": "S5.MEDIUM4",
            "ImageId": "img-abcdefgh",
            "InstanceState": "RUNNING",
            "Placement": {"Zone": "ap-seoul-1"},
            "SystemDisk": {"DiskType": "CLOUD_PREMIUM", "DiskSize": 50},
        }
    ]


def test_tencent_cvm_desc_full(mock_cvm_instances):
    cmd = TencentCvmDescCommand()
    args = argparse.Namespace(
        account="demo-account",
        regions="ap-seoul",
        name=None,
        keys=None,
        list_keys=False,
        output="yaml"
    )

    with patch("ic.platforms.tencent.cvm.desc.check_sdk_available"):
        with patch("ic.platforms.tencent.cvm.desc.get_accounts", return_value=[{"id": "1001", "name": "demo-account"}]):
            with patch("ic.platforms.tencent.cvm.desc.get_tencent_regions", return_value=["ap-seoul"]):
                with patch("ic.platforms.tencent.cvm.desc.fetch_raw_cvm_one_account_region", return_value=mock_cvm_instances):
                    result = cmd.execute(args)
                    assert len(result.data) == 1
                    assert result.data[0]["InstanceId"] == "ins-12345678"


def test_tencent_cvm_desc_with_keys(mock_cvm_instances):
    cmd = TencentCvmDescCommand()
    args = argparse.Namespace(
        account="demo-account",
        regions="ap-seoul",
        name=None,
        keys="ImageId,Placement.Zone,SystemDisk.DiskSize",
        list_keys=False,
        output="json"
    )

    with patch("ic.platforms.tencent.cvm.desc.check_sdk_available"):
        with patch("ic.platforms.tencent.cvm.desc.get_accounts", return_value=[{"id": "1001", "name": "demo-account"}]):
            with patch("ic.platforms.tencent.cvm.desc.get_tencent_regions", return_value=["ap-seoul"]):
                with patch("ic.platforms.tencent.cvm.desc.fetch_raw_cvm_one_account_region", return_value=mock_cvm_instances):
                    result = cmd.execute(args)
                    assert len(result.data) == 1
                    item = result.data[0]
                    assert item["ImageId"] == "img-abcdefgh"
                    assert item["Placement.Zone"] == "ap-seoul-1"
                    assert item["SystemDisk.DiskSize"] == 50
