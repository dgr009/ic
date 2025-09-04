"""
Unit tests for AWSSessionManager class.

Tests AWS profile detection, session creation, and caching functionality.
"""

import os
import re
import time
import configparser
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from src.ic.core.session import AWSSessionManager, ProfileInfo, SessionInfo


class TestAWSSessionManager:
    """Test cases for AWSSessionManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.config.session_duration = 3600
        self.config.max_workers = 10
        
        self.manager = AWSSessionManager(self.config)
        
        # Sample AWS config content
        self.aws_config_content = """
[default]
region = us-east-1

[profile assume-role-profile]
role_arn = arn:aws:iam::123456789012:role/TestRole
source_profile = default
region = us-east-1

[profile direct-profile]
region = us-west-2

[profile another-assume-role]
role_arn = arn:aws:iam::987654321098:role/AnotherRole
source_profile = direct-profile
region = eu-west-1
"""
    
    def test_aws_session_manager_initialization(self):
        """Test AWSSessionManager initialization."""
        # Test with config
        manager = AWSSessionManager(self.config)
        assert manager.config == self.config
        assert manager.session_duration == 3600
        assert manager.max_workers == 10
        assert manager.profile_cache == {}
        assert manager.session_cache == {}
        assert manager.account_alias_cache == {}
        assert manager._profiles_loaded is False
        
        # Test without config
        manager_no_config = AWSSessionManager()
        assert manager_no_config.config is None
        assert manager_no_config.session_duration == 3600  # Default
        assert manager_no_config.max_workers == 10  # Default
    
    def test_extract_account_id_from_arn(self):
        """Test account ID extraction from role ARN."""
        # Valid role ARNs
        assert self.manager._extract_account_id_from_arn(
            'arn:aws:iam::123456789012:role/TestRole'
        ) == '123456789012'
        
        assert self.manager._extract_account_id_from_arn(
            'arn:aws:iam::987654321098:role/path/to/role'
        ) == '987654321098'
        
        # Invalid ARNs
        assert self.manager._extract_account_id_from_arn('invalid-arn') is None
        assert self.manager._extract_account_id_from_arn('') is None
        assert self.manager._extract_account_id_from_arn(
            'arn:aws:s3:::bucket-name'
        ) is None
    
    @patch('boto3.Session')
    def test_get_account_id_from_session_success(self, mock_session_class):
        """Test getting account ID from session successfully."""
        # Mock session and STS client
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_session.client.return_value = mock_sts_client
        mock_session_class.return_value = mock_session
        
        account_id = self.manager._get_account_id_from_session('test-profile')
        
        assert account_id == '123456789012'
        mock_session_class.assert_called_once_with(profile_name='test-profile')
        mock_session.client.assert_called_once_with('sts')
        mock_sts_client.get_caller_identity.assert_called_once()
    
    @patch('boto3.Session')
    def test_get_account_id_from_session_failure(self, mock_session_class):
        """Test getting account ID from session with failure."""
        # Mock session to raise exception
        mock_session_class.side_effect = NoCredentialsError()
        
        account_id = self.manager._get_account_id_from_session('invalid-profile')
        
        assert account_id is None
    
    @patch('os.path.exists')
    @patch('configparser.ConfigParser.read')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_profiles_success(self, mock_file, mock_read, mock_exists):
        """Test loading AWS profiles successfully."""
        mock_exists.return_value = True
        
        # Mock configparser
        mock_config = configparser.ConfigParser()
        mock_config.read_string(self.aws_config_content)
        
        with patch('configparser.ConfigParser') as mock_config_class:
            mock_config_instance = mock_config_class.return_value
            mock_config_instance.sections.return_value = mock_config.sections()
            mock_config_instance.__getitem__ = mock_config.__getitem__
            
            # Mock account ID retrieval for direct profiles
            with patch.object(self.manager, '_get_account_id_from_session') as mock_get_account:
                mock_get_account.return_value = '111111111111'
                
                profiles = self.manager.get_profiles()
        
        # Should find assume role profiles
        assert '123456789012' in profiles
        assert profiles['123456789012'].type == 'assume_role'
        assert profiles['123456789012'].role_arn == 'arn:aws:iam::123456789012:role/TestRole'
        assert profiles['123456789012'].source_profile == 'default'
        
        assert '987654321098' in profiles
        assert profiles['987654321098'].type == 'assume_role'
        
        # Should find direct profile
        assert '111111111111' in profiles
        assert profiles['111111111111'].type == 'direct'
    
    @patch('os.path.exists')
    def test_get_profiles_no_config_file(self, mock_exists):
        """Test loading profiles when AWS config file doesn't exist."""
        mock_exists.return_value = False
        
        profiles = self.manager.get_profiles()
        
        assert profiles == {}
    
    @patch('os.path.exists')
    @patch('configparser.ConfigParser.read')
    def test_get_profiles_config_read_error(self, mock_read, mock_exists):
        """Test loading profiles when config file read fails."""
        mock_exists.return_value = True
        mock_read.side_effect = Exception("Config read error")
        
        profiles = self.manager.get_profiles()
        
        assert profiles == {}
    
    def test_process_profile_section_assume_role(self):
        """Test processing assume role profile section."""
        profiles = {}
        section = {
            'role_arn': 'arn:aws:iam::123456789012:role/TestRole',
            'source_profile': 'default'
        }
        
        # Mock section.get method
        mock_section = Mock()
        mock_section.get.side_effect = lambda key: section.get(key)
        
        self.manager._process_profile_section(mock_section, 'test-profile', profiles)
        
        assert '123456789012' in profiles
        assert profiles['123456789012'].name == 'test-profile'
        assert profiles['123456789012'].type == 'assume_role'
        assert profiles['123456789012'].role_arn == section['role_arn']
        assert profiles['123456789012'].source_profile == section['source_profile']
    
    def test_process_profile_section_direct(self):
        """Test processing direct credentials profile section."""
        profiles = {}
        section = {'region': 'us-west-2'}
        
        # Mock section.get method
        mock_section = Mock()
        mock_section.get.side_effect = lambda key: section.get(key)
        
        with patch.object(self.manager, '_get_account_id_from_session') as mock_get_account:
            mock_get_account.return_value = '111111111111'
            
            self.manager._process_profile_section(mock_section, 'direct-profile', profiles)
        
        assert '111111111111' in profiles
        assert profiles['111111111111'].name == 'direct-profile'
        assert profiles['111111111111'].type == 'direct'
        assert profiles['111111111111'].role_arn is None
        assert profiles['111111111111'].source_profile is None
    
    def test_create_session_cached(self):
        """Test creating session from cache."""
        # Setup cached session
        mock_session = Mock()
        session_info = SessionInfo(
            session=mock_session,
            account_id='123456789012',
            account_alias='test-account',
            region='us-east-1',
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=3600)
        )
        
        cache_key = '123456789012:us-east-1'
        self.manager.session_cache[cache_key] = session_info
        
        with patch.object(self.manager, '_is_session_valid', return_value=True):
            session = self.manager.create_session('123456789012', 'us-east-1')
        
        assert session == mock_session
    
    def test_create_session_no_profile(self):
        """Test creating session when no profile found."""
        with patch.object(self.manager, 'get_profiles', return_value={}):
            session = self.manager.create_session('999999999999', 'us-east-1')
        
        assert session is None
    
    def test_create_assume_role_session_success(self):
        """Test creating assume role session successfully."""
        profile_info = ProfileInfo(
            name='test-profile',
            type='assume_role',
            account_id='123456789012',
            role_arn='arn:aws:iam::123456789012:role/TestRole',
            source_profile='default'
        )
        
        # Mock source session and STS client
        mock_source_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'AKIA123',
                'SecretAccessKey': 'secret123',
                'SessionToken': 'token123'
            }
        }
        mock_source_session.client.return_value = mock_sts_client
        
        with patch('boto3.Session') as mock_session_class:
            mock_session_class.side_effect = [mock_source_session, Mock()]
            
            session = self.manager._create_assume_role_session(profile_info, 'us-east-1')
        
        assert session is not None
        mock_sts_client.assume_role.assert_called_once()
        
        # Verify assume_role call parameters
        call_args = mock_sts_client.assume_role.call_args
        assert call_args[1]['RoleArn'] == profile_info.role_arn
        assert call_args[1]['DurationSeconds'] == self.manager.session_duration
        assert 'ic-session-' in call_args[1]['RoleSessionName']
    
    def test_create_assume_role_session_missing_info(self):
        """Test creating assume role session with missing information."""
        # Missing source_profile
        profile_info = ProfileInfo(
            name='test-profile',
            type='assume_role',
            account_id='123456789012',
            role_arn='arn:aws:iam::123456789012:role/TestRole',
            source_profile=None
        )
        
        session = self.manager._create_assume_role_session(profile_info, 'us-east-1')
        assert session is None
        
        # Missing role_arn
        profile_info.source_profile = 'default'
        profile_info.role_arn = None
        
        session = self.manager._create_assume_role_session(profile_info, 'us-east-1')
        assert session is None
    
    def test_create_assume_role_session_failure(self):
        """Test creating assume role session with STS failure."""
        profile_info = ProfileInfo(
            name='test-profile',
            type='assume_role',
            account_id='123456789012',
            role_arn='arn:aws:iam::123456789012:role/TestRole',
            source_profile='default'
        )
        
        # Mock source session to raise exception
        mock_source_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.assume_role.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'AssumeRole'
        )
        mock_source_session.client.return_value = mock_sts_client
        
        with patch('boto3.Session', return_value=mock_source_session):
            session = self.manager._create_assume_role_session(profile_info, 'us-east-1')
        
        assert session is None
    
    def test_create_direct_session_success(self):
        """Test creating direct session successfully."""
        profile_info = ProfileInfo(
            name='direct-profile',
            type='direct',
            account_id='111111111111'
        )
        
        mock_session = Mock()
        
        with patch('boto3.Session', return_value=mock_session) as mock_session_class:
            session = self.manager._create_direct_session(profile_info, 'us-west-2')
        
        assert session == mock_session
        mock_session_class.assert_called_once_with(
            profile_name='direct-profile',
            region_name='us-west-2'
        )
    
    def test_create_direct_session_failure(self):
        """Test creating direct session with failure."""
        profile_info = ProfileInfo(
            name='invalid-profile',
            type='direct',
            account_id='111111111111'
        )
        
        with patch('boto3.Session', side_effect=NoCredentialsError()):
            session = self.manager._create_direct_session(profile_info, 'us-west-2')
        
        assert session is None
    
    def test_is_session_valid_assume_role(self):
        """Test session validity check for assume role sessions."""
        # Valid session (not expired)
        session_info = SessionInfo(
            session=Mock(),
            account_id='123456789012',
            account_alias='test-account',
            region='us-east-1',
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=1800)  # 30 minutes from now
        )
        
        assert self.manager._is_session_valid(session_info) is True
        
        # Expired session
        session_info.expires_at = datetime.now() - timedelta(seconds=300)  # 5 minutes ago
        assert self.manager._is_session_valid(session_info) is False
    
    def test_is_session_valid_direct(self):
        """Test session validity check for direct sessions."""
        # Recent session (valid)
        session_info = SessionInfo(
            session=Mock(),
            account_id='111111111111',
            account_alias='direct-account',
            region='us-west-2',
            created_at=datetime.now() - timedelta(minutes=30),  # 30 minutes ago
            expires_at=None  # Direct sessions don't have expiration
        )
        
        assert self.manager._is_session_valid(session_info) is True
        
        # Old session (should refresh)
        session_info.created_at = datetime.now() - timedelta(hours=2)  # 2 hours ago
        assert self.manager._is_session_valid(session_info) is False
    
    def test_get_account_alias_success(self):
        """Test getting account alias successfully."""
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_iam_client = Mock()
        
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_iam_client.list_account_aliases.return_value = {'AccountAliases': ['test-account']}
        
        mock_session.client.side_effect = lambda service: {
            'sts': mock_sts_client,
            'iam': mock_iam_client
        }[service]
        
        alias = self.manager.get_account_alias(mock_session)
        
        assert alias == 'test-account'
        assert self.manager.account_alias_cache['123456789012'] == 'test-account'
    
    def test_get_account_alias_no_alias(self):
        """Test getting account alias when no alias exists."""
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_iam_client = Mock()
        
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_iam_client.list_account_aliases.return_value = {'AccountAliases': []}
        
        mock_session.client.side_effect = lambda service: {
            'sts': mock_sts_client,
            'iam': mock_iam_client
        }[service]
        
        alias = self.manager.get_account_alias(mock_session)
        
        assert alias == '123456789012'  # Should return account ID
        assert self.manager.account_alias_cache['123456789012'] == '123456789012'
    
    def test_get_account_alias_cached(self):
        """Test getting account alias from cache."""
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_session.client.return_value = mock_sts_client
        
        # Pre-populate cache
        self.manager.account_alias_cache['123456789012'] = 'cached-alias'
        
        alias = self.manager.get_account_alias(mock_session)
        
        assert alias == 'cached-alias'
    
    def test_get_account_alias_failure(self):
        """Test getting account alias with failure."""
        mock_session = Mock()
        mock_session.client.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetCallerIdentity'
        )
        
        alias = self.manager.get_account_alias(mock_session)
        
        assert alias == 'unknown'
    
    def test_create_sessions_parallel(self):
        """Test creating multiple sessions in parallel."""
        account_regions = [
            ('123456789012', 'us-east-1'),
            ('987654321098', 'us-west-2'),
            ('111111111111', 'eu-west-1')
        ]
        
        mock_sessions = {
            '123456789012:us-east-1': Mock(),
            '987654321098:us-west-2': Mock(),
            '111111111111:eu-west-1': Mock()
        }
        
        def mock_create_session(account_id, region):
            cache_key = f"{account_id}:{region}"
            return mock_sessions.get(cache_key)
        
        with patch.object(self.manager, 'create_session', side_effect=mock_create_session):
            sessions = self.manager.create_sessions_parallel(account_regions)
        
        assert len(sessions) == 3
        assert '123456789012:us-east-1' in sessions
        assert '987654321098:us-west-2' in sessions
        assert '111111111111:eu-west-1' in sessions
    
    def test_clear_cache(self):
        """Test clearing all caches."""
        # Populate caches
        self.manager.session_cache['test'] = Mock()
        self.manager.profile_cache['test'] = Mock()
        self.manager.account_alias_cache['test'] = 'test-alias'
        self.manager._profiles_loaded = True
        
        self.manager.clear_cache()
        
        assert self.manager.session_cache == {}
        assert self.manager.profile_cache == {}
        assert self.manager.account_alias_cache == {}
        assert self.manager._profiles_loaded is False
    
    def test_get_session_info(self):
        """Test getting cached session information."""
        mock_session_info = SessionInfo(
            session=Mock(),
            account_id='123456789012',
            account_alias='test-account',
            region='us-east-1',
            created_at=datetime.now()
        )
        
        cache_key = '123456789012:us-east-1'
        self.manager.session_cache[cache_key] = mock_session_info
        
        session_info = self.manager.get_session_info('123456789012', 'us-east-1')
        
        assert session_info == mock_session_info
    
    def test_list_cached_sessions(self):
        """Test listing all cached sessions."""
        mock_session_info1 = SessionInfo(
            session=Mock(),
            account_id='123456789012',
            account_alias='account1',
            region='us-east-1',
            created_at=datetime.now()
        )
        
        mock_session_info2 = SessionInfo(
            session=Mock(),
            account_id='987654321098',
            account_alias='account2',
            region='us-west-2',
            created_at=datetime.now()
        )
        
        self.manager.session_cache['123456789012:us-east-1'] = mock_session_info1
        self.manager.session_cache['987654321098:us-west-2'] = mock_session_info2
        
        cached_sessions = self.manager.list_cached_sessions()
        
        assert len(cached_sessions) == 2
        assert '123456789012:us-east-1' in cached_sessions
        assert '987654321098:us-west-2' in cached_sessions


class TestBackwardCompatibilityFunctions:
    """Test cases for backward compatibility functions."""
    
    @patch('src.ic.core.session.AWSSessionManager')
    def test_get_profiles_backward_compatibility(self, mock_manager_class):
        """Test backward compatibility get_profiles function."""
        from src.ic.core.session import get_profiles
        
        # Mock manager and profiles
        mock_manager = Mock()
        mock_profiles = {
            '123456789012': ProfileInfo('profile1', 'assume_role', '123456789012'),
            '987654321098': ProfileInfo('profile2', 'direct', '987654321098')
        }
        mock_manager.get_profiles.return_value = mock_profiles
        mock_manager_class.return_value = mock_manager
        
        result = get_profiles()
        
        expected = {
            '123456789012': 'profile1',
            '987654321098': 'profile2'
        }
        assert result == expected
    
    @patch('boto3.Session')
    def test_create_session_backward_compatibility(self, mock_session_class):
        """Test backward compatibility create_session function."""
        from src.ic.core.session import create_session
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        session = create_session('test-profile', 'us-east-1')
        
        assert session == mock_session
        mock_session_class.assert_called_once_with(
            profile_name='test-profile',
            region_name='us-east-1'
        )
    
    @patch('boto3.Session')
    def test_create_session_backward_compatibility_failure(self, mock_session_class):
        """Test backward compatibility create_session function with failure."""
        from src.ic.core.session import create_session
        
        mock_session_class.side_effect = NoCredentialsError()
        
        session = create_session('invalid-profile', 'us-east-1')
        
        assert session is None


if __name__ == '__main__':
    pytest.main([__file__])