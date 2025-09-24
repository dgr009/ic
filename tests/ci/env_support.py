"""
Environment Variable Support for CI Testing

Comprehensive environment variable fallback system for CI testing that allows
configuration through environment variables when config files are not available.

Requirements: 3.3, 3.5, 7.4 - Environment variable fallback system for CI testing
"""

import os
import sys
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
import logging
import json


class EnvironmentVariableManager:
    """Manages environment variables for CI testing with validation and fallbacks."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._original_env: Dict[str, str] = {}
        self._ci_env_vars: Dict[str, str] = {}
    
    def setup_ci_environment_variables(self) -> Dict[str, str]:
        """Set up comprehensive environment variables for CI testing."""
        self.logger.info("Setting up CI environment variables...")
        
        # Store original environment for restoration
        self._original_env = dict(os.environ)
        
        # Core CI configuration
        ci_vars = {
            # CI Detection
            'CI': 'true',
            'IC_CI_MODE': 'true',
            'IC_TEST_MODE': 'true',
            'IC_MOCK_MODE': 'true',
            
            # Logging Configuration
            'IC_LOG_LEVEL': 'ERROR',
            'IC_FILE_LOG_LEVEL': 'INFO',
            'IC_LOG_FILE': '/tmp/ic_ci.log',
            'IC_LOG_MAX_FILES': '3',
            'IC_MASK_SENSITIVE': 'true',
            'IC_DISABLE_PROGRESS_BARS': 'true',
            'IC_FORCE_COLOR': 'false',
            
            # Performance Configuration
            'IC_MAX_WORKERS': '5',
            'IC_TIMEOUT': '30',
            'IC_RETRY_ATTEMPTS': '2',
            'IC_RETRY_DELAY': '1.0',
            'IC_MAX_CONCURRENT': '10',
            
            # Security Configuration
            'IC_MASK_PATTERN': '***MASKED***',
            'IC_SENSITIVE_KEYS': 'password,token,key,secret,access_key,secret_key',
            'IC_LOG_SENSITIVE': 'false',
            'IC_DISABLE_TELEMETRY': 'true',
            
            # Test Configuration
            'IC_OFFLINE_MODE': 'true',
            'IC_MOCK_EXTERNAL_CALLS': 'true',
            'IC_DISABLE_INTERACTIVE': 'true',
            'IC_AUTO_CLEANUP': 'true',
            
            # AWS Configuration
            'AWS_ACCESS_KEY_ID': 'AKIAIOSFODNN7EXAMPLE',
            'AWS_SECRET_ACCESS_KEY': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            'AWS_DEFAULT_REGION': 'us-east-1',
            'AWS_REGION': 'us-east-1',
            'AWS_REGIONS': 'us-east-1,us-west-2,ap-northeast-2',
            'AWS_ACCOUNTS': '123456789012,210987654321',
            'AWS_MAX_WORKERS': '5',
            'AWS_TIMEOUT': '30',
            'AWS_PROFILES': 'default,production',
            'AWS_DEFAULT_OUTPUT': 'json',
            'AWS_PAGER': '',
            
            # Azure Configuration
            'AZURE_CLIENT_ID': '12345678-1234-1234-1234-123456789012',
            'AZURE_CLIENT_SECRET': 'mock-client-secret-value',
            'AZURE_TENANT_ID': '87654321-4321-4321-4321-210987654321',
            'AZURE_SUBSCRIPTION_ID': 'abcdef12-3456-7890-abcd-ef1234567890',
            'AZURE_LOCATIONS': 'East US,West US 2,Central US',
            'AZURE_DEFAULT_LOCATION': 'East US',
            'AZURE_SUBSCRIPTIONS': 'sub-12345,sub-67890',
            'AZURE_MAX_WORKERS': '5',
            'AZURE_TIMEOUT': '30',
            'AZURE_CORE_OUTPUT': 'json',
            
            # GCP Configuration
            'GOOGLE_APPLICATION_CREDENTIALS': '/tmp/mock-gcp-credentials.json',
            'GCP_PROJECT': 'mock-gcp-project-12345',
            'GCP_REGIONS': 'us-central1,us-east1,europe-west1',
            'GCP_DEFAULT_REGION': 'us-central1',
            'GCP_PROJECTS': 'mock-gcp-project-12345,mock-gcp-project-67890',
            'GCP_MAX_WORKERS': '5',
            'GCP_TIMEOUT': '30',
            'GOOGLE_CLOUD_PROJECT': 'mock-gcp-project-12345',
            
            # OCI Configuration
            'OCI_CONFIG_FILE': '/tmp/mock-oci-config',
            'OCI_CONFIG_PROFILE': 'DEFAULT',
            'OCI_REGIONS': 'us-ashburn-1,us-phoenix-1,eu-frankfurt-1',
            'OCI_DEFAULT_REGION': 'us-ashburn-1',
            'OCI_COMPARTMENTS': 'ocid1.compartment.oc1..mock1,ocid1.compartment.oc1..mock2',
            'OCI_MAX_WORKERS': '5',
            'OCI_TIMEOUT': '30',
            
            # NCP Configuration
            'NCP_ACCESS_KEY': 'MOCK_NCP_ACCESS_KEY_12345',
            'NCP_SECRET_KEY': 'MOCK_NCP_SECRET_KEY_67890',
            'NCP_REGION': 'KR',
            'NCP_ENDPOINT': 'https://ncloud.apigw.ntruss.com',
            'NCP_TIMEOUT': '30',
            'NCP_MAX_RETRIES': '3',
            'NCP_RETRY_DELAY': '1.0',
            'NCP_LOG_LEVEL': 'INFO',
            'NCP_LOG_REQUESTS': 'false',
            'NCP_SERVER_ENDPOINT': 'https://ncloud.apigw.ntruss.com/vserver/v2',
            'NCP_VPC_ENDPOINT': 'https://ncloud.apigw.ntruss.com/vpc/v2',
            'NCP_STORAGE_ENDPOINT': 'https://ncloud.apigw.ntruss.com/vnas/v2',
            'NCP_LB_ENDPOINT': 'https://ncloud.apigw.ntruss.com/vloadbalancer/v2',
            
            # NCPGOV Configuration
            'NCPGOV_ACCESS_KEY': 'MOCK_NCPGOV_ACCESS_KEY_12345',
            'NCPGOV_SECRET_KEY': 'MOCK_NCPGOV_SECRET_KEY_67890',
            'NCPGOV_REGION': 'KR',
            'NCPGOV_ENDPOINT': 'https://ncloud.apigw.gov-ntruss.com',
            'NCPGOV_TIMEOUT': '30',
            'NCPGOV_MAX_RETRIES': '3',
            'NCPGOV_RETRY_DELAY': '1.0',
            'NCPGOV_LOG_LEVEL': 'INFO',
            'NCPGOV_LOG_REQUESTS': 'false',
            'NCPGOV_SERVER_ENDPOINT': 'https://ncloud.apigw.gov-ntruss.com/vserver/v2',
            'NCPGOV_VPC_ENDPOINT': 'https://ncloud.apigw.gov-ntruss.com/vpc/v2',
            'NCPGOV_STORAGE_ENDPOINT': 'https://ncloud.apigw.gov-ntruss.com/vnas/v2',
            'NCPGOV_LB_ENDPOINT': 'https://ncloud.apigw.gov-ntruss.com/vloadbalancer/v2',
            
            # CloudFlare Configuration
            'CLOUDFLARE_API_TOKEN': 'mock_cloudflare_api_token_12345',
            'CLOUDFLARE_EMAIL': 'mock@example.com',
            'CLOUDFLARE_API_KEY': 'mock_cloudflare_api_key_67890',
            
            # SSH Configuration
            'SSH_TIMEOUT': '30',
            'SSH_MAX_RETRIES': '3',
            'SSH_KEY_PATH': '/tmp/mock_ssh_key',
            
            # Test Data Paths
            'IC_TEST_DATA_PATH': '/tmp/ic_ci_data',
            'IC_MOCK_DATA_PATH': '/tmp/ic_ci_mock_data',
            'IC_CACHE_PATH': '/tmp/ic_ci_cache',
            'IC_CONFIG_PATH': '/tmp/ic_ci_configs'
        }
        
        # Set environment variables
        for key, value in ci_vars.items():
            os.environ[key] = value
            self._ci_env_vars[key] = value
        
        self.logger.info(f"Set {len(ci_vars)} CI environment variables")
        return ci_vars
    
    def get_environment_config(self, platform: str) -> Dict[str, Any]:
        """Get configuration for specified platform from environment variables."""
        if platform == 'ic':
            return self._get_ic_env_config()
        elif platform == 'aws':
            return self._get_aws_env_config()
        elif platform == 'azure':
            return self._get_azure_env_config()
        elif platform == 'gcp':
            return self._get_gcp_env_config()
        elif platform == 'oci':
            return self._get_oci_env_config()
        elif platform == 'ncp':
            return self._get_ncp_env_config()
        elif platform == 'ncpgov':
            return self._get_ncpgov_env_config()
        elif platform == 'cloudflare':
            return self._get_cloudflare_env_config()
        else:
            raise ValueError(f"Unsupported platform: {platform}")
    
    def _get_ic_env_config(self) -> Dict[str, Any]:
        """Get IC configuration from environment variables."""
        return {
            'version': '1.0',
            'logging': {
                'console_level': os.getenv('IC_LOG_LEVEL', 'ERROR'),
                'file_level': os.getenv('IC_FILE_LOG_LEVEL', 'INFO'),
                'file_path': os.getenv('IC_LOG_FILE', '/tmp/ic_ci.log'),
                'max_files': int(os.getenv('IC_LOG_MAX_FILES', '3')),
                'mask_sensitive': os.getenv('IC_MASK_SENSITIVE', 'true').lower() == 'true'
            },
            'performance': {
                'max_workers': int(os.getenv('IC_MAX_WORKERS', '5')),
                'timeout': int(os.getenv('IC_TIMEOUT', '30')),
                'retry_attempts': int(os.getenv('IC_RETRY_ATTEMPTS', '2')),
                'retry_delay': float(os.getenv('IC_RETRY_DELAY', '1.0')),
                'max_concurrent': int(os.getenv('IC_MAX_CONCURRENT', '10'))
            },
            'security': {
                'mask_pattern': os.getenv('IC_MASK_PATTERN', '***MASKED***'),
                'sensitive_keys': os.getenv('IC_SENSITIVE_KEYS', 'password,token,key,secret').split(','),
                'log_sensitive_data': os.getenv('IC_LOG_SENSITIVE', 'false').lower() == 'true'
            },
            'test': {
                'ci_mode': os.getenv('IC_CI_MODE', 'false').lower() == 'true',
                'mock_mode': os.getenv('IC_MOCK_MODE', 'false').lower() == 'true',
                'offline_mode': os.getenv('IC_OFFLINE_MODE', 'false').lower() == 'true',
                'disable_interactive': os.getenv('IC_DISABLE_INTERACTIVE', 'false').lower() == 'true'
            }
        }
    
    def _get_aws_env_config(self) -> Dict[str, Any]:
        """Get AWS configuration from environment variables."""
        return {
            'access_key_id': os.getenv('AWS_ACCESS_KEY_ID', ''),
            'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY', ''),
            'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
            'regions': os.getenv('AWS_REGIONS', 'us-east-1').split(','),
            'accounts': os.getenv('AWS_ACCOUNTS', '123456789012').split(','),
            'profiles': os.getenv('AWS_PROFILES', 'default').split(','),
            'max_workers': int(os.getenv('AWS_MAX_WORKERS', '5')),
            'timeout': int(os.getenv('AWS_TIMEOUT', '30')),
            'output_format': os.getenv('AWS_DEFAULT_OUTPUT', 'json')
        }
    
    def _get_azure_env_config(self) -> Dict[str, Any]:
        """Get Azure configuration from environment variables."""
        return {
            'client_id': os.getenv('AZURE_CLIENT_ID', ''),
            'client_secret': os.getenv('AZURE_CLIENT_SECRET', ''),
            'tenant_id': os.getenv('AZURE_TENANT_ID', ''),
            'subscription_id': os.getenv('AZURE_SUBSCRIPTION_ID', ''),
            'locations': os.getenv('AZURE_LOCATIONS', 'East US').split(','),
            'default_location': os.getenv('AZURE_DEFAULT_LOCATION', 'East US'),
            'subscriptions': os.getenv('AZURE_SUBSCRIPTIONS', 'default-sub').split(','),
            'max_workers': int(os.getenv('AZURE_MAX_WORKERS', '5')),
            'timeout': int(os.getenv('AZURE_TIMEOUT', '30'))
        }
    
    def _get_gcp_env_config(self) -> Dict[str, Any]:
        """Get GCP configuration from environment variables."""
        return {
            'credentials_file': os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''),
            'project': os.getenv('GCP_PROJECT', ''),
            'regions': os.getenv('GCP_REGIONS', 'us-central1').split(','),
            'default_region': os.getenv('GCP_DEFAULT_REGION', 'us-central1'),
            'projects': os.getenv('GCP_PROJECTS', 'default-project').split(','),
            'max_workers': int(os.getenv('GCP_MAX_WORKERS', '5')),
            'timeout': int(os.getenv('GCP_TIMEOUT', '30'))
        }
    
    def _get_oci_env_config(self) -> Dict[str, Any]:
        """Get OCI configuration from environment variables."""
        return {
            'config_file': os.getenv('OCI_CONFIG_FILE', ''),
            'profile': os.getenv('OCI_CONFIG_PROFILE', 'DEFAULT'),
            'regions': os.getenv('OCI_REGIONS', 'us-ashburn-1').split(','),
            'default_region': os.getenv('OCI_DEFAULT_REGION', 'us-ashburn-1'),
            'compartments': os.getenv('OCI_COMPARTMENTS', 'default-compartment').split(','),
            'max_workers': int(os.getenv('OCI_MAX_WORKERS', '5')),
            'timeout': int(os.getenv('OCI_TIMEOUT', '30'))
        }
    
    def _get_ncp_env_config(self) -> Dict[str, Any]:
        """Get NCP configuration from environment variables."""
        return {
            'access_key': os.getenv('NCP_ACCESS_KEY', ''),
            'secret_key': os.getenv('NCP_SECRET_KEY', ''),
            'region': os.getenv('NCP_REGION', 'KR'),
            'endpoint': os.getenv('NCP_ENDPOINT', 'https://ncloud.apigw.ntruss.com'),
            'timeout': int(os.getenv('NCP_TIMEOUT', '30')),
            'max_retries': int(os.getenv('NCP_MAX_RETRIES', '3')),
            'retry_delay': float(os.getenv('NCP_RETRY_DELAY', '1.0')),
            'log_level': os.getenv('NCP_LOG_LEVEL', 'INFO'),
            'log_requests': os.getenv('NCP_LOG_REQUESTS', 'false').lower() == 'true',
            'services': {
                'server': os.getenv('NCP_SERVER_ENDPOINT', 'https://ncloud.apigw.ntruss.com/vserver/v2'),
                'vpc': os.getenv('NCP_VPC_ENDPOINT', 'https://ncloud.apigw.ntruss.com/vpc/v2'),
                'storage': os.getenv('NCP_STORAGE_ENDPOINT', 'https://ncloud.apigw.ntruss.com/vnas/v2'),
                'loadbalancer': os.getenv('NCP_LB_ENDPOINT', 'https://ncloud.apigw.ntruss.com/vloadbalancer/v2')
            }
        }
    
    def _get_ncpgov_env_config(self) -> Dict[str, Any]:
        """Get NCPGOV configuration from environment variables."""
        return {
            'access_key': os.getenv('NCPGOV_ACCESS_KEY', ''),
            'secret_key': os.getenv('NCPGOV_SECRET_KEY', ''),
            'region': os.getenv('NCPGOV_REGION', 'KR'),
            'endpoint': os.getenv('NCPGOV_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com'),
            'timeout': int(os.getenv('NCPGOV_TIMEOUT', '30')),
            'max_retries': int(os.getenv('NCPGOV_MAX_RETRIES', '3')),
            'retry_delay': float(os.getenv('NCPGOV_RETRY_DELAY', '1.0')),
            'log_level': os.getenv('NCPGOV_LOG_LEVEL', 'INFO'),
            'log_requests': os.getenv('NCPGOV_LOG_REQUESTS', 'false').lower() == 'true',
            'services': {
                'server': os.getenv('NCPGOV_SERVER_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com/vserver/v2'),
                'vpc': os.getenv('NCPGOV_VPC_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com/vpc/v2'),
                'storage': os.getenv('NCPGOV_STORAGE_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com/vnas/v2'),
                'loadbalancer': os.getenv('NCPGOV_LB_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com/vloadbalancer/v2')
            }
        }
    
    def _get_cloudflare_env_config(self) -> Dict[str, Any]:
        """Get CloudFlare configuration from environment variables."""
        return {
            'api_token': os.getenv('CLOUDFLARE_API_TOKEN', ''),
            'email': os.getenv('CLOUDFLARE_EMAIL', ''),
            'api_key': os.getenv('CLOUDFLARE_API_KEY', '')
        }
    
    def validate_environment_config(self, platform: str) -> Tuple[bool, List[str]]:
        """Validate environment configuration for specified platform."""
        try:
            config = self.get_environment_config(platform)
            issues = []
            
            if platform == 'ncp':
                if not config.get('access_key'):
                    issues.append("NCP_ACCESS_KEY not set")
                if not config.get('secret_key'):
                    issues.append("NCP_SECRET_KEY not set")
                if config.get('region') not in ['KR', 'US', 'JP']:
                    issues.append(f"Invalid NCP region: {config.get('region')}")
            
            elif platform == 'ncpgov':
                if not config.get('access_key'):
                    issues.append("NCPGOV_ACCESS_KEY not set")
                if not config.get('secret_key'):
                    issues.append("NCPGOV_SECRET_KEY not set")
                if config.get('region') != 'KR':
                    issues.append(f"Invalid NCPGOV region: {config.get('region')}")
                if 'gov-ntruss.com' not in config.get('endpoint', ''):
                    issues.append("NCPGOV endpoint must use gov-ntruss.com domain")
            
            elif platform == 'aws':
                if not config.get('access_key_id'):
                    issues.append("AWS_ACCESS_KEY_ID not set")
                if not config.get('secret_access_key'):
                    issues.append("AWS_SECRET_ACCESS_KEY not set")
            
            elif platform == 'azure':
                if not config.get('client_id'):
                    issues.append("AZURE_CLIENT_ID not set")
                if not config.get('tenant_id'):
                    issues.append("AZURE_TENANT_ID not set")
            
            elif platform == 'gcp':
                if not config.get('credentials_file') and not config.get('project'):
                    issues.append("GOOGLE_APPLICATION_CREDENTIALS or GCP_PROJECT not set")
            
            return len(issues) == 0, issues
            
        except Exception as e:
            return False, [f"Failed to validate {platform} config: {str(e)}"]
    
    def create_mock_credential_files(self) -> Dict[str, Path]:
        """Create mock credential files for platforms that require them."""
        self.logger.info("Creating mock credential files...")
        
        created_files = {}
        
        # Create mock GCP credentials file
        gcp_creds_path = Path('/tmp/mock-gcp-credentials.json')
        gcp_creds = {
            "type": "service_account",
            "project_id": "mock-gcp-project-12345",
            "private_key_id": "mock-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
            "client_email": "mock@mock-gcp-project-12345.iam.gserviceaccount.com",
            "client_id": "123456789012345678901",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        
        try:
            with open(gcp_creds_path, 'w') as f:
                json.dump(gcp_creds, f, indent=2)
            created_files['gcp_credentials'] = gcp_creds_path
            self.logger.info(f"Created mock GCP credentials: {gcp_creds_path}")
        except Exception as e:
            self.logger.warning(f"Failed to create GCP credentials file: {e}")
        
        # Create mock OCI config file
        oci_config_path = Path('/tmp/mock-oci-config')
        oci_config_content = """[DEFAULT]
user=ocid1.user.oc1..mock_user_ocid
fingerprint=aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99
key_file=/tmp/mock_oci_api_key.pem
tenancy=ocid1.tenancy.oc1..mock_tenancy_ocid
region=us-ashburn-1
"""
        
        try:
            with open(oci_config_path, 'w') as f:
                f.write(oci_config_content)
            created_files['oci_config'] = oci_config_path
            self.logger.info(f"Created mock OCI config: {oci_config_path}")
            
            # Create mock OCI private key
            oci_key_path = Path('/tmp/mock_oci_api_key.pem')
            oci_key_content = """-----BEGIN RSA PRIVATE KEY-----
MOCK_PRIVATE_KEY_CONTENT_FOR_TESTING_ONLY
-----END RSA PRIVATE KEY-----"""
            
            with open(oci_key_path, 'w') as f:
                f.write(oci_key_content)
            created_files['oci_key'] = oci_key_path
            
        except Exception as e:
            self.logger.warning(f"Failed to create OCI config files: {e}")
        
        # Create mock SSH key
        ssh_key_path = Path('/tmp/mock_ssh_key')
        ssh_key_content = """-----BEGIN OPENSSH PRIVATE KEY-----
MOCK_SSH_PRIVATE_KEY_CONTENT_FOR_TESTING_ONLY
-----END OPENSSH PRIVATE KEY-----"""
        
        try:
            with open(ssh_key_path, 'w') as f:
                f.write(ssh_key_content)
            # Set appropriate permissions
            ssh_key_path.chmod(0o600)
            created_files['ssh_key'] = ssh_key_path
            self.logger.info(f"Created mock SSH key: {ssh_key_path}")
        except Exception as e:
            self.logger.warning(f"Failed to create SSH key file: {e}")
        
        return created_files
    
    def restore_original_environment(self):
        """Restore original environment variables."""
        self.logger.info("Restoring original environment variables...")
        
        # Remove CI-specific variables
        for var in self._ci_env_vars.keys():
            if var in os.environ:
                del os.environ[var]
        
        # Restore original variables
        for key, value in self._original_env.items():
            os.environ[key] = value
        
        # Clear tracking dictionaries
        self._ci_env_vars.clear()
        self._original_env.clear()
        
        self.logger.info("Environment variables restored")
    
    def get_environment_summary(self) -> Dict[str, Any]:
        """Get summary of current environment configuration."""
        return {
            'ci_mode': os.getenv('IC_CI_MODE', 'false').lower() == 'true',
            'mock_mode': os.getenv('IC_MOCK_MODE', 'false').lower() == 'true',
            'test_mode': os.getenv('IC_TEST_MODE', 'false').lower() == 'true',
            'offline_mode': os.getenv('IC_OFFLINE_MODE', 'false').lower() == 'true',
            'log_level': os.getenv('IC_LOG_LEVEL', 'INFO'),
            'platforms_configured': {
                'aws': bool(os.getenv('AWS_ACCESS_KEY_ID')),
                'azure': bool(os.getenv('AZURE_CLIENT_ID')),
                'gcp': bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')),
                'oci': bool(os.getenv('OCI_CONFIG_FILE')),
                'ncp': bool(os.getenv('NCP_ACCESS_KEY')),
                'ncpgov': bool(os.getenv('NCPGOV_ACCESS_KEY')),
                'cloudflare': bool(os.getenv('CLOUDFLARE_API_TOKEN'))
            },
            'ci_variables_set': len(self._ci_env_vars),
            'total_env_variables': len(os.environ)
        }


# Global instance for easy access
env_manager = EnvironmentVariableManager()


def setup_ci_environment_variables() -> Dict[str, str]:
    """Convenience function to set up CI environment variables."""
    return env_manager.setup_ci_environment_variables()


def get_platform_config_from_env(platform: str) -> Dict[str, Any]:
    """Convenience function to get platform configuration from environment."""
    return env_manager.get_environment_config(platform)


def validate_platform_env_config(platform: str) -> Tuple[bool, List[str]]:
    """Convenience function to validate platform environment configuration."""
    return env_manager.validate_environment_config(platform)


def create_mock_credential_files() -> Dict[str, Path]:
    """Convenience function to create mock credential files."""
    return env_manager.create_mock_credential_files()


def restore_environment() -> None:
    """Convenience function to restore original environment."""
    env_manager.restore_original_environment()


def get_env_summary() -> Dict[str, Any]:
    """Convenience function to get environment summary."""
    return env_manager.get_environment_summary()