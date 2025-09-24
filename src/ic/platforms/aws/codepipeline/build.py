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

def fetch_pipeline_build_stages(account_id, profile_name, region_name, pipeline_name):
    """CodePipeline의 빌드 스테이지 정보를 수집합니다."""
    log_info_non_console(f"CodePipeline 빌드 스테이지 정보 수집: Account={account_id}, Region={region_name}, Pipeline={pipeline_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    codepipeline_client = session.client("codepipeline", region_name=region_name)
    
    try:
        # 파이프라인 상태 조회
        pipeline_state = codepipeline_client.get_pipeline_state(name=pipeline_name)
        stage_states = pipeline_state.get('stageStates', [])
        
        # 빌드 관련 스테이지 필터링 (대소문자 구분 없음)
        build_stages = []
        for stage in stage_states:
            stage_name = stage.get('stageName', '').lower()
            if 'build' in stage_name:
                stage['account_id'] = account_id
                stage['region'] = region_name
                stage['pipeline_name'] = pipeline_name
                build_stages.append(stage)
        
        if not build_stages:
            log_error(f"Error: No stage matching 'build' found in pipeline '{pipeline_name}'.")
            return []
        
        return build_stages
        
    except Exception as e:
        log_error(f"CodePipeline 상태 조회 실패: Account={account_id}, Region={region_name}, Pipeline={pipeline_name}, Error={e}")
        return []

def format_output(stages_info, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(stages_info, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(stages_info, default_flow_style=False, allow_unicode=True)
    else:
        return None  # 테이블 형식은 별도 함수에서 처리

def format_build_stages_table(stages_info):
    """빌드 스테이지를 테이블 형식으로 출력합니다."""
    if not stages_info:
        console.print("[yellow]표시할 빌드 스테이지가 없습니다.[/yellow]")
        return
    
    console.print(f"\n[bold blue]═══ CodePipeline Build Stages ═══[/bold blue]")
    
    for stage in stages_info:
        # 스테이지별 상세 정보 출력
        console.print(f"\n[bold cyan]Pipeline:[/bold cyan] {stage.get('pipeline_name', '-')}")
        console.print(f"[bold cyan]Stage:[/bold cyan] {stage.get('stageName', '-')}")
        console.print(f"[bold cyan]Account:[/bold cyan] {stage.get('account_id', '-')} | [bold cyan]Region:[/bold cyan] {stage.get('region', '-')}")
        
        # 액션 상태 테이블
        action_states = stage.get('actionStates', [])
        if action_states:
            action_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
            action_table.add_column("Action", style="white")
            action_table.add_column("Status", justify="center")
            action_table.add_column("Last Status Change", style="white")
            action_table.add_column("Execution ID", style="white")
            action_table.add_column("Source Revision", style="white")
            
            for action in action_states:
                # 최신 실행 정보 가져오기
                latest_execution = action.get('latestExecution', {})
                current_revision = action.get('currentRevision', {})
                
                action_table.add_row(
                    action.get('actionName', '-'),
                    format_status_with_symbol(latest_execution.get('status', '-')),
                    format_datetime(latest_execution.get('lastStatusChange')),
                    latest_execution.get('externalExecutionId', '-'),
                    current_revision.get('revisionId', '-')
                )
            
            console.print(action_table)
        else:
            console.print("[yellow]No action states found for this stage.[/yellow]")

def format_status_with_symbol(status):
    """상태에 따라 심볼과 색상을 적용합니다."""
    if not status or status == '-':
        return status
        
    status_lower = status.lower()
    if status_lower == 'succeeded':
        return f"[bold green]✓ {status}[/bold green]"
    elif status_lower == 'failed':
        return f"[bold red]✗ {status}[/bold red]"
    elif status_lower == 'inprogress':
        return f"[bold blue]→ {status}[/bold blue]"
    elif status_lower == 'stopped':
        return f"[bold yellow]⏹ {status}[/bold yellow]"
    elif status_lower == 'stopping':
        return f"[bold yellow]⏹ {status}[/bold yellow]"
    elif status_lower == 'superseded':
        return f"[dim]≫ {status}[/dim]"
    elif status_lower == 'cancelled':
        return f"[dim]∅ {status}[/dim]"
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
    if not args.pipeline_name:
        log_error("pipeline_name 인수가 필요합니다.")
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
    all_stages = []
    
    with ManualProgress(f"Collecting CodePipeline build stages for '{args.pipeline_name}' across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                for reg in regions:
                    future = executor.submit(
                        fetch_pipeline_build_stages, 
                        acct, 
                        profile_name, 
                        reg, 
                        args.pipeline_name
                    )
                    futures.append(future)
                    future_to_info[future] = (acct, reg)
            
            completed = 0
            for future in as_completed(futures):
                acct, reg = future_to_info[future]
                try:
                    result = future.result()
                    if result:
                        all_stages.extend(result)
                    completed += 1
                    stage_count = len(result) if result else 0
                    progress.update(f"Processed {acct}/{reg} - Found {stage_count} build stages", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect CodePipeline build data for {acct}/{reg}: {e}")
                    progress.update(f"Failed {acct}/{reg} - {str(e)[:50]}...", advance=1)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_stages, args.output)
        print(output)
    else:
        format_build_stages_table(all_stages)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('pipeline_name', help='상태를 조회할 CodePipeline의 이름')
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodePipeline 빌드 스테이지 상태 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)