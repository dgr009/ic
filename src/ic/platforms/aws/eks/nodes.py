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

@progress_bar("Fetching EKS node information")
def fetch_eks_nodes_info(account_id, profile_name, region_name, cluster_name_filter=None):
    """EKS 노드 정보를 수집합니다."""
    log_info_non_console(f"EKS 노드 정보 수집 시작: Account={account_id}, Region={region_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    eks_client = session.client("eks", region_name=region_name)
    ec2_client = session.client("ec2", region_name=region_name)
    
    try:
        # 클러스터 목록 조회
        clusters_response = eks_client.list_clusters()
        cluster_names = clusters_response.get('clusters', [])
        
        if cluster_name_filter:
            cluster_names = [name for name in cluster_names if cluster_name_filter.lower() in name.lower()]
        
        if not cluster_names:
            return []
        
        nodes_info_list = []
        
        for cluster_name in cluster_names:
            try:
                # 노드 그룹 목록 조회
                nodegroups_response = eks_client.list_nodegroups(clusterName=cluster_name)
                nodegroup_names = nodegroups_response.get('nodegroups', [])
                
                if not nodegroup_names:
                    continue
                
                # 각 노드 그룹 상세 정보 조회
                for ng_name in nodegroup_names:
                    try:
                        ng_response = eks_client.describe_nodegroup(
                            clusterName=cluster_name,
                            nodegroupName=ng_name
                        )
                        nodegroup = ng_response['nodegroup']
                        
                        # EC2 인스턴스 정보 조회
                        instance_ids = []
                        if nodegroup.get('resources', {}).get('autoScalingGroups'):
                            for asg in nodegroup['resources']['autoScalingGroups']:
                                asg_name = asg['name']
                                try:
                                    # Auto Scaling Group의 인스턴스 조회
                                    autoscaling_client = session.client('autoscaling', region_name=region_name)
                                    asg_response = autoscaling_client.describe_auto_scaling_groups(
                                        AutoScalingGroupNames=[asg_name]
                                    )
                                    for group in asg_response.get('AutoScalingGroups', []):
                                        for instance in group.get('Instances', []):
                                            instance_ids.append(instance['InstanceId'])
                                except Exception as e:
                                    log_info_non_console(f"ASG {asg_name} 인스턴스 조회 실패: {e}")
                        
                        # EC2 인스턴스 상세 정보 조회
                        ec2_instances = []
                        if instance_ids:
                            try:
                                ec2_response = ec2_client.describe_instances(InstanceIds=instance_ids)
                                for reservation in ec2_response.get('Reservations', []):
                                    for instance in reservation.get('Instances', []):
                                        ec2_instances.append(instance)
                            except Exception as e:
                                log_info_non_console(f"EC2 인스턴스 정보 조회 실패: {e}")
                        
                        node_info = {
                            'account_id': account_id,
                            'region': region_name,
                            'cluster_name': cluster_name,
                            'nodegroup': nodegroup,
                            'ec2_instances': ec2_instances
                        }
                        nodes_info_list.append(node_info)
                        
                    except Exception as e:
                        log_info_non_console(f"노드 그룹 {ng_name} 정보 조회 실패: {e}")
                        continue
                
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster_name} 노드 정보 조회 실패: {e}")
                continue
        
        return nodes_info_list
        
    except Exception as e:
        log_error(f"EKS 노드 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

def format_output(nodes_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(nodes_info_list, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(nodes_info_list, default_flow_style=False, allow_unicode=True)
    else:
        return format_table_output(nodes_info_list)

def format_table_output(nodes_info_list):
    """테이블 형식으로 출력합니다."""
    if not nodes_info_list:
        console.print("[yellow]표시할 EKS 노드 정보가 없습니다.[/yellow]")
        return
    
    # 클러스터별로 그룹화
    clusters = {}
    for node_info in nodes_info_list:
        cluster_name = node_info['cluster_name']
        if cluster_name not in clusters:
            clusters[cluster_name] = []
        clusters[cluster_name].append(node_info)
    
    for cluster_name, cluster_nodes in clusters.items():
        console.print(f"\n[bold blue]🔹 Cluster: {cluster_name}[/bold blue]")
        
        # 노드그룹 요약 테이블
        console.print(f"\n[bold]📊 Node Groups Summary[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("Node Group", style="cyan")
        summary_table.add_column("Status", justify="center")
        summary_table.add_column("Instance Type(s)", style="white")
        summary_table.add_column("AMI Type", style="green")
        summary_table.add_column("Capacity Type", style="yellow")
        summary_table.add_column("Scaling (Min/Max/Desired)", justify="center")
        summary_table.add_column("Running Instances", justify="right", style="blue")
        summary_table.add_column("Kubernetes Version", justify="center")
        
        for node_info in cluster_nodes:
            nodegroup = node_info['nodegroup']
            ec2_instances = node_info['ec2_instances']
            
            scaling_config = nodegroup.get('scalingConfig', {})
            scaling_text = f"{scaling_config.get('minSize', 0)}/{scaling_config.get('maxSize', 0)}/{scaling_config.get('desiredSize', 0)}"
            instance_types = ', '.join(nodegroup.get('instanceTypes', []))
            
            # 실행 중인 인스턴스 개수
            running_instances = len([i for i in ec2_instances if i.get('State', {}).get('Name') == 'running'])
            
            summary_table.add_row(
                nodegroup.get('nodegroupName', '-'),
                format_status(nodegroup.get('status', '-')),
                instance_types or '-',
                nodegroup.get('amiType', '-'),
                nodegroup.get('capacityType', '-'),
                scaling_text,
                str(running_instances),
                nodegroup.get('version', '-')
            )
        
        console.print(summary_table)
        
        # 인스턴스 상세 정보
        for node_info in cluster_nodes:
            nodegroup = node_info['nodegroup']
            ec2_instances = node_info['ec2_instances']
            
            if not ec2_instances:
                continue
                
            console.print(f"\n[bold]🖥️  Node Group: {nodegroup.get('nodegroupName', 'Unknown')} - EC2 Instances[/bold]")
            
            instances_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            instances_table.add_column("Instance ID", style="cyan")
            instances_table.add_column("State", justify="center")
            instances_table.add_column("Instance Type", style="white")
            instances_table.add_column("AZ", justify="center")
            instances_table.add_column("Private IP", style="green")
            instances_table.add_column("Public IP", style="yellow")
            instances_table.add_column("Launch Time", style="dim")
            
            for instance in ec2_instances:
                state = instance.get('State', {})
                placement = instance.get('Placement', {})
                
                instances_table.add_row(
                    instance.get('InstanceId', '-'),
                    format_instance_state(state.get('Name', '-')),
                    instance.get('InstanceType', '-'),
                    placement.get('AvailabilityZone', '-'),
                    instance.get('PrivateIpAddress', '-'),
                    instance.get('PublicIpAddress', '-') or 'N/A',
                    format_datetime(instance.get('LaunchTime'))
                )
            
            console.print(instances_table)

def format_status(status):
    """노드그룹 상태에 따라 색상을 적용합니다."""
    status_lower = status.lower()
    if status_lower in ['active']:
        return f"[bold green]{status}[/bold green]"
    elif status_lower in ['creating', 'updating', 'scaling']:
        return f"[bold yellow]{status}[/bold yellow]"
    elif status_lower in ['deleting', 'create_failed', 'delete_failed']:
        return f"[bold red]{status}[/bold red]"
    elif status_lower in ['degraded']:
        return f"[bold orange]{status}[/bold orange]"
    else:
        return status

def format_instance_state(state):
    """EC2 인스턴스 상태에 따라 색상을 적용합니다."""
    state_lower = state.lower()
    if state_lower == 'running':
        return f"[bold green]{state}[/bold green]"
    elif state_lower in ['pending', 'rebooting']:
        return f"[bold yellow]{state}[/bold yellow]"
    elif state_lower in ['stopping', 'stopped', 'shutting-down', 'terminated']:
        return f"[bold red]{state}[/bold red]"
    else:
        return state

def format_datetime(dt):
    """datetime 객체를 문자열로 포맷합니다."""
    if dt:
        if isinstance(dt, str):
            return dt
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    return '-'

@progress_bar("Processing EKS node discovery across accounts and regions")
def main(args):
    """메인 함수"""
    accounts = get_env_accounts(args.account)
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    
    all_nodes_info = []
    
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            for reg in regions:
                futures.append(executor.submit(
                    fetch_eks_nodes_info, 
                    acct, 
                    profile_name, 
                    reg, 
                    args.cluster
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_nodes_info.extend(result)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_nodes_info, args.output)
        print(output)
    else:
        format_table_output(all_nodes_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-c', '--cluster', help='클러스터 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EKS 노드 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)