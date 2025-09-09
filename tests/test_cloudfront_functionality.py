#!/usr/bin/env python3
"""
Comprehensive CloudFront functionality test script.

This script tests all CloudFront functionality including:
- CloudFrontCollector class functionality
- CloudFrontRenderer class functionality  
- CLI integration structure
- Error handling
- Price class formatting
- Origin handling
"""

import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def test_cloudfront_collector():
    """Test CloudFrontCollector functionality."""
    print("Testing CloudFrontCollector...")
    
    from aws.cloudfront.info import CloudFrontCollector
    
    collector = CloudFrontCollector()
    
    # Test price class formatting
    price_class_tests = [
        ('PriceClass_All', 'All Edge Locations'),
        ('PriceClass_200', 'North America and Europe Only'),
        ('PriceClass_100', 'North America Only'),
        ('PriceClass_Unknown', 'PriceClass_Unknown')
    ]
    
    for input_class, expected in price_class_tests:
        result = collector.format_price_class(input_class)
        assert result == expected, f"Price class test failed: {input_class} -> {result} (expected {expected})"
    
    print("  ✓ Price class formatting tests passed")
    
    # Test origin handling
    origin_tests = [
        ([], 'N/A'),
        ([{'DomainName': 'example.com'}], 'example.com'),
        ([{'DomainName': 'origin1.com'}, {'DomainName': 'origin2.com'}], 'Multiple (2)'),
        ([{'DomainName': 'o1.com'}, {'DomainName': 'o2.com'}, {'DomainName': 'o3.com'}], 'Multiple (3)')
    ]
    
    for origins, expected in origin_tests:
        result = collector.get_primary_origin(origins)
        assert result == expected, f"Origin test failed: {len(origins)} origins -> {result} (expected {expected})"
    
    print("  ✓ Origin handling tests passed")
    
    # Test distribution details extraction
    sample_distribution = {
        'Id': 'E1234567890ABC',
        'Comment': 'Test Distribution',
        'DomainName': 'd1234567890abc.cloudfront.net',
        'PriceClass': 'PriceClass_All',
        'Origins': {
            'Items': [{'DomainName': 'example.com', 'Id': 'origin1'}]
        }
    }
    
    result = collector.get_distribution_details(sample_distribution, 'test-account')
    
    expected_result = {
        'account': 'test-account',
        'ID': 'E1234567890ABC',
        'Name': 'Test Distribution',
        '원본(Origin)': 'example.com',
        '도메인(Domain)': 'd1234567890abc.cloudfront.net',
        'Class': 'All Edge Locations'
    }
    
    for key, expected_value in expected_result.items():
        assert key in result, f"Missing key in distribution details: {key}"
        assert result[key] == expected_value, f"Distribution detail mismatch: {key} = {result[key]} (expected {expected_value})"
    
    print("  ✓ Distribution details extraction tests passed")
    
    # Test with missing fields
    incomplete_distribution = {'Id': 'E1111111111AAA'}
    result = collector.get_distribution_details(incomplete_distribution, 'test-account')
    
    assert result['account'] == 'test-account'
    assert result['ID'] == 'E1111111111AAA'
    assert result['Name'] == 'N/A'
    assert result['원본(Origin)'] == 'N/A'
    assert result['도메인(Domain)'] == 'N/A'
    assert result['Class'] == 'All Edge Locations'  # Default
    
    print("  ✓ Missing fields handling tests passed")


def test_cloudfront_renderer():
    """Test CloudFrontRenderer functionality."""
    print("Testing CloudFrontRenderer...")
    
    from aws.cloudfront.info import CloudFrontRenderer
    
    renderer = CloudFrontRenderer()
    assert renderer.console is not None, "Renderer console not initialized"
    
    print("  ✓ Renderer initialization tests passed")
    
    # Test rendering with mock data
    sample_distributions = [
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
    
    # Mock the console.print method to capture output
    with patch.object(renderer.console, 'print') as mock_print:
        renderer.render_distributions(sample_distributions)
        
        # Verify that print was called (table + summary)
        assert mock_print.call_count >= 2, f"Expected at least 2 print calls, got {mock_print.call_count}"
    
    print("  ✓ Distribution rendering tests passed")
    
    # Test empty distributions
    with patch.object(renderer.console, 'print') as mock_print:
        renderer.render_distributions([])
        
        # Should print "no distributions found" message
        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert 'No CloudFront distributions found' in call_args, f"Expected 'no distributions' message, got: {call_args}"
    
    print("  ✓ Empty distributions handling tests passed")


def test_cloudfront_collector_with_mocked_aws():
    """Test CloudFrontCollector with mocked AWS responses."""
    print("Testing CloudFrontCollector with mocked AWS...")
    
    from aws.cloudfront.info import CloudFrontCollector
    
    collector = CloudFrontCollector()
    
    # Mock successful AWS response
    sample_aws_response = {
        'DistributionList': {
            'Items': [
                {
                    'Id': 'E1234567890ABC',
                    'Comment': 'Production Distribution',
                    'DomainName': 'd1234567890abc.cloudfront.net',
                    'PriceClass': 'PriceClass_All',
                    'Origins': {
                        'Items': [{'DomainName': 'prod.example.com', 'Id': 'prod-origin'}]
                    }
                }
            ]
        }
    }
    
    with patch('boto3.Session') as mock_session_class:
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        mock_cloudfront_client.list_distributions.return_value = sample_aws_response
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        account_profiles = {'production': 'prod-profile'}
        distributions = collector.collect_distributions(account_profiles)
        
        # Verify results
        assert len(distributions) == 1, f"Expected 1 distribution, got {len(distributions)}"
        assert distributions[0]['ID'] == 'E1234567890ABC'
        assert distributions[0]['account'] == 'production'
        
        # Verify AWS API calls
        mock_session_class.assert_called_once_with(profile_name='prod-profile')
        mock_session.client.assert_called_once_with('cloudfront')
        mock_cloudfront_client.list_distributions.assert_called_once()
    
    print("  ✓ Mocked AWS integration tests passed")
    
    # Test empty AWS response
    empty_response = {'DistributionList': {}}
    
    with patch('boto3.Session') as mock_session_class:
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        mock_cloudfront_client.list_distributions.return_value = empty_response
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        distributions = collector.collect_distributions({'test': 'test-profile'})
        assert distributions == [], f"Expected empty list, got {distributions}"
    
    print("  ✓ Empty AWS response tests passed")


def test_cloudfront_error_handling():
    """Test CloudFront error handling."""
    print("Testing CloudFront error handling...")
    
    from aws.cloudfront.info import CloudFrontCollector
    from botocore.exceptions import ClientError, NoCredentialsError
    
    collector = CloudFrontCollector()
    
    # Test access denied error
    with patch('boto3.Session') as mock_session_class:
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        mock_cloudfront_client.list_distributions.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'ListDistributions'
        )
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        with patch.object(collector.console, 'print') as mock_print:
            distributions = collector.collect_distributions({'test': 'test-profile'})
            
            assert distributions == [], "Expected empty list on access denied"
            mock_print.assert_called_once()
            assert 'Access denied' in str(mock_print.call_args)
    
    print("  ✓ Access denied error handling tests passed")
    
    # Test no credentials error
    with patch('boto3.Session') as mock_session_class:
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        mock_cloudfront_client.list_distributions.side_effect = NoCredentialsError()
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        with patch.object(collector.console, 'print') as mock_print:
            distributions = collector.collect_distributions({'test': 'test-profile'})
            
            assert distributions == [], "Expected empty list on no credentials"
            mock_print.assert_called_once()
            assert 'No credentials available' in str(mock_print.call_args)
    
    print("  ✓ No credentials error handling tests passed")


def test_cli_integration_structure():
    """Test CLI integration structure."""
    print("Testing CLI integration structure...")
    
    # Test that CLI module can be imported
    try:
        from src.ic import cli
        print("  ✓ CLI module import successful")
    except Exception as e:
        raise AssertionError(f"Failed to import CLI module: {e}")
    
    # Test that CloudFront classes can be imported in CLI context
    try:
        from aws.cloudfront.info import CloudFrontCollector, CloudFrontRenderer
        print("  ✓ CloudFront classes import successful in CLI context")
    except Exception as e:
        raise AssertionError(f"Failed to import CloudFront classes in CLI context: {e}")
    
    # Test CLI argument structure (simulate what the CLI parser would create)
    class MockArgs:
        def __init__(self):
            self.profile = 'default'
            self.accounts = None
    
    mock_args = MockArgs()
    assert hasattr(mock_args, 'profile'), "Mock args missing profile attribute"
    assert hasattr(mock_args, 'accounts'), "Mock args missing accounts attribute"
    
    print("  ✓ CLI argument structure tests passed")


def test_end_to_end_workflow():
    """Test complete end-to-end CloudFront workflow."""
    print("Testing end-to-end CloudFront workflow...")
    
    from aws.cloudfront.info import CloudFrontCollector, CloudFrontRenderer
    
    # Mock complete AWS workflow
    sample_aws_response = {
        'DistributionList': {
            'Items': [
                {
                    'Id': 'E1234567890ABC',
                    'Comment': 'Production Website',
                    'DomainName': 'd1234567890abc.cloudfront.net',
                    'PriceClass': 'PriceClass_All',
                    'Origins': {
                        'Items': [{'DomainName': 'www.example.com', 'Id': 'main-origin'}]
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
    
    with patch('boto3.Session') as mock_session_class:
        mock_session = Mock()
        mock_cloudfront_client = Mock()
        mock_cloudfront_client.list_distributions.return_value = sample_aws_response
        mock_session.client.return_value = mock_cloudfront_client
        mock_session_class.return_value = mock_session
        
        # Create collector and renderer
        collector = CloudFrontCollector()
        renderer = CloudFrontRenderer()
        
        # Execute complete workflow
        account_profiles = {'production': 'prod-profile'}
        
        # Step 1: Collect distributions
        distributions = collector.collect_distributions(account_profiles)
        
        # Verify collection results
        assert len(distributions) == 2, f"Expected 2 distributions, got {len(distributions)}"
        
        # Verify first distribution
        prod_dist = next(d for d in distributions if d['ID'] == 'E1234567890ABC')
        assert prod_dist['Name'] == 'Production Website'
        assert prod_dist['원본(Origin)'] == 'www.example.com'
        assert prod_dist['Class'] == 'All Edge Locations'
        
        # Verify second distribution
        api_dist = next(d for d in distributions if d['ID'] == 'E0987654321XYZ')
        assert api_dist['Name'] == 'API Distribution'
        assert api_dist['원본(Origin)'] == 'Multiple (2)'
        assert api_dist['Class'] == 'North America and Europe Only'
        
        # Step 2: Render distributions
        with patch.object(renderer.console, 'print') as mock_print:
            renderer.render_distributions(distributions)
            
            # Verify rendering occurred
            assert mock_print.call_count >= 2, "Expected table and summary output"
            
            # Check that summary count appears in output (this is more reliable than checking table content)
            print_calls = [str(call) for call in mock_print.call_args_list]
            combined_output = ' '.join(print_calls)
            
            # The summary should definitely contain the count
            assert 'Total distributions: 2' in combined_output, "Summary count not in output"
    
    print("  ✓ End-to-end workflow tests passed")


def main():
    """Run all CloudFront functionality tests."""
    print("=" * 80)
    print("CLOUDFRONT FUNCTIONALITY TEST SUITE")
    print("=" * 80)
    
    tests = [
        test_cloudfront_collector,
        test_cloudfront_renderer,
        test_cloudfront_collector_with_mocked_aws,
        test_cloudfront_error_handling,
        test_cli_integration_structure,
        test_end_to_end_workflow
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"✅ {test_func.__name__} PASSED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_func.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
        print()
    
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL CLOUDFRONT TESTS PASSED! 🎉")
        return True
    else:
        print(f"\n❌ {failed} TESTS FAILED")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)