#!/usr/bin/env python3
import os
import sys
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from azure.mgmt.containerservice import ContainerServiceClient
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

def fetch_aks_info(subscription_id, location_filter=None, resource_group_filter=None, cluster_name_filter=None):
    """Azure AKS 클러스터 정보를 수집합니다."""
    log_info(f"Azure AKS 정보 수집 시작: Subscription={subscription_id}")
    
    aks_client = create_azure_client(ContainerServiceClient, subscription_id)
    if not aks_client:
        return []
    
    try:
        aks_info_list = []
        
        # 리소스 그룹별로 AKS 클러스터 조회
        resource_groups = get_resource_groups(subscription_id)
        
        for rg in resource_groups:
            rg_name = rg['name']
            
            # 리소스 그룹 필터 적용
            if resource_group_filter and resource_group_filter.lower() not in rg_name.lower():
                continue
            
            try:
                # AKS 클러스터 목록 조회
                clusters = aks_client.managed_clusters.list_by_resource_group(resource_group_name=rg_name)
                
                for cluster in clusters:
                    # 클러스터 이름 필터 적용
                    if cluster_name_filter and cluster_name_filter.lower() not in cluster.name.lower():
                        continue
                    
                    # 위치 필터 적용
                    if location_filter and location_filter.lower() not in cluster.location.lower():
                        continue
                    
                    # AKS 클러스터 상세 정보 수집
                    cluster_detail = collect_aks_details(aks_client, rg_name, cluster, subscription_id)
                    if cluster_detail:
                        aks_info_list.append(cluster_detail)
                        
            except Exception as e:
                log_error(f"리소스 그룹 {rg_name}의 AKS 클러스터 조회 실패: {e}")
                continue
        
        return aks_info_list
        
    except Exception as e:
        log_error(f"Azure AKS 목록 조회 실패: Subscription={subscription_id}, Error={e}")
        return []

def collect_aks_details(aks_client, resource_group_name, cluster, subscription_id):
    """AKS 클러스터의 상세 정보를 수집합니다."""
    try:
        # 노드 풀 정보
        node_pools_info = []
        if cluster.agent_pool_profiles:
            for pool in cluster.agent_pool_profiles:
                pool_detail = {
                    'name': pool.name,
                    'count': pool.count,
                    'vm_size': pool.vm_size,
                    'os_type': str(pool.os_type) if pool.os_type else 'Linux',
                    'os_disk_size_gb': pool.os_disk_size_gb,
                    'max_pods': pool.max_pods,
                    'provisioning_state': str(pool.provisioning_state) if pool.provisioning_state else 'Unknown',
                    'availability_zones': list(pool.availability_zones) if pool.availability_zones else [],
                    'enable_auto_scaling': pool.enable_auto_scaling if hasattr(pool, 'enable_auto_scaling') else False,
                    'min_count': pool.min_count if hasattr(pool, 'min_count') else None,
                    'max_count': pool.max_count if hasattr(pool, 'max_count') else None,
                    'node_taints': list(pool.node_taints) if hasattr(pool, 'node_taints') and pool.node_taints else [],
                    'node_labels': dict(pool.node_labels) if hasattr(pool, 'node_labels') and pool.node_labels else {}
                }
                
                # 스케일링 모드
                if hasattr(pool, 'mode'):
                    pool_detail['mode'] = str(pool.mode)
                
                node_pools_info.append(pool_detail)
        
        # 네트워크 프로필
        network_profile = {}
        if cluster.network_profile:
            network_profile = {
                'network_plugin': str(cluster.network_profile.network_plugin) if cluster.network_profile.network_plugin else 'kubenet',
                'network_policy': str(cluster.network_profile.network_policy) if cluster.network_profile.network_policy else None,
                'pod_cidr': cluster.network_profile.pod_cidr,
                'service_cidr': cluster.network_profile.service_cidr,
                'dns_service_ip': cluster.network_profile.dns_service_ip,
                'docker_bridge_cidr': cluster.network_profile.docker_bridge_cidr,
                'load_balancer_sku': str(cluster.network_profile.load_balancer_sku) if cluster.network_profile.load_balancer_sku else 'Standard'
            }
        
        # 애드온 프로필
        addon_profiles = {}
        if cluster.addon_profiles:
            for addon_name, addon_config in cluster.addon_profiles.items():
                addon_profiles[addon_name] = {
                    'enabled': addon_config.enabled,
                    'config': dict(addon_config.config) if addon_config.config else {}
                }
        
        # 서비스 주체 또는 관리 ID
        identity_info = {}
        if cluster.service_principal_profile:
            identity_info['type'] = 'ServicePrincipal'
            identity_info['client_id'] = cluster.service_principal_profile.client_id
        elif cluster.identity:
            identity_info['type'] = str(cluster.identity.type)
            if cluster.identity.user_assigned_identities:
                identity_info['user_assigned_identities'] = list(cluster.identity.user_assigned_identities.keys())
        
        # API 서버 접근 프로필
        api_server_profile = {}
        if hasattr(cluster, 'api_server_access_profile') and cluster.api_server_access_profile:
            api_server_profile = {
                'enable_private_cluster': cluster.api_server_access_profile.enable_private_cluster,
                'authorized_ip_ranges': list(cluster.api_server_access_profile.authorized_ip_ranges) if cluster.api_server_access_profile.authorized_ip_ranges else []
            }
        
        # AKS 클러스터 정보 구성
        aks_data = {
            'subscription_id': subscription_id,
            'resource_group': resource_group_name,
            'cluster': {
                'name': cluster.name,
                'id': cluster.id,
                'location': cluster.location,
                'provisioning_state': str(cluster.provisioning_state),
                'kubernetes_version': cluster.kubernetes_version,
                'dns_prefix': cluster.dns_prefix,
                'fqdn': cluster.fqdn,
                'private_fqdn': cluster.private_fqdn if hasattr(cluster, 'private_fqdn') else None,
                'enable_rbac': cluster.enable_rbac if hasattr(cluster, 'enable_rbac') else True,
                'tags': get_azure_resource_tags(cluster),
                'node_pools': node_pools_info,
                'network_profile': network_profile,
                'addon_profiles': addon_profiles,
                'identity': identity_info,
                'api_server_access_profile': api_server_profile,
                'node_pool_count': len(node_pools_info),
                'total_node_count': sum(pool.get('count', 0) for pool in node_pools_info)
            }
        }
        
        # 자동 스케일러 프로필
        if hasattr(cluster, 'auto_scaler_profile') and cluster.auto_scaler_profile:
            aks_data['cluster']['auto_scaler_profile'] = {
                'balance_similar_node_groups': cluster.auto_scaler_profile.balance_similar_node_groups,
                'expander': str(cluster.auto_scaler_profile.expander) if cluster.auto_scaler_profile.expander else None,
                'max_empty_bulk_delete': cluster.auto_scaler_profile.max_empty_bulk_delete,
                'max_graceful_termination_sec': cluster.auto_scaler_profile.max_graceful_termination_sec,
                'max_node_provision_time': cluster.auto_scaler_profile.max_node_provision_time,
                'max_total_unready_percentage': cluster.auto_scaler_profile.max_total_unready_percentage,
                'new_pod_scale_up_delay': cluster.auto_scaler_profile.new_pod_scale_up_delay,
                'ok_total_unready_count': cluster.auto_scaler_profile.ok_total_unready_count,
                'scale_down_delay_after_add': cluster.auto_scaler_profile.scale_down_delay_after_add,
                'scale_down_delay_after_delete': cluster.auto_scaler_profile.scale_down_delay_after_delete,
                'scale_down_delay_after_failure': cluster.auto_scaler_profile.scale_down_delay_after_failure,
                'scale_down_unneeded_time': cluster.auto_scaler_profile.scale_down_unneeded_time,
                'scale_down_unready_time': cluster.auto_scaler_profile.scale_down_unready_time,
                'scale_down_utilization_threshold': cluster.auto_scaler_profile.scale_down_utilization_threshold,
                'scan_interval': cluster.auto_scaler_profile.scan_interval,
                'skip_nodes_with_local_storage': cluster.auto_scaler_profile.skip_nodes_with_local_storage,
                'skip_nodes_with_system_pods': cluster.auto_scaler_profile.skip_nodes_with_system_pods
            }
        
        return aks_data
        
    except Exception as e:
        log_error(f"AKS 클러스터 상세 정보 수집 실패: {cluster.name}, Error={e}")
        return None

def format_output(aks_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return format_azure_output(aks_info_list, 'json')
    elif output_format == 'yaml':
        return format_azure_output(aks_info_list, 'yaml')
    elif output_format == 'tree':
        return format_tree_output(aks_info_list)
    else:
        return format_table_output(aks_info_list)

def format_tree_output(aks_info_list):
    """트리 형식으로 출력합니다."""
    if not aks_info_list:
        console.print("[yellow]표시할 Azure AKS 클러스터가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for aks_info in aks_info_list:
        subscription_id = aks_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = {}
        
        resource_group = aks_info['resource_group']
        if resource_group not in subscriptions[subscription_id]:
            subscriptions[subscription_id][resource_group] = []
        
        subscriptions[subscription_id][resource_group].append(aks_info)
    
    tree = Tree("☸️ [bold blue]Azure Kubernetes Service (AKS)[/bold blue]")
    
    for subscription_id, resource_groups in subscriptions.items():
        sub_tree = tree.add(f"📋 Subscription: {subscription_id}")
        
        for rg_name, clusters in resource_groups.items():
            rg_tree = sub_tree.add(f"📁 Resource Group: [magenta]{rg_name}[/magenta]")
            
            for aks_info in clusters:
                cluster = aks_info['cluster']
                cluster_tree = rg_tree.add(f"☸️ [cyan]{cluster['name']}[/cyan] (v{cluster['kubernetes_version']})")
                
                # 기본 정보
                cluster_tree.add(f"📍 Location: [green]{cluster['location']}[/green]")
                cluster_tree.add(f"📊 State: {format_provisioning_state_simple(cluster['provisioning_state'])}")
                cluster_tree.add(f"🌐 FQDN: {cluster['fqdn']}")
                cluster_tree.add(f"🔐 RBAC: {'✅' if cluster['enable_rbac'] else '❌'}")
                
                # 노드 풀
                if cluster['node_pools']:
                    pool_tree = cluster_tree.add(f"🖥️ Node Pools ({len(cluster['node_pools'])})")
                    for pool in cluster['node_pools']:
                        pool_node = pool_tree.add(f"🔧 {pool['name']} ({pool['vm_size']})")
                        pool_node.add(f"📊 Nodes: {pool['count']}")
                        pool_node.add(f"🐧 OS: {pool['os_type']}")
                        if pool['enable_auto_scaling']:
                            pool_node.add(f"📈 Auto Scaling: {pool['min_count']}-{pool['max_count']}")
                        if pool['availability_zones']:
                            pool_node.add(f"🌍 Zones: {', '.join(pool['availability_zones'])}")
                
                # 네트워크
                if cluster['network_profile']:
                    net_tree = cluster_tree.add("🌐 Network")
                    net_tree.add(f"🔌 Plugin: {cluster['network_profile']['network_plugin']}")
                    if cluster['network_profile']['network_policy']:
                        net_tree.add(f"🛡️ Policy: {cluster['network_profile']['network_policy']}")
                    if cluster['network_profile']['service_cidr']:
                        net_tree.add(f"🏠 Service CIDR: {cluster['network_profile']['service_cidr']}")
                
                # 애드온
                if cluster['addon_profiles']:
                    addon_tree = cluster_tree.add("🔧 Add-ons")
                    for addon_name, addon_config in cluster['addon_profiles'].items():
                        status = "✅" if addon_config['enabled'] else "❌"
                        addon_tree.add(f"{status} {addon_name}")
    
    console.print(tree)

def format_table_output(aks_info_list):
    """테이블 형식으로 출력합니다."""
    if not aks_info_list:
        console.print("[yellow]표시할 Azure AKS 클러스터가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for aks_info in aks_info_list:
        subscription_id = aks_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = []
        subscriptions[subscription_id].append(aks_info)
    
    for subscription_id, subscription_clusters in subscriptions.items():
        console.print(f"\n[bold blue]🔹 Subscription: {subscription_id}[/bold blue]")
        
        # AKS 클러스터 요약 테이블
        console.print(f"\n[bold]☸️ AKS Clusters ({len(subscription_clusters)} clusters)[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("Cluster Name", style="cyan")
        summary_table.add_column("Resource Group", style="magenta")
        summary_table.add_column("Location", style="green")
        summary_table.add_column("K8s Version", style="yellow")
        summary_table.add_column("Node Pools", justify="center")
        summary_table.add_column("Total Nodes", justify="center")
        summary_table.add_column("State", justify="center")
        summary_table.add_column("RBAC", justify="center")
        
        for aks_info in subscription_clusters:
            cluster = aks_info['cluster']
            
            summary_table.add_row(
                cluster.get('name', '-'),
                aks_info.get('resource_group', '-'),
                cluster.get('location', '-'),
                cluster.get('kubernetes_version', '-'),
                str(cluster.get('node_pool_count', 0)),
                str(cluster.get('total_node_count', 0)),
                format_provisioning_state(cluster.get('provisioning_state', 'Unknown')),
                '✅' if cluster.get('enable_rbac', False) else '❌'
            )
        
        console.print(summary_table)
        
        # 노드 풀 상세 정보
        for aks_info in subscription_clusters:
            cluster = aks_info['cluster']
            if cluster.get('node_pools'):
                console.print(f"\n[bold]🖥️ Node Pools for {cluster['name']}[/bold]")
                pool_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
                pool_table.add_column("Pool Name", style="cyan")
                pool_table.add_column("VM Size", style="yellow")
                pool_table.add_column("OS Type", style="green")
                pool_table.add_column("Node Count", justify="center")
                pool_table.add_column("Auto Scaling", justify="center")
                pool_table.add_column("Max Pods", justify="center")
                pool_table.add_column("Zones", style="blue")
                pool_table.add_column("State", justify="center")
                
                for pool in cluster['node_pools']:
                    auto_scaling = "❌"
                    if pool.get('enable_auto_scaling'):
                        auto_scaling = f"✅ ({pool.get('min_count', 0)}-{pool.get('max_count', 0)})"
                    
                    zones = ', '.join(pool.get('availability_zones', [])) if pool.get('availability_zones') else '-'
                    
                    pool_table.add_row(
                        pool.get('name', '-'),
                        pool.get('vm_size', '-'),
                        pool.get('os_type', '-'),
                        str(pool.get('count', 0)),
                        auto_scaling,
                        str(pool.get('max_pods', '-')),
                        zones,
                        format_provisioning_state(pool.get('provisioning_state', 'Unknown'))
                    )
                
                console.print(pool_table)
        
        # 위치별 통계
        location_stats = {}
        for aks_info in subscription_clusters:
            location = aks_info['cluster'].get('location', 'Unknown')
            if location not in location_stats:
                location_stats[location] = {'clusters': 0, 'total_nodes': 0, 'node_pools': 0}
            location_stats[location]['clusters'] += 1
            location_stats[location]['total_nodes'] += aks_info['cluster'].get('total_node_count', 0)
            location_stats[location]['node_pools'] += aks_info['cluster'].get('node_pool_count', 0)
        
        if len(location_stats) > 1:
            console.print(f"\n[bold]📊 Location Statistics[/bold]")
            stats_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            stats_table.add_column("Location", style="green")
            stats_table.add_column("Clusters", justify="center")
            stats_table.add_column("Total Nodes", justify="center")
            stats_table.add_column("Node Pools", justify="center")
            
            for location, stats in sorted(location_stats.items()):
                stats_table.add_row(
                    location,
                    str(stats['clusters']),
                    str(stats['total_nodes']),
                    str(stats['node_pools'])
                )
            
            console.print(stats_table)

def format_provisioning_state(state):
    """프로비저닝 상태에 따라 색상을 적용합니다."""
    state_lower = state.lower()
    if 'succeeded' in state_lower:
        return f"[bold green]{state}[/bold green]"
    elif 'failed' in state_lower:
        return f"[bold red]{state}[/bold red]"
    elif 'updating' in state_lower or 'creating' in state_lower:
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
    
    all_aks_info = parallel_azure_operation(
        fetch_aks_info,
        subscriptions,
        args.location,
        args.resource_group,
        args.name
    )
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_aks_info, args.output)
        print(output)
    elif args.output == 'tree':
        format_tree_output(all_aks_info)
    else:
        format_table_output(all_aks_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-s', '--subscription', help='특정 Azure 구독 ID 목록(,) (없으면 모든 구독 사용)')
    parser.add_argument('-l', '--location', help='위치 필터 (부분 일치)')
    parser.add_argument('-g', '--resource-group', help='리소스 그룹 필터 (부분 일치)')
    parser.add_argument('-n', '--name', help='AKS 클러스터 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml', 'tree'], default='table',
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure AKS 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)