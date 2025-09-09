"""
Unit tests for MCPManager class.

Tests MCP server configuration loading, query methods, and security validation.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from ic.core.mcp_manager import MCPManager, MCPServerConfig, MCPQueryResult, create_default_mcp_config
from ic.config.security import SecurityManager


class TestMCPManagerUnit:
    """Unit test cases for MCPManager class."""
    
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
                },
                "azure": {
                    "command": "npx",
                    "args": ["-y", "@azure/mcp@latest", "server", "start"],
                    "env": {"AZURE_TENANT_ID": "tenant-123", "AZURE_CLIENT_SECRET": "secret-456"},
                    "disabled": False,
                    "autoApprove": ["documentation"]
                }
            }
        }
    
    def test_mcp_manager_initialization(self):
        """Test MCPManager initialization."""
        # Test with security manager
        manager = MCPManager(security_manager=self.security_manager)
        assert manager.security == self.security_manager
        assert isinstance(manager.servers, dict)
        
        # Test with config
        config = {"mcp": {"servers": {"test": {"command": "test"}}}}
        manager_with_config = MCPManager(config=config, security_manager=self.security_manager)
        assert manager_with_config.config == config
    
    def test_mcp_server_config_creation(self):
        """Test MCPServerConfig dataclass creation."""
        config = MCPServerConfig(
            name="test-server",
            command="uvx",
            args=["test-package"],
            env={"TEST_VAR": "test_value"},
            disabled=False,
            auto_approve=["test_method"]
        )
        
        assert config.name == "test-server"
        assert config.command == "uvx"
        assert config.args == ["test-package"]
        assert config.env == {"TEST_VAR": "test_value"}
        assert config.disabled is False
        assert config.auto_approve == ["test_method"]
    
    def test_mcp_query_result_creation(self):
        """Test MCPQueryResult dataclass creation."""
        # Successful result
        result = MCPQueryResult(
            success=True,
            data={"key": "value"},
            server_name="test-server"
        )
        
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.server_name == "test-server"
        
        # Failed result
        failed_result = MCPQueryResult(
            success=False,
            data={},
            error="Server unavailable"
        )
        
        assert failed_result.success is False
        assert failed_result.error == "Server unavailable"
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_load_mcp_config_file_success(self, mock_exists, mock_file):
        """Test loading MCP configuration file successfully."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.sample_mcp_config)
        
        manager = MCPManager(security_manager=self.security_manager)
        config = manager._load_mcp_config_file(Path('.kiro/settings/mcp.json'))
        
        assert config == self.sample_mcp_config
        mock_file.assert_called_once()
    
    @patch('pathlib.Path.exists')
    def test_load_mcp_config_file_not_found(self, mock_exists):
        """Test loading MCP configuration file when file doesn't exist."""
        mock_exists.return_value = False
        
        manager = MCPManager(security_manager=self.security_manager)
        config = manager._load_mcp_config_file(Path('.kiro/settings/mcp.json'))
        
        assert config is None
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_load_mcp_config_file_invalid_json(self, mock_exists, mock_file):
        """Test loading MCP configuration file with invalid JSON."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = "invalid json content"
        
        manager = MCPManager(security_manager=self.security_manager)
        config = manager._load_mcp_config_file(Path('.kiro/settings/mcp.json'))
        
        assert config is None
    
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
        assert manager.servers['aws-docs'].disabled is False
        
        assert 'github' in manager.servers
        assert manager.servers['github'].disabled is True
    
    def test_get_server_config_with_masking(self):
        """Test getting server configuration with sensitive data masking."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add a test server with sensitive data
        manager.servers['test-server'] = MCPServerConfig(
            name='test-server',
            command='test',
            args=[],
            env={'API_TOKEN': 'sk-1234567890abcdefghijklmnopqrstuvwxyz'},
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
        assert config['env']['API_TOKEN'] == 'sk-1234567890abcdefghijklmnopqrstuvwxyz'
    
    def test_get_server_config_not_found(self):
        """Test getting configuration for non-existent server."""
        manager = MCPManager(security_manager=self.security_manager)
        
        config = manager.get_server_config('nonexistent-server')
        assert config is None
    
    def test_list_servers(self):
        """Test listing MCP servers."""
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
        
        # List enabled servers only (default)
        enabled_servers = manager.list_servers(include_disabled=False)
        assert 'enabled-server' in enabled_servers
        assert 'disabled-server' not in enabled_servers
        
        # List all servers
        all_servers = manager.list_servers(include_disabled=True)
        assert 'enabled-server' in all_servers
        assert 'disabled-server' in all_servers
    
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
    
    def test_query_aws_best_practices_server_available(self):
        """Test AWS best practices query with server available."""
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
        assert result.server_name == 'awslabs.aws-documentation-mcp-server'
    
    @patch('pathlib.Path.exists')
    def test_query_aws_best_practices_server_unavailable(self, mock_exists):
        """Test AWS best practices query with server unavailable."""
        mock_exists.return_value = False  # No config files
        
        manager = MCPManager(security_manager=self.security_manager)
        
        result = manager.query_aws_best_practices('s3', 'create-bucket')
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is False
        assert 'AWS documentation MCP server not available' in result.error
        assert result.data['fallback'] is True
        assert 'recommendations' in result.data
    
    def test_query_aws_best_practices_custom_search_phrase(self):
        """Test AWS best practices query with custom search phrase."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add AWS docs server
        manager.servers['aws-docs'] = MCPServerConfig(
            name='aws-docs',
            command='uvx',
            args=['awslabs.aws-documentation-mcp-server@latest'],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        result = manager.query_aws_best_practices('', '', 'lambda security best practices')
        
        assert result.success is True
        assert result.data['query'] == 'lambda security best practices'
    
    def test_query_terraform_module_server_available(self):
        """Test Terraform module query with server available."""
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
        assert result.server_name == 'terraform'
    
    def test_query_terraform_module_with_module_name(self):
        """Test Terraform module query with specific module name."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add Terraform server
        manager.servers['terraform'] = MCPServerConfig(
            name='terraform',
            command='terraform',
            args=[],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        result = manager.query_terraform_module('aws', 's3', 'terraform-aws-modules/s3-bucket/aws')
        
        assert result.success is True
        assert result.data['module_name'] == 'terraform-aws-modules/s3-bucket/aws'
        assert result.data['query'] == 'terraform-aws-modules/s3-bucket/aws'
    
    def test_query_azure_documentation_server_available(self):
        """Test Azure documentation query with server available."""
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
        assert result.server_name == 'Azure MCP Server'
    
    def test_query_github_operations_server_available(self):
        """Test GitHub operations query with server available."""
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
        assert result.server_name == 'github'
    
    def test_query_github_operations_with_sensitive_params(self):
        """Test GitHub operations query with sensitive parameters."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add GitHub server
        manager.servers['github'] = MCPServerConfig(
            name='github',
            command='github',
            args=[],
            env={},
            disabled=False,
            auto_approve=[]
        )
        
        result = manager.query_github_operations(
            'create_issue',
            'owner/repo',
            token='ghp_1234567890abcdefghijklmnopqrstuvwxyz',
            title='Test Issue'
        )
        
        assert result.success is True
        # Sensitive data should be masked
        assert result.data['parameters']['token'] == '***MASKED***'
        assert result.data['parameters']['title'] == 'Test Issue'
    
    def test_validate_server_security(self):
        """Test server security validation."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add server with sensitive data
        manager.servers['insecure-server'] = MCPServerConfig(
            name='insecure-server',
            command='test',
            args=['--token', 'sk-1234567890abcdefghijklmnopqrstuvwxyz'],
            env={'API_KEY': 'sk-1234567890abcdefghijklmnopqrstuvwxyz'},
            disabled=False,
            auto_approve=[]
        )
        
        warnings = manager.validate_server_security('insecure-server')
        
        assert len(warnings) > 0
        assert any('env' in warning for warning in warnings)
        assert any('args' in warning for warning in warnings)
    
    def test_validate_server_security_not_found(self):
        """Test security validation for non-existent server."""
        manager = MCPManager(security_manager=self.security_manager)
        
        warnings = manager.validate_server_security('nonexistent-server')
        
        assert len(warnings) == 1
        assert 'not found' in warnings[0]
    
    def test_get_security_summary(self):
        """Test getting security summary."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Add test servers
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
    
    def test_create_fallback_result(self):
        """Test creating fallback result."""
        manager = MCPManager(security_manager=self.security_manager)
        
        fallback_data = {'fallback': True, 'message': 'Server unavailable'}
        result = manager._create_fallback_result('Test error', fallback_data)
        
        assert isinstance(result, MCPQueryResult)
        assert result.success is False
        assert result.error == 'Test error'
        assert result.data == fallback_data
        assert result.server_name is None
    
    def test_get_aws_recommendations(self):
        """Test getting AWS service recommendations."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Test known service
        s3_recommendations = manager._get_aws_recommendations('s3', 'create-bucket')
        assert len(s3_recommendations) > 0
        assert any('versioning' in rec.lower() for rec in s3_recommendations)
        
        # Test unknown service
        unknown_recommendations = manager._get_aws_recommendations('unknown-service', 'operation')
        assert len(unknown_recommendations) > 0
        assert 'unknown-service' in unknown_recommendations[0]
    
    def test_get_terraform_module_recommendations(self):
        """Test getting Terraform module recommendations."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Test AWS S3 modules
        aws_s3_modules = manager._get_terraform_module_recommendations('aws', 's3')
        assert len(aws_s3_modules) > 0
        assert any('s3-bucket' in module['name'] for module in aws_s3_modules)
        
        # Test unknown provider/service
        unknown_modules = manager._get_terraform_module_recommendations('unknown', 'service')
        assert len(unknown_modules) == 0
    
    def test_get_azure_service_info(self):
        """Test getting Azure service information."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Test known service
        vm_info = manager._get_azure_service_info('vm')
        assert vm_info['name'] == 'Virtual Machines'
        assert 'description' in vm_info
        
        # Test unknown service
        unknown_info = manager._get_azure_service_info('unknown-service')
        assert unknown_info['name'] == 'unknown-service'
        assert 'Azure unknown-service service' in unknown_info['description']
    
    def test_get_github_operation_info(self):
        """Test getting GitHub operation information."""
        manager = MCPManager(security_manager=self.security_manager)
        
        # Test known operation
        list_issues_info = manager._get_github_operation_info('list_issues')
        assert list_issues_info['description'] == 'List issues in a repository'
        assert list_issues_info['method'] == 'GET'
        
        # Test unknown operation
        unknown_info = manager._get_github_operation_info('unknown_operation')
        assert 'GitHub unknown_operation operation' in unknown_info['description']


class TestCreateDefaultMCPConfig:
    """Test cases for creating default MCP configuration."""
    
    def test_create_default_mcp_config(self):
        """Test creating default MCP configuration."""
        config = create_default_mcp_config()
        
        assert 'mcp' in config
        assert 'servers' in config['mcp']
        
        servers = config['mcp']['servers']
        assert 'aws_docs' in servers
        assert 'terraform' in servers
        assert 'azure' in servers
        assert 'github' in servers
        
        # Check that GitHub is disabled by default for security
        assert servers['github']['disabled'] is True
        
        # Check that AWS docs has auto-approve settings
        assert 'read_documentation' in servers['aws_docs']['auto_approve']
        assert 'search_documentation' in servers['aws_docs']['auto_approve']
    
    def test_default_config_structure(self):
        """Test default configuration structure."""
        config = create_default_mcp_config()
        
        # Verify each server has required fields
        for server_name, server_config in config['mcp']['servers'].items():
            assert 'enabled' in server_config
            assert 'auto_approve' in server_config
            assert isinstance(server_config['auto_approve'], list)
            assert isinstance(server_config['enabled'], bool)


if __name__ == '__main__':
    pytest.main([__file__])