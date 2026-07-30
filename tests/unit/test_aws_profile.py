#!/usr/bin/env python3
"""
Unit tests for AWS profile information module.

This module tests the AWS profile parser, collector, and renderer functionality.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import modules to test
from ic.platforms.aws.profile.info import AWSProfileParser, ProfileInfoCollector, ProfileTableRenderer


class TestAWSProfileParser(unittest.TestCase):
    """Test cases for AWSProfileParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = AWSProfileParser()
        
        # Create temporary config content
        self.sample_config = """
[default]
region = us-east-1
output = json

[profile dev]
region = us-west-2
role_arn = arn:aws:iam::123456789012:role/DevRole
source_profile = default

[profile prod]
region = us-east-1
role_arn = arn:aws:iam::987654321098:role/ProdRole
source_profile = default
"""
        
        self.sample_credentials = """
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

[dev]
aws_access_key_id = AKIAI44QH8DHBEXAMPLE
aws_secret_access_key = je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY
"""
    
    def test_parse_config_file_success(self):
        """Test successful parsing of AWS config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f:
            f.write(self.sample_config)
            config_path = f.name
        
        try:
            result = self.parser.parse_config_file(config_path)
            
            # Verify parsing results
            self.assertIn('default', result)
            self.assertIn('dev', result)
            self.assertIn('prod', result)
            
            # Check specific values
            self.assertEqual(result['default']['region'], 'us-east-1')
            self.assertEqual(result['dev']['region'], 'us-west-2')
            self.assertIn('role_arn', result['dev'])
            
        finally:
            os.unlink(config_path)
    
    def test_parse_config_file_not_found(self):
        """Test handling of missing config file."""
        result = self.parser.parse_config_file('/nonexistent/path')
        self.assertEqual(result, {})
    
    def test_parse_credentials_file_success(self):
        """Test successful parsing of AWS credentials file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.credentials', delete=False) as f:
            f.write(self.sample_credentials)
            creds_path = f.name
        
        try:
            result = self.parser.parse_credentials_file(creds_path)
            
            # Verify parsing results
            self.assertIn('default', result)
            self.assertIn('dev', result)
            
            # Check specific values
            self.assertIn('aws_access_key_id', result['default'])
            self.assertIn('aws_secret_access_key', result['default'])
            
        finally:
            os.unlink(creds_path)
    
    def test_extract_account_from_role_arn(self):
        """Test account ID extraction from role ARN."""
        test_cases = [
            ('arn:aws:iam::123456789012:role/TestRole', '123456789012'),
            ('arn:aws:iam::987654321098:role/AnotherRole', '987654321098'),
            ('invalid-arn', None),
            ('', None),
            (None, None)
        ]
        
        for arn, expected in test_cases:
            with self.subTest(arn=arn):
                result = self.parser.extract_account_from_role_arn(arn)
                self.assertEqual(result, expected)
    
    def test_extract_role_name_from_arn(self):
        """Test role name extraction from role ARN."""
        test_cases = [
            ('arn:aws:iam::123456789012:role/TestRole', 'TestRole'),
            ('arn:aws:iam::987654321098:role/path/to/AnotherRole', 'AnotherRole'),
            ('invalid-arn', None),
            ('', None),
            (None, None)
        ]
        
        for arn, expected in test_cases:
            with self.subTest(arn=arn):
                result = self.parser.extract_role_name_from_arn(arn)
                self.assertEqual(result, expected)


class TestProfileInfoCollector(unittest.TestCase):
    """Test cases for ProfileInfoCollector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.collector = ProfileInfoCollector()
    
    @patch.object(AWSProfileParser, 'parse_config_file')
    @patch.object(AWSProfileParser, 'parse_credentials_file')
    def test_collect_profile_info(self, mock_creds, mock_config):
        """Test profile information collection."""
        # Mock return values
        mock_config.return_value = {
            'default': {'region': 'us-east-1'},
            'dev': {
                'region': 'us-west-2',
                'role_arn': 'arn:aws:iam::123456789012:role/DevRole',
                'source_profile': 'default'
            }
        }
        
        mock_creds.return_value = {
            'default': {'aws_access_key_id': 'AKIA...'},
            'dev': {'aws_access_key_id': 'AKIA...'}
        }
        
        result = self.collector.collect_profile_info()
        
        # Verify results
        self.assertEqual(len(result), 2)
        
        # Find profiles by name
        default_profile = next(p for p in result if p['profile_name'] == 'default')
        dev_profile = next(p for p in result if p['profile_name'] == 'dev')
        
        # Check default profile
        self.assertEqual(default_profile['region'], 'us-east-1')
        self.assertEqual(default_profile['credential'], 'active')
        
        # Check dev profile
        self.assertEqual(dev_profile['region'], 'us-west-2')
        self.assertEqual(dev_profile['account_id'], '123456789012')
        self.assertEqual(dev_profile['role_name'], 'DevRole')
        self.assertEqual(dev_profile['source'], 'default')
    
    def test_merge_config_and_credentials(self):
        """Test merging of config and credentials data."""
        config_data = {
            'default': {'region': 'us-east-1'},
            'prod': {
                'region': 'us-west-1',
                'role_arn': 'arn:aws:iam::987654321098:role/ProdRole'
            }
        }
        
        creds_data = {
            'default': {'aws_access_key_id': 'AKIA...'},
            'staging': {'aws_access_key_id': 'AKIA...'}
        }
        
        result = self.collector.merge_config_and_credentials(config_data, creds_data)
        
        # Should have all unique profiles
        profile_names = [p['profile_name'] for p in result]
        self.assertIn('default', profile_names)
        self.assertIn('prod', profile_names)
        self.assertIn('staging', profile_names)
        
        # Check credential status
        default_profile = next(p for p in result if p['profile_name'] == 'default')
        prod_profile = next(p for p in result if p['profile_name'] == 'prod')
        staging_profile = next(p for p in result if p['profile_name'] == 'staging')
        
        self.assertEqual(default_profile['credential'], 'active')
        self.assertEqual(prod_profile['credential'], 'inactive')
        self.assertEqual(staging_profile['credential'], 'active')


class TestProfileTableRenderer(unittest.TestCase):
    """Test cases for ProfileTableRenderer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.renderer = ProfileTableRenderer()
    
    def test_render_profiles_empty(self):
        """Test rendering with empty profile list."""
        with patch.object(self.renderer, 'console') as mock_console:
            self.renderer.render_profiles([])
            
            # Verify console.print was called with appropriate message
            mock_console.print.assert_called()
            call_args = [call[0][0] for call in mock_console.print.call_args_list]
            self.assertTrue(any('No AWS profiles found' in str(arg) for arg in call_args))
    
    def test_render_profiles_with_data(self):
        """Test rendering with profile data."""
        profiles = [
            {
                'profile_name': 'default',
                'account_id': '123456789012',
                'source': '',
                'role_name': '',
                'credential': 'active',
                'region': 'us-east-1'
            },
            {
                'profile_name': 'dev',
                'account_id': '123456789012',
                'source': 'default',
                'role_name': 'DevRole',
                'credential': 'inactive',
                'region': 'us-west-2'
            }
        ]
        
        with patch.object(self.renderer, 'console') as mock_console:
            self.renderer.render_profiles(profiles)
            
            # Verify console.print was called (table and summary)
            self.assertTrue(mock_console.print.called)
            
            # Check that summary information is printed
            call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
            summary_found = any('Total profiles: 2' in arg for arg in call_args)
            self.assertTrue(summary_found)


if __name__ == '__main__':
    unittest.main()