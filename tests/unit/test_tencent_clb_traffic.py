"""
Unit tests for Tencent CLB Traffic module.
"""

import unittest
from unittest.mock import MagicMock
from ic.platforms.tencent.clb.traffic import (
    format_bandwidth,
    format_total_data,
    get_monitor_period_and_range,
    fetch_metric_timeseries,
    calculate_stats,
    print_traffic_table,
    resolve_clb_vip,
)


class TestTencentCLBTraffic(unittest.TestCase):
    """Test CLB traffic bandwidth calculations and formatting."""

    def test_format_bandwidth(self):
        self.assertEqual(format_bandwidth(0.0), "0.00 Mbps")
        self.assertEqual(format_bandwidth(0.005), "0.005 Mbps")
        self.assertEqual(format_bandwidth(0.18), "0.18 Mbps")
        self.assertEqual(format_bandwidth(0.62), "0.62 Mbps")
        self.assertEqual(format_bandwidth(12.3456), "12.35 Mbps")
        self.assertEqual(format_bandwidth(None), "-")

    def test_format_total_data(self):
        self.assertEqual(format_total_data(0.5), "512.0 MB")
        self.assertEqual(format_total_data(12.34), "12.34 GB")
        self.assertEqual(format_total_data(2048.0), "2.00 TB")
        self.assertEqual(format_total_data(None), "-")

    def test_resolve_clb_vip(self):
        lb = MagicMock()
        lb.LoadBalancerId = "lb-12345"
        lb.LoadBalancerVips = ["10.0.1.5"]
        lb.LoadBalancerDomain = None
        lb.Domain = None
        eip_map = {"lb-12345": ["203.0.113.20"]}

        ip, display, matched = resolve_clb_vip(lb, eip_map)
        self.assertEqual(ip, "10.0.1.5")
        self.assertEqual(display, "10.0.1.5 / 203.0.113.20")
        self.assertEqual(matched, ["203.0.113.20"])

    def test_get_monitor_period_and_range(self):
        start, end, period_1 = get_monitor_period_and_range(1)
        self.assertEqual(period_1, 300)
        self.assertTrue(len(start) > 0 and len(end) > 0)

        _, _, period_7 = get_monitor_period_and_range(7)
        self.assertEqual(period_7, 3600)

        _, _, period_30 = get_monitor_period_and_range(30)
        self.assertEqual(period_30, 3600)

    def test_fetch_metric_timeseries(self):
        mock_mon_client = MagicMock()
        mock_dp = MagicMock()
        mock_dp.Values = [1.0, 2.0, 3.0, 4.0, 5.0]
        mock_resp = MagicMock()
        mock_resp.DataPoints = [mock_dp]
        mock_mon_client.GetMonitorData.return_value = mock_resp

        series = fetch_metric_timeseries(
            mock_mon_client,
            "QCE/LB_PUBLIC",
            "ClientIntraffic",
            [{"Name": "vip", "Value": "1.2.3.4"}],
            "2026-08-01 00:00:00",
            "2026-08-08 00:00:00",
            3600,
        )

        self.assertEqual(series, [1.0, 2.0, 3.0, 4.0, 5.0])

    def test_calculate_stats(self):
        series = [0.05, 0.18, 0.62]
        stats = calculate_stats(series, 3600)
        self.assertEqual(stats["min"], 0.05)
        self.assertAlmostEqual(stats["avg"], (0.05 + 0.18 + 0.62) / 3.0, places=4)
        self.assertEqual(stats["max"], 0.62)

    def test_print_traffic_table(self):
        rows = [
            {
                "account": "my-account",
                "region": "ap-seoul",
                "lb_name": "live-clb-01",
                "lb_id": "lb-12345",
                "type": "[bold green]Public[/bold green]",
                "vip": "1.2.3.4",
                "status": "[bold green]Active[/bold green]",
                "days": "7d",
                "c_min_in": "0.05 Mbps",
                "c_avg_in": "0.18 Mbps",
                "c_max_in": "0.62 Mbps",
                "c_min_out": "0.10 Mbps",
                "c_avg_out": "1.20 Mbps",
                "c_max_out": "4.50 Mbps",
                "b_min_in": "0.03 Mbps",
                "b_avg_in": "0.08 Mbps",
                "b_max_in": "0.37 Mbps",
                "b_min_out": "0.04 Mbps",
                "b_avg_out": "0.10 Mbps",
                "b_max_out": "0.32 Mbps",
                "total_traffic": "15.40 GB",
            }
        ]
        # Test both default and verbose tables
        print_traffic_table(rows, 7, verbose=False)
        print_traffic_table(rows, 7, verbose=True)

    def test_multi_name_filter(self):
        filter_str = "web,api"
        patterns = [p.strip().lower() for p in filter_str.split(",") if p.strip()]

        lb1_name = "sample-web-service-lb"
        lb2_name = "internal-db-cluster"
        lb3_name = "payment-api-gateway"

        self.assertTrue(any(p in lb1_name.lower() for p in patterns))
        self.assertFalse(any(p in lb2_name.lower() for p in patterns))
        self.assertTrue(any(p in lb3_name.lower() for p in patterns))


if __name__ == "__main__":
    unittest.main()
