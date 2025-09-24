"""
Security patterns for detecting sensitive data in code and configuration files
"""

import re
from typing import Dict, List, Pattern, NamedTuple
from dataclasses import dataclass


class DetectionPattern(NamedTuple):
    """Represents a pattern for detecting sensitive data"""
    name: str
    pattern: Pattern[str]
    description: str
    severity: str  # 'high', 'medium', 'low'
    guidance: str


@dataclass
class SecurityPatterns:
    """Manages security patterns for sensitive data detection"""
    
    def __init__(self):
        self._patterns: List[DetectionPattern] = []
        self._load_default_patterns()
    
    def _load_default_patterns(self):
        """Load default security patterns"""
        
        # API Keys and Access Tokens
        self._patterns.extend([
            DetectionPattern(
                name="ncp_access_key",
                pattern=re.compile(r'(?i)(ncp[_-]?access[_-]?key|access[_-]?key[_-]?id)\s*[:=]\s*["\']?([A-Za-z0-9]{20,})["\']?', re.MULTILINE),
                description="NCP Access Key detected",
                severity="high",
                guidance="Move NCP access keys to ~/.ncp/config.yaml or use environment variables"
            ),
            DetectionPattern(
                name="ncp_secret_key",
                pattern=re.compile(r'(?i)(ncp[_-]?secret[_-]?key|secret[_-]?key)\s*[:=]\s*["\']?([A-Za-z0-9+/]{40,})["\']?', re.MULTILINE),
                description="NCP Secret Key detected",
                severity="high",
                guidance="Move NCP secret keys to ~/.ncp/config.yaml or use environment variables"
            ),
            DetectionPattern(
                name="ncpgov_access_key",
                pattern=re.compile(r'(?i)(ncpgov[_-]?access[_-]?key|gov[_-]?access[_-]?key)\s*[:=]\s*["\']?([A-Za-z0-9]{20,})["\']?', re.MULTILINE),
                description="NCPGOV Access Key detected",
                severity="high",
                guidance="Move NCPGOV access keys to ~/.ncpgov/config.yaml or use environment variables"
            ),
            DetectionPattern(
                name="ncpgov_secret_key",
                pattern=re.compile(r'(?i)(ncpgov[_-]?secret[_-]?key|gov[_-]?secret[_-]?key)\s*[:=]\s*["\']?([A-Za-z0-9+/]{40,})["\']?', re.MULTILINE),
                description="NCPGOV Secret Key detected",
                severity="high",
                guidance="Move NCPGOV secret keys to ~/.ncpgov/config.yaml or use environment variables"
            ),
            DetectionPattern(
                name="aws_access_key",
                pattern=re.compile(r'(?i)(aws[_-]?access[_-]?key[_-]?id|access[_-]?key[_-]?id)\s*[:=]\s*["\']?(AKIA[0-9A-Z]{16})["\']?', re.MULTILINE),
                description="AWS Access Key ID detected",
                severity="high",
                guidance="Move AWS credentials to ~/.aws/credentials or use IAM roles"
            ),
            DetectionPattern(
                name="aws_secret_key",
                pattern=re.compile(r'(?i)(aws[_-]?secret[_-]?access[_-]?key|secret[_-]?access[_-]?key)\s*[:=]\s*["\']?([A-Za-z0-9+/]{40})["\']?', re.MULTILINE),
                description="AWS Secret Access Key detected",
                severity="high",
                guidance="Move AWS credentials to ~/.aws/credentials or use IAM roles"
            ),
            DetectionPattern(
                name="gcp_service_account",
                pattern=re.compile(r'(?i)(service[_-]?account[_-]?key|gcp[_-]?key)\s*[:=]\s*["\']?({[^}]*"type"\s*:\s*"service_account"[^}]*})["\']?', re.MULTILINE | re.DOTALL),
                description="GCP Service Account Key detected",
                severity="high",
                guidance="Move GCP service account keys to secure location and use GOOGLE_APPLICATION_CREDENTIALS"
            ),
            DetectionPattern(
                name="azure_client_secret",
                pattern=re.compile(r'(?i)(azure[_-]?client[_-]?secret|client[_-]?secret)\s*[:=]\s*["\']?([A-Za-z0-9~._-]{34,})["\']?', re.MULTILINE),
                description="Azure Client Secret detected",
                severity="high",
                guidance="Move Azure credentials to Azure Key Vault or use managed identities"
            )
        ])
        
        # Slack and Communication Tokens
        self._patterns.extend([
            DetectionPattern(
                name="slack_token",
                pattern=re.compile(r'(?i)(slack[_-]?token|slack[_-]?api[_-]?key)\s*[:=]\s*["\']?(xox[bpars]-[0-9]{12}-[0-9]{12}-[0-9a-zA-Z]{24})["\']?', re.MULTILINE),
                description="Slack API Token detected",
                severity="high",
                guidance="Move Slack tokens to environment variables or secure configuration"
            ),
            DetectionPattern(
                name="slack_webhook",
                pattern=re.compile(r'(?i)(slack[_-]?webhook|webhook[_-]?url)\s*[:=]\s*["\']?(https://hooks\.slack\.com/services/[A-Z0-9/]+)["\']?', re.MULTILINE),
                description="Slack Webhook URL detected",
                severity="medium",
                guidance="Move Slack webhook URLs to environment variables"
            ),
            DetectionPattern(
                name="slack_user_id",
                pattern=re.compile(r'(?i)(slack[_-]?user[_-]?id|user[_-]?id)\s*[:=]\s*["\']?([UW][A-Z0-9]{8,})["\']?', re.MULTILINE),
                description="Slack User ID detected",
                severity="medium",
                guidance="Replace Slack User IDs with generic placeholders like [USER_ID]"
            ),
            DetectionPattern(
                name="slack_channel_id",
                pattern=re.compile(r'(?i)(slack[_-]?channel[_-]?id|channel[_-]?id)\s*[:=]\s*["\']?([C][A-Z0-9]{8,})["\']?', re.MULTILINE),
                description="Slack Channel ID detected",
                severity="medium",
                guidance="Replace Slack Channel IDs with generic placeholders like [CHANNEL_ID]"
            )
        ])
        
        # Personal and Project Identifiers
        self._patterns.extend([
            DetectionPattern(
                name="email_address",
                pattern=re.compile(r'(?i)(email|mail)\s*[:=]\s*["\']?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})["\']?', re.MULTILINE),
                description="Email address detected",
                severity="medium",
                guidance="Replace email addresses with generic placeholders like [EMAIL]"
            ),
            DetectionPattern(
                name="phone_number",
                pattern=re.compile(r'(?i)(phone|tel|mobile)\s*[:=]\s*["\']?([\+]?[1-9][\d\s\-\(\)]{7,15})["\']?', re.MULTILINE),
                description="Phone number detected",
                severity="medium",
                guidance="Replace phone numbers with generic placeholders like [PHONE_NUMBER]"
            ),
            DetectionPattern(
                name="ip_address",
                pattern=re.compile(r'(?i)(ip|host|server)\s*[:=]\s*["\']?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})["\']?', re.MULTILINE),
                description="IP address detected",
                severity="low",
                guidance="Replace IP addresses with generic placeholders like [IP_ADDRESS] unless they are public/example IPs"
            ),
            DetectionPattern(
                name="project_name",
                pattern=re.compile(r'(?i)(project[_-]?name|project[_-]?id)\s*[:=]\s*["\']?([a-zA-Z0-9][a-zA-Z0-9_-]{2,30})["\']?', re.MULTILINE),
                description="Project name/ID detected",
                severity="low",
                guidance="Replace project names with generic placeholders like [PROJECT_NAME]"
            )
        ])
        
        # Generic API Keys and Tokens
        self._patterns.extend([
            DetectionPattern(
                name="generic_api_key",
                pattern=re.compile(r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([A-Za-z0-9]{32,})["\']?', re.MULTILINE),
                description="Generic API Key detected",
                severity="high",
                guidance="Move API keys to secure configuration or environment variables"
            ),
            DetectionPattern(
                name="bearer_token",
                pattern=re.compile(r'(?i)(bearer[_-]?token|authorization)\s*[:=]\s*["\']?(Bearer\s+[A-Za-z0-9._-]+)["\']?', re.MULTILINE),
                description="Bearer Token detected",
                severity="high",
                guidance="Move bearer tokens to secure configuration or environment variables"
            ),
            DetectionPattern(
                name="jwt_token",
                pattern=re.compile(r'(?i)(jwt[_-]?token|token)\s*[:=]\s*["\']?(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*)["\']?', re.MULTILINE),
                description="JWT Token detected",
                severity="high",
                guidance="Move JWT tokens to secure configuration or environment variables"
            )
        ])
    
    def get_patterns(self) -> List[DetectionPattern]:
        """Get all detection patterns"""
        return self._patterns.copy()
    
    def get_patterns_by_severity(self, severity: str) -> List[DetectionPattern]:
        """Get patterns filtered by severity level"""
        return [p for p in self._patterns if p.severity == severity]
    
    def add_custom_pattern(self, name: str, pattern_str: str, description: str, 
                          severity: str, guidance: str) -> None:
        """Add a custom detection pattern"""
        try:
            compiled_pattern = re.compile(pattern_str, re.MULTILINE)
            custom_pattern = DetectionPattern(
                name=name,
                pattern=compiled_pattern,
                description=description,
                severity=severity,
                guidance=guidance
            )
            self._patterns.append(custom_pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern_str}': {e}")
    
    def load_custom_patterns_from_config(self, config_dict: Dict) -> None:
        """Load custom patterns from configuration dictionary"""
        custom_patterns = config_dict.get('custom_patterns', [])
        for pattern_config in custom_patterns:
            self.add_custom_pattern(
                name=pattern_config['name'],
                pattern_str=pattern_config['pattern'],
                description=pattern_config['description'],
                severity=pattern_config.get('severity', 'medium'),
                guidance=pattern_config.get('guidance', 'Move sensitive data to secure configuration')
            )