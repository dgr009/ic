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

def fetch_nsg_info(subscription_id, location_filter=None, resource_group_filter=None, nsg_name_filter=None):
    """Azure Network Security Group 정보를 수집합니다."""
    log_info(f"Azure NSG 정보 수집 시작: Subscription={subscription_id}")
    
    network_client = create_azure_client(NetworkManagementClient, subscription_id)
    if not network_client:
        return []
    
    try:
        nsg_info_list = []
        
        # 리소스 그룹별로 NSG 조회
        resource_groups = get_resource_groups(subscription_id)
        
        for rg in resource_groups:
            rg_name = rg['name']
            
            # 리소스 그룹 필터 적용
            if resource_group_filter and resource_group_filter.lower() not in rg_name.lower():
                continue
            
            try:
                # NSG 목록 조회
                nsgs = network_client.network_security_groups.list(resource_group_name=rg_name)
                
                for nsg in nsgs:
                    # NSG 이름 필터 적용
                    if nsg_name_filter and nsg_name_filter.lower() not in nsg.name.lower():
                        continue
                    
                    # 위치 필터 적용
                    if location_filter and location_filter.lower() not in nsg.location.lower():
                        continue
                    
                    # NSG 상세 정보 수집
                    nsg_detail = collect_nsg_details(network_client, rg_name, nsg, subscription_id)
                    if nsg_detail:
                        nsg_info_list.append(nsg_detail)
                        
            except Exception as e:
                log_error(f"리소스 그룹 {rg_name}의 NSG 조회 실패: {e}")
                continue
        
        return nsg_info_list
        
    except Exception as e:
        log_error(f"Azure NSG 목록 조회 실패: Subscription={subscription_id}, Error={e}")
        return []

def collect_nsg_details(network_client, resource_group_name, nsg, subscription_id):
    """NSG의 상세 정보를 수집합니다."""
    try:
        # 보안 규칙 정보 수집
        security_rules = []
        if nsg.security_rules:
            for rule in nsg.security_rules:
                rule_detail = {
                    'name': rule.name,
                    'priority': rule.priority,
                    'direction': str(rule.direction),
                    'access': str(rule.access),
                    'protocol': str(rule.protocol),
                    'source_port_range': rule.source_port_range,
                    'destination_port_range': rule.destination_port_range,
                    'source_address_prefix': rule.source_address_prefix,
                    'destination_address_prefix': rule.destination_address_prefix,
                    'source_port_ranges': list(rule.source_port_ranges) if rule.source_port_ranges else [],
                    'destination_port_ranges': list(rule.destination_port_ranges) if rule.destination_port_ranges else [],
                    'source_address_prefixes': list(rule.source_address_prefixes) if rule.source_address_prefixes else [],
                    'destination_address_prefixes': list(rule.destination_address_prefixes) if rule.destination_address_prefixes else [],
                    'provisioning_state': str(rule.provisioning_state)
                }
                
                # 서비스 태그 정보
                if hasattr(rule, 'source_application_security_groups') and rule.source_application_security_groups:
                    rule_detail['source_application_security_groups'] = [asg.id for asg in rule.source_application_security_groups]
                
                if hasattr(rule, 'destination_application_security_groups') and rule.destination_application_security_groups:
                    rule_detail['destination_application_security_groups'] = [asg.id for asg in rule.destination_application_security_groups]
                
                security_rules.append(rule_detail)
        
        # 기본 보안 규칙 정보
        default_security_rules = []
        if nsg.default_security_rules:
            for rule in nsg.default_security_rules:
                default_rule_detail = {
                    'name': rule.name,
                    'priority': rule.priority,
                    'direction': str(rule.direction),
                    'access': str(rule.access),
                    'protocol': str(rule.protocol),
                    'source_port_range': rule.source_port_range,
                    'destination_port_range': rule.destination_port_range,
                    'source_address_prefix': rule.source_address_prefix,
                    'destination_address_prefix': rule.destination_address_prefix
                }
                default_security_rules.append(default_rule_detail)
        
        # 연결된 네트워크 인터페이스
        network_interfaces = []
        if nsg.network_interfaces:
            for nic in nsg.network_interfaces:
                network_interfaces.append({
                    'id': nic.id,
                    'name': nic.id.split('/')[-1] if nic.id else 'Unknown'
                })
        
        # 연결된 서브넷
        subnets = []
        if nsg.subnets:
            for subnet in nsg.subnets:
                subnets.append({
                    'id': subnet.id,
                    'name': subnet.id.split('/')[-1] if subnet.id else 'Unknown',
                    'vnet_name': subnet.id.split('/')[-3] if subnet.id and len(subnet.id.split('/')) >= 3 else 'Unknown'
                })
        
        # NSG 정보 구성
        nsg_data = {
            'subscription_id': subscription_id,
            'resource_group': resource_group_name,
            'nsg': {
                'name': nsg.name,
                'id': nsg.id,
                'location': nsg.location,
                'provisioning_state': str(nsg.provisioning_state),
                'tags': get_azure_resource_tags(nsg),
                'security_rules': security_rules,
                'default_security_rules': default_security_rules,
                'network_interfaces': network_interfaces,
                'subnets': subnets,
                'security_rules_count': len(security_rules),
                'default_rules_count': len(default_security_rules),
                'attached_nics_count': len(network_interfaces),
                'attached_subnets_count': len(subnets)
            }
        }
        
        return nsg_data
        
    except Exception as e:
        log_error(f"NSG 상세 정보 수집 실패: {nsg.name}, Error={e}")
        return None

def format_output(nsg_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return format_azure_output(nsg_info_list, 'json')
    elif output_format == 'yaml':
        return format_azure_output(nsg_info_list, 'yaml')
    elif output_format == 'tree':
        return format_tree_output(nsg_info_list)
    else:
        return format_table_output(nsg_info_list)

def format_tree_output(nsg_info_list):
    """트리 형식으로 출력합니다."""
    if not nsg_info_list:
        console.print("[yellow]표시할 Azure NSG가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for nsg_info in nsg_info_list:
        subscription_id = nsg_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = {}
        
        resource_group = nsg_info['resource_group']
        if resource_group not in subscriptions[subscription_id]:
            subscriptions[subscription_id][resource_group] = []
        
        subscriptions[subscription_id][resource_group].append(nsg_info)
    
    tree = Tree("🛡️ [bold blue]Azure Network Security Groups[/bold blue]")
    
    for subscription_id, resource_groups in subscriptions.items():
        sub_tree = tree.add(f"📋 Subscription: {subscription_id}")
        
        for rg_name, nsgs in resource_groups.items():
            rg_tree = sub_tree.add(f"📁 Resource Group: [magenta]{rg_name}[/magenta]")
            
            for nsg_info in nsgs:
                nsg = nsg_info['nsg']
                nsg_tree = rg_tree.add(f"🛡️ [cyan]{nsg['name']}[/cyan]")
                
                # 기본 정보
                nsg_tree.add(f"📍 Location: [green]{nsg['location']}[/green]")
                nsg_tree.add(f"📊 State: {format_provisioning_state_simple(nsg['provisioning_state'])}")
                
                # 보안 규칙
                if nsg['security_rules']:
                    rules_tree = nsg_tree.add(f"📋 Security Rules ({len(nsg['security_rules'])})")
                    for rule in nsg['security_rules'][:5]:  # 처음 5개만 표시
                        rule_color = "green" if rule['access'] == 'Allow' else "red"
                        direction_icon = "⬇️" if rule['direction'] == 'Inbound' else "⬆️"
                        rules_tree.add(f"{direction_icon} [{rule_color}]{rule['name']}[/{rule_color}] ({rule['protocol']}, {rule['access']})")
                    if len(nsg['security_rules']) > 5:
                        rules_tree.add(f"... and {len(nsg['security_rules']) - 5} more rules")
                
                # 연결된 리소스
                if nsg['subnets']:
                    subnet_tree = nsg_tree.add(f"🔗 Attached Subnets ({len(nsg['subnets'])})")
                    for subnet in nsg['subnets'][:3]:  # 처음 3개만 표시
                        subnet_tree.add(f"🌐 {subnet['name']} (VNet: {subnet['vnet_name']})")
                    if len(nsg['subnets']) > 3:
                        subnet_tree.add(f"... and {len(nsg['subnets']) - 3} more subnets")
                
                if nsg['network_interfaces']:
                    nic_tree = nsg_tree.add(f"🔌 Attached NICs ({len(nsg['network_interfaces'])})")
                    for nic in nsg['network_interfaces'][:3]:  # 처음 3개만 표시
                        nic_tree.add(f"🔌 {nic['name']}")
                    if len(nsg['network_interfaces']) > 3:
                        nic_tree.add(f"... and {len(nsg['network_interfaces']) - 3} more NICs")
    
    console.print(tree)

def format_table_output(nsg_info_list):
    """테이블 형식으로 출력합니다."""
    if not nsg_info_list:
        console.print("[yellow]표시할 Azure NSG가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for nsg_info in nsg_info_list:
        subscription_id = nsg_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = []
        subscriptions[subscription_id].append(nsg_info)
    
    for subscription_id, subscription_nsgs in subscriptions.items():
        console.print(f"\n[bold blue]🔹 Subscription: {subscription_id}[/bold blue]")
        
        # NSG 요약 테이블
        console.print(f"\n[bold]🛡️ Network Security Groups ({len(subscription_nsgs)} NSGs)[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("NSG Name", style="cyan")
        summary_table.add_column("Resource Group", style="magenta")
        summary_table.add_column("Location", style="green")
        summary_table.add_column("Security Rules", justify="center")
        summary_table.add_column("Attached Subnets", justify="center")
        summary_table.add_column("Attached NICs", justify="center")
        summary_table.add_column("State", justify="center")
        
        for nsg_info in subscription_nsgs:
            nsg = nsg_info['nsg']
            
            summary_table.add_row(
                nsg.get('name', '-'),
                nsg_info.get('resource_group', '-'),
                nsg.get('location', '-'),
                str(nsg.get('security_rules_count', 0)),
                str(nsg.get('attached_subnets_count', 0)),
                str(nsg.get('attached_nics_count', 0)),
                format_provisioning_state(nsg.get('provisioning_state', 'Unknown'))
            )
        
        console.print(summary_table)
        
        # 보안 규칙 상세 정보
        for nsg_info in subscription_nsgs:
            nsg = nsg_info['nsg']
            if nsg.get('security_rules'):
                console.print(f"\n[bold]📋 Security Rules for {nsg['name']}[/bold]")
                rules_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
                rules_table.add_column("Rule Name", style="cyan")
                rules_table.add_column("Priority", justify="center")
                rules_table.add_column("Direction", justify="center")
                rules_table.add_column("Access", justify="center")
                rules_table.add_column("Protocol", style="yellow")
                rules_table.add_column("Source", style="blue")
                rules_table.add_column("Destination", style="green")
                rules_table.add_column("Port Range", style="magenta")
                
                for rule in nsg['security_rules'][:10]:  # 처음 10개만 표시
                    # 소스 정보 요약
                    source = rule.get('source_address_prefix', '')
                    if rule.get('source_address_prefixes'):
                        source = f"{rule['source_address_prefixes'][0]} (+{len(rule['source_address_prefixes'])-1})" if len(rule['source_address_prefixes']) > 1 else rule['source_address_prefixes'][0]
                    
                    # 대상 정보 요약
                    destination = rule.get('destination_address_prefix', '')
                    if rule.get('destination_address_prefixes'):
                        destination = f"{rule['destination_address_prefixes'][0]} (+{len(rule['destination_address_prefixes'])-1})" if len(rule['destination_address_prefixes']) > 1 else rule['destination_address_prefixes'][0]
                    
                    # 포트 범위 정보
                    port_range = rule.get('destination_port_range', '')
                    if rule.get('destination_port_ranges'):
                        port_range = f"{rule['destination_port_ranges'][0]} (+{len(rule['destination_port_ranges'])-1})" if len(rule['destination_port_ranges']) > 1 else rule['destination_port_ranges'][0]
                    
                    rules_table.add_row(
                        rule.get('name', '-'),
                        str(rule.get('priority', '-')),
                        format_direction(rule.get('direction', 'Unknown')),
                        format_access(rule.get('access', 'Unknown')),
                        rule.get('protocol', '-'),
                        source or '*',
                        destination or '*',
                        port_range or '*'
                    )
                
                console.print(rules_table)
                
                if len(nsg['security_rules']) > 10:
                    console.print(f"[dim]... and {len(nsg['security_rules']) - 10} more rules[/dim]")
        
        # 위치별 통계
        location_stats = {}
        for nsg_info in subscription_nsgs:
            location = nsg_info['nsg'].get('location', 'Unknown')
            if location not in location_stats:
                location_stats[location] = {'nsgs': 0, 'total_rules': 0, 'attached_subnets': 0}
            location_stats[location]['nsgs'] += 1
            location_stats[location]['total_rules'] += nsg_info['nsg'].get('security_rules_count', 0)
            location_stats[location]['attached_subnets'] += nsg_info['nsg'].get('attached_subnets_count', 0)
        
        if len(location_stats) > 1:
            console.print(f"\n[bold]📊 Location Statistics[/bold]")
            stats_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            stats_table.add_column("Location", style="green")
            stats_table.add_column("NSGs", justify="center")
            stats_table.add_column("Total Rules", justify="center")
            stats_table.add_column("Attached Subnets", justify="center")
            
            for location, stats in sorted(location_stats.items()):
                stats_table.add_row(
                    location,
                    str(stats['nsgs']),
                    str(stats['total_rules']),
                    str(stats['attached_subnets'])
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

def format_direction(direction):
    """방향에 따라 아이콘을 추가합니다."""
    if direction == 'Inbound':
        return f"⬇️ {direction}"
    elif direction == 'Outbound':
        return f"⬆️ {direction}"
    else:
        return direction

def format_access(access):
    """접근 권한에 따라 색상을 적용합니다."""
    if access == 'Allow':
        return f"[bold green]{access}[/bold green]"
    elif access == 'Deny':
        return f"[bold red]{access}[/bold red]"
    else:
        return access

def main(args):
    """메인 함수"""
    subscriptions = args.subscription.split(",") if args.subscription else get_azure_subscriptions()
    
    if not subscriptions:
        log_error("Azure 구독을 찾을 수 없습니다. AZURE_SUBSCRIPTIONS 환경변수를 설정하거나 Azure CLI로 로그인하세요.")
        return
    
    all_nsg_info = parallel_azure_operation(
        fetch_nsg_info,
        subscriptions,
        args.location,
        args.resource_group,
        args.name
    )
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_nsg_info, args.output)
        print(output)
    elif args.output == 'tree':
        format_tree_output(all_nsg_info)
    else:
        format_table_output(all_nsg_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-s', '--subscription', help='특정 Azure 구독 ID 목록(,) (없으면 모든 구독 사용)')
    parser.add_argument('-l', '--location', help='위치 필터 (부분 일치)')
    parser.add_argument('-g', '--resource-group', help='리소스 그룹 필터 (부분 일치)')
    parser.add_argument('-n', '--name', help='NSG 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml', 'tree'], default='table',
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure NSG 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)