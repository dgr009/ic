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

def fetch_ecs_services_info(account_id, profile_name, region_name, cluster_name=None, service_name_filter=None):
    """ECS 서비스 정보를 수집합니다."""
    log_info_non_console(f"ECS 서비스 정보 수집 시작: Account={account_id}, Region={region_name}")
    
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
        
        services_info_list = []
        
        for cluster in cluster_names:
            try:
                # 서비스 목록 조회
                services_response = ecs_client.list_services(cluster=cluster)
                service_arns = services_response.get('serviceArns', [])
                
                if not service_arns:
                    continue
                
                # 서비스 상세 정보 조회
                services_detail = ecs_client.describe_services(cluster=cluster, services=service_arns)
                services = services_detail.get('services', [])
                
                # 서비스 이름 필터링
                if service_name_filter:
                    services = [s for s in services if service_name_filter.lower() in s['serviceName'].lower()]
                
                for service in services:
                    # 태스크 정의 정보 조회
                    task_def_arn = service.get('taskDefinition')
                    task_def_family = task_def_arn.split('/')[-1].split(':')[0] if task_def_arn else 'N/A'
                    task_def_revision = task_def_arn.split(':')[-1] if task_def_arn else 'N/A'
                    
                    # 로드 밸런서 정보
                    load_balancers = service.get('loadBalancers', [])
                    lb_info = []
                    for lb in load_balancers:
                        if 'loadBalancerName' in lb:
                            lb_info.append(f"CLB:{lb['loadBalancerName']}")
                        elif 'targetGroupArn' in lb:
                            tg_name = lb['targetGroupArn'].split('/')[-2] if '/' in lb['targetGroupArn'] else lb['targetGroupArn']
                            lb_info.append(f"ALB/NLB:{tg_name}")
                    
                    # 서비스 이벤트 (최근 5개)
                    events = service.get('events', [])[:5]
                    latest_event = events[0]['message'] if events else 'No recent events'
                    
                    service_info = {
                        'account_id': account_id,
                        'region': region_name,
                        'cluster_name': cluster,
                        'service_name': service['serviceName'],
                        'service_arn': service['serviceArn'],
                        'status': service.get('status', 'UNKNOWN'),
                        'running_count': service.get('runningCount', 0),
                        'pending_count': service.get('pendingCount', 0),
                        'desired_count': service.get('desiredCount', 0),
                        'task_definition_family': task_def_family,
                        'task_definition_revision': task_def_revision,
                        'launch_type': service.get('launchType', 'EC2'),
                        'platform_version': service.get('platformVersion', 'N/A'),
                        'load_balancers': lb_info,
                        'created_at': service.get('createdAt'),
                        'updated_at': service.get('updatedAt', service.get('createdAt')),
                        'latest_event': latest_event,
                        'service_registries': len(service.get('serviceRegistries', [])),
                        'enable_execute_command': service.get('enableExecuteCommand', False),
                        'tags': service.get('tags', [])
                    }
                    services_info_list.append(service_info)
                    
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster} 서비스 정보 조회 실패: {e}")
                continue
        
        return services_info_list
        
    except Exception as e:
        log_error(f"ECS 서비스 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

def format_output(services_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(services_info_list, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(services_info_list, default_flow_style=False, allow_unicode=True)
    else:
        return format_table_output(services_info_list)

def format_table_output(services_info_list):
    """테이블 형식으로 출력합니다."""
    if not services_info_list:
        console.print("[yellow]표시할 ECS 서비스 정보가 없습니다.[/yellow]")
        return
    
    # 서비스 정보를 계정, 리전, 클러스터별로 정렬
    services_info_list.sort(key=lambda x: (x["account_id"], x["region"], x["cluster_name"], x["service_name"]))
    
    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    # 테이블 컬럼 정의
    table.add_column("Account", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("Cluster", style="white")
    table.add_column("Service Name", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Desired", justify="right", style="blue")
    table.add_column("Running", justify="right", style="green")
    table.add_column("Pending", justify="right", style="yellow")
    table.add_column("Task Definition", style="cyan")
    table.add_column("Launch Type", justify="center", style="magenta")
    table.add_column("Load Balancers", style="green")
    table.add_column("Updated", style="dim")
    
    last_account = None
    last_region = None
    last_cluster = None
    
    for i, service in enumerate(services_info_list):
        account_changed = service["account_id"] != last_account
        region_changed = service["region"] != last_region
        cluster_changed = service["cluster_name"] != last_cluster
        
        # 구분선 추가
        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in range(12)])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in range(11)])
            elif cluster_changed:
                table.add_row("", "", *[Rule(style="dim") for _ in range(10)])
        
        # 태스크 정의 정보 포맷
        task_def = f"{service['task_definition_family']}:{service['task_definition_revision']}"
        
        # 로드 밸런서 정보 포맷
        lb_text = ', '.join(service['load_balancers']) if service['load_balancers'] else '-'
        if len(lb_text) > 30:
            lb_text = lb_text[:27] + "..."
        
        # 업데이트 시간 포맷
        updated_time = format_datetime(service['updated_at'])
        
        # 행 데이터 구성
        display_values = [
            service["account_id"] if account_changed else "",
            service["region"] if account_changed or region_changed else "",
            service["cluster_name"] if account_changed or region_changed or cluster_changed else "",
            service["service_name"],
            format_status(service["status"]),
            str(service["desired_count"]),
            str(service["running_count"]),
            str(service["pending_count"]),
            task_def,
            service["launch_type"],
            lb_text,
            updated_time
        ]
        
        table.add_row(*display_values)
        
        last_account = service["account_id"]
        last_region = service["region"]
        last_cluster = service["cluster_name"]
    
    console.print(table)

def format_status(status):
    """상태에 따라 색상을 적용합니다."""
    status_lower = status.lower()
    if status_lower == 'active':
        return f"[bold green]{status}[/bold green]"
    elif status_lower in ['inactive', 'draining']:
        return f"[bold yellow]{status}[/bold yellow]"
    elif status_lower == 'pending':
        return f"[bold blue]{status}[/bold blue]"
    else:
        return status

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
    
    all_services_info = []
    
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            for reg in regions:
                futures.append(executor.submit(
                    fetch_ecs_services_info, 
                    acct, 
                    profile_name, 
                    reg, 
                    args.cluster,
                    args.name
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_services_info.extend(result)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_services_info, args.output)
        print(output)
    else:
        format_table_output(all_services_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('--cluster', help='특정 클러스터 이름 (없으면 모든 클러스터 조회)')
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-n', '--name', help='서비스 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ECS 서비스 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)