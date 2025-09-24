"""
NCPGOV Mock Data for CI Testing

Comprehensive mock data that accurately represents real NCPGOV service responses
for EC2, S3, VPC, Security Groups, and RDS services in the government cloud.

Requirements: 3.3, 3.5, 7.4 - Mock data that accurately represents real service responses
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
import json


class NCPGovMockDataProvider:
    """Provides comprehensive mock data for NCPGOV services."""
    
    def __init__(self):
        self.base_date = "2023-01-01T12:00:00+0900"
        self.region_code = "KR"
        self.zone_code = "KR-2"
        self.gov_prefix = "gov-"
    
    def get_server_instance_list_response(self) -> Dict[str, Any]:
        """Mock response for NCPGOV server instance list."""
        return {
            "getServerInstanceListResponse": {
                "requestId": "ncpgov-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 3,
                "serverInstanceList": [
                    {
                        "serverInstanceNo": "9876543210",
                        "serverName": "gov-web-server-01",
                        "serverDescription": "Government web server for public services",
                        "cpuCount": 4,
                        "memorySize": 8589934592,  # 8GB in bytes
                        "baseBlockStorageSize": 107374182400,  # 100GB in bytes
                        "platformType": {
                            "code": "LNX64",
                            "codeName": "Linux 64 Bit"
                        },
                        "loginKeyName": "gov-production-key",
                        "isFeeChargingMonitoring": True,
                        "publicIp": "203.0.114.10",
                        "privateIp": "10.1.1.10",
                        "serverImageName": "centos-7.8-64-gov",
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
                        "serverImageProductCode": "SPSW0LINUX000046GOV",
                        "serverProductCode": "SPSVRSSD00000003GOV",
                        "isProtectServerTermination": True,
                        "portForwardingPublicIp": "203.0.114.10",
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
                        "userData": "#!/bin/bash\n# Government security hardening\nyum update -y\nyum install -y aide\n",
                        "accessControlGroupList": [
                            {
                                "accessControlGroupConfigurationNo": "5964",
                                "accessControlGroupName": "gov-default-acg",
                                "accessControlGroupDescription": "Government Default AccessControlGroup",
                                "isDefault": True,
                                "createDate": "2017-02-23T10:25:39+0900"
                            },
                            {
                                "accessControlGroupConfigurationNo": "5965",
                                "accessControlGroupName": "gov-web-security-acg",
                                "accessControlGroupDescription": "Government Web Security Group",
                                "isDefault": False,
                                "createDate": "2023-01-01T10:25:39+0900"
                            }
                        ],
                        "networkInterfaceList": [
                            {
                                "networkInterfaceNo": "***990",
                                "networkInterfaceName": "nic-gov-web-server-01",
                                "subnetNo": "***667",
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
                        "serverInstanceNo": "8765432109",
                        "serverName": "gov-db-server-01",
                        "serverDescription": "Government database server with enhanced security",
                        "cpuCount": 8,
                        "memorySize": 17179869184,  # 16GB in bytes
                        "baseBlockStorageSize": 214748364800,  # 200GB in bytes
                        "platformType": {
                            "code": "LNX64",
                            "codeName": "Linux 64 Bit"
                        },
                        "loginKeyName": "gov-production-key",
                        "isFeeChargingMonitoring": True,
                        "publicIp": "",
                        "privateIp": "10.1.2.10",
                        "serverImageName": "rhel-8.4-64-gov",
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
                        "serverImageProductCode": "SPSW0LINUX000048GOV",
                        "serverProductCode": "SPSVRSSD00000015GOV",
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
                        "userData": "#!/bin/bash\n# Government database security setup\nyum update -y\nyum install -y postgresql-server\nsystemctl enable postgresql\n",
                        "accessControlGroupList": [
                            {
                                "accessControlGroupConfigurationNo": "5966",
                                "accessControlGroupName": "gov-database-acg",
                                "accessControlGroupDescription": "Government Database Security Group",
                                "isDefault": False,
                                "createDate": "2023-01-01T10:25:39+0900"
                            }
                        ]
                    },
                    {
                        "serverInstanceNo": "7654321098",
                        "serverName": "gov-monitoring-server-01",
                        "serverDescription": "Government monitoring and compliance server",
                        "cpuCount": 2,
                        "memorySize": 4294967296,  # 4GB in bytes
                        "baseBlockStorageSize": 53687091200,  # 50GB in bytes
                        "platformType": {
                            "code": "LNX64",
                            "codeName": "Linux 64 Bit"
                        },
                        "loginKeyName": "gov-monitoring-key",
                        "isFeeChargingMonitoring": True,
                        "publicIp": "",
                        "privateIp": "10.1.3.10",
                        "serverImageName": "ubuntu-20.04-64-gov",
                        "serverInstanceStatus": {
                            "code": "RUN",
                            "codeName": "Server run state"
                        },
                        "serverInstanceOperation": {
                            "code": "NULL",
                            "codeName": "Server NULL OP"
                        },
                        "serverInstanceStatusName": "running",
                        "createDate": "2023-01-03T12:00:00+0900",
                        "uptime": "2023-01-03T12:00:00+0900",
                        "serverImageProductCode": "SPSW0LINUX000050GOV",
                        "serverProductCode": "SPSVRSSD00000007GOV",
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
                        "userData": "#!/bin/bash\n# Government monitoring setup\napt-get update\napt-get install -y prometheus grafana\n",
                        "accessControlGroupList": [
                            {
                                "accessControlGroupConfigurationNo": "5967",
                                "accessControlGroupName": "gov-monitoring-acg",
                                "accessControlGroupDescription": "Government Monitoring Security Group",
                                "isDefault": False,
                                "createDate": "2023-01-01T10:25:39+0900"
                            }
                        ]
                    }
                ]
            }
        }
    
    def get_vpc_list_response(self) -> Dict[str, Any]:
        """Mock response for NCPGOV VPC list."""
        return {
            "getVpcListResponse": {
                "requestId": "ncpgov-vpc-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 2,
                "vpcList": [
                    {
                        "vpcNo": "22345",
                        "vpcName": "gov-production-vpc",
                        "ipv4CidrBlock": "10.1.0.0/16",
                        "vpcStatus": {
                            "code": "RUN",
                            "codeName": "VPC run state"
                        },
                        "regionCode": "KR",
                        "createDate": self.base_date,
                        "defaultNetworkAclNo": "***223",
                        "defaultAccessControlGroupConfigurationNo": "***556",
                        "defaultPublicRouteTableNo": "***889",
                        "defaultPrivateRouteTableNo": "***112"
                    },
                    {
                        "vpcNo": "33456",
                        "vpcName": "gov-development-vpc",
                        "ipv4CidrBlock": "172.17.0.0/16",
                        "vpcStatus": {
                            "code": "RUN",
                            "codeName": "VPC run state"
                        },
                        "regionCode": "KR",
                        "createDate": "2023-01-02T12:00:00+0900",
                        "defaultNetworkAclNo": "***224",
                        "defaultAccessControlGroupConfigurationNo": "***557",
                        "defaultPublicRouteTableNo": "***890",
                        "defaultPrivateRouteTableNo": "***113"
                    }
                ]
            }
        }
    
    def get_subnet_list_response(self) -> Dict[str, Any]:
        """Mock response for NCPGOV subnet list."""
        return {
            "getSubnetListResponse": {
                "requestId": "ncpgov-subnet-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 6,
                "subnetList": [
                    {
                        "subnetNo": "***667",
                        "vpcNo": "22345",
                        "subnetName": "gov-public-subnet-1",
                        "subnet": "10.1.1.0/24",
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
                        "subnetNo": "***668",
                        "vpcNo": "22345",
                        "subnetName": "gov-private-subnet-1",
                        "subnet": "10.1.2.0/24",
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
                    },
                    {
                        "subnetNo": "***669",
                        "vpcNo": "22345",
                        "subnetName": "gov-secure-subnet-1",
                        "subnet": "10.1.3.0/24",
                        "availableIpAddressCount": 253,
                        "subnetType": {
                            "code": "PRIVATE",
                            "codeName": "Private"
                        },
                        "usageType": {
                            "code": "SECURE",
                            "codeName": "Secure"
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
        """Mock response for NCPGOV access control group (security group) list."""
        return {
            "getAccessControlGroupListResponse": {
                "requestId": "ncpgov-acg-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 4,
                "accessControlGroupList": [
                    {
                        "accessControlGroupConfigurationNo": "5964",
                        "accessControlGroupName": "gov-default-acg",
                        "accessControlGroupDescription": "Government Default AccessControlGroup with enhanced security",
                        "vpcNo": "22345",
                        "accessControlGroupStatus": {
                            "code": "RUN",
                            "codeName": "AccessControlGroup run state"
                        },
                        "createDate": "2017-02-23T10:25:39+0900",
                        "isDefault": True
                    },
                    {
                        "accessControlGroupConfigurationNo": "5965",
                        "accessControlGroupName": "gov-web-security-acg",
                        "accessControlGroupDescription": "Government web server security group with strict rules",
                        "vpcNo": "22345",
                        "accessControlGroupStatus": {
                            "code": "RUN",
                            "codeName": "AccessControlGroup run state"
                        },
                        "createDate": self.base_date,
                        "isDefault": False
                    },
                    {
                        "accessControlGroupConfigurationNo": "5966",
                        "accessControlGroupName": "gov-database-acg",
                        "accessControlGroupDescription": "Government database security group with encryption requirements",
                        "vpcNo": "22345",
                        "accessControlGroupStatus": {
                            "code": "RUN",
                            "codeName": "AccessControlGroup run state"
                        },
                        "createDate": self.base_date,
                        "isDefault": False
                    },
                    {
                        "accessControlGroupConfigurationNo": "5967",
                        "accessControlGroupName": "gov-monitoring-acg",
                        "accessControlGroupDescription": "Government monitoring and compliance security group",
                        "vpcNo": "22345",
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
        """Mock response for NCPGOV access control group rules with government security requirements."""
        return {
            "getAccessControlGroupRuleListResponse": {
                "requestId": "ncpgov-acg-rule-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 6,
                "accessControlGroupRuleList": [
                    {
                        "accessControlGroupRuleConfigurationNo": "***101",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "203.0.114.0/24",  # Government IP range only
                        "accessControlGroupSequence": "0",
                        "portRange": "22",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "SSH access from government network only"
                    },
                    {
                        "accessControlGroupRuleConfigurationNo": "***102",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "0.0.0.0/0",
                        "accessControlGroupSequence": "1",
                        "portRange": "443",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "HTTPS access for public services"
                    },
                    {
                        "accessControlGroupRuleConfigurationNo": "***103",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "10.1.0.0/16",
                        "accessControlGroupSequence": "2",
                        "portRange": "5432",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "PostgreSQL access from VPC only"
                    },
                    {
                        "accessControlGroupRuleConfigurationNo": "***104",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "10.1.3.0/24",
                        "accessControlGroupSequence": "3",
                        "portRange": "9090",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "Prometheus monitoring from secure subnet"
                    },
                    {
                        "accessControlGroupRuleConfigurationNo": "***105",
                        "protocolType": {
                            "code": "TCP",
                            "codeName": "tcp"
                        },
                        "ipBlock": "10.1.3.0/24",
                        "accessControlGroupSequence": "4",
                        "portRange": "3000",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "Grafana dashboard from secure subnet"
                    },
                    {
                        "accessControlGroupRuleConfigurationNo": "***106",
                        "protocolType": {
                            "code": "ICMP",
                            "codeName": "icmp"
                        },
                        "ipBlock": "10.1.0.0/16",
                        "accessControlGroupSequence": "5",
                        "portRange": "",
                        "accessControlGroupRuleType": {
                            "code": "INBND",
                            "codeName": "inbound"
                        },
                        "accessControlGroupRuleDescription": "ICMP ping from VPC for monitoring"
                    }
                ]
            }
        }
    
    def get_storage_instance_list_response(self) -> Dict[str, Any]:
        """Mock response for NCPGOV storage (S3-like) instance list."""
        return {
            "getStorageInstanceListResponse": {
                "requestId": "ncpgov-storage-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 3,
                "storageInstanceList": [
                    {
                        "storageInstanceNo": "***889",
                        "storageInstanceName": "gov-production-storage",
                        "storageInstanceDescription": "Government production storage with encryption",
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
                        "storageSize": 214748364800,  # 200GB in bytes
                        "storageType": {
                            "code": "SSD",
                            "codeName": "SSD Storage"
                        },
                        "isEncrypted": True,
                        "encryptionType": "AES256",
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
                        "storageInstanceNo": "***890",
                        "storageInstanceName": "gov-backup-storage",
                        "storageInstanceDescription": "Government backup storage with compliance logging",
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
                        "storageSize": 429496729600,  # 400GB in bytes
                        "storageType": {
                            "code": "SSD",
                            "codeName": "SSD Storage"
                        },
                        "isEncrypted": True,
                        "encryptionType": "AES256",
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
                        "storageInstanceNo": "***891",
                        "storageInstanceName": "gov-archive-storage",
                        "storageInstanceDescription": "Government long-term archive storage",
                        "storageInstanceStatus": {
                            "code": "CREAT",
                            "codeName": "Storage create state"
                        },
                        "storageInstanceOperation": {
                            "code": "NULL",
                            "codeName": "Storage NULL OP"
                        },
                        "storageInstanceStatusName": "created",
                        "createDate": "2023-01-03T12:00:00+0900",
                        "storageSize": 1073741824000,  # 1TB in bytes
                        "storageType": {
                            "code": "HDD",
                            "codeName": "HDD Storage"
                        },
                        "isEncrypted": True,
                        "encryptionType": "AES256",
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
        """Mock response for NCPGOV Cloud DB (RDS-like) instance list."""
        return {
            "getCloudDBInstanceListResponse": {
                "requestId": "ncpgov-rds-mock-request-12345",
                "returnCode": "0",
                "returnMessage": "success",
                "totalRows": 2,
                "cloudDBInstanceList": [
                    {
                        "cloudDBInstanceNo": "***556",
                        "cloudDBServiceName": "gov-production-postgres",
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
                        "cloudDBImageProductCode": "SPSW0PGSQL001GOV",
                        "cloudDBProductCode": "SPSCDB00000001GOV",
                        "engineVersion": "POSTGRESQL12",
                        "licenseModel": "LICENSE_INCLUDED",
                        "cloudDBPort": 5432,
                        "isHa": True,
                        "isMultiZone": True,
                        "isStorage": True,
                        "isBackup": True,
                        "isEncrypted": True,
                        "encryptionType": "AES256",
                        "backupFileRetentionPeriod": 30,  # Government requires longer retention
                        "backupTime": "02:00",
                        "dataStorageType": {
                            "code": "SSD",
                            "codeName": "SSD"
                        },
                        "dataStorageSize": 214748364800,  # 200GB
                        "usedDataStorageSize": 42949672960,  # 40GB used
                        "cpuCount": 4,
                        "memorySize": 8589934592,  # 8GB
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
                            "vpcNo": "22345"
                        },
                        "subnet": {
                            "subnetNo": "***668"
                        },
                        "cloudDBServerInstanceList": [
                            {
                                "cloudDBServerInstanceNo": "***211",
                                "cloudDBServerName": "gov-production-postgres-master",
                                "cloudDBServerRole": {
                                    "code": "M",
                                    "codeName": "Master"
                                },
                                "privateIp": "10.1.2.100",
                                "publicIp": "",
                                "cloudDBServerInstanceStatusName": "running",
                                "createDate": self.base_date
                            },
                            {
                                "cloudDBServerInstanceNo": "***212",
                                "cloudDBServerName": "gov-production-postgres-standby",
                                "cloudDBServerRole": {
                                    "code": "H",
                                    "codeName": "Standby Master"
                                },
                                "privateIp": "10.1.2.101",
                                "publicIp": "",
                                "cloudDBServerInstanceStatusName": "running",
                                "createDate": self.base_date
                            }
                        ]
                    },
                    {
                        "cloudDBInstanceNo": "***557",
                        "cloudDBServiceName": "gov-audit-mysql",
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
                        "cloudDBImageProductCode": "SPSW0MYSQL001GOV",
                        "cloudDBProductCode": "SPSCDB00000002GOV",
                        "engineVersion": "MYSQL8.0",
                        "licenseModel": "LICENSE_INCLUDED",
                        "cloudDBPort": 3306,
                        "isHa": True,
                        "isMultiZone": False,
                        "isStorage": True,
                        "isBackup": True,
                        "isEncrypted": True,
                        "encryptionType": "AES256",
                        "backupFileRetentionPeriod": 90,  # Audit database requires longer retention
                        "backupTime": "01:00",
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
                            "vpcNo": "22345"
                        },
                        "subnet": {
                            "subnetNo": "***669"
                        },
                        "cloudDBServerInstanceList": [
                            {
                                "cloudDBServerInstanceNo": "***213",
                                "cloudDBServerName": "gov-audit-mysql-master",
                                "cloudDBServerRole": {
                                    "code": "M",
                                    "codeName": "Master"
                                },
                                "privateIp": "10.1.3.100",
                                "publicIp": "",
                                "cloudDBServerInstanceStatusName": "running",
                                "createDate": "2023-01-02T12:00:00+0900"
                            },
                            {
                                "cloudDBServerInstanceNo": "***214",
                                "cloudDBServerName": "gov-audit-mysql-standby",
                                "cloudDBServerRole": {
                                    "code": "H",
                                    "codeName": "Standby Master"
                                },
                                "privateIp": "10.1.3.101",
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
ncpgov_mock_data = NCPGovMockDataProvider()


def get_ncpgov_mock_response(service: str, operation: str) -> Dict[str, Any]:
    """Get mock response for NCPGOV service operation."""
    service_operations = {
        'server': {
            'getServerInstanceList': ncpgov_mock_data.get_server_instance_list_response,
        },
        'vpc': {
            'getVpcList': ncpgov_mock_data.get_vpc_list_response,
            'getSubnetList': ncpgov_mock_data.get_subnet_list_response,
        },
        'sg': {
            'getAccessControlGroupList': ncpgov_mock_data.get_access_control_group_list_response,
            'getAccessControlGroupRuleList': ncpgov_mock_data.get_access_control_group_rule_list_response,
        },
        's3': {
            'getStorageInstanceList': ncpgov_mock_data.get_storage_instance_list_response,
        },
        'rds': {
            'getCloudDBInstanceList': ncpgov_mock_data.get_cloud_db_instance_list_response,
        }
    }
    
    if service in service_operations and operation in service_operations[service]:
        return service_operations[service][operation]()
    else:
        raise ValueError(f"Unsupported NCPGOV service/operation: {service}/{operation}")


def get_all_ncpgov_mock_responses() -> Dict[str, Dict[str, Any]]:
    """Get all available NCPGOV mock responses."""
    return {
        'server_instances': ncpgov_mock_data.get_server_instance_list_response(),
        'vpc_list': ncpgov_mock_data.get_vpc_list_response(),
        'subnet_list': ncpgov_mock_data.get_subnet_list_response(),
        'access_control_groups': ncpgov_mock_data.get_access_control_group_list_response(),
        'access_control_group_rules': ncpgov_mock_data.get_access_control_group_rule_list_response(),
        'storage_instances': ncpgov_mock_data.get_storage_instance_list_response(),
        'cloud_db_instances': ncpgov_mock_data.get_cloud_db_instance_list_response()
    }