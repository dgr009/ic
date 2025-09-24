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

@progress_bar("Fetching EKS addon information")
def fetch_eks_addons_info(account_id, profile_name, region_name, cluster_name_filter=None):
    """EKS 애드온 정보를 수집합니다."""
    log_info_non_console(f"EKS 애드온 정보 수집 시작: Account={account_id}, Region={region_name}")
    
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
        
        addons_info_list = []
        
        for cluster_name in cluster_names:
            try:
                # 애드온 목록 조회
                addons_response = eks_client.list_addons(clusterName=cluster_name)
                addon_names = addons_response.get('addons', [])
                
                if not addon_names:
                    # 애드온이 없어도 클러스터 정보는 포함
                    addons_info_list.append({
                        'account_id': account_id,
                        'region': region_name,
                        'cluster_name': cluster_name,
                        'addons': []
                    })
                    continue
                
                # 각 애드온 상세 정보 조회
                addons_details = []
                for addon_name in addon_names:
                    try:
                        addon_response = eks_client.describe_addon(
                            clusterName=cluster_name,
                            addonName=addon_name
                        )
                        addon_info = addon_response['addon']
                        addons_details.append(addon_info)
                        
                    except Exception as e:
                        log_info_non_console(f"애드온 {addon_name} 정보 조회 실패: {e}")
                        continue
                
                addons_data = {
                    'account_id': account_id,
                    'region': region_name,
                    'cluster_name': cluster_name,
                    'addons': addons_details
                }
                addons_info_list.append(addons_data)
                
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster_name} 애드온 정보 조회 실패: {e}")
                continue
        
        return addons_info_list
        
    except Exception as e:
        log_error(f"EKS 애드온 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

def format_output(addons_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(addons_info_list, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(addons_info_list, default_flow_style=False, allow_unicode=True)
    else:
        return format_table_output(addons_info_list)

def format_table_output(addons_info_list):
    """테이블 형식으로 출력합니다."""
    if not addons_info_list:
        console.print("[yellow]표시할 EKS 애드온 정보가 없습니다.[/yellow]")
        return
    
    # 계정, 리전별로 정렬
    addons_info_list.sort(key=lambda x: (x["account_id"], x["region"], x["cluster_name"]))
    
    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    # 테이블 컬럼 정의
    table.add_column("Account", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("Cluster Name", style="white")
    table.add_column("Addon Name", style="green")
    table.add_column("Status", justify="center")
    table.add_column("Version", style="blue")
    table.add_column("Service Account Role", style="yellow", max_width=30)
    table.add_column("Created At", style="dim")
    
    last_account = None
    last_region = None
    last_cluster = None
    
    for i, addon_info in enumerate(addons_info_list):
        account_changed = addon_info["account_id"] != last_account
        region_changed = addon_info["region"] != last_region
        cluster_changed = addon_info["cluster_name"] != last_cluster
        
        # 계정이 바뀔 때 구분선 추가
        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in range(8)])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in range(7)])
        
        addons = addon_info.get('addons', [])
        
        if not addons:
            # 애드온이 없는 경우
            display_values = [
                addon_info["account_id"] if account_changed else "",
                addon_info["region"] if account_changed or region_changed else "",
                addon_info["cluster_name"] if account_changed or region_changed or cluster_changed else "",
                "[dim]No addons[/dim]",
                "-",
                "-",
                "-",
                "-"
            ]
            table.add_row(*display_values)
        else:
            # 첫 번째 애드온
            first_addon = addons[0]
            service_account_role = first_addon.get('serviceAccountRoleArn', '-')
            if service_account_role != '-':
                service_account_role = service_account_role.split('/')[-1]  # 역할 이름만 추출
            
            display_values = [
                addon_info["account_id"] if account_changed else "",
                addon_info["region"] if account_changed or region_changed else "",
                addon_info["cluster_name"] if account_changed or region_changed or cluster_changed else "",
                first_addon.get('addonName', '-'),
                format_status(first_addon.get('status', '-')),
                first_addon.get('addonVersion', '-'),
                service_account_role,
                format_datetime(first_addon.get('createdAt'))
            ]
            table.add_row(*display_values)
            
            # 나머지 애드온들
            for addon in addons[1:]:
                service_account_role = addon.get('serviceAccountRoleArn', '-')
                if service_account_role != '-':
                    service_account_role = service_account_role.split('/')[-1]
                
                display_values = [
                    "",  # account
                    "",  # region
                    "",  # cluster
                    addon.get('addonName', '-'),
                    format_status(addon.get('status', '-')),
                    addon.get('addonVersion', '-'),
                    service_account_role,
                    format_datetime(addon.get('createdAt'))
                ]
                table.add_row(*display_values)
        
        last_account = addon_info["account_id"]
        last_region = addon_info["region"]
        last_cluster = addon_info["cluster_name"]
    
    console.print(table)
    
    # 상세 정보 출력
    print_detailed_addons(addons_info_list)

def print_detailed_addons(addons_info_list):
    """상세 애드온 정보를 출력합니다."""
    console.print("\n[bold]🔧 Detailed Addon Information[/bold]")
    
    for addon_info in addons_info_list:
        addons = addon_info.get('addons', [])
        if not addons:
            continue
            
        console.print(f"\n[bold cyan]🔹 {addon_info['cluster_name']}[/bold cyan] ([dim]{addon_info['account_id']} - {addon_info['region']}[/dim])")
        
        for addon in addons:
            addon_name = addon.get('addonName', 'Unknown')
            console.print(f"\n[bold]📦 {addon_name}[/bold]")
            
            details_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            details_table.add_column("Field", style="cyan", no_wrap=True)
            details_table.add_column("Value", style="white")
            
            details_table.add_row("Addon ARN", addon.get('addonArn', '-'))
            details_table.add_row("Version", addon.get('addonVersion', '-'))
            details_table.add_row("Status", format_status(addon.get('status', '-')))
            details_table.add_row("Service Account Role ARN", addon.get('serviceAccountRoleArn', '-'))
            details_table.add_row("Configuration Values", addon.get('configurationValues', '-') or 'Default')
            details_table.add_row("Resolve Conflicts", addon.get('resolveConflicts', '-'))
            
            # 태그 정보
            tags = addon.get('tags', {})
            if tags:
                tag_text = ', '.join([f"{k}={v}" for k, v in tags.items()])
                details_table.add_row("Tags", tag_text)
            
            console.print(details_table)
            
            # Health 정보
            health = addon.get('health', {})
            if health:
                issues = health.get('issues', [])
                if issues:
                    console.print(f"[bold red]⚠️  Health Issues:[/bold red]")
                    for issue in issues:
                        console.print(f"  • {issue.get('code', 'Unknown')}: {issue.get('message', 'No message')}")

def format_status(status):
    """상태에 따라 색상을 적용합니다."""
    status_lower = status.lower()
    if status_lower in ['active']:
        return f"[bold green]{status}[/bold green]"
    elif status_lower in ['creating', 'updating', 'resolving']:
        return f"[bold yellow]{status}[/bold yellow]"
    elif status_lower in ['create_failed', 'update_failed', 'degraded']:
        return f"[bold red]{status}[/bold red]"
    elif status_lower in ['deleting']:
        return f"[bold orange]{status}[/bold orange]"
    else:
        return status

def format_datetime(dt):
    """datetime 객체를 문자열로 포맷합니다."""
    if dt:
        if isinstance(dt, str):
            return dt
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    return '-'

@progress_bar("Processing EKS addon discovery across accounts and regions")
def main(args):
    """메인 함수"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    
    all_addons_info = []
    
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            for reg in regions:
                futures.append(executor.submit(
                    fetch_eks_addons_info, 
                    acct, 
                    profile_name, 
                    reg, 
                    args.cluster
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_addons_info.extend(result)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_addons_info, args.output)
        print(output)
    else:
        format_table_output(all_addons_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-c', '--cluster', help='클러스터 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EKS 애드온 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)