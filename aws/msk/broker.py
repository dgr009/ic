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
from common.utils import (
    get_env_accounts,
    get_profiles,
    DEFINED_REGIONS,
    create_session
)

load_dotenv()
console = Console()

def fetch_msk_broker_info(account_id, profile_name, region_name, cluster_name_filter=None):
    """MSK 브로커 정보를 수집합니다."""
    log_info_non_console(f"MSK 브로커 정보 수집 시작: Account={account_id}, Region={region_name}")
    
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
        
        broker_info_list = []
        
        for cluster in clusters:
            cluster_arn = cluster['ClusterArn']
            cluster_name = cluster['ClusterName']
            
            try:
                # 브로커 엔드포인트 정보 조회
                bootstrap_response = kafka_client.get_bootstrap_brokers(ClusterArn=cluster_arn)
                
                # 클러스터 상세 정보도 함께 조회 (브로커 수, 인스턴스 타입 등)
                cluster_detail = kafka_client.describe_cluster(ClusterArn=cluster_arn)
                cluster_info = cluster_detail.get('ClusterInfo', {})
                broker_node_info = cluster_info.get('BrokerNodeGroupInfo', {})
                
                # 브로커 엔드포인트 정보 파싱
                bootstrap_brokers = {}
                
                # 일반 브로커 (PLAINTEXT)
                if bootstrap_response.get('BootstrapBrokerString'):
                    bootstrap_brokers['plaintext'] = bootstrap_response['BootstrapBrokerString'].split(',')
                
                # TLS 브로커
                if bootstrap_response.get('BootstrapBrokerStringTls'):
                    bootstrap_brokers['tls'] = bootstrap_response['BootstrapBrokerStringTls'].split(',')
                
                # SASL/SCRAM 브로커
                if bootstrap_response.get('BootstrapBrokerStringSaslScram'):
                    bootstrap_brokers['sasl_scram'] = bootstrap_response['BootstrapBrokerStringSaslScram'].split(',')
                
                # SASL/IAM 브로커
                if bootstrap_response.get('BootstrapBrokerStringSaslIam'):
                    bootstrap_brokers['sasl_iam'] = bootstrap_response['BootstrapBrokerStringSaslIam'].split(',')
                
                # Public 액세스 브로커들
                if bootstrap_response.get('BootstrapBrokerStringPublicTls'):
                    bootstrap_brokers['public_tls'] = bootstrap_response['BootstrapBrokerStringPublicTls'].split(',')
                
                if bootstrap_response.get('BootstrapBrokerStringPublicSaslScram'):
                    bootstrap_brokers['public_sasl_scram'] = bootstrap_response['BootstrapBrokerStringPublicSaslScram'].split(',')
                
                if bootstrap_response.get('BootstrapBrokerStringPublicSaslIam'):
                    bootstrap_brokers['public_sasl_iam'] = bootstrap_response['BootstrapBrokerStringPublicSaslIam'].split(',')
                
                # VPC Connectivity 브로커들
                if bootstrap_response.get('BootstrapBrokerStringVpcConnectivityTls'):
                    bootstrap_brokers['vpc_tls'] = bootstrap_response['BootstrapBrokerStringVpcConnectivityTls'].split(',')
                
                if bootstrap_response.get('BootstrapBrokerStringVpcConnectivitySaslScram'):
                    bootstrap_brokers['vpc_sasl_scram'] = bootstrap_response['BootstrapBrokerStringVpcConnectivitySaslScram'].split(',')
                
                if bootstrap_response.get('BootstrapBrokerStringVpcConnectivitySaslIam'):
                    bootstrap_brokers['vpc_sasl_iam'] = bootstrap_response['BootstrapBrokerStringVpcConnectivitySaslIam'].split(',')
                
                # 브로커 개수 계산
                total_brokers = cluster_info.get('NumberOfBrokerNodes', 0)
                
                # 각 연결 타입별로 사용 가능한 브로커 개수 계산
                available_connection_types = []
                for conn_type, brokers in bootstrap_brokers.items():
                    if brokers:
                        available_connection_types.append({
                            'type': conn_type,
                            'count': len(brokers),
                            'endpoints': brokers
                        })
                
                broker_data = {
                    'account_id': account_id,
                    'region': region_name,
                    'cluster_name': cluster_name,
                    'cluster_arn': cluster_arn,
                    'cluster_state': cluster_info.get('State', 'UNKNOWN'),
                    'total_broker_nodes': total_brokers,
                    'instance_type': broker_node_info.get('InstanceType', 'Unknown'),
                    'broker_az_distribution': broker_node_info.get('BrokerAZDistribution', 'DEFAULT'),
                    'available_connection_types': available_connection_types,
                    'bootstrap_brokers': bootstrap_brokers,
                    'client_subnets': broker_node_info.get('ClientSubnets', []),
                    'security_groups': broker_node_info.get('SecurityGroups', [])
                }
                
                broker_info_list.append(broker_data)
                
            except Exception as e:
                log_info_non_console(f"클러스터 {cluster_name} 브로커 정보 조회 실패: {e}")
                continue
        
        return broker_info_list
        
    except Exception as e:
        log_error(f"MSK 브로커 목록 조회 실패: Account={account_id}, Region={region_name}, Error={e}")
        return []

def format_output(broker_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return json.dumps(broker_info_list, indent=2, default=str)
    elif output_format == 'yaml':
        return yaml.dump(broker_info_list, default_flow_style=False, allow_unicode=True)
    else:
        return format_table_output(broker_info_list)

def format_table_output(broker_info_list):
    """테이블 형식으로 출력합니다."""
    if not broker_info_list:
        console.print("[yellow]표시할 MSK 브로커 정보가 없습니다.[/yellow]")
        return
    
    # 브로커 정보를 계정, 리전별로 정렬
    broker_info_list.sort(key=lambda x: (x["account_id"], x["region"], x["cluster_name"]))
    
    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    # 테이블 컬럼 정의
    table.add_column("Account", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("Cluster Name", style="white")
    table.add_column("State", justify="center")
    table.add_column("Brokers", justify="right", style="blue")
    table.add_column("Instance Type", style="cyan")
    table.add_column("Connection Types", style="green")
    table.add_column("Endpoints Sample", style="dim", max_width=40)
    
    last_account = None
    last_region = None
    
    for i, broker in enumerate(broker_info_list):
        account_changed = broker["account_id"] != last_account
        region_changed = broker["region"] != last_region
        
        # 계정이 바뀔 때 구분선 추가
        if i > 0:
            if account_changed:
                table.add_row(*[Rule(style="dim") for _ in range(8)])
            elif region_changed:
                table.add_row("", *[Rule(style="dim") for _ in range(7)])
        
        # 연결 타입 포맷
        connection_types = format_connection_types(broker.get('available_connection_types', []))
        
        # 엔드포인트 샘플 (첫 번째 TLS 또는 첫 번째 사용 가능한 엔드포인트)
        sample_endpoint = get_sample_endpoint(broker.get('bootstrap_brokers', {}))
        
        # 행 데이터 구성
        display_values = [
            broker["account_id"] if account_changed else "",
            broker["region"] if account_changed or region_changed else "",
            broker["cluster_name"],
            format_cluster_state(broker["cluster_state"]),
            str(broker["total_broker_nodes"]),
            broker["instance_type"],
            connection_types,
            sample_endpoint
        ]
        
        table.add_row(*display_values)
        
        last_account = broker["account_id"]
        last_region = broker["region"]
    
    console.print(table)
    
    # 상세 엔드포인트 정보 출력
    print_detailed_endpoints(broker_info_list)

def format_cluster_state(state):
    """클러스터 상태에 따라 색상을 적용합니다."""
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

def format_connection_types(connection_types):
    """연결 타입들을 포맷합니다."""
    if not connection_types:
        return "[red]None[/red]"
    
    type_labels = {
        'plaintext': '[yellow]Plain[/yellow]',
        'tls': '[green]TLS[/green]',
        'sasl_scram': '[blue]SCRAM[/blue]',
        'sasl_iam': '[blue]IAM[/blue]',
        'public_tls': '[green]Pub-TLS[/green]',
        'public_sasl_scram': '[blue]Pub-SCRAM[/blue]',
        'public_sasl_iam': '[blue]Pub-IAM[/blue]',
        'vpc_tls': '[green]VPC-TLS[/green]',
        'vpc_sasl_scram': '[blue]VPC-SCRAM[/blue]',
        'vpc_sasl_iam': '[blue]VPC-IAM[/blue]'
    }
    
    formatted_types = []
    for conn in connection_types:
        conn_type = conn['type']
        count = conn['count']
        label = type_labels.get(conn_type, conn_type)
        formatted_types.append(f"{label}({count})")
    
    return " ".join(formatted_types)

def get_sample_endpoint(bootstrap_brokers):
    """샘플 엔드포인트를 반환합니다."""
    # 우선순위: TLS > PLAINTEXT > 기타
    priority_order = ['tls', 'plaintext', 'sasl_iam', 'sasl_scram']
    
    for conn_type in priority_order:
        if conn_type in bootstrap_brokers and bootstrap_brokers[conn_type]:
            endpoint = bootstrap_brokers[conn_type][0]
            # 긴 엔드포인트는 줄여서 표시
            if len(endpoint) > 35:
                return endpoint[:32] + "..."
            return endpoint
    
    # 다른 타입이 있으면 첫 번째 것 반환
    for conn_type, endpoints in bootstrap_brokers.items():
        if endpoints:
            endpoint = endpoints[0]
            if len(endpoint) > 35:
                return endpoint[:32] + "..."
            return endpoint
    
    return "N/A"

def print_detailed_endpoints(broker_info_list):
    """상세 엔드포인트 정보를 출력합니다."""
    console.print("\n[bold]📡 Detailed Broker Endpoints[/bold]")
    
    for broker in broker_info_list:
        console.print(f"\n[bold cyan]🔹 {broker['cluster_name']}[/bold cyan] ([dim]{broker['account_id']} - {broker['region']}[/dim])")
        
        bootstrap_brokers = broker.get('bootstrap_brokers', {})
        
        if not bootstrap_brokers:
            console.print("  [red]No endpoints available[/red]")
            continue
        
        # 연결 타입별로 엔드포인트 출력
        type_descriptions = {
            'plaintext': '🔓 PLAINTEXT (Port 9092)',
            'tls': '🔒 TLS (Port 9094)',
            'sasl_scram': '🔐 SASL/SCRAM',
            'sasl_iam': '🔐 SASL/IAM',
            'public_tls': '🌐 Public TLS',
            'public_sasl_scram': '🌐 Public SASL/SCRAM',
            'public_sasl_iam': '🌐 Public SASL/IAM',
            'vpc_tls': '🔗 VPC TLS',
            'vpc_sasl_scram': '🔗 VPC SASL/SCRAM',
            'vpc_sasl_iam': '🔗 VPC SASL/IAM'
        }
        
        for conn_type, endpoints in bootstrap_brokers.items():
            if endpoints:
                description = type_descriptions.get(conn_type, conn_type.upper())
                console.print(f"  [bold]{description}[/bold]")
                for endpoint in endpoints:
                    console.print(f"    • {endpoint}")

def main(args):
    """메인 함수"""
    accounts = args.account.split(",") if args.account else get_env_accounts()
    regions = args.regions.split(",") if args.regions else DEFINED_REGIONS
    profiles_map = get_profiles()
    
    all_broker_info = []
    
    with ThreadPoolExecutor() as executor:
        futures = []
        for acct in accounts:
            profile_name = profiles_map.get(acct)
            if not profile_name:
                log_info_non_console(f"Account {acct}에 대한 프로파일을 찾을 수 없습니다.")
                continue
            for reg in regions:
                futures.append(executor.submit(
                    fetch_msk_broker_info, 
                    acct, 
                    profile_name, 
                    reg, 
                    args.cluster
                ))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_broker_info.extend(result)
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_broker_info, args.output)
        print(output)
    else:
        format_table_output(all_broker_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
    parser.add_argument('-r', '--regions', help='리전 목록(,) (없으면 .env/DEFINED_REGIONS)')
    parser.add_argument('-c', '--cluster', help='클러스터 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml'], default='table', 
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MSK 브로커 엔드포인트 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)