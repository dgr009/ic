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

@progress_bar("Fetching EKS Fargate profile information")
def fetch_eks_fargate_info(account_id, profile_name, region_name, cluster_name_filter=None):
    """EKS Fargate 프로파일 정보를 수집합니다."""
    log_info_non_console(f"EKS Fargate 프로파일 정보 수집 시작: Account={account_id}, Region={region_name}")
    
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
        
        fargate_info_list = []
        
        for cluster_name in cluster_names:
            try:
                # Fargate 프로파일 목록 조회
                profiles_response = eks_client.list_fargate_profiles(clusterName=cluster_name)
                profile_names = profiles_response.get('fargateProfileNames', [])
                
                if not profile_names:
                    continue
                
                # 각 Fargate 프로파일 상세 정보 조회
                for profile_name_item in profile_names:
                    try:
                        profile_response = eks_client.describe_fargate_profile(
                            clusterName=cluster_name,
                            fargateProfileName=profile_name_item
                        )
                        profile_info = profile_response['fargateProfile']
                        
                        fargate_data = {
                            'account_id': account_id,
                            'region': region_name,
                            'cluster_name': cluster_name,
                            'profile': profile_info
                        }
                        fargate_info_list.append(fargate_data)
                        
                    except Exception as e:
                        log_info_non_console(f"Fargate 프로파일 {profile_name_item} 정보 조회 실패: {e}")
                        continue
                
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster_name} Fargate 정보 조회 실패: {e}")
                continue
        
        return fargate_info_list
        
    except Exception as e:
        log_error(f"EKS Fargate 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

def format_output(fargate_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(fargate_info_list, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(fargate_info_list, default_flow_style=False, allow_unicode=True)
    else:
        return format_table_output(fargate_info_list)

def format_table_output(fargate_info_list):
    """테이블 형식으로 출력합니다."""
    if not fargate_info_list:
        console.print("[yellow]표시할 EKS Fargate 프로파일이 없습니다.[/yellow]")
        return
    
    # 클러스터별로 그룹화
    clusters = {}
    for fargate_info in fargate_info_list:
        cluster_name = fargate_info['cluster_name']
        if cluster_name not in clusters:
            clusters[cluster_name] = []
        clusters[cluster_name].append(fargate_info)
    
    for cluster_name, cluster_fargate in clusters.items():
        console.print(f"\n[bold blue]🔹 Cluster: {cluster_name}[/bold blue]")
        
        # Fargate 프로파일 요약 테이블
        console.print(f"\n[bold]🚀 Fargate Profiles Summary[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("Profile Name", style="cyan")
        summary_table.add_column("Status", justify="center")
        summary_table.add_column("Pod Execution Role", style="white", max_width=40)
        summary_table.add_column("Subnets", style="green", max_width=30)
        summary_table.add_column("Selectors", style="yellow", max_width=40)
        summary_table.add_column("Created At", style="dim")
        
        for fargate_info in cluster_fargate:
            profile = fargate_info['profile']
            
            # Pod Execution Role ARN에서 역할 이름만 추출
            pod_role_arn = profile.get('podExecutionRoleArn', '-')
            pod_role_name = pod_role_arn.split('/')[-1] if '/' in pod_role_arn else pod_role_arn
            
            # 서브넷 개수 표시
            subnets = profile.get('subnets', [])
            subnet_text = f"{len(subnets)} subnets" if subnets else "No subnets"
            
            # Selectors 정보 포맷팅
            selectors = profile.get('selectors', [])
            selector_text = []
            for selector in selectors:
                namespace = selector.get('namespace', '*')
                labels = selector.get('labels', {})
                if labels:
                    label_count = len(labels)
                    selector_text.append(f"ns:{namespace} ({label_count} labels)")
                else:
                    selector_text.append(f"ns:{namespace}")
            
            summary_table.add_row(
                profile.get('fargateProfileName', '-'),
                format_status(profile.get('status', '-')),
                pod_role_name,
                subnet_text,
                '; '.join(selector_text) or 'No selectors',
                format_datetime(profile.get('createdAt'))
            )
        
        console.print(summary_table)
        
        # 상세 정보
        for fargate_info in cluster_fargate:
            profile = fargate_info['profile']
            profile_name = profile.get('fargateProfileName', 'Unknown')
            
            console.print(f"\n[bold]📋 Profile Details: {profile_name}[/bold]")
            
            details_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            details_table.add_column("Field", style="cyan", no_wrap=True)
            details_table.add_column("Value", style="white")
            
            details_table.add_row("Profile ARN", profile.get('fargateProfileArn', '-'))
            details_table.add_row("Pod Execution Role ARN", profile.get('podExecutionRoleArn', '-'))
            details_table.add_row("Platform Version", profile.get('platformVersion', '-'))
            
            # 서브넷 정보
            subnets = profile.get('subnets', [])
            if subnets:
                details_table.add_row("Subnets", ', '.join(subnets))
            
            # 태그 정보
            tags = profile.get('tags', {})
            if tags:
                tag_text = ', '.join([f"{k}={v}" for k, v in tags.items()])
                details_table.add_row("Tags", tag_text)
            
            console.print(details_table)
            
            # Selectors 상세 정보
            selectors = profile.get('selectors', [])
            if selectors:
                console.print(f"\n[bold]🎯 Pod Selectors for {profile_name}[/bold]")
                
                selectors_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
                selectors_table.add_column("Namespace", style="cyan")
                selectors_table.add_column("Labels", style="yellow")
                
                for selector in selectors:
                    namespace = selector.get('namespace', '*')
                    labels = selector.get('labels', {})
                    
                    if labels:
                        label_text = ', '.join([f"{k}={v}" for k, v in labels.items()])
                    else:
                        label_text = "Any labels"
                    
                    selectors_table.add_row(namespace, label_text)
                
                console.print(selectors_table)

def format_status(status):
    """상태에 따라 색상을 적용합니다."""
    status_lower = status.lower()
    if status_lower in ['active']:
        return f"[bold green]{status}[/bold green]"
    elif status_lower in ['creating', 'deleting']:
        return f"[bold yellow]{status}[/bold yellow]"
    elif status_lower in ['create_failed', 'delete_failed']:
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

@progress_bar("Processing EKS Fargate profile discovery across accounts and regions")
def main(args):
    """메인 함수"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    
    all_fargate_info = []
    
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            for reg in regions:
                futures.append(executor.submit(
                    fetch_eks_fargate_info, 
                    acct, 
                    profile_name, 
                    reg, 
                    args.cluster
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_fargate_info.extend(result)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_fargate_info, args.output)
        print(output)
    else:
        format_table_output(all_fargate_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-c', '--cluster', help='클러스터 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EKS Fargate 프로파일 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)