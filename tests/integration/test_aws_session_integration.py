"""
Integration tests for AWS session creation with real profile configurations.

Tests AWS session management with various profile types and configurations.
"""

import os
import tempfile
import configparser
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from ic.core.session import AWSSessionManager, ProfileInfo
from ic.core.logging import ICLogger


class TestAWSSessionIntegration:
    """Integration tests for AWS session management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.config.session_duration = 3600
        self.config.max_workers = 5
        
        self.logger_config = {
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'mask_sensitive': True
            }
        }
        self.logger = ICLogger(self.logger_config)
        
        # Sample AWS config content for testing
        self.aws_config_content = """
[default]
region = us-east-1
output = json

[profile test-direct]
region = us-west-2
output = json

[profile test-assume-role]
role_arn = arn:aws:iam::123456789012:role/TestRole
source_profile = default
region = us-east-1
session_name = test-session

[profile cross-account-role]
role_arn = arn:aws:iam::987654321098:role/CrossAccountRole
source_profile = test-direct
region = eu-west-1
duration_seconds = 7200

[profile invalid-role]
role_arn = arn:aws:iam::111111111111:role/InvalidRole
source_profile = nonexistent-profile
region = us-central-1
"""
    
    def create_temp_aws_config(self, content):
        """Create temporary AWS config file."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.config')
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    def test_profile_loading_integration(self):
        """Test loading profiles from real AWS config file."""
        temp_config_file = self.create_temp_aws_config(self.aws_config_content)
        
        try:
            with patch('os.path.expanduser', return_value=temp_config_file):
                manager = AWSSessionManager(self.config)
                
                # Mock account ID retrieval for direct profiles
                with patch.object(manager, '_get_account_id_from_session') as mock_get_account:
                    mock_get_account.side_effect = lambda profile: {
                        'default': '111111111111',
                        'test-direct': '222222222222'
                    }.get(profile)
                    
                    profiles = manager.get_profiles()
            
            # Verify assume role profiles were detected
            assert '123456789012' in profiles
            assert profiles['123456789012'].type == 'assume_role'
            assert profiles['123456789012'].name == 'test-assume-role'
            assert profiles['123456789012'].source_profile == 'default'
            
            assert '987654321098' in profiles
            assert profiles['987654321098'].type == 'assume_role'
            assert profiles['987654321098'].name == 'cross-account-role'
            assert profiles['987654321098'].source_profile == 'test-direct'
            
            # Verify direct profiles were detected
            assert '111111111111' in profiles
            assert profiles['111111111111'].type == 'direct'
            assert profiles['111111111111'].name == 'default'
            
            assert '222222222222' in profiles
            assert profiles['222222222222'].type == 'direct'
            assert profiles['222222222222'].name == 'test-direct'
            
        finally:
            os.unlink(temp_config_file)
    
    @patch('boto3.Session')
    def test_direct_session_creation_integration(self, mock_session_class):
        """Test creating direct credential sessions."""
        temp_config_file = self.create_temp_aws_config(self.aws_config_content)
        
        try:
            with patch('os.path.expanduser', return_value=temp_config_file):
                manager = AWSSessionManager(self.config)
                
                # Mock successful session creation
                mock_session = Mock()
                mock_sts_client = Mock()
                mock_iam_client = Mock()
                
                mock_sts_client.get_caller_identity.return_value = {'Account': '222222222222'}
                mock_iam_client.list_account_aliases.return_value = {'AccountAliases': ['test-account']}
                
                mock_session.client.side_effect = lambda service: {
                    'sts': mock_sts_client,
                    'iam': mock_iam_client
                }[service]
                
                mock_session_class.return_value = mock_session
                
                # Mock account ID retrieval
                with patch.object(manager, '_get_account_id_from_session', return_value='222222222222'):
                    # Load profiles first
                    profiles = manager.get_profiles()
                    
                    # Create session
                    session = manager.create_session('222222222222', 'us-west-2')
                
                assert session is not None
                assert session == mock_session
                
                # Verify session was cached
                cached_session = manager.get_session_info('222222222222', 'us-west-2')
                assert cached_session is not None
                assert cached_session.session == mock_session
                assert cached_session.account_alias == 'test-account'
                
        finally:
            os.unlink(temp_config_file)
    
    @patch('boto3.Session')
    def test_assume_role_session_creation_integration(self, mock_session_class):
        """Test creating assume role sessions."""
        temp_config_file = self.create_temp_aws_config(self.aws_config_content)
        
        try:
            with patch('os.path.expanduser', return_value=temp_config_file):
                manager = AWSSessionManager(self.config)
                
                # Mock source session and assume role response
                mock_source_session = Mock()
                mock_target_session = Mock()
                mock_sts_client = Mock()
                mock_iam_client = Mock()
                
                # Mock assume role response
                mock_sts_client.assume_role.return_value = {
                    'Credentials': {
                        'AccessKeyId': 'AKIA123EXAMPLE',
                        'SecretAccessKey': 'secret123example',
                        'SessionToken': 'token123example'
                    }
                }
                
                # Mock account alias retrieval
                mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
                mock_iam_client.list_account_aliases.return_value = {'AccountAliases': ['target-account']}
                
                mock_source_session.client.return_value = mock_sts_client
                mock_target_session.client.side_effect = lambda service: {
                    'sts': mock_sts_client,
                    'iam': mock_iam_client
                }[service]
                
                # Mock session creation
                mock_session_class.side_effect = [mock_source_session, mock_target_session]
                
                # Mock account ID retrieval for direct profiles
                with patch.object(manager, '_get_account_id_from_session', return_value='111111111111'):
                    # Load profiles first
                    profiles = manager.get_profiles()
                    
                    # Create assume role session
                    session = manager.create_session('123456789012', 'us-east-1')
                
                assert session is not None
                assert session == mock_target_session
                
                # Verify assume role was called correctly
                mock_sts_client.assume_role.assert_called_once()
                call_args = mock_sts_client.assume_role.call_args
                assert call_args[1]['RoleArn'] == 'arn:aws:iam::123456789012:role/TestRole'
                assert call_args[1]['DurationSeconds'] == 3600
                assert 'ic-session-' in call_args[1]['RoleSessionName']
                
                # Verify session was cached with expiration
                cached_session = manager.get_session_info('123456789012', 'us-east-1')
                assert cached_session is not None
                assert cached_session.expires_at is not None
                
        finally:
            os.unlink(temp_config_file)
    
    @patch('boto3.Session')
    def test_parallel_session_creation_integration(self, mock_session_class):
        """Test creating multiple sessions in parallel."""
        temp_config_file = self.create_temp_aws_config(self.aws_config_content)
        
        try:
            with patch('os.path.expanduser', return_value=temp_config_file):
                manager = AWSSessionManager(self.config)
                
                # Mock sessions for different accounts
                mock_sessions = {}
                for i, account_id in enumerate(['111111111111', '222222222222', '123456789012']):
                    mock_session = Mock()
                    mock_sts_client = Mock()
                    mock_iam_client = Mock()
                    
                    mock_sts_client.get_caller_identity.return_value = {'Account': account_id}
                    mock_iam_client.list_account_aliases.return_value = {
                        'AccountAliases': [f'account-{i+1}']
                    }
                    
                    if account_id == '123456789012':  # Assume role account
                        mock_sts_client.assume_role.return_value = {
                            'Credentials': {
                                'AccessKeyId': f'AKIA{i}EXAMPLE',
                                'SecretAccessKey': f'secret{i}example',
                                'SessionToken': f'token{i}example'
                            }
                        }
                    
                    mock_session.client.side_effect = lambda service: {
                        'sts': mock_sts_client,
                        'iam': mock_iam_client
                    }[service]
                    
                    mock_sessions[account_id] = mock_session
                
                # Mock session creation to return appropriate sessions
                def mock_session_side_effect(*args, **kwargs):
                    if 'aws_access_key_id' in kwargs:
                        return mock_sessions['123456789012']  # Assume role session
                    elif kwargs.get('profile_name') == 'default':
                        return mock_sessions['111111111111']
                    elif kwargs.get('profile_name') == 'test-direct':
                        return mock_sessions['222222222222']
                    else:
                        return mock_sessions['111111111111']  # Default
                
                mock_session_class.side_effect = mock_session_side_effect
                
                # Mock account ID retrieval
                with patch.object(manager, '_get_account_id_from_session') as mock_get_account:
                    mock_get_account.side_effect = lambda profile: {
                        'default': '111111111111',
                        'test-direct': '222222222222'
                    }.get(profile)
                    
                    # Load profiles first
                    profiles = manager.get_profiles()
                    
                    # Create sessions in parallel
                    account_regions = [
                        ('111111111111', 'us-east-1'),
                        ('222222222222', 'us-west-2'),
                        ('123456789012', 'us-east-1')
                    ]
                    
                    sessions = manager.create_sessions_parallel(account_regions)
                
                # Verify all sessions were created
                assert len(sessions) == 3
                assert '111111111111:us-east-1' in sessions
                assert '222222222222:us-west-2' in sessions
                assert '123456789012:us-east-1' in sessions
                
                # Verify sessions are cached
                for account_id, region in account_regions:
                    cached_session = manager.get_session_info(account_id, region)
                    assert cached_session is not None
                
        finally:
            os.unlink(temp_config_file)
    
    @patch('pathlib.Path.exists', return_value=False)
    @patch('boto3.Session')
    def test_session_caching_and_expiration_integration(self, mock_session_class, mock_path_exists):
        """Test session caching and expiration logic."""
        temp_config_file = self.create_temp_aws_config(self.aws_config_content)
        
        try:
            with patch('os.path.expanduser', return_value=temp_config_file):
                manager = AWSSessionManager(self.config)
                
                # Mock session
                mock_session = Mock()
                mock_sts_client = Mock()
                mock_iam_client = Mock()
                
                mock_sts_client.get_caller_identity.return_value = {'Account': '111111111111'}
                mock_iam_client.list_account_aliases.return_value = {'AccountAliases': ['test-account']}
                
                mock_session.client.side_effect = lambda service: {
                    'sts': mock_sts_client,
                    'iam': mock_iam_client
                }[service]
                
                mock_session_class.return_value = mock_session
                
                # Mock account ID retrieval
                with patch.object(manager, '_get_account_id_from_session', return_value='111111111111'):
                    # Load profiles first
                    profiles = manager.get_profiles()
                    mock_session_class.reset_mock()
                    
                    # Create session first time
                    session1 = manager.create_session('111111111111', 'us-east-1')
                    
                    # Create session second time (should use cache)
                    session2 = manager.create_session('111111111111', 'us-east-1')
                
                # Should return same session from cache
                assert session1 is session2
                
                # Verify only one session was created
                assert mock_session_class.call_count == 1
                
                # Test cache clearing
                manager.clear_cache()
                
                # Create session after cache clear
                session3 = manager.create_session('111111111111', 'us-east-1')
                
                # Should create new session
                assert session3 is not None
                assert mock_session_class.call_count > 1
                
        finally:
            os.unlink(temp_config_file)
    
    @patch('boto3.Session')
    def test_error_handling_integration(self, mock_session_class):
        """Test error handling in session creation."""
        temp_config_file = self.create_temp_aws_config(self.aws_config_content)
        
        try:
            with patch('os.path.expanduser', return_value=temp_config_file):
                manager = AWSSessionManager(self.config)
                
                # Test with credentials error
                mock_session_class.side_effect = NoCredentialsError()
                
                with patch.object(manager, '_get_account_id_from_session', return_value=None):
                    profiles = manager.get_profiles()
                    
                    # Should handle error gracefully
                    session = manager.create_session('999999999999', 'us-east-1')
                    assert session is None
                
                # Test assume role failure
                mock_session_class.side_effect = None
                mock_source_session = Mock()
                mock_sts_client = Mock()
                
                # Mock assume role failure
                mock_sts_client.assume_role.side_effect = ClientError(
                    {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                    'AssumeRole'
                )
                
                mock_source_session.client.return_value = mock_sts_client
                mock_session_class.return_value = mock_source_session
                
                with patch.object(manager, '_get_account_id_from_session', return_value='111111111111'):
                    profiles = manager.get_profiles()
                    
                    # Should handle assume role failure gracefully
                    session = manager.create_session('123456789012', 'us-east-1')
                    assert session is None
                
        finally:
            os.unlink(temp_config_file)
    
    def test_account_alias_resolution_integration(self):
        """Test account alias resolution with various scenarios."""
        with patch('boto3.Session') as mock_session_class:
            manager = AWSSessionManager(self.config)
            
            # Test with account alias available
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_iam_client = Mock()
            
            mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
            mock_iam_client.list_account_aliases.return_value = {'AccountAliases': ['my-company']}
            
            mock_session.client.side_effect = lambda service: {
                'sts': mock_sts_client,
                'iam': mock_iam_client
            }[service]
            
            alias = manager.get_account_alias(mock_session)
            assert alias == 'my-company'
            
            # Test with no account alias (should return account ID)
            manager.account_alias_cache.clear()
            mock_iam_client.list_account_aliases.return_value = {'AccountAliases': []}
            
            alias = manager.get_account_alias(mock_session)
            assert alias == '123456789012'
            
            # Test with IAM access denied (should return account ID)
            manager.account_alias_cache.clear()
            mock_iam_client.list_account_aliases.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                'ListAccountAliases'
            )
            
            alias = manager.get_account_alias(mock_session)
            assert alias == '123456789012'
            
            # Test with complete failure (should return 'unknown')
            manager.account_alias_cache.clear()
            mock_session.client.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                'GetCallerIdentity'
            )
            
            alias = manager.get_account_alias(mock_session)
            assert alias == 'unknown'
    
    def test_configuration_integration_with_logging(self):
        """Test AWS session manager integration with logging system."""
        temp_config_file = self.create_temp_aws_config(self.aws_config_content)
        
        try:
            with patch('os.path.expanduser', return_value=temp_config_file):
                # Create manager with logging
                manager = AWSSessionManager(self.config)
                
                with patch('ic.core.session.logger') as mock_logger:
                    # Mock account ID retrieval
                    with patch.object(manager, '_get_account_id_from_session', return_value='111111111111'):
                        profiles = manager.get_profiles()
                    
                    # Verify logging calls were made
                    assert mock_logger.log_info_file_only.called
                    
                    # Check that sensitive information is not logged
                    log_calls = [call[0][0] for call in mock_logger.log_info_file_only.call_args_list]
                    for log_message in log_calls:
                        assert 'secret' not in log_message.lower()
                        assert 'password' not in log_message.lower()
                        assert 'token' not in log_message.lower()
                
        finally:
            os.unlink(temp_config_file)


if __name__ == '__main__':
    pytest.main([__file__])