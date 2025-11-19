#!/usr/bin/env python3

import argparse
import sys
import warnings

class DevelopmentStatusHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter that adds development status warnings."""
    
    def __init__(self, platform_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform_name = platform_name
    
    def format_help(self):
        help_text = super().format_help()
        
        # Add development status warning at the beginning
        warning_text = (
            f"\n⚠️  DEVELOPMENT STATUS WARNING:\n"
            f"   {self.platform_name} features are currently in development.\n"
            f"   While usable, they may contain bugs or incomplete functionality.\n"
            f"   Please report any issues you encounter.\n\n"
        )
        
        # Insert warning after the usage line
        lines = help_text.split('\n')
        usage_line_idx = -1
        for i, line in enumerate(lines):
            if line.startswith('usage:'):
                usage_line_idx = i
                break
        
        if usage_line_idx >= 0:
            # Insert warning after usage line and any following empty lines
            insert_idx = usage_line_idx + 1
            while insert_idx < len(lines) and lines[insert_idx].strip() == '':
                insert_idx += 1
            
            lines.insert(insert_idx, warning_text)
        else:
            # Fallback: add at the beginning
            lines.insert(0, warning_text)
        
        return '\n'.join(lines)

# Silence all logging except ERROR messages
try:
    from .core.silence_logging import silence_all_logging
    silence_all_logging()
except ImportError:
    # Handle case when run directly
    import sys
    from pathlib import Path
    
    # Add src directory to path for direct execution
    src_dir = Path(__file__).parent.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    try:
        from ic.core.silence_logging import silence_all_logging
        silence_all_logging()
    except ImportError:
        # If silence_logging is not available, continue without it
        pass

# Dependency validation
def validate_core_dependencies():
    """
    Validate core dependencies and provide helpful error messages.
    
    Returns:
        bool: True if all core dependencies are available
    """
    try:
        try:
            from .core.dependency_validator import DependencyValidator
        except ImportError:
            # Handle case when run directly
            from ic.core.dependency_validator import DependencyValidator
        
        validator = DependencyValidator()
        
        # Check Python version first
        if not validator.validate_python_version():
            print("❌ Python version compatibility issue detected.")
            print(f"   IC CLI requires Python 3.9-3.12 (current: {sys.version_info.major}.{sys.version_info.minor})")
            return False
        
        # Check core dependencies
        core_ok = validator.validate_core_dependencies()
        
        if not core_ok:
            print("❌ Missing or incompatible dependencies detected:")
            
            if validator.missing_dependencies:
                print(f"\n   Missing packages ({len(validator.missing_dependencies)}):")
                for package in validator.missing_dependencies:
                    print(f"     - {package}")
            
            if validator.incompatible_dependencies:
                print(f"\n   Incompatible packages ({len(validator.incompatible_dependencies)}):")
                for package in validator.incompatible_dependencies:
                    print(f"     - {package}")
            
            install_cmd = validator.generate_installation_command()
            if install_cmd:
                print(f"\n💡 To fix these issues, run:")
                print(f"   {install_cmd}")
            else:
                print(f"\n💡 To fix these issues, run:")
                print(f"   pip install -r requirements.txt")
            
            print(f"\n📖 For more help, see: https://github.com/dgr009/ic#installation")
            return False
            
        return True
        
    except ImportError:
        # Dependency validator itself is missing - this means core dependencies are not installed
        print("❌ IC CLI core dependencies are not installed.")
        print("\n💡 To install dependencies, run:")
        print("   pip install -r requirements.txt")
        print("\n📖 For installation help, see: https://github.com/dgr009/ic#installation")
        return False
    except Exception as e:
        # Unexpected error during validation
        print(f"⚠️  Warning: Could not validate dependencies: {e}")
        return True  # Continue anyway

# Set up compatibility layer first
try:
    from .compat.cli import setup_cli_compatibility, wrap_command_function, ensure_env_compatibility
    from .config.manager import ConfigManager
    from .config.security import SecurityManager
    from .core.logging import init_logger
    from .core.platform_discovery import get_platform_discovery
except ImportError:
    # Handle case when run directly
    from ic.compat.cli import setup_cli_compatibility, wrap_command_function, ensure_env_compatibility
    from ic.config.manager import ConfigManager
    from ic.config.security import SecurityManager
    from ic.core.logging import init_logger
    from ic.core.platform_discovery import get_platform_discovery

# Initialize compatibility layer
setup_cli_compatibility()

# Global configuration manager instance
_config_manager = None
_ic_logger = None

def get_config_manager():
    """Get or create global configuration manager."""
    global _config_manager, _ic_logger
    if _config_manager is None:
        # Suppress all logging during initialization
        import logging
        logging.getLogger().setLevel(logging.CRITICAL)
        
        security_manager = SecurityManager()
        _config_manager = ConfigManager(security_manager)
        
        # Load all configurations
        config = _config_manager.load_all_configs()
        
        # Initialize logging with new configuration
        _ic_logger = init_logger(config)
        
        # Log .env file usage to file only (no console output)
        from pathlib import Path
        if Path('.env').exists() and _ic_logger:
            _ic_logger.log_info_file_only("Using .env file for configuration. Consider migrating to YAML configuration with 'ic config migrate'")
    
    return _config_manager

# Legacy dotenv support (silent loading)
try:
    from dotenv import load_dotenv
    from pathlib import Path
    if Path('.env').exists():
        load_dotenv()
except ImportError:
    pass

def execute_multi_service_command(platform_name, services, command, args):
    """Execute a command across multiple services in parallel."""
    import concurrent.futures
    from threading import Lock
    
    discovery = get_platform_discovery()
    output_lock = Lock()
    
    def execute_service(service_name):
        """Execute a command for a single service."""
        try:
            # Create a copy of args with the specific service
            service_args = argparse.Namespace(**vars(args))
            service_args.service = service_name
            service_args.command = command
            
            # Get the command module
            command_module = discovery.get_command_module(platform_name, service_name, command)
            
            if not command_module:
                return {
                    'service': service_name,
                    'success': False,
                    'output': '',
                    'error': f"Command '{command}' not found in service '{service_name}'"
                }
            
            main_func = getattr(command_module, 'main', None)
            if not main_func:
                return {
                    'service': service_name,
                    'success': False,
                    'output': '',
                    'error': f"Command '{command}' does not have a main function"
                }
            
            # Capture output for thread-safe display
            import io
            import contextlib
            
            output_buffer = io.StringIO()
            with contextlib.redirect_stdout(output_buffer):
                config_manager = get_config_manager()
                config = config_manager.load_all_configs() if config_manager else None
                main_func(service_args, config)
            
            return {
                'service': service_name,
                'success': True,
                'output': output_buffer.getvalue(),
                'error': None
            }
            
        except Exception as e:
            return {
                'service': service_name,
                'success': False,
                'output': '',
                'error': str(e)
            }
    
    # Execute services in parallel
    try:
        from rich.console import Console
        console = Console()
        console.print(f"\n[bold cyan]Executing {platform_name.upper()} services in parallel: {', '.join(services)}[/bold cyan]")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(services), 5)) as executor:
            future_to_service = {executor.submit(execute_service, service): service for service in services}
            results = []
            
            for future in concurrent.futures.as_completed(future_to_service):
                result = future.result()
                results.append(result)
        
        # Sort results by original service order
        service_order = {service: i for i, service in enumerate(services)}
        results.sort(key=lambda x: service_order[x['service']])
        
        # Display results with thread-safe output
        with output_lock:
            has_error = False
            for result in results:
                service = result['service']
                if result['success']:
                    console.print(f"\n[bold green]✓ {platform_name.upper()} {service.upper()} Results:[/bold green]")
                    if result['output'].strip():
                        print(result['output'])
                    else:
                        console.print(f"[dim]No output from {service} service[/dim]")
                else:
                    console.print(f"\n[bold red]✗ {platform_name.upper()} {service.upper()} Failed:[/bold red]")
                    console.print(f"[red]Error: {result['error']}[/red]")
                    has_error = True
            
            if has_error:
                console.print(f"\n[bold yellow]⚠️ Some {platform_name.upper()} services failed. Check individual service configurations.[/bold yellow]")
                sys.exit(1)
            else:
                console.print(f"\n[bold green]✓ All {platform_name.upper()} services completed successfully[/bold green]")
                
    except ImportError:
        # Fallback without rich formatting
        print(f"\nExecuting {platform_name.upper()} services: {', '.join(services)}")
        for service in services:
            result = execute_service(service)
            if result['success']:
                print(f"\n✓ {platform_name.upper()} {service.upper()} Results:")
                if result['output'].strip():
                    print(result['output'])
            else:
                print(f"\n✗ {platform_name.upper()} {service.upper()} Failed: {result['error']}")

def execute_single_command(args):
    """Execute a single command using the platform discovery system."""
    discovery = get_platform_discovery()
    
    # Validate platform availability
    platform_available, platform_error = discovery.validate_platform_availability(args.platform)
    if not platform_available:
        print(f"❌ {platform_error}")
        available_platforms = discovery.list_platforms()
        if available_platforms:
            print(f"Available platforms: {', '.join(available_platforms)}")
        sys.exit(1)
    
    # Check if service exists
    service_info = discovery.get_service(args.platform, args.service)
    if not service_info:
        print(f"❌ Service '{args.service}' not found in platform '{args.platform}'")
        available_services = discovery.list_services(args.platform)
        if available_services:
            print(f"Available services: {', '.join(available_services)}")
        sys.exit(1)
    
    if not service_info.available:
        print(f"❌ Service '{args.service}' is not available: {service_info.error}")
        sys.exit(1)
    
    # Get the command module
    command_module = discovery.get_command_module(args.platform, args.service, args.command)
    
    if not command_module:
        print(f"❌ Command '{args.command}' not found in service '{args.service}' of platform '{args.platform}'")
        available_commands = list(discovery.get_service_commands(args.platform, args.service).keys())
        if available_commands:
            print(f"Available commands: {', '.join(available_commands)}")
        sys.exit(1)
    
    # Check if the command module has a main function
    main_func = getattr(command_module, 'main', None)
    if not main_func:
        print(f"❌ Command '{args.command}' does not have a main function")
        sys.exit(1)
    
    # Execute the command
    try:
        config_manager = get_config_manager()
        config = config_manager.load_all_configs() if config_manager else None
        
        # Check function signature to determine how to call it
        import inspect
        sig = inspect.signature(main_func)
        param_count = len(sig.parameters)
        
        if param_count == 1:
            # Legacy signature: main(args)
            main_func(args)
        elif param_count == 2:
            # New signature: main(args, config)
            main_func(args, config)
        else:
            # Fallback: try with args only
            main_func(args)
    except KeyboardInterrupt:
        print("\n⚠️ Command interrupted by user")
        sys.exit(130)
    except SystemExit:
        # Re-raise SystemExit to preserve exit codes
        raise
    except Exception as e:
        print(f"❌ Error executing command: {e}")
        import traceback
        if hasattr(args, 'verbose') and args.verbose:
            print("\nFull traceback:")
            traceback.print_exc()
        sys.exit(1)

def setup_platform_parsers(platform_subparsers):
    """Set up parsers for all discovered platforms."""
    discovery = get_platform_discovery()
    platforms = discovery.discover_platforms()
    
    # Development status platforms
    dev_platforms = {'azure', 'gcp'}
    
    for platform_name, platform_info in platforms.items():
        if not platform_info.available:
            continue
            
        # Create platform parser
        help_text = f"{platform_name.upper()} 관련 명령어"
        if platform_name in dev_platforms:
            help_text += " (개발 중 - 버그 가능성 있음)"
            
        if platform_name in dev_platforms:
            platform_parser = platform_subparsers.add_parser(
                platform_name,
                help=help_text,
                formatter_class=lambda prog: DevelopmentStatusHelpFormatter(platform_name.upper(), prog)
            )
        else:
            platform_parser = platform_subparsers.add_parser(platform_name, help=help_text)
        
        # Create service subparsers
        service_subparsers = platform_parser.add_subparsers(
            dest="service",
            required=True,
            help=f"{platform_name.upper()} 리소스 관리 서비스"
        )
        
        # Add services for this platform
        for service_name, service_info in platform_info.services.items():
            if not service_info.available:
                continue
                
            service_parser = service_subparsers.add_parser(
                service_name,
                help=f"{service_name} 관련 명령어"
            )
            
            # Create command subparsers for the service
            command_subparsers = service_parser.add_subparsers(
                dest="command",
                required=True,
                help=f"{service_name} 명령어"
            )
            
            # Add commands for this service
            commands = discovery.get_service_commands(platform_name, service_name)
            for command_name, command_module in commands.items():
                command_parser = command_subparsers.add_parser(
                    command_name,
                    help=f"{command_name} 명령어"
                )
                
                # Add command-specific arguments if available
                add_arguments = getattr(command_module, 'add_arguments', None)
                if add_arguments:
                    try:
                        add_arguments(command_parser)
                    except Exception as e:
                        # Only show warning in verbose mode to avoid cluttering output
                        if '--verbose' in sys.argv or '-v' in sys.argv:
                            print(f"Warning: Could not add arguments for {platform_name}.{service_name}.{command_name}: {e}")
                
                # Set the default function with proper closure
                command_parser.set_defaults(func=execute_single_command)

def main():
    """IC CLI 엔트리 포인트"""
    # Validate core dependencies first
    if not validate_core_dependencies():
        sys.exit(1)
    
    # Initialize configuration system early
    try:
        config_manager = get_config_manager()
    except Exception as e:
        print(f"Warning: Failed to initialize configuration system: {e}")
        print("Falling back to legacy configuration...")
    
    parser = argparse.ArgumentParser(
        description="Infra CLI: Platform Resource CLI Tool\n\n"
                   "⚠️  Development Status:\n"
                   "   • Azure: In development - usable but may contain bugs\n"
                   "   • GCP: In development - usable but may contain bugs\n"
                   "   • AWS, OCI, CloudFlare, SSH: Production ready",
        usage="ic <platform|config> <service> <command> [options]",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add version argument
    try:
        from . import __version__
    except ImportError:
        from ic import __version__
    parser.add_argument('--version', '-v', action='version', version=f'ic-code {__version__}')
    
    platform_subparsers = parser.add_subparsers(
        dest="platform",
        required=False,
        help="클라우드 플랫폼 (aws, oci, cf, ssh, azure, gcp) 또는 config 관리"
    )
    
    # Add version command
    version_parser = platform_subparsers.add_parser('version', help='Show IC version')
    version_parser.set_defaults(func=lambda args: print(f'ic-code {__version__}'))
    
    # Add config commands
    try:
        from .commands.config import ConfigCommands
    except ImportError:
        from ic.commands.config import ConfigCommands
    config_commands = ConfigCommands()
    config_commands.add_subparsers(platform_subparsers)
    
    # Add security commands
    try:
        from .commands.security import SecurityCommands
    except ImportError:
        from ic.commands.security import SecurityCommands
    security_commands = SecurityCommands()
    security_commands.add_subparsers(platform_subparsers)
    
    # Set up platform parsers using discovery
    setup_platform_parsers(platform_subparsers)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check for multi-service commands (comma-separated services)
    if hasattr(args, 'service') and hasattr(args, 'command') and ',' in args.service:
        services = [s.strip() for s in args.service.split(',')]
        execute_multi_service_command(args.platform, services, args.command, args)
    else:
        # Execute the command
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()

if __name__ == "__main__":
    main()