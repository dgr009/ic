"""
NCP Mock Data for CI Testing

Comprehensive mock data that accurately represents real NCP service responses
for EC2, S3, VPC, Security Groups, and RDS services.

Requirements: 3.3, 3.5, 7.4 - Mock data that accurately represents real service responses
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
import json


class NCPMockDataProvider:
    """Provides comprehensive mock data for NCP services."""
    
    def __init__(self):
        self.base_date = "2023-01-01T12:00:00+0900"
        self.region_code = "KR"
        self.zone_code = "KR-2"
    
    def get_server_instance_list_response(self) -> Dict[str, Any]:
        """Mock response for NCP server instance list."""
        return {
            "getServerInstanceListResponse": {
                "requestId": "ncp-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 3,
                "serverInstanceList": [
                    {
                        "serverInstanceNo": "1234567890",
                        "serverName": "web-server-01",
                        "serverDescription": "Production web server",
                        "cpuCount": 2,
                        "memorySize": 4294967296,  # 4GB in bytes
                        "baseBlockStorageSize": 53687091200,  # 50GB in bytes
                        "platformType": {
                            "code": "LNX64",
                            "codeName": "Linux 64 Bit"
                        },
                        "loginKeyName": "production-key",
                        "isFeeChargingMonitoring": False,
                        "publicIp": "203.0.113.10",
                        "privateIp": "10.0.1.10",
                        "serverImageName": "centos-7.8-64",
                        "serverInstanceStatus": {
                            "code": "RUN",
                            "codeName": "Server run state"
                        },
                        "serverInstanceOperation": {
                            "code": "NULL",
                            "codeName": "Server NULL OP"
                        },
                        "serverInstanceStatusName": "running",
                        "createDate": self.base_date,
                        "uptime": "2023-01-01T12:00:00+0900",
                        "serverImageProductCode": "SPSW0LINUX000046",
                        "serverProductCode": "SPSVRSSD00000003",
                        "isProtectServerTermination": False,
                        "portForwardingPublicIp": "203.0.113.10",
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        },
                        "region": {
                            "regionNo": "1",
                            "regionName": "Korea",
                            "regionCode": "KR"
                        },
                        "baseBlockStorageDiskType": {
                            "code": "NET",
                            "codeName": "Network Storage"
                        },
                        "userData": "",
                        "accessControlGroupList": [
                            {
                                "accessControlGroupConfigurationNo": "4964",
                                "accessControlGroupName": "ncloud-default-acg",
                                "accessControlGroupDescription": "Default AccessControlGroup",
                                "isDefault": True,
                                "createDate": "2017-02-23T10:25:39+0900"
                            }
                        ],
                        "networkInterfaceList": [
                            {
                                "networkInterfaceNo": "***890",
                                "networkInterfaceName": "nic-web-server-01",
                                "subnetNo": "***567",
                                "deleteOnTermination": True,
                                "deviceIndex": 0,
                                "networkInterfaceStatus": {
                                    "code": "SET",
                                    "codeName": "Network Interface set state"
                                },
                                "instanceType": "VSERVER",
                                "isDefault": True,
                                "secondaryIpList": []
                            }
                        ]
                    },
                    {
                        "serverInstanceNo": "2345678901",
                        "serverName": "db-server-01",
                        "serverDescription": "Database server",
                        "cpuCount": 4,
                        "memorySize": 8589934592,  # 8GB in bytes
                        "baseBlockStorageSize": 107374182400,  # 100GB in bytes
                        "platformType": {
                            "code": "LNX64",
                            "codeName": "Linux 64 Bit"
                        },
                        "loginKeyName": "production-key",
                        "isFeeChargingMonitoring": True,
                        "publicIp": "",
                        "privateIp": "10.0.2.10",
                        "serverImageName": "ubuntu-18.04-64",
                        "serverInstanceStatus": {
                            "code": "RUN",
                            "codeName": "Server run state"
                        },
                        "serverInstanceOperation": {
                            "code": "NULL",
                            "codeName": "Server NULL OP"
                        },
                        "serverInstanceStatusName": "running",
                        "createDate": "2023-01-02T12:00:00+0900",
                        "uptime": "2023-01-02T12:00:00+0900",
                        "serverImageProductCode": "SPSW0LINUX000032",
                        "serverProductCode": "SPSVRSSD00000011",
                        "isProtectServerTermination": True,
                        "portForwardingPublicIp": "",
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        },
                        "region": {
                            "regionNo": "1",
                            "regionName": "Korea",
                            "regionCode": "KR"
                        },
                        "baseBlockStorageDiskType": {
                            "code": "SSD",
                            "codeName": "SSD Storage"
                        },
                        "userData": "#!/bin/bash\napt-get update\napt-get install -y mysql-server",
                        "accessControlGroupList": [
                            {
                                "accessControlGroupConfigurationNo": "4965",
                                "accessControlGroupName": "database-acg",
                                "accessControlGroupDescription": "Database AccessControlGroup",
                                "isDefault": False,
                                "createDate": "2023-01-01T10:25:39+0900"
                            }
                        ]
                    },
                    {
                        "serverInstanceNo": "3456789012",
                        "serverName": "test-server-01",
                        "serverDescription": "Development test server",
                        "cpuCount": 1,
                        "memorySize": 2147483648,  # 2GB in bytes
                        "baseBlockStorageSize": 26843545600,  # 25GB in bytes
                        "platformType": {
                            "code": "WND64",
                            "codeName": "Windows 64 Bit"
                        },
                        "loginKeyName": "test-key",
                        "isFeeChargingMonitoring": False,
                        "publicIp": "203.0.113.11",
                        "privateIp": "10.0.3.10",
                        "serverImageName": "win-2019-64-en",
                        "serverInstanceStatus": {
                            "code": "STOP",
                            "codeName": "Server stop state"
                        },
                        "serverInstanceOperation": {
                            "code": "NULL",
                            "codeName": "Server NULL OP"
                        },
                        "serverInstanceStatusName": "stopped",
                        "createDate": "2023-01-03T12:00:00+0900",
                        "uptime": "",
                        "serverImageProductCode": "SPSW0WINNT000016",
                        "serverProductCode": "SPSVRSSD00000001",
                        "isProtectServerTermination": False,
                        "portForwardingPublicIp": "203.0.113.11",
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        },
                        "region": {
                            "regionNo": "1",
                            "regionName": "Korea",
                            "regionCode": "KR"
                        },
                        "baseBlockStorageDiskType": {
                            "code": "NET",
                            "codeName": "Network Storage"
                        },
                        "userData": "",
                        "accessControlGroupList": [
                            {
                                "accessControlGroupConfigurationNo": "4964",
                                "accessControlGroupName": "ncloud-default-acg",
                                "accessControlGroupDescription": "Default AccessControlGroup",
                                "isDefault": True,
                                "createDate": "2017-02-23T10:25:39+0900"
                            }
                        ]
                    }
                ]
            }
        }
    
    def get_vpc_list_response(self) -> Dict[str, Any]:
        """Mock response for NCP VPC list."""
        return {
            "getVpcListResponse": {
                "requestId": "ncp-vpc-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 2,
                "vpcList": [
                    {
                        "vpcNo": "12345",
                        "vpcName": "production-vpc",
                        "ipv4CidrBlock": "10.0.0.0/16",
                        "vpcStatus": {
                            "code": "RUN",
                            "codeName": "VPC run state"
                        },
                        "regionCode": "KR",
                        "createDate": self.base_date,
                        "defaultNetworkAclNo": "***123",
                        "defaultAccessControlGroupConfigurationNo": "***456",
                        "defaultPublicRouteTableNo": "***789",
                        "defaultPrivateRouteTableNo": "***012"
                    },
                    {
                        "vpcNo": "23456",
                        "vpcName": "development-vpc",
                        "ipv4CidrBlock": "172.16.0.0/16",
                        "vpcStatus": {
                            "code": "RUN",
                            "codeName": "VPC run state"
                        },
                        "regionCode": "KR",
                        "createDate": "2023-01-02T12:00:00+0900",
                        "defaultNetworkAclNo": "***124",
                        "defaultAccessControlGroupConfigurationNo": "***457",
                        "defaultPublicRouteTableNo": "***790",
                        "defaultPrivateRouteTableNo": "***013"
                    }
                ]
            }
        }
    
    def get_subnet_list_response(self) -> Dict[str, Any]:
        """Mock response for NCP subnet list."""
        return {
            "getSubnetListResponse": {
                "requestId": "ncp-subnet-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 4,
                "subnetList": [
                    {
                        "subnetNo": "***567",
                        "vpcNo": "12345",
                        "subnetName": "public-subnet-1",
                        "subnet": "10.0.1.0/24",
                        "availableIpAddressCount": 251,
                        "subnetType": {
                            "code": "PUBLIC",
                            "codeName": "Public"
                        },
                        "usageType": {
                            "code": "GEN",
                            "codeName": "General"
                        },
                        "subnetStatus": {
                            "code": "RUN",
                            "codeName": "Subnet run state"
                        },
                        "createDate": self.base_date,
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        }
                    },
                    {
                        "subnetNo": "***568",
                        "vpcNo": "12345",
                        "subnetName": "private-subnet-1",
                        "subnet": "10.0.2.0/24",
                        "availableIpAddressCount": 253,
                        "subnetType": {
                            "code": "PRIVATE",
                            "codeName": "Private"
                        },
                        "usageType": {
                            "code": "GEN",
                            "codeName": "General"
                        },
                        "subnetStatus": {
                            "code": "RUN",
                            "codeName": "Subnet run state"
                        },
                        "createDate": self.base_date,
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        }
                    }
                ]
            }
        }
    
    def get_access_control_group_list_response(self) -> Dict[str, Any]:
        """Mock response for NCP access control group (security group) list."""
        return {
            "getAccessControlGroupListResponse": {
                "requestId": "ncp-acg-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 3,
                "accessControlGroupList": [
                    {
                        "accessControlGroupConfigurationNo": "4964",
                        "accessControlGroupName": "ncloud-default-acg",
                        "accessControlGroupDescription": "Default AccessControlGroup",
                        "vpcNo": "12345",
                        "accessControlGroupStatus": {
                            "code": "RUN",
                            "codeName": "AccessControlGroup run state"
                        },
                        "createDate": "2017-02-23T10:25:39+0900",
                        "isDefault": True
                    },
                    {
                        "accessControlGroupConfigurationNo": "4965",
                        "accessControlGroupName": "web-server-acg",
                        "accessControlGroupDescription": "Web server security group",
                        "vpcNo": "12345",
                        "accessControlGroupStatus": {
                            "code": "RUN",
                            "codeName": "AccessControlGroup run state"
                        },
                        "createDate": self.base_date,
                        "isDefault": False
                    },
                    {
                        "accessControlGroupConfigurationNo": "4966",
                        "accessControlGroupName": "database-acg",
                        "accessControlGroupDescription": "Database security group",
                        "vpcNo": "12345",
                        "accessControlGroupStatus": {
                            "code": "RUN",
                            "codeName": "AccessControlGroup run state"
                        },
                        "createDate": self.base_date,
                        "isDefault": False
                    }
                ]
            }
        }
    
    def get_access_control_group_rule_list_response(self) -> Dict[str, Any]:
        """Mock response for NCP access control group rules."""
        return {
            "getAccessControlGroupRuleListResponse": {
                "requestId": "ncp-acg-rule-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 4,
                "accessControlGroupRuleList": [
                    {
                        "accessControlGroupRuleConfigurationNo": "***001",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "0.0.0.0/0",
                        "accessControlGroupSequence": "0",
                        "portRange": "22",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "SSH access"
                    },
                    {
                        "accessControlGroupRuleConfigurationNo": "***002",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "0.0.0.0/0",
                        "accessControlGroupSequence": "1",
                        "portRange": "80",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "HTTP access"
                    },
                    {
                        "accessControlGroupRuleConfigurationNo": "***003",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "0.0.0.0/0",
                        "accessControlGroupSequence": "2",
                        "portRange": "443",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "HTTPS access"
                    },
                    {
                        "accessControlGroupRuleConfigurationNo": "***004",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "10.0.0.0/16",
                        "accessControlGroupSequence": "3",
                        "portRange": "3306",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "MySQL access from VPC"
                    }
                ]
            }
        }
    
    def get_storage_instance_list_response(self) -> Dict[str, Any]:
        """Mock response for NCP storage (S3-like) instance list."""
        return {
            "getStorageInstanceListResponse": {
                "requestId": "ncp-storage-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 2,
                "storageInstanceList": [
                    {
                        "storageInstanceNo": "***789",
                        "storageInstanceName": "production-storage",
                        "storageInstanceDescription": "Production file storage",
                        "storageInstanceStatus": {
                            "code": "CREAT",
                            "codeName": "Storage create state"
                        },
                        "storageInstanceOperation": {
                            "code": "NULL",
                            "codeName": "Storage NULL OP"
                        },
                        "storageInstanceStatusName": "created",
                        "createDate": self.base_date,
                        "storageSize": 107374182400,  # 100GB in bytes
                        "storageType": {
                            "code": "SSD",
                            "codeName": "SSD Storage"
                        },
                        "region": {
                            "regionNo": "1",
                            "regionName": "Korea",
                            "regionCode": "KR"
                        },
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        }
                    },
                    {
                        "storageInstanceNo": "***790",
                        "storageInstanceName": "backup-storage",
                        "storageInstanceDescription": "Backup storage",
                        "storageInstanceStatus": {
                            "code": "CREAT",
                            "codeName": "Storage create state"
                        },
                        "storageInstanceOperation": {
                            "code": "NULL",
                            "codeName": "Storage NULL OP"
                        },
                        "storageInstanceStatusName": "created",
                        "createDate": "2023-01-02T12:00:00+0900",
                        "storageSize": 214748364800,  # 200GB in bytes
                        "storageType": {
                            "code": "HDD",
                            "codeName": "HDD Storage"
                        },
                        "region": {
                            "regionNo": "1",
                            "regionName": "Korea",
                            "regionCode": "KR"
                        },
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        }
                    }
                ]
            }
        }
    
    def get_cloud_db_instance_list_response(self) -> Dict[str, Any]:
        """Mock response for NCP Cloud DB (RDS-like) instance list."""
        return {
            "getCloudDBInstanceListResponse": {
                "requestId": "ncp-rds-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 2,
                "cloudDBInstanceList": [
                    {
                        "cloudDBInstanceNo": "***456",
                        "cloudDBServiceName": "production-mysql",
                        "cloudDBInstanceStatusName": "running",
                        "cloudDBInstanceStatus": {
                            "code": "RUN",
                            "codeName": "CloudDB run state"
                        },
                        "cloudDBInstanceOperation": {
                            "code": "NULL",
                            "codeName": "CloudDB NULL OP"
                        },
                        "createDate": self.base_date,
                        "cloudDBImageProductCode": "SPSW0MYSQL001",
                        "cloudDBProductCode": "SPSCDB00000001",
                        "engineVersion": "MYSQL5.7",
                        "licenseModel": "LICENSE_INCLUDED",
                        "cloudDBPort": 3306,
                        "isHa": True,
                        "isMultiZone": False,
                        "isStorage": True,
                        "isBackup": True,
                        "backupFileRetentionPeriod": 7,
                        "backupTime": "02:00",
                        "dataStorageType": {
                            "code": "SSD",
                            "codeName": "SSD"
                        },
                        "dataStorageSize": 107374182400,  # 100GB
                        "usedDataStorageSize": 21474836480,  # 20GB used
                        "cpuCount": 2,
                        "memorySize": 4294967296,  # 4GB
                        "region": {
                            "regionNo": "1",
                            "regionName": "Korea",
                            "regionCode": "KR"
                        },
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        },
                        "vpc": {
                            "vpcNo": "12345"
                        },
                        "subnet": {
                            "subnetNo": "***568"
                        },
                        "cloudDBServerInstanceList": [
                            {
                                "cloudDBServerInstanceNo": "***111",
                                "cloudDBServerName": "production-mysql-master",
                                "cloudDBServerRole": {
                                    "code": "M",
                                    "codeName": "Master"
                                },
                                "privateIp": "10.0.2.100",
                                "publicIp": "",
                                "cloudDBServerInstanceStatusName": "running",
                                "createDate": self.base_date
                            },
                            {
                                "cloudDBServerInstanceNo": "***112",
                                "cloudDBServerName": "production-mysql-standby",
                                "cloudDBServerRole": {
                                    "code": "H",
                                    "codeName": "Standby Master"
                                },
                                "privateIp": "10.0.2.101",
                                "publicIp": "",
                                "cloudDBServerInstanceStatusName": "running",
                                "createDate": self.base_date
                            }
                        ]
                    },
                    {
                        "cloudDBInstanceNo": "***457",
                        "cloudDBServiceName": "development-postgres",
                        "cloudDBInstanceStatusName": "running",
                        "cloudDBInstanceStatus": {
                            "code": "RUN",
                            "codeName": "CloudDB run state"
                        },
                        "cloudDBInstanceOperation": {
                            "code": "NULL",
                            "codeName": "CloudDB NULL OP"
                        },
                        "createDate": "2023-01-02T12:00:00+0900",
                        "cloudDBImageProductCode": "SPSW0PGSQL001",
                        "cloudDBProductCode": "SPSCDB00000002",
                        "engineVersion": "POSTGRESQL10",
                        "licenseModel": "LICENSE_INCLUDED",
                        "cloudDBPort": 5432,
                        "isHa": False,
                        "isMultiZone": False,
                        "isStorage": True,
                        "isBackup": True,
                        "backupFileRetentionPeriod": 3,
                        "backupTime": "03:00",
                        "dataStorageType": {
                            "code": "SSD",
                            "codeName": "SSD"
                        },
                        "dataStorageSize": 53687091200,  # 50GB
                        "usedDataStorageSize": 5368709120,  # 5GB used
                        "cpuCount": 1,
                        "memorySize": 2147483648,  # 2GB
                        "region": {
                            "regionNo": "1",
                            "regionName": "Korea",
                            "regionCode": "KR"
                        },
                        "zone": {
                            "zoneNo": "3",
                            "zoneName": "KR-2",
                            "zoneCode": "KR-2"
                        },
                        "vpc": {
                            "vpcNo": "23456"
                        },
                        "subnet": {
                            "subnetNo": "***569"
                        },
                        "cloudDBServerInstanceList": [
                            {
                                "cloudDBServerInstanceNo": "***113",
                                "cloudDBServerName": "development-postgres-master",
                                "cloudDBServerRole": {
                                    "code": "M",
                                    "codeName": "Master"
                                },
                                "privateIp": "172.16.1.100",
                                "publicIp": "",
                                "cloudDBServerInstanceStatusName": "running",
                                "createDate": "2023-01-02T12:00:00+0900"
                            }
                        ]
                    }
                ]
            }
        }


# Global instance for easy access
ncp_mock_data = NCPMockDataProvider()


def get_ncp_mock_response(service: str, operation: str) -> Dict[str, Any]:
    """Get mock response for NCP service operation."""
    service_operations = {
        'server': {
            'getServerInstanceList': ncp_mock_data.get_server_instance_list_response,
        },
        'vpc': {
            'getVpcList': ncp_mock_data.get_vpc_list_response,
            'getSubnetList': ncp_mock_data.get_subnet_list_response,
        },
        'sg': {
            'getAccessControlGroupList': ncp_mock_data.get_access_control_group_list_response,
            'getAccessControlGroupRuleList': ncp_mock_data.get_access_control_group_rule_list_response,
        },
        's3': {
            'getStorageInstanceList': ncp_mock_data.get_storage_instance_list_response,
        },
        'rds': {
            'getCloudDBInstanceList': ncp_mock_data.get_cloud_db_instance_list_response,
        }
    }
    
    if service in service_operations and operation in service_operations[service]:
        return service_operations[service][operation]()
    else:
        raise ValueError(f"Unsupported NCP service/operation: {service}/{operation}")


def get_all_ncp_mock_responses() -> Dict[str, Dict[str, Any]]:
    """Get all available NCP mock responses."""
    return {
        'server_instances': ncp_mock_data.get_server_instance_list_response(),
        'vpc_list': ncp_mock_data.get_vpc_list_response(),
        'subnet_list': ncp_mock_data.get_subnet_list_response(),
        'access_control_groups': ncp_mock_data.get_access_control_group_list_response(),
        'access_control_group_rules': ncp_mock_data.get_access_control_group_rule_list_response(),
        'storage_instances': ncp_mock_data.get_storage_instance_list_response(),
        'cloud_db_instances': ncp_mock_data.get_cloud_db_instance_list_response()
    }