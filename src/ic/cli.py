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
except ImportError:
    # Handle case when run directly
    from ic.compat.cli import setup_cli_compatibility, wrap_command_function, ensure_env_compatibility
    from ic.config.manager import ConfigManager
    from ic.config.security import SecurityManager
    from ic.core.logging import init_logger

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
# AWS imports - Unified module structure
from src.ic.platforms.aws.ec2 import list_tags as ec2_list_tags
from src.ic.platforms.aws.ec2 import tag_check as ec2_tag_check
from src.ic.platforms.aws.ec2 import info as ec2_info
from src.ic.platforms.aws.lb import list_tags as lb_list_tags
from src.ic.platforms.aws.lb import tag_check as lb_tag_check
from src.ic.platforms.aws.vpc import tag_check as vpc_tag_check
from src.ic.platforms.aws.vpc import list_tags as vpc_list_tags
from src.ic.platforms.aws.rds import list_tags as rds_list_tags
from src.ic.platforms.aws.rds import tag_check as rds_tag_check
from src.ic.platforms.aws.s3 import list_tags as s3_list_tags
from src.ic.platforms.aws.s3 import tag_check as s3_tag_check
from src.ic.platforms.aws.sg import info as sg_info
from src.ic.platforms.aws.eks import info as eks_info
from src.ic.platforms.aws.eks import nodes as eks_nodes
from src.ic.platforms.aws.eks import pods as eks_pods
from src.ic.platforms.aws.eks import fargate as eks_fargate
from src.ic.platforms.aws.eks import addons as eks_addons
from src.ic.platforms.aws.eks import update_config as eks_update_config
from src.ic.platforms.aws.fargate import info as fargate_info
from src.ic.platforms.aws.codepipeline import build as codepipeline_build
from src.ic.platforms.aws.codepipeline import deploy as codepipeline_deploy
from src.ic.platforms.aws.ecs import info as ecs_info
from src.ic.platforms.aws.ecs import service as ecs_service
from src.ic.platforms.aws.ecs import task as ecs_task
from src.ic.platforms.aws.msk import info as msk_info
from src.ic.platforms.aws.msk import broker as msk_broker
from src.ic.platforms.aws.profile.info import ProfileInfoCollector, ProfileTableRenderer
from src.ic.platforms.aws.cloudfront.info import CloudFrontCollector, CloudFrontRenderer
# CloudFlare imports - Unified module structure
from src.ic.platforms.cloudflare.dns import list_info as dns_info
# OCI imports - Unified module structure
from src.ic.platforms.oci.info import oci_info as oci_info # Deprecated. 통합 oci info
from src.ic.platforms.oci.vm import add_arguments as vm_add_args, main as vm_main
from src.ic.platforms.oci.lb import add_arguments as lb_add_args, main as lb_main
from src.ic.platforms.oci.nsg import add_arguments as nsg_add_args, main as nsg_main
from src.ic.platforms.oci.volume import add_arguments as volume_add_args, main as volume_main
from src.ic.platforms.oci.policy import add_arguments as policy_add_args, main as policy_main
from src.ic.platforms.oci.policy import search as oci_policy_search
from src.ic.platforms.oci.obj import add_arguments as obj_add_args, main as obj_main
from src.ic.platforms.oci.cost.usage import add_arguments as cost_usage_add_args, main as cost_usage_main
from src.ic.platforms.oci.cost.credit import add_arguments as cost_credit_add_args, main as cost_credit_main
from src.ic.platforms.oci.vcn import info as vcn_info
from src.ic.platforms.oci.compartment.info import CompartmentTreeBuilder, CompartmentTreeRenderer
# SSH imports - Unified module structure
from src.ic.platforms.ssh import auto_ssh, server_info
# NCP imports - Unified module structure
from src.ic.platforms.ncp.ec2 import info as ncp_ec2_info
from src.ic.platforms.ncp.s3 import info as ncp_s3_info
from src.ic.platforms.ncp.vpc import info as ncp_vpc_info
from src.ic.platforms.ncp.sg import info as ncp_sg_info
from src.ic.platforms.ncp.rds import info as ncp_rds_info
# NCP Gov imports - Unified module structure
from src.ic.platforms.ncpgov.ec2 import info as ncpgov_ec2_info
from src.ic.platforms.ncpgov.s3 import info as ncpgov_s3_info
from src.ic.platforms.ncpgov.vpc import info as ncpgov_vpc_info
from src.ic.platforms.ncpgov.sg import info as ncpgov_sg_info
from src.ic.platforms.ncpgov.rds import info as ncpgov_rds_info
import concurrent.futures
from threading import Lock

load_dotenv()

# Global lock for thread-safe output formatting
output_lock = Lock()

def oci_info_deprecated(args):
    from rich.console import Console
    console = Console()
    console.print("\n[bold yellow]⚠️ 'ic oci info' 명령어는 더 이상 사용되지 않습니다.[/bold yellow]")
    console.print("대신 각 서비스별 `info` 명령어를 사용해주세요. 예시:\n")
    console.print("  - `ic oci vm info`")
    console.print("  - `ic oci lb info`")
    console.print("  - `ic oci nsg info`")
    console.print("  - `ic oci volume info`")
    console.print("  - `ic oci obj info`")
    console.print("  - `ic oci policy info`\n")
    console.print("  - 여러 서비스 : `ic oci vm,lb,nsg,volume,obj,policy info`\n")
    console.print("전체 OCI 명령어는 `ic oci --help`로 확인하실 수 있습니다.")

def execute_gcp_multi_service(services, command_and_options, parser):
    """GCP 다중 서비스 명령을 병렬로 실행합니다."""
    from rich.console import Console
    console = Console()
    
    def execute_service(service):
        """단일 GCP 서비스를 실행하고 결과를 반환합니다."""
        try:
            current_argv = ['gcp', service] + command_and_options
            args = parser.parse_args(current_argv)
            
            # Capture output for thread-safe display
            import io
            import contextlib
            
            output_buffer = io.StringIO()
            with contextlib.redirect_stdout(output_buffer):
                execute_single_command(args)
            
            return {
                'service': service,
                'success': True,
                'output': output_buffer.getvalue(),
                'error': None
            }
        except SystemExit as e:
            # SystemExit with code 0 is normal (e.g., help command)
            if e.code == 0:
                return {
                    'service': service,
                    'success': True,
                    'output': output_buffer.getvalue(),
                    'error': None
                }
            else:
                return {
                    'service': service,
                    'success': False,
                    'output': '',
                    'error': f"Command failed with exit code: {e.code}"
                }
        except Exception as e:
            return {
                'service': service,
                'success': False,
                'output': '',
                'error': str(e)
            }
    
    # Execute services in parallel
    console.print(f"\n[bold cyan]Executing GCP services in parallel: {', '.join(services)}[/bold cyan]")
    
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
                console.print(f"\n[bold green]✓ GCP {service.upper()} Results:[/bold green]")
                if result['output'].strip():
                    print(result['output'])
                else:
                    console.print(f"[dim]No output from {service} service[/dim]")
            else:
                console.print(f"\n[bold red]✗ GCP {service.upper()} Failed:[/bold red]")
                console.print(f"[red]Error: {result['error']}[/red]")
                has_error = True
        
        if has_error:
            console.print(f"\n[bold yellow]⚠️ Some GCP services failed. Check individual service configurations.[/bold yellow]")
            sys.exit(1)
        else:
            console.print(f"\n[bold green]✓ All GCP services completed successfully[/bold green]")

def gcp_monitor_performance_command(args):
    """GCP 성능 메트릭을 표시하는 명령어"""
    try:
        from common.gcp_monitoring import log_gcp_performance_summary
        log_gcp_performance_summary()
    except ImportError:
        from rich.console import Console
        console = Console()
        console.print("[bold red]GCP monitoring module not available[/bold red]")

def gcp_monitor_health_command(args):
    """GCP 서비스 헬스 상태를 표시하는 명령어"""
    try:
        from common.gcp_monitoring import gcp_monitor
        from rich.console import Console
        from rich.panel import Panel
        
        console = Console()
        health_status = gcp_monitor.get_health_status()
        
        health_text = f"MCP Connected: {'✓' if health_status['mcp_connected'] else '✗'}\n"
        health_text += f"Uptime: {health_status['uptime_minutes']:.1f} minutes\n"
        health_text += f"Total API Calls: {health_status['total_api_calls']}\n"
        
        if health_status['service_health']:
            health_text += "\nService Health:\n"
            for service, is_healthy in health_status['service_health'].items():
                status = '✓' if is_healthy else '✗'
                health_text += f"  {service}: {status}\n"
        else:
            health_text += "\nNo service health data available"
        
        console.print(Panel(
            health_text,
            title="GCP System Health",
            border_style="green" if health_status['mcp_connected'] else "yellow"
        ))
        
    except ImportError:
        from rich.console import Console
        console = Console()
        console.print("[bold red]GCP monitoring module not available[/bold red]")

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
    platform_subparsers = parser.add_subparsers(
        dest="platform",
        required=True,
        help="클라우드 플랫폼 (aws, oci, cf, ssh, azure, gcp) 또는 config 관리"
    )
    
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
    
    aws_parser = platform_subparsers.add_parser("aws", help="AWS 관련 명령어")
    oci_parser = platform_subparsers.add_parser("oci", help="OCI 관련 명령어")
    azure_parser = platform_subparsers.add_parser(
        "azure", 
        help="Azure 관련 명령어 (개발 중 - 버그 가능성 있음)",
        formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
    )
    gcp_parser = platform_subparsers.add_parser(
        "gcp", 
        help="GCP 관련 명령어 (개발 중 - 버그 가능성 있음)",
        formatter_class=lambda prog: DevelopmentStatusHelpFormatter("GCP", prog)
    )
    cf_parser = platform_subparsers.add_parser("cf", help="CloudFlare 관련 명령어")
    ssh_parser = platform_subparsers.add_parser("ssh", help="SSH 관련 명령어")
    ncp_parser = platform_subparsers.add_parser(
        "ncp", 
        help="NCP (Naver Cloud Platform) 관련 명령어",
        description="NCP 클라우드 서비스 관리 도구\n\n"
                   "지원 서비스:\n"
                   "  • ec2: 서버 인스턴스 관리\n"
                   "  • s3: 오브젝트 스토리지 관리\n"
                   "  • vpc: 가상 네트워크 관리\n"
                   "  • sg: 보안 그룹 관리\n\n"
                   "사용 예시:\n"
                   "  ic ncp ec2 info --name web\n"
                   "  ic ncp s3 info --format json\n"
                   "  ic ncp vpc info --profile production\n"
                   "  ic ncp sg info --verbose",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_parser = platform_subparsers.add_parser(
        "ncpgov", 
        help="NCP Gov (Naver Cloud Platform Government) 관련 명령어",
        description="NCP 정부 클라우드 서비스 관리 도구 (보안 강화)\n\n"
                   "지원 서비스:\n"
                   "  • ec2: 정부 클라우드 서버 인스턴스 관리\n"
                   "  • s3: 정부 클라우드 오브젝트 스토리지 관리\n"
                   "  • vpc: 정부 클라우드 가상 네트워크 관리\n"
                   "  • sg: 정부 클라우드 보안 그룹 관리\n\n"
                   "보안 특징:\n"
                   "  • 민감한 정보 자동 마스킹\n"
                   "  • 정부 클라우드 규정 준수 검증\n"
                   "  • 감사 로그 자동 기록\n\n"
                   "사용 예시:\n"
                   "  ic ncpgov ec2 info --name secure\n"
                   "  ic ncpgov s3 info --format json\n"
                   "  ic ncpgov vpc info --profile government\n"
                   "  ic ncpgov sg info --verbose",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    aws_subparsers = aws_parser.add_subparsers(dest="service",required=True,help="AWS 리소스 관리 서비스")
    oci_subparsers = oci_parser.add_subparsers(dest="service",required=True,help="OCI 리소스 관리 서비스")
    azure_subparsers = azure_parser.add_subparsers(dest="service", required=True, help="Azure 리소스 관리 서비스")
    gcp_subparsers = gcp_parser.add_subparsers(dest="service", required=True, help="GCP 리소스 관리 서비스")
    cf_subparsers = cf_parser.add_subparsers(dest="service",required=True,help="CloudFlare 리소스 관리 서비스")
    ssh_subparsers = ssh_parser.add_subparsers(dest="service",required=True,help="SSH 관리 서비스")
    ncp_subparsers = ncp_parser.add_subparsers(dest="service", required=True, help="NCP 리소스 관리 서비스")
    ncpgov_subparsers = ncpgov_parser.add_subparsers(dest="service", required=True, help="NCP Gov 리소스 관리 서비스")

    # ---------------- AWS ----------------
    ec2_parser = aws_subparsers.add_parser("ec2", help="EC2 관련 명령어")
    ec2_subparsers = ec2_parser.add_subparsers(dest="command", required=True)
    ec2_list_tags_parser = ec2_subparsers.add_parser("list_tags", help="EC2 인스턴스 태그 나열")
    ec2_list_tags.add_arguments(ec2_list_tags_parser)
    ec2_list_tags_parser.set_defaults(func=ec2_list_tags.main)
    ec2_tag_check_parser = ec2_subparsers.add_parser("tag_check", help="EC2 태그 유효성 검사")
    ec2_tag_check.add_arguments(ec2_tag_check_parser)
    ec2_tag_check_parser.set_defaults(func=ec2_tag_check.main)
    ec2_info_parser = ec2_subparsers.add_parser("info", help="EC2 인스턴스 정보 나열")
    ec2_info.add_arguments(ec2_info_parser)
    ec2_info_parser.set_defaults(func=ec2_info.main)

    lb_parser = aws_subparsers.add_parser("lb", help="LB 관련 명령어")
    lb_subparsers = lb_parser.add_subparsers(dest="command", required=True)
    lb_list_parser = lb_subparsers.add_parser("list_tags", help="LB 태그 조회")
    lb_list_tags.add_arguments(lb_list_parser)
    lb_list_parser.set_defaults(func=lb_list_tags.main)
    lb_check_parser = lb_subparsers.add_parser("tag_check", help="LB 태그 유효성 검사")
    lb_tag_check.add_arguments(lb_check_parser)
    lb_check_parser.set_defaults(func=lb_tag_check.main)

    lb_info_parser = lb_subparsers.add_parser("info", help="LB 상세 정보 조회")
    from src.ic.platforms.aws.lb import info as lb_info
    lb_info.add_arguments(lb_info_parser)
    lb_info_parser.set_defaults(func=lb_info.main)

    vpc_parser = aws_subparsers.add_parser("vpc", help="VPC + Gateway + VPN 관련 명령어")
    vpc_subparsers = vpc_parser.add_subparsers(dest="command", required=True)
    vpc_check_parser = vpc_subparsers.add_parser("tag_check", help="VPC + Gateway + VPN 태그 유효성 검사")
    vpc_tag_check.add_arguments(vpc_check_parser)
    vpc_check_parser.set_defaults(func=vpc_tag_check.main)
    vpc_list_parser = vpc_subparsers.add_parser("list_tags", help="VPC + Gateway + VPN 태그 조회")
    vpc_tag_check.add_arguments(vpc_list_parser)
    vpc_list_parser.set_defaults(func=vpc_list_tags.main)

    vpc_info_parser = vpc_subparsers.add_parser("info", help="VPC 상세 정보 조회")
    from src.ic.platforms.aws.vpc import info as vpc_info
    vpc_info.add_arguments(vpc_info_parser)
    vpc_info_parser.set_defaults(func=vpc_info.main)

    vpn_parser = aws_subparsers.add_parser("vpn", help="TGW, VGW, VPN Connection, Endpoint 관련 명령어")
    vpn_subparsers = vpn_parser.add_subparsers(dest="command", required=True)
    vpn_info_parser = vpn_subparsers.add_parser("info", help="VPN 관련 상세 정보 조회")
    from src.ic.platforms.aws.vpn import info as vpn_info
    vpn_info.add_arguments(vpn_info_parser)
    vpn_info_parser.set_defaults(func=vpn_info.main)


    rds_parser = aws_subparsers.add_parser("rds", help="RDS 관련 명령어")
    rds_subparsers = rds_parser.add_subparsers(dest="command", required=True)
    rds_list_cmd = rds_subparsers.add_parser("list_tags", help="RDS 태그 조회")
    rds_list_tags.add_arguments(rds_list_cmd)
    rds_list_cmd.set_defaults(func=rds_list_tags.main)
    rds_check_cmd = rds_subparsers.add_parser("tag_check", help="RDS 태그 유효성 검사")
    rds_tag_check.add_arguments(rds_check_cmd)
    rds_check_cmd.set_defaults(func=rds_tag_check.main)

    rds_info_parser = rds_subparsers.add_parser("info", help="RDS 상세 정보 조회")
    from src.ic.platforms.aws.rds import info as rds_info
    rds_info.add_arguments(rds_info_parser)
    rds_info_parser.set_defaults(func=rds_info.main)

    s3_parser = aws_subparsers.add_parser("s3", help="S3 관련 명령어")
    s3_subparsers = s3_parser.add_subparsers(dest="command", required=True)
    s3_list_cmd = s3_subparsers.add_parser("list_tags", help="S3 버킷 태그 조회")
    s3_list_tags.add_arguments(s3_list_cmd)
    s3_list_cmd.set_defaults(func=s3_list_tags.main)
    s3_check_cmd = s3_subparsers.add_parser("tag_check", help="S3 태그 유효성 검사")
    s3_tag_check.add_arguments(s3_check_cmd)
    s3_check_cmd.set_defaults(func=s3_tag_check.main)

    s3_info_parser = s3_subparsers.add_parser("info", help="S3 상세 정보 조회")
    from src.ic.platforms.aws.s3 import info as s3_info
    s3_info.add_arguments(s3_info_parser)
    s3_info_parser.set_defaults(func=s3_info.main)

    sg_parser = aws_subparsers.add_parser("sg", help="Security Group 관련 명령어")
    sg_subparsers = sg_parser.add_subparsers(dest="command", required=True)
    sg_info_parser = sg_subparsers.add_parser("info", help="Security Group 상세 정보 조회")
    sg_info.add_arguments(sg_info_parser)
    sg_info_parser.set_defaults(func=sg_info.main)

    # EKS 관련 명령어
    eks_parser = aws_subparsers.add_parser("eks", help="EKS 관련 명령어")
    eks_subparsers = eks_parser.add_subparsers(dest="command", required=True)
    
    eks_info_parser = eks_subparsers.add_parser("info", help="EKS 클러스터 정보 조회")
    eks_info.add_arguments(eks_info_parser)
    eks_info_parser.set_defaults(func=eks_info.main)
    
    eks_nodes_parser = eks_subparsers.add_parser("nodes", help="EKS 노드 정보 조회")
    eks_nodes.add_arguments(eks_nodes_parser)
    eks_nodes_parser.set_defaults(func=eks_nodes.main)
    
    eks_pods_parser = eks_subparsers.add_parser("pods", help="EKS 파드 정보 조회")
    eks_pods.add_arguments(eks_pods_parser)
    eks_pods_parser.set_defaults(func=eks_pods.main)
    
    eks_fargate_parser = eks_subparsers.add_parser("fargate", help="EKS Fargate 프로파일 정보 조회")
    eks_fargate.add_arguments(eks_fargate_parser)
    eks_fargate_parser.set_defaults(func=eks_fargate.main)
    
    eks_addons_parser = eks_subparsers.add_parser("addons", help="EKS 애드온 정보 조회")
    eks_addons.add_arguments(eks_addons_parser)
    eks_addons_parser.set_defaults(func=eks_addons.main)
    
    eks_update_config_parser = eks_subparsers.add_parser("update-config", help="EKS kubeconfig 업데이트")
    eks_update_config.add_arguments(eks_update_config_parser)
    eks_update_config_parser.set_defaults(func=eks_update_config.main)

    # Fargate 관련 명령어 (DEPRECATED - EKS로 완전 통합됨)
    def fargate_deprecated_handler(args):
        from rich.console import Console
        console = Console()
        console.print("\n[bold red]⚠️ 'ic aws fargate' 명령어는 더 이상 사용되지 않습니다.[/bold red]")
        console.print("EKS Fargate 기능이 EKS 서비스로 완전히 통합되었습니다.\n")
        console.print("[bold yellow]새로운 명령어를 사용해주세요:[/bold yellow]")
        console.print("  • EKS Fargate 프로파일: [bold cyan]ic aws eks fargate[/bold cyan]")
        console.print("  • EKS 파드 정보: [bold cyan]ic aws eks pods[/bold cyan]")
        console.print("  • EKS 전체 정보: [bold cyan]ic aws eks --help[/bold cyan]\n")
        console.print("ECS Fargate는 [bold cyan]ic aws ecs task[/bold cyan] 명령어를 사용하세요.")
        return
    
    def handle_aws_profile_info(args):
        """Handle AWS profile info command."""
        import time
        start_time = time.time()
        
        try:
            from pathlib import Path
            from rich.console import Console
            console = Console()
            
            # Create profile collector and renderer
            collector = ProfileInfoCollector()
            renderer = ProfileTableRenderer()
            
            # Override default paths if provided
            if hasattr(args, 'config_path') and args.config_path:
                config_path = Path(args.config_path)
                if not config_path.exists():
                    console.print(f"❌ AWS config file not found: {config_path}")
                    console.print("\n💡 Troubleshooting:")
                    console.print("  • Check the specified config file path")
                    console.print("  • Ensure the file exists and is readable")
                    sys.exit(1)
                collector.parser.aws_config_path = config_path
                
            if hasattr(args, 'credentials_path') and args.credentials_path:
                creds_path = Path(args.credentials_path)
                if not creds_path.exists():
                    console.print(f"❌ AWS credentials file not found: {creds_path}")
                    console.print("\n💡 Troubleshooting:")
                    console.print("  • Check the specified credentials file path")
                    console.print("  • Ensure the file exists and is readable")
                    sys.exit(1)
                collector.parser.aws_credentials_path = creds_path
            
            # Collect and render profile information
            profiles = collector.collect_profile_info()
            
            if not profiles:
                console.print("⚠️  No AWS profiles found.")
                console.print("\n💡 Getting started:")
                console.print("  • Run 'aws configure' to set up your first profile")
                console.print("  • Or run 'aws configure --profile <name>' for named profiles")
                console.print("  • Check AWS CLI documentation for setup instructions")
                sys.exit(0)
            
            renderer.render_profiles(profiles)
            
            # Display execution time
            execution_time = time.time() - start_time
            console.print(f"\n⏱️  Command completed in {execution_time:.2f} seconds")
            
        except FileNotFoundError as e:
            from rich.console import Console
            console = Console()
            console.print(f"❌ AWS configuration file not found: {e}")
            console.print("\n💡 Troubleshooting:")
            console.print("  • Run 'aws configure' to create AWS configuration")
            console.print("  • Ensure ~/.aws/config and ~/.aws/credentials files exist")
            console.print("  • Check if AWS CLI is installed: 'aws --version'")
            sys.exit(1)
        except PermissionError as e:
            from rich.console import Console
            console = Console()
            console.print(f"❌ Permission denied accessing AWS configuration: {e}")
            console.print("\n💡 Troubleshooting:")
            console.print("  • Check file permissions on ~/.aws/ directory")
            console.print("  • Ensure current user has read access to AWS config files")
            console.print("  • Try: chmod 600 ~/.aws/config ~/.aws/credentials")
            sys.exit(1)
        except ImportError as e:
            from rich.console import Console
            console = Console()
            console.print(f"❌ Missing required dependencies: {e}")
            console.print("\n💡 Troubleshooting:")
            console.print("  • Install required packages: pip install configparser")
            console.print("  • Ensure all AWS profile dependencies are installed")
            sys.exit(1)
        except Exception as e:
            from rich.console import Console
            console = Console()
            console.print(f"❌ Failed to retrieve AWS profile information: {e}")
            console.print("\n💡 Troubleshooting:")
            console.print("  • Ensure AWS CLI is installed and configured")
            console.print("  • Check if ~/.aws/config and ~/.aws/credentials files exist")
            console.print("  • Verify file permissions (should be readable)")
            console.print("  • Run 'aws configure list' to check current configuration")
            console.print("  • Try running with --debug flag for more details")
            sys.exit(1)
    
    def handle_aws_cloudfront_info(args):
        """Handle AWS CloudFront info command."""
        import time
        start_time = time.time()
        
        try:
            from rich.console import Console
            console = Console()
            
            # Create CloudFront collector and renderer
            collector = CloudFrontCollector()
            renderer = CloudFrontRenderer()
            
            # Determine account profiles to use
            account_profiles = {}
            
            if hasattr(args, 'accounts') and args.accounts:
                # Use specified accounts with profile mapping
                for account in args.accounts:
                    profile_name = getattr(args, 'profile', account)
                    account_profiles[account] = profile_name
            elif hasattr(args, 'profile') and args.profile:
                # Use single specified profile
                account_profiles[args.profile] = args.profile
            else:
                # Use default profile
                account_profiles['default'] = 'default'
            
            console.print(f"🔍 Collecting CloudFront distributions from {len(account_profiles)} account(s)...")
            
            # Validate profiles exist before proceeding
            if hasattr(args, 'profile') and args.profile:
                try:
                    import boto3
                    session = boto3.Session(profile_name=args.profile)
                    # Test if profile is valid by getting credentials
                    session.get_credentials()
                except Exception as profile_error:
                    console.print(f"❌ Invalid AWS profile '{args.profile}': {profile_error}")
                    console.print("\n💡 Troubleshooting:")
                    console.print("  • Check available profiles: aws configure list-profiles")
                    console.print("  • Ensure the profile is properly configured")
                    console.print("  • Run 'aws configure --profile <name>' to set up the profile")
                    sys.exit(1)
            
            # Collect and render CloudFront distributions
            distributions = collector.collect_distributions(account_profiles)
            
            if not distributions:
                console.print("📋 No CloudFront distributions found.")
                console.print("\n💡 This could mean:")
                console.print("  • No distributions exist in the specified accounts")
                console.print("  • Insufficient permissions to list distributions")
                console.print("  • The specified profiles don't have access to CloudFront")
                sys.exit(0)
            
            renderer.render_distributions(distributions)
            
            # Display execution time
            execution_time = time.time() - start_time
            console.print(f"\n⏱️  Command completed in {execution_time:.2f} seconds")
            
        except ImportError as e:
            from rich.console import Console
            console = Console()
            console.print(f"❌ Missing required dependencies: {e}")
            console.print("\n💡 Troubleshooting:")
            console.print("  • Install required packages: pip install boto3")
            console.print("  • Ensure all AWS dependencies are installed")
            sys.exit(1)
        except Exception as e:
            from rich.console import Console
            console = Console()
            error_msg = str(e).lower()
            
            if 'credentials' in error_msg or 'access' in error_msg:
                console.print(f"❌ AWS credentials error: {e}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Ensure AWS CLI is configured: aws configure")
                console.print("  • Check if credentials are valid: aws sts get-caller-identity")
                console.print("  • Verify CloudFront permissions: cloudfront:ListDistributions")
            elif 'profile' in error_msg:
                console.print(f"❌ AWS profile error: {e}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Check available profiles: aws configure list-profiles")
                console.print("  • Ensure the specified profile exists and is configured")
            elif 'region' in error_msg:
                console.print(f"❌ AWS region error: {e}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • CloudFront is a global service, but requires valid region config")
                console.print("  • Set default region: aws configure set region us-east-1")
            else:
                console.print(f"❌ Failed to retrieve CloudFront information: {e}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Ensure AWS CLI is configured with proper credentials")
                console.print("  • Verify CloudFront permissions (cloudfront:ListDistributions)")
                console.print("  • Check if the specified AWS profile exists")
                console.print("  • CloudFront is a global service - ensure proper region access")
                console.print("  • Try running with --debug flag for more details")
            sys.exit(1)
    
    def handle_oci_compartment_info(args):
        """Handle OCI compartment info command."""
        import time
        # start_time = time.time()
        
        try:
            import oci
            from rich.console import Console
            console = Console()
            
            # Create compartment tree builder and renderer
            builder = CompartmentTreeBuilder()
            renderer = CompartmentTreeRenderer()
            
            # console.print("🔍 Building OCI compartment tree...")
            
            # Set up OCI configuration
            config_file = getattr(args, 'config_file', None)
            profile = getattr(args, 'profile', 'DEFAULT')
            
            # Load OCI configuration
            if config_file:
                config = oci.config.from_file(config_file, profile)
            else:
                config = oci.config.from_file(profile_name=profile)
            
            # Validate configuration
            oci.config.validate_config(config)
            
            # Create identity client
            identity_client = oci.identity.IdentityClient(config)
            tenancy_ocid = config['tenancy']
            
            # Validate configuration file exists if specified
            if config_file:
                from pathlib import Path
                config_path = Path(config_file)
                if not config_path.exists():
                    console.print(f"❌ OCI configuration file not found: {config_file}")
                    console.print("\n💡 Troubleshooting:")
                    console.print("  • Check the specified config file path")
                    console.print("  • Ensure the file exists and is readable")
                    console.print("  • Use default config location: ~/.oci/config")
                    sys.exit(1)
            
            # Build and render compartment tree
            tree_data = builder.build_compartment_tree(identity_client, tenancy_ocid)
            
            if not tree_data:
                console.print("📋 No compartment data available.")
                console.print("\n💡 This could mean:")
                console.print("  • No compartments exist in the tenancy")
                console.print("  • Insufficient permissions to list compartments")
                console.print("  • Network connectivity issues")
                sys.exit(0)
            
            renderer.render_tree(tree_data)
            
            # Display execution time
            # execution_time = time.time() - start_time
            # console.print(f"\n⏱️  Command completed in {execution_time:.2f} seconds")
            
        except ImportError as e:
            from rich.console import Console
            console = Console()
            console.print(f"❌ Missing required dependencies: {e}")
            console.print("\n💡 Troubleshooting:")
            console.print("  • Install OCI SDK: pip install oci")
            console.print("  • Ensure all OCI dependencies are installed")
            sys.exit(1)
        except oci.exceptions.ConfigFileNotFound as e:
            from rich.console import Console
            console = Console()
            console.print(f"❌ OCI configuration file not found: {e}")
            console.print("\n💡 Troubleshooting:")
            console.print("  • Run 'oci setup config' to create OCI configuration")
            console.print("  • Ensure ~/.oci/config file exists")
            console.print("  • Verify the specified profile exists in the config file")
            console.print("  • Check OCI CLI installation: oci --version")
            sys.exit(1)
        except oci.exceptions.InvalidConfig as e:
            from rich.console import Console
            console = Console()
            console.print(f"❌ Invalid OCI configuration: {e}")
            console.print("\n💡 Troubleshooting:")
            console.print("  • Check OCI configuration file format")
            console.print("  • Verify all required fields are present (user, fingerprint, key_file, tenancy, region)")
            console.print("  • Ensure private key file exists and is readable")
            console.print("  • Validate key file permissions: chmod 600 ~/.oci/oci_api_key.pem")
            sys.exit(1)
        except oci.exceptions.ServiceError as e:
            from rich.console import Console
            console = Console()
            if e.status == 401:
                console.print(f"❌ OCI authentication failed: {e.message}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Verify OCI credentials are correct")
                console.print("  • Check if API key fingerprint matches")
                console.print("  • Ensure private key file is valid")
                console.print("  • Test authentication: oci iam user get --user-id <user-ocid>")
            elif e.status == 403:
                console.print(f"❌ OCI permission denied: {e.message}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Ensure user has identity:compartments:list permission")
                console.print("  • Check IAM policies for compartment access")
                console.print("  • Verify tenancy-level permissions")
            elif e.status == 404:
                console.print(f"❌ OCI resource not found: {e.message}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Verify tenancy OCID is correct")
                console.print("  • Check if compartments exist in the tenancy")
            else:
                console.print(f"❌ OCI service error ({e.status}): {e.message}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Check OCI service status")
                console.print("  • Verify network connectivity to OCI")
                console.print("  • Try again later if this is a temporary issue")
            sys.exit(1)
        except Exception as e:
            from rich.console import Console
            console = Console()
            error_msg = str(e).lower()
            
            if 'network' in error_msg or 'connection' in error_msg:
                console.print(f"❌ Network connectivity error: {e}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Check internet connectivity")
                console.print("  • Verify firewall settings")
                console.print("  • Check if OCI endpoints are accessible")
            elif 'timeout' in error_msg:
                console.print(f"❌ Request timeout: {e}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Check network connectivity")
                console.print("  • Try again later")
                console.print("  • Consider using a different region")
            else:
                console.print(f"❌ Failed to retrieve OCI compartment information: {e}")
                console.print("\n💡 Troubleshooting:")
                console.print("  • Ensure OCI CLI is installed and configured")
                console.print("  • Verify OCI credentials and permissions")
                console.print("  • Check network connectivity to OCI")
                console.print("  • Ensure identity:compartments:list permission")
                console.print("  • Try running with --debug flag for more details")
            sys.exit(1)
    
    fargate_parser = aws_subparsers.add_parser("fargate", help="[DEPRECATED] Fargate 관련 명령어 - 'ic aws eks' 사용 권장")
    fargate_subparsers = fargate_parser.add_subparsers(dest="command", required=False)
    fargate_parser.set_defaults(func=fargate_deprecated_handler)

    # CodePipeline 관련 명령어 (code 서비스 하위)
    code_parser = aws_subparsers.add_parser("code", help="CodePipeline 관련 명령어")
    code_subparsers = code_parser.add_subparsers(dest="command", required=True)
    
    code_build_parser = code_subparsers.add_parser("build", help="CodePipeline 빌드 스테이지 상태 조회")
    codepipeline_build.add_arguments(code_build_parser)
    code_build_parser.set_defaults(func=codepipeline_build.main)
    
    code_deploy_parser = code_subparsers.add_parser("deploy", help="CodePipeline 배포 스테이지 상태 조회")
    codepipeline_deploy.add_arguments(code_deploy_parser)
    code_deploy_parser.set_defaults(func=codepipeline_deploy.main)

    # ECS 관련 명령어
    ecs_parser = aws_subparsers.add_parser("ecs", help="ECS 관련 명령어")
    ecs_subparsers = ecs_parser.add_subparsers(dest="command", required=True)
    
    ecs_info_parser = ecs_subparsers.add_parser("info", help="ECS 클러스터 정보 조회")
    ecs_info.add_arguments(ecs_info_parser)
    ecs_info_parser.set_defaults(func=ecs_info.main)
    
    ecs_service_parser = ecs_subparsers.add_parser("service", help="ECS 서비스 정보 조회")
    ecs_service.add_arguments(ecs_service_parser)
    ecs_service_parser.set_defaults(func=ecs_service.main)
    
    ecs_task_parser = ecs_subparsers.add_parser("task", help="ECS 태스크 정보 조회")
    ecs_task.add_arguments(ecs_task_parser)
    ecs_task_parser.set_defaults(func=ecs_task.main)

    # MSK 관련 명령어
    msk_parser = aws_subparsers.add_parser("msk", help="MSK (Managed Streaming for Apache Kafka) 관련 명령어")
    msk_subparsers = msk_parser.add_subparsers(dest="command", required=True)
    
    msk_info_parser = msk_subparsers.add_parser("info", help="MSK 클러스터 정보 조회")
    msk_info.add_arguments(msk_info_parser)
    msk_info_parser.set_defaults(func=msk_info.main)
    
    msk_broker_parser = msk_subparsers.add_parser("broker", help="MSK 브로커 엔드포인트 정보 조회")
    msk_broker.add_arguments(msk_broker_parser)
    msk_broker_parser.set_defaults(func=msk_broker.main)

    # AWS Profile 관련 명령어
    profile_parser = aws_subparsers.add_parser("profile", help="AWS Profile 정보 조회")
    profile_subparsers = profile_parser.add_subparsers(dest="command", required=True)
    
    profile_info_parser = profile_subparsers.add_parser("info", help="AWS Profile 상세 정보 조회")
    profile_info_parser.add_argument("--config-path", help="AWS config 파일 경로 (기본값: ~/.aws/config)")
    profile_info_parser.add_argument("--credentials-path", help="AWS credentials 파일 경로 (기본값: ~/.aws/credentials)")
    profile_info_parser.set_defaults(func=handle_aws_profile_info)

    # AWS CloudFront 관련 명령어
    cloudfront_parser = aws_subparsers.add_parser("cloudfront", help="AWS CloudFront 배포 정보 조회")
    cloudfront_subparsers = cloudfront_parser.add_subparsers(dest="command", required=True)
    
    cloudfront_info_parser = cloudfront_subparsers.add_parser("info", help="CloudFront 배포 상세 정보 조회")
    cloudfront_info_parser.add_argument("--profile", help="사용할 AWS 프로파일")
    cloudfront_info_parser.add_argument("--accounts", nargs="+", help="조회할 AWS 계정 목록")
    cloudfront_info_parser.set_defaults(func=handle_aws_cloudfront_info)

    # ---------------- Azure ----------------
    # Azure VM 관련 명령어
    azure_vm_parser = azure_subparsers.add_parser("vm", help="Azure Virtual Machine 관련 명령어")
    azure_vm_subparsers = azure_vm_parser.add_subparsers(dest="command", required=True)
    azure_vm_info_parser = azure_vm_subparsers.add_parser("info", help="Azure VM 정보 조회")
    try:
        from azure_module.vm import info as azure_vm_info
        azure_vm_info.add_arguments(azure_vm_info_parser)
        azure_vm_info_parser.set_defaults(func=azure_vm_info.main)
    except ImportError:
        azure_vm_info_parser.set_defaults(func=lambda args: print("Azure 모듈이 설치되지 않았습니다. pip install azure-mgmt-compute를 실행하세요."))

    # Azure VNet 관련 명령어
    azure_vnet_parser = azure_subparsers.add_parser("vnet", help="Azure Virtual Network 관련 명령어")
    azure_vnet_subparsers = azure_vnet_parser.add_subparsers(dest="command", required=True)
    azure_vnet_info_parser = azure_vnet_subparsers.add_parser("info", help="Azure VNet 정보 조회")
    try:
        from azure_module.vnet import info as azure_vnet_info
        azure_vnet_info.add_arguments(azure_vnet_info_parser)
        azure_vnet_info_parser.set_defaults(func=azure_vnet_info.main)
    except ImportError:
        azure_vnet_info_parser.set_defaults(func=lambda args: print("Azure 모듈이 설치되지 않았습니다."))

    # Azure AKS 관련 명령어
    azure_aks_parser = azure_subparsers.add_parser("aks", help="Azure Kubernetes Service 관련 명령어")
    azure_aks_subparsers = azure_aks_parser.add_subparsers(dest="command", required=True)
    azure_aks_info_parser = azure_aks_subparsers.add_parser("info", help="Azure AKS 클러스터 정보 조회")
    try:
        from azure_module.aks import info as azure_aks_info
        azure_aks_info.add_arguments(azure_aks_info_parser)
        azure_aks_info_parser.set_defaults(func=azure_aks_info.main)
    except ImportError:
        azure_aks_info_parser.set_defaults(func=lambda args: print("Azure 모듈이 설치되지 않았습니다."))

    # Azure Storage 관련 명령어
    azure_storage_parser = azure_subparsers.add_parser("storage", help="Azure Storage Account 관련 명령어")
    azure_storage_subparsers = azure_storage_parser.add_subparsers(dest="command", required=True)
    azure_storage_info_parser = azure_storage_subparsers.add_parser("info", help="Azure Storage Account 정보 조회")
    try:
        from azure_module.storage import info as azure_storage_info
        azure_storage_info.add_arguments(azure_storage_info_parser)
        azure_storage_info_parser.set_defaults(func=azure_storage_info.main)
    except ImportError:
        azure_storage_info_parser.set_defaults(func=lambda args: print("Azure 모듈이 설치되지 않았습니다."))

    # Azure NSG 관련 명령어
    azure_nsg_parser = azure_subparsers.add_parser("nsg", help="Azure Network Security Group 관련 명령어")
    azure_nsg_subparsers = azure_nsg_parser.add_subparsers(dest="command", required=True)
    azure_nsg_info_parser = azure_nsg_subparsers.add_parser("info", help="Azure NSG 정보 조회")
    try:
        from azure_module.nsg import info as azure_nsg_info
        azure_nsg_info.add_arguments(azure_nsg_info_parser)
        azure_nsg_info_parser.set_defaults(func=azure_nsg_info.main)
    except ImportError:
        azure_nsg_info_parser.set_defaults(func=lambda args: print("Azure 모듈이 설치되지 않았습니다."))

    # Azure Load Balancer 관련 명령어
    azure_lb_parser = azure_subparsers.add_parser("lb", help="Azure Load Balancer 관련 명령어")
    azure_lb_subparsers = azure_lb_parser.add_subparsers(dest="command", required=True)
    azure_lb_info_parser = azure_lb_subparsers.add_parser("info", help="Azure Load Balancer 정보 조회")
    try:
        from azure_module.lb import info as azure_lb_info
        azure_lb_info.add_arguments(azure_lb_info_parser)
        azure_lb_info_parser.set_defaults(func=azure_lb_info.main)
    except ImportError:
        azure_lb_info_parser.set_defaults(func=lambda args: print("Azure 모듈이 설치되지 않았습니다."))

    # Azure Container Instances 관련 명령어
    azure_aci_parser = azure_subparsers.add_parser("aci", help="Azure Container Instances 관련 명령어")
    azure_aci_subparsers = azure_aci_parser.add_subparsers(dest="command", required=True)
    azure_aci_info_parser = azure_aci_subparsers.add_parser("info", help="Azure Container Instances 정보 조회")
    try:
        from azure_module.aci import info as azure_aci_info
        azure_aci_info.add_arguments(azure_aci_info_parser)
        azure_aci_info_parser.set_defaults(func=azure_aci_info.main)
    except ImportError:
        azure_aci_info_parser.set_defaults(func=lambda args: print("Azure 모듈이 설치되지 않았습니다."))

    # ---------------- GCP ----------------
    gcp_compute_parser = gcp_subparsers.add_parser("compute", help="GCP Compute Engine 관련 명령어")
    gcp_compute_subparsers = gcp_compute_parser.add_subparsers(dest="command", required=True)
    gcp_compute_info_parser = gcp_compute_subparsers.add_parser("info", help="GCP Compute Engine 정보 조회 (Mock)")
    from gcp.compute import info as gcp_compute_info
    gcp_compute_info.add_arguments(gcp_compute_info_parser)
    gcp_compute_info_parser.set_defaults(func=gcp_compute_info.main)

    gcp_vpc_parser = gcp_subparsers.add_parser("vpc", help="GCP VPC 관련 명령어")
    gcp_vpc_subparsers = gcp_vpc_parser.add_subparsers(dest="command", required=True)
    gcp_vpc_info_parser = gcp_vpc_subparsers.add_parser("info", help="GCP VPC 정보 조회 (Mock)")
    from gcp.vpc import info as gcp_vpc_info
    gcp_vpc_info.add_arguments(gcp_vpc_info_parser)
    gcp_vpc_info_parser.set_defaults(func=gcp_vpc_info.main)

    gcp_gke_parser = gcp_subparsers.add_parser("gke", help="GCP Google Kubernetes Engine 관련 명령어")
    gcp_gke_subparsers = gcp_gke_parser.add_subparsers(dest="command", required=True)
    gcp_gke_info_parser = gcp_gke_subparsers.add_parser("info", help="GCP GKE 클러스터 정보 조회")
    from gcp.gke import info as gcp_gke_info
    gcp_gke_info.add_arguments(gcp_gke_info_parser)
    gcp_gke_info_parser.set_defaults(func=gcp_gke_info.main)

    gcp_storage_parser = gcp_subparsers.add_parser("storage", help="GCP Cloud Storage 관련 명령어")
    gcp_storage_subparsers = gcp_storage_parser.add_subparsers(dest="command", required=True)
    gcp_storage_info_parser = gcp_storage_subparsers.add_parser("info", help="GCP Cloud Storage 버킷 정보 조회")
    from gcp.storage import info as gcp_storage_info
    gcp_storage_info.add_arguments(gcp_storage_info_parser)
    gcp_storage_info_parser.set_defaults(func=gcp_storage_info.main)

    gcp_sql_parser = gcp_subparsers.add_parser("sql", help="GCP Cloud SQL 관련 명령어")
    gcp_sql_subparsers = gcp_sql_parser.add_subparsers(dest="command", required=True)
    gcp_sql_info_parser = gcp_sql_subparsers.add_parser("info", help="GCP Cloud SQL 인스턴스 정보 조회")
    from gcp.sql import info as gcp_sql_info
    gcp_sql_info.add_arguments(gcp_sql_info_parser)
    gcp_sql_info_parser.set_defaults(func=gcp_sql_info.main)

    gcp_functions_parser = gcp_subparsers.add_parser("functions", help="GCP Cloud Functions 관련 명령어")
    gcp_functions_subparsers = gcp_functions_parser.add_subparsers(dest="command", required=True)
    gcp_functions_info_parser = gcp_functions_subparsers.add_parser("info", help="GCP Cloud Functions 정보 조회")
    from gcp.functions import info as gcp_functions_info
    gcp_functions_info.add_arguments(gcp_functions_info_parser)
    gcp_functions_info_parser.set_defaults(func=gcp_functions_info.main)

    gcp_run_parser = gcp_subparsers.add_parser("run", help="GCP Cloud Run 관련 명령어")
    gcp_run_subparsers = gcp_run_parser.add_subparsers(dest="command", required=True)
    gcp_run_info_parser = gcp_run_subparsers.add_parser("info", help="GCP Cloud Run 서비스 정보 조회")
    from gcp.run import info as gcp_run_info
    gcp_run_info.add_arguments(gcp_run_info_parser)
    gcp_run_info_parser.set_defaults(func=gcp_run_info.main)

    gcp_lb_parser = gcp_subparsers.add_parser("lb", help="GCP Load Balancing 관련 명령어")
    gcp_lb_subparsers = gcp_lb_parser.add_subparsers(dest="command", required=True)
    gcp_lb_info_parser = gcp_lb_subparsers.add_parser("info", help="GCP Load Balancer 정보 조회")
    from gcp.lb import info as gcp_lb_info
    gcp_lb_info.add_arguments(gcp_lb_info_parser)
    gcp_lb_info_parser.set_defaults(func=gcp_lb_info.main)

    gcp_firewall_parser = gcp_subparsers.add_parser("firewall", help="GCP 방화벽 규칙 관련 명령어")
    gcp_firewall_subparsers = gcp_firewall_parser.add_subparsers(dest="command", required=True)
    gcp_firewall_info_parser = gcp_firewall_subparsers.add_parser("info", help="GCP 방화벽 규칙 정보 조회")
    from gcp.firewall import info as gcp_firewall_info
    gcp_firewall_info.add_arguments(gcp_firewall_info_parser)
    gcp_firewall_info_parser.set_defaults(func=gcp_firewall_info.main)

    gcp_billing_parser = gcp_subparsers.add_parser("billing", help="GCP Billing 및 비용 관련 명령어")
    gcp_billing_subparsers = gcp_billing_parser.add_subparsers(dest="command", required=True)
    gcp_billing_info_parser = gcp_billing_subparsers.add_parser("info", help="GCP Billing 정보 및 비용 조회")
    from gcp.billing import info as gcp_billing_info
    gcp_billing_info.add_arguments(gcp_billing_info_parser)
    gcp_billing_info_parser.set_defaults(func=gcp_billing_info.main)

    # GCP 모니터링 및 성능 메트릭
    gcp_monitor_parser = gcp_subparsers.add_parser("monitor", help="GCP 모니터링 및 성능 메트릭")
    gcp_monitor_subparsers = gcp_monitor_parser.add_subparsers(dest="command", required=True)
    gcp_monitor_perf_parser = gcp_monitor_subparsers.add_parser("performance", help="GCP 성능 메트릭 조회")
    gcp_monitor_perf_parser.add_argument("--time-window", type=int, default=60, 
                                        help="메트릭 조회 시간 창 (분, 기본값: 60)")
    gcp_monitor_perf_parser.set_defaults(func=gcp_monitor_performance_command)
    
    gcp_monitor_health_parser = gcp_monitor_subparsers.add_parser("health", help="GCP 서비스 헬스 체크")
    gcp_monitor_health_parser.set_defaults(func=gcp_monitor_health_command)

    # ---------------- CloudFlare ----------------
    cf_dns_parser = cf_subparsers.add_parser("dns", help="DNS Record 관련 명령어")
    dns_subparsers = cf_dns_parser.add_subparsers(dest="command", required=True)
    dns_info_cmd = dns_subparsers.add_parser("info", help="DNS Record 정보 조회")
    dns_info.add_arguments(dns_info_cmd)
    dns_info_cmd.set_defaults(func=dns_info.info)

    # ---------------- SSH ----------------
    ssh_info_parser = ssh_subparsers.add_parser("info", help="등록된 SSH 서버의 상세 정보(CPU/Mem/Disk)를 스캔합니다.")
    ssh_info_parser.add_argument("--host", help="특정 호스트 문자열을 포함하는 서버만 필터링합니다.")
    ssh_info_parser.add_argument("--key", help="사용할 특정 프라이빗 키 파일을 지정합니다. (config 파일 우선)")
    ssh_info_parser.set_defaults(func=server_info.main)

    ssh_reg_parser = ssh_subparsers.add_parser("reg", help="네트워크를 스캔하여 새로운 SSH 서버를 찾아 .ssh/config에 등록합니다.")
    ssh_reg_parser.set_defaults(func=lambda args: auto_ssh.main())

    # ---------------- NCP ----------------
    # NCP EC2 commands
    ncp_ec2_parser = ncp_subparsers.add_parser(
        "ec2", 
        help="NCP EC2 관련 명령어",
        description="NCP 서버 인스턴스 관리\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: 인스턴스 목록 및 상세 정보 조회\n\n"
                   "예시:\n"
                   "  ic ncp ec2 info                    # 모든 인스턴스 조회\n"
                   "  ic ncp ec2 info --name web         # 이름에 'web' 포함된 인스턴스\n"
                   "  ic ncp ec2 info --format json      # JSON 형식으로 출력\n"
                   "  ic ncp ec2 info --profile prod     # 특정 프로필 사용",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_ec2_subparsers = ncp_ec2_parser.add_subparsers(dest="command", required=True)
    ncp_ec2_info_parser = ncp_ec2_subparsers.add_parser(
        "info", 
        help="NCP EC2 인스턴스 정보 조회",
        description="NCP EC2 인스턴스의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • 인스턴스 ID, 이름, 상태\n"
                   "  • 인스턴스 타입, 플랫폼\n"
                   "  • 공인/사설 IP 주소\n"
                   "  • VPC, 서브넷 정보\n"
                   "  • 생성 날짜\n\n"
                   "필터링 옵션:\n"
                   "  --name: 인스턴스 이름으로 필터링\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_ec2_info_parser.add_argument("--name", help="인스턴스 이름 필터 (부분 일치)")
    ncp_ec2_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                   help="출력 형식: table (기본값), json")
    ncp_ec2_info_parser.add_argument("--profile", default='default', 
                                   help="사용할 NCP 프로필 (기본값: default)")
    ncp_ec2_info_parser.set_defaults(func=lambda args: ncp_ec2_info.ncp_ec2_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile
    ))

    # NCP S3 commands
    ncp_s3_parser = ncp_subparsers.add_parser(
        "s3", 
        help="NCP S3 관련 명령어",
        description="NCP 오브젝트 스토리지 관리\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: 버킷 목록 및 상세 정보 조회\n\n"
                   "예시:\n"
                   "  ic ncp s3 info                     # 모든 버킷 조회\n"
                   "  ic ncp s3 info --name backup       # 이름에 'backup' 포함된 버킷\n"
                   "  ic ncp s3 info --format json       # JSON 형식으로 출력\n"
                   "  ic ncp s3 info --profile prod      # 특정 프로필 사용",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_s3_subparsers = ncp_s3_parser.add_subparsers(dest="command", required=True)
    ncp_s3_info_parser = ncp_s3_subparsers.add_parser(
        "info", 
        help="NCP S3 버킷 정보 조회",
        description="NCP S3 버킷의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • 버킷 이름, 리전, 생성일\n"
                   "  • 객체 수, 총 크기\n"
                   "  • 스토리지 클래스\n"
                   "  • 접근 제어 설정\n"
                   "  • 버전 관리, 암호화 상태\n\n"
                   "필터링 옵션:\n"
                   "  --name: 버킷 이름으로 필터링\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_s3_info_parser.add_argument("--name", help="버킷 이름 필터 (부분 일치)")
    ncp_s3_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                   help="출력 형식: table (기본값), json")
    ncp_s3_info_parser.add_argument("--profile", default='default', 
                                   help="사용할 NCP 프로필 (기본값: default)")
    ncp_s3_info_parser.set_defaults(func=lambda args: ncp_s3_info.ncp_s3_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile
    ))

    # NCP VPC commands
    ncp_vpc_parser = ncp_subparsers.add_parser(
        "vpc", 
        help="NCP VPC 관련 명령어",
        description="NCP 가상 네트워크 관리\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: VPC 목록 및 상세 정보 조회\n\n"
                   "예시:\n"
                   "  ic ncp vpc info                    # 모든 VPC 조회\n"
                   "  ic ncp vpc info --name main        # 이름에 'main' 포함된 VPC\n"
                   "  ic ncp vpc info --format json      # JSON 형식으로 출력\n"
                   "  ic ncp vpc info --profile prod     # 특정 프로필 사용",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_vpc_subparsers = ncp_vpc_parser.add_subparsers(dest="command", required=True)
    ncp_vpc_info_parser = ncp_vpc_subparsers.add_parser(
        "info", 
        help="NCP VPC 정보 조회",
        description="NCP VPC의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • VPC ID, 이름, CIDR 블록\n"
                   "  • 상태, 리전\n"
                   "  • 서브넷 수, 라우트 테이블 수\n"
                   "  • 연결된 리소스 수 (인스턴스, 로드밸런서 등)\n"
                   "  • 기본 VPC 여부, 생성일\n\n"
                   "필터링 옵션:\n"
                   "  --name: VPC 이름으로 필터링\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_vpc_info_parser.add_argument("--name", help="VPC 이름 필터 (부분 일치)")
    ncp_vpc_info_parser.add_argument("--verbose", "-v", action="store_true", 
                                   help="상세 정보 표시 (서브넷 및 라우트 테이블 포함)")
    ncp_vpc_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                   help="출력 형식: table (기본값), json")
    ncp_vpc_info_parser.add_argument("--profile", default='default', 
                                   help="사용할 NCP 프로필 (기본값: default)")
    ncp_vpc_info_parser.set_defaults(func=lambda args: ncp_vpc_info.ncp_vpc_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile,
        verbose=args.verbose
    ))

    # NCP Security Group commands
    ncp_sg_parser = ncp_subparsers.add_parser(
        "sg", 
        help="NCP Security Group 관련 명령어",
        description="NCP 보안 그룹(Access Control Group) 관리\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: 보안 그룹 목록 및 상세 정보 조회\n\n"
                   "예시:\n"
                   "  ic ncp sg info                     # 모든 보안 그룹 조회\n"
                   "  ic ncp sg info --name web          # 이름에 'web' 포함된 보안 그룹\n"
                   "  ic ncp sg info --verbose           # 규칙 포함 상세 정보\n"
                   "  ic ncp sg info --format json       # JSON 형식으로 출력\n"
                   "  ic ncp sg info --profile prod      # 특정 프로필 사용",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_sg_subparsers = ncp_sg_parser.add_subparsers(dest="command", required=True)
    ncp_sg_info_parser = ncp_sg_subparsers.add_parser(
        "info", 
        help="NCP Security Group 정보 조회",
        description="NCP 보안 그룹의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • 보안 그룹 ID, 이름, 설명\n"
                   "  • 상태, 플랫폼 타입, VPC 정보\n"
                   "  • 인바운드/아웃바운드 규칙 수\n"
                   "  • 생성일\n\n"
                   "상세 모드 (--verbose):\n"
                   "  • 모든 보안 그룹 규칙 상세 정보\n"
                   "  • 프로토콜, 포트, 소스/대상 IP\n"
                   "  • 규칙 설명\n\n"
                   "필터링 옵션:\n"
                   "  --name: 보안 그룹 이름으로 필터링\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_sg_info_parser.add_argument("--name", help="보안 그룹 이름 필터 (부분 일치)")
    ncp_sg_info_parser.add_argument("--verbose", "-v", action="store_true", 
                                   help="상세 정보 표시 (규칙 포함)")
    ncp_sg_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                   help="출력 형식: table (기본값), json")
    ncp_sg_info_parser.add_argument("--profile", default='default', 
                                   help="사용할 NCP 프로필 (기본값: default)")
    ncp_sg_info_parser.set_defaults(func=lambda args: ncp_sg_info.ncp_sg_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile,
        verbose=args.verbose
    ))

    # NCP RDS commands
    ncp_rds_parser = ncp_subparsers.add_parser(
        "rds", 
        help="NCP RDS 관련 명령어",
        description="NCP Cloud DB (RDS) 관리\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: 데이터베이스 인스턴스 목록 및 상세 정보 조회\n\n"
                   "예시:\n"
                   "  ic ncp rds info                    # 모든 데이터베이스 조회\n"
                   "  ic ncp rds info --name mysql       # 이름에 'mysql' 포함된 DB\n"
                   "  ic ncp rds info --verbose          # 상세 정보 표시\n"
                   "  ic ncp rds info --format json      # JSON 형식으로 출력\n"
                   "  ic ncp rds info --profile prod     # 특정 프로필 사용",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_rds_subparsers = ncp_rds_parser.add_subparsers(dest="command", required=True)
    ncp_rds_info_parser = ncp_rds_subparsers.add_parser(
        "info", 
        help="NCP RDS 인스턴스 정보 조회",
        description="NCP Cloud DB 인스턴스의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • 인스턴스 ID, 서비스 이름, 상태\n"
                   "  • 엔진 버전, 라이선스 모델\n"
                   "  • 포트, 백업 설정\n"
                   "  • 스토리지 타입, 크기\n"
                   "  • CPU, 메모리 정보\n"
                   "  • 생성 날짜\n\n"
                   "필터링 옵션:\n"
                   "  --name: 데이터베이스 이름으로 필터링\n"
                   "  --verbose: 상세 정보 표시\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncp_rds_info_parser.add_argument("--name", help="데이터베이스 이름 필터 (부분 일치)")
    ncp_rds_info_parser.add_argument("--verbose", "-v", action="store_true", 
                                   help="상세 정보 표시 (전체 컬럼 표시)")
    ncp_rds_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                   help="출력 형식: table (기본값), json")
    ncp_rds_info_parser.add_argument("--profile", default='default', 
                                   help="사용할 NCP 프로필 (기본값: default)")
    ncp_rds_info_parser.set_defaults(func=lambda args: ncp_rds_info.ncp_rds_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile,
        verbose=args.verbose
    ))

    # ---------------- NCP Gov ----------------
    # NCP Gov EC2 commands
    ncpgov_ec2_parser = ncpgov_subparsers.add_parser(
        "ec2", 
        help="NCP Gov EC2 관련 명령어",
        description="NCP 정부 클라우드 서버 인스턴스 관리 (보안 강화)\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: 인스턴스 목록 및 상세 정보 조회\n\n"
                   "보안 특징:\n"
                   "  • 민감한 IP 정보 자동 마스킹\n"
                   "  • 정부 클라우드 보안 정책 준수 검증\n"
                   "  • 감사 로그 자동 기록\n"
                   "  • 보안 상태 및 규정 준수 상태 표시\n\n"
                   "예시:\n"
                   "  ic ncpgov ec2 info                 # 모든 인스턴스 조회\n"
                   "  ic ncpgov ec2 info --name secure   # 이름에 'secure' 포함된 인스턴스\n"
                   "  ic ncpgov ec2 info --format json   # JSON 형식으로 출력",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_ec2_subparsers = ncpgov_ec2_parser.add_subparsers(dest="command", required=True)
    ncpgov_ec2_info_parser = ncpgov_ec2_subparsers.add_parser(
        "info", 
        help="NCP Gov EC2 인스턴스 정보 조회",
        description="NCP 정부 클라우드 EC2 인스턴스의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • 인스턴스 ID, 이름, 상태\n"
                   "  • 인스턴스 타입, 플랫폼\n"
                   "  • 공인/사설 IP 주소 (마스킹됨)\n"
                   "  • VPC, 서브넷 정보\n"
                   "  • 보안 상태, 규정 준수 상태\n"
                   "  • 생성 날짜\n\n"
                   "보안 기능:\n"
                   "  • 민감한 정보 자동 마스킹\n"
                   "  • 정부 클라우드 보안 정책 검증\n"
                   "  • 감사 로그 기록\n\n"
                   "필터링 옵션:\n"
                   "  --name: 인스턴스 이름으로 필터링\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP Gov 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_ec2_info_parser.add_argument("--name", help="인스턴스 이름 필터 (부분 일치)")
    ncpgov_ec2_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                      help="출력 형식: table (기본값), json")
    ncpgov_ec2_info_parser.add_argument("--profile", default='default', 
                                      help="사용할 NCP Gov 프로필 (기본값: default)")
    ncpgov_ec2_info_parser.set_defaults(func=ncpgov_ec2_info.main)

    # NCP Gov S3 commands
    ncpgov_s3_parser = ncpgov_subparsers.add_parser(
        "s3", 
        help="NCP Gov S3 관련 명령어",
        description="NCP 정부 클라우드 오브젝트 스토리지 관리 (보안 강화)\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: 버킷 목록 및 상세 정보 조회\n\n"
                   "보안 특징:\n"
                   "  • 정부 클라우드 보안 정책 준수 검증\n"
                   "  • 네트워크 재시도 로직 (지수 백오프)\n"
                   "  • 감사 로그 자동 기록\n"
                   "  • 보안 등급 및 규정 준수 상태 표시\n\n"
                   "예시:\n"
                   "  ic ncpgov s3 info                  # 모든 버킷 조회\n"
                   "  ic ncpgov s3 info --name secure    # 이름에 'secure' 포함된 버킷\n"
                   "  ic ncpgov s3 info --format json    # JSON 형식으로 출력",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_s3_subparsers = ncpgov_s3_parser.add_subparsers(dest="command", required=True)
    ncpgov_s3_info_parser = ncpgov_s3_subparsers.add_parser(
        "info", 
        help="NCP Gov S3 버킷 정보 조회",
        description="NCP 정부 클라우드 S3 버킷의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • 버킷 이름, 리전, 생성일\n"
                   "  • 객체 수, 총 크기\n"
                   "  • 스토리지 클래스 (정부 클라우드 전용)\n"
                   "  • 접근 제어 설정\n"
                   "  • 버전 관리, 암호화 상태\n"
                   "  • 보안 등급, 규정 준수 상태\n"
                   "  • 감사 상태\n\n"
                   "보안 기능:\n"
                   "  • 정부 클라우드 보안 정책 검증\n"
                   "  • 네트워크 재시도 로직\n"
                   "  • 감사 로그 기록\n\n"
                   "필터링 옵션:\n"
                   "  --name: 버킷 이름으로 필터링\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP Gov 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_s3_info_parser.add_argument("--name", help="버킷 이름 필터 (부분 일치)")
    ncpgov_s3_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                     help="출력 형식: table (기본값), json")
    ncpgov_s3_info_parser.add_argument("--profile", default='default', 
                                     help="사용할 NCP Gov 프로필 (기본값: default)")
    ncpgov_s3_info_parser.set_defaults(func=lambda args: ncpgov_s3_info.ncpgov_s3_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile
    ))

    # NCP Gov VPC commands
    ncpgov_vpc_parser = ncpgov_subparsers.add_parser(
        "vpc", 
        help="NCP Gov VPC 관련 명령어",
        description="NCP 정부 클라우드 가상 네트워크 관리 (보안 강화)\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: VPC 목록 및 상세 정보 조회\n\n"
                   "보안 특징:\n"
                   "  • 정부 네트워크 정책 준수 검증\n"
                   "  • 민감한 네트워크 정보 자동 마스킹\n"
                   "  • 감사 로그 자동 기록\n"
                   "  • 정책 준수 상태 및 보안 등급 표시\n\n"
                   "예시:\n"
                   "  ic ncpgov vpc info                 # 모든 VPC 조회\n"
                   "  ic ncpgov vpc info --name gov      # 이름에 'gov' 포함된 VPC\n"
                   "  ic ncpgov vpc info --format json   # JSON 형식으로 출력",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_vpc_subparsers = ncpgov_vpc_parser.add_subparsers(dest="command", required=True)
    ncpgov_vpc_info_parser = ncpgov_vpc_subparsers.add_parser(
        "info", 
        help="NCP Gov VPC 정보 조회",
        description="NCP 정부 클라우드 VPC의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • VPC ID, 이름, CIDR 블록 (마스킹됨)\n"
                   "  • 상태, 리전\n"
                   "  • 서브넷 수, 라우트 테이블 수\n"
                   "  • 연결된 리소스 수\n"
                   "  • 정책 준수 상태, 보안 등급\n"
                   "  • 정부 승인 상태, 네트워크 보안 상태\n"
                   "  • 기본 VPC 여부, 생성일\n\n"
                   "보안 기능:\n"
                   "  • 정부 네트워크 정책 준수 검증\n"
                   "  • 민감한 네트워크 정보 마스킹\n"
                   "  • 감사 로그 기록\n\n"
                   "필터링 옵션:\n"
                   "  --name: VPC 이름으로 필터링\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP Gov 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_vpc_info_parser.add_argument("--name", help="VPC 이름 필터 (부분 일치)")
    ncpgov_vpc_info_parser.add_argument("--verbose", "-v", action="store_true", 
                                      help="상세 정보 표시 (서브넷 및 라우트 테이블 포함)")
    ncpgov_vpc_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                      help="출력 형식: table (기본값), json")
    ncpgov_vpc_info_parser.add_argument("--profile", default='default', 
                                      help="사용할 NCP Gov 프로필 (기본값: default)")
    ncpgov_vpc_info_parser.set_defaults(func=lambda args: ncpgov_vpc_info.ncpgov_vpc_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile,
        verbose=args.verbose
    ))

    # NCP Gov Security Group commands
    ncpgov_sg_parser = ncpgov_subparsers.add_parser(
        "sg", 
        help="NCP Gov Security Group 관련 명령어",
        description="NCP 정부 클라우드 보안 그룹(Access Control Group) 관리 (보안 강화)\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: 보안 그룹 목록 및 상세 정보 조회\n\n"
                   "보안 특징:\n"
                   "  • API Gateway를 통한 보안 강화된 접근\n"
                   "  • 민감한 정보 자동 마스킹\n"
                   "  • 감사 로그 자동 기록\n"
                   "  • 정부 클라우드 규정 준수\n\n"
                   "예시:\n"
                   "  ic ncpgov sg info                  # 모든 보안 그룹 조회\n"
                   "  ic ncpgov sg info --name secure    # 이름에 'secure' 포함된 보안 그룹\n"
                   "  ic ncpgov sg info --verbose        # 규칙 포함 상세 정보\n"
                   "  ic ncpgov sg info --format json    # JSON 형식으로 출력\n"
                   "  ic ncpgov sg info --profile gov    # 정부 클라우드 프로필 사용",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_sg_subparsers = ncpgov_sg_parser.add_subparsers(dest="command", required=True)
    ncpgov_sg_info_parser = ncpgov_sg_subparsers.add_parser(
        "info", 
        help="NCP Gov Security Group 정보 조회",
        description="NCP 정부 클라우드 보안 그룹의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • 보안 그룹 ID, 이름, 설명 (마스킹 적용)\n"
                   "  • 상태, 플랫폼 타입, VPC 정보\n"
                   "  • 인바운드/아웃바운드 규칙 수\n"
                   "  • 생성일\n\n"
                   "상세 모드 (--verbose):\n"
                   "  • 모든 보안 그룹 규칙 상세 정보\n"
                   "  • 프로토콜, 포트, 소스/대상 IP (마스킹 적용)\n"
                   "  • 규칙 설명\n\n"
                   "보안 기능:\n"
                   "  • 민감한 IP 주소 자동 마스킹\n"
                   "  • 감사 로그 자동 기록\n"
                   "  • 정부 클라우드 보안 정책 준수\n\n"
                   "필터링 옵션:\n"
                   "  --name: 보안 그룹 이름으로 필터링\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP Gov 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_sg_info_parser.add_argument("--name", help="보안 그룹 이름 필터 (부분 일치)")
    ncpgov_sg_info_parser.add_argument("--verbose", "-v", action="store_true", 
                                      help="상세 정보 표시 (규칙 포함)")
    ncpgov_sg_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                      help="출력 형식: table (기본값), json")
    ncpgov_sg_info_parser.add_argument("--profile", default='default', 
                                      help="사용할 NCP Gov 프로필 (기본값: default)")
    ncpgov_sg_info_parser.set_defaults(func=lambda args: ncpgov_sg_info.ncpgov_sg_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile,
        verbose=args.verbose
    ))

    # NCP Gov RDS commands
    ncpgov_rds_parser = ncpgov_subparsers.add_parser(
        "rds", 
        help="NCP Gov RDS 관련 명령어",
        description="NCP 정부 클라우드 RDS 데이터베이스 관리 (보안 강화)\n\n"
                   "사용 가능한 명령어:\n"
                   "  info: 데이터베이스 인스턴스 목록 및 상세 정보 조회\n\n"
                   "보안 특징:\n"
                   "  • API Gateway를 통한 보안 강화된 접근\n"
                   "  • 민감한 정보 자동 마스킹\n"
                   "  • 감사 로그 자동 기록\n"
                   "  • 정부 클라우드 규정 준수\n"
                   "  • 데이터베이스 암호화 상태 표시\n\n"
                   "예시:\n"
                   "  ic ncpgov rds info                 # 모든 데이터베이스 조회\n"
                   "  ic ncpgov rds info --name secure   # 이름에 'secure' 포함된 DB\n"
                   "  ic ncpgov rds info --verbose       # 상세 정보 표시\n"
                   "  ic ncpgov rds info --format json   # JSON 형식으로 출력\n"
                   "  ic ncpgov rds info --profile gov   # 정부 클라우드 프로필 사용",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_rds_subparsers = ncpgov_rds_parser.add_subparsers(dest="command", required=True)
    ncpgov_rds_info_parser = ncpgov_rds_subparsers.add_parser(
        "info", 
        help="NCP Gov RDS 인스턴스 정보 조회",
        description="NCP 정부 클라우드 RDS 인스턴스의 상세 정보를 조회합니다.\n\n"
                   "출력 정보:\n"
                   "  • 인스턴스 ID, 서비스 이름 (마스킹됨), 상태\n"
                   "  • 엔진 버전, 라이선스 모델\n"
                   "  • 포트, 백업 설정\n"
                   "  • 스토리지 타입, 크기\n"
                   "  • 암호화 상태 (데이터/백업)\n"
                   "  • 보안 등급, 규정 준수 상태\n"
                   "  • 생성 날짜\n\n"
                   "보안 기능:\n"
                   "  • 민감한 데이터베이스 정보 자동 마스킹\n"
                   "  • 감사 로그 자동 기록\n"
                   "  • 정부 클라우드 보안 정책 준수\n\n"
                   "필터링 옵션:\n"
                   "  --name: 데이터베이스 이름으로 필터링\n"
                   "  --verbose: 상세 정보 표시\n"
                   "  --format: 출력 형식 (table/json)\n"
                   "  --profile: 사용할 NCP Gov 프로필",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ncpgov_rds_info_parser.add_argument("--name", help="데이터베이스 이름 필터 (부분 일치)")
    ncpgov_rds_info_parser.add_argument("--verbose", "-v", action="store_true", 
                                      help="상세 정보 표시 (전체 컬럼 표시)")
    ncpgov_rds_info_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                                      help="출력 형식: table (기본값), json")
    ncpgov_rds_info_parser.add_argument("--profile", default='default', 
                                      help="사용할 NCP Gov 프로필 (기본값: default)")
    ncpgov_rds_info_parser.add_argument("--mask-sensitive", action="store_true", default=True,
                                      help="민감한 정보 마스킹 활성화 (정부 클라우드 기본값)")
    ncpgov_rds_info_parser.set_defaults(func=lambda args: ncpgov_rds_info.ncpgov_rds_info_command(
        name_filter=args.name, 
        output_format=args.format, 
        profile=args.profile,
        verbose=args.verbose,
        mask_sensitive=args.mask_sensitive
    ))

    # ---------------- OCI ----------------
    oci_info_parser = oci_subparsers.add_parser("info", help="[DEPRECATED] OCI 리소스 통합 조회. 각 서비스별 명령어를 사용하세요.")
    oci_info_parser.set_defaults(func=oci_info_deprecated)
    
    # ---- new structured services ----
    vm_parser = oci_subparsers.add_parser("vm", help="OCI VM(Instance) 관련")
    vm_sub = vm_parser.add_subparsers(dest="command", required=True)
    vm_info_p = vm_sub.add_parser("info", help="VM 정보 조회")
    vm_add_args(vm_info_p)
    vm_info_p.set_defaults(func=vm_main)

    lb_parser = oci_subparsers.add_parser("lb", help="OCI LoadBalancer 관련")
    lb_sub = lb_parser.add_subparsers(dest="command", required=True)
    lb_info_p = lb_sub.add_parser("info", help="LB 정보 조회")
    lb_add_args(lb_info_p)
    lb_info_p.set_defaults(func=lb_main)

    nsg_parser = oci_subparsers.add_parser("nsg", help="OCI NSG 관련")
    nsg_sub = nsg_parser.add_subparsers(dest="command", required=True)
    nsg_info_p = nsg_sub.add_parser("info", help="NSG 정보 조회")
    nsg_add_args(nsg_info_p)
    nsg_info_p.set_defaults(func=nsg_main)

    vcn_parser = oci_subparsers.add_parser("vcn", help="OCI VCN 관련")
    vcn_sub = vcn_parser.add_subparsers(dest="command", required=True)
    vcn_info_p = vcn_sub.add_parser("info", help="VCN, Subnet, Route Table 정보 조회")
    vcn_info.add_arguments(vcn_info_p)
    vcn_info_p.set_defaults(func=vcn_info.main)

    vol_parser = oci_subparsers.add_parser("volume", help="OCI Block/Boot Volume 관련")
    vol_sub = vol_parser.add_subparsers(dest="command", required=True)
    vol_info_p = vol_sub.add_parser("info", help="Volume 정보 조회")
    volume_add_args(vol_info_p)
    vol_info_p.set_defaults(func=volume_main)

    obj_parser = oci_subparsers.add_parser("obj", help="OCI Object Storage 관련")
    obj_sub = obj_parser.add_subparsers(dest="command", required=True)
    obj_info_p = obj_sub.add_parser("info", help="Bucket 정보 조회")
    obj_add_args(obj_info_p)
    obj_info_p.set_defaults(func=obj_main)

    pol_parser = oci_subparsers.add_parser("policy", help="OCI Policy 관련")
    pol_sub = pol_parser.add_subparsers(dest="command", required=True)
    pol_info_p = pol_sub.add_parser("info", help="Policy 목록/구문 조회")
    policy_add_args(pol_info_p)
    pol_info_p.set_defaults(func=policy_main)
    pol_search_p = pol_sub.add_parser("search", help="Policy 구문 검색")
    oci_policy_search.add_arguments(pol_search_p)
    pol_search_p.set_defaults(func=oci_policy_search.main)

    cost_parser = oci_subparsers.add_parser("cost", help="OCI 비용/크레딧 관련")
    cost_sub = cost_parser.add_subparsers(dest="command", required=True)
    cost_usage_p = cost_sub.add_parser("usage", help="비용 조회")
    cost_usage_add_args(cost_usage_p)
    cost_usage_p.set_defaults(func=cost_usage_main)
    cost_credit_p = cost_sub.add_parser("credit", help="크레딧 사용 조회")
    cost_credit_add_args(cost_credit_p)
    cost_credit_p.set_defaults(func=cost_credit_main)

    # OCI Compartment 관련 명령어
    # OCI comp (compartment) command
    comp_parser = oci_subparsers.add_parser("comp", help="OCI Compartment 정보 조회")
    comp_sub = comp_parser.add_subparsers(dest="command", required=True)
    comp_info_p = comp_sub.add_parser("info", help="Compartment 계층 구조를 트리 형태로 표시")
    comp_info_p.add_argument("--config-file", help="OCI 설정 파일 경로")
    comp_info_p.add_argument("--profile", help="사용할 OCI 프로파일", default="DEFAULT")
    comp_info_p.set_defaults(func=handle_oci_compartment_info)

    # 인수 처리
    process_and_execute_commands(parser)

def process_and_execute_commands(parser):
    """명령행 인수를 파싱하고 각 서비스에 대해 명령을 실행합니다."""
    if len(sys.argv) > 2 and sys.argv[1] == 'oci' and sys.argv[2] == 'info':
        oci_info_deprecated(None)
        sys.exit(0)
        
    if len(sys.argv) > 2 and ',' in sys.argv[2]:
        platform = sys.argv[1]
        services = [s.strip() for s in sys.argv[2].split(',')]
        command_and_options = sys.argv[3:]
        
        # For GCP multi-service commands, use parallel execution
        if platform == 'gcp':
            execute_gcp_multi_service(services, command_and_options, parser)
        else:
            # Sequential execution for other platforms
            has_error = False
            for service in services:
                print(f"--- Executing: ic {platform} {service} {' '.join(command_and_options)} ---")
                current_argv = [platform, service] + command_and_options
                try:
                    args = parser.parse_args(current_argv)
                    execute_single_command(args)
                except SystemExit:
                    print(f"--- Skipping service '{service}' due to an error or invalid arguments ---")
                    has_error = True
                except Exception as e:
                    # Initialize IC logger for error logging
                    try:
                        config_manager = get_config_manager()
                        config = config_manager.get_config()
                        try:
                            from .core.logging import ICLogger
                        except ImportError:
                            from ic.core.logging import ICLogger
                        ic_logger = ICLogger(config)
                        ic_logger.log_error(f"Error processing service '{service}': {e}")
                    except:
                        print(f"ERROR: Error processing service '{service}': {e}")
                    has_error = True
            
            if has_error:
                sys.exit(1)
            
    else:
        try:
            args = parser.parse_args()
            execute_single_command(args)
        except SystemExit:
            sys.exit(0)
        except Exception as e:
            # Initialize IC logger for error logging
            try:
                config_manager = get_config_manager()
                config = config_manager.get_config()
                try:
                    from .core.logging import ICLogger
                except ImportError:
                    from ic.core.logging import ICLogger
                ic_logger = ICLogger(config)
                ic_logger.log_error(f"명령어 실행 중 오류 발생: {e}")
            except:
                print(f"ERROR: 명령어 실행 중 오류 발생: {e}")
            sys.exit(1)

def _show_ncp_help_message():
    """NCP 설정 도움말 메시지를 표시합니다."""
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    
    help_panel = Panel(
        "[yellow]NCP 설정이 필요합니다.[/yellow]\n\n"
        "다음 명령어로 NCP 설정을 생성하세요:\n"
        "[bold cyan]ic config init[/bold cyan]\n\n"
        "설정 파일 위치: [dim]~/.ncp/config[/dim]\n"
        "필수 설정 항목:\n"
        "  - access_key: NCP Access Key\n"
        "  - secret_key: NCP Secret Key\n"
        "  - region: KR (기본값)\n\n"
        "사용 예시:\n"
        "  [cyan]ic ncp ec2 info[/cyan]                    # EC2 인스턴스 목록\n"
        "  [cyan]ic ncp ec2 info --name web[/cyan]         # 이름 필터링\n"
        "  [cyan]ic ncp s3 info --format json[/cyan]       # JSON 형식 출력\n"
        "  [cyan]ic ncp vpc info --profile prod[/cyan]     # 특정 프로필 사용",
        title="NCP (Naver Cloud Platform) 설정 안내",
        border_style="yellow"
    )
    console.print()
    console.print(help_panel)

def _show_ncpgov_help_message():
    """정부 클라우드 설정 도움말 메시지를 표시합니다."""
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    
    help_panel = Panel(
        "[yellow]NCP Gov 설정이 필요합니다.[/yellow]\n\n"
        "다음 명령어로 정부 클라우드 설정을 생성하세요:\n"
        "[bold cyan]ic config init[/bold cyan]\n\n"
        "설정 파일 위치: [dim]~/.ncpgov/config[/dim]\n"
        "보안 요구사항: 파일 권한 600 필수\n"
        "필수 설정 항목:\n"
        "  - access_key: NCP Gov Access Key\n"
        "  - secret_key: NCP Gov Secret Key\n"
        "  - region: KR (기본값)\n"
        "  - encryption_enabled: true\n"
        "  - audit_logging_enabled: true\n"
        "  - access_control_enabled: true\n\n"
        "사용 예시:\n"
        "  [cyan]ic ncpgov ec2 info[/cyan]                 # 정부 클라우드 EC2 인스턴스\n"
        "  [cyan]ic ncpgov s3 info --name secure[/cyan]    # 보안 버킷 필터링\n"
        "  [cyan]ic ncpgov vpc info --format json[/cyan]   # 정부 VPC JSON 출력",
        title="NCP Government Cloud 설정 안내",
        border_style="yellow"
    )
    console.print()
    console.print(help_panel)

def execute_single_command(args):
    """파싱된 인수를 기반으로 실제 단일 명령을 실행합니다."""
    # Handle config commands specially (they don't have 'service' attribute)
    if args.platform == 'config':
        if hasattr(args, 'func'):
            args.func(args)
        return
    
    if not hasattr(args, 'service') or not args.service:
        return

    if args.platform == "ssh" and args.service == "info":
        args.command = "none"
    elif args.platform == "oci" and args.service == "info":
        args.command = "none"

    # Use new IC logger system
    config_manager = get_config_manager()
    config = config_manager.get_config()
    
    # Initialize IC logger with config
    try:
        from .core.logging import ICLogger
    except ImportError:
        from ic.core.logging import ICLogger
    ic_logger = ICLogger(config)
    
    # Log arguments using new system
    ic_logger.log_args(args)
    
    # Log relevant configuration if needed (optional)
    if hasattr(args, 'debug') and args.debug:
        platform_config = config.get(args.platform, {})
        if platform_config:
            config_str = str(platform_config)[:100] + "..." if len(str(platform_config)) > 100 else str(platform_config)
            ic_logger.log_info_file_only(f"{args.platform}_config: {config_str}")

    # Handle config commands specially
    if args.platform == 'config':
        if hasattr(args, 'func'):
            args.func(args)
        else:
            log_error(f"Config command not specified. Use 'ic config --help' for available commands.")
            raise ValueError("No config function to execute")
    elif hasattr(args, 'func'):
        # Add consistent error handling for GCP services
        if args.platform == 'gcp':
            try:
                args.func(args)
            except ImportError as e:
                ic_logger.log_error(f"GCP service '{args.service}' dependencies not available: {e}")
                raise
            except Exception as e:
                ic_logger.log_error(f"GCP service '{args.service}' execution failed: {e}")
                raise
        # Add consistent error handling for NCP services
        elif args.platform == 'ncp':
            try:
                args.func(args)
            except ImportError as e:
                ic_logger.log_error(f"NCP service '{args.service}' dependencies not available: {e}")
                from rich.console import Console
                console = Console()
                console.print(f"[red]NCP 서비스 '{args.service}' 의존성을 찾을 수 없습니다: {e}[/red]")
                console.print("\n💡 NCP SDK 설치가 필요합니다:")
                console.print("   pip install ncloud-sdk-python")
                _show_ncp_help_message()
                raise
            except Exception as e:
                ic_logger.log_error(f"NCP service '{args.service}' execution failed: {e}")
                if "authentication" in str(e).lower() or "config" in str(e).lower():
                    _show_ncp_help_message()
                raise
        # Add consistent error handling for NCP Gov services
        elif args.platform == 'ncpgov':
            try:
                args.func(args)
            except ImportError as e:
                ic_logger.log_error(f"NCP Gov service '{args.service}' dependencies not available: {e}")
                from rich.console import Console
                console = Console()
                console.print(f"[red]NCP Gov 서비스 '{args.service}' 의존성을 찾을 수 없습니다: {e}[/red]")
                console.print("\n💡 NCP Gov SDK 설치가 필요합니다:")
                console.print("   pip install ncloud-sdk-python")
                _show_ncpgov_help_message()
                raise
            except Exception as e:
                ic_logger.log_error(f"NCP Gov service '{args.service}' execution failed: {e}")
                if "authentication" in str(e).lower() or "config" in str(e).lower() or "compliance" in str(e).lower():
                    _show_ncpgov_help_message()
                raise
        else:
            args.func(args)
    else:
        log_error(f"'{args.service}' 서비스에 대해 실행할 명령어가 지정되지 않았습니다. 'ic {args.platform} {args.service} --help'를 확인하세요.")
        raise ValueError("No function to execute")

if __name__ == "__main__":
    main()
