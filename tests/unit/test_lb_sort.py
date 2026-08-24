"""
Unit tests for Load Balancer target sorting in AWS LB and Tencent CLB.
"""

import unittest


class TestLBSort(unittest.TestCase):
    """Test target sorting logic for AWS LB and Tencent CLB."""

    def test_aws_lb_target_sorting(self):
        rows = [
            {
                "account": "acc1",
                "region": "ap-northeast-2",
                "lb_name": "my-alb",
                "listener": "HTTPS:443",
                "target_group": "tg-01",
                "targets": "was-live-02 (10.0.1.2:80)",
            },
            {
                "account": "acc1",
                "region": "ap-northeast-2",
                "lb_name": "my-alb",
                "listener": "HTTPS:443",
                "target_group": "tg-01",
                "targets": "was-live-01 (10.0.1.1:80)",
            },
            {
                "account": "acc1",
                "region": "ap-northeast-2",
                "lb_name": "my-alb",
                "listener": "HTTPS:443",
                "target_group": "tg-01",
                "targets": "was-live-03 (10.0.1.3:80)",
            },
        ]

        rows.sort(
            key=lambda x: (
                x["account"],
                x["region"],
                x["lb_name"],
                x["listener"],
                x["target_group"],
                x["targets"],
            )
        )

        expected = [
            "was-live-01 (10.0.1.1:80)",
            "was-live-02 (10.0.1.2:80)",
            "was-live-03 (10.0.1.3:80)",
        ]
        actual = [r["targets"] for r in rows]
        self.assertEqual(actual, expected)

    def test_tencent_clb_target_sorting(self):
        rows = [
            {
                "account": "acc1",
                "region": "ap-seoul",
                "lb_name": "my-clb",
                "listener": "HTTPS:443",
                "domain_url": "example.com/",
                "targets": "tencent-cvm-03 (10.0.2.3:80)",
            },
            {
                "account": "acc1",
                "region": "ap-seoul",
                "lb_name": "my-clb",
                "listener": "HTTPS:443",
                "domain_url": "example.com/",
                "targets": "tencent-cvm-01 (10.0.2.1:80)",
            },
            {
                "account": "acc1",
                "region": "ap-seoul",
                "lb_name": "my-clb",
                "listener": "HTTPS:443",
                "domain_url": "example.com/",
                "targets": "tencent-cvm-02 (10.0.2.2:80)",
            },
        ]

        rows.sort(
            key=lambda x: (
                x["account"],
                x["region"],
                x["lb_name"],
                x["listener"],
                x["domain_url"],
                x["targets"],
            )
        )

        expected = [
            "tencent-cvm-01 (10.0.2.1:80)",
            "tencent-cvm-02 (10.0.2.2:80)",
            "tencent-cvm-03 (10.0.2.3:80)",
        ]
        actual = [r["targets"] for r in rows]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
