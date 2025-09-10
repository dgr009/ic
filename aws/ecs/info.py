#!/usr/bin/env python3
import os
import sys
import argparse
import json
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule

from common.log import log_info_non_console, log_error
from common.progress_decorator import ManualProgress
from common.utils import (
    get_env_accounts,
    get_profiles,
    DEFINED_REGIONS,
    create_session
)

load_dotenv()
console = Console()

def fetch_ecs_cluster_info(account_id, profile_name, region_name, cluster_name_filter=None):
    """ECS 클러스터 정보를 수집합니다."""
    log_info_non_console(f"ECS 클러스터 정보 수집 시작: Account={account_id}, Region={region_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    ecs_client = session.client("ecs", region_name=region_name)
    
    try:
        # 클러스터 목록 조회
        clusters_response = ecs_client.list_clusters()
        cluster_arns = clusters_response.get('clusterArns', [])
        
        if not cluster_arns:
            return []
        
        # 클러스터 상세 정보 조회
        clusters_detail = ecs_client.describe_clusters(clusters=cluster_arns, include=['STATISTICS'])
        clusters = clusters_detail.get('clusters', [])
        
        # 클러스터 이름 필터링
        if cluster_name_filter:
            clusters = [c for c in clusters if cluster_name_filter.lower() in c['clusterName'].lower()]
        
        cluster_info_list = []
        
        for cluster in clusters:
            cluster_name = cluster['clusterName']
            
            try:
                # 서비스 목록 조회
                services_response = ecs_client.list_services(cluster=cluster_name)
                service_arns = services_response.get('serviceArns', [])
                service_count = len(service_arns)
                
                # 태스크 목록 조회 (모든 상태)
                tasks_response = ecs_client.list_tasks(cluster=cluster_name)
                task_arns = tasks_response.get('taskArns', [])
                
                # 태스크 상태별 개수 계산
                task_status_counts = defaultdict(int)
                if task_arns:
                    tasks_detail = ecs_client.describe_tasks(cluster=cluster_name, tasks=task_arns)
                    for task in tasks_detail.get('tasks', []):
                        last_status = task.get('lastStatus', 'UNKNOWN')
                        task_status_counts[last_status] += 1
                
                # 컨테이너 인스턴스 목록 조회
                container_instances_response = ecs_client.list_container_instances(cluster=cluster_name)
                container_instance_arns = container_instances_response.get('containerInstanceArns', [])
                container_instance_count = len(container_instance_arns)
                
                # 활성/비활성 컨테이너 인스턴스 개수
                active_instances = 0
                if container_instance_arns:
                    instances_detail = ecs_client.describe_container_instances(
                        cluster=cluster_name, 
                        containerInstances=container_instance_arns
                    )
                    for instance in instances_detail.get('containerInstances', []):
                        if instance.get('status') == 'ACTIVE':
                            active_instances += 1
                
                cluster_info = {
                    'account_id': account_id,
                    'region': region_name,
                    'cluster_name': cluster_name,
                    'cluster_arn': cluster['clusterArn'],
                    'status': cluster.get('status', 'UNKNOWN'),
                    'service_count': service_count,
                    'total_tasks': len(task_arns),
                    'task_status_counts': dict(task_status_counts),
                    'container_instance_count': container_instance_count,
                    'active_instances': active_instances,
                    'running_tasks_count': cluster.get('runningTasksCount', 0),
                    'pending_tasks_count': cluster.get('pendingTasksCount', 0),
                    'active_services_count': cluster.get('activeServicesCount', 0),
                    'statistics': cluster.get('statistics', []),
                    'tags': cluster.get('tags', [])
                }
                cluster_info_list.append(cluster_info)
                
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster_name} 상세 정보 조회 실패: {e}")
                continue
        
        return cluster_info_list
        
    except Exception as e:
        log_error(f"ECS 클러스터 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
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
        console.print("[yellow]표시할 ECS 클러스터 정보가 없습니다.[/yellow]")
        return
    
    # 클러스터 정보를 계정, 리전별로 정렬
    cluster_info_list.sort(key=lambda x: (x["account_id"], x["region"], x["cluster_name"]))
    
    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    # 테이블 컬럼 정의
    table.add_column("Account", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("Cluster Name", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Services", justify="right", style="green")
    table.add_column("Total Tasks", justify="right", style="blue")
    table.add_column("Running", justify="right", style="green")
    table.add_column("Pending", justify="right", style="yellow")
    table.add_column("Stopped", justify="right", style="red")
    table.add_column("Container Instances", justify="right", style="cyan")
    table.add_column("Active Instances", justify="right", style="green")
    
    last_account = None
    last_region = None
    
    for i, cluster in enumerate(cluster_info_list):
        account_changed = cluster["account_id"] != last_account
        region_changed = cluster["region"] != last_region
        
        # 계정이 바뀔 때 구분선 추가
        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in range(11)])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in range(10)])
        
        # 태스크 상태별 개수 추출
        task_counts = cluster.get('task_status_counts', {})
        running_count = task_counts.get('RUNNING', 0)
        pending_count = task_counts.get('PENDING', 0)
        stopped_count = task_counts.get('STOPPED', 0)
        
        # 행 데이터 구성
        display_values = [
            cluster["account_id"] if account_changed else "",
            cluster["region"] if account_changed or region_changed else "",
            cluster["cluster_name"],
            format_status(cluster["status"]),
            str(cluster["service_count"]),
            str(cluster["total_tasks"]),
            str(running_count),
            str(pending_count),
            str(stopped_count),
            str(cluster["container_instance_count"]),
            str(cluster["active_instances"])
        ]
        
        table.add_row(*display_values)
        
        last_account = cluster["account_id"]
        last_region = cluster["region"]
    
    console.print(table)

def format_status(status):
    """상태에 따라 색상을 적용합니다."""
    status_lower = status.lower()
    if status_lower == 'active':
        return f"[bold green]{status}[/bold green]"
    elif status_lower in ['inactive', 'draining']:
        return f"[bold yellow]{status}[/bold yellow]"
    elif status_lower == 'provisioning':
        return f"[bold blue]{status}[/bold blue]"
    else:
        return status

def main(args):
    """메인 함수"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    
    # Filter out accounts without valid profiles
    valid_accounts = []
    for acct in accounts:
        profile_name = profiles_map.get(acct)
        if profile_name:
            valid_accounts.append((acct, profile_name))
        else:
            log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
    
    total_operations = len(valid_accounts) * len(regions)
    all_cluster_info = []
    
    with ManualProgress("Collecting ECS cluster information across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                for reg in regions:
                    future = executor.submit(
                        fetch_ecs_cluster_info, 
                        acct, 
                        profile_name, 
                        reg, 
                        args.name
                    )
                    futures.append(future)
                    future_to_info[future] = (acct, reg)
            
            completed = 0
            for future in as_completed(futures):
                acct, reg = future_to_info[future]
                try:
                    result = future.result()
                    if result:
                        all_cluster_info.extend(result)
                    completed += 1
                    cluster_count = len(result) if result else 0
                    progress.update(f"Processed {acct}/{reg} - Found {cluster_count} ECS clusters", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect ECS data for {acct}/{reg}: {e}")
                    progress.update(f"Failed {acct}/{reg} - {str(e)[:50]}...", advance=1)
    
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
    parser = argparse.ArgumentParser(description="ECS 클러스터 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)