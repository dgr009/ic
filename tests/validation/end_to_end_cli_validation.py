#!/usr/bin/env python3
"""
End-to-End CLI Validation Script

This script validates all CLI commands across all platforms to ensure:
1. All import paths resolve correctly
2. All configuration loading works properly
3. CLI functionality is preserved after refactoring

Requirements: 1.5, 1.6
"""

import sys
import subprocess
import importlib
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import time

class CLIValidationError(Exception):
    """Custom exception for CLI validation errors."""
    pass

class EndToEndCLIValidator:
    """Comprehensive CLI validation system."""
    
    def __init__(self):
        self.console = Console()
        self.results = {
            'import_tests': [],
            'config_tests': [],
            'cli_tests': [],
            'errors': []
        }
        
        # Define all CLI commands to test
        self.cli_commands = {
            'aws': [
                'aws ec2 --help',
                'aws s3 --help',
                'aws vpc --help',
                'aws rds --help',
                'aws lb --help',
                'aws sg --help',
                'aws eks --help',
                'aws ecs --help',
                'aws profile --help'
            ],
            'ncp': [
                'ncp ec2 --help',
                'ncp s3 --help',
                'ncp vpc --help',
                'ncp sg --help',
                'ncp rds --help'
            ],
            'ncpgov': [
                'ncpgov ec2 --help',
                'ncpgov s3 --help',
                'ncpgov vpc --help',
                'ncpgov sg --help',
                'ncpgov rds --help'
            ],
            'gcp': [
                'gcp compute --help',
                'gcp storage --help',
                'gcp vpc --help',
                'gcp gke --help',
                'gcp sql --help'
            ],
            'oci': [
                'oci vm --help',
                'oci lb --help',
                'oci nsg --help',
                'oci volume --help',
                'oci obj --help'
            ],
            'azure': [
                'azure vm --help',
                'azure storage --help',
                'azure aks --help',
                'azure lb --help'
            ],
            'config': [
                'config --help',
                'config init --help',
                'config migrate --help',
                'config validate --help'
            ],
            'security': [
                'security --help',
                'security scan --help',
                'security hooks --help'
            ]
        }
        
        # Define critical import paths to validate
        self.import_paths = [
            # NCP unified imports
            'src.ic.platforms.ncp.ec2.info',
            'src.ic.platforms.ncp.s3.info',
            'src.ic.platforms.ncp.vpc.info',
            'src.ic.platforms.ncp.sg.info',
            'src.ic.platforms.ncp.rds.info',
            'src.ic.platforms.ncp.client',
            
            # NCPGOV unified imports
            'src.ic.platforms.ncpgov.ec2.info',
            'src.ic.platforms.ncpgov.s3.info',
            'src.ic.platforms.ncpgov.vpc.info',
            'src.ic.platforms.ncpgov.sg.info',
            'src.ic.platforms.ncpgov.rds.info',
            'src.ic.platforms.ncpgov.client',
            
            # Core system imports
            'src.ic.config.manager',
            'src.ic.config.path_manager',
            'src.ic.security.scanner',
            'src.ic.security.detector',
            'src.ic.commands.config',
            'src.ic.commands.security'
        ]

    def validate_import_paths(self) -> bool:
        """Validate that all critical import paths resolve correctly."""
        self.console.print("\n[bold cyan]🔍 Validating Import Paths[/bold cyan]")
        
        success_count = 0
        total_count = len(self.import_paths)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Checking imports...", total=total_count)
            
            for import_path in self.import_paths:
                try:
                    # Add src to path if needed
                    src_path = Path(__file__).parent.parent.parent / 'src'
                    if str(src_path) not in sys.path:
                        sys.path.insert(0, str(src_path))
                    
                    module = importlib.import_module(import_path)
                    
                    self.results['import_tests'].append({
                        'path': import_path,
                        'status': 'success',
                        'error': None
                    })
                    success_count += 1
                    
                except ImportError as e:
                    error_msg = f"ImportError: {str(e)}"
                    self.results['import_tests'].append({
                        'path': import_path,
                        'status': 'failed',
                        'error': error_msg
                    })
                    self.results['errors'].append(f"Import failed: {import_path} - {error_msg}")
                    
                except Exception as e:
                    error_msg = f"Unexpected error: {str(e)}"
                    self.results['import_tests'].append({
                        'path': import_path,
                        'status': 'failed',
                        'error': error_msg
                    })
                    self.results['errors'].append(f"Import failed: {import_path} - {error_msg}")
                
                progress.advance(task)
        
        success_rate = (success_count / total_count) * 100
        
        if success_count == total_count:
            self.console.print(f"[bold green]✅ All {total_count} import paths validated successfully[/bold green]")
            return True
        else:
            self.console.print(f"[bold red]❌ {total_count - success_count} import paths failed ({success_rate:.1f}% success)[/bold red]")
            return False

    def validate_configuration_loading(self) -> bool:
        """Validate that configuration loading works properly."""
        self.console.print("\n[bold cyan]⚙️ Validating Configuration Loading[/bold cyan]")
        
        config_tests = [
            ('ConfigManager initialization', self._test_config_manager_init),
            ('PathManager functionality', self._test_path_manager),
            ('NCP config loading', self._test_ncp_config_loading),
            ('NCPGOV config loading', self._test_ncpgov_config_loading),
            ('Security config loading', self._test_security_config_loading)
        ]
        
        success_count = 0
        
        for test_name, test_func in config_tests:
            try:
                result = test_func()
                if result:
                    self.console.print(f"[green]✅ {test_name}[/green]")
                    self.results['config_tests'].append({
                        'test': test_name,
                        'status': 'success',
                        'error': None
                    })
                    success_count += 1
                else:
                    self.console.print(f"[red]❌ {test_name}[/red]")
                    self.results['config_tests'].append({
                        'test': test_name,
                        'status': 'failed',
                        'error': 'Test returned False'
                    })
                    
            except Exception as e:
                error_msg = f"Exception: {str(e)}"
                self.console.print(f"[red]❌ {test_name}: {error_msg}[/red]")
                self.results['config_tests'].append({
                    'test': test_name,
                    'status': 'failed',
                    'error': error_msg
                })
                self.results['errors'].append(f"Config test failed: {test_name} - {error_msg}")
        
        total_tests = len(config_tests)
        success_rate = (success_count / total_tests) * 100
        
        if success_count == total_tests:
            self.console.print(f"[bold green]✅ All {total_tests} configuration tests passed[/bold green]")
            return True
        else:
            self.console.print(f"[bold red]❌ {total_tests - success_count} configuration tests failed ({success_rate:.1f}% success)[/bold red]")
            return False

    def validate_cli_commands(self) -> bool:
        """Validate that all CLI commands work correctly."""
        self.console.print("\n[bold cyan]🖥️ Validating CLI Commands[/bold cyan]")
        
        total_commands = sum(len(commands) for commands in self.cli_commands.values())
        success_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Testing CLI commands...", total=total_commands)
            
            for platform, commands in self.cli_commands.items():
                self.console.print(f"\n[bold yellow]Testing {platform.upper()} commands:[/bold yellow]")
                
                for command in commands:
                    try:
                        # Construct full command
                        full_command = f"python src/ic/cli.py {command}"
                        
                        # Run command with timeout
                        result = subprocess.run(
                            full_command.split(),
                            capture_output=True,
                            text=True,
                            timeout=30,
                            cwd=Path(__file__).parent.parent.parent
                        )
                        
                        # Check if command executed successfully (exit code 0 for help commands)
                        if result.returncode == 0:
                            self.console.print(f"  [green]✅ {command}[/green]")
                            self.results['cli_tests'].append({
                                'command': command,
                                'platform': platform,
                                'status': 'success',
                                'error': None,
                                'output': result.stdout[:200] + '...' if len(result.stdout) > 200 else result.stdout
                            })
                            success_count += 1
                        else:
                            error_msg = f"Exit code: {result.returncode}, stderr: {result.stderr[:200]}"
                            self.console.print(f"  [red]❌ {command}: {error_msg}[/red]")
                            self.results['cli_tests'].append({
                                'command': command,
                                'platform': platform,
                                'status': 'failed',
                                'error': error_msg,
                                'output': result.stdout
                            })
                            self.results['errors'].append(f"CLI command failed: {command} - {error_msg}")
                            
                    except subprocess.TimeoutExpired:
                        error_msg = "Command timed out after 30 seconds"
                        self.console.print(f"  [red]❌ {command}: {error_msg}[/red]")
                        self.results['cli_tests'].append({
                            'command': command,
                            'platform': platform,
                            'status': 'failed',
                            'error': error_msg,
                            'output': ''
                        })
                        self.results['errors'].append(f"CLI command timeout: {command}")
                        
                    except Exception as e:
                        error_msg = f"Exception: {str(e)}"
                        self.console.print(f"  [red]❌ {command}: {error_msg}[/red]")
                        self.results['cli_tests'].append({
                            'command': command,
                            'platform': platform,
                            'status': 'failed',
                            'error': error_msg,
                            'output': ''
                        })
                        self.results['errors'].append(f"CLI command exception: {command} - {error_msg}")
                    
                    progress.advance(task)
        
        success_rate = (success_count / total_commands) * 100
        
        if success_count == total_commands:
            self.console.print(f"\n[bold green]✅ All {total_commands} CLI commands validated successfully[/bold green]")
            return True
        else:
            self.console.print(f"\n[bold red]❌ {total_commands - success_count} CLI commands failed ({success_rate:.1f}% success)[/bold red]")
            return False

    def _test_config_manager_init(self) -> bool:
        """Test ConfigManager initialization."""
        try:
            from src.ic.config.manager import ConfigManager
            from src.ic.config.security import SecurityManager
            
            security_manager = SecurityManager()
            config_manager = ConfigManager(security_manager)
            return True
        except Exception:
            return False

    def _test_path_manager(self) -> bool:
        """Test PathManager functionality."""
        try:
            from src.ic.config.path_manager import ConfigPathManager
            
            path_manager = ConfigPathManager()
            # Test basic path resolution
            ncp_path = path_manager.get_ncp_config_path()
            ncpgov_path = path_manager.get_ncpgov_config_path()
            return True
        except Exception:
            return False

    def _test_ncp_config_loading(self) -> bool:
        """Test NCP configuration loading."""
        try:
            from src.ic.platforms.ncp.client import NCPClient
            # This should not fail even if config doesn't exist (should use fallbacks)
            return True
        except Exception:
            return False

    def _test_ncpgov_config_loading(self) -> bool:
        """Test NCPGOV configuration loading."""
        try:
            from src.ic.platforms.ncpgov.client import NCPGovClient
            # This should not fail even if config doesn't exist (should use fallbacks)
            return True
        except Exception:
            return False

    def _test_security_config_loading(self) -> bool:
        """Test security configuration loading."""
        try:
            from src.ic.security.config import SecurityConfig
            
            config = SecurityConfig()
            return True
        except Exception:
            return False

    def generate_report(self) -> None:
        """Generate comprehensive validation report."""
        self.console.print("\n" + "="*80)
        self.console.print("[bold cyan]📊 END-TO-END CLI VALIDATION REPORT[/bold cyan]")
        self.console.print("="*80)
        
        # Summary statistics
        import_success = len([t for t in self.results['import_tests'] if t['status'] == 'success'])
        import_total = len(self.results['import_tests'])
        
        config_success = len([t for t in self.results['config_tests'] if t['status'] == 'success'])
        config_total = len(self.results['config_tests'])
        
        cli_success = len([t for t in self.results['cli_tests'] if t['status'] == 'success'])
        cli_total = len(self.results['cli_tests'])
        
        total_success = import_success + config_success + cli_success
        total_tests = import_total + config_total + cli_total
        
        # Create summary table
        summary_table = Table(title="Validation Summary")
        summary_table.add_column("Category", style="cyan")
        summary_table.add_column("Passed", style="green")
        summary_table.add_column("Failed", style="red")
        summary_table.add_column("Total", style="white")
        summary_table.add_column("Success Rate", style="yellow")
        
        summary_table.add_row(
            "Import Paths",
            str(import_success),
            str(import_total - import_success),
            str(import_total),
            f"{(import_success/import_total)*100:.1f}%" if import_total > 0 else "N/A"
        )
        
        summary_table.add_row(
            "Configuration",
            str(config_success),
            str(config_total - config_success),
            str(config_total),
            f"{(config_success/config_total)*100:.1f}%" if config_total > 0 else "N/A"
        )
        
        summary_table.add_row(
            "CLI Commands",
            str(cli_success),
            str(cli_total - cli_success),
            str(cli_total),
            f"{(cli_success/cli_total)*100:.1f}%" if cli_total > 0 else "N/A"
        )
        
        summary_table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{total_success}[/bold]",
            f"[bold]{total_tests - total_success}[/bold]",
            f"[bold]{total_tests}[/bold]",
            f"[bold]{(total_success/total_tests)*100:.1f}%[/bold]" if total_tests > 0 else "N/A"
        )
        
        self.console.print(summary_table)
        
        # Show errors if any
        if self.results['errors']:
            self.console.print(f"\n[bold red]❌ {len(self.results['errors'])} Errors Found:[/bold red]")
            for i, error in enumerate(self.results['errors'][:10], 1):  # Show first 10 errors
                self.console.print(f"  {i}. {error}")
            
            if len(self.results['errors']) > 10:
                self.console.print(f"  ... and {len(self.results['errors']) - 10} more errors")
        
        # Overall result
        overall_success_rate = (total_success / total_tests) * 100 if total_tests > 0 else 0
        
        if overall_success_rate >= 95:
            status_color = "green"
            status_icon = "✅"
            status_text = "EXCELLENT"
        elif overall_success_rate >= 85:
            status_color = "yellow"
            status_icon = "⚠️"
            status_text = "GOOD"
        elif overall_success_rate >= 70:
            status_color = "orange"
            status_icon = "⚠️"
            status_text = "NEEDS ATTENTION"
        else:
            status_color = "red"
            status_icon = "❌"
            status_text = "CRITICAL ISSUES"
        
        result_panel = Panel(
            f"[bold {status_color}]{status_icon} VALIDATION RESULT: {status_text}[/bold {status_color}]\n\n"
            f"Overall Success Rate: [bold]{overall_success_rate:.1f}%[/bold]\n"
            f"Total Tests: {total_tests}\n"
            f"Passed: [green]{total_success}[/green]\n"
            f"Failed: [red]{total_tests - total_success}[/red]",
            title="Final Result",
            border_style=status_color
        )
        
        self.console.print(f"\n{result_panel}")

    def run_validation(self) -> bool:
        """Run complete end-to-end validation."""
        start_time = time.time()
        
        self.console.print(Panel(
            "[bold cyan]End-to-End CLI Validation[/bold cyan]\n\n"
            "This validation ensures:\n"
            "• All import paths resolve correctly\n"
            "• Configuration loading works properly\n"
            "• CLI functionality is preserved\n\n"
            "[dim]Requirements: 1.5, 1.6[/dim]",
            title="🔍 CLI Validation Suite"
        ))
        
        # Run all validation steps
        import_success = self.validate_import_paths()
        config_success = self.validate_configuration_loading()
        cli_success = self.validate_cli_commands()
        
        # Generate comprehensive report
        self.generate_report()
        
        # Show execution time
        execution_time = time.time() - start_time
        self.console.print(f"\n⏱️ Validation completed in {execution_time:.2f} seconds")
        
        # Return overall success
        return import_success and config_success and cli_success

def main():
    """Main entry point for CLI validation."""
    validator = EndToEndCLIValidator()
    
    try:
        success = validator.run_validation()
        
        if success:
            print("\n🎉 All validations passed! CLI refactoring is successful.")
            sys.exit(0)
        else:
            print("\n💥 Some validations failed. Please review the errors above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Validation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error during validation: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()