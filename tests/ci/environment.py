"""
CI Environment Detection and Setup

This module provides utilities for detecting CI environments and setting up
appropriate test configurations for GitHub Actions and other CI systems.

Requirements: 3.1, 3.2, 3.7 - CI environment detection and fallback mechanisms
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging


class CIEnvironmentDetector:
    """Detects and manages CI environment configurations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._ci_indicators = {
            'GITHUB_ACTIONS': 'GitHub Actions',
            'CI': 'Generic CI',
            'CONTINUOUS_INTEGRATION': 'Generic CI',
            'TRAVIS': 'Travis CI',
            'CIRCLECI': 'Circle CI',
            'JENKINS_URL': 'Jenkins',
            'GITLAB_CI': 'GitLab CI',
            'BUILDKITE': 'Buildkite',
            'TF_BUILD': 'Azure DevOps'
        }
    
    def is_ci_environment(self) -> bool:
        """Check if running in a CI environment."""
        return any(env_var in os.environ for env_var in self._ci_indicators.keys())
    
    def get_ci_provider(self) -> Optional[str]:
        """Get the name of the CI provider."""
        for env_var, provider in self._ci_indicators.items():
            if env_var in os.environ:
                return provider
        return None
    
    def is_github_actions(self) -> bool:
        """Check if running in GitHub Actions specifically."""
        return os.getenv('GITHUB_ACTIONS', '').lower() == 'true'
    
    def get_ci_info(self) -> Dict[str, Any]:
        """Get comprehensive CI environment information."""
        info = {
            'is_ci': self.is_ci_environment(),
            'provider': self.get_ci_provider(),
            'is_github_actions': self.is_github_actions(),
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'platform': sys.platform,
            'environment_variables': {}
        }
        
        # Collect relevant environment variables
        ci_env_vars = [
            'CI', 'GITHUB_ACTIONS', 'GITHUB_WORKFLOW', 'GITHUB_RUN_ID',
            'RUNNER_OS', 'RUNNER_ARCH', 'PYTHON_VERSION'
        ]
        
        for var in ci_env_vars:
            if var in os.environ:
                info['environment_variables'][var] = os.environ[var]
        
        return info


class MockConfigurationManager:
    """Manages mock configurations for CI testing."""
    
    def __init__(self, ci_detector: CIEnvironmentDetector):
        self.ci_detector = ci_detector
        self.logger = logging.getLogger(__name__)
        self.temp_dirs: List[Path] = []
        
    def create_mock_ic_config(self) -> Path:
        """Create a temporary IC configuration for CI testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix='ic_ci_config_'))
        self.temp_dirs.append(temp_dir)
        
        config_dir = temp_dir / '.ic' / 'config'
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create default.yaml
        default_config = {
            'version': '1.0',
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'file_path': str(temp_dir / 'logs' / 'ic.log'),
                'max_files': 5,
                'mask_sensitive': True
            },
            'aws': {
                'regions': ['us-east-1', 'us-west-2'],
                'default_region': 'us-east-1',
                'accounts': ['123456789012'],
                'max_workers': 10,
                'timeout': 30
            },
            'azure': {
                'locations': ['East US', 'West US 2'],
                'default_location': 'East US',
                'subscriptions': ['sub-12345'],
                'max_workers': 10
            },
            'gcp': {
                'regions': ['us-central1', 'us-east1'],
                'default_region': 'us-central1',
                'projects': ['project-12345'],
                'max_workers': 10
            },
            'oci': {
                'regions': ['us-ashburn-1', 'us-phoenix-1'],
                'default_region': 'us-ashburn-1',
                'compartments': ['ocid1.compartment.oc1..example'],
                'max_workers': 10
            },
            'security': {
                'mask_pattern': '***MASKED***',
                'sensitive_keys': ['password', 'token', 'key', 'secret'],
                'log_sensitive_data': False
            }
        }
        
        import yaml
        config_file = config_dir / 'default.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
        
        self.logger.info(f"Created mock IC config at {config_file}")
        return config_file
    
    def create_mock_ncp_config(self) -> Path:
        """Create a temporary NCP configuration for CI testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix='ncp_ci_config_'))
        self.temp_dirs.append(temp_dir)
        
        ncp_dir = temp_dir / '.ncp'
        ncp_dir.mkdir(parents=True, exist_ok=True)
        
        ncp_config = {
            'access_key': 'MOCK_NCP_ACCESS_KEY',
            'secret_key': 'MOCK_NCP_SECRET_KEY',
            'region': 'KR',
            'endpoint': 'https://ncloud.apigw.ntruss.com',
            'timeout': 30,
            'max_retries': 3
        }
        
        import yaml
        config_file = ncp_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(ncp_config, f, default_flow_style=False)
        
        self.logger.info(f"Created mock NCP config at {config_file}")
        return config_file
    
    def create_mock_ncpgov_config(self) -> Path:
        """Create a temporary NCPGOV configuration for CI testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix='ncpgov_ci_config_'))
        self.temp_dirs.append(temp_dir)
        
        ncpgov_dir = temp_dir / '.ncpgov'
        ncpgov_dir.mkdir(parents=True, exist_ok=True)
        
        ncpgov_config = {
            'access_key': 'MOCK_NCPGOV_ACCESS_KEY',
            'secret_key': 'MOCK_NCPGOV_SECRET_KEY',
            'region': 'KR',
            'endpoint': 'https://ncloud.apigw.gov-ntruss.com',
            'timeout': 30,
            'max_retries': 3
        }
        
        import yaml
        config_file = ncpgov_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(ncpgov_config, f, default_flow_style=False)
        
        self.logger.info(f"Created mock NCPGOV config at {config_file}")
        return config_file
    
    def setup_environment_variables(self) -> Dict[str, str]:
        """Set up environment variables for CI testing."""
        ci_env_vars = {
            # IC Configuration
            'IC_LOG_LEVEL': 'ERROR',
            'IC_CONFIG_PATH': '',  # Will be set by create_mock_ic_config
            
            # AWS Mock Configuration
            'AWS_ACCESS_KEY_ID': 'MOCK_AWS_ACCESS_KEY',
            'AWS_SECRET_ACCESS_KEY': 'MOCK_AWS_SECRET_KEY',
            'AWS_DEFAULT_REGION': 'us-east-1',
            'AWS_REGION': 'us-east-1',
            
            # Azure Mock Configuration
            'AZURE_CLIENT_ID': 'mock-client-id',
            'AZURE_CLIENT_SECRET': 'mock-client-secret',
            'AZURE_TENANT_ID': 'mock-tenant-id',
            'AZURE_SUBSCRIPTION_ID': 'mock-subscription-id',
            
            # GCP Mock Configuration
            'GOOGLE_APPLICATION_CREDENTIALS': '/tmp/mock-gcp-credentials.json',
            'GCP_PROJECT': 'mock-project-id',
            
            # OCI Mock Configuration
            'OCI_CONFIG_FILE': '/tmp/mock-oci-config',
            'OCI_CONFIG_PROFILE': 'DEFAULT',
            
            # NCP Mock Configuration
            'NCP_ACCESS_KEY': 'MOCK_NCP_ACCESS_KEY',
            'NCP_SECRET_KEY': 'MOCK_NCP_SECRET_KEY',
            'NCP_REGION': 'KR',
            
            # NCPGOV Mock Configuration
            'NCPGOV_ACCESS_KEY': 'MOCK_NCPGOV_ACCESS_KEY',
            'NCPGOV_SECRET_KEY': 'MOCK_NCPGOV_SECRET_KEY',
            'NCPGOV_REGION': 'KR',
            
            # Test Configuration
            'IC_TEST_MODE': 'true',
            'IC_MOCK_MODE': 'true',
            'IC_CI_MODE': 'true'
        }
        
        # Set environment variables
        for key, value in ci_env_vars.items():
            os.environ[key] = value
        
        self.logger.info(f"Set {len(ci_env_vars)} CI environment variables")
        return ci_env_vars
    
    def cleanup_temp_directories(self):
        """Clean up temporary directories created during testing."""
        import shutil
        
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    self.logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up {temp_dir}: {e}")
        
        self.temp_dirs.clear()


class FallbackConfigurationProvider:
    """Provides fallback configurations when config files are missing."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_fallback_ic_config(self) -> Dict[str, Any]:
        """Get fallback IC configuration."""
        return {
            'version': '1.0',
            'logging': {
                'console_level': os.getenv('IC_LOG_LEVEL', 'ERROR'),
                'file_level': 'INFO',
                'file_path': '/tmp/ic_ci.log',
                'max_files': 3,
                'mask_sensitive': True
            },
            'aws': {
                'regions': os.getenv('AWS_REGIONS', 'us-east-1').split(','),
                'default_region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
                'accounts': os.getenv('AWS_ACCOUNTS', '123456789012').split(','),
                'max_workers': int(os.getenv('AWS_MAX_WORKERS', '5')),
                'timeout': int(os.getenv('AWS_TIMEOUT', '30'))
            },
            'azure': {
                'locations': os.getenv('AZURE_LOCATIONS', 'East US').split(','),
                'default_location': os.getenv('AZURE_DEFAULT_LOCATION', 'East US'),
                'subscriptions': os.getenv('AZURE_SUBSCRIPTIONS', 'mock-sub').split(','),
                'max_workers': int(os.getenv('AZURE_MAX_WORKERS', '5'))
            },
            'gcp': {
                'regions': os.getenv('GCP_REGIONS', 'us-central1').split(','),
                'default_region': os.getenv('GCP_DEFAULT_REGION', 'us-central1'),
                'projects': os.getenv('GCP_PROJECTS', 'mock-project').split(','),
                'max_workers': int(os.getenv('GCP_MAX_WORKERS', '5'))
            },
            'oci': {
                'regions': os.getenv('OCI_REGIONS', 'us-ashburn-1').split(','),
                'default_region': os.getenv('OCI_DEFAULT_REGION', 'us-ashburn-1'),
                'compartments': os.getenv('OCI_COMPARTMENTS', 'mock-compartment').split(','),
                'max_workers': int(os.getenv('OCI_MAX_WORKERS', '5'))
            },
            'security': {
                'mask_pattern': '***MASKED***',
                'sensitive_keys': ['password', 'token', 'key', 'secret'],
                'log_sensitive_data': False
            }
        }
    
    def get_fallback_ncp_config(self) -> Dict[str, Any]:
        """Get fallback NCP configuration."""
        return {
            'access_key': os.getenv('NCP_ACCESS_KEY', 'MOCK_NCP_ACCESS_KEY'),
            'secret_key': os.getenv('NCP_SECRET_KEY', 'MOCK_NCP_SECRET_KEY'),
            'region': os.getenv('NCP_REGION', 'KR'),
            'endpoint': os.getenv('NCP_ENDPOINT', 'https://ncloud.apigw.ntruss.com'),
            'timeout': int(os.getenv('NCP_TIMEOUT', '30')),
            'max_retries': int(os.getenv('NCP_MAX_RETRIES', '3'))
        }
    
    def get_fallback_ncpgov_config(self) -> Dict[str, Any]:
        """Get fallback NCPGOV configuration."""
        return {
            'access_key': os.getenv('NCPGOV_ACCESS_KEY', 'MOCK_NCPGOV_ACCESS_KEY'),
            'secret_key': os.getenv('NCPGOV_SECRET_KEY', 'MOCK_NCPGOV_SECRET_KEY'),
            'region': os.getenv('NCPGOV_REGION', 'KR'),
            'endpoint': os.getenv('NCPGOV_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com'),
            'timeout': int(os.getenv('NCPGOV_TIMEOUT', '30')),
            'max_retries': int(os.getenv('NCPGOV_MAX_RETRIES', '3'))
        }


class CITestEnvironmentSetup:
    """Main class for setting up CI test environments."""
    
    def __init__(self):
        self.detector = CIEnvironmentDetector()
        self.mock_manager = MockConfigurationManager(self.detector)
        self.fallback_provider = FallbackConfigurationProvider()
        self.logger = logging.getLogger(__name__)
        
        # Configure logging for CI
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def setup_ci_environment(self) -> Dict[str, Any]:
        """Set up complete CI test environment."""
        self.logger.info("Setting up CI test environment...")
        
        ci_info = self.detector.get_ci_info()
        self.logger.info(f"CI Environment: {ci_info}")
        
        # Set up environment variables
        env_vars = self.mock_manager.setup_environment_variables()
        
        # Create mock configurations if in CI
        config_paths = {}
        if self.detector.is_ci_environment():
            self.logger.info("CI environment detected, creating mock configurations...")
            
            try:
                config_paths['ic_config'] = self.mock_manager.create_mock_ic_config()
                config_paths['ncp_config'] = self.mock_manager.create_mock_ncp_config()
                config_paths['ncpgov_config'] = self.mock_manager.create_mock_ncpgov_config()
                
                # Update environment variables with config paths
                os.environ['IC_CONFIG_PATH'] = str(config_paths['ic_config'].parent)
                os.environ['NCP_CONFIG_PATH'] = str(config_paths['ncp_config'].parent)
                os.environ['NCPGOV_CONFIG_PATH'] = str(config_paths['ncpgov_config'].parent)
                
            except Exception as e:
                self.logger.warning(f"Failed to create mock configs: {e}")
                self.logger.info("Will use fallback configurations")
        
        setup_info = {
            'ci_info': ci_info,
            'environment_variables': env_vars,
            'config_paths': config_paths,
            'fallback_configs': {
                'ic': self.fallback_provider.get_fallback_ic_config(),
                'ncp': self.fallback_provider.get_fallback_ncp_config(),
                'ncpgov': self.fallback_provider.get_fallback_ncpgov_config()
            }
        }
        
        self.logger.info("CI test environment setup complete")
        return setup_info
    
    def cleanup(self):
        """Clean up CI test environment."""
        self.logger.info("Cleaning up CI test environment...")
        self.mock_manager.cleanup_temp_directories()
        
        # Remove CI-specific environment variables
        ci_vars_to_remove = [
            'IC_TEST_MODE', 'IC_MOCK_MODE', 'IC_CI_MODE',
            'IC_CONFIG_PATH', 'NCP_CONFIG_PATH', 'NCPGOV_CONFIG_PATH'
        ]
        
        for var in ci_vars_to_remove:
            if var in os.environ:
                del os.environ[var]
        
        self.logger.info("CI test environment cleanup complete")


# Global instance for easy access
ci_setup = CITestEnvironmentSetup()


def setup_ci_test_environment():
    """Convenience function to set up CI test environment."""
    return ci_setup.setup_ci_environment()


def cleanup_ci_test_environment():
    """Convenience function to clean up CI test environment."""
    ci_setup.cleanup()


def is_ci_environment():
    """Convenience function to check if running in CI."""
    return ci_setup.detector.is_ci_environment()


def get_ci_info():
    """Convenience function to get CI information."""
    return ci_setup.detector.get_ci_info()