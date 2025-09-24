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

def fetch_msk_cluster_info(account_id, profile_name, region_name, cluster_name_filter=None):
    """MSK 클러스터 정보를 수집합니다."""
    log_info_non_console(f"MSK 클러스터 정보 수집 시작: Account={account_id}, Region={region_name}")
    
    session = create_session(profile_name, region_name)
    if not session:
        return []
    
    kafka_client = session.client("kafka", region_name=region_name)
    
    try:
        # 클러스터 목록 조회
        clusters_response = kafka_client.list_clusters()
        clusters = clusters_response.get('ClusterInfoList', [])
        
        if not clusters:
            return []
        
        # 클러스터 이름 필터링
        if cluster_name_filter:
            clusters = [c for c in clusters if cluster_name_filter.lower() in c['ClusterName'].lower()]
        
        cluster_info_list = []
        
        for cluster in clusters:
            cluster_arn = cluster['ClusterArn']
            cluster_name = cluster['ClusterName']
            
            try:
                # 클러스터 상세 정보 조회
                cluster_detail = kafka_client.describe_cluster(ClusterArn=cluster_arn)
                cluster_info = cluster_detail.get('ClusterInfo', {})
                
                # 브로커 노드 정보
                broker_info = cluster_info.get('BrokerNodeGroupInfo', {})
                
                # 암호화 정보
                encryption_info = cluster_info.get('EncryptionInfo', {})
                encryption_at_rest = encryption_info.get('EncryptionAtRest', {})
                encryption_in_transit = encryption_info.get('EncryptionInTransit', {})
                
                # 모니터링 정보
                open_monitoring = cluster_info.get('OpenMonitoring', {})
                prometheus_info = open_monitoring.get('Prometheus', {})
                
                # 현재 소프트웨어 정보
                current_software = cluster_info.get('CurrentBrokerSoftwareInfo', {})
                
                cluster_data = {
                    'account_id': account_id,
                    'region': region_name,
                    'cluster_name': cluster_name,
                    'cluster_arn': cluster_arn,
                    'state': cluster_info.get('State', 'UNKNOWN'),
                    'creation_time': cluster_info.get('CreationTime'),
                    'current_version': cluster_info.get('CurrentVersion', ''),
                    'kafka_version': current_software.get('KafkaVersion', 'Unknown'),
                    'number_of_broker_nodes': cluster_info.get('NumberOfBrokerNodes', 0),
                    'instance_type': broker_info.get('InstanceType', 'Unknown'),
                    'broker_az_distribution': broker_info.get('BrokerAZDistribution', 'DEFAULT'),
                    'client_subnets': broker_info.get('ClientSubnets', []),
                    'security_groups': broker_info.get('SecurityGroups', []),
                    'storage_info': broker_info.get('StorageInfo', {}),
                    'enhanced_monitoring': cluster_info.get('EnhancedMonitoring', 'DEFAULT'),
                    'encryption_at_rest_enabled': bool(encryption_at_rest.get('DataVolumeKMSKeyId')),
                    'encryption_in_transit_client_broker': encryption_in_transit.get('ClientBroker', 'PLAINTEXT'),
                    'encryption_in_transit_in_cluster': encryption_in_transit.get('InCluster', False),
                    'prometheus_jmx_enabled': prometheus_info.get('JmxExporter', {}).get('EnabledInBroker', False),
                    'prometheus_node_enabled': prometheus_info.get('NodeExporter', {}).get('EnabledInBroker', False),
                    'zookeeper_connect_string': cluster_info.get('ZookeeperConnectString', ''),
                    'tags': cluster_info.get('Tags', {})
                }
                
                cluster_info_list.append(cluster_data)
                
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster_name} 상세 정보 조회 실패: {e}")
                continue
        
        return cluster_info_list
        
    except Exception as e:
        log_error(f"MSK 클러스터 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
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
        console.print("[yellow]표시할 MSK 클러스터 정보가 없습니다.[/yellow]")
        return
    
    # 클러스터 정보를 계정, 리전별로 정렬
    cluster_info_list.sort(key=lambda x: (x["account_id"], x["region"], x["cluster_name"]))
    
    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    # 테이블 컬럼 정의
    table.add_column("Account", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("Cluster Name", style="white")
    table.add_column("State", justify="center")
    table.add_column("Kafka Version", style="green")
    table.add_column("Brokers", justify="right", style="blue")
    table.add_column("Instance Type", style="cyan")
    table.add_column("Encryption", justify="center", style="yellow")
    table.add_column("Monitoring", justify="center", style="magenta")
    table.add_column("Creation Time", style="dim")
    
    last_account = None
    last_region = None
    
    for i, cluster in enumerate(cluster_info_list):
        account_changed = cluster["account_id"] != last_account
        region_changed = cluster["region"] != last_region
        
        # 계정이 바뀔 때 구분선 추가
        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in range(10)])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in range(9)])
        
        # 암호화 상태 표시
        encryption_status = format_encryption_status(
            cluster.get('encryption_at_rest_enabled', False),
            cluster.get('encryption_in_transit_client_broker', 'PLAINTEXT'),
            cluster.get('encryption_in_transit_in_cluster', False)
        )
        
        # 모니터링 상태 표시
        monitoring_status = format_monitoring_status(
            cluster.get('enhanced_monitoring', 'DEFAULT'),
            cluster.get('prometheus_jmx_enabled', False),
            cluster.get('prometheus_node_enabled', False)
        )
        
        # 생성 시간 포맷
        creation_time = cluster.get('creation_time')
        if creation_time:
            if isinstance(creation_time, str):
                formatted_time = creation_time[:19]  # YYYY-MM-DD HH:MM:SS
            else:
                formatted_time = creation_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            formatted_time = 'Unknown'
        
        # 행 데이터 구성
        display_values = [
            cluster["account_id"] if account_changed else "",
            cluster["region"] if account_changed or region_changed else "",
            cluster["cluster_name"],
            format_state(cluster["state"]),
            cluster["kafka_version"],
            str(cluster["number_of_broker_nodes"]),
            cluster["instance_type"],
            encryption_status,
            monitoring_status,
            formatted_time
        ]
        
        table.add_row(*display_values)
        
        last_account = cluster["account_id"]
        last_region = cluster["region"]
    
    console.print(table)

def format_state(state):
    """상태에 따라 색상을 적용합니다."""
    state_lower = state.lower()
    if state_lower == 'active':
        return f"[bold green]{state}[/bold green]"
    elif state_lower in ['creating', 'updating']:
        return f"[bold blue]{state}[/bold blue]"
    elif state_lower in ['deleting', 'failed']:
        return f"[bold red]{state}[/bold red]"
    elif state_lower == 'healing':
        return f"[bold yellow]{state}[/bold yellow]"
    else:
        return state

def format_encryption_status(at_rest, in_transit_client, in_transit_cluster):
    """암호화 상태를 포맷합니다."""
    statuses = []
    
    if at_rest:
        statuses.append("[green]Rest[/green]")
    
    if in_transit_client != 'PLAINTEXT':
        statuses.append("[green]Transit[/green]")
    
    if in_transit_cluster:
        statuses.append("[green]Cluster[/green]")
    
    if not statuses:
        return "[red]None[/red]"
    
    return " ".join(statuses)

def format_monitoring_status(enhanced, prometheus_jmx, prometheus_node):
    """모니터링 상태를 포맷합니다."""
    statuses = []
    
    if enhanced != 'DEFAULT':
        statuses.append(f"[green]{enhanced}[/green]")
    
    if prometheus_jmx:
        statuses.append("[blue]JMX[/blue]")
    
    if prometheus_node:
        statuses.append("[blue]Node[/blue]")
    
    if not statuses:
        return "[dim]Default[/dim]"
    
    return " ".join(statuses)

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
    
    with ManualProgress("Collecting MSK cluster information across accounts and regions", total=total_operations) as progress:
        with ThreadPoolExecutor() as executor:
            futures = []
            future_to_info = {}
            
            for acct, profile_name in valid_accounts:
                for reg in regions:
                    future = executor.submit(
                        fetch_msk_cluster_info, 
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
                    progress.update(f"Processed {acct}/{reg} - Found {cluster_count} MSK clusters", advance=1)
                except Exception as e:
                    completed += 1
                    log_info_non_console(f"Failed to collect MSK data for {acct}/{reg}: {e}")
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
    parser = argparse.ArgumentParser(description="MSK 클러스터 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)