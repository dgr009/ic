"""
NCP Security Utilities

This module provides NCP-specific security utilities including sensitive data masking,
compliance validation, and security monitoring for both NCP and NCP Gov services.
"""

import re
import os
import json
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class NCPSensitiveDataMasker:
    """
    NCP-specific sensitive data masking utility.
    
    Provides enhanced masking for NCP and NCP Gov services with government
    compliance requirements and Korean data protection standards.
    """
    
    def __init__(self, mask_pattern: str = "***MASKED***"):
        """
        Initialize the data masker.
        
        Args:
            mask_pattern: Pattern to use for masking sensitive data
        """
        self.mask_pattern = mask_pattern
        self.ncp_sensitive_keys = [
            # NCP credentials
            "ncp_access_key", "ncp_secret_key", "access_key", "secret_key",
            "apigw_key", "api_gateway_key", "private_key", "public_key",
            
            # Network information
            "private_ip", "internal_ip", "vpc_id", "subnet_id", "security_group_id",
            "network_interface_id", "route_table_id",
            
            # Instance information
            "server_instance_no", "instance_id", "server_name", "hostname",
            
            # Database information
            "db_instance_id", "database_name", "db_username", "db_password",
            
            # Storage information
            "bucket_name", "object_key", "storage_account",
            
            # Personal information (Korean compliance)
            "주민등록번호", "resident_number", "ssn", "social_security_number",
            "전화번호", "phone_number", "mobile_number", "휴대폰번호",
            "이메일", "email_address", "email",
            "주소", "address", "location",
            
            # Financial information
            "계좌번호", "account_number", "card_number", "카드번호",
            "bank_account", "credit_card"
        ]
    
    def mask_ncp_data(self, data: Any) -> Any:
        """
        Mask NCP-specific sensitive data.
        
        Args:
            data: Data to mask (dict, list, str, or other)
            
        Returns:
            Data with NCP-specific sensitive information masked
        """
        if isinstance(data, dict):
            return self._mask_dict(data)
        elif isinstance(data, list):
            return [self.mask_ncp_data(item) for item in data]
        elif isinstance(data, str):
            return self._mask_string(data)
        else:
            return data
    
    def _mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data in dictionary."""
        masked = {}
        for key, value in data.items():
            if self._is_ncp_sensitive_key(key):
                masked[key] = self.mask_pattern
            else:
                masked[key] = self.mask_ncp_data(value)
        return masked
    
    def _is_ncp_sensitive_key(self, key: str) -> bool:
        """Check if key is NCP-sensitive."""
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self.ncp_sensitive_keys)
    
    def _mask_string(self, text: str) -> str:
        """Mask sensitive patterns in string."""
        if not isinstance(text, str):
            return text
        
        masked_text = text
        
        # NCP-specific patterns
        ncp_patterns = [
            # NCP Access Keys (typically 20 characters)
            (r'\b[A-Z0-9]{20}\b', self.mask_pattern),
            # NCP Secret Keys (base64-like, 40+ characters)
            (r'\b[A-Za-z0-9+/]{40,}={0,2}\b', self.mask_pattern),
            # VPC IDs
            (r'vpc-[a-zA-Z0-9]+', '***VPC_ID***'),
            # Subnet IDs
            (r'subnet-[a-zA-Z0-9]+', '***SUBNET_ID***'),
            # IP addresses
            (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '***IP_ADDRESS***'),
            # Korean phone numbers
            (r'\b01[016789]-?\d{3,4}-?\d{4}\b', '***PHONE***'),
            # Korean resident registration numbers
            (r'\b\d{6}-?[1-4]\d{6}\b', '***RRN***'),
            # Email addresses
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***EMAIL***'),
        ]
        
        for pattern, replacement in ncp_patterns:
            masked_text = re.sub(pattern, replacement, masked_text)
        
        return masked_text
    
    def mask_log_message(self, message: str) -> str:
        """
        Mask sensitive data in log messages with NCP-specific patterns.
        
        Args:
            message: Log message to mask
            
        Returns:
            Masked log message
        """
        if not isinstance(message, str):
            return str(message)
        
        masked_message = message
        
        # NCP credential patterns in logs
        log_patterns = [
            (r'(ncp[_-]?access[_-]?key[\s=:]+)[^\s]+', rf'\1{self.mask_pattern}'),
            (r'(ncp[_-]?secret[_-]?key[\s=:]+)[^\s]+', rf'\1{self.mask_pattern}'),
            (r'(access[_-]?key[\s=:]+)[^\s]+', rf'\1{self.mask_pattern}'),
            (r'(secret[_-]?key[\s=:]+)[^\s]+', rf'\1{self.mask_pattern}'),
            (r'(apigw[_-]?key[\s=:]+)[^\s]+', rf'\1{self.mask_pattern}'),
            (r'(private[_-]?ip[\s=:]+)[^\s]+', rf'\1{self.mask_pattern}'),
            (r'(vpc[_-]?id[\s=:]+)[^\s]+', rf'\1{self.mask_pattern}'),
            (r'(subnet[_-]?id[\s=:]+)[^\s]+', rf'\1{self.mask_pattern}'),
            (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', f'Bearer {self.mask_pattern}'),
            (r'Basic\s+[A-Za-z0-9+/]+=*', f'Basic {self.mask_pattern}'),
        ]
        
        for pattern, replacement in log_patterns:
            masked_message = re.sub(pattern, replacement, masked_message, flags=re.IGNORECASE)
        
        return masked_message


class NCPComplianceValidator:
    """
    NCP Government Cloud compliance validator.
    
    Validates configuration and operations against Korean government cloud
    compliance requirements and security standards.
    """
    
    def __init__(self):
        """Initialize compliance validator."""
        self.compliance_frameworks = {
            'ncp_gov': {
                'name': 'NCP Government Cloud Compliance',
                'requirements': {
                    'encryption_enabled': 'Data encryption must be enabled',
                    'audit_logging_enabled': 'Audit logging must be enabled for compliance',
                    'access_control_enabled': 'Access control must be enabled',
                    'apigw_key': 'API Gateway key must be configured',
                    'region': 'Must use Korean region (KR)',
                    'platform': 'Must use VPC platform for enhanced security',
                    'network_security_enabled': 'Network security monitoring required',
                    'data_residency_compliant': 'Data must remain in Korean jurisdiction'
                }
            },
            'korean_privacy': {
                'name': 'Korean Personal Information Protection Act (PIPA)',
                'requirements': {
                    'personal_data_encryption': 'Personal data must be encrypted',
                    'consent_management': 'User consent must be managed',
                    'data_retention_policy': 'Data retention policy must be defined',
                    'breach_notification': 'Breach notification procedures required',
                    'data_minimization': 'Data collection must be minimized',
                    'cross_border_transfer': 'Cross-border data transfer restrictions'
                }
            }
        }
    
    def validate_ncp_gov_compliance(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate NCP Government Cloud compliance.
        
        Args:
            config_data: Configuration to validate
            
        Returns:
            Compliance validation results
        """
        framework = self.compliance_frameworks['ncp_gov']
        results = {
            'framework': framework['name'],
            'compliant': True,
            'score': 0,
            'passed_requirements': 0,
            'failed_requirements': [],
            'warnings': [],
            'recommendations': []
        }
        
        total_requirements = len(framework['requirements'])
        
        for requirement, description in framework['requirements'].items():
            if self._check_ncp_gov_requirement(requirement, config_data):
                results['passed_requirements'] += 1
            else:
                results['failed_requirements'].append({
                    'requirement': requirement,
                    'description': description
                })
                results['compliant'] = False
        
        # Calculate compliance score
        results['score'] = (results['passed_requirements'] / total_requirements) * 100
        
        # Generate recommendations
        results['recommendations'] = self._generate_ncp_gov_recommendations(
            results['failed_requirements'], config_data
        )
        
        return results
    
    def _check_ncp_gov_requirement(self, requirement: str, config_data: Dict[str, Any]) -> bool:
        """Check individual NCP Gov compliance requirement."""
        requirement_checks = {
            'encryption_enabled': lambda c: c.get('encryption_enabled', False),
            'audit_logging_enabled': lambda c: c.get('audit_logging_enabled', False),
            'access_control_enabled': lambda c: c.get('access_control_enabled', False),
            'apigw_key': lambda c: bool(c.get('apigw_key')) and c.get('apigw_key') not in ['', 'your-ncpgov-apigw-key'],
            'region': lambda c: c.get('region', '').upper() == 'KR',
            'platform': lambda c: c.get('platform', '').upper() == 'VPC',
            'network_security_enabled': lambda c: c.get('network_security_enabled', False),
            'data_residency_compliant': lambda c: c.get('data_residency_compliant', False)
        }
        
        check_func = requirement_checks.get(requirement)
        if check_func:
            return check_func(config_data)
        
        return False
    
    def _generate_ncp_gov_recommendations(self, failed_requirements: List[Dict], 
                                         config_data: Dict[str, Any]) -> List[str]:
        """Generate recommendations for NCP Gov compliance."""
        recommendations = []
        
        for req in failed_requirements:
            requirement = req['requirement']
            
            if requirement == 'encryption_enabled':
                recommendations.append("Enable data encryption in NCP Gov configuration")
            elif requirement == 'audit_logging_enabled':
                recommendations.append("Enable audit logging for compliance monitoring")
            elif requirement == 'access_control_enabled':
                recommendations.append("Enable access control mechanisms")
            elif requirement == 'apigw_key':
                recommendations.append("Configure valid API Gateway key for NCP Gov")
            elif requirement == 'region':
                recommendations.append("Set region to 'KR' for government cloud compliance")
            elif requirement == 'platform':
                recommendations.append("Use 'VPC' platform for enhanced security")
            elif requirement == 'network_security_enabled':
                recommendations.append("Enable network security monitoring")
            elif requirement == 'data_residency_compliant':
                recommendations.append("Ensure data residency compliance settings")
        
        # Additional recommendations based on configuration
        if not config_data.get('multi_factor_auth', False):
            recommendations.append("Consider enabling multi-factor authentication")
        
        if not config_data.get('session_timeout'):
            recommendations.append("Configure session timeout for security")
        
        return recommendations
    
    def validate_korean_privacy_compliance(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Korean Personal Information Protection Act (PIPA) compliance.
        
        Args:
            config_data: Configuration to validate
            
        Returns:
            PIPA compliance validation results
        """
        framework = self.compliance_frameworks['korean_privacy']
        results = {
            'framework': framework['name'],
            'compliant': True,
            'score': 0,
            'passed_requirements': 0,
            'failed_requirements': [],
            'warnings': [],
            'recommendations': []
        }
        
        total_requirements = len(framework['requirements'])
        
        for requirement, description in framework['requirements'].items():
            if self._check_korean_privacy_requirement(requirement, config_data):
                results['passed_requirements'] += 1
            else:
                results['failed_requirements'].append({
                    'requirement': requirement,
                    'description': description
                })
                results['compliant'] = False
        
        results['score'] = (results['passed_requirements'] / total_requirements) * 100
        
        return results
    
    def _check_korean_privacy_requirement(self, requirement: str, config_data: Dict[str, Any]) -> bool:
        """Check Korean privacy compliance requirement."""
        # This would be implemented based on specific PIPA requirements
        # For now, return basic checks
        privacy_checks = {
            'personal_data_encryption': lambda c: c.get('personal_data_encryption', False),
            'consent_management': lambda c: c.get('consent_management_enabled', False),
            'data_retention_policy': lambda c: bool(c.get('data_retention_days')),
            'breach_notification': lambda c: c.get('breach_notification_enabled', False),
            'data_minimization': lambda c: c.get('data_minimization_enabled', False),
            'cross_border_transfer': lambda c: c.get('cross_border_transfer_restricted', False)
        }
        
        check_func = privacy_checks.get(requirement)
        if check_func:
            return check_func(config_data)
        
        return False


class NCPSecurityMonitor:
    """
    NCP security monitoring and alerting utility.
    
    Monitors NCP operations for security events and compliance violations.
    """
    
    def __init__(self, masker: NCPSensitiveDataMasker = None):
        """
        Initialize security monitor.
        
        Args:
            masker: Data masker instance
        """
        self.masker = masker or NCPSensitiveDataMasker()
        self.security_events = []
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], 
                          severity: str = 'INFO') -> None:
        """
        Log a security event with masking.
        
        Args:
            event_type: Type of security event
            details: Event details
            severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
        """
        # Mask sensitive data in event details
        masked_details = self.masker.mask_ncp_data(details)
        
        security_event = {
            'timestamp': self._get_timestamp(),
            'event_type': event_type,
            'severity': severity,
            'details': masked_details,
            'compliance_framework': 'ncp_gov'
        }
        
        self.security_events.append(security_event)
        
        # Log to system logger
        log_message = f"[SECURITY] {event_type}: {json.dumps(masked_details, ensure_ascii=False)}"
        
        if severity == 'CRITICAL':
            logger.critical(log_message)
        elif severity == 'ERROR':
            logger.error(log_message)
        elif severity == 'WARNING':
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def monitor_api_call(self, service: str, action: str, params: Dict[str, Any], 
                        response: Dict[str, Any] = None, error: Exception = None) -> None:
        """
        Monitor NCP API call for security events.
        
        Args:
            service: NCP service name
            action: API action
            params: API parameters
            response: API response (optional)
            error: API error (optional)
        """
        event_details = {
            'service': service,
            'action': action,
            'params_count': len(params) if params else 0,
            'success': error is None
        }
        
        if error:
            event_details['error_type'] = type(error).__name__
            event_details['error_message'] = str(error)
            severity = 'ERROR'
        else:
            severity = 'INFO'
        
        self.log_security_event('api_call', event_details, severity)
    
    def monitor_config_access(self, config_path: str, operation: str) -> None:
        """
        Monitor configuration file access.
        
        Args:
            config_path: Path to configuration file
            operation: Operation performed (read, write, create, delete)
        """
        event_details = {
            'config_path': str(Path(config_path).name),  # Only log filename, not full path
            'operation': operation,
            'file_exists': Path(config_path).exists()
        }
        
        self.log_security_event('config_access', event_details, 'INFO')
    
    def monitor_credential_usage(self, credential_type: str, success: bool) -> None:
        """
        Monitor credential usage events.
        
        Args:
            credential_type: Type of credential used
            success: Whether credential usage was successful
        """
        event_details = {
            'credential_type': credential_type,
            'success': success
        }
        
        severity = 'INFO' if success else 'WARNING'
        self.log_security_event('credential_usage', event_details, severity)
    
    def get_security_events(self, event_type: str = None, 
                           severity: str = None) -> List[Dict[str, Any]]:
        """
        Get security events with optional filtering.
        
        Args:
            event_type: Filter by event type
            severity: Filter by severity
            
        Returns:
            List of matching security events
        """
        events = self.security_events
        
        if event_type:
            events = [e for e in events if e['event_type'] == event_type]
        
        if severity:
            events = [e for e in events if e['severity'] == severity]
        
        return events
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()


def validate_ncp_config_security(config_path: str) -> Dict[str, Any]:
    """
    Validate NCP configuration file security.
    
    Args:
        config_path: Path to NCP configuration file
        
    Returns:
        Security validation results
    """
    results = {
        'secure': True,
        'issues': [],
        'recommendations': []
    }
    
    config_file = Path(config_path).expanduser()
    
    # Check if file exists
    if not config_file.exists():
        results['issues'].append(f"Configuration file not found: {config_path}")
        results['secure'] = False
        return results
    
    # Check file permissions (Unix systems)
    if os.name != 'nt':
        try:
            file_mode = oct(config_file.stat().st_mode)[-3:]
            if file_mode != '600':
                results['issues'].append(f"Insecure file permissions: {file_mode} (should be 600)")
                results['secure'] = False
                results['recommendations'].append(f"Run: chmod 600 {config_path}")
        except Exception as e:
            results['issues'].append(f"Could not check file permissions: {e}")
    
    # Check directory permissions
    config_dir = config_file.parent
    if config_dir.exists() and os.name != 'nt':
        try:
            dir_mode = oct(config_dir.stat().st_mode)[-3:]
            if dir_mode not in ['700', '755']:
                results['issues'].append(f"Insecure directory permissions: {dir_mode} (should be 700)")
                results['recommendations'].append(f"Run: chmod 700 {config_dir}")
        except Exception as e:
            results['issues'].append(f"Could not check directory permissions: {e}")
    
    # Check file content for placeholder values
    try:
        import yaml
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if config_data:
            placeholder_patterns = [
                'your-ncp-access-key', 'your-ncp-secret-key', 'your-ncpgov-apigw-key',
                '<access-key>', '<secret-key>', '[access-key]', '[secret-key]'
            ]
            
            for profile_name, profile_config in config_data.items():
                if isinstance(profile_config, dict):
                    for key, value in profile_config.items():
                        if isinstance(value, str) and value in placeholder_patterns:
                            results['issues'].append(f"Placeholder value found in {profile_name}.{key}")
                            results['recommendations'].append(f"Replace placeholder value for {key}")
    
    except Exception as e:
        results['issues'].append(f"Could not validate configuration content: {e}")
    
    return results


def create_secure_ncp_config(config_path: str, config_data: Dict[str, Any]) -> bool:
    """
    Create NCP configuration file with secure permissions.
    
    Args:
        config_path: Path where to create the configuration file
        config_data: Configuration data to write
        
    Returns:
        True if file was created successfully
    """
    try:
        config_file = Path(config_path).expanduser()
        
        # Create directory with secure permissions
        config_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        
        # Write configuration file
        import yaml
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # Set secure file permissions
        if os.name != 'nt':
            config_file.chmod(0o600)
        
        logger.info(f"Secure NCP configuration created: {config_path}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to create secure NCP configuration: {e}")
        return False


# Global instances for easy access
ncp_data_masker = NCPSensitiveDataMasker()
ncp_compliance_validator = NCPComplianceValidator()
ncp_security_monitor = NCPSecurityMonitor(ncp_data_masker)