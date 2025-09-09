"""
Configuration management CLI commands.

This module provides CLI commands for configuration management, migration,
and validation.
"""

import argparse
import os
import sys
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from ..config.manager import ConfigManager
from ..config.security import SecurityManager
from ..config.migration import MigrationManager
from ..core.logging import ICLogger


class ConfigCommands:
    """Configuration management commands."""
    
    def __init__(self):
        self.console = Console()
        self.security_manager = SecurityManager()
        self.config_manager = ConfigManager(security_manager=self.security_manager)
        self.migration = MigrationManager()
    
    def add_subparsers(self, parent_parser: argparse.ArgumentParser) -> None:
        """
        Add config subcommands to parent parser.
        
        Args:
            parent_parser: Parent argument parser
        """
        config_parser = parent_parser.add_parser(
            "config", 
            help="Configuration management commands"
        )
        config_subparsers = config_parser.add_subparsers(
            dest="config_command",
            required=True,
            help="Configuration management operations"
        )
        
        # ic config init
        init_parser = config_subparsers.add_parser(
            "init",
            help="Initialize secure configuration setup"
        )
        init_parser.add_argument(
            "--output", "-o",
            default="ic.yaml",
            help="Output configuration file path (default: ic.yaml)"
        )
        init_parser.add_argument(
            "--template", "-t",
            choices=["minimal", "full", "aws", "azure", "gcp", "multi-cloud"],
            default="minimal",
            help="Configuration template to use (default: minimal)"
        )
        init_parser.add_argument(
            "--force", "-f",
            action="store_true",
            help="Overwrite existing configuration file"
        )
        init_parser.set_defaults(func=self.init_config)
        
        # ic config migrate
        migrate_parser = config_subparsers.add_parser(
            "migrate",
            help="Migrate from .env to YAML configuration"
        )
        migrate_parser.add_argument(
            "--env-file",
            default=".env",
            help="Source .env file path (default: .env)"
        )
        migrate_parser.add_argument(
            "--output", "-o",
            default="ic.yaml",
            help="Output YAML configuration file (default: ic.yaml)"
        )
        migrate_parser.add_argument(
            "--backup", "-b",
            action="store_true",
            default=True,
            help="Create backup of existing files (default: True)"
        )
        migrate_parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="Show what would be migrated without making changes"
        )
        migrate_parser.set_defaults(func=self.migrate_config)
        
        # ic config validate
        validate_parser = config_subparsers.add_parser(
            "validate",
            help="Validate configuration files"
        )
        validate_parser.add_argument(
            "config_file",
            nargs="?",
            help="Configuration file to validate (default: auto-detect)"
        )
        validate_parser.add_argument(
            "--security", "-s",
            action="store_true",
            help="Include security validation"
        )
        validate_parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Show detailed validation results"
        )
        validate_parser.set_defaults(func=self.validate_config)
        
        # ic config show
        show_parser = config_subparsers.add_parser(
            "show",
            help="Show current configuration"
        )
        show_parser.add_argument(
            "--sources", "-s",
            action="store_true",
            help="Show configuration sources"
        )
        show_parser.add_argument(
            "--mask-sensitive", "-m",
            action="store_true",
            default=True,
            help="Mask sensitive data in output (default: True)"
        )
        show_parser.add_argument(
            "--format", "-f",
            choices=["yaml", "json", "table"],
            default="yaml",
            help="Output format (default: yaml)"
        )
        show_parser.add_argument(
            "--aws",
            action="store_true",
            help="Show only AWS-related configuration settings"
        )
        show_parser.add_argument(
            "key_path",
            nargs="?",
            help="Specific configuration key to show (dot notation, e.g., aws.regions)"
        )
        show_parser.set_defaults(func=self.show_config)
        
        # ic config set
        set_parser = config_subparsers.add_parser(
            "set",
            help="Set configuration value"
        )
        set_parser.add_argument(
            "key_path",
            help="Configuration key to set (dot notation, e.g., aws.regions)"
        )
        set_parser.add_argument(
            "value",
            help="Value to set (JSON format for complex values)"
        )
        set_parser.add_argument(
            "--config-file", "-c",
            default="ic.yaml",
            help="Configuration file to update (default: ic.yaml)"
        )
        set_parser.add_argument(
            "--create", 
            action="store_true",
            help="Create configuration file if it doesn't exist"
        )
        set_parser.set_defaults(func=self.set_config)
        
        # ic config get
        get_parser = config_subparsers.add_parser(
            "get",
            help="Get configuration value"
        )
        get_parser.add_argument(
            "key_path",
            help="Configuration key to get (dot notation, e.g., aws.regions)"
        )
        get_parser.add_argument(
            "--default", "-d",
            help="Default value if key not found"
        )
        get_parser.add_argument(
            "--format", "-f",
            choices=["raw", "json", "yaml"],
            default="raw",
            help="Output format (default: raw)"
        )
        get_parser.set_defaults(func=self.get_config)
    
    def init_config(self, args) -> None:
        """
        Initialize secure configuration setup.
        
        Args:
            args: Command line arguments
        """
        output_path = Path(args.output)
        
        # Check if file exists and not forcing
        if output_path.exists() and not args.force:
            if not Confirm.ask(f"Configuration file {output_path} already exists. Overwrite?"):
                self.console.print("❌ Configuration initialization cancelled.")
                return
        
        self.console.print(f"🚀 Initializing IC configuration with template: {args.template}")
        
        # Get template configuration
        template_config = self._get_template_config(args.template)
        
        # Interactive configuration if not minimal
        if args.template != "minimal":
            template_config = self._interactive_config_setup(template_config, args.template)
        
        try:
            # Save configuration
            self.config_manager.save_config(output_path, template_config)
            
            # Create .env.example if it doesn't exist
            env_example_path = Path(".env.example")
            if not env_example_path.exists():
                self._create_env_example(env_example_path, args.template)
            
            # Update .gitignore
            self._update_gitignore()
            
            self.console.print(Panel(
                f"✅ Configuration initialized successfully!\n\n"
                f"📁 Configuration file: {output_path}\n"
                f"📄 Environment example: .env.example\n"
                f"🔒 .gitignore updated for security\n\n"
                f"Next steps:\n"
                f"1. Review and customize {output_path}\n"
                f"2. Set up environment variables (see .env.example)\n"
                f"3. Run 'ic config validate' to verify setup",
                title="Configuration Initialized",
                border_style="green"
            ))
            
        except Exception as e:
            self.console.print(f"❌ Failed to initialize configuration: {e}")
            sys.exit(1)
    
    def migrate_config(self, args) -> None:
        """
        Migrate from .env to YAML configuration.
        
        Args:
            args: Command line arguments
        """
        env_file = Path(args.env_file)
        output_file = Path(args.output)
        
        if not env_file.exists():
            self.console.print(f"❌ Environment file {env_file} not found.")
            sys.exit(1)
        
        self.console.print(f"🔄 Migrating configuration from {env_file} to {output_file}")
        
        try:
            # Perform migration
            if args.dry_run:
                self.console.print("🔍 Dry run - showing what would be migrated:")
                # TODO: Implement dry run preview
                result = {"success": True, "dry_run": True}
            else:
                success = self.migration.migrate_env_to_yaml(str(env_file), force=True)
                result = {"success": success, "output_file": str(output_file)}
            
            if args.dry_run:
                self.console.print("🔍 Dry run - showing what would be migrated:")
                self._display_migration_preview(result)
            else:
                self._display_migration_result(result)
                
        except Exception as e:
            self.console.print(f"❌ Migration failed: {e}")
            sys.exit(1)
    
    def validate_config(self, args) -> None:
        """
        Validate configuration files.
        
        Args:
            args: Command line arguments
        """
        if args.config_file:
            config_file = Path(args.config_file)
            if not config_file.exists():
                self.console.print(f"❌ Configuration file {config_file} not found.")
                sys.exit(1)
            config_files = [config_file]
        else:
            # Auto-detect configuration files
            config_files = self._find_config_files()
        
        if not config_files:
            self.console.print("❌ No configuration files found.")
            sys.exit(1)
        
        self.console.print("🔍 Validating configuration files...")
        
        all_valid = True
        for config_file in config_files:
            self.console.print(f"\n📄 Validating {config_file}:")
            
            try:
                # Load and validate configuration
                config_data = self.config_manager._load_config_file(config_file)
                errors = self.config_manager.validate_config(config_data)
                
                # Security validation if requested
                security_warnings = []
                if args.security:
                    security_warnings = self.security_manager.validate_config_security(config_data)
                
                # Display results
                if not errors and not security_warnings:
                    self.console.print("  ✅ Configuration is valid")
                else:
                    all_valid = False
                    
                    if errors:
                        self.console.print("  ❌ Validation errors:")
                        for error in errors:
                            self.console.print(f"    • {error}")
                    
                    if security_warnings:
                        self.console.print("  ⚠️  Security warnings:")
                        for warning in security_warnings:
                            self.console.print(f"    • {warning}")
                
                if args.verbose:
                    self._display_config_summary(config_data)
                    
            except Exception as e:
                all_valid = False
                self.console.print(f"  ❌ Failed to validate: {e}")
        
        if all_valid:
            self.console.print("\n✅ All configuration files are valid!")
        else:
            self.console.print("\n❌ Some configuration files have issues.")
            sys.exit(1)
    
    def show_config(self, args) -> None:
        """
        Show current configuration.
        
        Args:
            args: Command line arguments
        """
        try:
            # Load configuration with enhanced error handling
            config = self._load_config_with_validation()
            
            # Mask sensitive data if requested
            if args.mask_sensitive:
                config = self.security_manager.mask_sensitive_data(config)
            
            # Filter AWS configuration if requested
            if args.aws:
                config = self._filter_aws_config(config)
                # Use AWS-specific display for better formatting
                if args.format == "table":
                    self._display_aws_config(config)
                    return
            
            # Show specific key if requested
            if args.key_path:
                value = self.config_manager.get_config_value(args.key_path)
                if value is None:
                    self.console.print(f"❌ Configuration key '{args.key_path}' not found.")
                    self._suggest_similar_keys(args.key_path)
                    sys.exit(1)
                config = {args.key_path: value}
            
            # Display configuration
            if args.format == "json":
                self.console.print(json.dumps(config, indent=2))
            elif args.format == "yaml":
                yaml_output = yaml.dump(config, default_flow_style=False, indent=2)
                syntax = Syntax(yaml_output, "yaml", theme="monokai", line_numbers=True)
                self.console.print(syntax)
            elif args.format == "table":
                self._display_config_table(config)
            
            # Show sources if requested
            if args.sources:
                sources = self.config_manager.get_config_sources()
                self.console.print(f"\n📋 Configuration sources: {', '.join(sources)}")
                
        except FileNotFoundError as e:
            self._handle_missing_config_error(e)
        except yaml.YAMLError as e:
            self._handle_yaml_error(e)
        except PermissionError as e:
            self._handle_permission_error(e)
        except Exception as e:
            self.console.print(f"❌ Failed to show configuration: {e}")
            self._suggest_config_troubleshooting()
            sys.exit(1)
    
    def set_config(self, args) -> None:
        """
        Set configuration value.
        
        Args:
            args: Command line arguments
        """
        config_file = Path(args.config_file)
        
        # Create config file if requested and doesn't exist
        if not config_file.exists():
            if args.create:
                config_data = self.config_manager._get_default_config()
            else:
                self.console.print(f"❌ Configuration file {config_file} not found. Use --create to create it.")
                sys.exit(1)
        else:
            config_data = self.config_manager._load_config_file(config_file)
        
        # Parse value (try JSON first, then string)
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        
        # Set the value
        keys = args.key_path.split('.')
        current = config_data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        
        try:
            # Save configuration
            self.config_manager.safe_update_config(config_file, config_data)
            self.console.print(f"✅ Configuration updated: {args.key_path} = {value}")
            
        except Exception as e:
            self.console.print(f"❌ Failed to update configuration: {e}")
            sys.exit(1)
    
    def get_config(self, args) -> None:
        """
        Get configuration value.
        
        Args:
            args: Command line arguments
        """
        try:
            # Load configuration
            self.config_manager.load_config()
            
            # Get value
            value = self.config_manager.get_config_value(args.key_path, args.default)
            
            if value is None:
                self.console.print(f"❌ Configuration key '{args.key_path}' not found.")
                sys.exit(1)
            
            # Format output
            if args.format == "json":
                self.console.print(json.dumps(value, indent=2))
            elif args.format == "yaml":
                yaml_output = yaml.dump({args.key_path: value}, default_flow_style=False)
                self.console.print(yaml_output.strip())
            else:
                self.console.print(str(value))
                
        except Exception as e:
            self.console.print(f"❌ Failed to get configuration: {e}")
            sys.exit(1)
    
    def _get_template_config(self, template: str) -> Dict[str, Any]:
        """Get configuration template."""
        base_config = self.config_manager._get_default_config()
        
        if template == "minimal":
            return {
                "version": base_config["version"],
                "logging": base_config["logging"],
                "security": base_config["security"],
            }
        elif template == "aws":
            return {
                "version": base_config["version"],
                "logging": base_config["logging"],
                "aws": base_config["aws"],
                "security": base_config["security"],
            }
        elif template == "azure":
            return {
                "version": base_config["version"],
                "logging": base_config["logging"],
                "azure": base_config["azure"],
                "security": base_config["security"],
            }
        elif template == "gcp":
            return {
                "version": base_config["version"],
                "logging": base_config["logging"],
                "gcp": base_config["gcp"],
                "security": base_config["security"],
            }
        elif template == "multi-cloud":
            return base_config
        else:
            return base_config
    
    def _interactive_config_setup(self, config: Dict[str, Any], template: str) -> Dict[str, Any]:
        """Interactive configuration setup."""
        self.console.print(f"\n🔧 Interactive setup for {template} template:")
        
        if template in ["aws", "multi-cloud"]:
            accounts = Prompt.ask("AWS Account IDs (comma-separated)", default="")
            if accounts:
                config["aws"]["accounts"] = [acc.strip() for acc in accounts.split(",")]
            
            regions = Prompt.ask("AWS Regions (comma-separated)", default="ap-northeast-2")
            config["aws"]["regions"] = [reg.strip() for reg in regions.split(",")]
        
        if template in ["azure", "multi-cloud"]:
            subscription_id = Prompt.ask("Azure Subscription ID", default="")
            if subscription_id:
                config["azure"]["subscription_id"] = subscription_id
        
        if template in ["gcp", "multi-cloud"]:
            project_id = Prompt.ask("GCP Project ID", default="")
            if project_id:
                config["gcp"]["project_id"] = project_id
        
        return config
    
    def _create_env_example(self, env_example_path: Path, template: str) -> None:
        """Create .env.example file."""
        env_content = [
            "# IC Configuration Environment Variables",
            "# Copy this file to .env and fill in your actual values",
            "# DO NOT commit .env to version control!",
            "",
            "# Logging Configuration",
            "# IC_LOG_LEVEL=ERROR",
            "# IC_LOG_FILE_LEVEL=INFO",
            "",
        ]
        
        if template in ["aws", "multi-cloud"]:
            env_content.extend([
                "# AWS Configuration",
                "# AWS_PROFILE=your-profile-name",
                "# AWS_ACCOUNTS=123456789012,987654321098",
                "# AWS_REGIONS=ap-northeast-2,us-east-1",
                "# AWS_CROSS_ACCOUNT_ROLE=OrganizationAccountAccessRole",
                "",
            ])
        
        if template in ["azure", "multi-cloud"]:
            env_content.extend([
                "# Azure Configuration",
                "# AZURE_SUBSCRIPTION_ID=your-subscription-id",
                "# AZURE_TENANT_ID=your-tenant-id",
                "# AZURE_CLIENT_ID=your-client-id",
                "# AZURE_CLIENT_SECRET=your-client-secret",
                "",
            ])
        
        if template in ["gcp", "multi-cloud"]:
            env_content.extend([
                "# GCP Configuration",
                "# GCP_PROJECT_ID=your-project-id",
                "# GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json",
                "# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json",
                "",
            ])
        
        env_content.extend([
            "# Optional: Slack Integration",
            "# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...",
            "",
            "# Optional: MCP GitHub Integration",
            "# MCP_GITHUB_TOKEN=your-github-token",
        ])
        
        with open(env_example_path, 'w') as f:
            f.write('\n'.join(env_content))
    
    def _update_gitignore(self) -> None:
        """Update .gitignore with security entries."""
        gitignore_path = Path(".gitignore")
        security_entries = self.security_manager.create_gitignore_entries()
        
        existing_content = ""
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                existing_content = f.read()
        
        # Add security entries if not already present
        new_entries = []
        for entry in security_entries:
            if entry not in existing_content:
                new_entries.append(entry)
        
        if new_entries:
            with open(gitignore_path, 'a') as f:
                if existing_content and not existing_content.endswith('\n'):
                    f.write('\n')
                f.write('\n'.join(new_entries) + '\n')
    
    def _find_config_files(self) -> List[Path]:
        """Find configuration files in common locations."""
        config_files = []
        
        # Check common config file locations
        possible_paths = [
            Path("ic.yaml"),
            Path("ic.yml"),
            Path(".ic/config.yaml"),
            Path(".ic/config.yml"),
            Path("config/config.yaml"),
            Path("config/config.yml"),
            Path.home() / ".ic" / "config.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                config_files.append(path)
        
        return config_files
    
    def _display_migration_preview(self, result: Dict[str, Any]) -> None:
        """Display migration preview."""
        if result.get("config_data"):
            self.console.print("📋 Configuration that would be created:")
            yaml_output = yaml.dump(result["config_data"], default_flow_style=False, indent=2)
            syntax = Syntax(yaml_output, "yaml", theme="monokai")
            self.console.print(syntax)
        
        if result.get("warnings"):
            self.console.print("\n⚠️  Warnings:")
            for warning in result["warnings"]:
                self.console.print(f"  • {warning}")
    
    def _display_migration_result(self, result: Dict[str, Any]) -> None:
        """Display migration result."""
        if result.get("success"):
            self.console.print(Panel(
                f"✅ Migration completed successfully!\n\n"
                f"📁 Configuration file: {result.get('output_file', 'ic.yaml')}\n"
                f"📄 Backup created: {result.get('backup_file', 'N/A')}\n\n"
                f"Next steps:\n"
                f"1. Review the generated configuration file\n"
                f"2. Remove sensitive data from the config file\n"
                f"3. Set up environment variables for secrets\n"
                f"4. Run 'ic config validate' to verify setup",
                title="Migration Complete",
                border_style="green"
            ))
        else:
            self.console.print(f"❌ Migration failed: {result.get('error', 'Unknown error')}")
        
        if result.get("warnings"):
            self.console.print("\n⚠️  Warnings:")
            for warning in result["warnings"]:
                self.console.print(f"  • {warning}")
    
    def _display_config_summary(self, config_data: Dict[str, Any]) -> None:
        """Display configuration summary."""
        table = Table(title="Configuration Summary")
        table.add_column("Section", style="cyan")
        table.add_column("Keys", style="green")
        table.add_column("Status", style="yellow")
        
        for section, data in config_data.items():
            if isinstance(data, dict):
                keys = list(data.keys())
                status = "✅ Configured" if keys else "⚠️  Empty"
                table.add_row(section, ", ".join(keys[:3]) + ("..." if len(keys) > 3 else ""), status)
        
        self.console.print(table)
    
    def _filter_aws_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter configuration to show only AWS-related settings.
        
        Args:
            config: Full configuration dictionary
            
        Returns:
            Dictionary containing only AWS-related configuration
        """
        aws_config = {}
        
        # Include AWS-specific sections
        aws_keys = ['aws', 'AWS']
        for key in aws_keys:
            if key in config:
                aws_config[key] = config[key]
        
        # Include environment variables that are AWS-related
        if 'environment' in config:
            aws_env = {}
            for env_key, env_value in config['environment'].items():
                if env_key.startswith(('AWS_', 'aws_')):
                    aws_env[env_key] = env_value
            if aws_env:
                aws_config['environment'] = aws_env
        
        # Include logging and security if they exist (common sections)
        for common_key in ['logging', 'security', 'version']:
            if common_key in config:
                aws_config[common_key] = config[common_key]
        
        return aws_config if aws_config else {"message": "No AWS configuration found"}
    
    def _display_aws_config(self, config: Dict[str, Any]) -> None:
        """
        Display AWS-specific configuration in table format.
        
        Args:
            config: AWS configuration dictionary
        """
        if not config or config.get("message") == "No AWS configuration found":
            self.console.print("📋 No AWS configuration found.")
            return
        
        table = Table(title="AWS Configuration")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_column("Source", style="yellow")
        
        def add_aws_rows(data: Dict[str, Any], prefix: str = "", source: str = "config"):
            for key, value in data.items():
                setting_name = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    add_aws_rows(value, setting_name, source)
                elif isinstance(value, list):
                    table.add_row(setting_name, f"[{len(value)} items: {', '.join(map(str, value[:3]))}{'...' if len(value) > 3 else ''}]", source)
                else:
                    # Mask sensitive AWS data
                    masked_value = self._mask_aws_credentials(str(value), key)
                    table.add_row(setting_name, masked_value, source)
        
        add_aws_rows(config)
        self.console.print(table)
    
    def _mask_aws_credentials(self, value: str, key: str) -> str:
        """
        Security masking for AWS credentials and sensitive data.
        
        Args:
            value: Configuration value to potentially mask
            key: Configuration key name
            
        Returns:
            Masked value if sensitive, original value otherwise
        """
        sensitive_keys = [
            'access_key', 'secret_key', 'session_token', 'password', 'token',
            'key', 'secret', 'credential', 'auth', 'api_key'
        ]
        
        # Check if key contains sensitive terms
        key_lower = key.lower()
        if any(sensitive_term in key_lower for sensitive_term in sensitive_keys):
            if len(value) > 8:
                return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
            else:
                return "*" * len(value)
        
        # Check for AWS access key pattern (AKIA...)
        if value.startswith('AKIA') and len(value) == 20:
            return f"AKIA{'*' * 12}{value[-4:]}"
        
        # Check for AWS secret key pattern (long base64-like string)
        if len(value) == 40 and value.isalnum():
            return f"{value[:8]}{'*' * 24}{value[-8:]}"
        
        return value
    
    def _load_config_with_validation(self) -> Dict[str, Any]:
        """
        Load configuration with enhanced validation and error handling.
        
        Returns:
            Validated configuration dictionary
            
        Raises:
            Various exceptions for different error conditions
        """
        try:
            # Load configuration
            config = self.config_manager.load_config()
            
            # Validate AWS-specific settings if present
            if 'aws' in config:
                self._validate_aws_config(config['aws'])
            
            return config
            
        except Exception as e:
            # Re-raise with more context
            raise e
    
    def _validate_aws_config(self, aws_config: Dict[str, Any]) -> None:
        """
        Validate AWS-specific configuration settings.
        
        Args:
            aws_config: AWS configuration dictionary
            
        Raises:
            ValueError: If AWS configuration is invalid
        """
        # Validate regions
        if 'regions' in aws_config:
            regions = aws_config['regions']
            if not isinstance(regions, list) or not regions:
                raise ValueError("AWS regions must be a non-empty list")
            
            # Check for valid region format
            valid_region_pattern = r'^[a-z]{2}-[a-z]+-\d+$'
            import re
            for region in regions:
                if not re.match(valid_region_pattern, region):
                    self.console.print(f"⚠️  Warning: '{region}' may not be a valid AWS region format")
        
        # Validate accounts
        if 'accounts' in aws_config:
            accounts = aws_config['accounts']
            if not isinstance(accounts, list):
                raise ValueError("AWS accounts must be a list")
            
            # Check for valid account ID format (12 digits)
            for account in accounts:
                if not isinstance(account, str) or not account.isdigit() or len(account) != 12:
                    raise ValueError(f"Invalid AWS account ID format: {account}. Must be 12 digits.")
    
    def _handle_missing_config_error(self, error: FileNotFoundError) -> None:
        """Handle missing configuration file errors."""
        self.console.print("❌ Configuration file not found.")
        self.console.print("\n💡 Suggestions:")
        self.console.print("  • Run 'ic config init' to create a new configuration")
        self.console.print("  • Check if you're in the correct directory")
        self.console.print("  • Verify configuration file permissions")
        sys.exit(1)
    
    def _handle_yaml_error(self, error: yaml.YAMLError) -> None:
        """Handle YAML parsing errors."""
        self.console.print(f"❌ Configuration file has invalid YAML syntax: {error}")
        self.console.print("\n💡 Suggestions:")
        self.console.print("  • Check for proper indentation (use spaces, not tabs)")
        self.console.print("  • Verify all quotes are properly closed")
        self.console.print("  • Run 'ic config validate' for detailed error information")
        sys.exit(1)
    
    def _handle_permission_error(self, error: PermissionError) -> None:
        """Handle file permission errors."""
        self.console.print(f"❌ Permission denied accessing configuration file: {error}")
        self.console.print("\n💡 Suggestions:")
        self.console.print("  • Check file permissions with 'ls -la'")
        self.console.print("  • Ensure you have read access to the configuration directory")
        self.console.print("  • Try running with appropriate permissions")
        sys.exit(1)
    
    def _suggest_similar_keys(self, key_path: str) -> None:
        """Suggest similar configuration keys when a key is not found."""
        try:
            config = self.config_manager.load_config()
            all_keys = self._get_all_config_keys(config)
            
            # Simple similarity check
            similar_keys = [k for k in all_keys if key_path.lower() in k.lower() or k.lower() in key_path.lower()]
            
            if similar_keys:
                self.console.print("\n💡 Did you mean one of these?")
                for key in similar_keys[:5]:  # Show max 5 suggestions
                    self.console.print(f"  • {key}")
        except:
            pass  # Ignore errors in suggestion generation
    
    def _get_all_config_keys(self, config: Dict[str, Any], prefix: str = "") -> List[str]:
        """Get all configuration keys in dot notation."""
        keys = []
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.append(full_key)
            if isinstance(value, dict):
                keys.extend(self._get_all_config_keys(value, full_key))
        return keys
    
    def _suggest_config_troubleshooting(self) -> None:
        """Provide general configuration troubleshooting suggestions."""
        self.console.print("\n🔧 Troubleshooting steps:")
        self.console.print("  1. Run 'ic config validate' to check for issues")
        self.console.print("  2. Verify configuration file exists and is readable")
        self.console.print("  3. Check YAML syntax with an online validator")
        self.console.print("  4. Review the documentation for configuration format")
        self.console.print("  5. Try 'ic config init' to create a fresh configuration")
    
    def _display_config_table(self, config: Dict[str, Any], prefix: str = "") -> None:
        """Display configuration as table."""
        table = Table(title="Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Type", style="yellow")
        
        def add_rows(data: Dict[str, Any], current_prefix: str = ""):
            for key, value in data.items():
                full_key = f"{current_prefix}.{key}" if current_prefix else key
                
                if isinstance(value, dict):
                    table.add_row(full_key, "[dict]", "object")
                    add_rows(value, full_key)
                elif isinstance(value, list):
                    table.add_row(full_key, f"[{len(value)} items]", "array")
                else:
                    table.add_row(full_key, str(value), type(value).__name__)
        
        add_rows(config)
        self.console.print(table)