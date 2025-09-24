#!/usr/bin/env python3
import os
import sys
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from azure.mgmt.storage import StorageManagementClient
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree

from common.log import log_info, log_error
from common.azure_utils import (
    get_azure_subscriptions,
    create_azure_client,
    get_resource_groups,
    format_azure_output,
    get_azure_resource_tags,
    parallel_azure_operation
)

load_dotenv()
console = Console()

def fetch_storage_info(subscription_id, location_filter=None, resource_group_filter=None, storage_name_filter=None):
    """Azure Storage Account 정보를 수집합니다."""
    log_info(f"Azure Storage Account 정보 수집 시작: Subscription={subscription_id}")
    
    storage_client = create_azure_client(StorageManagementClient, subscription_id)
    if not storage_client:
        return []
    
    try:
        storage_info_list = []
        
        # 리소스 그룹별로 Storage Account 조회
        resource_groups = get_resource_groups(subscription_id)
        
        for rg in resource_groups:
            rg_name = rg['name']
            
            # 리소스 그룹 필터 적용
            if resource_group_filter and resource_group_filter.lower() not in rg_name.lower():
                continue
            
            try:
                # Storage Account 목록 조회
                storage_accounts = storage_client.storage_accounts.list_by_resource_group(resource_group_name=rg_name)
                
                for storage_account in storage_accounts:
                    # Storage Account 이름 필터 적용
                    if storage_name_filter and storage_name_filter.lower() not in storage_account.name.lower():
                        continue
                    
                    # 위치 필터 적용
                    if location_filter and location_filter.lower() not in storage_account.location.lower():
                        continue
                    
                    # Storage Account 상세 정보 수집
                    storage_detail = collect_storage_details(storage_client, rg_name, storage_account, subscription_id)
                    if storage_detail:
                        storage_info_list.append(storage_detail)
                        
            except Exception as e:
                log_error(f"리소스 그룹 {rg_name}의 Storage Account 조회 실패: {e}")
                continue
        
        return storage_info_list
        
    except Exception as e:
        log_error(f"Azure Storage Account 목록 조회 실패: Subscription={subscription_id}, Error={e}")
        return []

def collect_storage_details(storage_client, resource_group_name, storage_account, subscription_id):
    """Storage Account의 상세 정보를 수집합니다."""
    try:
        # Storage Account 키 조회 (권한이 있는 경우)
        keys_info = []
        try:
            keys = storage_client.storage_accounts.list_keys(
                resource_group_name=resource_group_name,
                account_name=storage_account.name
            )
            for key in keys.keys:
                keys_info.append({
                    'key_name': key.key_name,
                    'permissions': str(key.permissions),
                    'creation_time': key.creation_time.isoformat() if key.creation_time else None
                })
        except Exception as e:
            log_error(f"Storage Account 키 조회 실패: {storage_account.name}, Error={e}")
        
        # Blob 서비스 속성
        blob_services = []
        try:
            blob_service = storage_client.blob_services.get_service_properties(
                resource_group_name=resource_group_name,
                account_name=storage_account.name
            )
            
            blob_services.append({
                'cors_rules': len(blob_service.cors.cors_rules) if blob_service.cors and blob_service.cors.cors_rules else 0,
                'delete_retention_policy_enabled': blob_service.delete_retention_policy.enabled if blob_service.delete_retention_policy else False,
                'delete_retention_days': blob_service.delete_retention_policy.days if blob_service.delete_retention_policy else None,
                'versioning_enabled': blob_service.is_versioning_enabled if hasattr(blob_service, 'is_versioning_enabled') else False,
                'change_feed_enabled': blob_service.change_feed.enabled if hasattr(blob_service, 'change_feed') and blob_service.change_feed else False
            })
        except Exception as e:
            log_error(f"Blob 서비스 속성 조회 실패: {storage_account.name}, Error={e}")
        
        # 컨테이너 목록 조회
        containers_info = []
        try:
            containers = storage_client.blob_containers.list(
                resource_group_name=resource_group_name,
                account_name=storage_account.name
            )
            
            for container in containers:
                container_detail = {
                    'name': container.name,
                    'public_access': str(container.public_access) if container.public_access else 'None',
                    'last_modified_time': container.last_modified_time.isoformat() if container.last_modified_time else None,
                    'lease_status': str(container.lease_status) if container.lease_status else 'Unlocked',
                    'lease_state': str(container.lease_state) if container.lease_state else 'Available',
                    'has_immutability_policy': container.has_immutability_policy if hasattr(container, 'has_immutability_policy') else False,
                    'has_legal_hold': container.has_legal_hold if hasattr(container, 'has_legal_hold') else False,
                    'metadata': dict(container.metadata) if container.metadata else {}
                }
                containers_info.append(container_detail)
        except Exception as e:
            log_error(f"컨테이너 목록 조회 실패: {storage_account.name}, Error={e}")
        
        # 파일 공유 목록 조회
        file_shares_info = []
        try:
            file_shares = storage_client.file_shares.list(
                resource_group_name=resource_group_name,
                account_name=storage_account.name
            )
            
            for file_share in file_shares:
                share_detail = {
                    'name': file_share.name,
                    'quota': file_share.share_quota if hasattr(file_share, 'share_quota') else None,
                    'last_modified_time': file_share.last_modified_time.isoformat() if file_share.last_modified_time else None,
                    'access_tier': str(file_share.access_tier) if hasattr(file_share, 'access_tier') and file_share.access_tier else None,
                    'enabled_protocols': str(file_share.enabled_protocols) if hasattr(file_share, 'enabled_protocols') and file_share.enabled_protocols else 'SMB',
                    'metadata': dict(file_share.metadata) if file_share.metadata else {}
                }
                file_shares_info.append(share_detail)
        except Exception as e:
            log_error(f"파일 공유 목록 조회 실패: {storage_account.name}, Error={e}")
        
        # 네트워크 규칙
        network_rules = {}
        if storage_account.network_rule_set:
            network_rules = {
                'default_action': str(storage_account.network_rule_set.default_action),
                'bypass': str(storage_account.network_rule_set.bypass) if storage_account.network_rule_set.bypass else 'None',
                'ip_rules_count': len(storage_account.network_rule_set.ip_rules) if storage_account.network_rule_set.ip_rules else 0,
                'virtual_network_rules_count': len(storage_account.network_rule_set.virtual_network_rules) if storage_account.network_rule_set.virtual_network_rules else 0
            }
        
        # 암호화 설정
        encryption_info = {}
        if storage_account.encryption:
            encryption_info = {
                'key_source': str(storage_account.encryption.key_source) if storage_account.encryption.key_source else 'Microsoft.Storage',
                'blob_enabled': storage_account.encryption.services.blob.enabled if storage_account.encryption.services and storage_account.encryption.services.blob else False,
                'file_enabled': storage_account.encryption.services.file.enabled if storage_account.encryption.services and storage_account.encryption.services.file else False,
                'queue_enabled': storage_account.encryption.services.queue.enabled if storage_account.encryption.services and storage_account.encryption.services.queue else False,
                'table_enabled': storage_account.encryption.services.table.enabled if storage_account.encryption.services and storage_account.encryption.services.table else False
            }
        
        # Storage Account 정보 구성
        storage_data = {
            'subscription_id': subscription_id,
            'resource_group': resource_group_name,
            'storage_account': {
                'name': storage_account.name,
                'id': storage_account.id,
                'location': storage_account.location,
                'kind': str(storage_account.kind),
                'sku_name': str(storage_account.sku.name),
                'sku_tier': str(storage_account.sku.tier),
                'provisioning_state': str(storage_account.provisioning_state),
                'creation_time': storage_account.creation_time.isoformat() if storage_account.creation_time else None,
                'primary_location': storage_account.primary_location,
                'secondary_location': storage_account.secondary_location,
                'status_of_primary': str(storage_account.status_of_primary) if storage_account.status_of_primary else 'Available',
                'status_of_secondary': str(storage_account.status_of_secondary) if storage_account.status_of_secondary else None,
                'access_tier': str(storage_account.access_tier) if storage_account.access_tier else None,
                'enable_https_traffic_only': storage_account.enable_https_traffic_only,
                'allow_blob_public_access': storage_account.allow_blob_public_access if hasattr(storage_account, 'allow_blob_public_access') else True,
                'minimum_tls_version': str(storage_account.minimum_tls_version) if hasattr(storage_account, 'minimum_tls_version') and storage_account.minimum_tls_version else 'TLS1_0',
                'tags': get_azure_resource_tags(storage_account),
                'keys': keys_info,
                'blob_services': blob_services,
                'containers': containers_info,
                'file_shares': file_shares_info,
                'network_rules': network_rules,
                'encryption': encryption_info,
                'container_count': len(containers_info),
                'file_share_count': len(file_shares_info)
            }
        }
        
        # 엔드포인트 정보
        if storage_account.primary_endpoints:
            storage_data['storage_account']['primary_endpoints'] = {
                'blob': storage_account.primary_endpoints.blob,
                'queue': storage_account.primary_endpoints.queue,
                'table': storage_account.primary_endpoints.table,
                'file': storage_account.primary_endpoints.file,
                'web': storage_account.primary_endpoints.web if hasattr(storage_account.primary_endpoints, 'web') else None,
                'dfs': storage_account.primary_endpoints.dfs if hasattr(storage_account.primary_endpoints, 'dfs') else None
            }
        
        return storage_data
        
    except Exception as e:
        log_error(f"Storage Account 상세 정보 수집 실패: {storage_account.name}, Error={e}")
        return None

def format_output(storage_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return format_azure_output(storage_info_list, 'json')
    elif output_format == 'yaml':
        return format_azure_output(storage_info_list, 'yaml')
    elif output_format == 'tree':
        return format_tree_output(storage_info_list)
    else:
        return format_table_output(storage_info_list)

def format_tree_output(storage_info_list):
    """트리 형식으로 출력합니다."""
    if not storage_info_list:
        console.print("[yellow]표시할 Azure Storage Account가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for storage_info in storage_info_list:
        subscription_id = storage_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = {}
        
        resource_group = storage_info['resource_group']
        if resource_group not in subscriptions[subscription_id]:
            subscriptions[subscription_id][resource_group] = []
        
        subscriptions[subscription_id][resource_group].append(storage_info)
    
    tree = Tree("💾 [bold blue]Azure Storage Accounts[/bold blue]")
    
    for subscription_id, resource_groups in subscriptions.items():
        sub_tree = tree.add(f"📋 Subscription: {subscription_id}")
        
        for rg_name, storage_accounts in resource_groups.items():
            rg_tree = sub_tree.add(f"📁 Resource Group: [magenta]{rg_name}[/magenta]")
            
            for storage_info in storage_accounts:
                storage = storage_info['storage_account']
                storage_tree = rg_tree.add(f"💾 [cyan]{storage['name']}[/cyan] ({storage['sku_name']})")
                
                # 기본 정보
                storage_tree.add(f"📍 Location: [green]{storage['location']}[/green]")
                storage_tree.add(f"📊 State: {format_provisioning_state_simple(storage['provisioning_state'])}")
                storage_tree.add(f"🏷️ Kind: {storage['kind']}")
                storage_tree.add(f"🔒 HTTPS Only: {'✅' if storage['enable_https_traffic_only'] else '❌'}")
                
                # 엔드포인트
                if storage.get('primary_endpoints'):
                    endpoint_tree = storage_tree.add("🌐 Endpoints")
                    endpoints = storage['primary_endpoints']
                    if endpoints.get('blob'):
                        endpoint_tree.add(f"📦 Blob: {endpoints['blob']}")
                    if endpoints.get('file'):
                        endpoint_tree.add(f"📁 File: {endpoints['file']}")
                    if endpoints.get('queue'):
                        endpoint_tree.add(f"📬 Queue: {endpoints['queue']}")
                    if endpoints.get('table'):
                        endpoint_tree.add(f"📊 Table: {endpoints['table']}")
                
                # 컨테이너
                if storage['containers']:
                    container_tree = storage_tree.add(f"📦 Blob Containers ({len(storage['containers'])})")
                    for container in storage['containers'][:5]:  # 처음 5개만 표시
                        access_level = container['public_access'] if container['public_access'] != 'None' else 'Private'
                        container_tree.add(f"📦 {container['name']} ({access_level})")
                    if len(storage['containers']) > 5:
                        container_tree.add(f"... and {len(storage['containers']) - 5} more")
                
                # 파일 공유
                if storage['file_shares']:
                    share_tree = storage_tree.add(f"📁 File Shares ({len(storage['file_shares'])})")
                    for share in storage['file_shares'][:5]:  # 처음 5개만 표시
                        quota_info = f" ({share['quota']}GB)" if share.get('quota') else ""
                        share_tree.add(f"📁 {share['name']}{quota_info}")
                    if len(storage['file_shares']) > 5:
                        share_tree.add(f"... and {len(storage['file_shares']) - 5} more")
    
    console.print(tree)

def format_table_output(storage_info_list):
    """테이블 형식으로 출력합니다."""
    if not storage_info_list:
        console.print("[yellow]표시할 Azure Storage Account가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for storage_info in storage_info_list:
        subscription_id = storage_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = []
        subscriptions[subscription_id].append(storage_info)
    
    for subscription_id, subscription_storage in subscriptions.items():
        console.print(f"\n[bold blue]🔹 Subscription: {subscription_id}[/bold blue]")
        
        # Storage Account 요약 테이블
        console.print(f"\n[bold]💾 Storage Accounts ({len(subscription_storage)} accounts)[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("Account Name", style="cyan")
        summary_table.add_column("Resource Group", style="magenta")
        summary_table.add_column("Location", style="green")
        summary_table.add_column("SKU", style="yellow")
        summary_table.add_column("Kind", style="blue")
        summary_table.add_column("Containers", justify="center")
        summary_table.add_column("File Shares", justify="center")
        summary_table.add_column("HTTPS Only", justify="center")
        summary_table.add_column("State", justify="center")
        
        for storage_info in subscription_storage:
            storage = storage_info['storage_account']
            
            summary_table.add_row(
                storage.get('name', '-'),
                storage_info.get('resource_group', '-'),
                storage.get('location', '-'),
                storage.get('sku_name', '-'),
                storage.get('kind', '-'),
                str(storage.get('container_count', 0)),
                str(storage.get('file_share_count', 0)),
                '✅' if storage.get('enable_https_traffic_only', False) else '❌',
                format_provisioning_state(storage.get('provisioning_state', 'Unknown'))
            )
        
        console.print(summary_table)
        
        # 컨테이너 상세 정보 (컨테이너가 있는 경우)
        for storage_info in subscription_storage:
            storage = storage_info['storage_account']
            if storage.get('containers'):
                console.print(f"\n[bold]📦 Blob Containers for {storage['name']}[/bold]")
                container_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
                container_table.add_column("Container Name", style="cyan")
                container_table.add_column("Public Access", style="red")
                container_table.add_column("Lease Status", style="yellow")
                container_table.add_column("Last Modified", style="blue")
                container_table.add_column("Immutability Policy", justify="center")
                container_table.add_column("Legal Hold", justify="center")
                
                for container in storage['containers'][:10]:  # 처음 10개만 표시
                    last_modified = container.get('last_modified_time', '')
                    if last_modified:
                        last_modified = last_modified.split('T')[0]  # 날짜만 표시
                    
                    container_table.add_row(
                        container.get('name', '-'),
                        container.get('public_access', 'None'),
                        container.get('lease_status', 'Unlocked'),
                        last_modified or '-',
                        '✅' if container.get('has_immutability_policy', False) else '❌',
                        '✅' if container.get('has_legal_hold', False) else '❌'
                    )
                
                console.print(container_table)
                
                if len(storage['containers']) > 10:
                    console.print(f"[dim]... and {len(storage['containers']) - 10} more containers[/dim]")
        
        # 위치별 통계
        location_stats = {}
        for storage_info in subscription_storage:
            location = storage_info['storage_account'].get('location', 'Unknown')
            if location not in location_stats:
                location_stats[location] = {'accounts': 0, 'containers': 0, 'file_shares': 0}
            location_stats[location]['accounts'] += 1
            location_stats[location]['containers'] += storage_info['storage_account'].get('container_count', 0)
            location_stats[location]['file_shares'] += storage_info['storage_account'].get('file_share_count', 0)
        
        if len(location_stats) > 1:
            console.print(f"\n[bold]📊 Location Statistics[/bold]")
            stats_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            stats_table.add_column("Location", style="green")
            stats_table.add_column("Accounts", justify="center")
            stats_table.add_column("Total Containers", justify="center")
            stats_table.add_column("Total File Shares", justify="center")
            
            for location, stats in sorted(location_stats.items()):
                stats_table.add_row(
                    location,
                    str(stats['accounts']),
                    str(stats['containers']),
                    str(stats['file_shares'])
                )
            
            console.print(stats_table)

def format_provisioning_state(state):
    """프로비저닝 상태에 따라 색상을 적용합니다."""
    state_lower = state.lower()
    if 'succeeded' in state_lower:
        return f"[bold green]{state}[/bold green]"
    elif 'failed' in state_lower:
        return f"[bold red]{state}[/bold red]"
    elif 'creating' in state_lower:
        return f"[bold yellow]{state}[/bold yellow]"
    else:
        return state

def format_provisioning_state_simple(state):
    """트리용 간단한 상태 포맷"""
    state_lower = state.lower()
    if 'succeeded' in state_lower:
        return f"[green]{state}[/green]"
    elif 'failed' in state_lower:
        return f"[red]{state}[/red]"
    else:
        return state

def main(args):
    """메인 함수"""
    subscriptions = args.subscription.split(",") if args.subscription else get_azure_subscriptions()
    
    if not subscriptions:
        log_error("Azure 구독을 찾을 수 없습니다. AZURE_SUBSCRIPTIONS 환경변수를 설정하거나 Azure CLI로 로그인하세요.")
        return
    
    all_storage_info = parallel_azure_operation(
        fetch_storage_info,
        subscriptions,
        args.location,
        args.resource_group,
        args.name
    )
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_storage_info, args.output)
        print(output)
    elif args.output == 'tree':
        format_tree_output(all_storage_info)
    else:
        format_table_output(all_storage_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-s', '--subscription', help='특정 Azure 구독 ID 목록(,) (없으면 모든 구독 사용)')
    parser.add_argument('-l', '--location', help='위치 필터 (부분 일치)')
    parser.add_argument('-g', '--resource-group', help='리소스 그룹 필터 (부분 일치)')
    parser.add_argument('-n', '--name', help='Storage Account 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml', 'tree'], default='table',
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure Storage Account 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)