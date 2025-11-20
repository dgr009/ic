#!/usr/bin/env python3
"""
Unit tests for CloudFlare analytics API methods.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from src.ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig


@pytest.fixture
def mock_config():
    """Create a mock CloudFlare configuration."""
    return CloudFlareConfig(
        email="test@example.com",
        api_token="test_token_123",
        accounts=[],
        zones=[]
    )


@pytest.fixture
def client(mock_config):
    """Create a CloudFlare client with mock config."""
    return CloudFlareClient(mock_config)


class TestGetAnalytics:
    """Test get_analytics method."""
    
    def test_get_analytics_enterprise_zone(self, client):
        """Test analytics retrieval for Enterprise zone using GraphQL."""
        zone_id = "test_zone_123"
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        # Mock zone details response (Enterprise plan)
        zone_response = {
            "success": True,
            "result": {
                "id": zone_id,
                "name": "example.com",
                "plan": {
                    "name": "Enterprise Website"
                }
            }
        }
        
        # Mock GraphQL response
        graphql_response = {
            "data": {
                "viewer": {
                    "zones": [{
                        "httpRequests1dGroups": [{
                            "sum": {
                                "requests": 1000000,
                                "bytes": 5000000000,
                                "threats": 1234,
                                "cachedRequests": 800000,
                                "pageViews": 500000
                            },
                            "uniq": {
                                "uniques": 45678
                            }
                        }]
                    }]
                }
            }
        }
        
        with patch.object(client, '_make_request', return_value=zone_response):
            with patch('requests.post') as mock_post:
                mock_post.return_value = Mock(
                    ok=True,
                    json=lambda: graphql_response
                )
                
                result = client.get_analytics(zone_id, since, until)
        
        # Verify result structure
        assert result["zone_id"] == zone_id
        assert result["license_type"] == "Enterprise"
        assert result["requests"] == 1000000
        assert result["bandwidth"] == 5000000000
        assert result["unique_visitors"] == 45678
        assert result["cache_hit_ratio"] == 0.8
        assert result["threats_blocked"] == 1234
        assert result["peak_requests_per_hour"] is not None
    
    def test_get_analytics_free_zone(self, client):
        """Test analytics retrieval for Free zone using REST API."""
        zone_id = "test_zone_456"
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        # Mock zone details response (Free plan)
        zone_response = {
            "success": True,
            "result": {
                "id": zone_id,
                "name": "test.com",
                "plan": {
                    "name": "Free Website"
                }
            }
        }
        
        # Mock REST analytics response
        analytics_response = {
            "success": True,
            "result": {
                "totals": {
                    "requests": {
                        "all": 10000,
                        "cached": 7000
                    },
                    "bandwidth": {
                        "all": 50000000
                    },
                    "threats": {
                        "all": 0
                    },
                    "pageviews": {
                        "all": 5000
                    }
                }
            }
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = [zone_response, analytics_response]
            
            result = client.get_analytics(zone_id, since, until)
        
        # Verify result structure
        assert result["zone_id"] == zone_id
        assert result["license_type"] == "Free"
        assert result["requests"] == 10000
        assert result["bandwidth"] == 50000000
        assert result["unique_visitors"] is None  # Not available for Free zones
        assert result["cache_hit_ratio"] == 0.7
        assert result["threats_blocked"] is None  # 0 threats
        assert result["peak_requests_per_hour"] is not None
    
    def test_get_analytics_handles_missing_metrics(self, client):
        """Test that missing metrics are handled gracefully with None values."""
        zone_id = "test_zone_789"
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        # Mock zone details response
        zone_response = {
            "success": True,
            "result": {
                "id": zone_id,
                "name": "minimal.com",
                "plan": {
                    "name": "Free Website"
                }
            }
        }
        
        # Mock REST analytics response with minimal data
        analytics_response = {
            "success": True,
            "result": {
                "totals": {
                    "requests": {
                        "all": 100
                    },
                    "bandwidth": {
                        "all": 1000
                    }
                }
            }
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = [zone_response, analytics_response]
            
            result = client.get_analytics(zone_id, since, until)
        
        # Verify missing metrics are None
        assert result["zone_id"] == zone_id
        assert result["requests"] == 100
        assert result["bandwidth"] == 1000
        assert result["unique_visitors"] is None
        assert result["cache_hit_ratio"] is None
        assert result["threats_blocked"] is None
    
    def test_get_analytics_graphql_fallback_to_rest(self, client):
        """Test that GraphQL failure falls back to REST API."""
        zone_id = "test_zone_fallback"
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        # Mock zone details response (Enterprise plan)
        zone_response = {
            "success": True,
            "result": {
                "id": zone_id,
                "name": "fallback.com",
                "plan": {
                    "name": "Enterprise Website"
                }
            }
        }
        
        # Mock REST analytics response (fallback)
        analytics_response = {
            "success": True,
            "result": {
                "totals": {
                    "requests": {
                        "all": 5000
                    },
                    "bandwidth": {
                        "all": 25000000
                    }
                }
            }
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = [zone_response, analytics_response]
            
            with patch('requests.post') as mock_post:
                # Simulate GraphQL failure
                mock_post.return_value = Mock(ok=False, status_code=500)
                
                result = client.get_analytics(zone_id, since, until)
        
        # Verify fallback worked
        assert result["zone_id"] == zone_id
        assert result["license_type"] == "Enterprise"
        assert result["requests"] == 5000
        assert result["bandwidth"] == 25000000
    
    def test_get_analytics_empty_data(self, client):
        """Test handling of empty analytics data."""
        zone_id = "test_zone_empty"
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        # Mock zone details response
        zone_response = {
            "success": True,
            "result": {
                "id": zone_id,
                "name": "empty.com",
                "plan": {
                    "name": "Free Website"
                }
            }
        }
        
        # Mock empty analytics response
        analytics_response = {
            "success": True,
            "result": {
                "totals": {}
            }
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = [zone_response, analytics_response]
            
            result = client.get_analytics(zone_id, since, until)
        
        # Verify empty data handling
        assert result["zone_id"] == zone_id
        assert result["requests"] == 0
        assert result["bandwidth"] == 0
        assert result["unique_visitors"] is None
        assert result["cache_hit_ratio"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
