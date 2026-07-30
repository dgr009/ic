"""
Unit tests for AWS CloudFront information collector and renderer.

Tests CloudFront distribution data collection, formatting, and table rendering.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError

from ic.platforms.aws.cloudfront.info import CloudFrontCollector, CloudFrontRenderer


class TestCloudFrontCollector:
    """Test cases for CloudFrontCollector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.collector = CloudFrontCollector()
        
        # Sample CloudFront distribution data
        self.sample_distribution = {
            'Id': 'E1234567890ABC',
            'Comment': 'Test Distribution',
            'DomainName': 'd1234567890abc.cloudfront.net',
            'PriceClass': 'PriceClass_All',
            'Origins': {
                'Items': [
                    {
                        'DomainName': 'example.com',
                        'Id': 'origin1'
                    }
                ]
            }
        }
        
        self.sample_distribution_multiple_origins = {
            'Id': 'E0987654321XYZ',
            'Comment': 'Multi-Origin Distribution',
            'DomainName': 'd0987654321xyz.cloudfront.net',
            'PriceClass': 'PriceClass_200',
            'Origins': {
                'Items': [
                    {'DomainName': 'origin1.example.com', 'Id': 'origin1'},
                    {'DomainName': 'origin2.example.com', 'Id': 'origin2'},
                    {'DomainName': 'origin3.example.com', 'Id': 'origin3'}
                ]
            }
        }
    
    def test_cloudfront_collector_initialization(self):
        """Test CloudFrontCollector initialization."""
        collector = CloudFrontCollector()
        assert collector.console is not None
    
    def test_format_price_class_all_locations(self):
        """Test price class formatting for all edge locations."""
        result = self.collector.format_price_class('PriceClass_All')
        assert result == 'All Edge Locations'
    
    def test_format_price_class_north_america_europe(self):
        """Test price class formatting for North America and Europe."""
        result = self.collector.format_price_class('PriceClass_200')
        assert result == 'North America and Europe Only'
    
    def test_format_price_class_north_america_only(self):
        """Test price class formatting for North America only."""
        result = self.collector.format_price_class('PriceClass_100')
        assert result == 'North America Only'
    
    def test_format_price_class_unknown(self):
        """Test price class formatting for unknown price class."""
        result = self.collector.format_price_class('PriceClass_Unknown')
        assert result == 'PriceClass_Unknown'
    
    def test_get_primary_origin_single(self):
        """Test getting primary origin with single origin."""
        origins = [{'DomainName': 'example.com', 'Id': 'origin1'}]
        result = self.collector.get_primary_origin(origins)
        assert result == 'example.com'
    
    def test_get_primary_origin_multiple(self):
        """Test getting primary origin with multiple origins."""
        origins = [
            {'DomainName': 'origin1.example.com', 'Id': 'origin1'},
            {'DomainName': 'origin2.example.com', 'Id': 'origin2'},
            {'DomainName': 'origin3.example.com', 'Id': 'origin3'}
        ]
        result = self.collector.get_primary_origin(origins)
        assert result == 'Multiple (3)'
    
    def test_get_primary_origin_empty(self):
        """Test getting primary origin with no origins."""
        origins = []
        result = self.collector.get_primary_origin(origins)
        assert result == 'N/A'
    
    def test_get_distribution_details(self):
        """Test extracting distribution details."""
        result = self.collector.get_distribution_details(self.sample_distribution, 'test-account')
        
        expected = {
            'account': 'test-account',
            'ID': 'E1234567890ABC',
            'Name': 'Test Distribution',
            '원본(Origin)': 'example.com',
            '도메인(Domain)': 'd1234567890abc.cloudfront.net',
            'Class': 'All Edge Locations'
        }
        
        assert result == expected
    
    def test_get_distribution_details_multiple_origins(self):
        """Test extracting distribution details with multiple origins."""
        result = self.collector.get_distribution_details(
            self.sample_distribution_multiple_origins, 
            'test-account'
        )
        
        expected = {
            'account': 'test-account',
            'ID': 'E0987654321XYZ',
            'Name': 'Multi-Origin Distribution',
            '원본(Origin)': 'Multiple (3)',
            '도메인(Domain)': 'd0987654321xyz.cloudfront.net',
            'Class': 'North America and Europe Only'
        }
        
        assert result == expected
    
    def test_get_distribution_details_missing_fields(self):
        """Test extracting distribution details with missing fields."""
        incomplete_distribution = {
            'Id': 'E1111111111AAA'
            # Missing Comment, DomainName, PriceClass, Origins
        }
        
        result = self.collector.get_distribution_details(incomplete_distribution, 'test-account')
        
        expected = {
            'account': 'test-account',
            'ID': 'E1111111111AAA',
            'Name': 'N/A',
            '원본(Origin)': 'N/A',
            '도메인(Domain)': 'N/A',
            'Class': 'All Edge Locations'  # Default price class
        }
        
        assert result == expected
    
    def test_get_distribution_details_empty_comment(self):
        """Test extracting distribution details with empty comment."""
        distribution_empty_comment = self.sample_distribution.copy()
        distribution_empty_comment['Comment'] = ''
        
        result = self.collector.get_distribution_details(distribution_empty_comment, 'test-account')
        
        assert result['Name'] == 'N/A'
    
    @patch('boto3.Session')
    def test_get_account_distributions_success(self, mock_session_class):
        """Test getting CloudFront distributions successfully."""
        # Mock CloudFront client and response
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        mock_cloudfront_client.list_distributions.return_value = {
            'DistributionList': {
                'Items': [self.sample_distribution, self.sample_distribution_multiple_origins]
            }
        }
        
        mock_session.client.return_value = mock_cloudfront_client
        
        result = self.collector._get_account_distributions(mock_session, 'test-account')
        
        assert len(result) == 2
        assert result[0]['ID'] == 'E1234567890ABC'
        assert result[1]['ID'] == 'E0987654321XYZ'
        
        mock_session.client.assert_called_once_with('cloudfront')
        mock_cloudfront_client.list_distributions.assert_called_once()
    
    @patch('boto3.Session')
    def test_get_account_distributions_empty_response(self, mock_session_class):
        """Test getting CloudFront distributions with empty response."""
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        # Empty distribution list
        mock_cloudfront_client.list_distributions.return_value = {
            'DistributionList': {}
        }
        
        mock_session.client.return_value = mock_cloudfront_client
        
        result = self.collector._get_account_distributions(mock_session, 'test-account')
        
        assert result == []
    
    @patch('boto3.Session')
    def test_get_account_distributions_access_denied(self, mock_session_class):
        """Test getting CloudFront distributions with access denied."""
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        # Mock access denied error
        mock_cloudfront_client.list_distributions.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'ListDistributions'
        )
        
        mock_session.client.return_value = mock_cloudfront_client
        
        with patch.object(self.collector.console, 'print') as mock_print:
            result = self.collector._get_account_distributions(mock_session, 'test-account')
        
        assert result == []
        mock_print.assert_called_once()
        assert 'Access denied' in str(mock_print.call_args)
    
    @patch('boto3.Session')
    def test_get_account_distributions_no_credentials(self, mock_session_class):
        """Test getting CloudFront distributions with no credentials."""
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        # Mock no credentials error
        mock_cloudfront_client.list_distributions.side_effect = NoCredentialsError()
        
        mock_session.client.return_value = mock_cloudfront_client
        
        with patch.object(self.collector.console, 'print') as mock_print:
            result = self.collector._get_account_distributions(mock_session, 'test-account')
        
        assert result == []
        mock_print.assert_called_once()
        assert 'No credentials available' in str(mock_print.call_args)
    
    @patch('boto3.Session')
    def test_collect_distributions_success(self, mock_session_class):
        """Test collecting distributions from multiple accounts successfully."""
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        
        mock_cloudfront_client.list_distributions.return_value = {
            'DistributionList': {
                'Items': [self.sample_distribution]
            }
        }
        
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        account_profiles = {
            'account1': 'profile1',
            'account2': 'profile2'
        }
        
        result = self.collector.collect_distributions(account_profiles)
        
        # Should have 2 distributions (one from each account)
        assert len(result) == 2
        assert all(dist['account'] in ['account1', 'account2'] for dist in result)
        
        # Verify sessions were created for both profiles
        assert mock_session_class.call_count == 2
        mock_session_class.assert_any_call(profile_name='profile1')
        mock_session_class.assert_any_call(profile_name='profile2')
    
    @patch('boto3.Session')
    def test_collect_distributions_partial_failure(self, mock_session_class):
        """Test collecting distributions with partial failures."""
        # First session succeeds, second fails
        mock_session_success = Mock()
        mock_cloudfront_client_success = Mock()
        mock_cloudfront_client_success.list_distributions.return_value = {
            'DistributionList': {
                'Items': [self.sample_distribution]
            }
        }
        mock_session_success.client.return_value = mock_cloudfront_client_success
        
        # Second session fails
        mock_session_class.side_effect = [
            mock_session_success,
            Exception("Session creation failed")
        ]
        
        account_profiles = {
            'account1': 'profile1',
            'account2': 'invalid-profile'
        }
        
        with patch.object(self.collector.console, 'print') as mock_print:
            result = self.collector.collect_distributions(account_profiles)
        
        # Should have 1 distribution from successful account
        assert len(result) == 1
        assert result[0]['account'] == 'account1'
        
        # Should have printed error for failed account
        mock_print.assert_called()
        call_args = [str(call) for call in mock_print.call_args_list]
        assert any('Failed to collect CloudFront data for account2' in arg for arg in call_args)


class TestCloudFrontRenderer:
    """Test cases for CloudFrontRenderer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.renderer = CloudFrontRenderer()
        
        # Sample distribution data for rendering
        self.sample_distributions = [
            {
                'account': 'account1',
                'ID': 'E1234567890ABC',
                'Name': 'Test Distribution 1',
                '원본(Origin)': 'example.com',
                '도메인(Domain)': 'd1234567890abc.cloudfront.net',
                'Class': 'All Edge Locations'
            },
            {
                'account': 'account2',
                'ID': 'E0987654321XYZ',
                'Name': 'Test Distribution 2',
                '원본(Origin)': 'Multiple (3)',
                '도메인(Domain)': 'd0987654321xyz.cloudfront.net',
                'Class': 'North America and Europe Only'
            }
        ]
    
    def test_cloudfront_renderer_initialization(self):
        """Test CloudFrontRenderer initialization."""
        renderer = CloudFrontRenderer()
        assert renderer.console is not None
    
    def test_render_distributions_success(self):
        """Test rendering distributions successfully."""
        with patch.object(self.renderer.console, 'print') as mock_print:
            self.renderer.render_distributions(self.sample_distributions)
        
        # Should print table and summary
        assert mock_print.call_count >= 2
        
        # Check that table was created and printed
        table_calls = [call for call in mock_print.call_args_list if 'Table' in str(call)]
        assert len(table_calls) > 0
        
        # Check that summary was printed
        summary_calls = [call for call in mock_print.call_args_list if 'Total distributions: 2' in str(call)]
        assert len(summary_calls) > 0
    
    def test_render_distributions_empty(self):
        """Test rendering empty distributions list."""
        with patch.object(self.renderer.console, 'print') as mock_print:
            self.renderer.render_distributions([])
        
        # Should print "no distributions found" message
        mock_print.assert_called_once()
        assert 'No CloudFront distributions found' in str(mock_print.call_args)
    
    def test_render_distributions_single(self):
        """Test rendering single distribution."""
        single_distribution = [self.sample_distributions[0]]
        
        with patch.object(self.renderer.console, 'print') as mock_print:
            self.renderer.render_distributions(single_distribution)
        
        # Should print table and summary with count 1
        assert mock_print.call_count >= 2
        
        # Check that summary shows correct count
        summary_calls = [call for call in mock_print.call_args_list if 'Total distributions: 1' in str(call)]
        assert len(summary_calls) > 0


if __name__ == '__main__':
    pytest.main([__file__])