#!/usr/bin/env python3
"""
Migration commands for IC CLI.

This module provides CLI commands for managing project structure migration
including validation, rollback, and monitoring capabilities.
"""

import sys
from pathlib import Path
from typing import Dict, Any

try:
    from ..migration import MigrationManager
except ImportError:
    # Handle case when run directly
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.ic.migration import MigrationManager


class MigrationCommands:
    """Migration-related CLI commands."""
    
    def __init__(self):
        """Initialize migration commands."""
        self.manager = None
    
    def add_subparsers(self, platform_subparsers):
        """Add migration subparsers to the main CLI."""
        migration_parser = platform_subparsers.add_parser(
            "migration",
            help="Migration validation and rollback commands",
            description="Manage IC CLI project structure migration\n\n"
                       "This tool provides comprehensive migration validation and rollback\n"
                       "capabilities to ensure safe refactoring of the project structure.\n\n"
                       "Migration Process:\n"
                       "  1. Run pre-migration validation to capture baselines\n"
                       "  2. Perform migration changes\n"
                       "  3. Run post-migration validation to verify success\n"
                       "  4. If issues detected, use rollback to restore previous state\n\n"
                       "Commands:\n"
                       "  pre-validate    - Capture pre-migration baselines and validate current state\n"
                       "  post-validate   - Validate migration success by comparing with baselines\n"
                       "  rollback        - Rollback migration changes to previous state\n"
                       "  emergency       - Create emergency rollback script\n"
                       "  status          - Show migration status and summary\n\n"
                       "Examples:\n"
                       "  ic migration pre-validate\n"
                       "  ic migration post-validate\n"
                       "  ic migration rollback\n"
                       "  ic migration status",
            formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(prog)
        )
        
        migration_subparsers = migration_parser.add_subparsers(
            dest="migration_command",
            required=True,
            help="Migration command to execute"
        )
        
        # Pre-validation command
        pre_validate_parser = migration_subparsers.add_parser(
            "pre-validate",
            help="Run pre-migration validation and capture baselines"
        )
        pre_validate_parser.add_argument(
            "--output", "-o",
            type=Path,
            help="Output file for validation results"
        )
        pre_validate_parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose output"
        )
        pre_validate_parser.set_defaults(func=self.pre_validate_command)
        
        # Post-validation command
        post_validate_parser = migration_subparsers.add_parser(
            "post-validate",
            help="Run post-migration validation and comparison"
        )
        post_validate_parser.add_argument(
            "--output", "-o",
            type=Path,
            help="Output file for validation results"
        )
        post_validate_parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose output"
        )
        post_validate_parser.set_defaults(func=self.post_validate_command)
        
        # Rollback command
        rollback_parser = migration_subparsers.add_parser(
            "rollback",
            help="Rollback migration changes to previous state"
        )
        rollback_parser.add_argument(
            "--backup-dir",
            type=Path,
            help="Specific backup directory to restore from"
        )
        rollback_parser.add_argument(
            "--confirm",
            action="store_true",
            help="Skip confirmation prompt"
        )
        rollback_parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose output"
        )
        rollback_parser.set_defaults(func=self.rollback_command)
        
        # Emergency script command
        emergency_parser = migration_subparsers.add_parser(
            "emergency",
            help="Create emergency rollback script"
        )
        emergency_parser.add_argument(
            "--output", "-o",
            type=Path,
            help="Output path for emergency script"
        )
        emergency_parser.set_defaults(func=self.emergency_command)
        
        # Status command
        status_parser = migration_subparsers.add_parser(
            "status",
            help="Show migration status and summary"
        )
        status_parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed status information"
        )
        status_parser.set_defaults(func=self.status_command)
    
    def _get_manager(self) -> MigrationManager:
        """Get or create migration manager instance."""
        if self.manager is None:
            self.manager = MigrationManager()
        return self.manager
    
    def pre_validate_command(self, args):
        """Execute pre-migration validation command."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import Progress, SpinnerColumn, TextColumn
        import json
        
        console = Console()
        
        console.print(Panel(
            "[bold cyan]Pre-Migration Validation[/bold cyan]\n\n"
            "This will capture current CLI command outputs, test baselines,\n"
            "configuration states, and module structure for comparison\n"
            "after migration.",
            title="🔍 Migration Validation",
            border_style="cyan"
        ))
        
        try:
            manager = self._get_manager()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Running pre-migration validation...", total=None)
                
                result = manager.run_pre_migration_validation()
                
                progress.update(task, description="✅ Pre-migration validation completed")
            
            # Display results
            if result.get("ready_for_migration", False):
                console.print("\n✅ [bold green]Pre-migration validation PASSED[/bold green]")
                console.print("🚀 System is ready for migration")
            else:
                console.print("\n❌ [bold red]Pre-migration validation FAILED[/bold red]")
                console.print("⚠️  Critical issues detected:")
                
                for issue in result.get("critical_issues", []):
                    console.print(f"   • {issue}")
                
                console.print("\n💡 Please resolve these issues before proceeding with migration")
            
            # Show summary statistics
            cli_data = result.get("cli_baselines", {})
            test_data = result.get("test_baselines", {})
            config_data = result.get("configuration_validation", {})
            
            console.print(f"\n📊 [bold]Validation Summary:[/bold]")
            console.print(f"   • CLI Commands: {cli_data.get('successful_commands', 0)}/{cli_data.get('total_commands', 0)} successful")
            console.print(f"   • Test Suites: {test_data.get('successful_test_suites', 0)}/{test_data.get('total_test_suites', 0)} successful")
            console.print(f"   • Configurations: {config_data.get('valid_configs', 0)}/{config_data.get('existing_configs', 0)} valid")
            
            # Save results if requested
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2, default=str)
                console.print(f"\n💾 Results saved to: {args.output}")
            
            console.print(f"\n📁 Validation data: {manager.validation_dir}")
            console.print(f"💾 Backup location: {manager.pre_validator.backup_dir}")
            
        except Exception as e:
            console.print(f"\n❌ [bold red]Pre-migration validation failed:[/bold red] {e}")
            if args.verbose:
                import traceback
                console.print(f"\n[dim]{traceback.format_exc()}[/dim]")
            sys.exit(1)
    
    def post_validate_command(self, args):
        """Execute post-migration validation command."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import Progress, SpinnerColumn, TextColumn
        import json
        
        console = Console()
        
        console.print(Panel(
            "[bold cyan]Post-Migration Validation[/bold cyan]\n\n"
            "This will compare current system state with pre-migration\n"
            "baselines to verify migration success and detect any\n"
            "regressions or issues.",
            title="✅ Migration Verification",
            border_style="cyan"
        ))
        
        try:
            manager = self._get_manager()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Running post-migration validation...", total=None)
                
                result = manager.run_post_migration_validation()
                
                progress.update(task, description="✅ Post-migration validation completed")
            
            # Display results
            if result.get("success", False):
                console.print("\n✅ [bold green]Post-migration validation PASSED[/bold green]")
                console.print("🎉 Migration completed successfully!")
            else:
                console.print("\n❌ [bold red]Post-migration validation FAILED[/bold red]")
                console.print("⚠️  Critical issues detected:")
                
                for failure in result.get("critical_failures", []):
                    console.print(f"   • {failure}")
                
                console.print("\n💡 Consider running rollback to restore previous state")
            
            # Show summary statistics
            console.print(f"\n📊 [bold]Validation Summary:[/bold]")
            console.print(f"   • Total Checks: {result.get('total_checks', 0)}")
            console.print(f"   • Passed: {result.get('passed_checks', 0)}")
            console.print(f"   • Failed: {result.get('failed_checks', 0)}")
            
            if result.get("warnings"):
                console.print(f"   • Warnings: {len(result['warnings'])}")
            
            # Save results if requested
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2, default=str)
                console.print(f"\n💾 Results saved to: {args.output}")
            
            console.print(f"\n📁 Validation data: {manager.post_validator.post_validation_dir}")
            
        except Exception as e:
            console.print(f"\n❌ [bold red]Post-migration validation failed:[/bold red] {e}")
            if args.verbose:
                import traceback
                console.print(f"\n[dim]{traceback.format_exc()}[/dim]")
            sys.exit(1)
    
    def rollback_command(self, args):
        """Execute rollback command."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import Progress, SpinnerColumn, TextColumn
        from rich.prompt import Confirm
        
        console = Console()
        
        console.print(Panel(
            "[bold red]Migration Rollback[/bold red]\n\n"
            "⚠️  [bold yellow]WARNING:[/bold yellow] This will restore the previous project state\n"
            "and undo all migration changes. This action cannot be undone.\n\n"
            "The rollback will:\n"
            "• Remove new unified module structure\n"
            "• Restore original module directories\n"
            "• Restore configuration files\n"
            "• Restore CLI and test files",
            title="🔄 Rollback Migration",
            border_style="red"
        ))
        
        # Confirmation prompt
        if not args.confirm:
            if not Confirm.ask("\n[bold red]Are you sure you want to rollback the migration?[/bold red]"):
                console.print("Rollback cancelled.")
                return
        
        try:
            manager = self._get_manager()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Running migration rollback...", total=None)
                
                result = manager.run_rollback(args.backup_dir)
                
                progress.update(task, description="✅ Migration rollback completed")
            
            # Display results
            if result.get("success", False):
                console.print("\n✅ [bold green]Migration rollback SUCCESSFUL[/bold green]")
                console.print("🔄 Previous project state has been restored")
            else:
                console.print("\n❌ [bold red]Migration rollback FAILED[/bold red]")
                console.print("⚠️  Some operations failed:")
                
                console.print(f"\n📊 [bold]Rollback Summary:[/bold]")
                console.print(f"   • Total Operations: {result.get('total_operations', 0)}")
                console.print(f"   • Successful: {result.get('successful_operations', 0)}")
                console.print(f"   • Failed: {result.get('failed_operations', 0)}")
                
                console.print("\n💡 Check rollback report for details on failed operations")
            
            if result.get("backup_restored_from"):
                console.print(f"\n💾 Restored from: {result['backup_restored_from']}")
            
            console.print(f"\n📁 Rollback data: {manager.rollback_manager.rollback_dir}")
            
        except Exception as e:
            console.print(f"\n❌ [bold red]Migration rollback failed:[/bold red] {e}")
            if args.verbose:
                import traceback
                console.print(f"\n[dim]{traceback.format_exc()}[/dim]")
            sys.exit(1)
    
    def emergency_command(self, args):
        """Execute emergency script creation command."""
        from rich.console import Console
        from rich.panel import Panel
        
        console = Console()
        
        console.print(Panel(
            "[bold yellow]Emergency Rollback Script[/bold yellow]\n\n"
            "This creates a standalone Python script that can be used\n"
            "to perform emergency rollback without the full IC CLI system.\n\n"
            "Use this script if the main system becomes unusable after\n"
            "migration and you need to quickly restore the previous state.",
            title="🚨 Emergency Rollback",
            border_style="yellow"
        ))
        
        try:
            manager = self._get_manager()
            script_path = manager.create_emergency_rollback_script()
            
            console.print(f"\n✅ [bold green]Emergency rollback script created![/bold green]")
            console.print(f"📄 Script location: {script_path}")
            console.print(f"\n🚨 [bold]To use in emergency:[/bold]")
            console.print(f"   python {script_path}")
            
            if args.output:
                import shutil
                shutil.copy2(script_path, args.output)
                console.print(f"\n💾 Script copied to: {args.output}")
            
        except Exception as e:
            console.print(f"\n❌ [bold red]Failed to create emergency script:[/bold red] {e}")
            sys.exit(1)
    
    def status_command(self, args):
        """Execute status command."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        
        console = Console()
        
        try:
            manager = self._get_manager()
            summary = manager.generate_migration_summary()
            
            # Status panel
            status_color = {
                "migration_successful": "green",
                "migration_failed": "red", 
                "rollback_completed": "yellow",
                "pre_migration_only": "blue",
                "validation_incomplete": "orange",
                "unknown": "dim"
            }.get(summary["status"], "dim")
            
            status_text = {
                "migration_successful": "✅ Migration Successful",
                "migration_failed": "❌ Migration Failed",
                "rollback_completed": "🔄 Rollback Completed", 
                "pre_migration_only": "🔍 Pre-Migration Only",
                "validation_incomplete": "⚠️ Validation Incomplete",
                "unknown": "❓ Unknown Status"
            }.get(summary["status"], "❓ Unknown Status")
            
            console.print(Panel(
                f"[bold {status_color}]{status_text}[/bold {status_color}]\n\n"
                f"Project Root: {summary['project_root']}\n"
                f"Validation Directory: {summary['validation_directory']}\n"
                f"Last Updated: {summary['timestamp']}",
                title="📊 Migration Status",
                border_style=status_color
            ))
            
            # Files table
            if summary["files_generated"]:
                table = Table(title="Generated Files", show_header=True, header_style="bold magenta")
                table.add_column("File", style="cyan")
                table.add_column("Description", style="white")
                table.add_column("Size", justify="right", style="green")
                table.add_column("Modified", style="dim")
                
                for file_info in summary["files_generated"]:
                    size_kb = file_info["size"] / 1024
                    size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{file_info['size']} B"
                    
                    # Truncate file path for display
                    file_path = Path(file_info["file"])
                    display_path = str(file_path.relative_to(Path(summary["project_root"])))
                    
                    table.add_row(
                        display_path,
                        file_info["description"],
                        size_str,
                        file_info["modified"][:19]  # Remove microseconds
                    )
                
                console.print(table)
            else:
                console.print("\n[dim]No migration files found[/dim]")
            
            # Detailed information
            if args.detailed:
                console.print(f"\n[bold]Detailed Information:[/bold]")
                console.print(f"Total files generated: {len(summary['files_generated'])}")
                
                total_size = sum(f["size"] for f in summary["files_generated"])
                total_size_kb = total_size / 1024
                size_str = f"{total_size_kb:.1f} KB" if total_size_kb >= 1 else f"{total_size} B"
                console.print(f"Total size: {size_str}")
                
                # Show recommendations based on status
                if summary["status"] == "pre_migration_only":
                    console.print("\n💡 [bold]Next Steps:[/bold]")
                    console.print("   1. Perform migration changes")
                    console.print("   2. Run: ic migration post-validate")
                elif summary["status"] == "migration_failed":
                    console.print("\n💡 [bold]Recommended Actions:[/bold]")
                    console.print("   1. Review validation report for issues")
                    console.print("   2. Consider running: ic migration rollback")
                elif summary["status"] == "migration_successful":
                    console.print("\n🎉 [bold]Migration Complete![/bold]")
                    console.print("   All validation checks passed successfully")
            
        except Exception as e:
            console.print(f"\n❌ [bold red]Failed to get migration status:[/bold red] {e}")
            sys.exit(1)


# For backwards compatibility and direct execution
def main():
    """Main entry point when run directly."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IC CLI Migration Commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    migration_commands = MigrationCommands()
    migration_commands.add_subparsers(subparsers)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()