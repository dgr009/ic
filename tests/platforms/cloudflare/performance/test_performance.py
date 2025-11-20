#!/usr/bin/env python3
"""
CloudFlare Performance Tests

Performance benchmarks for CloudFlare API client operations.
Tests response times and memory usage with large datasets.

Benchmarks:
- Account retrieval: < 2s for 10 accounts
- Zone retrieval: < 5s for 100 zones
- DNS records: < 3s for 1000 records
- Analytics retrieval: < 10s for 10 zones
- WAF rules: < 5s for 100 rules
- Page rules: < 3s for 50 rules
"""

import pytest
import responses
import time
import tracemalloc
from datetime import datetime, timedelta
from typing import List, Dict, Any

try:
    from src.ic.platforms.cloudflare.client import (
        CloudFlareClient,
        CloudFlareConfig
    )
except ImportError:
    from ic.platforms.cloudflare.client import (
        CloudFlareClient,
        CloudFlareConfig
    )


class TestPerformanceBenchmarks:
    """Performance benchmark tests for CloudFlare client operations."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return CloudFlareConfig(
            email='test@example.com',
            api_token='test_token_123',
            accounts=[],
            zones=[]
        )
    
    @pytest.fixture
    def client(self, config):
        """Create a test client."""
        return CloudFlareClient(config)
    
    def _generate_accounts(self, count: int) -> List[Dict[str, Any]]:
        """Generate mock account data."""
        return [
            {
                'id': f'acc{i}',
                'name': f'Account {i}',
                'type': 'enterprise' if i % 2 == 0 else 'free',
                'settings': {'enforce_twofactor': i % 2 == 0}
            }
            for i in range(1, count + 1)
        ]
    
    def _generate_zones(self, count: int, account_id: str) -> List[Dict[str, Any]]:
        """Generate mock zone data."""
        return [
            {
                'id': f'zone{i}',
                'name': f'zone{i}.example.com',
                'status': 'active',
                'plan': {'name': 'Enterprise' if i % 3 == 0 else 'Free'},
                'name_servers': [f'ns{i}.cloudflare.com']
            }
            for i in range(1, count + 1)
        ]
    
    def _generate_dns_records(self, count: int) -> List[Dict[str, Any]]:
        """Generate mock DNS record data."""
        record_types = ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS']
        return [
            {
                'id': f'rec{i}',
                'type': record_types[i % len(record_types)],
                'name': f'record{i}.example.com',
                'content': f'192.0.2.{i % 256}' if i % 2 == 0 else f'target{i}.example.com',
                'ttl': 3600,
                'proxied': i % 2 == 0
            }
            for i in range(1, count + 1)
        ]
    
    def _generate_firewall_rules(self, count: int) -> List[Dict[str, Any]]:
        """Generate mock firewall rule data."""
        actions = ['block', 'challenge', 'allow', 'log']
        return [
            {
                'id': f'rule{i}',
                'action': actions[i % len(actions)],
                'description': f'Firewall rule {i}',
                'priority': i,
                'paused': i % 5 == 0,
                'filter': {
                    'expression': f'(http.request.uri.path contains "/path{i}")'
                }
            }
            for i in range(1, count + 1)
        ]
    
    def _generate_page_rules(self, count: int) -> List[Dict[str, Any]]:
        """Generate mock page rule data."""
        return [
            {
                'id': f'pr{i}',
                'status': 'active' if i % 4 != 0 else 'disabled',
                'priority': i,
                'targets': [
                    {
                        'target': 'url',
                        'constraint': {
                            'operator': 'matches',
                            'value': f'*example.com/path{i}/*'
                        }
                    }
                ],
                'actions': [
                    {'id': 'cache_level', 'value': 'cache_everything'},
                    {'id': 'edge_cache_ttl', 'value': 86400}
                ]
            }
            for i in range(1, count + 1)
        ]
    
    @responses.activate
    def test_account_retrieval_performance(self, client):
        """
        Benchmark: Account retrieval should complete in < 2s for 10 accounts.
        """
        # Generate 10 accounts
        accounts = self._generate_accounts(10)
        
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': accounts,
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Measure performance
        start_time = time.time()
        result = client.get_accounts()
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(result) == 10
        assert elapsed_time < 2.0, f"Account retrieval took {elapsed_time:.2f}s (expected < 2s)"
        
        print(f"\n✓ Account retrieval: {elapsed_time:.3f}s for 10 accounts (target: < 2s)")
    
    @responses.activate
    def test_zone_retrieval_performance(self, client):
        """
        Benchmark: Zone retrieval should complete in < 5s for 100 zones.
        """
        # Generate 100 zones across 2 pages
        zones_page1 = self._generate_zones(50, 'acc1')
        zones_page2 = self._generate_zones(50, 'acc1')
        
        # Mock first page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': zones_page1,
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 2}
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': zones_page2,
                'result_info': {'page': 2, 'per_page': 50, 'total_pages': 2}
            },
            status=200
        )
        
        # Measure performance
        start_time = time.time()
        result = client.get_zones('acc1')
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(result) == 100
        assert elapsed_time < 5.0, f"Zone retrieval took {elapsed_time:.2f}s (expected < 5s)"
        
        print(f"✓ Zone retrieval: {elapsed_time:.3f}s for 100 zones (target: < 5s)")
    
    @responses.activate
    def test_dns_records_performance(self, client):
        """
        Benchmark: DNS records retrieval should complete in < 3s for 1000 records.
        """
        # Generate 1000 DNS records across 20 pages (50 per page)
        per_page = 50
        total_records = 1000
        total_pages = total_records // per_page
        
        for page in range(1, total_pages + 1):
            start_idx = (page - 1) * per_page + 1
            records = self._generate_dns_records(per_page)
            
            responses.add(
                responses.GET,
                'https://api.cloudflare.com/client/v4/zones/zone1/dns_records',
                json={
                    'success': True,
                    'result': records,
                    'result_info': {'page': page, 'per_page': per_page, 'total_pages': total_pages}
                },
                status=200
            )
        
        # Measure performance
        start_time = time.time()
        result = client.get_dns_records('zone1')
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(result) == 1000
        assert elapsed_time < 3.0, f"DNS records retrieval took {elapsed_time:.2f}s (expected < 3s)"
        
        print(f"✓ DNS records retrieval: {elapsed_time:.3f}s for 1000 records (target: < 3s)")
    
    @responses.activate
    def test_analytics_retrieval_performance(self, client):
        """
        Benchmark: Analytics retrieval should complete in < 10s for 10 zones.
        """
        # Mock zone details for 10 zones
        for i in range(1, 11):
            responses.add(
                responses.GET,
                f'https://api.cloudflare.com/client/v4/zones/zone{i}',
                json={
                    'success': True,
                    'result': {
                        'id': f'zone{i}',
                        'name': f'zone{i}.example.com',
                        'plan': {'name': 'Free'}
                    }
                },
                status=200
            )
            
            # Mock analytics data
            responses.add(
                responses.GET,
                f'https://api.cloudflare.com/client/v4/zones/zone{i}/analytics/dashboard',
                json={
                    'success': True,
                    'result': {
                        'totals': {
                            'requests': {'all': 50000 * i, 'cached': 30000 * i},
                            'bandwidth': {'all': 250000000 * i},
                            'threats': {'all': 100 * i},
                            'pageviews': {'all': 5000 * i}
                        }
                    }
                },
                status=200
            )
        
        # Measure performance
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        start_time = time.time()
        results = []
        for i in range(1, 11):
            result = client.get_analytics(f'zone{i}', since, until)
            results.append(result)
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(results) == 10
        assert all(r['requests'] > 0 for r in results)
        assert elapsed_time < 10.0, f"Analytics retrieval took {elapsed_time:.2f}s (expected < 10s)"
        
        print(f"✓ Analytics retrieval: {elapsed_time:.3f}s for 10 zones (target: < 10s)")
    
    @responses.activate
    def test_waf_rules_performance(self, client):
        """
        Benchmark: WAF rules retrieval should complete in < 5s for 100 rules.
        """
        # Generate 100 firewall rules across 2 pages
        rules_page1 = self._generate_firewall_rules(50)
        rules_page2 = self._generate_firewall_rules(50)
        
        # Mock first page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/firewall/rules',
            json={
                'success': True,
                'result': rules_page1,
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 2}
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/firewall/rules',
            json={
                'success': True,
                'result': rules_page2,
                'result_info': {'page': 2, 'per_page': 50, 'total_pages': 2}
            },
            status=200
        )
        
        # Measure performance
        start_time = time.time()
        result = client.get_firewall_rules('zone1')
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(result) == 100
        assert elapsed_time < 5.0, f"WAF rules retrieval took {elapsed_time:.2f}s (expected < 5s)"
        
        print(f"✓ WAF rules retrieval: {elapsed_time:.3f}s for 100 rules (target: < 5s)")
    
    @responses.activate
    def test_page_rules_performance(self, client):
        """
        Benchmark: Page rules retrieval should complete in < 3s for 50 rules.
        """
        # Generate 50 page rules
        rules = self._generate_page_rules(50)
        
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/pagerules',
            json={
                'success': True,
                'result': rules,
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Measure performance
        start_time = time.time()
        result = client.get_page_rules('zone1')
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(result) == 50
        assert elapsed_time < 3.0, f"Page rules retrieval took {elapsed_time:.2f}s (expected < 3s)"
        
        print(f"✓ Page rules retrieval: {elapsed_time:.3f}s for 50 rules (target: < 3s)")


class TestMemoryUsage:
    """Memory usage tests with large datasets."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return CloudFlareConfig(
            email='test@example.com',
            api_token='test_token_123',
            accounts=[],
            zones=[]
        )
    
    @pytest.fixture
    def client(self, config):
        """Create a test client."""
        return CloudFlareClient(config)
    
    def _generate_large_dns_records(self, count: int) -> List[Dict[str, Any]]:
        """Generate large DNS record dataset."""
        record_types = ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA']
        return [
            {
                'id': f'rec{i}',
                'type': record_types[i % len(record_types)],
                'name': f'subdomain{i}.example.com',
                'content': f'192.0.2.{i % 256}' if i % 2 == 0 else f'target{i}.example.com',
                'ttl': 3600,
                'proxied': i % 2 == 0,
                'meta': {
                    'auto_added': False,
                    'managed_by_apps': False,
                    'managed_by_argo_tunnel': False
                },
                'comment': f'DNS record {i} for testing',
                'tags': [f'tag{i % 10}', f'category{i % 5}']
            }
            for i in range(1, count + 1)
        ]
    
    @responses.activate
    def test_memory_usage_large_dns_dataset(self, client):
        """
        Test memory usage with large DNS records dataset (5000 records).
        """
        # Generate 5000 DNS records across 100 pages
        per_page = 50
        total_records = 5000
        total_pages = total_records // per_page
        
        # Start memory tracking
        tracemalloc.start()
        
        # Mock API responses
        for page in range(1, total_pages + 1):
            records = self._generate_large_dns_records(per_page)
            
            responses.add(
                responses.GET,
                'https://api.cloudflare.com/client/v4/zones/zone1/dns_records',
                json={
                    'success': True,
                    'result': records,
                    'result_info': {'page': page, 'per_page': per_page, 'total_pages': total_pages}
                },
                status=200
            )
        
        # Get baseline memory
        baseline = tracemalloc.get_traced_memory()[0]
        
        # Retrieve DNS records
        result = client.get_dns_records('zone1')
        
        # Get peak memory
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Calculate memory usage
        memory_used_mb = (peak - baseline) / 1024 / 1024
        
        # Verify results
        assert len(result) == 5000
        
        # Memory usage should be reasonable (< 50 MB for 5000 records)
        assert memory_used_mb < 50, f"Memory usage {memory_used_mb:.2f} MB exceeds 50 MB limit"
        
        print(f"\n✓ Memory usage for 5000 DNS records: {memory_used_mb:.2f} MB (limit: < 50 MB)")
    
    @responses.activate
    def test_memory_usage_multiple_zones(self, client):
        """
        Test memory usage when processing multiple zones (50 zones with 100 records each).
        """
        # Start memory tracking
        tracemalloc.start()
        
        # Mock 50 zones
        for zone_idx in range(1, 51):
            # Mock 100 DNS records per zone (2 pages)
            for page in range(1, 3):
                records = self._generate_large_dns_records(50)
                
                responses.add(
                    responses.GET,
                    f'https://api.cloudflare.com/client/v4/zones/zone{zone_idx}/dns_records',
                    json={
                        'success': True,
                        'result': records,
                        'result_info': {'page': page, 'per_page': 50, 'total_pages': 2}
                    },
                    status=200
                )
        
        # Get baseline memory
        baseline = tracemalloc.get_traced_memory()[0]
        
        # Retrieve DNS records for all zones
        all_records = []
        for zone_idx in range(1, 51):
            records = client.get_dns_records(f'zone{zone_idx}')
            all_records.extend(records)
        
        # Get peak memory
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Calculate memory usage
        memory_used_mb = (peak - baseline) / 1024 / 1024
        
        # Verify results
        assert len(all_records) == 5000  # 50 zones * 100 records
        
        # Memory usage should be reasonable (< 100 MB for 5000 records across 50 zones)
        assert memory_used_mb < 100, f"Memory usage {memory_used_mb:.2f} MB exceeds 100 MB limit"
        
        print(f"✓ Memory usage for 50 zones (5000 total records): {memory_used_mb:.2f} MB (limit: < 100 MB)")
    
    @responses.activate
    def test_memory_usage_analytics_multiple_zones(self, client):
        """
        Test memory usage when retrieving analytics for multiple zones (20 zones).
        """
        # Start memory tracking
        tracemalloc.start()
        
        # Mock zone details and analytics for 20 zones
        for i in range(1, 21):
            responses.add(
                responses.GET,
                f'https://api.cloudflare.com/client/v4/zones/zone{i}',
                json={
                    'success': True,
                    'result': {
                        'id': f'zone{i}',
                        'name': f'zone{i}.example.com',
                        'plan': {'name': 'Free'}
                    }
                },
                status=200
            )
            
            responses.add(
                responses.GET,
                f'https://api.cloudflare.com/client/v4/zones/zone{i}/analytics/dashboard',
                json={
                    'success': True,
                    'result': {
                        'totals': {
                            'requests': {'all': 100000 * i, 'cached': 60000 * i},
                            'bandwidth': {'all': 500000000 * i},
                            'threats': {'all': 500 * i},
                            'pageviews': {'all': 10000 * i}
                        }
                    }
                },
                status=200
            )
        
        # Get baseline memory
        baseline = tracemalloc.get_traced_memory()[0]
        
        # Retrieve analytics for all zones
        since = datetime.now() - timedelta(hours=24)
        until = datetime.now()
        
        analytics_results = []
        for i in range(1, 21):
            result = client.get_analytics(f'zone{i}', since, until)
            analytics_results.append(result)
        
        # Get peak memory
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Calculate memory usage
        memory_used_mb = (peak - baseline) / 1024 / 1024
        
        # Verify results
        assert len(analytics_results) == 20
        
        # Memory usage should be reasonable (< 20 MB for 20 zones analytics)
        assert memory_used_mb < 20, f"Memory usage {memory_used_mb:.2f} MB exceeds 20 MB limit"
        
        print(f"✓ Memory usage for 20 zones analytics: {memory_used_mb:.2f} MB (limit: < 20 MB)")


class TestConcurrentOperations:
    """Test performance with concurrent-like operations."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return CloudFlareConfig(
            email='test@example.com',
            api_token='test_token_123',
            accounts=[],
            zones=[]
        )
    
    @pytest.fixture
    def client(self, config):
        """Create a test client."""
        return CloudFlareClient(config)
    
    @responses.activate
    def test_sequential_multi_zone_operations(self, client):
        """
        Test performance of sequential operations across multiple zones.
        Simulates real-world usage pattern: get zones, then get DNS records for each.
        """
        # Mock 10 zones
        zones = [
            {'id': f'zone{i}', 'name': f'zone{i}.example.com', 'status': 'active'}
            for i in range(1, 11)
        ]
        
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': zones,
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock DNS records for each zone (100 records per zone)
        for i in range(1, 11):
            records = [
                {
                    'id': f'rec{j}',
                    'type': 'A',
                    'name': f'record{j}.zone{i}.example.com',
                    'content': f'192.0.2.{j % 256}'
                }
                for j in range(1, 101)
            ]
            
            responses.add(
                responses.GET,
                f'https://api.cloudflare.com/client/v4/zones/zone{i}/dns_records',
                json={
                    'success': True,
                    'result': records,
                    'result_info': {'page': 1, 'per_page': 100, 'total_pages': 1}
                },
                status=200
            )
        
        # Measure performance
        start_time = time.time()
        
        # Get zones
        zones_result = client.get_zones('acc1')
        
        # Get DNS records for each zone
        all_records = []
        for zone in zones_result:
            records = client.get_dns_records(zone['id'])
            all_records.extend(records)
        
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(zones_result) == 10
        assert len(all_records) == 1000  # 10 zones * 100 records
        
        # Should complete in reasonable time (< 15s for 10 zones + 1000 records)
        assert elapsed_time < 15.0, f"Sequential operations took {elapsed_time:.2f}s (expected < 15s)"
        
        print(f"\n✓ Sequential multi-zone operations: {elapsed_time:.3f}s for 10 zones + 1000 records (target: < 15s)")


class TestPaginationPerformance:
    """Test pagination performance with various page sizes."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return CloudFlareConfig(
            email='test@example.com',
            api_token='test_token_123',
            accounts=[],
            zones=[]
        )
    
    @pytest.fixture
    def client(self, config):
        """Create a test client."""
        return CloudFlareClient(config)
    
    @responses.activate
    def test_pagination_many_small_pages(self, client):
        """
        Test performance with many small pages (100 pages of 10 records each).
        """
        # Mock 100 pages of 10 records each
        for page in range(1, 101):
            records = [
                {
                    'id': f'rec{(page-1)*10 + i}',
                    'type': 'A',
                    'name': f'record{(page-1)*10 + i}.example.com',
                    'content': f'192.0.2.{i}'
                }
                for i in range(1, 11)
            ]
            
            responses.add(
                responses.GET,
                'https://api.cloudflare.com/client/v4/zones/zone1/dns_records',
                json={
                    'success': True,
                    'result': records,
                    'result_info': {'page': page, 'per_page': 10, 'total_pages': 100}
                },
                status=200
            )
        
        # Measure performance
        start_time = time.time()
        result = client.get_dns_records('zone1')
        elapsed_time = time.time() - start_time
        
        # Verify results
        assert len(result) == 1000
        
        # Should handle many pages efficiently (< 5s for 100 pages)
        assert elapsed_time < 5.0, f"Pagination took {elapsed_time:.2f}s (expected < 5s)"
        
        print(f"\n✓ Pagination (100 pages): {elapsed_time:.3f}s for 1000 records (target: < 5s)")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
