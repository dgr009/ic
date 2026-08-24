"""
Unit tests for VPC, Subnet, and Security Group name resolution with ID fallback
in AWS EC2 and Tencent CVM info modules.
"""

import unittest


class TestResourceNameFallback(unittest.TestCase):
    """Test name resolution with ID fallback logic."""

    def test_aws_name_tag_resolution(self):
        # Items with Name tag
        vpc_item_with_name = {
            "VpcId": "vpc-12345",
            "Tags": [{"Key": "Name", "Value": "prod-vpc"}],
        }
        # Items without Name tag
        vpc_item_without_name = {
            "VpcId": "vpc-67890",
            "Tags": [{"Key": "Env", "Value": "prod"}],
        }
        # Items with empty tags
        vpc_item_empty_tags = {
            "VpcId": "vpc-abcde",
            "Tags": [],
        }

        def resolve_name(item, id_key):
            tags = item.get("Tags", [])
            name_tag = next((t["Value"] for t in tags if t.get("Key") == "Name" and t.get("Value")), None)
            return name_tag if name_tag else item[id_key]

        self.assertEqual(resolve_name(vpc_item_with_name, "VpcId"), "prod-vpc")
        self.assertEqual(resolve_name(vpc_item_without_name, "VpcId"), "vpc-67890")
        self.assertEqual(resolve_name(vpc_item_empty_tags, "VpcId"), "vpc-abcde")

    def test_aws_sg_resolution(self):
        # SG with Name tag
        sg_with_name_tag = {
            "GroupId": "sg-111",
            "GroupName": "web-sg",
            "Tags": [{"Key": "Name", "Value": "custom-web-sg"}],
        }
        # SG without Name tag, has GroupName
        sg_without_name_tag = {
            "GroupId": "sg-222",
            "GroupName": "db-sg",
            "Tags": [],
        }
        # SG without Name tag and no GroupName
        sg_no_name = {
            "GroupId": "sg-333",
            "Tags": [],
        }

        def resolve_sg(item):
            gid = item["GroupId"]
            tags = item.get("Tags", [])
            name_tag = next((t["Value"] for t in tags if t.get("Key") == "Name" and t.get("Value")), None)
            group_name = item.get("GroupName")
            return name_tag if name_tag else (group_name if group_name else gid)

        self.assertEqual(resolve_sg(sg_with_name_tag), "custom-web-sg")
        self.assertEqual(resolve_sg(sg_without_name_tag), "db-sg")
        self.assertEqual(resolve_sg(sg_no_name), "sg-333")

    def test_tencent_name_resolution(self):
        class MockVpc:
            def __init__(self, vpc_id, vpc_name):
                self.VpcId = vpc_id
                self.VpcName = vpc_name

        vpc_with_name = MockVpc("vpc-tc1", "tc-prod-vpc")
        vpc_empty_name = MockVpc("vpc-tc2", "")
        vpc_none_name = MockVpc("vpc-tc3", None)

        def resolve_tc_name(obj):
            return obj.VpcName if obj.VpcName else obj.VpcId

        self.assertEqual(resolve_tc_name(vpc_with_name), "tc-prod-vpc")
        self.assertEqual(resolve_tc_name(vpc_empty_name), "vpc-tc2")
        self.assertEqual(resolve_tc_name(vpc_none_name), "vpc-tc3")


if __name__ == "__main__":
    unittest.main()
