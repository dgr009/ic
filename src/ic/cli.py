#!/usr/bin/env python3

import argparse
import sys
import warnings

# Silence all logging except ERROR messages
from .core.silence_logging import silence_all_logging
silence_all_logging()

# Set up compatibility layer first
from .compat.cli import setup_cli_compatibility, wrap_command_function, ensure_env_compatibility
from .compat.common import log_error, log_env_short, log_args_short, gather_env_for_command

# Initialize compatibility layer
setup_cli_compatibility()

# Initialize new configuration system
from .config.manager import ConfigManager
from .config.security import SecurityManager
from .core.logging import init_logger

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
from aws.ec2 import list_tags as ec2_list_tags
from aws.ec2 import tag_check as ec2_tag_check
from aws.ec2 import info as ec2_info
from aws.lb import list_tags as lb_list_tags
from aws.lb import tag_check as lb_tag_check
from aws.vpc import tag_check as vpc_tag_check
from aws.vpc import list_tags as vpc_list_tags
from aws.rds import list_tags as rds_list_tags
from aws.rds import tag_check as rds_tag_check
from aws.s3 import list_tags as s3_list_tags
from aws.s3 import tag_check as s3_tag_check
from aws.sg import info as sg_info
from aws.eks import info as eks_info
from aws.eks import nodes as eks_nodes
from aws.eks import pods as eks_pods
from aws.eks import fargate as eks_fargate
from aws.eks import addons as eks_addons
from aws.eks import update_config as eks_update_config
from aws.fargate import info as fargate_info
from aws.codepipeline import build as codepipeline_build
from aws.codepipeline import deploy as codepipeline_deploy
from aws.ecs import info as ecs_info
from aws.ecs import service as ecs_service
from aws.ecs import task as ecs_task
from aws.msk import info as msk_info
from aws.msk import broker as msk_broker
from cf.dns import list_info as dns_info
from oci_module.info import oci_info as oci_info # Deprecated. 통합 oci info
from oci_module.vm import add_arguments as vm_add_args, main as vm_main
from oci_module.lb import add_arguments as lb_add_args, main as lb_main
from oci_module.nsg import add_arguments as nsg_add_args, main as nsg_main
from oci_module.volume import add_arguments as volume_add_args, main as volume_main
from oci_module.policy import add_arguments as policy_add_args, main as policy_main
from oci_module.policy import search as oci_policy_search
from oci_module.obj import add_arguments as obj_add_args, main as obj_main
from oci_module.cost import usage_add_arguments as cost_usage_add_args, usage_main as cost_usage_main
from oci_module.cost import credit_add_arguments as cost_credit_add_args, credit_main as cost_credit_main
from oci_module.vcn import info as vcn_info
from ssh import auto_ssh, server_info
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
    # Initialize configuration system early
    try:
        config_manager = get_config_manager()
    except Exception as e:
        print(f"Warning: Failed to initialize configuration system: {e}")
        print("Falling back to legacy configuration...")
    
    parser = argparse.ArgumentParser(
        description="Infra CLI: Platform Resource CLI Tool",
        usage="ic <platform|config> <service> <command> [options]"
    )
    platform_subparsers = parser.add_subparsers(
        dest="platform",
        required=True,
        help="클라우드 플랫폼 (aws, oci, cf, ssh, azure, gcp) 또는 config 관리"
    )
    
    # Add config commands
    from .commands.config import ConfigCommands
    config_commands = ConfigCommands()
    config_commands.add_subparsers(platform_subparsers)
    
    aws_parser = platform_subparsers.add_parser("aws", help="AWS 관련 명령어")
    oci_parser = platform_subparsers.add_parser("oci", help="OCI 관련 명령어")
    azure_parser = platform_subparsers.add_parser("azure", help="Azure 관련 명령어")
    gcp_parser = platform_subparsers.add_parser("gcp", help="GCP 관련 명령어")
    cf_parser = platform_subparsers.add_parser("cf", help="CloudFlare 관련 명령어")
    ssh_parser = platform_subparsers.add_parser("ssh", help="SSH 관련 명령어")

    aws_subparsers = aws_parser.add_subparsers(dest="service",required=True,help="AWS 리소스 관리 서비스")
    oci_subparsers = oci_parser.add_subparsers(dest="service",required=True,help="OCI 리소스 관리 서비스")
    azure_subparsers = azure_parser.add_subparsers(dest="service", required=True, help="Azure 리소스 관리 서비스")
    gcp_subparsers = gcp_parser.add_subparsers(dest="service", required=True, help="GCP 리소스 관리 서비스")
    cf_subparsers = cf_parser.add_subparsers(dest="service",required=True,help="CloudFlare 리소스 관리 서비스")
    ssh_subparsers = ssh_parser.add_subparsers(dest="service",required=True,help="SSH 관리 서비스")

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
    from aws.lb import info as lb_info
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
    from aws.vpc import info as vpc_info
    vpc_info.add_arguments(vpc_info_parser)
    vpc_info_parser.set_defaults(func=vpc_info.main)

    vpn_parser = aws_subparsers.add_parser("vpn", help="TGW, VGW, VPN Connection, Endpoint 관련 명령어")
    vpn_subparsers = vpn_parser.add_subparsers(dest="command", required=True)
    vpn_info_parser = vpn_subparsers.add_parser("info", help="VPN 관련 상세 정보 조회")
    from aws.vpn import info as vpn_info
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
    from aws.rds import info as rds_info
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
    from aws.s3 import info as s3_info
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
                    log_error(f"Error processing service '{service}': {e}")
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
            log_error(f"명령어 실행 중 오류 발생: {e}")
            sys.exit(1)

def execute_single_command(args):
    """파싱된 인수를 기반으로 실제 단일 명령을 실행합니다."""
    if not hasattr(args, 'service') or not args.service:
        return

    if args.platform == "ssh" and args.service == "info":
        args.command = "none"
    elif args.platform == "oci" and args.service == "info":
        args.command = "none"

    log_args_short(args)
    env_used = gather_env_for_command(args.platform, args.service, args.command)
    if env_used:
        log_env_short(env_used)

    if hasattr(args, 'func'):
        # Add consistent error handling for GCP services
        if args.platform == 'gcp':
            try:
                args.func(args)
            except ImportError as e:
                log_error(f"GCP service '{args.service}' dependencies not available: {e}")
                raise
            except Exception as e:
                log_error(f"GCP service '{args.service}' execution failed: {e}")
                raise
        else:
            args.func(args)
    else:
        log_error(f"'{args.service}' 서비스에 대해 실행할 명령어가 지정되지 않았습니다. 'ic {args.platform} {args.service} --help'를 확인하세요.")
        raise ValueError("No function to execute")

if __name__ == "__main__":
    main()
