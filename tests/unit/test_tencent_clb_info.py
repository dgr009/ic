"""
Unit tests for Tencent CLB info collector, specifically testing Layer 4 (TCP/UDP) and Layer 7 target resolution.
"""

import unittest
from unittest.mock import MagicMock, patch
from ic.platforms.tencent.clb.info import fetch_clb_one_account_region, print_clb_table


class TestTencentCLBInfo(unittest.TestCase):
    """Test Tencent CLB info data fetching and formatting."""

    @patch("tencentcloud.clb.v20180317.clb_client.ClbClient")
    @patch("tencentcloud.vpc.v20170312.vpc_client.VpcClient")
    def test_layer4_tcp_listener_targets(self, mock_vpc_cls, mock_clb_cls):
        """Verify that Layer 4 TCP listeners correctly parse targets attached directly to the listener."""
        mock_clb = MagicMock()
        mock_clb_cls.return_value = mock_clb

        mock_vpc = MagicMock()
        mock_vpc_cls.return_value = mock_vpc
        mock_vpc.DescribeAddresses.return_value.AddressSet = []

        # Mock LoadBalancer
        mock_lb = MagicMock()
        mock_lb.LoadBalancerId = "lb-test1234"
        mock_lb.LoadBalancerName = "sample-tcp-lb"
        mock_lb.LoadBalancerType = "OPEN"
        mock_lb.Status = 1
        mock_lb.LoadBalancerVips = ["203.0.113.10"]
        mock_lb.Domain = "sample-tcp-lb.tencentclb.com"
        mock_lb.VpcId = "vpc-test9999"
        mock_lb.ChargeType = "POSTPAID_BY_HOUR"
        mock_lb.CreateTime = "2026-08-01 12:00:00"

        mock_clb.DescribeLoadBalancers.return_value.LoadBalancerSet = [mock_lb]
        mock_clb.DescribeLoadBalancers.return_value.TotalCount = 1

        # 1. Mock DescribeListeners (TCP listener with no rules)
        mock_l = MagicMock()
        mock_l.Protocol = "TCP"
        mock_l.Port = 8980
        mock_l.Rules = []
        mock_l.HealthCheck = MagicMock()
        mock_l.HealthCheck.HealthSwitch = 1
        mock_l.HealthCheck.HttpCheckPath = None  # TCP health check has no http path

        mock_clb.DescribeListeners.return_value.Listeners = [mock_l]

        # 2. Mock DescribeTargetHealth (Layer 4 target health directly on listener)
        mock_lb_h = MagicMock()
        mock_l_h = MagicMock()
        mock_l_h.Protocol = "TCP"
        mock_l_h.Port = 8980
        mock_l_h.Rules = []

        mock_t_h = MagicMock()
        mock_t_h.TargetId = "ins-sample01"
        mock_t_h.IP = "10.0.1.10"
        mock_t_h.Port = 8980
        mock_t_h.HealthStatus = True
        mock_t_h.HealthStatusDetail = ""

        mock_l_h.Targets = [mock_t_h]
        mock_lb_h.Listeners = [mock_l_h]
        mock_clb.DescribeTargetHealth.return_value.LoadBalancers = [mock_lb_h]

        # 3. Mock DescribeTargets (Layer 4 targets directly on listener)
        mock_l_t = MagicMock()
        mock_l_t.Protocol = "TCP"
        mock_l_t.Port = 8980
        mock_l_t.Rules = []

        mock_target = MagicMock()
        mock_target.InstanceId = "ins-sample01"
        mock_target.InstanceName = "sample-backend-svr"
        mock_target.PrivateIpAddresses = ["10.0.1.10"]
        mock_target.Port = 8980

        mock_l_t.Targets = [mock_target]
        mock_clb.DescribeTargets.return_value.Listeners = [mock_l_t]

        account_info = {"id": "1000000001", "name": "test-account"}
        rows = fetch_clb_one_account_region(account_info, "ap-seoul", name_filter=None)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["lb_name"], "sample-tcp-lb")
        self.assertEqual(row["listener"], "TCP:8980")
        self.assertEqual(row["domain_url"], "-")
        self.assertEqual(row["targets"], "sample-backend-svr (10.0.1.10:8980)")
        self.assertIn("Healthy", row["target_health"])

    def test_print_clb_table_execution(self):
        """Ensure print_clb_table runs cleanly with Layer 4 rows."""
        sample_rows = [
            {
                "account": "test-account",
                "region": "ap-seoul",
                "lb_name": "sample-tcp-lb",
                "lb_id": "lb-test1234",
                "type": "Public",
                "vips": "203.0.113.10",
                "dns": "sample.com",
                "status": "Active",
                "vpc_id": "vpc-test",
                "listener": "TCP:8980",
                "domain_url": "-",
                "hc_path": "-",
                "targets": "sample-backend-svr (10.0.1.10:8980)",
                "target_health": "[bold green]Healthy[/bold green]",
                "charge_type": "POSTPAID_BY_HOUR",
                "create_time": "2026-08-01",
            }
        ]
        # Should execute without throwing errors
        print_clb_table(sample_rows, verbose=False)
        print_clb_table(sample_rows, verbose=True)


    @patch("tencentcloud.clb.v20180317.clb_client.ClbClient")
    @patch("tencentcloud.vpc.v20170312.vpc_client.VpcClient")
    def test_layer7_multi_listener_health(self, mock_vpc_cls, mock_clb_cls):
        """Verify that multiple Layer 7 listeners (HTTP and HTTPS) both resolve target health correctly."""
        mock_clb = MagicMock()
        mock_clb_cls.return_value = mock_clb

        mock_vpc = MagicMock()
        mock_vpc_cls.return_value = mock_vpc
        mock_vpc.DescribeAddresses.return_value.AddressSet = []

        mock_lb = MagicMock()
        mock_lb.LoadBalancerId = "lb-test7777"
        mock_lb.LoadBalancerName = "sample-l7-lb"
        mock_lb.LoadBalancerType = "OPEN"
        mock_lb.Status = 1
        mock_lb.LoadBalancerVips = ["203.0.113.20"]
        mock_lb.Domain = "sample-l7-lb.tencentclb.com"
        mock_lb.VpcId = "vpc-test9999"
        mock_lb.ChargeType = "POSTPAID_BY_HOUR"
        mock_lb.CreateTime = "2026-08-01 12:00:00"

        mock_clb.DescribeLoadBalancers.return_value.LoadBalancerSet = [mock_lb]
        mock_clb.DescribeLoadBalancers.return_value.TotalCount = 1

        # DescribeListeners
        mock_l_http = MagicMock(Protocol="HTTP", Port=80)
        mock_r_http = MagicMock(Domain="*.sample.com", Url="/")
        mock_r_http.HealthCheck.HealthSwitch = 1
        mock_r_http.HealthCheck.HttpCheckPath = "/check"
        mock_l_http.Rules = [mock_r_http]

        mock_l_https = MagicMock(Protocol="HTTPS", Port=443)
        mock_r_https = MagicMock(Domain="*.sample.com", Url="/")
        mock_r_https.HealthCheck.HealthSwitch = 1
        mock_r_https.HealthCheck.HttpCheckPath = "/check"
        mock_l_https.Rules = [mock_r_https]

        mock_clb.DescribeListeners.return_value.Listeners = [mock_l_http, mock_l_https]

        # DescribeTargetHealth
        h_t_http = MagicMock(TargetId="ins-sample01", IP="10.0.1.10", Port=80, HealthStatus=True, HealthStatusDetail="Alive")
        h_r_http = MagicMock(Domain="*.sample.com", Url="/", Targets=[h_t_http])
        h_l_http = MagicMock(Protocol="HTTP", Port=80, Rules=[h_r_http])
        del h_l_http.Targets  # ListenerHealth has no Targets attr

        h_t_https = MagicMock(TargetId="ins-sample01", IP="10.0.1.10", Port=81, HealthStatus=False, HealthStatusDetail="Dead")
        h_r_https = MagicMock(Domain="*.sample.com", Url="/", Targets=[h_t_https])
        h_l_https = MagicMock(Protocol="HTTPS", Port=443, Rules=[h_r_https])
        del h_l_https.Targets

        mock_clb.DescribeTargetHealth.return_value.LoadBalancers = [MagicMock(Listeners=[h_l_http, h_l_https])]

        # DescribeTargets
        t_http = MagicMock(InstanceId="ins-sample01", InstanceName="sample-svr", PrivateIpAddresses=["10.0.1.10"], Port=80)
        r_t_http = MagicMock(Domain="*.sample.com", Url="/", Targets=[t_http])
        l_t_http = MagicMock(Protocol="HTTP", Port=80, Rules=[r_t_http])

        t_https = MagicMock(InstanceId="ins-sample01", InstanceName="sample-svr", PrivateIpAddresses=["10.0.1.10"], Port=81)
        r_t_https = MagicMock(Domain="*.sample.com", Url="/", Targets=[t_https])
        l_t_https = MagicMock(Protocol="HTTPS", Port=443, Rules=[r_t_https])

        mock_clb.DescribeTargets.return_value.Listeners = [l_t_http, l_t_https]

        rows = fetch_clb_one_account_region({"id": "1000000001", "name": "test-account"}, "ap-seoul", name_filter=None)

        self.assertEqual(len(rows), 2)
        row_http = next(r for r in rows if r["listener"] == "HTTP:80")
        row_https = next(r for r in rows if r["listener"] == "HTTPS:443")

        self.assertIn("Healthy", row_http["target_health"])
        self.assertIn("Unhealthy", row_https["target_health"])
        self.assertIn("Dead", row_https["target_health"])


if __name__ == "__main__":
    unittest.main()
