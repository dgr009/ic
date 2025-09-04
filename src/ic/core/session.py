#!/usr/bin/env python3
"""
Enhanced AWS Session Manager for IC CLI

This module provides intelligent AWS session management with:
- Profile type detection (assume_role vs direct credentials)
- Session caching for improved performance
- Account alias resolution with fallback to account ID
- Backward compatibility with existing configurations
"""

import os
import re
import time
import configparser
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from ic.core.logging import get_logger

logger = get_logger()


@dataclass
class ProfileInfo:
    """Information about an AWS profile"""
    name: str
    type: str  # 'assume_role' or 'direct'
    account_id: str
    role_arn: Optional[str] = None
    source_profile: Optional[str] = None


@dataclass
class SessionInfo:
    """Information about an AWS session"""
    session: boto3.Session
    account_id: str
    account_alias: str
    region: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class AWSSessionManager:
    """Enhanced AWS session manager with intelligent profile detection and caching"""
    
    def __init__(self, config=None):
        """
        Initialize the AWS session manager
        
        Args:
            config: Configuration object with AWS settings
        """
        self.config = config
        self.profile_cache: Dict[str, ProfileInfo] = {}
        self.session_cache: Dict[str, SessionInfo] = {}
        self.account_alias_cache: Dict[str, str] = {}
        self._profiles_loaded = False
        
        # Configuration defaults
        self.session_duration = getattr(config, 'session_duration', 3600) if config else 3600
        self.max_workers = getattr(config, 'max_workers', 10) if config else 10
        
    def get_profiles(self) -> Dict[str, ProfileInfo]:
        """
        Get AWS profiles with account ID mapping and type detection
        
        Returns:
            Dict mapping account_id to ProfileInfo
        """
        if self._profiles_loaded and self.profile_cache:
            return self.profile_cache
            
        logger.log_info_file_only("Loading AWS profiles from ~/.aws/config")
        
        config = configparser.ConfigParser()
        aws_config_path = os.path.expanduser('~/.aws/config')
        
        if not os.path.exists(aws_config_path):
            logger.log_error(f"AWS config file not found: {aws_config_path}")
            return {}
            
        try:
            config.read(aws_config_path)
        except Exception as e:
            logger.log_error(f"Failed to read AWS config: {e}")
            return {}
        
        profiles = {}
        
        # Process profile sections
        for section in config.sections():
            if section.startswith('profile '):
                profile_name = section.split('profile ')[1]
                self._process_profile_section(config[section], profile_name, profiles)
        
        # Process default profile if exists
        if 'default' in config.sections():
            self._process_profile_section(config['default'], 'default', profiles)
        
        self.profile_cache = profiles
        self._profiles_loaded = True
        
        logger.log_info_file_only(f"Loaded {len(profiles)} AWS profiles")
        return profiles
    
    def _process_profile_section(self, section, profile_name: str, profiles: Dict[str, ProfileInfo]):
        """Process a single profile section from AWS config"""
        try:
            role_arn = section.get('role_arn')
            
            if role_arn:
                # Assume role profile
                account_id = self._extract_account_id_from_arn(role_arn)
                if account_id:
                    source_profile = section.get('source_profile')
                    profiles[account_id] = ProfileInfo(
                        name=profile_name,
                        type='assume_role',
                        account_id=account_id,
                        role_arn=role_arn,
                        source_profile=source_profile
                    )
                    logger.log_info_file_only(f"Found assume_role profile: {profile_name} -> {account_id}")
            else:
                # Direct credentials profile
                account_id = self._get_account_id_from_session(profile_name)
                if account_id:
                    profiles[account_id] = ProfileInfo(
                        name=profile_name,
                        type='direct',
                        account_id=account_id
                    )
                    logger.log_info_file_only(f"Found direct profile: {profile_name} -> {account_id}")
                    
        except Exception as e:
            logger.log_error(f"Error processing profile {profile_name}: {e}")
    
    def _extract_account_id_from_arn(self, role_arn: str) -> Optional[str]:
        """Extract account ID from role ARN"""
        match = re.search(r'arn:aws:iam::(\d+):role', role_arn)
        return match.group(1) if match else None
    
    def _get_account_id_from_session(self, profile_name: str) -> Optional[str]:
        """Get account ID from a session using STS get_caller_identity"""
        try:
            session = boto3.Session(profile_name=profile_name)
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            return identity['Account']
        except Exception as e:
            logger.log_info_file_only(f"Could not get account ID for profile {profile_name}: {e}")
            return None
    
    def create_session(self, account_id: str, region: str) -> Optional[boto3.Session]:
        """
        Create an AWS session for the specified account and region
        
        Args:
            account_id: AWS account ID
            region: AWS region name
            
        Returns:
            boto3.Session or None if creation fails
        """
        cache_key = f"{account_id}:{region}"
        
        # Check cache first
        if cache_key in self.session_cache:
            session_info = self.session_cache[cache_key]
            if self._is_session_valid(session_info):
                logger.log_info_file_only(f"Using cached session for {account_id} in {region}")
                return session_info.session
            else:
                # Remove expired session
                del self.session_cache[cache_key]
        
        # Get profile information
        profiles = self.get_profiles()
        profile_info = profiles.get(account_id)
        
        if not profile_info:
            logger.log_error(f"No profile found for account {account_id}")
            return None
        
        logger.log_info_file_only(f"Creating {profile_info.type} session for account {account_id} in {region}")
        
        try:
            if profile_info.type == 'assume_role':
                session = self._create_assume_role_session(profile_info, region)
            else:
                session = self._create_direct_session(profile_info, region)
            
            if session:
                # Get account alias for caching
                account_alias = self.get_account_alias(session)
                
                # Cache the session
                session_info = SessionInfo(
                    session=session,
                    account_id=account_id,
                    account_alias=account_alias,
                    region=region,
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(seconds=self.session_duration) if profile_info.type == 'assume_role' else None
                )
                self.session_cache[cache_key] = session_info
                
                logger.log_info_file_only(f"Successfully created session for {account_id} ({account_alias}) in {region}")
                return session
            
        except Exception as e:
            logger.log_error(f"Failed to create session for account {account_id}: {e}")
            
        return None
    
    def _create_assume_role_session(self, profile_info: ProfileInfo, region: str) -> Optional[boto3.Session]:
        """Create session using assume role"""
        if not profile_info.source_profile or not profile_info.role_arn:
            logger.log_error(f"Missing source_profile or role_arn for assume_role profile {profile_info.name}")
            return None
        
        try:
            # Create source session
            source_session = boto3.Session(
                profile_name=profile_info.source_profile,
                region_name=region
            )
            
            # Assume role
            sts_client = source_session.client('sts')
            response = sts_client.assume_role(
                RoleArn=profile_info.role_arn,
                RoleSessionName=f"ic-session-{int(time.time())}",
                DurationSeconds=self.session_duration
            )
            
            credentials = response['Credentials']
            return boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=region
            )
            
        except Exception as e:
            logger.log_error(f"Failed to assume role {profile_info.role_arn}: {e}")
            return None
    
    def _create_direct_session(self, profile_info: ProfileInfo, region: str) -> Optional[boto3.Session]:
        """Create session using direct credentials"""
        try:
            return boto3.Session(
                profile_name=profile_info.name,
                region_name=region
            )
        except Exception as e:
            logger.log_error(f"Failed to create direct session for profile {profile_info.name}: {e}")
            return None
    
    def _is_session_valid(self, session_info: SessionInfo) -> bool:
        """Check if a cached session is still valid"""
        if session_info.expires_at:
            # Check if assume role session has expired
            return datetime.now() < session_info.expires_at
        else:
            # Direct sessions don't expire, but check if they're too old
            age = datetime.now() - session_info.created_at
            return age < timedelta(hours=1)  # Refresh after 1 hour
    
    def get_account_alias(self, session: boto3.Session) -> str:
        """
        Get account alias with fallback to account ID
        
        Args:
            session: boto3.Session
            
        Returns:
            Account alias or account ID if alias not available
        """
        try:
            # Try to get from cache first
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            account_id = identity['Account']
            
            if account_id in self.account_alias_cache:
                return self.account_alias_cache[account_id]
            
            # Try to get account alias
            iam = session.client('iam')
            aliases = iam.list_account_aliases()
            
            if aliases['AccountAliases']:
                alias = aliases['AccountAliases'][0]
                self.account_alias_cache[account_id] = alias
                return alias
            else:
                # No alias, use account ID
                self.account_alias_cache[account_id] = account_id
                return account_id
                
        except Exception as e:
            logger.log_info_file_only(f"Failed to get account alias: {e}")
            return "unknown"
    
    def create_sessions_parallel(self, account_regions: list) -> Dict[str, boto3.Session]:
        """
        Create multiple sessions in parallel
        
        Args:
            account_regions: List of (account_id, region) tuples
            
        Returns:
            Dict mapping "account_id:region" to session
        """
        sessions = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_key = {}
            
            for account_id, region in account_regions:
                cache_key = f"{account_id}:{region}"
                future = executor.submit(self.create_session, account_id, region)
                future_to_key[future] = cache_key
            
            for future in as_completed(future_to_key):
                cache_key = future_to_key[future]
                try:
                    session = future.result()
                    if session:
                        sessions[cache_key] = session
                except Exception as e:
                    logger.log_error(f"Failed to create session for {cache_key}: {e}")
        
        return sessions
    
    def clear_cache(self):
        """Clear all cached sessions and profiles"""
        self.session_cache.clear()
        self.profile_cache.clear()
        self.account_alias_cache.clear()
        self._profiles_loaded = False
        logger.log_info_file_only("Cleared AWS session cache")
    
    def get_session_info(self, account_id: str, region: str) -> Optional[SessionInfo]:
        """Get cached session information"""
        cache_key = f"{account_id}:{region}"
        return self.session_cache.get(cache_key)
    
    def list_cached_sessions(self) -> Dict[str, SessionInfo]:
        """List all cached sessions"""
        return self.session_cache.copy()


# Backward compatibility functions
def get_profiles() -> Dict[str, str]:
    """
    Backward compatibility function for existing code
    
    Returns:
        Dict mapping account_id to profile_name
    """
    manager = AWSSessionManager()
    profiles = manager.get_profiles()
    return {account_id: profile.name for account_id, profile in profiles.items()}


def create_session(profile_name: str, region_name: str) -> Optional[boto3.Session]:
    """
    Backward compatibility function for existing code
    
    Args:
        profile_name: AWS profile name
        region_name: AWS region name
        
    Returns:
        boto3.Session or None
    """
    try:
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
        logger.log_info_file_only(f"Created session for profile '{profile_name}' in region '{region_name}'")
        return session
    except Exception as e:
        logger.log_error(f"Failed to create session for profile '{profile_name}' in region '{region_name}': {e}")
        return None