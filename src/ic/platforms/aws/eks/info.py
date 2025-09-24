#!/usr/bin/env python3
import os
import sys
import argparse
import json
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

from common.log import log_info_non_console, log_error
from common.progress_decorator import progress_bar
from common.utils import (
    get_env_accounts,
    get_profiles,
    DEFINED_REGIONS,
    create_session
)

load_dotenv()
console = Console()

@progress_bar("Fetching EKS cluster information")
def fetch_eks_cluster_info(account_id, profile_name, region_name, cluster_name_filter=None):
    """EKS 클러스터 정보를 수집합니다."""
    log_info_non_console(f"EKS 클러스터 정보 수집 시작: Account={account_id}, Region={region_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    eks_client = session.client("eks", region_name=region_name)
    
    try:
        # 클러스터 목록 조회
        clusters_response = eks_client.list_clusters()
        cluster_names = clusters_response.get('clusters', [])
        
        if cluster_name_filter:
            cluster_names = [name for name in cluster_names if cluster_name_filter.lower() in name.lower()]
        
        if not cluster_names:
            return []
        
        cluster_info_list = []
        
        for cluster_name in cluster_names:
            try:
                # 클러스터 상세 정보 조회
                cluster_response = eks_client.describe_cluster(name=cluster_name)
                cluster = cluster_response['cluster']
                
                # 노드 그룹 목록 조회
                nodegroups_response = eks_client.list_nodegroups(clusterName=cluster_name)
                nodegroup_names = nodegroups_response.get('nodegroups', [])
                
                # 각 노드 그룹 상세 정보 조회
                nodegroups_info = []
                for ng_name in nodegroup_names:
                    try:
                        ng_response = eks_client.describe_nodegroup(
                            clusterName=cluster_name,
                            nodegroupName=ng_name
                        )
                        nodegroups_info.append(ng_response['nodegroup'])
                    except Exception as e:
                        log_info_non_console(f"노드 그룹 {ng_name} 정보 조회 실패: {e}")
                        continue
                
                cluster_info = {
                    'account_id': account_id,
                    'region': region_name,
                    'cluster': cluster,
                    'nodegroups': nodegroups_info
                }
                cluster_info_list.append(cluster_info)
                
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster_name} 정보 조회 실패: {e}")
                continue
        
        return cluster_info_list
        
    except Exception as e:
        log_error(f"EKS 클러스터 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

def format_output(cluster_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(cluster_info_list, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(cluster_info_list, default_flow_style=False, allow_unicode=True)
    else:
        return format_table_output(cluster_info_list)

def format_table_output(cluster_info_list):
    """테이블 형식으로 출력합니다."""
    if not cluster_info_list:
        console.print("[yellow]표시할 EKS 클러스터 정보가 없습니다.[/yellow]")
        return
    
    for cluster_info in cluster_info_list:
        cluster = cluster_info['cluster']
        nodegroups = cluster_info['nodegroups']
        
        # Cluster Overview 섹션
        console.print(f"\n[bold blue]═══ Cluster Overview ═══[/bold blue]")
        overview_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        overview_table.add_column("Field", style="cyan", no_wrap=True)
        overview_table.add_column("Value", style="white")
        
        overview_table.add_row("Cluster Name", cluster.get('name', '-'))
        overview_table.add_row("ARN", cluster.get('arn', '-'))
        overview_table.add_row("Status", format_status(cluster.get('status', '-')))
        overview_table.add_row("Kubernetes Version", cluster.get('version', '-'))
        overview_table.add_row("Platform Version", cluster.get('platformVersion', '-'))
        overview_table.add_row("Endpoint URL", cluster.get('endpoint', '-'))
        overview_table.add_row("Created At", format_datetime(cluster.get('createdAt')))
        
        console.print(overview_table)
        
        # Networking & Security 섹션
        console.print(f"\n[bold blue]═══ Networking & Security ═══[/bold blue]")
        vpc_config = cluster.get('resourcesVpcConfig', {})
        network_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        network_table.add_column("Field", style="cyan", no_wrap=True)
        network_table.add_column("Value", style="white")
        
        network_table.add_row("VPC ID", vpc_config.get('vpcId', '-'))
        network_table.add_row("Subnet IDs", ', '.join(vpc_config.get('subnetIds', [])) or '-')
        network_table.add_row("Cluster Security Group ID", vpc_config.get('clusterSecurityGroupId', '-'))
        
        console.print(network_table)
        
        # API Server Access 섹션
        console.print(f"\n[bold blue]═══ API Server Access ═══[/bold blue]")
        access_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        access_table.add_column("Field", style="cyan", no_wrap=True)
        access_table.add_column("Value", style="white")
        
        public_access = vpc_config.get('endpointPublicAccess', False)
        private_access = vpc_config.get('endpointPrivateAccess', False)
        public_cidrs = vpc_config.get('publicAccessCidrs', [])
        
        access_table.add_row("Public Access", "Enabled" if public_access else "Disabled")
        access_table.add_row("Public Access CIDRs", ', '.join(public_cidrs) if public_cidrs else '-')
        access_table.add_row("Private Access", "Enabled" if private_access else "Disabled")
        
        console.print(access_table)
        
        # Managed Node Groups 섹션
        console.print(f"\n[bold blue]═══ Managed Node Groups ═══[/bold blue]")
        if not nodegroups:
            console.print("[yellow]No managed node groups found.[/yellow]")
        else:
            ng_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            ng_table.add_column("Node Group Name", style="cyan")
            ng_table.add_column("Status", justify="center")
            ng_table.add_column("Instance Type(s)", style="white")
            ng_table.add_column("Scaling (Min/Max/Desired)", justify="center")
            ng_table.add_column("Kubernetes Version", justify="center")
            ng_table.add_column("AMI Release Version", style="white")
            
            for ng in nodegroups:
                scaling_config = ng.get('scalingConfig', {})
                scaling_text = f"{scaling_config.get('minSize', 0)}/{scaling_config.get('maxSize', 0)}/{scaling_config.get('desiredSize', 0)}"
                instance_types = ', '.join(ng.get('instanceTypes', []))
                
                ng_table.add_row(
                    ng.get('nodegroupName', '-'),
                    format_status(ng.get('status', '-')),
                    instance_types or '-',
                    scaling_text,
                    ng.get('version', '-'),
                    ng.get('releaseVersion', '-')
                )
            
            console.print(ng_table)

def format_status(status):
    """상태에 따라 색상을 적용합니다."""
    status_lower = status.lower()
    if status_lower in ['active', 'succeeded']:
        return f"[bold green]{status}[/bold green]"
    elif status_lower in ['creating', 'updating', 'deleting']:
        return f"[bold yellow]{status}[/bold yellow]"
    elif status_lower in ['failed', 'degraded']:
        return f"[bold red]{status}[/bold red]"
    else:
        return status

def format_datetime(dt):
    """datetime 객체를 문자열로 포맷합니다."""
    if dt:
        if isinstance(dt, str):
            return dt
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    return '-'

@progress_bar("Processing EKS cluster discovery across accounts and regions")
def main(args):
    """메인 함수"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    
    all_cluster_info = []
    
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            for reg in regions:
                futures.append(executor.submit(
                    fetch_eks_cluster_info, 
                    acct, 
                    profile_name, 
                    reg, 
                    args.name
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_cluster_info.extend(result)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_cluster_info, args.output)
        print(output)
    else:
        format_table_output(all_cluster_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-n', '--name', help='클러스터 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EKS 클러스터 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)