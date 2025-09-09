"""
Integration tests for MCP server communication and query handling.

Tests MCP server configuration loading and query execution.
"""

import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from ic.core.mcp_manager import MCPManager, MCPQueryResult
from ic.config.security import SecurityManager


class TestMCPServerIntegration:
    """Integration tests for MCP server functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        
        # Sample MCP configuration for integration testing
        self.workspace_mcp_config = {
            "mcpServers": {
                "aws-docs": {
                    "command": "uvx",
                    "args": ["awslabs.aws-documentation-mcp-server@latest"],
                    "env": {"AWS_DOCUMENTATION_PARTITION": "aws"},
                    "disabled": False,
                    "autoApprove": ["read_documentation", "search_documentation"]
                },
                "terraform": {
                    "command": "docker",
                    "args": ["run", "-i", "--rm", "hashicorp/terraform-mcp-server"],
                    "env": {},
                    "disabled": False,
                    "autoApprove": []
                }
            }
        }
        
        self.user_mcp_config = {
            "mcpServers": {
                "github": {
                    "command": "docker",
                    "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_user_token_12345"},
                    "disabled": False,
                    "autoApprove": ["list_repositories"]
                },
                "azure": {
                    "command": "npx",
                    "args": ["-y", "@azure/mcp@latest", "server", "start"],
                    "env": {"AZURE_TENANT_ID": "tenant-456"},
                    "disabled": True,
                    "autoApprove": []
                }
            }
        }
    
    def create_temp_mcp_config(self, config_data, filename):
        """Create temporary MCP configuration file."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(config_data, temp_file)
        temp_file.close()
        return temp_file.name
    
    def test_mcp_config_loading_integration(self):
        """Test loading MCP configuration from multiple sources."""
        workspace_config_file = self.create_temp_mcp_config(
            self.workspace_mcp_config, 'workspace_mcp.json'
        )
        user_config_file = self.create_temp_mcp_config(
            self.user_mcp_config, 'user_mcp.json'
        )
        
        try:
            # Mock file paths
            with patch.object(Path, 'exists') as mock_exists:
                with patch('builtins.open', mock_open()) as mock_file:
                    def mock_exists_side_effect(path_obj):
                        path_str = str(path_obj)
                        if 'workspace' in path_str or '.kiro/settings/mcp.json' in path_str:
                            return True
                        elif 'user' in path_str or '.kiro/settings/mcp.json' in str(Path.home()):
                            return True
                        return False
                    
                    def mock_file_side_effect(file_path, *args, **kwargs):
                        if '.kiro/settings/mcp.json' in str(file_path):
                            if Path.home() in Path(file_path).parents:
                                # User config
                                mock_file.return_value.read.return_value = json.dumps(self.user_mcp_config)
                            else:
                                # Workspace config
                                mock_file.return_value.read.return_value = json.dumps(self.workspace_mcp_config)
                        return mock_file.return_value
                    
                    mock_exists.side_effect = mock_exists_side_effect
                    mock_file.side_effect = mock_file_side_effect
                    
                    # Create MCP manager
                    manager = MCPManager(security_manager=self.security_manager)
            
            # Verify servers from both configs were loaded
            assert 'aws-docs' in manager.servers  # From workspace config
            assert 'terraform' in manager.servers  # From workspace config
            assert 'github' in manager.servers  # From user config
            assert 'azure' in manager.servers  # From user config
            
            # Verify workspace config takes precedence (if there were conflicts)
            assert manager.servers['aws-docs'].disabled is False
            assert manager.servers['github'].disabled is False
            assert manager.servers['azure'].disabled is True
            
        finally:
            import os
            os.unlink(workspace_config_file)
            os.unlink(user_config_file)
    
    def test_mcp_server_availability_integration(self):
        """Test MCP server availability checking."""
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(self.workspace_mcp_config))):
                manager = MCPManager(security_manager=self.security_manager)
        
        # Test enabled servers
        assert manager.is_server_available('aws-docs') is True
        assert manager.is_server_available('terraform') is True
        
        # Test non-existent server
        assert manager.is_server_available('nonexistent-server') is False
        
        # Test disabled server
        manager.servers['terraform'].disabled = True
        assert manager.is_server_available('terraform') is False
    
    def test_aws_documentation_query_integration(self):
        """Test AWS documentation query integration."""
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(self.workspace_mcp_config))):
                manager = MCPManager(security_manager=self.security_manager)
        
        # Test successful query
        result = manager.query_aws_best_practices('s3', 'create-bucket')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is True
        assert result.data['service'] == 's3'
        assert result.data['operation'] == 'create-bucket'
        assert result.data['search_type'] == 'aws_documentation'
        assert 'recommendations' in result.data
        assert 'best_practices' in result.data
        assert 'documentation_urls' in result.data
        assert result.server_name == 'awslabs.aws-documentation-mcp-server'
        
        # Verify recommendations are relevant
        recommendations = result.data['recommendations']
        assert len(recommendations) > 0
        assert any('versioning' in rec.lower() for rec in recommendations)
        assert any('encryption' in rec.lower() for rec in recommendations)
        
        # Test with custom search phrase
        result = manager.query_aws_best_practices('', '', 'lambda security best practices')
        assert result.success is True
        assert result.data['query'] == 'lambda security best practices'
    
    def test_terraform_module_query_integration(self):
        """Test Terraform module query integration."""
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(self.workspace_mcp_config))):
                manager = MCPManager(security_manager=self.security_manager)
        
        # Test successful query
        result = manager.query_terraform_module('aws', 's3')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is True
        assert result.data['provider'] == 'aws'
        assert result.data['service'] == 's3'
        assert result.data['search_type'] == 'terraform_modules'
        assert 'recommended_modules' in result.data
        assert 'provider_info' in result.data
        assert 'usage_examples' in result.data
        assert result.server_name == 'terraform'
        
        # Verify module recommendations
        modules = result.data['recommended_modules']
        assert len(modules) > 0
        assert any('s3-bucket' in module['name'] for module in modules)
        
        # Verify provider info
        provider_info = result.data['provider_info']
        assert provider_info['source'] == 'hashicorp/aws'
        assert 'documentation' in provider_info
    
    def test_mcp_query_fallback_integration(self):
        """Test MCP query fallback when servers are unavailable."""
        # Create manager with no servers configured
        with patch.object(Path, 'exists', return_value=False):
            manager = MCPManager(security_manager=self.security_manager)
        
        # Test AWS query fallback
        result = manager.query_aws_best_practices('ec2', 'launch-instance')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is False
        assert 'AWS documentation MCP server not available' in result.error
        assert result.data['fallback'] is True
        assert 'recommendations' in result.data
        assert 'documentation_urls' in result.data
        
        # Verify fallback data is meaningful
        recommendations = result.data['recommendations']
        assert len(recommendations) > 0
        assert any('security' in rec.lower() for rec in recommendations)
        
        # Test Terraform query fallback
        result = manager.query_terraform_module('azure', 'vm')
        
        assert result.success is False
        assert 'Terraform MCP server not available' in result.error
        assert result.data['fallback'] is True
        assert 'recommended_modules' in result.data
    
    def test_mcp_security_integration(self):
        """Test MCP security features integration."""
        # Create config with sensitive data
        sensitive_config = {
            "mcpServers": {
                "github": {
                    "command": "docker",
                    "args": ["run", "-i", "--rm"],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
                        "API_SECRET": "sk-1234567890abcdefghijklmnopqrstuvwxyz"
                    },
                    "disabled": False,
                    "autoApprove": []
                }
            }
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(sensitive_config))):
                manager = MCPManager(security_manager=self.security_manager)
        
        # Test server configuration with masking
        config = manager.get_server_config('github', mask_sensitive=True)
        assert config['env']['GITHUB_PERSONAL_ACCESS_TOKEN'] == '***MASKED***'
        assert config['env']['API_SECRET'] == '***MASKED***'
        
        # Test server configuration without masking
        config = manager.get_server_config('github', mask_sensitive=False)
        assert config['env']['GITHUB_PERSONAL_ACCESS_TOKEN'] == 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'
        assert config['env']['API_SECRET'] == 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
        
        # Test security validation
        warnings = manager.validate_server_security('github')
        assert len(warnings) > 0
        assert any('env' in warning for warning in warnings)
        
        # Test security summary
        summary = manager.get_security_summary()
        assert summary['total_servers'] == 1
        assert summary['enabled_servers'] == 1
        assert summary['servers_with_env_vars'] == 1
        assert 'github' in summary['security_warnings']
        assert 'github' in summary['masked_configs']
    
    def test_github_operations_query_integration(self):
        """Test GitHub operations query integration."""
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(self.user_mcp_config))):
                manager = MCPManager(security_manager=self.security_manager)
        
        # Test successful query
        result = manager.query_github_operations('list_issues', 'owner/repo')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is True
        assert result.data['operation'] == 'list_issues'
        assert result.data['repository'] == 'owner/repo'
        assert result.data['search_type'] == 'github_operations'
        assert 'operation_info' in result.data
        assert 'api_endpoints' in result.data
        assert 'examples' in result.data
        assert result.server_name == 'github'
        
        # Test with sensitive parameters
        result = manager.query_github_operations(
            'create_issue',
            'owner/repo',
            token='ghp_sensitive_token_12345',
            title='Test Issue'
        )
        
        assert result.success is True
        # Sensitive data should be masked in result
        assert result.data['parameters']['token'] == '***MASKED***'
        assert result.data['parameters']['title'] == 'Test Issue'
    
    def test_azure_documentation_query_integration(self):
        """Test Azure documentation query integration."""
        # Enable Azure server for testing
        azure_config = {
            "mcpServers": {
                "Azure MCP Server": {
                    "command": "npx",
                    "args": ["-y", "@azure/mcp@latest", "server", "start"],
                    "env": {},
                    "disabled": False,
                    "autoApprove": ["documentation"]
                }
            }
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(azure_config))):
                manager = MCPManager(security_manager=self.security_manager)
        
        # Test successful query
        result = manager.query_azure_documentation('vm', 'documentation', 'create')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is True
        assert result.data['service'] == 'vm'
        assert result.data['intent'] == 'documentation'
        assert result.data['operation'] == 'create'
        assert result.data['search_type'] == 'azure_documentation'
        assert 'service_info' in result.data
        assert 'best_practices' in result.data
        assert 'documentation_links' in result.data
        assert 'cli_examples' in result.data
        assert result.server_name == 'Azure MCP Server'
        
        # Verify service info
        service_info = result.data['service_info']
        assert service_info['name'] == 'Virtual Machines'
        assert 'description' in service_info
        
        # Verify best practices
        best_practices = result.data['best_practices']
        assert len(best_practices) > 0
        assert any('managed disks' in practice.lower() for practice in best_practices)
    
    def test_mcp_configuration_merging_integration(self):
        """Test MCP configuration merging from multiple sources."""
        # Create overlapping configurations
        workspace_config = {
            "mcpServers": {
                "aws-docs": {
                    "command": "uvx",
                    "args": ["awslabs.aws-documentation-mcp-server@latest"],
                    "env": {},
                    "disabled": False,
                    "autoApprove": ["read_documentation"]
                },
                "shared-server": {
                    "command": "workspace-command",
                    "args": ["workspace-arg"],
                    "env": {"WORKSPACE_VAR": "workspace-value"},
                    "disabled": False,
                    "autoApprove": []
                }
            }
        }
        
        user_config = {
            "mcpServers": {
                "github": {
                    "command": "docker",
                    "args": ["run", "-i", "--rm"],
                    "env": {"GITHUB_TOKEN": "user-token"},
                    "disabled": False,
                    "autoApprove": []
                },
                "shared-server": {
                    "command": "user-command",
                    "args": ["user-arg"],
                    "env": {"USER_VAR": "user-value"},
                    "disabled": True,
                    "autoApprove": ["user-method"]
                }
            }
        }
        
        constructor_config = {
            "mcp": {
                "servers": {
                    "terraform": {
                        "enabled": True,
                        "auto_approve": ["search_modules"]
                    }
                }
            }
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open()) as mock_file:
                def mock_file_side_effect(file_path, *args, **kwargs):
                    if Path.home() in Path(file_path).parents:
                        # User config
                        mock_file.return_value.read.return_value = json.dumps(user_config)
                    else:
                        # Workspace config
                        mock_file.return_value.read.return_value = json.dumps(workspace_config)
                    return mock_file.return_value
                
                mock_file.side_effect = mock_file_side_effect
                
                # Create manager with constructor config
                manager = MCPManager(
                    config=constructor_config,
                    security_manager=self.security_manager
                )
        
        # Verify all servers are loaded
        assert 'aws-docs' in manager.servers  # From workspace
        assert 'github' in manager.servers  # From user
        assert 'terraform' in manager.servers  # From constructor
        assert 'shared-server' in manager.servers  # Merged
        
        # Verify workspace config takes precedence for shared-server
        shared_server = manager.servers['shared-server']
        assert shared_server.command == 'workspace-command'
        assert shared_server.args == ['workspace-arg']
        assert shared_server.disabled is False  # Workspace overrides user
    
    def test_mcp_error_handling_integration(self):
        """Test MCP error handling in various scenarios."""
        # Test with invalid JSON configuration
        invalid_json = "{ invalid json content"
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=invalid_json)):
                # Should handle invalid JSON gracefully
                manager = MCPManager(security_manager=self.security_manager)
                
                # Should have no servers loaded due to invalid JSON
                assert len(manager.servers) == 0
        
        # Test with missing configuration files
        with patch.object(Path, 'exists', return_value=False):
            manager = MCPManager(security_manager=self.security_manager)
            
            # Should handle missing files gracefully
            assert len(manager.servers) == 0
            
            # Queries should return fallback results
            result = manager.query_aws_best_practices('s3', 'create-bucket')
            assert result.success is False
            assert result.data['fallback'] is True
        
        # Test with file read errors
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', side_effect=IOError("Permission denied")):
                # Should handle file read errors gracefully
                manager = MCPManager(security_manager=self.security_manager)
                
                assert len(manager.servers) == 0


if __name__ == '__main__':
    pytest.main([__file__])