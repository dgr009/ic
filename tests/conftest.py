"""
Pytest configuration and fixtures for IC CLI tests.

Enhanced for CI/CD environments with graceful handling of missing configuration files
and cloud credentials. Provides mock configurations and environment setup for testing
without requiring live cloud services.
"""

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add project root to path for common modules
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest


def pytest_configure(config):
    """Configure pytest for CI/CD environments."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "requires_config: mark test as requiring configuration files"
    )
    config.addinivalue_line(
        "markers", "requires_credentials: mark test as requiring cloud credentials"
    )
    config.addinivalue_line(
        "markers", "ci_safe: mark test as safe to run in CI/CD environments"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection for CI/CD environments."""
    # Check if running in CI environment
    is_ci = os.environ.get('CI', '').lower() == 'true' or os.environ.get('GITHUB_ACTIONS', '').lower() == 'true'
    
    if is_ci:
        # Skip tests that require configuration files or credentials in CI
        skip_config = pytest.mark.skip(reason="Skipping config-dependent test in CI environment")
        skip_credentials = pytest.mark.skip(reason="Skipping credential-dependent test in CI environment")
        
        for item in items:
            if "requires_config" in item.keywords:
                item.add_marker(skip_config)
            if "requires_credentials" in item.keywords:
                item.add_marker(skip_credentials)


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager for testing."""
    with patch('ic.config.manager.ConfigManager') as mock:
        # Set up default mock behavior
        mock_instance = Mock()
        mock.return_value = mock_instance
        
        # Mock default configuration
        mock_instance.load_config.return_value = {
            'version': '1.0',
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'file_path': '/tmp/ic_test.log',
                'max_files': 10,
                'mask_sensitive': True
            },
            'aws': {
                'accounts': ['123456789012'],
                'regions': ['us-east-1'],
                'max_workers': 5
            },
            'azure': {
                'subscriptions': ['sub-12345'],
                'locations': ['East US']
            },
            'gcp': {
                'projects': ['test-project'],
                'regions': ['us-central1']
            },
            'security': {
                'sensitive_keys': ['password', 'token', 'key'],
                'mask_pattern': '***MASKED***'
            }
        }
        
        yield mock


@pytest.fixture
def mock_security_manager():
    """Mock SecurityManager for testing."""
    with patch('ic.config.security.SecurityManager') as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        
        # Mock security validation
        mock_instance.validate_config_security.return_value = []
        mock_instance.mask_sensitive_data.side_effect = lambda x: x
        
        yield mock


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create example config files
    (config_dir / "default.yaml").write_text("""
version: "1.0"
logging:
  console_level: "ERROR"
  file_level: "INFO"
  max_files: 10
aws:
  regions: ["us-east-1"]
  max_workers: 5
azure:
  locations: ["East US"]
gcp:
  regions: ["us-central1"]
security:
  sensitive_keys: ["password", "token", "key"]
  mask_pattern: "***MASKED***"
""")
    
    (config_dir / "secrets.yaml").write_text("""
aws:
  accounts: ["123456789012"]
azure:
  subscription_id: "sub-12345"
gcp:
  project_id: "test-project"
""")
    
    return config_dir


@pytest.fixture
def mock_environment():
    """Mock environment variables for testing."""
    env_vars = {
        'AWS_PROFILE': 'test-profile',
        'AWS_REGION': 'us-east-1',
        'AZURE_SUBSCRIPTION_ID': 'sub-12345',
        'GCP_PROJECT_ID': 'test-project',
        'IC_LOG_LEVEL': 'ERROR'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_aws_session():
    """Mock AWS boto3 session for testing."""
    with patch('boto3.Session') as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock AWS clients
        mock_ec2_client = Mock()
        mock_rds_client = Mock()
        mock_s3_client = Mock()
        
        def mock_client(service_name, **kwargs):
            if service_name == 'ec2':
                return mock_ec2_client
            elif service_name == 'rds':
                return mock_rds_client
            elif service_name == 's3':
                return mock_s3_client
            else:
                return Mock()
        
        mock_session.client = mock_client
        
        # Mock EC2 responses
        mock_ec2_client.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'InstanceType': 't3.micro',
                            'State': {'Name': 'running'},
                            'Tags': [{'Key': 'Name', 'Value': 'test-instance'}]
                        }
                    ]
                }
            ]
        }
        
        # Mock RDS responses
        mock_rds_client.describe_db_instances.return_value = {
            'DBInstances': [
                {
                    'DBInstanceIdentifier': 'test-db',
                    'DBInstanceClass': 'db.t3.micro',
                    'Engine': 'mysql',
                    'DBInstanceStatus': 'available'
                }
            ]
        }
        
        # Mock S3 responses
        mock_s3_client.list_buckets.return_value = {
            'Buckets': [
                {
                    'Name': 'test-bucket',
                    'CreationDate': '2023-01-01T00:00:00Z'
                }
            ]
        }
        
        yield mock_session


@pytest.fixture
def mock_oci_config():
    """Mock OCI configuration for testing."""
    mock_config = {
        'tenancy': 'ocid1.tenancy.oc1..test',
        'user': 'ocid1.user.oc1..test',
        'fingerprint': 'test-fingerprint',
        'key_file': '/path/to/test.pem',
        'region': 'us-ashburn-1'
    }
    
    with patch('oci.config.from_file') as mock_config_from_file:
        mock_config_from_file.return_value = mock_config
        
        with patch('oci.identity.IdentityClient') as mock_identity_client_class:
            mock_identity_client = Mock()
            mock_identity_client_class.return_value = mock_identity_client
            
            # Mock compartment data
            mock_compartment = Mock()
            mock_compartment.id = 'ocid1.compartment.oc1..test'
            mock_compartment.name = 'Test Compartment'
            mock_compartment.lifecycle_state = 'ACTIVE'
            
            mock_identity_client.list_compartments.return_value.data = [mock_compartment]
            
            yield mock_config


@pytest.fixture
def mock_cloudflare_api():
    """Mock CloudFlare API for testing."""
    with patch('requests.get') as mock_get:
        with patch('requests.post') as mock_post:
            # Mock successful API responses
            mock_response = Mock()
            mock_response.json.return_value = {
                'success': True,
                'result': [
                    {
                        'id': 'zone123',
                        'name': 'example.com',
                        'status': 'active'
                    }
                ]
            }
            mock_response.status_code = 200
            
            mock_get.return_value = mock_response
            mock_post.return_value = mock_response
            
            yield mock_response


@pytest.fixture
def mock_ssh_client():
    """Mock SSH client for testing."""
    with patch('paramiko.SSHClient') as mock_ssh_client_class:
        mock_ssh_client = Mock()
        mock_ssh_client_class.return_value = mock_ssh_client
        
        # Mock SSH command execution
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        
        mock_stdout.read.return_value = b'Linux test-server 5.4.0-74-generic'
        mock_stderr.read.return_value = b''
        
        mock_ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        mock_ssh_client.connect.return_value = None
        
        yield mock_ssh_client


@pytest.fixture
def ci_environment():
    """Fixture to simulate CI/CD environment."""
    ci_env_vars = {
        'CI': 'true',
        'GITHUB_ACTIONS': 'true',
        'RUNNER_OS': 'Linux',
        'HOME': '/home/runner'
    }
    
    with patch.dict(os.environ, ci_env_vars):
        # Mock missing config directories
        with patch('pathlib.Path.exists') as mock_exists:
            with patch('pathlib.Path.is_file') as mock_is_file:
                # Config files don't exist in CI
                mock_exists.return_value = False
                mock_is_file.return_value = False
                
                yield ci_env_vars


@pytest.fixture
def no_rich_environment():
    """Fixture to simulate environment without Rich library."""
    with patch('common.progress_decorator.RICH_AVAILABLE', False):
        yield


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create temporary log directory for testing."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Automatically cleanup test files after each test."""
    yield
    
    # Cleanup any temporary files created during tests
    temp_files = [
        '/tmp/ic_test.log',
        '/tmp/test_config.yaml',
        '/tmp/test_secrets.yaml'
    ]
    
    for temp_file in temp_files:
        try:
            Path(temp_file).unlink(missing_ok=True)
        except Exception:
            pass  # Ignore cleanup errors