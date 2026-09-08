"""
Unit tests for ic.core.desc_helper.
"""

import pytest
from ic.core.desc_helper import (
    extract_nested_value,
    extract_filtered_attributes,
    get_available_keys,
)


def test_extract_nested_value_basic():
    data = {
        "InstanceId": "i-12345678",
        "InstanceType": "t3.medium",
        "State": {"Name": "running", "Code": 16},
    }
    assert extract_nested_value(data, "InstanceId") == "i-12345678"
    assert extract_nested_value(data, "State.Name") == "running"
    assert extract_nested_value(data, "State.Code") == 16
    assert extract_nested_value(data, "NonExistent") is None


def test_extract_nested_value_case_insensitive():
    data = {
        "HealthCheck": {
            "IntervalTime": 5,
            "TimeOut": 2,
            "HttpCheckPath": "/health",
        },
        "ImageId": "ami-01234567",
    }
    # Lowercase & mixed case lookup
    assert extract_nested_value(data, "healthcheck.intervaltime") == 5
    assert extract_nested_value(data, "HEALTHCHECK.TIMEOUT") == 2
    assert extract_nested_value(data, "imageid") == "ami-01234567"
    assert extract_nested_value(data, "image_id") == "ami-01234567"


def test_extract_nested_value_list_traversal():
    data = {
        "NetworkInterfaces": [
            {"Attachment": {"Status": "attached"}, "PrivateIpAddress": "10.0.1.10"},
            {"Attachment": {"Status": "detached"}, "PrivateIpAddress": "10.0.1.20"},
        ],
        "Tags": [
            {"Key": "Name", "Value": "demo-server"},
            {"Key": "Env", "Value": "prod"},
        ]
    }
    assert extract_nested_value(data, "NetworkInterfaces.PrivateIpAddress") == ["10.0.1.10", "10.0.1.20"]
    assert extract_nested_value(data, "tags.value") == ["demo-server", "prod"]


def test_extract_filtered_attributes():
    data = {
        "InstanceId": "i-9999",
        "Placement": {"Zone": "ap-seoul-1"},
        "Cpu": 4,
    }
    filtered = extract_filtered_attributes(data, ["InstanceId", "placement.zone", "Missing"])
    assert filtered == {
        "InstanceId": "i-9999",
        "placement.zone": "ap-seoul-1",
        "Missing": None,
    }


def test_get_available_keys():
    data = {
        "ImageId": "ami-123",
        "State": {"Name": "running", "Code": 16},
        "Disks": [{"DiskSize": 50, "DiskType": "CLOUD_SSD"}],
    }
    keys = get_available_keys(data, max_depth=3)
    assert "ImageId" in keys
    assert "State" in keys
    assert "State.Name" in keys
    assert "State.Code" in keys
    assert "Disks" in keys
    assert "Disks.DiskSize" in keys
