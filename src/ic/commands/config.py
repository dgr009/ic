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
from typing import Dict, Any, Optional, List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from ..config.manager import ConfigManager
from ..config.security import SecurityManager
from ..config.migration import MigrationManager
from ..config.path_manager import ConfigPathManager
from ..config.migration_utils import ConfigMigrationUtils, create_migration_confirmation_callback
from ..core.logging import ICLogger


class ConfigCommands:
    """Configuration management commands."""
    
    def __init__(self):
        self.console = Console()
        self.security_manager = SecurityManager()
        self.config_manager = ConfigManager(security_manager=self.security_manager)
        self.migration = MigrationManager()
        self.path_manager = ConfigPathManager()
        self.migration_utils = ConfigMigrationUtils(self.path_manager)
    
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
            choices=["minimal", "full", "aws", "azure", "gcp", "ncp", "ncpgov", "multi-cloud"],
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
        Initialize secure configuration setup with hierarchical path management.
        
        Args:
            args: Command line arguments
        """
        self.console.print(f"🚀 Initializing IC configuration with template: {args.template}")
        
        # Check for existing project-level configs that need migration
        migration_info = self.migration_utils._analyze_migration_needs()
        
        if migration_info["needs_migration"]:
            self.console.print("\n📦 Found existing configuration folders that should be migrated:")
            for config in migration_info["project_configs"]:
                self.console.print(f"  • {config['name']}: {config['path']}")
            
            if Confirm.ask("Would you like to migrate these configurations to user home directory?"):
                # Perform migration with user confirmation
                confirm_func = create_migration_confirmation_callback(interactive=True)
                migration_results = self.migration_utils.interactive_migration(confirm_func)
                
                if migration_results["migrations_performed"]:
                    self.console.print(f"✅ Migrated configurations: {', '.join(migration_results['migrations_performed'])}")
                if migration_results["errors"]:
                    self.console.print(f"⚠️  Migration errors: {migration_results['errors']}")
        
        # Create default configuration structure using path manager
        try:
            created_paths = self.path_manager.create_default_config_structure()
            
            # Determine output paths based on new structure
            config_dir = self.path_manager.home_dir / ".ic" / "config"
            
            if args.output == "ic.yaml":  # Default case
                default_config_path = config_dir / "default.yaml"
                secrets_config_path = config_dir / "secrets.yaml"
                secrets_example_path = config_dir / "secrets.yaml.example"
            else:
                # Custom output path - use as specified but still in ~/.ic/config
                default_config_path = config_dir / args.output
                secrets_config_path = config_dir / f"secrets_{Path(args.output).stem}.yaml"
                secrets_example_path = config_dir / f"secrets_{Path(args.output).stem}.yaml.example"
            
            # Check if files exist and not forcing
            if (default_config_path.exists() or secrets_config_path.exists()) and not args.force:
                if not Confirm.ask(f"Configuration files already exist in {config_dir}. Overwrite?"):
                    self.console.print("❌ Configuration initialization cancelled.")
                    return
            
            # Get template configurations (separated into default and secrets)
            default_config, secrets_config, secrets_example = self._get_separated_template_config(args.template)
            
            # Interactive configuration if not minimal
            if args.template != "minimal":
                default_config, secrets_config, secrets_example = self._interactive_separated_config_setup(
                    default_config, secrets_config, secrets_example, args.template
                )
            
            # Save default configuration (non-sensitive)
            with open(default_config_path, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2, sort_keys=False)
            
            # Save secrets example file
            with open(secrets_example_path, 'w') as f:
                yaml.dump(secrets_example, f, default_flow_style=False, indent=2, sort_keys=False)
            
            # Create backup if secrets.yaml already exists
            backup_path = None
            if secrets_config_path.exists():
                backup_path = config_dir / f"secrets_backup_{int(Path().stat().st_mtime)}.yaml"
                secrets_config_path.rename(backup_path)
            
            # Update .gitignore
            self._update_gitignore()
            
            # Create NCP/NCPGOV configuration files if templates are used
            if args.template in ["ncp", "ncpgov", "multi-cloud", "full"]:
                self._create_platform_config_files(args.template, secrets_config)
            
            # Display success message with path information
            config_info = self.path_manager.get_config_sources_info()
            
            self.console.print(Panel(
                f"✅ Configuration initialized successfully!\n\n"
                f"📁 Default config: {default_config_path}\n"
                f"📄 Secrets example: {secrets_example_path}\n"
                f"🏠 NCP config: {self.path_manager.home_dir / '.ncp' / 'config.yaml'}\n"
                f"🏛️  NCPGOV config: {self.path_manager.home_dir / '.ncpgov' / 'config.yaml'}\n"
                f"🔒 .gitignore updated for security\n"
                f"{f'💾 Backup created: {backup_path}' if backup_path else ''}\n\n"
                f"Configuration hierarchy:\n"
                f"1. Project: ./.ic/config/\n"
                f"2. User home: ~/.ic/config/\n"
                f"3. Platform-specific: ~/.ncp/, ~/.ncpgov/\n\n"
                f"Next steps:\n"
                f"1. Copy secrets example to secrets.yaml: cp {secrets_example_path} {secrets_config_path}\n"
                f"2. Edit platform configs with your actual credentials\n"
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
                
                # Determine file type and validate accordingly
                is_secrets_file = 'secrets' in config_file.name
                is_default_file = 'default' in config_file.name
                
                if is_secrets_file:
                    # Secrets files only need basic structure validation
                    errors = self._validate_secrets_config(config_data)
                    # Also validate NCP credentials if present
                    ncp_errors = self._validate_ncp_credentials(config_data)
                    errors.extend(ncp_errors)
                elif is_default_file:
                    # Default files need full structure validation
                    errors = self._validate_default_config(config_data)
                else:
                    # Legacy files - use full validation
                    errors = self.config_manager.validate_config(config_data)
                
                # Security validation - always run but with different expectations
                security_warnings = []
                if args.security or not is_secrets_file:  # Always check security for non-secrets files
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
            # Load configuration
            self.config_manager.load_config()
            config = self.config_manager.get_config()
            
            # Also load secrets if available
            secrets_path = Path.home() / ".ic" / "config" / "secrets.yaml"
            if secrets_path.exists():
                try:
                    with open(secrets_path, 'r') as f:
                        secrets = yaml.safe_load(f) or {}
                    # Merge secrets into config for display
                    if 'secrets' not in config:
                        config['secrets'] = {}
                    config['secrets'].update(secrets)
                except Exception as e:
                    self.console.print(f"⚠️  Warning: Could not load secrets: {e}")
            
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
        elif template == "ncp":
            return {
                "version": base_config["version"],
                "logging": base_config["logging"],
                "ncp": base_config["ncp"],
                "security": base_config["security"],
            }
        elif template == "ncpgov":
            return {
                "version": base_config["version"],
                "logging": base_config["logging"],
                "ncpgov": base_config["ncpgov"],
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
        
        if template in ["ncp", "multi-cloud"]:
            regions = Prompt.ask("NCP Regions (comma-separated)", default="KR")
            config["ncp"]["regions"] = [reg.strip() for reg in regions.split(",")]
        
        if template in ["ncpgov", "multi-cloud"]:
            regions = Prompt.ask("NCP Gov Regions (comma-separated)", default="KR")
            config["ncpgov"]["regions"] = [reg.strip() for reg in regions.split(",")]
        
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
            # New standard locations
            Path.home() / ".ic" / "config" / "default.yaml",
            Path.home() / ".ic" / "config" / "secrets.yaml",
            # Legacy locations for backward compatibility
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
    
    def _display_config_table(self, config: Dict[str, Any]) -> None:
        """Display configuration in table format."""
        table = Table(title="Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Type", style="yellow")
        
        def add_rows(data: Dict[str, Any], prefix: str = ""):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    add_rows(value, full_key)
                elif isinstance(value, list):
                    table.add_row(full_key, f"[{len(value)} items]", "list")
                else:
                    table.add_row(full_key, str(value), type(value).__name__)
        
        add_rows(config)
        self.console.print(table)
    
    def _suggest_similar_keys(self, key_path: str) -> None:
        """Suggest similar configuration keys."""
        try:
            config = self.config_manager.get_config()
            all_keys = self._get_all_keys(config)
            
            # Simple similarity check
            similar_keys = [k for k in all_keys if key_path.lower() in k.lower() or k.lower() in key_path.lower()]
            
            if similar_keys:
                self.console.print("💡 Did you mean one of these?")
                for key in similar_keys[:5]:  # Show max 5 suggestions
                    self.console.print(f"  • {key}")
        except Exception as e:
            # Log error but don't fail the operation
            import logging
            logging.getLogger(__name__).debug(f"Error generating suggestions: {e}")
    
    def _get_all_keys(self, data: Dict[str, Any], prefix: str = "") -> List[str]:
        """Get all configuration keys recursively."""
        keys = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.append(full_key)
            if isinstance(value, dict):
                keys.extend(self._get_all_keys(value, full_key))
        return keys
    
    def _handle_missing_config_error(self, error: FileNotFoundError) -> None:
        """Handle missing configuration file error."""
        self.console.print("❌ Configuration file not found.")
        self.console.print("💡 Try running 'ic config init' to create a configuration file.")
        sys.exit(1)
    
    def _handle_yaml_error(self, error: yaml.YAMLError) -> None:
        """Handle YAML parsing error."""
        self.console.print(f"❌ Configuration file has invalid YAML syntax: {error}")
        self.console.print("💡 Check your configuration file for syntax errors.")
        sys.exit(1)
    
    def _handle_permission_error(self, error: PermissionError) -> None:
        """Handle permission error."""
        self.console.print(f"❌ Permission denied accessing configuration: {error}")
        self.console.print("💡 Check file permissions or run with appropriate privileges.")
        sys.exit(1)
    
    def _suggest_config_troubleshooting(self) -> None:
        """Suggest configuration troubleshooting steps."""
        self.console.print("\n💡 Troubleshooting suggestions:")
        self.console.print("  • Check if configuration files exist")
        self.console.print("  • Verify YAML syntax with 'ic config validate'")
        self.console.print("  • Run 'ic config init' to create a new configuration")
        self.console.print("  • Check file permissions")
        
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
        except Exception as e:
            # Log error but don't fail the operation
            import logging
            logging.getLogger(__name__).debug(f"Error generating suggestions: {e}")
    
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
    
    def _get_separated_template_config(self, template: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Get configuration template separated into default config, secrets config, and secrets example.
        Based on real production configuration files.
        
        Returns:
            Tuple of (default_config, secrets_config, secrets_example)
        """
        # Base default configuration (non-sensitive) - based on real config
        default_config = {
            "version": "2.0",
            "logging": {
                "console_level": "ERROR",
                "file_level": "INFO", 
                "file_path": "~/.ic/logs/ic_{date}.log",
                "max_files": 30,
                "format": "%(asctime)s [%(levelname)s] - %(message)s",
                "mask_sensitive": True
            },
            "security": {
                "sensitive_keys": [
                    "password", "passwd", "pwd", "token", "access_token", "refresh_token",
                    "auth_token", "key", "api_key", "access_key", "secret_key", "private_key",
                    "secret", "client_secret", "webhook_secret", "webhook_url", "webhook",
                    "credential", "credentials", "cert", "certificate", "session", "session_token"
                ],
                "mask_pattern": "***MASKED***",
                "warn_on_sensitive_in_config": True,
                "git_hooks_enabled": True
            }
        }
        
        # Base secrets configuration (sensitive data)
        secrets_config = {
            "version": "2.0"
        }
        
        # Base secrets example (template for users)
        secrets_example = {
            "version": "2.0"
        }
        
        if template in ["aws", "multi-cloud", "full"]:
            default_config["aws"] = {
                "config_path": "~/.aws/config",
                "credentials_path": "~/.aws/credentials",
                "regions": ["ap-northeast-2"],
                "cross_account_role": "OrganizationAccountAccessRole",
                "session_duration": 3600,
                "max_workers": 10,
                "tags": {
                    "required": [
                        "User", "CreateBy", "Team", "TeamName", "Name", 
                        "Service", "Application", "Role", "Environment"
                    ],
                    "optional": ["Env"],
                    "rules": {
                        "User": "^.+$",
                        "Team": "^\\d+$",
                        "Environment": "^(PROD|STG|DEV|TEST|QA)$",
                        "Name": "^[a-zA-Z0-9_.\\-/+() ]+$",
                        "Role": "^[a-zA-Z0-9_\\-+, ]+$"
                    }
                }
            }
            
            secrets_config["aws"] = {
                "accounts": [],
                "regions": ["ap-northeast-2"]
            }
            
            secrets_example["aws"] = {
                "accounts": ["00000000000"],
                "regions": ["ap-northeast-2"]
            }
        
        if template in ["azure", "multi-cloud", "full"]:
            default_config["azure"] = {
                "subscriptions": [],
                "locations": [
                    "East US", "West US 2", "Korea Central", "Southeast Asia"
                ],
                "max_workers": 10
            }
            
            secrets_config["azure"] = {
                "tenant_id": "",
                "client_id": "",
                "client_secret": ""
            }
            
            secrets_example["azure"] = {
                "tenant_id": "your-tenant-id",
                "client_id": "your-client-id", 
                "client_secret": "your-client-secret"
            }
        
        if template in ["gcp", "multi-cloud", "full"]:
            default_config["gcp"] = {
                "mcp": {
                    "enabled": True,
                    "endpoint": "http://localhost:8080/gcp",
                    "auth_method": "service_account",
                    "prefer_mcp": True
                },
                "projects": [],
                "regions": ["asia-northeast3"],
                "zones": [
                    "asia-northeast3-a", "asia-northeast3-b", "asia-northeast3-c"
                ],
                "max_workers": 10
            }
            
            secrets_config["gcp"] = {
                "service_account_key_path": ""
            }
            
            secrets_example["gcp"] = {
                "service_account_key_path": "~/gcp-key/cruiser_gcp.json"
            }
        
        if template in ["oci", "multi-cloud", "full"]:
            default_config["oci"] = {
                "config_path": "~/.oci/config",
                "max_workers": 10
            }
            
            # OCI doesn't typically have secrets in the secrets file
            # as it uses the ~/.oci/config file for credentials
        
        if template in ["ncp", "multi-cloud", "full"]:
            default_config["ncp"] = {
                "config_path": "~/.ncp/config",
                "regions": ["KR"],
                "max_workers": 10
            }
            
            secrets_config["ncp"] = {
                "access_key": "",
                "secret_key": ""
            }
            
            secrets_example["ncp"] = {
                "access_key": "your-ncp-access-key",
                "secret_key": "your-ncp-secret-key"
            }
        
        if template in ["ncpgov", "multi-cloud", "full"]:
            default_config["ncpgov"] = {
                "config_path": "~/.ncpgov/config",
                "regions": ["KR"],
                "max_workers": 10,
                "security": {
                    "encryption_enabled": True,
                    "audit_logging_enabled": True,
                    "access_control_enabled": True
                }
            }
            
            secrets_config["ncpgov"] = {
                "access_key": "",
                "secret_key": ""
            }
            
            secrets_example["ncpgov"] = {
                "access_key": "your-ncpgov-access-key",
                "secret_key": "your-ncpgov-secret-key"
            }
        
        if template in ["cloudflare", "multi-cloud", "full"]:
            default_config["cloudflare"] = {
                "config_path": "~/.cloudflare/config",
                "accounts": [],
                "zones": []
            }
            
            secrets_config["cloudflare"] = {
                "email": "",
                "api_token": "",
                "zone_id": "",
                "cloudflare_accounts": "",
                "cloudflare_zones": ""
            }
            
            secrets_example["cloudflare"] = {
                "email": "",
                "api_token": "",
                "zone_id": "",
                "cloudflare_accounts": "",
                "cloudflare_zones": ""
            }
        
        if template in ["ssh", "multi-cloud", "full"]:
            default_config["ssh"] = {
                "config_file": "~/.ssh/config",
                "workers": 70,
                "timeout": 5,
                "port_timeout": 0.5,
                "network_ranges": [
                    "192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"
                ],
                "default_user": "ubuntu",
                "port": 22
            }
            
            secrets_config["ssh"] = {
                "key_dir": "",
                "skip_prefixes": []
            }
            
            secrets_example["ssh"] = {
                "key_dir": "~/.ssh",
                "skip_prefixes": [
                    "git", "prod"
                ]
            }
        
        # Add MCP configuration for full template
        if template in ["multi-cloud", "full"]:
            default_config["mcp"] = {
                "servers": {
                    "github": {
                        "enabled": True,
                        "auto_approve": []
                    },
                    "terraform": {
                        "enabled": True,
                        "auto_approve": []
                    },
                    "aws_docs": {
                        "enabled": True,
                        "auto_approve": ["read_documentation", "search_documentation"]
                    },
                    "azure": {
                        "enabled": True,
                        "auto_approve": ["documentation"]
                    },
                    "slack": {
                        "enabled": False
                    }
                }
            }
            
            # Add Slack webhook to secrets
            secrets_config["slack"] = {
                "webhook_url": ""
            }
            
            secrets_example["slack"] = {
                "webhook_url": "https://hooks.slack.com/services/web-hook"
            }
            
            # Add other configuration section
            default_config["other"] = {
                "azure_subscriptions": "subscription-id-1,subscription-id-2",
                "mcp_gcp_enabled": "true",
                "mcp_gcp_endpoint": "http://localhost:8080/gcp",
                "mcp_gcp_auth_method": "service_account",
                "gcp_prefer_mcp": "true",
                "gcp_projects": "infracli",
                "gcp_default_project": "infracli",
                "gcp_request_timeout": "30",
                "gcp_retry_attempts": "3",
                "gcp_enable_billing_api": "true",
                "gcp_enable_compute_api": "true",
                "gcp_enable_container_api": "true",
                "gcp_enable_storage_api": "true",
                "gcp_enable_sqladmin_api": "true",
                "gcp_enable_cloudfunctions_api": "true",
                "gcp_enable_run_api": "true"
            }
        
        return default_config, secrets_config, secrets_example
    
    def _interactive_separated_config_setup(self, default_config: Dict[str, Any], 
                                          secrets_config: Dict[str, Any], 
                                          secrets_example: Dict[str, Any], 
                                          template: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Interactive configuration setup for separated configs based on real production config."""
        self.console.print(f"\n🔧 Interactive setup for {template} template:")
        
        if template in ["aws", "multi-cloud", "full"]:
            accounts = Prompt.ask("AWS Account IDs (comma-separated)", default="")
            if accounts:
                account_list = [acc.strip() for acc in accounts.split(",")]
                secrets_config["aws"]["accounts"] = account_list
                secrets_example["aws"]["accounts"] = account_list
            
            regions = Prompt.ask("AWS Regions (comma-separated)", default="ap-northeast-2")
            region_list = [reg.strip() for reg in regions.split(",")]
            default_config["aws"]["regions"] = region_list
            secrets_config["aws"]["regions"] = region_list
            secrets_example["aws"]["regions"] = region_list
        
        if template in ["azure", "multi-cloud", "full"]:
            tenant_id = Prompt.ask("Azure Tenant ID", default="")
            if tenant_id:
                secrets_config["azure"]["tenant_id"] = tenant_id
                secrets_example["azure"]["tenant_id"] = tenant_id
            
            client_id = Prompt.ask("Azure Client ID", default="")
            if client_id:
                secrets_config["azure"]["client_id"] = client_id
                secrets_example["azure"]["client_id"] = client_id
        
        if template in ["gcp", "multi-cloud", "full"]:
            service_account_path = Prompt.ask("GCP Service Account Key Path", default="~/gcp-key/service-account.json")
            if service_account_path:
                secrets_config["gcp"]["service_account_key_path"] = service_account_path
                secrets_example["gcp"]["service_account_key_path"] = service_account_path
        
        if template in ["cloudflare", "multi-cloud", "full"]:
            cf_email = Prompt.ask("CloudFlare Email", default="")
            if cf_email:
                secrets_config["cloudflare"]["email"] = cf_email
                secrets_example["cloudflare"]["email"] = cf_email
            
            cf_accounts = Prompt.ask("CloudFlare Accounts (comma-separated)", default="")
            if cf_accounts:
                secrets_config["cloudflare"]["cloudflare_accounts"] = cf_accounts
                secrets_example["cloudflare"]["cloudflare_accounts"] = cf_accounts
            
            cf_zones = Prompt.ask("CloudFlare Zones (comma-separated)", default="")
            if cf_zones:
                secrets_config["cloudflare"]["cloudflare_zones"] = cf_zones
                secrets_example["cloudflare"]["cloudflare_zones"] = cf_zones
        
        if template in ["ncp", "multi-cloud", "full"]:
            ncp_access_key = Prompt.ask("NCP Access Key", default="")
            if ncp_access_key:
                secrets_config["ncp"]["access_key"] = ncp_access_key
                secrets_example["ncp"]["access_key"] = ncp_access_key
            
            ncp_secret_key = Prompt.ask("NCP Secret Key", default="")
            if ncp_secret_key:
                secrets_config["ncp"]["secret_key"] = ncp_secret_key
                secrets_example["ncp"]["secret_key"] = ncp_secret_key
        
        if template in ["ncpgov", "multi-cloud", "full"]:
            ncpgov_access_key = Prompt.ask("NCP Gov Access Key", default="")
            if ncpgov_access_key:
                secrets_config["ncpgov"]["access_key"] = ncpgov_access_key
                secrets_example["ncpgov"]["access_key"] = ncpgov_access_key
            
            ncpgov_secret_key = Prompt.ask("NCP Gov Secret Key", default="")
            if ncpgov_secret_key:
                secrets_config["ncpgov"]["secret_key"] = ncpgov_secret_key
                secrets_example["ncpgov"]["secret_key"] = ncpgov_secret_key
        
        if template in ["ssh", "multi-cloud", "full"]:
            ssh_key_dir = Prompt.ask("SSH Key Directory", default="~/aws-key")
            if ssh_key_dir:
                secrets_config["ssh"]["key_dir"] = ssh_key_dir
                secrets_example["ssh"]["key_dir"] = ssh_key_dir
        
        if template in ["multi-cloud", "full"]:
            slack_webhook = Prompt.ask("Slack Webhook URL (optional)", default="")
            if slack_webhook:
                secrets_config["slack"]["webhook_url"] = slack_webhook
                secrets_example["slack"]["webhook_url"] = slack_webhook
        
        return default_config, secrets_config, secrets_example
    
    def _validate_secrets_config(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate secrets configuration file.
        
        Args:
            config_data: Secrets configuration data
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Basic structure validation
        if not isinstance(config_data, dict):
            errors.append("Secrets configuration must be a dictionary")
            return errors
        
        # Secrets files don't need version or logging sections
        # Just validate that it contains expected platform sections
        valid_sections = ['aws', 'oci', 'azure', 'gcp', 'ncp', 'ncpgov', 'cloudflare', 'ssh']
        
        if not any(section in config_data for section in valid_sections):
            errors.append("Secrets configuration should contain at least one platform section (aws, oci, azure, gcp, ncp, ncpgov, cloudflare, ssh)")
        
        return errors
    
    def _validate_default_config(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate default configuration file.
        
        Args:
            config_data: Default configuration data
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Basic structure validation
        if not isinstance(config_data, dict):
            errors.append("Configuration must be a dictionary")
            return errors
        
        # Version validation
        if 'version' not in config_data:
            errors.append("Configuration missing required 'version' field")
        
        # Validate required sections for default config
        required_sections = ['logging', 'security']
        for section in required_sections:
            if section not in config_data:
                errors.append(f"Configuration missing required section: {section}")
        
        # Validate logging configuration
        if 'logging' in config_data:
            logging_config = config_data['logging']
            if not isinstance(logging_config, dict):
                errors.append("Logging configuration must be a dictionary")
            else:
                required_log_fields = ['console_level', 'file_level', 'file_path']
                for field in required_log_fields:
                    if field not in logging_config:
                        errors.append(f"Logging configuration missing required field: {field}")
        
        return errors
    
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
    
    def _create_ncp_config_files(self, template: str, secrets_config: Dict[str, Any]) -> None:
        """
        Create NCP configuration files with proper permissions.
        
        Args:
            template: Configuration template being used
            secrets_config: Secrets configuration data
        """
        try:
            if template in ["ncp", "multi-cloud", "full"] and "ncp" in secrets_config:
                # Create NCP config directory
                ncp_config_dir = Path.home() / ".ncp"
                ncp_config_dir.mkdir(mode=0o700, exist_ok=True)
                ncp_config_path = ncp_config_dir / "config"
                
                # Create NCP config file
                ncp_secrets = secrets_config.get("ncp", {})
                # Handle case where ncp_secrets might be a string or other type
                if not isinstance(ncp_secrets, dict):
                    ncp_secrets = {}
                
                ncp_config_data = {
                    "default": {
                        "access_key": ncp_secrets.get("access_key", ""),
                        "secret_key": ncp_secrets.get("secret_key", ""),
                        "region": "KR",
                        "platform": "VPC"
                    }
                }
                
                with open(ncp_config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(ncp_config_data, f, default_flow_style=False, indent=2)
                
                # Set proper permissions (600)
                if os.name != 'nt':  # Unix systems
                    os.chmod(ncp_config_path, 0o600)
                
                self.console.print(f"✅ NCP configuration created: {ncp_config_path}")
            
            if template in ["ncpgov", "multi-cloud", "full"] and "ncpgov" in secrets_config:
                # Create NCP Gov config directory
                ncpgov_config_dir = Path.home() / ".ncpgov"
                ncpgov_config_dir.mkdir(mode=0o700, exist_ok=True)
                ncpgov_config_path = ncpgov_config_dir / "config"
                
                # Create NCP Gov config file
                ncpgov_secrets = secrets_config.get("ncpgov", {})
                # Handle case where ncpgov_secrets might be a string or other type
                if not isinstance(ncpgov_secrets, dict):
                    ncpgov_secrets = {}
                
                ncpgov_config_data = {
                    "default": {
                        "access_key": ncpgov_secrets.get("access_key", ""),
                        "secret_key": ncpgov_secrets.get("secret_key", ""),
                        "apigw_key": ncpgov_secrets.get("apigw_key", ""),
                        "region": "KR",
                        "platform": "VPC",
                        "security": {
                            "encryption_enabled": True,
                            "audit_logging_enabled": True,
                            "access_control_enabled": True,
                            "mask_sensitive_data": True
                        }
                    }
                }
                
                with open(ncpgov_config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(ncpgov_config_data, f, default_flow_style=False, indent=2)
                
                # Set proper permissions (600) - required for government cloud
                if os.name != 'nt':  # Unix systems
                    os.chmod(ncpgov_config_path, 0o600)
                
                self.console.print(f"✅ NCP Gov configuration created: {ncpgov_config_path}")
                
        except Exception as e:
            self.console.print(f"❌ Failed to create NCP config files: {e}")
    
    def _validate_ncp_credentials(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate NCP credentials in configuration.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate NCP credentials
        if 'ncp' in config_data:
            ncp_config = config_data['ncp']
            if 'access_key' in ncp_config:
                access_key = ncp_config['access_key']
                if not access_key or len(access_key) < 10:
                    errors.append("NCP access_key appears to be invalid or too short")
            
            if 'secret_key' in ncp_config:
                secret_key = ncp_config['secret_key']
                if not secret_key or len(secret_key) < 20:
                    errors.append("NCP secret_key appears to be invalid or too short")
        
        # Validate NCP Gov credentials
        if 'ncpgov' in config_data:
            ncpgov_config = config_data['ncpgov']
            if 'access_key' in ncpgov_config:
                access_key = ncpgov_config['access_key']
                if not access_key or len(access_key) < 10:
                    errors.append("NCP Gov access_key appears to be invalid or too short")
            
            if 'secret_key' in ncpgov_config:
                secret_key = ncpgov_config['secret_key']
                if not secret_key or len(secret_key) < 20:
                    errors.append("NCP Gov secret_key appears to be invalid or too short")
        
        return errors 
   
    def _get_separated_template_config(self, template: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Get template configuration separated into default, secrets, and secrets example.
        
        Args:
            template: Template name
            
        Returns:
            Tuple of (default_config, secrets_config, secrets_example)
        """
        base_config = self.config_manager._get_default_config()
        
        # Default configuration (non-sensitive)
        default_config = {
            "version": base_config["version"],
            "logging": base_config["logging"],
            "security": base_config["security"],
        }
        
        # Add platform-specific default configs
        if template in ["aws", "multi-cloud", "full"]:
            default_config["aws"] = {
                "accounts": [],
                "regions": base_config["aws"]["regions"],
                "cross_account_role": base_config["aws"]["cross_account_role"],
                "session_duration": base_config["aws"]["session_duration"],
                "max_workers": base_config["aws"]["max_workers"],
                "tags": base_config["aws"]["tags"]
            }
        
        if template in ["azure", "multi-cloud", "full"]:
            default_config["azure"] = {
                "subscriptions": [],
                "locations": base_config["azure"]["locations"],
                "max_workers": base_config["azure"]["max_workers"]
            }
        
        if template in ["gcp", "multi-cloud", "full"]:
            default_config["gcp"] = {
                "mcp": base_config["gcp"]["mcp"],
                "projects": [],
                "regions": base_config["gcp"]["regions"],
                "zones": base_config["gcp"]["zones"],
                "max_workers": base_config["gcp"]["max_workers"]
            }
        
        if template in ["ncp", "multi-cloud", "full"]:
            default_config["ncp"] = {
                "config_path": base_config["ncp"]["config_path"],
                "regions": base_config["ncp"]["regions"],
                "max_workers": base_config["ncp"]["max_workers"]
            }
        
        if template in ["ncpgov", "multi-cloud", "full"]:
            default_config["ncpgov"] = {
                "config_path": base_config["ncpgov"]["config_path"],
                "regions": base_config["ncpgov"]["regions"],
                "max_workers": base_config["ncpgov"]["max_workers"],
                "security": base_config["ncpgov"]["security"]
            }
        
        # Secrets configuration (sensitive data)
        secrets_config = {}
        secrets_example = {}
        
        if template in ["aws", "multi-cloud", "full"]:
            secrets_example["aws"] = {
                "default_profile": "your-aws-profile",
                "access_key_id": "your-aws-access-key-id",
                "secret_access_key": "your-aws-secret-access-key"
            }
        
        if template in ["azure", "multi-cloud", "full"]:
            secrets_example["azure"] = {
                "subscription_id": "your-azure-subscription-id",
                "tenant_id": "your-azure-tenant-id",
                "client_id": "your-azure-client-id",
                "client_secret": "your-azure-client-secret"
            }
        
        if template in ["gcp", "multi-cloud", "full"]:
            secrets_example["gcp"] = {
                "project_id": "your-gcp-project-id",
                "service_account_key_path": "/path/to/service-account.json"
            }
        
        if template in ["ncp", "multi-cloud", "full"]:
            secrets_example["ncp"] = {
                "default": {
                    "access_key": "your-ncp-access-key",
                    "secret_key": "your-ncp-secret-key",
                    "region": "KR",
                    "platform": "VPC"
                }
            }
        
        if template in ["ncpgov", "multi-cloud", "full"]:
            secrets_example["ncpgov"] = {
                "default": {
                    "access_key": "your-ncpgov-access-key",
                    "secret_key": "your-ncpgov-secret-key",
                    "apigw_key": "your-ncpgov-apigw-key",
                    "region": "KR",
                    "platform": "VPC",
                    "encryption_enabled": True,
                    "audit_logging_enabled": True,
                    "access_control_enabled": True
                }
            }
        
        return default_config, secrets_config, secrets_example
    
    def _interactive_separated_config_setup(self, default_config: Dict[str, Any], 
                                          secrets_config: Dict[str, Any], 
                                          secrets_example: Dict[str, Any], 
                                          template: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Interactive configuration setup for separated configs.
        
        Args:
            default_config: Default configuration
            secrets_config: Secrets configuration
            secrets_example: Secrets example configuration
            template: Template name
            
        Returns:
            Updated configurations
        """
        self.console.print(f"\n🔧 Interactive setup for {template} template:")
        
        if template in ["aws", "multi-cloud", "full"]:
            accounts = Prompt.ask("AWS Account IDs (comma-separated)", default="")
            if accounts:
                default_config["aws"]["accounts"] = [acc.strip() for acc in accounts.split(",")]
            
            regions = Prompt.ask("AWS Regions (comma-separated)", default="ap-northeast-2")
            default_config["aws"]["regions"] = [reg.strip() for reg in regions.split(",")]
        
        if template in ["azure", "multi-cloud", "full"]:
            subscription_id = Prompt.ask("Azure Subscription ID", default="")
            if subscription_id:
                secrets_example["azure"]["subscription_id"] = subscription_id
        
        if template in ["gcp", "multi-cloud", "full"]:
            project_id = Prompt.ask("GCP Project ID", default="")
            if project_id:
                secrets_example["gcp"]["project_id"] = project_id
        
        if template in ["ncp", "multi-cloud", "full"]:
            regions = Prompt.ask("NCP Regions (comma-separated)", default="KR")
            default_config["ncp"]["regions"] = [reg.strip() for reg in regions.split(",")]
        
        if template in ["ncpgov", "multi-cloud", "full"]:
            regions = Prompt.ask("NCP Gov Regions (comma-separated)", default="KR")
            default_config["ncpgov"]["regions"] = [reg.strip() for reg in regions.split(",")]
        
        return default_config, secrets_config, secrets_example
    
    def _create_platform_config_files(self, template: str, secrets_config: Dict[str, Any]) -> None:
        """
        Create platform-specific configuration files using path manager.
        
        Args:
            template: Template name
            secrets_config: Secrets configuration
        """
        if template in ["ncp", "multi-cloud", "full"]:
            ncp_config_path = self.path_manager.home_dir / ".ncp" / "config.yaml"
            if not ncp_config_path.exists():
                ncp_content = self.path_manager._get_default_ncp_config()
                with open(ncp_config_path, 'w', encoding='utf-8') as f:
                    f.write(ncp_content)
                ncp_config_path.chmod(0o600)
                self.console.print(f"✅ NCP configuration created: {ncp_config_path}")
        
        if template in ["ncpgov", "multi-cloud", "full"]:
            ncpgov_config_path = self.path_manager.home_dir / ".ncpgov" / "config.yaml"
            if not ncpgov_config_path.exists():
                ncpgov_content = self.path_manager._get_default_ncpgov_config()
                with open(ncpgov_config_path, 'w', encoding='utf-8') as f:
                    f.write(ncpgov_content)
                ncpgov_config_path.chmod(0o600)
                self.console.print(f"✅ NCPGOV configuration created: {ncpgov_config_path}")
    
    def _validate_secrets_config(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate secrets configuration structure.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Basic structure validation for secrets
        if not isinstance(config_data, dict):
            errors.append("Configuration must be a dictionary")
            return errors
        
        # Validate platform-specific secrets
        for platform in ["aws", "azure", "gcp", "ncp", "ncpgov"]:
            if platform in config_data:
                platform_config = config_data[platform]
                if not isinstance(platform_config, dict):
                    errors.append(f"{platform} configuration must be a dictionary")
                    continue
                
                # Platform-specific validation
                if platform == "ncp":
                    for profile_name, profile_config in platform_config.items():
                        if not isinstance(profile_config, dict):
                            errors.append(f"NCP profile '{profile_name}' must be a dictionary")
                            continue
                        
                        required_keys = ["access_key", "secret_key"]
                        for key in required_keys:
                            if key not in profile_config or not profile_config[key]:
                                errors.append(f"NCP profile '{profile_name}' missing required key: {key}")
                
                elif platform == "ncpgov":
                    for profile_name, profile_config in platform_config.items():
                        if not isinstance(profile_config, dict):
                            errors.append(f"NCPGOV profile '{profile_name}' must be a dictionary")
                            continue
                        
                        required_keys = ["access_key", "secret_key", "apigw_key"]
                        for key in required_keys:
                            if key not in profile_config or not profile_config[key]:
                                errors.append(f"NCPGOV profile '{profile_name}' missing required key: {key}")
        
        return errors
    
    def _validate_default_config(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate default configuration structure.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Use existing config manager validation
        base_errors = self.config_manager.validate_config(config_data)
        errors.extend(base_errors)
        
        # Additional validation for new structure
        if "version" not in config_data:
            errors.append("Configuration version is required")
        
        if "logging" not in config_data:
            errors.append("Logging configuration is required")
        
        if "security" not in config_data:
            errors.append("Security configuration is required")
        
        return errors