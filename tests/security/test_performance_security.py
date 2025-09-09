"""
Performance tests for session caching and parallel execution with security considerations.

Tests performance of security-aware components under load.
"""

import time
import threading
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch

from ic.config.security import SecurityManager
from ic.core.session import AWSSessionManager
from ic.core.logging import ICLogger
from ic.core.mcp_manager import MCPManager


class TestPerformanceSecurity:
    """Performance tests with security considerations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
    
    def test_session_caching_performance(self):
        """Test AWS session caching performance."""
        config = Mock()
        config.session_duration = 3600
        config.max_workers = 10
        
        session_manager = AWSSessionManager(config)
        
        # Mock session creation to be slow
        def slow_session_creation(*args, **kwargs):
            time.sleep(0.1)  # Simulate slow session creation
            return Mock()
        
        with patch('boto3.Session', side_effect=slow_session_creation):
            with patch.object(session_manager, 'get_profiles') as mock_profiles:
                from ic.core.session import ProfileInfo
                mock_profiles.return_value = {
                    '123456789012': ProfileInfo('test-profile', 'direct', '123456789012')
                }
                
                with patch.object(session_manager, 'get_account_alias', return_value='test-account'):
                    # First session creation (should be slow)
                    start_time = time.time()
                    session1 = session_manager.create_session('123456789012', 'us-east-1')
                    first_creation_time = time.time() - start_time
                    
                    # Second session creation (should use cache, be fast)
                    start_time = time.time()
                    session2 = session_manager.create_session('123456789012', 'us-east-1')
                    cached_creation_time = time.time() - start_time
                    
                    # Cached session should be much faster
                    assert cached_creation_time < first_creation_time / 2
                    assert session1 is session2  # Should be same object from cache
    
    def test_parallel_session_creation_performance(self):
        """Test parallel session creation performance."""
        config = Mock()
        config.session_duration = 3600
        config.max_workers = 10
        
        session_manager = AWSSessionManager(config)
        
        # Mock multiple accounts
        account_regions = [
            ('123456789012', 'us-east-1'),
            ('123456789013', 'us-west-2'),
            ('123456789014', 'eu-west-1'),
            ('123456789015', 'ap-northeast-1'),
            ('123456789016', 'us-east-2')
        ]
        
        with patch.object(session_manager, 'create_session') as mock_create:
            def mock_session_creation(account_id, region):
                time.sleep(0.05)  # Simulate session creation time
                return Mock()
            
            mock_create.side_effect = mock_session_creation
            
            # Test parallel creation
            start_time = time.time()
            sessions = session_manager.create_sessions_parallel(account_regions)
            parallel_time = time.time() - start_time
            
            # Test sequential creation for comparison
            start_time = time.time()
            for account_id, region in account_regions:
                session_manager.create_session(account_id, region)
            sequential_time = time.time() - start_time
            
            # Parallel should be significantly faster
            assert parallel_time < sequential_time / 2
            assert len(sessions) == len(account_regions)
    
    def test_security_validation_performance_large_config(self):
        """Test security validation performance with large configurations."""
        # Create large configuration
        large_config = {'version': '1.0'}
        
        # Add many configuration entries
        for i in range(1000):
            large_config[f'service_{i}'] = {
                'name': f'service-{i}',
                'host': f'host-{i}.example.com',
                'port': 8080 + i,
                'timeout': 30,
                'retries': 3,
                'enabled': i % 2 == 0,
                'metadata': {
                    'version': f'1.{i}.0',
                    'description': f'Service {i} description',
                    'tags': [f'tag-{j}' for j in range(5)],
                    'config': {
                        'debug': i % 10 == 0,
                        'log_level': 'INFO',
                        'features': [f'feature-{k}' for k in range(3)]
                    }
                }
            }
        
        # Add some sensitive data
        for i in range(0, 1000, 100):
            large_config[f'service_{i}']['password'] = f'secret-{i}'
            large_config[f'service_{i}']['api_token'] = f'sk-{i:032d}'
        
        # Measure validation performance
        start_time = time.time()
        warnings = self.security_manager.validate_config_security(large_config)
        validation_time = time.time() - start_time
        
        # Should complete in reasonable time
        assert validation_time < 2.0, f"Validation took {validation_time:.2f}s"
        
        # Should detect all sensitive data
        assert len(warnings) == 20  # 2 sensitive fields × 10 services
    
    def test_sensitive_data_masking_performance(self):
        """Test sensitive data masking performance with large datasets."""
        # Create large dataset with nested structures
        large_dataset = {}
        
        for i in range(500):
            large_dataset[f'service_{i}'] = {
                'config': {
                    'host': f'host-{i}.example.com',
                    'port': 8080 + i,
                    'credentials': {
                        'username': f'user-{i}',
                        'password': f'secret-{i}' if i % 50 == 0 else f'placeholder-{i}',
                        'tokens': [
                            f'token-{i}-{j}' for j in range(3)
                        ]
                    },
                    'apis': [
                        {
                            'name': f'api-{i}-{k}',
                            'endpoint': f'https://api-{i}-{k}.example.com',
                            'key': f'sk-{i:032d}' if i % 25 == 0 else f'placeholder-key-{i}-{k}'
                        }
                        for k in range(2)
                    ]
                }
            }
        
        # Measure masking performance
        start_time = time.time()
        masked_dataset = self.security_manager.mask_sensitive_data(large_dataset)
        masking_time = time.time() - start_time
        
        # Should complete masking in reasonable time
        assert masking_time < 3.0, f"Masking took {masking_time:.2f}s"
        
        # Verify structure is preserved
        assert len(masked_dataset) == 500
        assert 'service_0' in masked_dataset
        assert 'config' in masked_dataset['service_0']
    
    def test_concurrent_security_operations(self):
        """Test concurrent security operations."""
        def validate_config(config_data):
            return self.security_manager.validate_config_security(config_data)
        
        def mask_data(data):
            return self.security_manager.mask_sensitive_data(data)
        
        # Create test data
        test_configs = []
        for i in range(20):
            config = {
                f'service_{i}': {
                    'host': f'host-{i}.example.com',
                    'password': f'secret-{i}',
                    'api_key': f'sk-{i:032d}',
                    'normal_config': f'value-{i}'
                }
            }
            test_configs.append(config)
        
        # Test concurrent validation
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=5) as executor:
            validation_futures = [executor.submit(validate_config, config) for config in test_configs]
            masking_futures = [executor.submit(mask_data, config) for config in test_configs]
            
            # Wait for all operations to complete
            validation_results = [future.result() for future in validation_futures]
            masking_results = [future.result() for future in masking_futures]
        
        concurrent_time = time.time() - start_time
        
        # Test sequential operations for comparison
        start_time = time.time()
        sequential_validation = [validate_config(config) for config in test_configs]
        sequential_masking = [mask_data(config) for config in test_configs]
        sequential_time = time.time() - start_time
        
        # Concurrent should be faster or at least not significantly slower
        assert concurrent_time <= sequential_time * 1.5
        
        # Results should be correct
        assert len(validation_results) == 20
        assert len(masking_results) == 20
        assert all(len(warnings) >= 2 for warnings in validation_results)  # Each config has 2 sensitive fields
    
    def test_logging_performance_with_masking(self):
        """Test logging performance with sensitive data masking."""
        config = {
            'logging': {
                'console_level': 'ERROR',
                'file_level': 'INFO',
                'mask_sensitive': True
            },
            'security': {
                'sensitive_keys': ['password', 'token', 'key', 'secret'],
                'mask_pattern': '***MASKED***'
            }
        }
        
        logger = ICLogger(config)
        logger.logger = Mock()  # Mock underlying logger
        
        # Test messages with varying amounts of sensitive data
        test_messages = [
            'Normal log message without sensitive data',
            'Login with password=secret123 successful',
            'API call with token=sk-1234567890abcdefghijklmnopqrstuvwxyz completed',
            'Multiple secrets: password=secret1, api_key=sk-abcdef123456, token=ghp_token123',
            'Very long message with password=secret123 and token=sk-1234567890abcdefghijklmnopqrstuvwxyz and key=AKIA1234567890ABCDEF repeated multiple times with password=secret456 and token=sk-9876543210zyxwvutsrqponmlkjihgfedcba'
        ]
        
        # Measure logging performance
        start_time = time.time()
        
        for _ in range(100):  # Log each message 100 times
            for message in test_messages:
                logger.log_info_file_only(message)
        
        logging_time = time.time() - start_time
        
        # Should complete logging in reasonable time
        assert logging_time < 2.0, f"Logging took {logging_time:.2f}s"
        
        # Verify logger was called
        assert logger.logger.info.call_count == 500  # 5 messages × 100 iterations
    
    def test_mcp_manager_performance_with_many_servers(self):
        """Test MCP manager performance with many servers."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add many servers with various configurations
        from ic.core.mcp_manager import MCPServerConfig
        
        for i in range(100):
            manager.servers[f'server_{i}'] = MCPServerConfig(
                name=f'server_{i}',
                command=f'command_{i}',
                args=[f'arg_{j}' for j in range(5)],
                env={
                    f'VAR_{j}': f'sk-{i:032d}' if j == 0 else f'value_{i}_{j}'
                    for j in range(10)
                },
                disabled=i % 10 == 0,  # Every 10th server is disabled
                auto_approve=[f'method_{k}' for k in range(3)]
            )
        
        # Test listing servers with masking
        start_time = time.time()
        masked_servers = manager.list_servers(include_disabled=True, mask_sensitive=True)
        masking_time = time.time() - start_time
        
        # Should complete in reasonable time
        assert masking_time < 1.0, f"Server listing with masking took {masking_time:.2f}s"
        
        # Test security summary generation
        start_time = time.time()
        security_summary = manager.get_security_summary()
        summary_time = time.time() - start_time
        
        # Should complete in reasonable time
        assert summary_time < 2.0, f"Security summary took {summary_time:.2f}s"
        
        # Verify results
        assert security_summary['total_servers'] == 100
        assert security_summary['enabled_servers'] == 90  # 10 disabled
        assert security_summary['servers_with_env_vars'] == 100
    
    def test_memory_usage_with_large_datasets(self):
        """Test memory usage with large datasets."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create large configuration
        large_config = {}
        for i in range(1000):
            large_config[f'service_{i}'] = {
                'name': f'service-{i}',
                'config': {
                    'host': f'host-{i}.example.com',
                    'port': 8080 + i,
                    'credentials': {
                        'username': f'user-{i}',
                        'password': f'secret-{i}',
                        'tokens': [f'token-{i}-{j}' for j in range(10)]
                    },
                    'metadata': {
                        'description': f'Service {i} ' * 100,  # Large text
                        'tags': [f'tag-{i}-{k}' for k in range(20)]
                    }
                }
            }
        
        # Perform security operations
        warnings = self.security_manager.validate_config_security(large_config)
        masked_config = self.security_manager.mask_sensitive_data(large_config)
        
        # Check memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.1f}MB"
        
        # Cleanup
        del large_config
        del masked_config
    
    def test_thread_safety_of_security_operations(self):
        """Test thread safety of security operations."""
        def worker_function(worker_id):
            results = []
            for i in range(50):
                config = {
                    f'worker_{worker_id}_item_{i}': {
                        'password': f'secret-{worker_id}-{i}',
                        'api_key': f'sk-{worker_id:02d}{i:02d}' + '0' * 28,
                        'normal_value': f'value-{worker_id}-{i}'
                    }
                }
                
                # Perform security operations
                warnings = self.security_manager.validate_config_security(config)
                masked = self.security_manager.mask_sensitive_data(config)
                
                results.append({
                    'warnings': len(warnings),
                    'masked_keys': len([k for k, v in masked[f'worker_{worker_id}_item_{i}'].items() if v == '***MASKED***'])
                })
            
            return results
        
        # Run multiple workers concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_function, i) for i in range(5)]
            results = [future.result() for future in futures]
        
        # Verify all workers completed successfully
        assert len(results) == 5
        for worker_results in results:
            assert len(worker_results) == 50
            for result in worker_results:
                assert result['warnings'] >= 2  # password and api_key
                assert result['masked_keys'] >= 2  # password and api_key masked


if __name__ == '__main__':
    pytest.main([__file__])