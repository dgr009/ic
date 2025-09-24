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

def fetch_eks_fargate_profiles(account_id, profile_name, region_name, cluster_name):
    """EKS Fargate 프로파일 정보를 수집합니다."""
    log_info_non_console(f"EKS Fargate 프로파일 정보 수집: Account={account_id}, Region={region_name}, Cluster={cluster_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    eks_client = session.client("eks", region_name=region_name)
    
    try:
        # Fargate 프로파일 목록 조회
        profiles_response = eks_client.list_fargate_profiles(clusterName=cluster_name)
        profile_names = profiles_response.get('fargateProfileNames', [])
        
        if not profile_names:
            return []
        
        profiles_info = []
        
        for profile_name_item in profile_names:
            try:
                # Fargate 프로파일 상세 정보 조회
                profile_response = eks_client.describe_fargate_profile(
                    clusterName=cluster_name,
                    fargateProfileName=profile_name_item
                )
                profile_info = profile_response['fargateProfile']
                profile_info['account_id'] = account_id
                profile_info['region'] = region_name
                profiles_info.append(profile_info)
                
            except Exception as e:
                log_info_non_console(f"Fargate 프로파일 {profile_name_item} 정보 조회 실패: {e}")
                continue
        
        return profiles_info
        
    except Exception as e:
        log_error(f"EKS Fargate 프로파일 목록 조회 실패: Account={account_id}, Region={region_name}, Cluster={cluster_name}, Error={e}")
        return []

def fetch_ecs_fargate_tasks(account_id, profile_name, region_name, cluster_name):
    """ECS Fargate 태스크 정보를 수집합니다."""
    log_info_non_console(f"ECS Fargate 태스크 정보 수집: Account={account_id}, Region={region_name}, Cluster={cluster_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    ecs_client = session.client("ecs", region_name=region_name)
    
    try:
        # Fargate 태스크 목록 조회
        tasks_response = ecs_client.list_tasks(
            cluster=cluster_name,
            launchType='FARGATE'
        )
        task_arns = tasks_response.get('taskArns', [])
        
        if not task_arns:
            return []
        
        # 태스크 상세 정보 조회
        tasks_response = ecs_client.describe_tasks(
            cluster=cluster_name,
            tasks=task_arns
        )
        
        tasks_info = []
        for task in tasks_response.get('tasks', []):
            task['account_id'] = account_id
            task['region'] = region_name
            tasks_info.append(task)
        
        return tasks_info
        
    except Exception as e:
        log_error(f"ECS Fargate 태스크 목록 조회 실패: Account={account_id}, Region={region_name}, Cluster={cluster_name}, Error={e}")
        return []

def format_output(data, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(data, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:
        return None  # 테이블 형식은 별도 함수에서 처리

def format_eks_fargate_table(profiles_info):
    """EKS Fargate 프로파일을 테이블 형식으로 출력합니다."""
    if not profiles_info:
        console.print("[yellow]표시할 EKS Fargate 프로파일이 없습니다.[/yellow]")
        return
    
    console.print(f"\n[bold blue]═══ EKS Fargate Profiles ═══[/bold blue]")
    
    table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
    table.add_column("Account", style="magenta")
    table.add_column("Region", style="cyan")
    table.add_column("Profile Name", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Pod Execution Role ARN", style="white")
    table.add_column("Subnets", style="white")
    table.add_column("Selectors", style="white")
    
    for profile in profiles_info:
        # Selectors 정보 포맷팅
        selectors = profile.get('selectors', [])
        selector_text = []
        for selector in selectors:
            namespace = selector.get('namespace', '*')
            labels = selector.get('labels', {})
            if labels:
                label_text = ', '.join([f"{k}={v}" for k, v in labels.items()])
                selector_text.append(f"ns:{namespace}, labels:{label_text}")
            else:
                selector_text.append(f"ns:{namespace}")
        
        table.add_row(
            profile.get('account_id', '-'),
            profile.get('region', '-'),
            profile.get('fargateProfileName', '-'),
            format_status(profile.get('status', '-')),
            profile.get('podExecutionRoleArn', '-'),
            ', '.join(profile.get('subnets', [])) or '-',
            '; '.join(selector_text) or '-'
        )
    
    console.print(table)

def format_ecs_fargate_table(tasks_info):
    """ECS Fargate 태스크를 테이블 형식으로 출력합니다."""
    if not tasks_info:
        console.print("[yellow]표시할 ECS Fargate 태스크가 없습니다.[/yellow]")
        return
    
    console.print(f"\n[bold blue]═══ ECS Fargate Tasks ═══[/bold blue]")
    
    table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
    table.add_column("Account", style="magenta")
    table.add_column("Region", style="cyan")
    table.add_column("Task ARN", style="white")
    table.add_column("Task Definition", style="white")
    table.add_column("Last Status", justify="center")
    table.add_column("Desired Status", justify="center")
    table.add_column("CPU", justify="right")
    table.add_column("Memory", justify="right")
    table.add_column("Created At", style="white")
    
    for task in tasks_info:
        # Task ARN에서 짧은 ID 추출
        task_arn = task.get('taskArn', '-')
        short_task_id = task_arn.split('/')[-1] if '/' in task_arn else task_arn
        
        # Task Definition에서 이름만 추출
        task_def = task.get('taskDefinitionArn', '-')
        task_def_name = task_def.split('/')[-1] if '/' in task_def else task_def
        
        table.add_row(
            task.get('account_id', '-'),
            task.get('region', '-'),
            short_task_id,
            task_def_name,
            format_status(task.get('lastStatus', '-')),
            format_status(task.get('desiredStatus', '-')),
            task.get('cpu', '-'),
            task.get('memory', '-'),
            format_datetime(task.get('createdAt'))
        )
    
    console.print(table)

def format_status(status):
    """상태에 따라 색상을 적용합니다."""
    if not status or status == '-':
        return status
        
    status_lower = status.lower()
    if status_lower in ['active', 'running', 'succeeded']:
        return f"[bold green]{status}[/bold green]"
    elif status_lower in ['creating', 'pending', 'provisioning']:
        return f"[bold yellow]{status}[/bold yellow]"
    elif status_lower in ['failed', 'stopped', 'stopping']:
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

def main(args):
    """메인 함수"""
    if not args.cluster_name:
        log_error("--cluster-name 인수가 필요합니다.")
        sys.exit(1)
    
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
    all_data = []
    
    service_type = "ECS Fargate tasks" if args.type == 'ecs' else "EKS Fargate profiles"
    with ManualProgress(f"Collecting {service_type} across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                for reg in regions:
                    if args.type == 'ecs':
                        future = executor.submit(
                            fetch_ecs_fargate_tasks, 
                            acct, 
                            profile_name, 
                            reg, 
                            args.cluster_name
                        )
                    else:  # 기본값: EKS
                        future = executor.submit(
                            fetch_eks_fargate_profiles, 
                            acct, 
                            profile_name, 
                            reg, 
                            args.cluster_name
                        )
                    futures.append(future)
                    future_to_info[future] = (acct, reg)
            
            completed = 0
            for future in as_completed(futures):
                acct, reg = future_to_info[future]
                try:
                    result = future.result()
                    if result:
                        all_data.extend(result)
                    completed += 1
                    item_count = len(result) if result else 0
                    item_type = "tasks" if args.type == 'ecs' else "profiles"
                    progress.update(f"Processed {acct}/{reg} - Found {item_count} Fargate {item_type}", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect Fargate data for {acct}/{reg}: {e}")
                    progress.update(f"Failed {acct}/{reg} - {str(e)[:50]}...", advance=1)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_data, args.output)
        print(output)
    else:
        if args.type == 'ecs':
            format_ecs_fargate_table(all_data)
        else:
            format_eks_fargate_table(all_data)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('--cluster-name', required=True, 
                       help='Fargate 프로파일/태스크를 조회할 클러스터 이름')
    parser.add_argument('--type', choices=['eks', 'ecs'], default='eks',
                       help='Fargate 컨텍스트 (기본값: eks)')
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fargate 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)