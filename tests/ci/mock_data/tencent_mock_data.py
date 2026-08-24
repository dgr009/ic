"""
Tencent Cloud Mock Data for Unit and CI Tests
"""

TENCENT_CVM_MOCK_DATA = [
    {
        "InstanceId": "ins-12345678",
        "InstanceName": "tencent-cvm-test-01",
        "InstanceState": "RUNNING",
        "CPU": 2,
        "Memory": 4,
        "Placement": {"Zone": "ap-seoul-1"},
        "PrivateIpAddresses": ["10.0.1.10"],
        "PublicIpAddresses": ["203.0.113.10"]
    }
]

TENCENT_CLB_MOCK_DATA = [
    {
        "LoadBalancerId": "lb-12345678",
        "LoadBalancerName": "tencent-clb-test-01",
        "LoadBalancerType": "OPEN",
        "Domain": "clb-12345678.ap-seoul.clb.tencentclouddns.com",
        "VpcId": "vpc-12345678"
    }
]
