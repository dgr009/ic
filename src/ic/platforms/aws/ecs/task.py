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
from common.utils import (
    get_env_accounts,
    get_profiles,
    DEFINED_REGIONS,
    create_session
)

load_dotenv()
console = Console()

def fetch_ecs_tasks_info(account_id, profile_name, region_name, cluster_name=None, task_name_filter=None):
    """ECS 태스크 정보를 수집합니다."""
    log_info_non_console(f"ECS 태스크 정보 수집 시작: Account={account_id}, Region={region_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    ecs_client = session.client("ecs", region_name=region_name)
    
    try:
        # 클러스터 목록 조회 (특정 클러스터가 지정되지 않은 경우)
        if cluster_name:
            cluster_names = [cluster_name]
        else:
            clusters_response = ecs_client.list_clusters()
            cluster_arns = clusters_response.get('clusterArns', [])
            if not cluster_arns:
                return []
            
            # 클러스터 이름 추출
            cluster_names = []
            for arn in cluster_arns:
                cluster_names.append(arn.split('/')[-1])
        
        tasks_info_list = []
        
        for cluster in cluster_names:
            try:
                # 태스크 목록 조회 (모든 상태)
                tasks_response = ecs_client.list_tasks(cluster=cluster)
                task_arns = tasks_response.get('taskArns', [])
                
                if not task_arns:
                    continue
                
                # 태스크 상세 정보 조회 (배치로 처리)
                batch_size = 100  # AWS API 제한
                for i in range(0, len(task_arns), batch_size):
                    batch_arns = task_arns[i:i + batch_size]
                    
                    tasks_detail = ecs_client.describe_tasks(cluster=cluster, tasks=batch_arns)
                    tasks = tasks_detail.get('tasks', [])
                    
                    for task in tasks:
                        # 태스크 정의 정보
                        task_def_arn = task.get('taskDefinitionArn', '')
                        task_def_family = task_def_arn.split('/')[-1].split(':')[0] if task_def_arn else 'N/A'
                        task_def_revision = task_def_arn.split(':')[-1] if task_def_arn else 'N/A'
                        
                        # 태스크 ID (짧은 형태)
                        task_arn = task.get('taskArn', '')
                        task_id = task_arn.split('/')[-1] if task_arn else 'N/A'
                        
                        # 컨테이너 정보
                        containers = task.get('containers', [])
                        container_count = len(containers)
                        
                        # 컨테이너 상태 요약
                        container_statuses = {}
                        for container in containers:
                            status = container.get('lastStatus', 'UNKNOWN')
                            container_statuses[status] = container_statuses.get(status, 0) + 1
                        
                        # 네트워크 정보
                        attachments = task.get('attachments', [])
                        eni_id = 'N/A'
                        private_ip = 'N/A'
                        for attachment in attachments:
                            if attachment.get('type') == 'ElasticNetworkInterface':
                                for detail in attachment.get('details', []):
                                    if detail.get('name') == 'networkInterfaceId':
                                        eni_id = detail.get('value', 'N/A')
                                    elif detail.get('name') == 'privateIPv4Address':
                                        private_ip = detail.get('value', 'N/A')
                        
                        # CPU 및 메모리 정보
                        cpu = task.get('cpu', 'N/A')
                        memory = task.get('memory', 'N/A')
                        
                        # 서비스 이름 (태그에서 추출)
                        service_name = 'N/A'
                        tags = task.get('tags', [])
                        for tag in tags:
                            if tag.get('key') == 'aws:ecs:serviceName':
                                service_name = tag.get('value', 'N/A')
                                break
                        
                        # 태스크 이름 필터링
                        if task_name_filter and task_name_filter.lower() not in task_id.lower():
                            continue
                        
                        task_info = {
                            'account_id': account_id,
                            'region': region_name,
                            'cluster_name': cluster,
                            'task_id': task_id,
                            'task_arn': task_arn,
                            'service_name': service_name,
                            'task_definition_family': task_def_family,
                            'task_definition_revision': task_def_revision,
                            'last_status': task.get('lastStatus', 'UNKNOWN'),
                            'desired_status': task.get('desiredStatus', 'UNKNOWN'),
                            'health_status': task.get('healthStatus', 'UNKNOWN'),
                            'launch_type': task.get('launchType', 'EC2'),
                            'platform_version': task.get('platformVersion', 'N/A'),
                            'cpu': cpu,
                            'memory': memory,
                            'container_count': container_count,
                            'container_statuses': container_statuses,
                            'private_ip': private_ip,
                            'eni_id': eni_id,
                            'availability_zone': task.get('availabilityZone', 'N/A'),
                            'created_at': task.get('createdAt'),
                            'started_at': task.get('startedAt'),
                            'stopped_at': task.get('stoppedAt'),
                            'stop_reason': task.get('stoppedReason', 'N/A'),
                            'connectivity': task.get('connectivity', 'UNKNOWN'),
                            'connectivity_at': task.get('connectivityAt'),
                            'pull_started_at': task.get('pullStartedAt'),
                            'pull_stopped_at': task.get('pullStoppedAt'),
                            'execution_stopped_at': task.get('executionStoppedAt')
                        }
                        tasks_info_list.append(task_info)
                        
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster} 태스크 정보 조회 실패: {e}")
                continue
        
        return tasks_info_list
        
    except Exception as e:
        log_error(f"ECS 태스크 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

def format_output(tasks_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(tasks_info_list, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(tasks_info_list, default_flow_style=False, allow_unicode=True)
    else:
        return format_table_output(tasks_info_list)

def format_table_output(tasks_info_list):
    """테이블 형식으로 출력합니다."""
    if not tasks_info_list:
        console.print("[yellow]표시할 ECS 태스크 정보가 없습니다.[/yellow]")
        return
    
    # 태스크 정보를 계정, 리전, 클러스터별로 정렬
    tasks_info_list.sort(key=lambda x: (x["account_id"], x["region"], x["cluster_name"], x["task_id"]))
    
    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    # 테이블 컬럼 정의
    table.add_column("Account", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("Cluster", style="white")
    table.add_column("Task ID", style="bold white")
    table.add_column("Service", style="green")
    table.add_column("Status", justify="center")
    table.add_column("Health", justify="center")
    table.add_column("Task Definition", style="cyan")
    table.add_column("Launch Type", justify="center", style="magenta")
    table.add_column("CPU", justify="right", style="blue")
    table.add_column("Memory", justify="right", style="blue")
    table.add_column("Containers", justify="right", style="yellow")
    table.add_column("Private IP", style="dim")
    table.add_column("AZ", style="dim")
    table.add_column("Created", style="dim")
    
    last_account = None
    last_region = None
    last_cluster = None
    
    for i, task in enumerate(tasks_info_list):
        account_changed = task["account_id"] != last_account
        region_changed = task["region"] != last_region
        cluster_changed = task["cluster_name"] != last_cluster
        
        # 구분선 추가
        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in range(15)])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in range(14)])
            elif cluster_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in range(13)])
        
        # 태스크 정의 정보 포맷
        task_def = f"{task['task_definition_family']}:{task['task_definition_revision']}"
        
        # 태스크 ID 짧게 표시 (처음 8자리)
        short_task_id = task['task_id'][:8] if len(task['task_id']) > 8 else task['task_id']
        
        # 서비스 이름 짧게 표시
        service_name = task['service_name']
        if len(service_name) > 15:
            service_name = service_name[:12] + "..."
        
        # 생성 시간 포맷
        created_time = format_datetime(task['created_at'])
        
        # AZ 짧게 표시 (마지막 문자만)
        az = task['availability_zone']
        if len(az) > 3:
            az = az[-1]  # 예: us-east-1a -> a
        
        # 행 데이터 구성
        display_values = [
            task["account_id"] if account_changed else "",
            task["region"] if account_changed or region_changed else "",
            task["cluster_name"] if account_changed or region_changed or cluster_changed else "",
            short_task_id,
            service_name,
            format_status(task["last_status"]),
            format_health_status(task["health_status"]),
            task_def,
            task["launch_type"],
            str(task["cpu"]),
            str(task["memory"]),
            str(task["container_count"]),
            task["private_ip"],
            az,
            created_time
        ]
        
        table.add_row(*display_values)
        
        last_account = task["account_id"]
        last_region = task["region"]
        last_cluster = task["cluster_name"]
    
    console.print(table)

def format_status(status):
    """상태에 따라 색상을 적용합니다."""
    status_lower = status.lower()
    if status_lower == 'running':
        return f"[bold green]{status}[/bold green]"
    elif status_lower == 'pending':
        return f"[bold yellow]{status}[/bold yellow]"
    elif status_lower == 'stopped':
        return f"[bold red]{status}[/bold red]"
    elif status_lower in ['provisioning', 'activating']:
        return f"[bold blue]{status}[/bold blue]"
    elif status_lower in ['stopping', 'deactivating']:
        return f"[bold magenta]{status}[/bold magenta]"
    else:
        return status

def format_health_status(health_status):
    """헬스 상태에 따라 색상을 적용합니다."""
    if health_status == 'HEALTHY':
        return f"[bold green]✓[/bold green]"
    elif health_status == 'UNHEALTHY':
        return f"[bold red]✗[/bold red]"
    elif health_status == 'UNKNOWN':
        return f"[dim]?[/dim]"
    else:
        return health_status

def format_datetime(dt):
    """datetime 객체를 문자열로 포맷합니다."""
    if dt:
        if isinstance(dt, str):
            return dt
        return dt.strftime('%m-%d %H:%M')
    return '-'

def main(args):
    """메인 함수"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    
    all_tasks_info = []
    
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            for reg in regions:
                futures.append(executor.submit(
                    fetch_ecs_tasks_info, 
                    acct, 
                    profile_name, 
                    reg, 
                    args.cluster,
                    args.name
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_tasks_info.extend(result)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_tasks_info, args.output)
        print(output)
    else:
        format_table_output(all_tasks_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('--cluster', help='특정 클러스터 이름 (없으면 모든 클러스터 조회)')
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-n', '--name', help='태스크 ID 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ECS 태스크 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)