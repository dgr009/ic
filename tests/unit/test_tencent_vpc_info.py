"""
Unit tests for Tencent VPC info module.
"""

import unittest
from unittest.mock import MagicMock
from ic.platforms.tencent.vpc.info import resolve_route_target, print_vpc_table


class TestTencentVPCInfo(unittest.TestCase):
    """Test Tencent VPC detailed info and routing target resolution."""

    def test_resolve_route_target_local(self):
        route = MagicMock()
        route.GatewayType = "LOCAL"
        route.GatewayId = "local"
        target = resolve_route_target(route, None, {}, None, "ap-seoul")
        self.assertEqual(target, "local")

    def test_resolve_route_target_igw(self):
        route = MagicMock()
        route.GatewayType = "INTERNET"
        route.GatewayId = "igw-12345"
        target = resolve_route_target(route, None, {}, None, "ap-seoul")
        self.assertEqual(target, "(igw)")

    def test_resolve_route_target_nat(self):
        route = MagicMock()
        route.GatewayType = "NAT"
        route.GatewayId = "nat-12345"

        mock_vpc_client = MagicMock()
        mock_nat = MagicMock()
        mock_nat.NatGatewayName = "my-prod-nat"
        mock_nat.PublicIpAddressSet = ["123.45.67.89"]
        mock_resp = MagicMock()
        mock_resp.NatGatewaySet = [mock_nat]
        mock_vpc_client.DescribeNatGateways.return_value = mock_resp

        target_cache = {}
        target = resolve_route_target(route, mock_vpc_client, target_cache, None, "ap-seoul")
        self.assertEqual(target, "my-prod-nat (nat: 123.45.67.89)")
        # Cache check
        self.assertEqual(target_cache[("NAT", "nat-12345")], "my-prod-nat (nat: 123.45.67.89)")

    def test_resolve_route_target_pcx(self):
        route = MagicMock()
        route.GatewayType = "PEERCONNECTION"
        route.GatewayId = "pcx-abcde"

        mock_vpc_client = MagicMock()
        mock_pcx = MagicMock()
        mock_pcx.PeeringConnectionName = "peering-to-stg"
        mock_resp = MagicMock()
        mock_resp.PeerConnectionSet = [mock_pcx]
        mock_vpc_client.DescribeVpcPeeringConnections.return_value = mock_resp

        target_cache = {}
        target = resolve_route_target(route, mock_vpc_client, target_cache, None, "ap-seoul")
        self.assertEqual(target, "peering-to-stg (pcx)")

    def test_print_vpc_table_no_error(self):
        rows = [
            {
                "account": "my-account",
                "region": "ap-seoul",
                "vpc_name": "vpc-live",
                "vpc_cidr": "10.0.0.0/16",
                "subnet_name": "subnet-public-1",
                "subnet_cidr": "10.0.1.0/24",
                "route_table": "rt-public",
                "route_rule": "0.0.0.0/0          -> (igw)",
            },
            {
                "account": "my-account",
                "region": "ap-seoul",
                "vpc_name": "vpc-live",
                "vpc_cidr": "10.0.0.0/16",
                "subnet_name": "subnet-private-1",
                "subnet_cidr": "10.0.2.0/24",
                "route_table": "rt-private",
                "route_rule": "0.0.0.0/0          -> nat-gw (nat: 1.2.3.4)",
            },
        ]
        # Verify it runs without exceptions
        print_vpc_table(rows)


if __name__ == "__main__":
    unittest.main()
