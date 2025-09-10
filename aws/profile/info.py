"""
AWS profile information parser and renderer.

This module provides classes to parse AWS configuration and credentials files
and render profile information in a user-friendly table format.
"""

import os
import re
import configparser
from pathlib import Path
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table


class AWSProfileParser:
    """Parses AWS configuration and credentials files."""
    
    def __init__(self):
        self.console = Console()
        self.aws_config_path = Path.home() / ".aws" / "config"
        self.aws_credentials_path = Path.home() / ".aws" / "credentials"
    
    def parse_config_file(self, config_path: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """
        Parse AWS config file (~/.aws/config).
        
        Args:
            config_path: Optional path to config file
            
        Returns:
            Dictionary of profile configurations
        """
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = self.aws_config_path
        
        if not config_file.exists():
            self.console.print(f"⚠️  AWS config file not found: {config_file}")
            return {}
        
        try:
            config = configparser.ConfigParser()
            config.read(config_file)
            
            profiles = {}
            for section_name in config.sections():
                # Handle both 'profile name' and 'name' formats
                if section_name.startswith('profile '):
                    profile_name = section_name[8:]  # Remove 'profile ' prefix
                else:
                    profile_name = section_name
                
                profile_data = dict(config[section_name])
                profiles[profile_name] = profile_data
            
            return profiles
            
        except Exception as e:
            self.console.print(f"❌ Failed to parse AWS config file: {e}")
            return {}
    
    def parse_credentials_file(self, creds_path: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """
        Parse AWS credentials file (~/.aws/credentials).
        
        Args:
            creds_path: Optional path to credentials file
            
        Returns:
            Dictionary of profile credentials
        """
        if creds_path:
            creds_file = Path(creds_path)
        else:
            creds_file = self.aws_credentials_path
        
        if not creds_file.exists():
            self.console.print(f"⚠️  AWS credentials file not found: {creds_file}")
            return {}
        
        try:
            config = configparser.ConfigParser()
            config.read(creds_file)
            
            credentials = {}
            for section_name in config.sections():
                profile_data = dict(config[section_name])
                credentials[section_name] = profile_data
            
            return credentials
            
        except Exception as e:
            self.console.print(f"❌ Failed to parse AWS credentials file: {e}")
            return {}
    
    def extract_account_from_role_arn(self, role_arn: str) -> Optional[str]:
        """
        Extract account ID from role ARN.
        
        Args:
            role_arn: AWS role ARN (e.g., arn:aws:iam::123456789012:role/RoleName)
            
        Returns:
            Account ID or None if not found
        """
        if not role_arn:
            return None
        
        # Pattern: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME
        arn_pattern = r'arn:aws:iam::(\d{12}):role/'
        match = re.search(arn_pattern, role_arn)
        
        if match:
            return match.group(1)
        
        return None
    
    def extract_role_name_from_arn(self, role_arn: str) -> Optional[str]:
        """
        Extract role name from role ARN (last part after final slash).
        
        Args:
            role_arn: AWS role ARN
            
        Returns:
            Role name or None if not found
        """
        if not role_arn:
            return None
        
        # Extract everything after the last slash
        parts = role_arn.split('/')
        if len(parts) > 1:
            return parts[-1]
        
        return None


class ProfileInfoCollector:
    """Collects and formats AWS profile information."""
    
    def __init__(self):
        self.parser = AWSProfileParser()
        self.console = Console()
    
    def collect_profile_info(self) -> List[Dict[str, str]]:
        """
        Collect comprehensive AWS profile information.
        
        Returns:
            List of profile information dictionaries
        """
        from rich.progress import Progress, SpinnerColumn, TextColumn
        import time
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            
            # Parse config file
            task = progress.add_task("Parsing AWS configuration files...", total=None)
            start_time = time.time()
            
            config_data = self.parser.parse_config_file()
            progress.update(task, description="Parsing AWS credentials file...")
            
            creds_data = self.parser.parse_credentials_file()
            progress.update(task, description="Merging profile information...")
            
            # Merge and format profile information
            profiles = self.merge_config_and_credentials(config_data, creds_data)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            progress.update(task, description=f"Completed in {processing_time:.2f}s")
            progress.stop()
        
        return profiles
    
    def merge_config_and_credentials(self, config_data: Dict[str, Dict[str, str]], 
                                   creds_data: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Merge configuration and credentials data into unified profile information.
        
        Args:
            config_data: Data from ~/.aws/config
            creds_data: Data from ~/.aws/credentials
            
        Returns:
            List of merged profile information
        """
        profiles = []
        
        # Get all unique profile names
        all_profiles = set(config_data.keys()) | set(creds_data.keys())
        
        for profile_name in sorted(all_profiles):
            config_info = config_data.get(profile_name, {})
            creds_info = creds_data.get(profile_name, {})
            
            # Extract profile information
            profile_info = {
                'profile_name': profile_name,
                'account_id': self._extract_account_id(config_info, creds_info),
                'source': config_info.get('source_profile', ''),
                'role_name': self._extract_role_name(config_info),
                'credential': 'active' if creds_info else 'inactive',
                'region': config_info.get('region', ''),
                'role_arn': config_info.get('role_arn', '')
            }
            
            profiles.append(profile_info)
        
        return profiles
    
    def _extract_account_id(self, config_info: Dict[str, str], creds_info: Dict[str, str]) -> str:
        """Extract account ID from various sources."""
        # Try direct account_id first
        if 'account_id' in config_info:
            return config_info['account_id']
        
        # Try extracting from role_arn
        if 'role_arn' in config_info:
            account_id = self.parser.extract_account_from_role_arn(config_info['role_arn'])
            if account_id:
                return account_id
        
        # Try from credentials (less common)
        if 'account_id' in creds_info:
            return creds_info['account_id']
        
        return ''
    
    def _extract_role_name(self, config_info: Dict[str, str]) -> str:
        """Extract role name from configuration."""
        if 'role_arn' in config_info:
            role_name = self.parser.extract_role_name_from_arn(config_info['role_arn'])
            if role_name:
                return role_name
        
        # Fallback to role_name if directly specified
        return config_info.get('role_name', '')


class ProfileTableRenderer:
    """Renders AWS profile information in table format using Rich."""
    
    def __init__(self):
        self.console = Console()
    
    def render_profiles(self, profiles: List[Dict[str, str]]) -> None:
        """
        Render AWS profiles in a Rich table.
        
        Args:
            profiles: List of profile information dictionaries
        """
        if not profiles:
            self.console.print("📋 No AWS profiles found.")
            self.console.print("\n💡 Suggestions:")
            self.console.print("  • Check if ~/.aws/config and ~/.aws/credentials files exist")
            self.console.print("  • Run 'aws configure' to set up your first profile")
            self.console.print("  • Verify AWS CLI installation")
            return
        
        table = Table(title="AWS Profiles")
        table.add_column("Profile Name", style="cyan", no_wrap=True)
        table.add_column("Account ID", style="green", no_wrap=True)
        table.add_column("Source", style="yellow")
        table.add_column("Role Name", style="blue")
        table.add_column("Credential", style="magenta")
        table.add_column("Region", style="white")
        
        for profile in profiles:
            # Format credential status with colors
            credential_status = profile['credential']
            if credential_status == 'active':
                credential_display = f"[green]{credential_status}[/green]"
            else:
                credential_display = f"[red]{credential_status}[/red]"
            
            table.add_row(
                profile['profile_name'],
                profile['account_id'] or '-',
                profile['source'] or '-',
                profile['role_name'] or '-',
                credential_display,
                profile['region'] or '-'
            )
        
        self.console.print(table)
        
        # Display summary
        active_profiles = sum(1 for p in profiles if p['credential'] == 'active')
        self.console.print(f"\n📊 Total profiles: {len(profiles)} | Active: {active_profiles} | Inactive: {len(profiles) - active_profiles}")
        
        # Display helpful information
        if active_profiles == 0:
            self.console.print("\n⚠️  No active profiles found (no credentials available)")
            self.console.print("💡 Run 'aws configure' to set up credentials for your profiles")
        
        # Show profiles with missing account IDs
        missing_accounts = [p['profile_name'] for p in profiles if not p['account_id']]
        if missing_accounts:
            self.console.print(f"\n⚠️  Profiles without account ID: {', '.join(missing_accounts)}")
            self.console.print("💡 Consider adding role_arn or account_id to these profiles")