"""
Security configuration management
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


class SecurityConfig:
    """Manages security configuration for the IC CLI"""
    
    DEFAULT_CONFIG = {
        "enabled": True,
        "scan_extensions": [
            ".py", ".yaml", ".yml", ".json", ".txt", ".md", ".sh", ".env",
            ".cfg", ".conf", ".ini", ".toml", ".properties", ".js", ".ts"
        ],
        "exclude_patterns": [
            ".git/*",
            "__pycache__/*",
            "*.pyc",
            "node_modules/*",
            ".pytest_cache/*",
            ".coverage",
            "build/*",
            "dist/*",
            ".venv/*",
            "venv/*"
        ],
        "severity_levels": ["high", "medium", "low"],
        "block_on_high_severity": True,
        "block_on_medium_severity": False,
        "pre_commit_enabled": True,
        "custom_patterns": [
            {
                "name": "example_custom_pattern",
                "pattern": r"(?i)(custom[_-]?secret)\s*[:=]\s*[\"']?([A-Za-z0-9]{20,})[\"']?",
                "description": "Custom secret pattern",
                "severity": "high",
                "guidance": "Move custom secrets to secure configuration"
            }
        ],
        "organization_patterns": {
            "project_names": [
                "ic-cli",
                "infrastructure-cli"
            ],
            "slack_workspace": "your-workspace",
            "email_domains": [
                "company.com",
                "organization.org"
            ]
        }
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
    
    def _get_default_config_path(self) -> Path:
        """Get default configuration file path"""
        home_dir = Path.home()
        ic_config_dir = home_dir / '.ic' / 'config'
        ic_config_dir.mkdir(parents=True, exist_ok=True)
        return ic_config_dir / 'security.json'
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default"""
        if not self.config_path.exists():
            self._create_default_config()
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, 'r') as f:
                user_config = json.load(f)
                
            # Merge with defaults
            config = self.DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load security config from {self.config_path}: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    def _create_default_config(self) -> None:
        """Create default configuration file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            json.dump(self.DEFAULT_CONFIG, f, indent=2)
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def is_enabled(self) -> bool:
        """Check if security scanning is enabled"""
        return self.config.get('enabled', True)
    
    def should_block_on_severity(self, severity: str) -> bool:
        """Check if commits should be blocked for given severity"""
        if severity == 'high':
            return self.config.get('block_on_high_severity', True)
        elif severity == 'medium':
            return self.config.get('block_on_medium_severity', False)
        else:
            return False
    
    def get_scan_extensions(self) -> List[str]:
        """Get list of file extensions to scan"""
        return self.config.get('scan_extensions', [])
    
    def get_exclude_patterns(self) -> List[str]:
        """Get list of patterns to exclude from scanning"""
        return self.config.get('exclude_patterns', [])
    
    def get_custom_patterns(self) -> List[Dict]:
        """Get custom detection patterns"""
        return self.config.get('custom_patterns', [])
    
    def add_custom_pattern(self, name: str, pattern: str, description: str, 
                          severity: str, guidance: str) -> None:
        """Add a custom detection pattern"""
        custom_pattern = {
            "name": name,
            "pattern": pattern,
            "description": description,
            "severity": severity,
            "guidance": guidance
        }
        
        if 'custom_patterns' not in self.config:
            self.config['custom_patterns'] = []
        
        self.config['custom_patterns'].append(custom_pattern)
        self.save_config()
    
    def remove_custom_pattern(self, name: str) -> bool:
        """Remove a custom detection pattern by name"""
        if 'custom_patterns' not in self.config:
            return False
        
        original_length = len(self.config['custom_patterns'])
        self.config['custom_patterns'] = [
            p for p in self.config['custom_patterns'] 
            if p.get('name') != name
        ]
        
        if len(self.config['custom_patterns']) < original_length:
            self.save_config()
            return True
        
        return False
    
    def update_organization_patterns(self, project_names: List[str] = None,
                                   slack_workspace: str = None,
                                   email_domains: List[str] = None) -> None:
        """Update organization-specific patterns"""
        if 'organization_patterns' not in self.config:
            self.config['organization_patterns'] = {}
        
        org_patterns = self.config['organization_patterns']
        
        if project_names is not None:
            org_patterns['project_names'] = project_names
        
        if slack_workspace is not None:
            org_patterns['slack_workspace'] = slack_workspace
        
        if email_domains is not None:
            org_patterns['email_domains'] = email_domains
        
        self.save_config()
    
    def get_organization_patterns(self) -> Dict:
        """Get organization-specific patterns"""
        return self.config.get('organization_patterns', {})