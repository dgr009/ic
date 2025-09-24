"""
Fallback Configuration System for CI Testing

Provides fallback mechanisms when configuration files are missing or inaccessible
in CI environments. Implements environment variable-based configuration and
default values for all supported platforms.

Requirements: 3.2, 3.7 - Fallback mechanisms for missing configuration files
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import logging
import yaml


class EnvironmentVariableConfigLoader:
    """Loads configuration from environment variables with fallbacks."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def load_ic_config_from_env(self) -> Dict[str, Any]:
        """Load IC configuration from environment variables."""
        config = {
            'version': '1.0',
            'logging': {
                'console_level': os.getenv('IC_LOG_LEVEL', 'ERROR'),
                'file_level': os.getenv('IC_FILE_LOG_LEVEL', 'INFO'),
                'file_path': os.getenv('IC_LOG_FILE', '/tmp/ic_ci.log'),
                'max_files': int(os.getenv('IC_LOG_MAX_FILES', '5')),
                'mask_sensitive': os.getenv('IC_MASK_SENSITIVE', 'true').lower() == 'true'
            },
            'aws': {
                'regions': self._parse_list_env('AWS_REGIONS', ['us-east-1']),
                'default_region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
                'accounts': self._parse_list_env('AWS_ACCOUNTS', ['123456789012']),
                'max_workers': int(os.getenv('AWS_MAX_WORKERS', '10')),
                'timeout': int(os.getenv('AWS_TIMEOUT', '30')),
                'profiles': self._parse_list_env('AWS_PROFILES', ['default'])
            },
            'azure': {
                'locations': self._parse_list_env('AZURE_LOCATIONS', ['East US']),
                'default_location': os.getenv('AZURE_DEFAULT_LOCATION', 'East US'),
                'subscriptions': self._parse_list_env('AZURE_SUBSCRIPTIONS', ['mock-subscription']),
                'max_workers': int(os.getenv('AZURE_MAX_WORKERS', '10')),
                'timeout': int(os.getenv('AZURE_TIMEOUT', '30'))
            },
            'gcp': {
                'regions': self._parse_list_env('GCP_REGIONS', ['us-central1']),
                'default_region': os.getenv('GCP_DEFAULT_REGION', 'us-central1'),
                'projects': self._parse_list_env('GCP_PROJECTS', ['mock-project']),
                'max_workers': int(os.getenv('GCP_MAX_WORKERS', '10')),
                'timeout': int(os.getenv('GCP_TIMEOUT', '30'))
            },
            'oci': {
                'regions': self._parse_list_env('OCI_REGIONS', ['us-ashburn-1']),
                'default_region': os.getenv('OCI_DEFAULT_REGION', 'us-ashburn-1'),
                'compartments': self._parse_list_env('OCI_COMPARTMENTS', ['mock-compartment']),
                'max_workers': int(os.getenv('OCI_MAX_WORKERS', '10')),
                'timeout': int(os.getenv('OCI_TIMEOUT', '30'))
            },
            'security': {
                'mask_pattern': os.getenv('IC_MASK_PATTERN', '***MASKED***'),
                'sensitive_keys': self._parse_list_env('IC_SENSITIVE_KEYS', 
                    ['password', 'token', 'key', 'secret']),
                'log_sensitive_data': os.getenv('IC_LOG_SENSITIVE', 'false').lower() == 'true'
            },
            'performance': {
                'max_concurrent_operations': int(os.getenv('IC_MAX_CONCURRENT', '50')),
                'request_timeout': int(os.getenv('IC_REQUEST_TIMEOUT', '30')),
                'retry_attempts': int(os.getenv('IC_RETRY_ATTEMPTS', '3')),
                'retry_delay': float(os.getenv('IC_RETRY_DELAY', '1.0'))
            }
        }
        
        self.logger.info("Loaded IC configuration from environment variables")
        return config
    
    def load_ncp_config_from_env(self) -> Dict[str, Any]:
        """Load NCP configuration from environment variables."""
        config = {
            'access_key': os.getenv('NCP_ACCESS_KEY', 'MOCK_NCP_ACCESS_KEY'),
            'secret_key': os.getenv('NCP_SECRET_KEY', 'MOCK_NCP_SECRET_KEY'),
            'region': os.getenv('NCP_REGION', 'KR'),
            'endpoint': os.getenv('NCP_ENDPOINT', 'https://ncloud.apigw.ntruss.com'),
            'timeout': int(os.getenv('NCP_TIMEOUT', '30')),
            'max_retries': int(os.getenv('NCP_MAX_RETRIES', '3')),
            'retry_delay': float(os.getenv('NCP_RETRY_DELAY', '1.0')),
            'services': {
                'server': os.getenv('NCP_SERVER_ENDPOINT', 'https://ncloud.apigw.ntruss.com/vserver/v2'),
                'vpc': os.getenv('NCP_VPC_ENDPOINT', 'https://ncloud.apigw.ntruss.com/vpc/v2'),
                'storage': os.getenv('NCP_STORAGE_ENDPOINT', 'https://ncloud.apigw.ntruss.com/vnas/v2'),
                'loadbalancer': os.getenv('NCP_LB_ENDPOINT', 'https://ncloud.apigw.ntruss.com/vloadbalancer/v2')
            },
            'logging': {
                'level': os.getenv('NCP_LOG_LEVEL', 'INFO'),
                'enable_request_logging': os.getenv('NCP_LOG_REQUESTS', 'false').lower() == 'true'
            }
        }
        
        self.logger.info("Loaded NCP configuration from environment variables")
        return config
    
    def load_ncpgov_config_from_env(self) -> Dict[str, Any]:
        """Load NCPGOV configuration from environment variables."""
        config = {
            'access_key': os.getenv('NCPGOV_ACCESS_KEY', 'MOCK_NCPGOV_ACCESS_KEY'),
            'secret_key': os.getenv('NCPGOV_SECRET_KEY', 'MOCK_NCPGOV_SECRET_KEY'),
            'region': os.getenv('NCPGOV_REGION', 'KR'),
            'endpoint': os.getenv('NCPGOV_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com'),
            'timeout': int(os.getenv('NCPGOV_TIMEOUT', '30')),
            'max_retries': int(os.getenv('NCPGOV_MAX_RETRIES', '3')),
            'retry_delay': float(os.getenv('NCPGOV_RETRY_DELAY', '1.0')),
            'services': {
                'server': os.getenv('NCPGOV_SERVER_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com/vserver/v2'),
                'vpc': os.getenv('NCPGOV_VPC_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com/vpc/v2'),
                'storage': os.getenv('NCPGOV_STORAGE_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com/vnas/v2'),
                'loadbalancer': os.getenv('NCPGOV_LB_ENDPOINT', 'https://ncloud.apigw.gov-ntruss.com/vloadbalancer/v2')
            },
            'logging': {
                'level': os.getenv('NCPGOV_LOG_LEVEL', 'INFO'),
                'enable_request_logging': os.getenv('NCPGOV_LOG_REQUESTS', 'false').lower() == 'true'
            }
        }
        
        self.logger.info("Loaded NCPGOV configuration from environment variables")
        return config
    
    def _parse_list_env(self, env_var: str, default: List[str]) -> List[str]:
        """Parse comma-separated environment variable into list."""
        value = os.getenv(env_var)
        if value:
            return [item.strip() for item in value.split(',') if item.strip()]
        return default


class ConfigurationPathResolver:
    """Resolves configuration file paths with fallback hierarchy."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.home_dir = Path.home()
        self.project_dir = Path.cwd()
    
    def resolve_ic_config_paths(self) -> List[Path]:
        """Resolve IC configuration file paths in order of preference."""
        paths = [
            # Project-specific configuration
            self.project_dir / '.ic' / 'config' / 'default.yaml',
            self.project_dir / '.ic' / 'config' / 'config.yaml',
            
            # User home configuration
            self.home_dir / '.ic' / 'config' / 'default.yaml',
            self.home_dir / '.ic' / 'config' / 'config.yaml',
            
            # Legacy locations
            self.project_dir / 'config' / 'default.yaml',
            self.project_dir / 'default.yaml'
        ]
        
        # Filter to existing files
        existing_paths = [path for path in paths if path.exists()]
        
        if existing_paths:
            self.logger.info(f"Found IC config files: {[str(p) for p in existing_paths]}")
        else:
            self.logger.warning("No IC configuration files found, will use fallback")
        
        return existing_paths
    
    def resolve_ncp_config_paths(self) -> List[Path]:
        """Resolve NCP configuration file paths in order of preference."""
        paths = [
            # User home configuration (preferred)
            self.home_dir / '.ncp' / 'config.yaml',
            self.home_dir / '.ncp' / 'default.yaml',
            
            # Project-specific configuration
            self.project_dir / '.ncp' / 'config.yaml',
            self.project_dir / '.ncp' / 'default.yaml',
            
            # Legacy locations
            self.project_dir / 'ncp_config.yaml',
            self.project_dir / '.ncp.yaml'
        ]
        
        # Filter to existing files
        existing_paths = [path for path in paths if path.exists()]
        
        if existing_paths:
            self.logger.info(f"Found NCP config files: {[str(p) for p in existing_paths]}")
        else:
            self.logger.warning("No NCP configuration files found, will use fallback")
        
        return existing_paths
    
    def resolve_ncpgov_config_paths(self) -> List[Path]:
        """Resolve NCPGOV configuration file paths in order of preference."""
        paths = [
            # User home configuration (preferred)
            self.home_dir / '.ncpgov' / 'config.yaml',
            self.home_dir / '.ncpgov' / 'default.yaml',
            
            # Project-specific configuration
            self.project_dir / '.ncpgov' / 'config.yaml',
            self.project_dir / '.ncpgov' / 'default.yaml',
            
            # Legacy locations
            self.project_dir / 'ncpgov_config.yaml',
            self.project_dir / '.ncpgov.yaml'
        ]
        
        # Filter to existing files
        existing_paths = [path for path in paths if path.exists()]
        
        if existing_paths:
            self.logger.info(f"Found NCPGOV config files: {[str(p) for p in existing_paths]}")
        else:
            self.logger.warning("No NCPGOV configuration files found, will use fallback")
        
        return existing_paths


class FallbackConfigurationLoader:
    """Main fallback configuration loader that combines multiple strategies."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.env_loader = EnvironmentVariableConfigLoader()
        self.path_resolver = ConfigurationPathResolver()
    
    def load_ic_config(self) -> Dict[str, Any]:
        """Load IC configuration with fallback strategy."""
        # Try to load from files first
        config_paths = self.path_resolver.resolve_ic_config_paths()
        
        if config_paths:
            try:
                config = self._load_yaml_config(config_paths[0])
                self.logger.info(f"Loaded IC config from file: {config_paths[0]}")
                return config
            except Exception as e:
                self.logger.warning(f"Failed to load IC config from file: {e}")
        
        # Fallback to environment variables
        self.logger.info("Using environment variable fallback for IC config")
        return self.env_loader.load_ic_config_from_env()
    
    def load_ncp_config(self) -> Dict[str, Any]:
        """Load NCP configuration with fallback strategy."""
        # Try to load from files first
        config_paths = self.path_resolver.resolve_ncp_config_paths()
        
        if config_paths:
            try:
                config = self._load_yaml_config(config_paths[0])
                self.logger.info(f"Loaded NCP config from file: {config_paths[0]}")
                return config
            except Exception as e:
                self.logger.warning(f"Failed to load NCP config from file: {e}")
        
        # Fallback to environment variables
        self.logger.info("Using environment variable fallback for NCP config")
        return self.env_loader.load_ncp_config_from_env()
    
    def load_ncpgov_config(self) -> Dict[str, Any]:
        """Load NCPGOV configuration with fallback strategy."""
        # Try to load from files first
        config_paths = self.path_resolver.resolve_ncpgov_config_paths()
        
        if config_paths:
            try:
                config = self._load_yaml_config(config_paths[0])
                self.logger.info(f"Loaded NCPGOV config from file: {config_paths[0]}")
                return config
            except Exception as e:
                self.logger.warning(f"Failed to load NCPGOV config from file: {e}")
        
        # Fallback to environment variables
        self.logger.info("Using environment variable fallback for NCPGOV config")
        return self.env_loader.load_ncpgov_config_from_env()
    
    def _load_yaml_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not isinstance(config, dict):
                raise ValueError(f"Configuration file {config_path} does not contain a valid dictionary")
            
            return config
        
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file {config_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to read configuration file {config_path}: {e}")


class DefaultConfigurationProvider:
    """Provides default configurations when all other methods fail."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_default_ic_config(self) -> Dict[str, Any]:
        """Get minimal default IC configuration."""
        return {
            'version': '1.0',
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'file_path': '/tmp/ic_default.log',
                'max_files': 3,
                'mask_sensitive': True
            },
            'aws': {
                'regions': ['us-east-1'],
                'default_region': 'us-east-1',
                'accounts': ['123456789012'],
                'max_workers': 5,
                'timeout': 30
            },
            'azure': {
                'locations': ['East US'],
                'default_location': 'East US',
                'subscriptions': ['default-subscription'],
                'max_workers': 5,
                'timeout': 30
            },
            'gcp': {
                'regions': ['us-central1'],
                'default_region': 'us-central1',
                'projects': ['default-project'],
                'max_workers': 5,
                'timeout': 30
            },
            'oci': {
                'regions': ['us-ashburn-1'],
                'default_region': 'us-ashburn-1',
                'compartments': ['default-compartment'],
                'max_workers': 5,
                'timeout': 30
            },
            'security': {
                'mask_pattern': '***MASKED***',
                'sensitive_keys': ['password', 'token', 'key', 'secret'],
                'log_sensitive_data': False
            }
        }
    
    def get_default_ncp_config(self) -> Dict[str, Any]:
        """Get minimal default NCP configuration."""
        return {
            'access_key': 'DEFAULT_NCP_ACCESS_KEY',
            'secret_key': 'DEFAULT_NCP_SECRET_KEY',
            'region': 'KR',
            'endpoint': 'https://ncloud.apigw.ntruss.com',
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 1.0,
            'services': {
                'server': 'https://ncloud.apigw.ntruss.com/vserver/v2',
                'vpc': 'https://ncloud.apigw.ntruss.com/vpc/v2',
                'storage': 'https://ncloud.apigw.ntruss.com/vnas/v2'
            }
        }
    
    def get_default_ncpgov_config(self) -> Dict[str, Any]:
        """Get minimal default NCPGOV configuration."""
        return {
            'access_key': 'DEFAULT_NCPGOV_ACCESS_KEY',
            'secret_key': 'DEFAULT_NCPGOV_SECRET_KEY',
            'region': 'KR',
            'endpoint': 'https://ncloud.apigw.gov-ntruss.com',
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 1.0,
            'services': {
                'server': 'https://ncloud.apigw.gov-ntruss.com/vserver/v2',
                'vpc': 'https://ncloud.apigw.gov-ntruss.com/vpc/v2',
                'storage': 'https://ncloud.apigw.gov-ntruss.com/vnas/v2'
            }
        }


class ConfigurationValidator:
    """Validates configuration completeness and correctness."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_ic_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate IC configuration and return list of issues."""
        issues = []
        
        # Check required top-level sections
        required_sections = ['version', 'logging', 'aws', 'azure', 'gcp', 'oci', 'security']
        for section in required_sections:
            if section not in config:
                issues.append(f"Missing required section: {section}")
        
        # Validate logging section
        if 'logging' in config:
            logging_config = config['logging']
            required_logging_keys = ['console_level', 'file_level', 'file_path']
            for key in required_logging_keys:
                if key not in logging_config:
                    issues.append(f"Missing required logging key: {key}")
        
        # Validate platform sections
        for platform in ['aws', 'azure', 'gcp', 'oci']:
            if platform in config:
                platform_config = config[platform]
                if 'regions' not in platform_config or not platform_config['regions']:
                    issues.append(f"Platform {platform} missing or empty regions list")
        
        return issues
    
    def validate_ncp_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate NCP configuration and return list of issues."""
        issues = []
        
        # Check required keys
        required_keys = ['access_key', 'secret_key', 'region', 'endpoint']
        for key in required_keys:
            if key not in config:
                issues.append(f"Missing required NCP key: {key}")
            elif not config[key]:
                issues.append(f"Empty value for required NCP key: {key}")
        
        # Validate region
        if 'region' in config and config['region'] not in ['KR', 'US', 'JP']:
            issues.append(f"Invalid NCP region: {config['region']}")
        
        # Validate endpoint
        if 'endpoint' in config and not config['endpoint'].startswith('https://'):
            issues.append("NCP endpoint must use HTTPS")
        
        return issues
    
    def validate_ncpgov_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate NCPGOV configuration and return list of issues."""
        issues = []
        
        # Check required keys (same as NCP)
        required_keys = ['access_key', 'secret_key', 'region', 'endpoint']
        for key in required_keys:
            if key not in config:
                issues.append(f"Missing required NCPGOV key: {key}")
            elif not config[key]:
                issues.append(f"Empty value for required NCPGOV key: {key}")
        
        # Validate region
        if 'region' in config and config['region'] not in ['KR']:
            issues.append(f"Invalid NCPGOV region: {config['region']}")
        
        # Validate endpoint (must be gov endpoint)
        if 'endpoint' in config:
            endpoint = config['endpoint']
            if not endpoint.startswith('https://'):
                issues.append("NCPGOV endpoint must use HTTPS")
            elif 'gov-ntruss.com' not in endpoint:
                issues.append("NCPGOV endpoint must use gov-ntruss.com domain")
        
        return issues


# Global instances for easy access
fallback_loader = FallbackConfigurationLoader()
default_provider = DefaultConfigurationProvider()
config_validator = ConfigurationValidator()


def load_config_with_fallback(platform: str) -> Dict[str, Any]:
    """Load configuration for specified platform with full fallback chain."""
    if platform == 'ic':
        return fallback_loader.load_ic_config()
    elif platform == 'ncp':
        return fallback_loader.load_ncp_config()
    elif platform == 'ncpgov':
        return fallback_loader.load_ncpgov_config()
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def get_default_config(platform: str) -> Dict[str, Any]:
    """Get default configuration for specified platform."""
    if platform == 'ic':
        return default_provider.get_default_ic_config()
    elif platform == 'ncp':
        return default_provider.get_default_ncp_config()
    elif platform == 'ncpgov':
        return default_provider.get_default_ncpgov_config()
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def validate_config(platform: str, config: Dict[str, Any]) -> List[str]:
    """Validate configuration for specified platform."""
    if platform == 'ic':
        return config_validator.validate_ic_config(config)
    elif platform == 'ncp':
        return config_validator.validate_ncp_config(config)
    elif platform == 'ncpgov':
        return config_validator.validate_ncpgov_config(config)
    else:
        raise ValueError(f"Unsupported platform: {platform}")