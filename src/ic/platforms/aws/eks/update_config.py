#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from InquirerPy import inquirer

from common.log import log_info_non_console, log_error
from common.progress_decorator import progress_bar, spinner
from common.utils import (
    get_env_accounts,
    get_profiles,
    DEFINED_REGIONS,
    create_session
)

load_dotenv()
console = Console()

@progress_bar("Fetching EKS cluster list")
def fetch_eks_clusters(account_id, profile_name, region_name, cluster_name_filter=None):
    """EKS 클러스터 목록을 조회합니다."""
    log_info_non_console(f"EKS 클러스터 목록 조회: Account={account_id}, Region={region_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    eks_client = session.client("eks", region_name=region_name)
    
    try:
        # 클러스터 목록 조회
        clusters_response = eks_client.list_clusters()
        cluster_names = clusters_response.get('clusters', [])
        
        # 이름 필터 적용
        if cluster_name_filter:
            cluster_names = [name for name in cluster_names if cluster_name_filter.lower() in name.lower()]
        
        # 클러스터 정보와 함께 반환
        cluster_list = []
        for cluster_name in cluster_names:
            cluster_info = {
                'name': cluster_name,
                'region': region_name,
                'account_id': account_id,
                'display_name': f"{cluster_name} (Account: {account_id}, Region: {region_name})"
            }
            cluster_list.append(cluster_info)
        
        return cluster_list
        
    except Exception as e:
        log_error(f"EKS 클러스터 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

@spinner("Updating kubeconfig")
def update_kubeconfig(cluster_name, region_name, profile_name=None):
    """kubeconfig를 업데이트합니다."""
    try:
        # aws eks update-kubeconfig 명령어 구성
        cmd = [
            'aws', 'eks', 'update-kubeconfig',
            '--region', region_name,
            '--name', cluster_name
        ]
        
        # 프로파일이 있으면 추가
        if profile_name and profile_name != 'default':
            cmd.extend(['--profile', profile_name])
        
        log_info_non_console(f"kubeconfig 업데이트 실행: {' '.join(cmd)}")
        
        # 명령어 실행
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        return True, result.stdout.strip()
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        return False, error_msg
    except Exception as e:
        return False, str(e)

def select_cluster_interactive(clusters):
    """여러 클러스터 중 하나를 선택합니다."""
    if len(clusters) == 1:
        return clusters[0]
    
    console.print(f"\n[bold yellow]🔍 {len(clusters)}개의 클러스터를 발견했습니다:[/bold yellow]")
    
    # 선택 옵션 생성
    choices = []
    for cluster in clusters:
        choices.append({
            'name': cluster['display_name'],
            'value': cluster
        })
    
    # 사용자 선택
    selected = inquirer.select(
        message="kubeconfig를 업데이트할 클러스터를 선택하세요:",
        choices=choices,
        default=choices[0]['value']
    ).execute()
    
    return selected

def display_cluster_table(clusters):
    """발견된 클러스터들을 테이블로 표시합니다."""
    if not clusters:
        return
    
    console.print(f"\n[bold blue]🔍 발견된 EKS 클러스터 ({len(clusters)}개)[/bold blue]")
    
    table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
    table.add_column("Cluster Name", style="cyan")
    table.add_column("Account ID", style="magenta")
    table.add_column("Region", style="green")
    
    for cluster in clusters:
        table.add_row(
            cluster['name'],
            cluster['account_id'],
            cluster['region']
        )
    
    console.print(table)

@progress_bar("Processing EKS kubeconfig update")
def main(args):
    """메인 함수"""
    # 기본 리전 설정 (서울)
    region = args.region if args.region else 'ap-northeast-2'
    
    if not args.name:
        log_error("클러스터 이름을 지정해주세요. --name 또는 -n 옵션을 사용하세요.")
        console.print("[red]사용법: ic aws eks update-config --name CLUSTER_NAME[/red]")
        sys.exit(1)
    
    console.print(f"[bold blue]🔍 EKS 클러스터 검색 중...[/bold blue]")
    console.print(f"검색어: [cyan]{args.name}[/cyan]")
    console.print(f"리전: [green]{region}[/green]")
    
    # 계정 및 프로파일 설정
    accounts = args.account.split(",") if args.account else get_env_accounts()
    profiles_map = get_profiles()
    
    all_clusters = []
    
    # 모든 계정에서 클러스터 검색
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            
            futures.append(executor.submit(
                fetch_eks_clusters,
                acct,
                profile_name,
                region,
                args.name
            ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_clusters.extend(result)
    
    # 결과 처리
    if not all_clusters:
        console.print(f"[red]❌ '{args.name}'과 일치하는 EKS 클러스터를 찾을 수 없습니다.[/red]")
        console.print(f"리전: {region}")
        console.print("다른 이름이나 리전을 시도해보세요.")
        sys.exit(1)
    
    # 발견된 클러스터 표시
    display_cluster_table(all_clusters)
    
    # 클러스터 선택
    if len(all_clusters) == 1:
        selected_cluster = all_clusters[0]
        console.print(f"\n[green]✅ 클러스터 자동 선택: {selected_cluster['name']}[/green]")
    else:
        selected_cluster = select_cluster_interactive(all_clusters)
        console.print(f"\n[green]✅ 선택된 클러스터: {selected_cluster['name']}[/green]")
    
    # kubeconfig 업데이트
    console.print(f"\n[bold blue]🔧 kubeconfig 업데이트 중...[/bold blue]")
    
    # 프로파일 이름 가져오기
    profile_name = profiles_map.get(selected_cluster['account_id'])
    
    success, message = update_kubeconfig(
        selected_cluster['name'],
        selected_cluster['region'],
        profile_name
    )
    
    if success:
        console.print(f"[bold green]🎉 kubeconfig 업데이트 성공![/bold green]")
        console.print(f"클러스터: [cyan]{selected_cluster['name']}[/cyan]")
        console.print(f"리전: [green]{selected_cluster['region']}[/green]")
        console.print(f"계정: [magenta]{selected_cluster['account_id']}[/magenta]")
        
        if message:
            console.print(f"\n[dim]{message}[/dim]")
        
        console.print(f"\n[bold yellow]💡 이제 다음 명령어들을 사용할 수 있습니다:[/bold yellow]")
        console.print(f"  • kubectl get nodes")
        console.print(f"  • kubectl get pods -n NAMESPACE")
        console.print(f"  • ic aws eks pods -n NAMESPACE")
        
    else:
        console.print(f"[bold red]❌ kubeconfig 업데이트 실패![/bold red]")
        console.print(f"오류: {message}")
        
        console.print(f"\n[yellow]💡 해결 방법:[/yellow]")
        console.print(f"  1. AWS CLI가 설치되어 있는지 확인: aws --version")
        console.print(f"  2. aws-iam-authenticator가 설치되어 있는지 확인: which aws-iam-authenticator")
        console.print(f"  3. EKS 클러스터 접근 권한이 있는지 확인")
        
        sys.exit(1)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-n', '--name', required=True,
                       help='검색할 클러스터 이름 (부분 일치)')
    parser.add_argument('-a', '--account', 
                       help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('--region', default='ap-northeast-2',
                       help='AWS 리전 (기본값: ap-northeast-2)')
    parser.add_argument('--debug', action='store_true', 
                       help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EKS kubeconfig 업데이트")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)