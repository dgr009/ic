"""
Tests for MCP Manager functionality.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from ic.core.mcp_manager import MCPManager, MCPServerConfig, MCPQueryResult, create_default_mcp_config
from ic.config.security import SecurityManager


class TestMCPManager:
    """Test cases for MCPManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.sample_mcp_config = {
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
                },
                "github": {
                    "command": "docker",
                    "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_test_token_12345"},
                    "disabled": True,
                    "autoApprove": []
                }
            }
        }
    
    def test_mcp_manager_initialization(self):
        """Test MCPManager initialization."""
        manager = MCPManager(security_manager=self.security_manager)
        assert manager.security == self.security_manager
        assert isinstance(manager.servers, dict)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_load_mcp_config_file(self, mock_exists, mock_file):
        """Test loading MCP configuration from file."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.sample_mcp_config)
        
        manager = MCPManager(security_manager=self.security_manager)
        config = manager._load_mcp_config_file(Path('.kiro/settings/mcp.json'))
        
        assert config is not None
        assert 'mcpServers' in config
        assert 'aws-docs' in config['mcpServers']
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_load_mcp_servers(self, mock_exists, mock_file):
        """Test loading MCP servers from configuration."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.sample_mcp_config)
        
        manager = MCPManager(security_manager=self.security_manager)
        
        assert len(manager.servers) > 0
        assert 'aws-docs' in manager.servers
        assert isinstance(manager.servers['aws-docs'], MCPServerConfig)
        assert manager.servers['aws-docs'].command == 'uvx'
    
    def test_get_server_config_with_masking(self):
        """Test getting server configuration with sensitive data masking."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add a test server with sensitive data
        manager.servers['test-server'] = MCPServerConfig(
            name='test-server',
            command='test',
            args=[],
            env={'API_TOKEN': 'secret-token-12345'},
            disabled=False,
            auto_approve=[]
        )
        
        # Get config with masking
        config = manager.get_server_config('test-server', mask_sensitive=True)
        assert config is not None
        assert config['env']['API_TOKEN'] == '***MASKED***'
        
        # Get config without masking
        config = manager.get_server_config('test-server', mask_sensitive=False)
        assert config is not None
        assert config['env']['API_TOKEN'] == 'secret-token-12345'
    
    def test_is_server_available(self):
        """Test checking server availability."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add test servers
        manager.servers['enabled-server'] = MCPServerConfig(
            name='enabled-server',
            command='test',
            args=[],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        manager.servers['disabled-server'] = MCPServerConfig(
            name='disabled-server',
            command='test',
            args=[],
            env={},
            disabled=True,
            auto_approve=[]
        )
        
        assert manager.is_server_available('enabled-server') is True
        assert manager.is_server_available('disabled-server') is False
        assert manager.is_server_available('nonexistent-server') is False
    
    def test_query_aws_best_practices(self):
        """Test AWS best practices query."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add AWS docs server
        manager.servers['awslabs.aws-documentation-mcp-server'] = MCPServerConfig(
            name='awslabs.aws-documentation-mcp-server',
            command='uvx',
            args=['awslabs.aws-documentation-mcp-server@latest'],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        result = manager.query_aws_best_practices('s3', 'create-bucket')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is True
        assert result.data['service'] == 's3'
        assert result.data['operation'] == 'create-bucket'
        assert 'recommendations' in result.data
        assert 'best_practices' in result.data
    
    @patch('pathlib.Path.exists')
    def test_query_aws_best_practices_fallback(self, mock_exists):
        """Test AWS best practices query with fallback when server unavailable."""
        # Mock no config files exist
        mock_exists.return_value = False
        
        manager = MCPManager(security_manager=self.security_manager)
        
        result = manager.query_aws_best_practices('s3', 'create-bucket')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is False
        assert 'AWS documentation MCP server not available' in result.error
        assert result.data['fallback'] is True
        assert 'recommendations' in result.data
    
    def test_query_terraform_module(self):
        """Test Terraform module query."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add Terraform server
        manager.servers['terraform'] = MCPServerConfig(
            name='terraform',
            command='docker',
            args=['run', '-i', '--rm', 'hashicorp/terraform-mcp-server'],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        result = manager.query_terraform_module('aws', 's3')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is True
        assert result.data['provider'] == 'aws'
        assert result.data['service'] == 's3'
        assert 'recommended_modules' in result.data
    
    def test_query_azure_documentation(self):
        """Test Azure documentation query."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add Azure server
        manager.servers['Azure MCP Server'] = MCPServerConfig(
            name='Azure MCP Server',
            command='npx',
            args=['-y', '@azure/mcp@latest', 'server', 'start'],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        result = manager.query_azure_documentation('vm', 'documentation')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is True
        assert result.data['service'] == 'vm'
        assert result.data['intent'] == 'documentation'
        assert 'service_info' in result.data
    
    def test_query_github_operations(self):
        """Test GitHub operations query."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add GitHub server
        manager.servers['github'] = MCPServerConfig(
            name='github',
            command='docker',
            args=['run', '-i', '--rm'],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        result = manager.query_github_operations('list_issues', 'owner/repo')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is True
        assert result.data['operation'] == 'list_issues'
        assert result.data['repository'] == 'owner/repo'
        assert 'operation_info' in result.data
    
    @patch('pathlib.Path.exists')
    def test_validate_server_security(self, mock_exists):
        """Test server security validation."""
        # Mock no config files exist
        mock_exists.return_value = False
        
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add server with sensitive data
        manager.servers['insecure-server'] = MCPServerConfig(
            name='insecure-server',
            command='test',
            args=['--token', 'sk-1234567890abcdefghijklmnopqrstuvwxyz'],  # Make it look more like a secret
            env={'API_KEY': 'sk-1234567890abcdefghijklmnopqrstuvwxyz'},
            disabled=False,
            auto_approve=[]
        )
        
        warnings = manager.validate_server_security('insecure-server')
        
        assert len(warnings) > 0
        assert any('env' in warning for warning in warnings)
    
    @patch('pathlib.Path.exists')
    def test_get_security_summary(self, mock_exists):
        """Test getting security summary."""
        # Mock no config files exist
        mock_exists.return_value = False
        
        manager = MCPManager(security_manager=self.security_manager)
        
        # Clear any loaded servers and add test servers
        manager.servers.clear()
        
        manager.servers['server1'] = MCPServerConfig(
            name='server1',
            command='test',
            args=[],
            env={'TOKEN': 'secret'},
            disabled=False,
            auto_approve=[]
        )
        
        manager.servers['server2'] = MCPServerConfig(
            name='server2',
            command='test',
            args=[],
            env={},
            disabled=True,
            auto_approve=[]
        )
        
        summary = manager.get_security_summary()
        
        assert summary['total_servers'] == 2
        assert summary['enabled_servers'] == 1
        assert summary['servers_with_env_vars'] == 1
        assert 'security_warnings' in summary
        assert 'masked_configs' in summary
    
    def test_create_default_mcp_config(self):
        """Test creating default MCP configuration."""
        config = create_default_mcp_config()
        
        assert 'mcp' in config
        assert 'servers' in config['mcp']
        assert 'aws_docs' in config['mcp']['servers']
        assert 'terraform' in config['mcp']['servers']
        assert 'azure' in config['mcp']['servers']
        assert 'github' in config['mcp']['servers']
        
        # Check that GitHub is disabled by default for security
        assert config['mcp']['servers']['github']['disabled'] is True


if __name__ == '__main__':
    pytest.main([__file__])