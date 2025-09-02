#!/usr/bin/env python3
import os
import sys
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from azure.mgmt.network import NetworkManagementClient
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

def fetch_vnet_info(subscription_id, location_filter=None, resource_group_filter=None, vnet_name_filter=None):
    """Azure VNet 정보를 수집합니다."""
    log_info(f"Azure VNet 정보 수집 시작: Subscription={subscription_id}")
    
    network_client = create_azure_client(NetworkManagementClient, subscription_id)
    if not network_client:
        return []
    
    try:
        vnet_info_list = []
        
        # 리소스 그룹별로 VNet 조회
        resource_groups = get_resource_groups(subscription_id)
        
        for rg in resource_groups:
            rg_name = rg['name']
            
            # 리소스 그룹 필터 적용
            if resource_group_filter and resource_group_filter.lower() not in rg_name.lower():
                continue
            
            try:
                # VNet 목록 조회
                vnets = network_client.virtual_networks.list(resource_group_name=rg_name)
                
                for vnet in vnets:
                    # VNet 이름 필터 적용
                    if vnet_name_filter and vnet_name_filter.lower() not in vnet.name.lower():
                        continue
                    
                    # 위치 필터 적용
                    if location_filter and location_filter.lower() not in vnet.location.lower():
                        continue
                    
                    # VNet 상세 정보 수집
                    vnet_detail = collect_vnet_details(network_client, rg_name, vnet, subscription_id)
                    if vnet_detail:
                        vnet_info_list.append(vnet_detail)
                        
            except Exception as e:
                log_error(f"리소스 그룹 {rg_name}의 VNet 조회 실패: {e}")
                continue
        
        return vnet_info_list
        
    except Exception as e:
        log_error(f"Azure VNet 목록 조회 실패: Subscription={subscription_id}, Error={e}")
        return []

def collect_vnet_details(network_client, resource_group_name, vnet, subscription_id):
    """VNet의 상세 정보를 수집합니다."""
    try:
        # 서브넷 정보 수집
        subnets_info = []
        if vnet.subnets:
            for subnet in vnet.subnets:
                subnet_detail = {
                    'name': subnet.name,
                    'id': subnet.id,
                    'address_prefix': subnet.address_prefix,
                    'provisioning_state': str(subnet.provisioning_state),
                    'private_endpoint_network_policies': str(subnet.private_endpoint_network_policies) if subnet.private_endpoint_network_policies else 'Enabled',
                    'private_link_service_network_policies': str(subnet.private_link_service_network_policies) if subnet.private_link_service_network_policies else 'Enabled'
                }
                
                # 네트워크 보안 그룹
                if subnet.network_security_group:
                    subnet_detail['network_security_group'] = subnet.network_security_group.id
                
                # 라우트 테이블
                if subnet.route_table:
                    subnet_detail['route_table'] = subnet.route_table.id
                
                # 연결된 리소스 수
                connected_resources = 0
                if subnet.ip_configurations:
                    connected_resources += len(subnet.ip_configurations)
                subnet_detail['connected_resources'] = connected_resources
                
                subnets_info.append(subnet_detail)
        
        # VNet 피어링 정보
        peerings_info = []
        if vnet.virtual_network_peerings:
            for peering in vnet.virtual_network_peerings:
                peering_detail = {
                    'name': peering.name,
                    'id': peering.id,
                    'peering_state': str(peering.peering_state),
                    'provisioning_state': str(peering.provisioning_state),
                    'allow_virtual_network_access': peering.allow_virtual_network_access,
                    'allow_forwarded_traffic': peering.allow_forwarded_traffic,
                    'allow_gateway_transit': peering.allow_gateway_transit,
                    'use_remote_gateways': peering.use_remote_gateways
                }
                
                if peering.remote_virtual_network:
                    peering_detail['remote_vnet_id'] = peering.remote_virtual_network.id
                
                peerings_info.append(peering_detail)
        
        # DNS 서버 정보
        dns_servers = []
        if vnet.dhcp_options and vnet.dhcp_options.dns_servers:
            dns_servers = list(vnet.dhcp_options.dns_servers)
        
        # VNet 정보 구성
        vnet_data = {
            'subscription_id': subscription_id,
            'resource_group': resource_group_name,
            'vnet': {
                'name': vnet.name,
                'id': vnet.id,
                'location': vnet.location,
                'provisioning_state': str(vnet.provisioning_state),
                'address_space': list(vnet.address_space.address_prefixes) if vnet.address_space else [],
                'dns_servers': dns_servers,
                'enable_ddos_protection': vnet.enable_ddos_protection if hasattr(vnet, 'enable_ddos_protection') else False,
                'enable_vm_protection': vnet.enable_vm_protection if hasattr(vnet, 'enable_vm_protection') else False,
                'tags': get_azure_resource_tags(vnet),
                'subnets': subnets_info,
                'peerings': peerings_info,
                'subnet_count': len(subnets_info),
                'peering_count': len(peerings_info)
            }
        }
        
        return vnet_data
        
    except Exception as e:
        log_error(f"VNet 상세 정보 수집 실패: {vnet.name}, Error={e}")
        return None

def format_output(vnet_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return format_azure_output(vnet_info_list, 'json')
    elif output_format == 'yaml':
        return format_azure_output(vnet_info_list, 'yaml')
    elif output_format == 'tree':
        return format_tree_output(vnet_info_list)
    else:
        return format_table_output(vnet_info_list)

def format_tree_output(vnet_info_list):
    """트리 형식으로 출력합니다."""
    if not vnet_info_list:
        console.print("[yellow]표시할 Azure VNet이 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for vnet_info in vnet_info_list:
        subscription_id = vnet_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = {}
        
        resource_group = vnet_info['resource_group']
        if resource_group not in subscriptions[subscription_id]:
            subscriptions[subscription_id][resource_group] = []
        
        subscriptions[subscription_id][resource_group].append(vnet_info)
    
    tree = Tree("🌐 [bold blue]Azure Virtual Networks[/bold blue]")
    
    for subscription_id, resource_groups in subscriptions.items():
        sub_tree = tree.add(f"📋 Subscription: {subscription_id}")
        
        for rg_name, vnets in resource_groups.items():
            rg_tree = sub_tree.add(f"📁 Resource Group: [magenta]{rg_name}[/magenta]")
            
            for vnet_info in vnets:
                vnet = vnet_info['vnet']
                vnet_tree = rg_tree.add(f"🌐 [cyan]{vnet['name']}[/cyan]")
                
                # 기본 정보
                vnet_tree.add(f"📍 Location: [green]{vnet['location']}[/green]")
                vnet_tree.add(f"📊 State: {format_provisioning_state_simple(vnet['provisioning_state'])}")
                
                # 주소 공간
                if vnet['address_space']:
                    addr_tree = vnet_tree.add("🏠 Address Space")
                    for addr in vnet['address_space']:
                        addr_tree.add(f"📍 {addr}")
                
                # 서브넷
                if vnet['subnets']:
                    subnet_tree = vnet_tree.add(f"📋 Subnets ({len(vnet['subnets'])})")
                    for subnet in vnet['subnets']:
                        subnet_node = subnet_tree.add(f"🔗 {subnet['name']} ({subnet['address_prefix']})")
                        subnet_node.add(f"🔌 Connected Resources: {subnet['connected_resources']}")
                        if subnet.get('network_security_group'):
                            nsg_name = subnet['network_security_group'].split('/')[-1]
                            subnet_node.add(f"🛡️ NSG: {nsg_name}")
                
                # 피어링
                if vnet['peerings']:
                    peering_tree = vnet_tree.add(f"🔗 Peerings ({len(vnet['peerings'])})")
                    for peering in vnet['peerings']:
                        peering_node = peering_tree.add(f"↔️ {peering['name']}")
                        peering_node.add(f"📊 State: {format_peering_state_simple(peering['peering_state'])}")
    
    console.print(tree)

def format_table_output(vnet_info_list):
    """테이블 형식으로 출력합니다."""
    if not vnet_info_list:
        console.print("[yellow]표시할 Azure VNet이 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for vnet_info in vnet_info_list:
        subscription_id = vnet_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = []
        subscriptions[subscription_id].append(vnet_info)
    
    for subscription_id, subscription_vnets in subscriptions.items():
        console.print(f"\n[bold blue]🔹 Subscription: {subscription_id}[/bold blue]")
        
        # VNet 요약 테이블
        console.print(f"\n[bold]🌐 Virtual Networks ({len(subscription_vnets)} VNets)[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("VNet Name", style="cyan")
        summary_table.add_column("Resource Group", style="magenta")
        summary_table.add_column("Location", style="green")
        summary_table.add_column("Address Space", style="yellow")
        summary_table.add_column("Subnets", justify="center")
        summary_table.add_column("Peerings", justify="center")
        summary_table.add_column("State", justify="center")
        summary_table.add_column("DDoS Protection", justify="center")
        
        for vnet_info in subscription_vnets:
            vnet = vnet_info['vnet']
            
            # 주소 공간 요약
            address_spaces = vnet.get('address_space', [])
            address_summary = ', '.join(address_spaces[:2])  # 처음 2개만 표시
            if len(address_spaces) > 2:
                address_summary += f" (+{len(address_spaces)-2} more)"
            
            summary_table.add_row(
                vnet.get('name', '-'),
                vnet_info.get('resource_group', '-'),
                vnet.get('location', '-'),
                address_summary or '-',
                str(vnet.get('subnet_count', 0)),
                str(vnet.get('peering_count', 0)),
                format_provisioning_state(vnet.get('provisioning_state', 'Unknown')),
                '✅' if vnet.get('enable_ddos_protection', False) else '❌'
            )
        
        console.print(summary_table)
        
        # 서브넷 상세 정보
        for vnet_info in subscription_vnets:
            vnet = vnet_info['vnet']
            if vnet.get('subnets'):
                console.print(f"\n[bold]📋 Subnets for {vnet['name']}[/bold]")
                subnet_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
                subnet_table.add_column("Subnet Name", style="cyan")
                subnet_table.add_column("Address Prefix", style="yellow")
                subnet_table.add_column("Connected Resources", justify="center")
                subnet_table.add_column("NSG", style="red")
                subnet_table.add_column("Route Table", style="blue")
                subnet_table.add_column("State", justify="center")
                
                for subnet in vnet['subnets']:
                    # NSG 이름 추출
                    nsg_name = '-'
                    if subnet.get('network_security_group'):
                        nsg_parts = subnet['network_security_group'].split('/')
                        if len(nsg_parts) >= 9:
                            nsg_name = nsg_parts[8]
                    
                    # 라우트 테이블 이름 추출
                    rt_name = '-'
                    if subnet.get('route_table'):
                        rt_parts = subnet['route_table'].split('/')
                        if len(rt_parts) >= 9:
                            rt_name = rt_parts[8]
                    
                    subnet_table.add_row(
                        subnet.get('name', '-'),
                        subnet.get('address_prefix', '-'),
                        str(subnet.get('connected_resources', 0)),
                        nsg_name,
                        rt_name,
                        format_provisioning_state(subnet.get('provisioning_state', 'Unknown'))
                    )
                
                console.print(subnet_table)
        
        # 위치별 통계
        location_stats = {}
        for vnet_info in subscription_vnets:
            location = vnet_info['vnet'].get('location', 'Unknown')
            if location not in location_stats:
                location_stats[location] = {'total': 0, 'subnets': 0, 'peerings': 0}
            location_stats[location]['total'] += 1
            location_stats[location]['subnets'] += vnet_info['vnet'].get('subnet_count', 0)
            location_stats[location]['peerings'] += vnet_info['vnet'].get('peering_count', 0)
        
        if len(location_stats) > 1:
            console.print(f"\n[bold]📊 Location Statistics[/bold]")
            stats_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            stats_table.add_column("Location", style="green")
            stats_table.add_column("VNets", justify="center")
            stats_table.add_column("Total Subnets", justify="center")
            stats_table.add_column("Total Peerings", justify="center")
            
            for location, stats in sorted(location_stats.items()):
                stats_table.add_row(
                    location,
                    str(stats['total']),
                    str(stats['subnets']),
                    str(stats['peerings'])
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

def format_peering_state_simple(state):
    """피어링 상태 간단 포맷"""
    state_lower = state.lower()
    if 'connected' in state_lower:
        return f"[green]{state}[/green]"
    elif 'disconnected' in state_lower:
        return f"[red]{state}[/red]"
    else:
        return state

def main(args):
    """메인 함수"""
    subscriptions = args.subscription.split(",") if args.subscription else get_azure_subscriptions()
    
    if not subscriptions:
        log_error("Azure 구독을 찾을 수 없습니다. AZURE_SUBSCRIPTIONS 환경변수를 설정하거나 Azure CLI로 로그인하세요.")
        return
    
    all_vnet_info = parallel_azure_operation(
        fetch_vnet_info,
        subscriptions,
        args.location,
        args.resource_group,
        args.name
    )
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_vnet_info, args.output)
        print(output)
    elif args.output == 'tree':
        format_tree_output(all_vnet_info)
    else:
        format_table_output(all_vnet_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-s', '--subscription', help='특정 Azure 구독 ID 목록(,) (없으면 모든 구독 사용)')
    parser.add_argument('-l', '--location', help='위치 필터 (부분 일치)')
    parser.add_argument('-g', '--resource-group', help='리소스 그룹 필터 (부분 일치)')
    parser.add_argument('-n', '--name', help='VNet 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml', 'tree'], default='table',
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure VNet 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)