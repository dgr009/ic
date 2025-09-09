"""
External configuration loader module for IC.

This module provides loading of external configuration files from various cloud providers.
"""

import configparser
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class ExternalConfigLoader:
    """
    Loads external configuration files from various sources.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize ExternalConfigLoader.
        
        Args:
            config_manager: Reference to ConfigManager instance
        """
        self.config_manager = config_manager
        self.external_configs: Dict[str, Any] = {}
    
    def load_all_external_configs(self) -> Dict[str, Any]:
        """
        Load all external configuration files.
        
        Returns:
            Dictionary containing all external configurations
        """
        external_configs = {}
        
        try:
            # Load AWS configuration
            aws_config = self.load_aws_config()
            if aws_config:
                external_configs['aws'] = aws_config
            
            # Load OCI configuration
            oci_config = self.load_oci_config()
            if oci_config:
                external_configs['oci'] = oci_config
            
            # Load SSH configuration
            ssh_config = self.load_ssh_config()
            if ssh_config:
                external_configs['ssh'] = ssh_config
            
            # Load CloudFlare configuration
            cf_config = self.load_cloudflare_config()
            if cf_config:
                external_configs['cloudflare'] = cf_config
                
        except Exception as e:
            logger.warning(f"Failed to load some external configurations: {e}")
        
        self.external_configs = external_configs
        return external_configs
    
    def load_aws_config(self) -> Dict[str, Any]:
        """
        Load AWS configuration from ~/.aws/config and ~/.aws/credentials.
        
        Returns:
            Dictionary containing AWS configuration
        """
        aws_config = {}
        
        # Load AWS config file
        aws_config_path = Path.home() / ".aws" / "config"
        if aws_config_path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(aws_config_path)
                
                profiles = {}
                for section_name in config.sections():
                    if section_name.startswith('profile '):
                        profile_name = section_name.split('profile ')[1]
                        profiles[profile_name] = dict(config[section_name])
                    elif section_name == 'default':
                        profiles['default'] = dict(config[section_name])
                
                if profiles:
                    aws_config['profiles'] = profiles
                    logger.debug(f"Loaded {len(profiles)} AWS profiles from config")
                    
            except Exception as e:
                logger.warning(f"Failed to load AWS config: {e}")
        else:
            logger.debug("AWS config file not found at ~/.aws/config")
        
        # Load AWS credentials file
        aws_creds_path = Path.home() / ".aws" / "credentials"
        if aws_creds_path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(aws_creds_path)
                
                credentials = {}
                for section_name in config.sections():
                    # Don't store actual credentials, just metadata
                    credentials[section_name] = {
                        'has_access_key': 'aws_access_key_id' in config[section_name],
                        'has_secret_key': 'aws_secret_access_key' in config[section_name],
                        'has_session_token': 'aws_session_token' in config[section_name]
                    }
                
                if credentials:
                    aws_config['credentials_profiles'] = credentials
                    logger.debug(f"Found {len(credentials)} AWS credential profiles")
                    
            except Exception as e:
                logger.warning(f"Failed to load AWS credentials metadata: {e}")
        else:
            logger.debug("AWS credentials file not found at ~/.aws/credentials")
        
        return aws_config
    
    def load_oci_config(self) -> Dict[str, Any]:
        """
        Load OCI configuration from ~/.oci/config.
        
        Returns:
            Dictionary containing OCI configuration
        """
        oci_config = {}
        
        oci_config_path = Path.home() / ".oci" / "config"
        if oci_config_path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(oci_config_path)
                
                profiles = {}
                for section_name in config.sections():
                    # Store non-sensitive configuration only
                    profile_config = {}
                    for key, value in config[section_name].items():
                        # Skip sensitive keys like private keys
                        if 'key' not in key.lower() or key.lower() in ['key_file', 'key_path']:
                            if key.lower() in ['key_file', 'key_path']:
                                # Just indicate that key file exists, don't store path
                                profile_config[key] = "***KEY_FILE_CONFIGURED***" if Path(value).exists() else "***KEY_FILE_MISSING***"
                            else:
                                profile_config[key] = value
                    
                    profiles[section_name] = profile_config
                
                if profiles:
                    oci_config['profiles'] = profiles
                    logger.debug(f"Loaded {len(profiles)} OCI profiles from config")
                    
            except Exception as e:
                logger.warning(f"Failed to load OCI config: {e}")
        else:
            logger.debug("OCI config file not found at ~/.oci/config")
        
        return oci_config
    
    def load_ssh_config(self) -> Dict[str, Any]:
        """
        Load SSH configuration from ~/.ssh/config.
        
        Returns:
            Dictionary containing SSH configuration
        """
        ssh_config = {}
        
        ssh_config_path = Path.home() / ".ssh" / "config"
        if ssh_config_path.exists():
            try:
                hosts = {}
                current_host = None
                
                with open(ssh_config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        if line.lower().startswith('host '):
                            current_host = line.split(' ', 1)[1]
                            hosts[current_host] = {}
                        elif current_host and ' ' in line:
                            key, value = line.split(' ', 1)
                            key_lower = key.lower()
                            
                            # Store configuration but mask sensitive information
                            if 'identityfile' in key_lower:
                                # Check if identity file exists
                                identity_path = Path(value).expanduser()
                                hosts[current_host][key_lower] = "***IDENTITY_FILE_CONFIGURED***" if identity_path.exists() else "***IDENTITY_FILE_MISSING***"
                            else:
                                hosts[current_host][key_lower] = value
                
                if hosts:
                    ssh_config['hosts'] = hosts
                    logger.debug(f"Loaded {len(hosts)} SSH host configurations")
                    
            except Exception as e:
                logger.warning(f"Failed to load SSH config: {e}")
        else:
            logger.debug("SSH config file not found at ~/.ssh/config")
        
        return ssh_config
    
    def load_cloudflare_config(self) -> Dict[str, Any]:
        """
        Load CloudFlare configuration from various possible locations.
        
        Returns:
            Dictionary containing CloudFlare configuration
        """
        cf_config = {}
        
        # Check for CloudFlare config in various locations
        possible_paths = [
            Path.home() / ".cloudflare" / "config",
            Path.home() / ".cloudflare" / "config.yaml",
            Path.home() / ".cloudflare" / "config.yml",
            Path("config") / "cloudflare.yaml",
            Path("config") / "cloudflare.yml"
        ]
        
        for cf_path in possible_paths:
            if cf_path.exists():
                try:
                    if cf_path.suffix.lower() in ['.yaml', '.yml']:
                        # Load YAML format
                        import yaml
                        with open(cf_path, 'r') as f:
                            cf_data = yaml.safe_load(f) or {}
                        
                        # Mask sensitive information
                        cf_config = self._mask_cloudflare_secrets(cf_data)
                        
                    else:
                        # Try to parse as simple key=value format
                        with open(cf_path, 'r') as f:
                            for line in f:
                                line = line.strip()
                                if '=' in line and not line.startswith('#'):
                                    key, value = line.split('=', 1)
                                    key = key.strip()
                                    value = value.strip()
                                    
                                    # Mask sensitive values
                                    if any(sensitive in key.lower() for sensitive in ['token', 'key', 'secret', 'password']):
                                        cf_config[key] = "***MASKED***"
                                    else:
                                        cf_config[key] = value
                    
                    if cf_config:
                        logger.debug(f"Loaded CloudFlare config from {cf_path}")
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to load CloudFlare config from {cf_path}: {e}")
        
        if not cf_config:
            logger.debug("No CloudFlare config file found")
        
        return cf_config
    
    def _mask_cloudflare_secrets(self, cf_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask sensitive information in CloudFlare configuration.
        
        Args:
            cf_data: CloudFlare configuration data
            
        Returns:
            Configuration with sensitive data masked
        """
        masked_data = {}
        
        for key, value in cf_data.items():
            if isinstance(value, dict):
                masked_data[key] = self._mask_cloudflare_secrets(value)
            elif isinstance(value, str) and any(sensitive in key.lower() for sensitive in ['token', 'key', 'secret', 'password']):
                if value:
                    masked_data[key] = "***MASKED***"
                else:
                    masked_data[key] = value
            else:
                masked_data[key] = value
        
        return masked_data
    
    def get_external_config_value(self, service: str, key_path: str, default: Any = None) -> Any:
        """
        Get a value from external configuration using dot notation.
        
        Args:
            service: Service name (aws, oci, ssh, cloudflare)
            key_path: Dot-separated path to configuration value
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        if service not in self.external_configs:
            return default
        
        keys = key_path.split('.')
        current = self.external_configs[service]
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def has_external_config(self, service: str) -> bool:
        """
        Check if external configuration exists for a service.
        
        Args:
            service: Service name to check
            
        Returns:
            True if external configuration exists
        """
        return service in self.external_configs and bool(self.external_configs[service])
    
    def get_aws_profile_names(self) -> list:
        """
        Get list of available AWS profile names.
        
        Returns:
            List of AWS profile names
        """
        aws_config = self.external_configs.get('aws', {})
        profiles = aws_config.get('profiles', {})
        return list(profiles.keys())
    
    def get_oci_profile_names(self) -> list:
        """
        Get list of available OCI profile names.
        
        Returns:
            List of OCI profile names
        """
        oci_config = self.external_configs.get('oci', {})
        profiles = oci_config.get('profiles', {})
        return list(profiles.keys())
    
    def get_ssh_host_names(self) -> list:
        """
        Get list of configured SSH host names.
        
        Returns:
            List of SSH host names
        """
        ssh_config = self.external_configs.get('ssh', {})
        hosts = ssh_config.get('hosts', {})
        return list(hosts.keys())
    
    def validate_external_configs(self) -> Dict[str, List[str]]:
        """
        Validate external configurations and return any issues found.
        
        Returns:
            Dictionary mapping service names to lists of validation issues
        """
        issues = {}
        
        # Validate AWS configuration
        aws_issues = self._validate_aws_config()
        if aws_issues:
            issues['aws'] = aws_issues
        
        # Validate OCI configuration
        oci_issues = self._validate_oci_config()
        if oci_issues:
            issues['oci'] = oci_issues
        
        # Validate SSH configuration
        ssh_issues = self._validate_ssh_config()
        if ssh_issues:
            issues['ssh'] = ssh_issues
        
        return issues
    
    def _validate_aws_config(self) -> List[str]:
        """Validate AWS configuration."""
        issues = []
        aws_config = self.external_configs.get('aws', {})
        
        if not aws_config:
            issues.append("No AWS configuration found")
            return issues
        
        profiles = aws_config.get('profiles', {})
        credentials = aws_config.get('credentials_profiles', {})
        
        if not profiles and not credentials:
            issues.append("No AWS profiles or credentials found")
        
        # Check for profiles without corresponding credentials
        for profile_name in profiles.keys():
            if profile_name not in credentials:
                issues.append(f"AWS profile '{profile_name}' has no corresponding credentials")
        
        return issues
    
    def _validate_oci_config(self) -> List[str]:
        """Validate OCI configuration."""
        issues = []
        oci_config = self.external_configs.get('oci', {})
        
        if not oci_config:
            issues.append("No OCI configuration found")
            return issues
        
        profiles = oci_config.get('profiles', {})
        
        for profile_name, profile_config in profiles.items():
            required_fields = ['user', 'fingerprint', 'tenancy', 'region']
            for field in required_fields:
                if field not in profile_config:
                    issues.append(f"OCI profile '{profile_name}' missing required field '{field}'")
            
            # Check if key file is configured and exists
            key_file_status = profile_config.get('key_file', '')
            if 'MISSING' in key_file_status:
                issues.append(f"OCI profile '{profile_name}' key file is missing")
        
        return issues
    
    def _validate_ssh_config(self) -> List[str]:
        """Validate SSH configuration."""
        issues = []
        ssh_config = self.external_configs.get('ssh', {})
        
        if not ssh_config:
            issues.append("No SSH configuration found")
            return issues
        
        hosts = ssh_config.get('hosts', {})
        
        for host_name, host_config in hosts.items():
            # Check if identity file exists
            identity_status = host_config.get('identityfile', '')
            if 'MISSING' in identity_status:
                issues.append(f"SSH host '{host_name}' identity file is missing")
        
        return issues