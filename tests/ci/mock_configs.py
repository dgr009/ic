"""
Mock Configuration System for CI Testing

Provides mock configurations and fallback mechanisms for all supported platforms
when running in CI environments without access to real configuration files.

Requirements: 3.1, 3.2, 3.7 - Mock configuration system and fallback mechanisms
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import Mock, MagicMock
import logging


class MockConfigProvider:
    """Provides mock configurations for different cloud platforms."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_mock_aws_config(self) -> Dict[str, Any]:
        """Get mock AWS configuration."""
        return {
            'aws_access_key_id': 'AKIAIOSFODNN7EXAMPLE',
            'aws_secret_access_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            'region_name': 'us-east-1',
            'regions': ['us-east-1', 'us-west-2', 'ap-northeast-2'],
            'accounts': ['123456789012', '210987654321'],
            'profiles': {
                'default': {
                    'aws_access_key_id': 'AKIAIOSFODNN7EXAMPLE',
                    'aws_secret_access_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                    'region': 'us-east-1'
                },
                'production': {
                    'aws_access_key_id': 'AKIAI44QH8DHBEXAMPLE',
                    'aws_secret_access_key': 'je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY',
                    'region': 'us-west-2'
                }
            }
        }
    
    def get_mock_azure_config(self) -> Dict[str, Any]:
        """Get mock Azure configuration."""
        return {
            'client_id': '12345678-1234-1234-1234-123456789012',
            'client_secret': 'mock-client-secret-value',
            'tenant_id': '87654321-4321-4321-4321-210987654321',
            'subscription_id': 'abcdef12-3456-7890-abcd-ef1234567890',
            'locations': ['East US', 'West US 2', 'Central US'],
            'resource_groups': ['rg-production', 'rg-development', 'rg-testing']
        }
    
    def get_mock_gcp_config(self) -> Dict[str, Any]:
        """Get mock GCP configuration."""
        return {
            'type': 'service_account',
            'project_id': 'mock-gcp-project-12345',
            'private_key_id': 'mock-key-id-12345',
            'private_key': '-----BEGIN PRIVATE KEY-----\nMOCK_PRIVATE_KEY_CONTENT\n-----END PRIVATE KEY-----\n',
            'client_email': 'mock-service-account@mock-gcp-project-12345.iam.gserviceaccount.com',
            'client_id': '123456789012345678901',
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'regions': ['us-central1', 'us-east1', 'europe-west1'],
            'projects': ['mock-gcp-project-12345', 'mock-gcp-project-67890']
        }
    
    def get_mock_oci_config(self) -> Dict[str, Any]:
        """Get mock OCI configuration."""
        return {
            'user': 'ocid1.user.oc1..mock_user_ocid',
            'key_file': '/tmp/mock_oci_api_key.pem',
            'fingerprint': 'aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99',
            'tenancy': 'ocid1.tenancy.oc1..mock_tenancy_ocid',
            'region': 'us-ashburn-1',
            'compartment': 'ocid1.compartment.oc1..mock_compartment_ocid',
            'regions': ['us-ashburn-1', 'us-phoenix-1', 'eu-frankfurt-1'],
            'compartments': [
                'ocid1.compartment.oc1..mock_compartment_ocid',
                'ocid1.compartment.oc1..mock_compartment_ocid_2'
            ]
        }
    
    def get_mock_ncp_config(self) -> Dict[str, Any]:
        """Get mock NCP configuration."""
        return {
            'access_key': 'MOCK_NCP_ACCESS_KEY_12345',
            'secret_key': 'MOCK_NCP_SECRET_KEY_67890',
            'region': 'KR',
            'endpoint': 'https://ncloud.apigw.ntruss.com',
            'timeout': 30,
            'max_retries': 3,
            'services': {
                'server': 'https://ncloud.apigw.ntruss.com/vserver/v2',
                'vpc': 'https://ncloud.apigw.ntruss.com/vpc/v2',
                'storage': 'https://ncloud.apigw.ntruss.com/vnas/v2'
            }
        }
    
    def get_mock_ncpgov_config(self) -> Dict[str, Any]:
        """Get mock NCPGOV configuration."""
        return {
            'access_key': 'MOCK_NCPGOV_ACCESS_KEY_12345',
            'secret_key': 'MOCK_NCPGOV_SECRET_KEY_67890',
            'region': 'KR',
            'endpoint': 'https://ncloud.apigw.gov-ntruss.com',
            'timeout': 30,
            'max_retries': 3,
            'services': {
                'server': 'https://ncloud.apigw.gov-ntruss.com/vserver/v2',
                'vpc': 'https://ncloud.apigw.gov-ntruss.com/vpc/v2',
                'storage': 'https://ncloud.apigw.gov-ntruss.com/vnas/v2'
            }
        }
    
    def get_mock_cloudflare_config(self) -> Dict[str, Any]:
        """Get mock CloudFlare configuration."""
        return {
            'api_token': 'mock_cloudflare_api_token_12345',
            'email': 'mock@example.com',
            'api_key': 'mock_cloudflare_api_key_67890',
            'zones': [
                {
                    'id': 'mock_zone_id_1',
                    'name': 'example.com',
                    'status': 'active'
                },
                {
                    'id': 'mock_zone_id_2',
                    'name': 'test.com',
                    'status': 'active'
                }
            ]
        }


class MockCredentialProvider:
    """Provides mock credentials and authentication for CI testing."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_provider = MockConfigProvider()
    
    def create_mock_aws_credentials_file(self) -> Path:
        """Create mock AWS credentials file."""
        temp_dir = Path(tempfile.mkdtemp(prefix='aws_ci_'))
        credentials_file = temp_dir / '.aws' / 'credentials'
        credentials_file.parent.mkdir(parents=True, exist_ok=True)
        
        credentials_content = """[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
region = us-east-1

[production]
aws_access_key_id = AKIAI44QH8DHBEXAMPLE
aws_secret_access_key = je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY
region = us-west-2
"""
        
        with open(credentials_file, 'w') as f:
            f.write(credentials_content)
        
        # Also create config file
        config_file = temp_dir / '.aws' / 'config'
        config_content = """[default]
region = us-east-1
output = json

[profile production]
region = us-west-2
output = json
"""
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        return credentials_file
    
    def create_mock_gcp_credentials_file(self) -> Path:
        """Create mock GCP service account credentials file."""
        temp_dir = Path(tempfile.mkdtemp(prefix='gcp_ci_'))
        credentials_file = temp_dir / 'gcp-service-account.json'
        
        gcp_config = self.config_provider.get_mock_gcp_config()
        
        with open(credentials_file, 'w') as f:
            json.dump(gcp_config, f, indent=2)
        
        return credentials_file
    
    def create_mock_oci_config_file(self) -> Path:
        """Create mock OCI configuration file."""
        temp_dir = Path(tempfile.mkdtemp(prefix='oci_ci_'))
        config_file = temp_dir / '.oci' / 'config'
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        oci_config = self.config_provider.get_mock_oci_config()
        
        config_content = f"""[DEFAULT]
user={oci_config['user']}
fingerprint={oci_config['fingerprint']}
key_file={oci_config['key_file']}
tenancy={oci_config['tenancy']}
region={oci_config['region']}
"""
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Create mock private key file
        key_file = Path(oci_config['key_file'])
        key_file.parent.mkdir(parents=True, exist_ok=True)
        
        mock_private_key = """-----BEGIN RSA PRIVATE KEY-----
MOCK_PRIVATE_KEY_CONTENT_FOR_TESTING_ONLY
THIS_IS_NOT_A_REAL_PRIVATE_KEY
-----END RSA PRIVATE KEY-----"""
        
        with open(key_file, 'w') as f:
            f.write(mock_private_key)
        
        return config_file


class MockServiceResponseProvider:
    """Provides mock service responses for different cloud platforms."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_mock_aws_ec2_response(self) -> Dict[str, Any]:
        """Get mock AWS EC2 describe_instances response."""
        return {
            'Reservations': [
                {
                    'ReservationId': 'r-1234567890abcdef0',
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'ImageId': 'ami-12345678',
                            'State': {'Code': 16, 'Name': 'running'},
                            'PrivateDnsName': 'ip-10-0-0-1.ec2.internal',
                            'PublicDnsName': 'ec2-203-0-113-12.compute-1.amazonaws.com',
                            'StateTransitionReason': '',
                            'InstanceType': 't3.micro',
                            'KeyName': 'my-key-pair',
                            'LaunchTime': '2023-01-01T12:00:00.000Z',
                            'Placement': {
                                'AvailabilityZone': 'us-east-1a',
                                'GroupName': '',
                                'Tenancy': 'default'
                            },
                            'Platform': 'windows',
                            'PrivateIpAddress': '10.0.0.1',
                            'PublicIpAddress': '203.0.113.12',
                            'Architecture': 'x86_64',
                            'RootDeviceType': 'ebs',
                            'VirtualizationType': 'hvm',
                            'Tags': [
                                {'Key': 'Name', 'Value': 'test-instance'},
                                {'Key': 'Environment', 'Value': 'development'}
                            ]
                        }
                    ]
                }
            ]
        }
    
    def get_mock_ncp_server_response(self) -> Dict[str, Any]:
        """Get mock NCP server list response."""
        return {
            'getServerInstanceListResponse': {
                'requestId': 'mock-request-id-12345',
                'returnCode': '0',
                'returnMessage': 'success',
                'totalRows': 2,
                'serverInstanceList': [
                    {
                        'serverInstanceNo': '12345678',
                        'serverName': 'test-server-01',
                        'serverDescription': 'Test server for CI',
                        'cpuCount': 2,
                        'memorySize': 4294967296,
                        'baseBlockStorageSize': 53687091200,
                        'platformType': {'code': 'LNX64', 'codeName': 'Linux 64 Bit'},
                        'loginKeyName': 'test-key',
                        'isFeeChargingMonitoring': False,
                        'publicIp': '203.0.113.10',
                        'privateIp': '10.0.0.10',
                        'serverImageName': 'centos-7.8-64',
                        'serverInstanceStatus': {'code': 'RUN', 'codeName': 'Server run state'},
                        'serverInstanceOperation': {'code': 'NULL', 'codeName': 'Server NULL OP'},
                        'serverInstanceStatusName': 'running',
                        'createDate': '2023-01-01T12:00:00+0900',
                        'uptime': '2023-01-01T12:00:00+0900',
                        'serverImageProductCode': 'SPSW0LINUX000046',
                        'serverProductCode': 'SPSVRSSD00000003',
                        'isProtectServerTermination': False,
                        'portForwardingPublicIp': '203.0.113.10',
                        'zone': {'zoneNo': '3', 'zoneName': 'KR-2', 'zoneCode': 'KR-2'},
                        'region': {'regionNo': '1', 'regionName': 'Korea', 'regionCode': 'KR'},
                        'baseBlockStorageDiskType': {'code': 'NET', 'codeName': 'Network Storage'},
                        'userData': '',
                        'accessControlGroupList': [
                            {
                                'accessControlGroupConfigurationNo': '4964',
                                'accessControlGroupName': 'ncloud-default-acg',
                                'accessControlGroupDescription': 'Default AccessControlGroup',
                                'isDefault': True,
                                'createDate': '2017-02-23T10:25:39+0900'
                            }
                        ]
                    },
                    {
                        'serverInstanceNo': '87654321',
                        'serverName': 'test-server-02',
                        'serverDescription': 'Another test server',
                        'cpuCount': 4,
                        'memorySize': 8589934592,
                        'baseBlockStorageSize': 53687091200,
                        'platformType': {'code': 'LNX64', 'codeName': 'Linux 64 Bit'},
                        'loginKeyName': 'test-key',
                        'isFeeChargingMonitoring': False,
                        'publicIp': '203.0.113.11',
                        'privateIp': '10.0.0.11',
                        'serverImageName': 'ubuntu-18.04-64',
                        'serverInstanceStatus': {'code': 'RUN', 'codeName': 'Server run state'},
                        'serverInstanceOperation': {'code': 'NULL', 'codeName': 'Server NULL OP'},
                        'serverInstanceStatusName': 'running',
                        'createDate': '2023-01-02T12:00:00+0900',
                        'uptime': '2023-01-02T12:00:00+0900',
                        'serverImageProductCode': 'SPSW0LINUX000032',
                        'serverProductCode': 'SPSVRSSD00000011',
                        'isProtectServerTermination': False,
                        'portForwardingPublicIp': '203.0.113.11',
                        'zone': {'zoneNo': '3', 'zoneName': 'KR-2', 'zoneCode': 'KR-2'},
                        'region': {'regionNo': '1', 'regionName': 'Korea', 'regionCode': 'KR'},
                        'baseBlockStorageDiskType': {'code': 'NET', 'codeName': 'Network Storage'},
                        'userData': '',
                        'accessControlGroupList': [
                            {
                                'accessControlGroupConfigurationNo': '4964',
                                'accessControlGroupName': 'ncloud-default-acg',
                                'accessControlGroupDescription': 'Default AccessControlGroup',
                                'isDefault': True,
                                'createDate': '2017-02-23T10:25:39+0900'
                            }
                        ]
                    }
                ]
            }
        }
    
    def get_mock_ncpgov_server_response(self) -> Dict[str, Any]:
        """Get mock NCPGOV server list response."""
        # Similar structure to NCP but with gov-specific endpoints
        response = self.get_mock_ncp_server_response()
        # Modify for gov cloud specifics
        for server in response['getServerInstanceListResponse']['serverInstanceList']:
            server['serverName'] = server['serverName'].replace('test', 'gov-test')
            server['serverDescription'] = f"Government {server['serverDescription']}"
        
        return response
    
    def get_mock_cloudflare_dns_response(self) -> Dict[str, Any]:
        """Get mock CloudFlare DNS records response."""
        return {
            'success': True,
            'errors': [],
            'messages': [],
            'result': [
                {
                    'id': 'mock_record_id_1',
                    'zone_id': 'mock_zone_id_1',
                    'zone_name': 'example.com',
                    'name': 'example.com',
                    'type': 'A',
                    'content': '203.0.113.1',
                    'proxiable': True,
                    'proxied': False,
                    'ttl': 300,
                    'locked': False,
                    'meta': {
                        'auto_added': False,
                        'managed_by_apps': False,
                        'managed_by_argo_tunnel': False
                    },
                    'created_on': '2023-01-01T12:00:00.000000Z',
                    'modified_on': '2023-01-01T12:00:00.000000Z'
                },
                {
                    'id': 'mock_record_id_2',
                    'zone_id': 'mock_zone_id_1',
                    'zone_name': 'example.com',
                    'name': 'www.example.com',
                    'type': 'CNAME',
                    'content': 'example.com',
                    'proxiable': True,
                    'proxied': True,
                    'ttl': 1,
                    'locked': False,
                    'meta': {
                        'auto_added': False,
                        'managed_by_apps': False,
                        'managed_by_argo_tunnel': False
                    },
                    'created_on': '2023-01-01T12:00:00.000000Z',
                    'modified_on': '2023-01-01T12:00:00.000000Z'
                }
            ],
            'result_info': {
                'page': 1,
                'per_page': 20,
                'count': 2,
                'total_count': 2,
                'total_pages': 1
            }
        }


class MockClientFactory:
    """Factory for creating mock clients for different cloud platforms."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.response_provider = MockServiceResponseProvider()
    
    def create_mock_aws_session(self):
        """Create mock AWS boto3 session."""
        mock_session = Mock()
        
        # Mock EC2 client
        mock_ec2 = Mock()
        mock_ec2.describe_instances.return_value = self.response_provider.get_mock_aws_ec2_response()
        mock_ec2.describe_regions.return_value = {
            'Regions': [
                {'RegionName': 'us-east-1', 'Endpoint': 'ec2.us-east-1.amazonaws.com'},
                {'RegionName': 'us-west-2', 'Endpoint': 'ec2.us-west-2.amazonaws.com'},
                {'RegionName': 'ap-northeast-2', 'Endpoint': 'ec2.ap-northeast-2.amazonaws.com'}
            ]
        }
        
        # Mock S3 client
        mock_s3 = Mock()
        mock_s3.list_buckets.return_value = {
            'Buckets': [
                {'Name': 'test-bucket-1', 'CreationDate': '2023-01-01T12:00:00.000Z'},
                {'Name': 'test-bucket-2', 'CreationDate': '2023-01-02T12:00:00.000Z'}
            ]
        }
        
        # Configure session to return appropriate clients
        def mock_client(service_name, **kwargs):
            if service_name == 'ec2':
                return mock_ec2
            elif service_name == 's3':
                return mock_s3
            else:
                return Mock()
        
        mock_session.client = mock_client
        return mock_session
    
    def create_mock_ncp_client(self):
        """Create mock NCP client."""
        mock_client = Mock()
        
        # Mock server operations
        mock_client.get_server_instance_list.return_value = self.response_provider.get_mock_ncp_server_response()
        
        # Mock VPC operations
        mock_client.get_vpc_list.return_value = {
            'getVpcListResponse': {
                'requestId': 'mock-vpc-request-id',
                'returnCode': '0',
                'returnMessage': 'success',
                'totalRows': 1,
                'vpcList': [
                    {
                        'vpcNo': '12345',
                        'vpcName': 'test-vpc',
                        'ipv4CidrBlock': '10.0.0.0/16',
                        'vpcStatus': {'code': 'RUN', 'codeName': 'VPC run state'},
                        'regionCode': 'KR',
                        'createDate': '2023-01-01T12:00:00+0900'
                    }
                ]
            }
        }
        
        return mock_client
    
    def create_mock_ncpgov_client(self):
        """Create mock NCPGOV client."""
        mock_client = Mock()
        
        # Mock server operations (similar to NCP but with gov-specific responses)
        mock_client.get_server_instance_list.return_value = self.response_provider.get_mock_ncpgov_server_response()
        
        return mock_client
    
    def create_mock_cloudflare_client(self):
        """Create mock CloudFlare client."""
        mock_client = Mock()
        
        # Mock DNS operations
        mock_response = Mock()
        mock_response.json.return_value = self.response_provider.get_mock_cloudflare_dns_response()
        mock_response.status_code = 200
        
        mock_client.get.return_value = mock_response
        mock_client.post.return_value = mock_response
        mock_client.put.return_value = mock_response
        mock_client.delete.return_value = mock_response
        
        return mock_client


# Global instances for easy access
mock_config_provider = MockConfigProvider()
mock_credential_provider = MockCredentialProvider()
mock_response_provider = MockServiceResponseProvider()
mock_client_factory = MockClientFactory()


def get_mock_config(platform: str) -> Dict[str, Any]:
    """Get mock configuration for specified platform."""
    config_methods = {
        'aws': mock_config_provider.get_mock_aws_config,
        'azure': mock_config_provider.get_mock_azure_config,
        'gcp': mock_config_provider.get_mock_gcp_config,
        'oci': mock_config_provider.get_mock_oci_config,
        'ncp': mock_config_provider.get_mock_ncp_config,
        'ncpgov': mock_config_provider.get_mock_ncpgov_config,
        'cloudflare': mock_config_provider.get_mock_cloudflare_config
    }
    
    if platform in config_methods:
        return config_methods[platform]()
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def get_mock_client(platform: str):
    """Get mock client for specified platform."""
    client_methods = {
        'aws': mock_client_factory.create_mock_aws_session,
        'ncp': mock_client_factory.create_mock_ncp_client,
        'ncpgov': mock_client_factory.create_mock_ncpgov_client,
        'cloudflare': mock_client_factory.create_mock_cloudflare_client
    }
    
    if platform in client_methods:
        return client_methods[platform]()
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def get_mock_response(platform: str, service: str) -> Dict[str, Any]:
    """Get mock service response for specified platform and service."""
    if platform == 'aws' and service == 'ec2':
        return mock_response_provider.get_mock_aws_ec2_response()
    elif platform == 'ncp' and service == 'server':
        return mock_response_provider.get_mock_ncp_server_response()
    elif platform == 'ncpgov' and service == 'server':
        return mock_response_provider.get_mock_ncpgov_server_response()
    elif platform == 'cloudflare' and service == 'dns':
        return mock_response_provider.get_mock_cloudflare_dns_response()
    else:
        raise ValueError(f"Unsupported platform/service: {platform}/{service}")