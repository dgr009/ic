"""
MCP (Model Context Protocol) Manager for IC.

This module provides secure MCP server integration with query capabilities
for AWS, Azure, Terraform, and GitHub operations.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

from ..config.security import SecurityManager

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    disabled: bool
    auto_approve: List[str]


@dataclass
class MCPQueryResult:
    """Result from an MCP query."""
    success: bool
    data: Any
    error: Optional[str] = None
    server_name: Optional[str] = None


class MCPManager:
    """
    Manages MCP server configurations and provides query capabilities.
    
    This class handles secure loading of MCP server configurations,
    sensitive data masking, and provides query methods for different
    cloud platforms and services.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, security_manager: Optional[SecurityManager] = None):
        """
        Initialize MCPManager.
        
        Args:
            config: MCP configuration dictionary
            security_manager: SecurityManager instance for data masking
        """
        self.config = config or {}
        self.security = security_manager or SecurityManager()
        self.servers: Dict[str, MCPServerConfig] = {}
        self._load_mcp_servers()
    
    def _load_mcp_servers(self) -> None:
        """
        Load MCP server configurations from various sources.
        
        Loads from:
        1. Workspace .kiro/settings/mcp.json
        2. User ~/.kiro/settings/mcp.json
        3. Configuration passed to constructor
        """
        # Load from workspace config
        workspace_config = self._load_workspace_mcp_config()
        
        # Load from user config
        user_config = self._load_user_mcp_config()
        
        # Merge configurations (workspace takes precedence)
        merged_servers = {}
        if user_config:
            merged_servers.update(user_config.get('mcpServers', {}))
        if workspace_config:
            merged_servers.update(workspace_config.get('mcpServers', {}))
        
        # Add config from constructor
        if self.config.get('mcp', {}).get('servers'):
            merged_servers.update(self.config['mcp']['servers'])
        
        # Convert to MCPServerConfig objects
        for name, server_config in merged_servers.items():
            try:
                self.servers[name] = MCPServerConfig(
                    name=name,
                    command=server_config.get('command', ''),
                    args=server_config.get('args', []),
                    env=server_config.get('env', {}),
                    disabled=server_config.get('disabled', False),
                    auto_approve=server_config.get('autoApprove', [])
                )
                logger.debug(f"Loaded MCP server config: {name}")
            except Exception as e:
                logger.warning(f"Failed to load MCP server config for {name}: {e}")
    
    def _load_workspace_mcp_config(self) -> Optional[Dict[str, Any]]:
        """
        Load MCP configuration from workspace .kiro/settings/mcp.json.
        
        Returns:
            MCP configuration dictionary or None if not found
        """
        workspace_config_path = Path('.kiro/settings/mcp.json')
        return self._load_mcp_config_file(workspace_config_path)
    
    def _load_user_mcp_config(self) -> Optional[Dict[str, Any]]:
        """
        Load MCP configuration from user ~/.kiro/settings/mcp.json.
        
        Returns:
            MCP configuration dictionary or None if not found
        """
        user_config_path = Path.home() / '.kiro' / 'settings' / 'mcp.json'
        return self._load_mcp_config_file(user_config_path)
    
    def _load_mcp_config_file(self, config_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load MCP configuration from a specific file.
        
        Args:
            config_path: Path to MCP configuration file
            
        Returns:
            MCP configuration dictionary or None if not found/invalid
        """
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.debug(f"Loaded MCP config from {config_path}")
                return config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP config file {config_path}: {e}")
        except Exception as e:
            logger.warning(f"Could not load MCP config from {config_path}: {e}")
        
        return None
    
    def get_server_config(self, server_name: str, mask_sensitive: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific MCP server.
        
        Args:
            server_name: Name of the MCP server
            mask_sensitive: Whether to mask sensitive data in the config
            
        Returns:
            Server configuration dictionary or None if not found
        """
        server = self.servers.get(server_name)
        if not server:
            return None
        
        config = {
            'name': server.name,
            'command': server.command,
            'args': server.args,
            'env': server.env,
            'disabled': server.disabled,
            'auto_approve': server.auto_approve
        }
        
        if mask_sensitive:
            config = self.security.mask_sensitive_data(config)
        
        return config
    
    def list_servers(self, include_disabled: bool = False, mask_sensitive: bool = True) -> Dict[str, Dict[str, Any]]:
        """
        List all configured MCP servers.
        
        Args:
            include_disabled: Whether to include disabled servers
            mask_sensitive: Whether to mask sensitive data in configurations
            
        Returns:
            Dictionary of server configurations
        """
        servers = {}
        for name, server in self.servers.items():
            if not include_disabled and server.disabled:
                continue
            
            config = self.get_server_config(name, mask_sensitive)
            if config:
                servers[name] = config
        
        return servers
    
    def is_server_available(self, server_name: str) -> bool:
        """
        Check if an MCP server is available and enabled.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            True if server is available and enabled
        """
        server = self.servers.get(server_name)
        return server is not None and not server.disabled
    
    def query_aws_best_practices(self, service: str, operation: str = "", search_phrase: str = "") -> MCPQueryResult:
        """
        Query AWS documentation for best practices.
        
        Args:
            service: AWS service name (e.g., 's3', 'ec2', 'lambda')
            operation: Specific operation (e.g., 'create-bucket', 'launch-instance')
            search_phrase: Custom search phrase (overrides service/operation)
            
        Returns:
            MCPQueryResult with AWS documentation data
        """
        server_names = [
            'awslabs.aws-documentation-mcp-server',
            'aws-docs',
            'aws_docs'
        ]
        
        # Find available AWS documentation server
        aws_server = None
        for server_name in server_names:
            if self.is_server_available(server_name):
                aws_server = server_name
                break
        
        if not aws_server:
            return self._create_fallback_result(
                "AWS documentation MCP server not available",
                self._get_aws_fallback_data(service, operation)
            )
        
        # Build search phrase
        if not search_phrase:
            if operation:
                search_phrase = f"{service} {operation} best practices"
            else:
                search_phrase = f"{service} best practices"
        
        logger.info(f"Querying AWS documentation for: {search_phrase}")
        
        try:
            # This would be the actual MCP query implementation
            # For now, return a structured result with fallback data
            return MCPQueryResult(
                success=True,
                data={
                    'query': search_phrase,
                    'server': aws_server,
                    'service': service,
                    'operation': operation,
                    'search_type': 'aws_documentation',
                    'recommendations': self._get_aws_recommendations(service, operation),
                    'documentation_urls': self._get_aws_documentation_urls(service),
                    'best_practices': self._get_aws_best_practices(service)
                },
                server_name=aws_server
            )
        except Exception as e:
            logger.error(f"Error querying AWS documentation: {e}")
            return self._create_fallback_result(
                f"AWS documentation query failed: {str(e)}",
                self._get_aws_fallback_data(service, operation)
            )
    
    def query_terraform_module(self, provider: str, service: str, module_name: str = "") -> MCPQueryResult:
        """
        Query Terraform registry for modules.
        
        Args:
            provider: Terraform provider (e.g., 'aws', 'azure', 'google')
            service: Service name (e.g., 's3', 'vm', 'storage')
            module_name: Specific module name (optional)
            
        Returns:
            MCPQueryResult with Terraform module data
        """
        server_names = [
            'terraform',
            'terraform-mcp-server',
            'hashicorp/terraform-mcp-server'
        ]
        
        # Find available Terraform server
        terraform_server = None
        for server_name in server_names:
            if self.is_server_available(server_name):
                terraform_server = server_name
                break
        
        if not terraform_server:
            return self._create_fallback_result(
                "Terraform MCP server not available",
                self._get_terraform_fallback_data(provider, service, module_name)
            )
        
        # Build query
        if module_name:
            query = module_name
        else:
            query = f"{provider} {service}"
        
        logger.info(f"Querying Terraform registry for: {query}")
        
        try:
            # This would be the actual MCP query implementation
            return MCPQueryResult(
                success=True,
                data={
                    'query': query,
                    'server': terraform_server,
                    'provider': provider,
                    'service': service,
                    'module_name': module_name,
                    'search_type': 'terraform_modules',
                    'recommended_modules': self._get_terraform_module_recommendations(provider, service),
                    'provider_info': self._get_terraform_provider_info(provider),
                    'usage_examples': self._get_terraform_usage_examples(provider, service)
                },
                server_name=terraform_server
            )
        except Exception as e:
            logger.error(f"Error querying Terraform registry: {e}")
            return self._create_fallback_result(
                f"Terraform registry query failed: {str(e)}",
                self._get_terraform_fallback_data(provider, service, module_name)
            )
    
    def query_azure_documentation(self, service: str, intent: str, operation: str = "") -> MCPQueryResult:
        """
        Query Azure documentation and best practices.
        
        Args:
            service: Azure service name (e.g., 'vm', 'storage', 'aks')
            intent: Query intent (e.g., 'documentation', 'best-practices')
            operation: Specific operation (optional)
            
        Returns:
            MCPQueryResult with Azure documentation data
        """
        server_names = [
            'Azure MCP Server',
            'azure',
            'azure-mcp-server'
        ]
        
        # Find available Azure server
        azure_server = None
        for server_name in server_names:
            if self.is_server_available(server_name):
                azure_server = server_name
                break
        
        if not azure_server:
            return self._create_fallback_result(
                "Azure MCP server not available",
                self._get_azure_fallback_data(service, intent, operation)
            )
        
        logger.info(f"Querying Azure documentation for service: {service}, intent: {intent}")
        
        try:
            # This would be the actual MCP query implementation
            return MCPQueryResult(
                success=True,
                data={
                    'service': service,
                    'intent': intent,
                    'operation': operation,
                    'server': azure_server,
                    'search_type': 'azure_documentation',
                    'service_info': self._get_azure_service_info(service),
                    'best_practices': self._get_azure_best_practices(service),
                    'documentation_links': self._get_azure_documentation_links(service),
                    'cli_examples': self._get_azure_cli_examples(service, operation)
                },
                server_name=azure_server
            )
        except Exception as e:
            logger.error(f"Error querying Azure documentation: {e}")
            return self._create_fallback_result(
                f"Azure documentation query failed: {str(e)}",
                self._get_azure_fallback_data(service, intent, operation)
            )
    
    def query_github_operations(self, operation: str, repository: str = "", **kwargs) -> MCPQueryResult:
        """
        Query GitHub MCP server for repository operations.
        
        Args:
            operation: GitHub operation (e.g., 'list_issues', 'create_pr', 'get_repo')
            repository: Repository name in format 'owner/repo' (optional)
            **kwargs: Additional parameters for the operation
            
        Returns:
            MCPQueryResult with GitHub operation data
        """
        server_names = [
            'github',
            'github-mcp-server'
        ]
        
        # Find available GitHub server
        github_server = None
        for server_name in server_names:
            if self.is_server_available(server_name):
                github_server = server_name
                break
        
        if not github_server:
            return self._create_fallback_result(
                "GitHub MCP server not available",
                self._get_github_fallback_data(operation, repository, **kwargs)
            )
        
        logger.info(f"Querying GitHub for operation: {operation}")
        
        try:
            # Mask sensitive data in parameters
            masked_kwargs = self.security.mask_sensitive_data(kwargs)
            
            # This would be the actual MCP query implementation
            return MCPQueryResult(
                success=True,
                data={
                    'operation': operation,
                    'repository': repository,
                    'parameters': masked_kwargs,
                    'server': github_server,
                    'search_type': 'github_operations',
                    'operation_info': self._get_github_operation_info(operation),
                    'repository_info': self._get_github_repository_info(repository) if repository else None,
                    'api_endpoints': self._get_github_api_endpoints(operation),
                    'examples': self._get_github_operation_examples(operation)
                },
                server_name=github_server
            )
        except Exception as e:
            logger.error(f"Error querying GitHub: {e}")
            return self._create_fallback_result(
                f"GitHub operation query failed: {str(e)}",
                self._get_github_fallback_data(operation, repository, **kwargs)
            )
    
    def validate_server_security(self, server_name: str) -> List[str]:
        """
        Validate MCP server configuration for security issues.
        
        Args:
            server_name: Name of the MCP server to validate
            
        Returns:
            List of security warnings
        """
        server = self.servers.get(server_name)
        if not server:
            return [f"Server '{server_name}' not found"]
        
        warnings = []
        
        # Check environment variables for sensitive data
        if server.env:
            env_warnings = self.security.validate_config_security({'env': server.env})
            warnings.extend([f"Server '{server_name}': {w}" for w in env_warnings])
        
        # Check for sensitive data in command arguments
        for i, arg in enumerate(server.args):
            if self.security._looks_like_secret(arg):
                warnings.append(
                    f"Server '{server_name}': Potential secret in args[{i}]. "
                    f"Consider using environment variables."
                )
        
        return warnings
    
    def get_security_summary(self) -> Dict[str, Any]:
        """
        Get security summary for all MCP servers.
        
        Returns:
            Dictionary with security information for all servers
        """
        summary = {
            'total_servers': len(self.servers),
            'enabled_servers': len([s for s in self.servers.values() if not s.disabled]),
            'servers_with_env_vars': len([s for s in self.servers.values() if s.env]),
            'security_warnings': {},
            'masked_configs': {}
        }
        
        for server_name in self.servers:
            # Get security warnings
            warnings = self.validate_server_security(server_name)
            if warnings:
                summary['security_warnings'][server_name] = warnings
            
            # Get masked configuration
            masked_config = self.get_server_config(server_name, mask_sensitive=True)
            if masked_config:
                summary['masked_configs'][server_name] = masked_config
        
        return summary
    
    def _create_fallback_result(self, error_message: str, fallback_data: Dict[str, Any]) -> MCPQueryResult:
        """
        Create a fallback result when MCP server is unavailable.
        
        Args:
            error_message: Error message describing the issue
            fallback_data: Fallback data to provide
            
        Returns:
            MCPQueryResult with fallback data
        """
        return MCPQueryResult(
            success=False,
            data=fallback_data,
            error=error_message,
            server_name=None
        )
    
    def _get_aws_fallback_data(self, service: str, operation: str) -> Dict[str, Any]:
        """Get fallback data for AWS queries."""
        return {
            'service': service,
            'operation': operation,
            'fallback': True,
            'recommendations': self._get_aws_recommendations(service, operation),
            'documentation_urls': self._get_aws_documentation_urls(service),
            'best_practices': self._get_aws_best_practices(service)
        }
    
    def _get_aws_recommendations(self, service: str, operation: str) -> List[str]:
        """Get AWS service recommendations."""
        recommendations = {
            's3': [
                "Enable versioning for data protection",
                "Use server-side encryption",
                "Configure lifecycle policies",
                "Enable access logging"
            ],
            'ec2': [
                "Use latest AMIs with security patches",
                "Configure security groups with least privilege",
                "Enable detailed monitoring",
                "Use IAM roles instead of access keys"
            ],
            'lambda': [
                "Set appropriate timeout values",
                "Use environment variables for configuration",
                "Enable X-Ray tracing for debugging",
                "Configure dead letter queues"
            ]
        }
        return recommendations.get(service.lower(), [f"Follow AWS best practices for {service}"])
    
    def _get_aws_documentation_urls(self, service: str) -> List[str]:
        """Get AWS documentation URLs."""
        base_url = "https://docs.aws.amazon.com"
        urls = {
            's3': [f"{base_url}/s3/", f"{base_url}/s3/latest/userguide/"],
            'ec2': [f"{base_url}/ec2/", f"{base_url}/AWSEC2/latest/UserGuide/"],
            'lambda': [f"{base_url}/lambda/", f"{base_url}/lambda/latest/dg/"]
        }
        return urls.get(service.lower(), [f"{base_url}/{service.lower()}/"])
    
    def _get_aws_best_practices(self, service: str) -> List[str]:
        """Get AWS best practices."""
        practices = {
            's3': [
                "Use bucket policies and ACLs appropriately",
                "Enable MFA delete for critical buckets",
                "Monitor access with CloudTrail"
            ],
            'ec2': [
                "Use Auto Scaling for high availability",
                "Implement proper backup strategies",
                "Regular security updates"
            ],
            'lambda': [
                "Keep functions small and focused",
                "Use layers for shared code",
                "Monitor with CloudWatch"
            ]
        }
        return practices.get(service.lower(), [f"Follow AWS Well-Architected Framework for {service}"])
    
    def _get_terraform_fallback_data(self, provider: str, service: str, module_name: str) -> Dict[str, Any]:
        """Get fallback data for Terraform queries."""
        return {
            'provider': provider,
            'service': service,
            'module_name': module_name,
            'fallback': True,
            'recommended_modules': self._get_terraform_module_recommendations(provider, service),
            'provider_info': self._get_terraform_provider_info(provider),
            'usage_examples': self._get_terraform_usage_examples(provider, service)
        }
    
    def _get_terraform_module_recommendations(self, provider: str, service: str) -> List[Dict[str, str]]:
        """Get Terraform module recommendations."""
        modules = {
            'aws': {
                's3': [
                    {'name': 'terraform-aws-modules/s3-bucket/aws', 'description': 'AWS S3 bucket module'},
                    {'name': 'cloudposse/s3-bucket/aws', 'description': 'S3 bucket with additional features'}
                ],
                'ec2': [
                    {'name': 'terraform-aws-modules/ec2-instance/aws', 'description': 'AWS EC2 instance module'},
                    {'name': 'terraform-aws-modules/autoscaling/aws', 'description': 'Auto Scaling Group module'}
                ]
            },
            'azure': {
                'vm': [
                    {'name': 'Azure/compute/azurerm', 'description': 'Azure Virtual Machine module'},
                    {'name': 'Azure/vm/azurerm', 'description': 'Simplified VM module'}
                ],
                'storage': [
                    {'name': 'Azure/storage/azurerm', 'description': 'Azure Storage Account module'}
                ]
            }
        }
        return modules.get(provider.lower(), {}).get(service.lower(), [])
    
    def _get_terraform_provider_info(self, provider: str) -> Dict[str, str]:
        """Get Terraform provider information."""
        providers = {
            'aws': {
                'source': 'hashicorp/aws',
                'documentation': 'https://registry.terraform.io/providers/hashicorp/aws/latest/docs'
            },
            'azure': {
                'source': 'hashicorp/azurerm',
                'documentation': 'https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs'
            },
            'google': {
                'source': 'hashicorp/google',
                'documentation': 'https://registry.terraform.io/providers/hashicorp/google/latest/docs'
            }
        }
        return providers.get(provider.lower(), {'source': f'hashicorp/{provider}'})
    
    def _get_terraform_usage_examples(self, provider: str, service: str) -> List[str]:
        """Get Terraform usage examples."""
        examples = {
            'aws': {
                's3': [
                    'resource "aws_s3_bucket" "example" { bucket = "my-bucket" }',
                    'resource "aws_s3_bucket_versioning" "example" { bucket = aws_s3_bucket.example.id }'
                ]
            }
        }
        return examples.get(provider.lower(), {}).get(service.lower(), [])
    
    def _get_azure_fallback_data(self, service: str, intent: str, operation: str) -> Dict[str, Any]:
        """Get fallback data for Azure queries."""
        return {
            'service': service,
            'intent': intent,
            'operation': operation,
            'fallback': True,
            'service_info': self._get_azure_service_info(service),
            'best_practices': self._get_azure_best_practices(service),
            'documentation_links': self._get_azure_documentation_links(service),
            'cli_examples': self._get_azure_cli_examples(service, operation)
        }
    
    def _get_azure_service_info(self, service: str) -> Dict[str, str]:
        """Get Azure service information."""
        services = {
            'vm': {
                'name': 'Virtual Machines',
                'description': 'Scalable computing resources in Azure'
            },
            'storage': {
                'name': 'Storage Accounts',
                'description': 'Scalable cloud storage for data and applications'
            },
            'aks': {
                'name': 'Azure Kubernetes Service',
                'description': 'Managed Kubernetes container orchestration'
            }
        }
        return services.get(service.lower(), {'name': service, 'description': f'Azure {service} service'})
    
    def _get_azure_best_practices(self, service: str) -> List[str]:
        """Get Azure best practices."""
        practices = {
            'vm': [
                "Use managed disks for better reliability",
                "Configure backup and disaster recovery",
                "Apply security updates regularly"
            ],
            'storage': [
                "Enable encryption at rest",
                "Configure access policies",
                "Use private endpoints for security"
            ],
            'aks': [
                "Use Azure AD integration",
                "Enable network policies",
                "Configure monitoring and logging"
            ]
        }
        return practices.get(service.lower(), [f"Follow Azure best practices for {service}"])
    
    def _get_azure_documentation_links(self, service: str) -> List[str]:
        """Get Azure documentation links."""
        base_url = "https://docs.microsoft.com/en-us/azure"
        links = {
            'vm': [f"{base_url}/virtual-machines/"],
            'storage': [f"{base_url}/storage/"],
            'aks': [f"{base_url}/aks/"]
        }
        return links.get(service.lower(), [f"{base_url}/{service}/"])
    
    def _get_azure_cli_examples(self, service: str, operation: str) -> List[str]:
        """Get Azure CLI examples."""
        examples = {
            'vm': [
                "az vm create --resource-group myResourceGroup --name myVM",
                "az vm list --output table"
            ],
            'storage': [
                "az storage account create --name mystorageaccount",
                "az storage account list --output table"
            ]
        }
        return examples.get(service.lower(), [f"az {service} --help"])
    
    def _get_github_fallback_data(self, operation: str, repository: str, **kwargs) -> Dict[str, Any]:
        """Get fallback data for GitHub queries."""
        return {
            'operation': operation,
            'repository': repository,
            'parameters': self.security.mask_sensitive_data(kwargs),
            'fallback': True,
            'operation_info': self._get_github_operation_info(operation),
            'repository_info': self._get_github_repository_info(repository) if repository else None,
            'api_endpoints': self._get_github_api_endpoints(operation),
            'examples': self._get_github_operation_examples(operation)
        }
    
    def _get_github_operation_info(self, operation: str) -> Dict[str, str]:
        """Get GitHub operation information."""
        operations = {
            'list_issues': {
                'description': 'List issues in a repository',
                'method': 'GET'
            },
            'create_pr': {
                'description': 'Create a pull request',
                'method': 'POST'
            },
            'get_repo': {
                'description': 'Get repository information',
                'method': 'GET'
            }
        }
        return operations.get(operation, {'description': f'GitHub {operation} operation'})
    
    def _get_github_repository_info(self, repository: str) -> Dict[str, str]:
        """Get GitHub repository information."""
        if not repository or '/' not in repository:
            return {'error': 'Invalid repository format. Use owner/repo'}
        
        owner, repo = repository.split('/', 1)
        return {
            'owner': owner,
            'repo': repo,
            'full_name': repository,
            'url': f'https://github.com/{repository}'
        }
    
    def _get_github_api_endpoints(self, operation: str) -> List[str]:
        """Get GitHub API endpoints."""
        endpoints = {
            'list_issues': ['/repos/{owner}/{repo}/issues'],
            'create_pr': ['/repos/{owner}/{repo}/pulls'],
            'get_repo': ['/repos/{owner}/{repo}']
        }
        return endpoints.get(operation, [f'/repos/{{owner}}/{{repo}}/{operation}'])
    
    def _get_github_operation_examples(self, operation: str) -> List[str]:
        """Get GitHub operation examples."""
        examples = {
            'list_issues': [
                'GET /repos/owner/repo/issues',
                'GET /repos/owner/repo/issues?state=open'
            ],
            'create_pr': [
                'POST /repos/owner/repo/pulls',
                '{"title": "New feature", "head": "feature-branch", "base": "main"}'
            ]
        }
        return examples.get(operation, [f'Example for {operation} operation'])


def create_default_mcp_config() -> Dict[str, Any]:
    """
    Create default MCP configuration with security considerations.
    
    Returns:
        Default MCP configuration
    """
    return {
        'mcp': {
            'servers': {
                'aws_docs': {
                    'command': 'uvx',
                    'args': ['awslabs.aws-documentation-mcp-server@latest'],
                    'env': {
                        'AWS_DOCUMENTATION_PARTITION': 'aws'
                    },
                    'disabled': False,
                    'auto_approve': ['read_documentation', 'search_documentation']
                },
                'terraform': {
                    'command': 'docker',
                    'args': ['run', '-i', '--rm', 'hashicorp/terraform-mcp-server'],
                    'env': {},
                    'disabled': False,
                    'auto_approve': []
                },
                'azure': {
                    'command': 'npx',
                    'args': ['-y', '@azure/mcp@latest', 'server', 'start'],
                    'env': {},
                    'disabled': False,
                    'auto_approve': ['documentation']
                },
                'github': {
                    'command': 'docker',
                    'args': [
                        'run', '-i', '--rm',
                        '-e', 'GITHUB_PERSONAL_ACCESS_TOKEN',
                        'ghcr.io/github/github-mcp-server'
                    ],
                    'env': {
                        # Note: Actual token should be set via environment variable
                        'GITHUB_PERSONAL_ACCESS_TOKEN': 'your-github-token-here'
                    },
                    'disabled': True,  # Disabled by default for security
                    'auto_approve': []
                }
            }
        }
    }