"""
Integration tests for AWS CloudFront CLI functionality.

Tests CloudFront command integration with CLI, session management, and error handling.
"""

import os
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from aws.cloudfront.info import CloudFrontCollector, CloudFrontRenderer


class TestCloudFrontCLIIntegration:
    """Integration tests for CloudFront CLI functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Sample CloudFront distribution data for mocking
        self.sample_distributions_response = {
            'DistributionList': {
                'Items': [
                    {
                        'Id': 'E1234567890ABC',
                        'Comment': 'Production Website Distribution',
                        'DomainName': 'd1234567890abc.cloudfront.net',
                        'PriceClass': 'PriceClass_All',
                        'Origins': {
                            'Items': [
                                {
                                    'DomainName': 'prod.example.com',
                                    'Id': 'prod-origin'
                                }
                            ]
                        }
                    },
                    {
                        'Id': 'E0987654321XYZ',
                        'Comment': 'API Distribution',
                        'DomainName': 'd0987654321xyz.cloudfront.net',
                        'PriceClass': 'PriceClass_200',
                        'Origins': {
                            'Items': [
                                {'DomainName': 'api1.example.com', 'Id': 'api1'},
                                {'DomainName': 'api2.example.com', 'Id': 'api2'}
                            ]
                        }
                    }
                ]
            }
        }
        
        self.empty_distributions_response = {
            'DistributionList': {}
        }
    
    @patch('boto3.Session')
    def test_cloudfront_collector_integration_success(self, mock_session_class):
        """Test CloudFront collector integration with real-like AWS API responses."""
        # Mock AWS session and CloudFront client
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        mock_cloudfront_client.list_distributions.return_value = self.sample_distributions_response
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        # Test collector
        collector = CloudFrontCollector()
        account_profiles = {
            'production': 'prod-profile',
            'staging': 'staging-profile'
        }
        
        distributions = collector.collect_distributions(account_profiles)
        
        # Verify results
        assert len(distributions) == 4  # 2 distributions × 2 accounts
        
        # Check first distribution details
        prod_dist = next(d for d in distributions if d['ID'] == 'E1234567890ABC')
        assert prod_dist['Name'] == 'Production Website Distribution'
        assert prod_dist['원본(Origin)'] == 'prod.example.com'
        assert prod_dist['Class'] == 'All Edge Locations'
        
        # Check second distribution details
        api_dist = next(d for d in distributions if d['ID'] == 'E0987654321XYZ')
        assert api_dist['Name'] == 'API Distribution'
        assert api_dist['원본(Origin)'] == 'Multiple (2)'
        assert api_dist['Class'] == 'North America and Europe Only'
        
        # Verify AWS API calls
        assert mock_session_class.call_count == 2
        assert mock_cloudfront_client.list_distributions.call_count == 2
    
    @patch('boto3.Session')
    def test_cloudfront_collector_integration_empty_response(self, mock_session_class):
        """Test CloudFront collector with empty AWS response."""
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        mock_cloudfront_client.list_distributions.return_value = self.empty_distributions_response
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        collector = CloudFrontCollector()
        account_profiles = {'test-account': 'test-profile'}
        
        distributions = collector.collect_distributions(account_profiles)
        
        assert distributions == []
        mock_cloudfront_client.list_distributions.assert_called_once()
    
    @patch('boto3.Session')
    def test_cloudfront_collector_integration_access_denied(self, mock_session_class):
        """Test CloudFront collector with access denied error."""
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        # Mock access denied error
        mock_cloudfront_client.list_distributions.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'User is not authorized'}},
            'ListDistributions'
        )
        
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        collector = CloudFrontCollector()
        account_profiles = {'test-account': 'test-profile'}
        
        with patch.object(collector.console, 'print') as mock_print:
            distributions = collector.collect_distributions(account_profiles)
        
        assert distributions == []
        mock_print.assert_called_once()
        assert 'Access denied' in str(mock_print.call_args)
    
    @patch('boto3.Session')
    def test_cloudfront_collector_integration_no_credentials(self, mock_session_class):
        """Test CloudFront collector with no credentials error."""
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        # Mock no credentials error
        mock_cloudfront_client.list_distributions.side_effect = NoCredentialsError()
        
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        collector = CloudFrontCollector()
        account_profiles = {'test-account': 'test-profile'}
        
        with patch.object(collector.console, 'print') as mock_print:
            distributions = collector.collect_distributions(account_profiles)
        
        assert distributions == []
        mock_print.assert_called_once()
        assert 'No credentials available' in str(mock_print.call_args)
    
    @patch('boto3.Session')
    def test_cloudfront_collector_integration_mixed_results(self, mock_session_class):
        """Test CloudFront collector with mixed success/failure results."""
        # First account succeeds
        mock_session_success = Mock()
        mock_cloudfront_client_success = Mock()
        mock_cloudfront_client_success.list_distributions.return_value = self.sample_distributions_response
        mock_session_success.client.return_value = mock_cloudfront_client_success
        
        # Second account fails
        mock_session_fail = Mock()
        mock_cloudfront_client_fail = Mock()
        mock_cloudfront_client_fail.list_distributions.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'ListDistributions'
        )
        mock_session_fail.client.return_value = mock_cloudfront_client_fail
        
        # Mock session creation to return different sessions
        mock_session_class.side_effect = [mock_session_success, mock_session_fail]
        
        collector = CloudFrontCollector()
        account_profiles = {
            'success-account': 'success-profile',
            'fail-account': 'fail-profile'
        }
        
        with patch.object(collector.console, 'print') as mock_print:
            distributions = collector.collect_distributions(account_profiles)
        
        # Should have distributions from successful account only
        assert len(distributions) == 2
        assert all(d['account'] == 'success-account' for d in distributions)
        
        # Should have printed error for failed account
        mock_print.assert_called_once()
        assert 'fail-account' in str(mock_print.call_args)
    
    def test_cloudfront_renderer_integration_with_real_data(self):
        """Test CloudFront renderer with realistic distribution data."""
        renderer = CloudFrontRenderer()
        
        # Realistic distribution data
        distributions = [
            {
                'account': 'production',
                'ID': 'E1A2B3C4D5E6F7',
                'Name': 'www.example.com Distribution',
                '원본(Origin)': 'www.example.com',
                '도메인(Domain)': 'd1a2b3c4d5e6f7.cloudfront.net',
                'Class': 'All Edge Locations'
            },
            {
                'account': 'production',
                'ID': 'E7F6E5D4C3B2A1',
                'Name': 'API Gateway Distribution',
                '원본(Origin)': 'Multiple (3)',
                '도메인(Domain)': 'd7f6e5d4c3b2a1.cloudfront.net',
                'Class': 'North America and Europe Only'
            },
            {
                'account': 'staging',
                'ID': 'E9G8H7I6J5K4L3',
                'Name': 'Staging Environment',
                '원본(Origin)': 'staging.example.com',
                '도메인(Domain)': 'd9g8h7i6j5k4l3.cloudfront.net',
                'Class': 'North America Only'
            }
        ]
        
        with patch.object(renderer.console, 'print') as mock_print:
            renderer.render_distributions(distributions)
        
        # Verify table was created and printed
        assert mock_print.call_count >= 2
        
        # Check that all distributions are included in output
        print_calls = [str(call) for call in mock_print.call_args_list]
        combined_output = ' '.join(print_calls)
        
        assert 'E1A2B3C4D5E6F7' in combined_output
        assert 'E7F6E5D4C3B2A1' in combined_output
        assert 'E9G8H7I6J5K4L3' in combined_output
        assert 'Total distributions: 3' in combined_output
    
    def test_cloudfront_renderer_integration_empty_data(self):
        """Test CloudFront renderer with no distributions."""
        renderer = CloudFrontRenderer()
        
        with patch.object(renderer.console, 'print') as mock_print:
            renderer.render_distributions([])
        
        mock_print.assert_called_once()
        assert 'No CloudFront distributions found' in str(mock_print.call_args)
    
    @patch('boto3.Session')
    def test_cloudfront_end_to_end_integration(self, mock_session_class):
        """Test complete CloudFront workflow from collection to rendering."""
        # Mock AWS session and response
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        mock_cloudfront_client.list_distributions.return_value = self.sample_distributions_response
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        # Create collector and renderer
        collector = CloudFrontCollector()
        renderer = CloudFrontRenderer()
        
        # Execute complete workflow
        account_profiles = {'production': 'prod-profile'}
        
        # Collect distributions
        distributions = collector.collect_distributions(account_profiles)
        
        # Render distributions
        with patch.object(renderer.console, 'print') as mock_print:
            renderer.render_distributions(distributions)
        
        # Verify end-to-end results
        assert len(distributions) == 2
        assert mock_print.call_count >= 2
        
        # Check that specific distribution details are rendered
        print_calls = [str(call) for call in mock_print.call_args_list]
        combined_output = ' '.join(print_calls)
        
        assert 'Production Website Distribution' in combined_output
        assert 'API Distribution' in combined_output
        assert 'Total distributions: 2' in combined_output
    
    def test_cloudfront_price_class_formatting_integration(self):
        """Test price class formatting in integration context."""
        collector = CloudFrontCollector()
        
        # Test all price class mappings
        test_cases = [
            ('PriceClass_All', 'All Edge Locations'),
            ('PriceClass_200', 'North America and Europe Only'),
            ('PriceClass_100', 'North America Only'),
            ('PriceClass_Custom', 'PriceClass_Custom')  # Unknown class
        ]
        
        for input_class, expected_output in test_cases:
            result = collector.format_price_class(input_class)
            assert result == expected_output
    
    def test_cloudfront_origin_handling_integration(self):
        """Test origin handling in integration context."""
        collector = CloudFrontCollector()
        
        # Test various origin scenarios
        test_cases = [
            ([], 'N/A'),  # No origins
            ([{'DomainName': 'single.example.com'}], 'single.example.com'),  # Single origin
            ([
                {'DomainName': 'origin1.example.com'},
                {'DomainName': 'origin2.example.com'},
                {'DomainName': 'origin3.example.com'}
            ], 'Multiple (3)')  # Multiple origins
        ]
        
        for origins, expected_output in test_cases:
            result = collector.get_primary_origin(origins)
            assert result == expected_output
    
    @patch('boto3.Session')
    def test_cloudfront_session_management_integration(self, mock_session_class):
        """Test CloudFront integration with session management."""
        # Test multiple profile handling
        profiles = ['profile1', 'profile2', 'profile3']
        mock_sessions = []
        
        for i, profile in enumerate(profiles):
            mock_session = Mock()
            mock_cloudfront_client = Mock()
            
            # Each profile returns different distributions
            mock_cloudfront_client.list_distributions.return_value = {
                'DistributionList': {
                    'Items': [{
                        'Id': f'E{i}234567890ABC',
                        'Comment': f'Distribution {i+1}',
                        'DomainName': f'd{i}234567890abc.cloudfront.net',
                        'PriceClass': 'PriceClass_All',
                        'Origins': {'Items': [{'DomainName': f'origin{i+1}.example.com'}]}
                    }]
                }
            }
            
            mock_session.client.return_value = mock_cloudfront_client
            mock_sessions.append(mock_session)
        
        mock_session_class.side_effect = mock_sessions
        
        collector = CloudFrontCollector()
        account_profiles = {f'account{i+1}': profile for i, profile in enumerate(profiles)}
        
        distributions = collector.collect_distributions(account_profiles)
        
        # Verify all profiles were used
        assert len(distributions) == 3
        assert mock_session_class.call_count == 3
        
        # Verify each profile was called correctly
        for i, profile in enumerate(profiles):
            mock_session_class.assert_any_call(profile_name=profile)
        
        # Verify distribution data
        for i, dist in enumerate(distributions):
            assert dist['ID'] == f'E{i}234567890ABC'
            assert dist['Name'] == f'Distribution {i+1}'
    
    def test_cloudfront_error_resilience_integration(self):
        """Test CloudFront error handling resilience in integration context."""
        collector = CloudFrontCollector()
        
        # Test with various error scenarios
        with patch('boto3.Session') as mock_session_class:
            # Simulate different types of failures
            error_scenarios = [
                NoCredentialsError(),
                ClientError({'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}, 'ListDistributions'),
                ClientError({'Error': {'Code': 'Throttling', 'Message': 'Rate exceeded'}}, 'ListDistributions'),
                Exception("Unexpected error")
            ]
            
            for i, error in enumerate(error_scenarios):
                mock_session = Mock()
                mock_cloudfront_client = Mock()
                mock_cloudfront_client.list_distributions.side_effect = error
                mock_session.client.return_value = mock_cloudfront_client
                mock_session_class.return_value = mock_session
                
                account_profiles = {f'account{i+1}': f'profile{i+1}'}
                
                with patch.object(collector.console, 'print') as mock_print:
                    distributions = collector.collect_distributions(account_profiles)
                
                # Should handle all errors gracefully
                assert distributions == []
                mock_print.assert_called_once()
                
                # Reset mock for next iteration
                mock_session_class.reset_mock()


class TestCloudFrontCLICommandIntegration:
    """Integration tests for CloudFront CLI command functionality."""
    
    def test_cli_command_handler_structure(self):
        """Test that CLI command handler is properly structured."""
        # Import the CLI handler function
        from src.ic.cli import handle_aws_cloudfront_info
        
        # Verify function exists and is callable
        assert callable(handle_aws_cloudfront_info)
        
        # Test with mock arguments
        mock_args = Mock()
        mock_args.profile = 'test-profile'
        mock_args.accounts = None
        
        with patch('aws.cloudfront.info.CloudFrontCollector') as mock_collector_class:
            with patch('aws.cloudfront.info.CloudFrontRenderer') as mock_renderer_class:
                mock_collector = Mock()
                mock_renderer = Mock()
                mock_collector.collect_distributions.return_value = []
                
                mock_collector_class.return_value = mock_collector
                mock_renderer_class.return_value = mock_renderer
                
                # Should not raise exception
                try:
                    handle_aws_cloudfront_info(mock_args)
                except SystemExit:
                    pass  # Expected for successful execution
                
                # Verify collector and renderer were used
                mock_collector_class.assert_called_once()
                mock_renderer_class.assert_called_once()
                mock_collector.collect_distributions.assert_called_once()
                mock_renderer.render_distributions.assert_called_once()
    
    def test_cli_argument_parsing_integration(self):
        """Test CLI argument parsing for CloudFront commands."""
        # This would typically test the actual CLI parsing
        # For now, we'll test the expected argument structure
        
        expected_args = {
            'profile': 'test-profile',
            'accounts': ['account1', 'account2']
        }
        
        # Verify that the expected arguments can be processed
        from src.ic.cli import handle_aws_cloudfront_info
        
        mock_args = Mock()
        for key, value in expected_args.items():
            setattr(mock_args, key, value)
        
        with patch('aws.cloudfront.info.CloudFrontCollector') as mock_collector_class:
            with patch('aws.cloudfront.info.CloudFrontRenderer') as mock_renderer_class:
                mock_collector = Mock()
                mock_renderer = Mock()
                mock_collector.collect_distributions.return_value = []
                
                mock_collector_class.return_value = mock_collector
                mock_renderer_class.return_value = mock_renderer
                
                try:
                    handle_aws_cloudfront_info(mock_args)
                except SystemExit:
                    pass
                
                # Verify arguments were processed correctly
                call_args = mock_collector.collect_distributions.call_args[0][0]
                assert 'account1' in call_args
                assert 'account2' in call_args


if __name__ == '__main__':
    pytest.main([__file__])