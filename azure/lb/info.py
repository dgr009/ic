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

def fetch_lb_info(subscription_id, location_filter=None, resource_group_filter=None, lb_name_filter=None):
    """Azure Load Balancer 정보를 수집합니다."""
    log_info(f"Azure Load Balancer 정보 수집 시작: Subscription={subscription_id}")
    
    network_client = create_azure_client(NetworkManagementClient, subscription_id)
    if not network_client:
        return []
    
    try:
        lb_info_list = []
        
        # 리소스 그룹별로 Load Balancer 조회
        resource_groups = get_resource_groups(subscription_id)
        
        for rg in resource_groups:
            rg_name = rg['name']
            
            # 리소스 그룹 필터 적용
            if resource_group_filter and resource_group_filter.lower() not in rg_name.lower():
                continue
            
            try:
                # Load Balancer 목록 조회
                load_balancers = network_client.load_balancers.list(resource_group_name=rg_name)
                
                for lb in load_balancers:
                    # Load Balancer 이름 필터 적용
                    if lb_name_filter and lb_name_filter.lower() not in lb.name.lower():
                        continue
                    
                    # 위치 필터 적용
                    if location_filter and location_filter.lower() not in lb.location.lower():
                        continue
                    
                    # Load Balancer 상세 정보 수집
                    lb_detail = collect_lb_details(network_client, rg_name, lb, subscription_id)
                    if lb_detail:
                        lb_info_list.append(lb_detail)
                        
            except Exception as e:
                log_error(f"리소스 그룹 {rg_name}의 Load Balancer 조회 실패: {e}")
                continue
        
        return lb_info_list
        
    except Exception as e:
        log_error(f"Azure Load Balancer 목록 조회 실패: Subscription={subscription_id}, Error={e}")
        return []

def collect_lb_details(network_client, resource_group_name, lb, subscription_id):
    """Load Balancer의 상세 정보를 수집합니다."""
    try:
        # Frontend IP 구성
        frontend_ip_configs = []
        if lb.frontend_ip_configurations:
            for frontend in lb.frontend_ip_configurations:
                frontend_detail = {
                    'name': frontend.name,
                    'id': frontend.id,
                    'private_ip_address': frontend.private_ip_address,
                    'private_ip_allocation_method': str(frontend.private_ip_allocation_method) if frontend.private_ip_allocation_method else None,
                    'provisioning_state': str(frontend.provisioning_state),
                    'zones': list(frontend.zones) if frontend.zones else []
                }
                
                # 공용 IP 정보
                if frontend.public_ip_address:
                    public_ip_info = get_public_ip_info(network_client, frontend.public_ip_address.id)
                    frontend_detail['public_ip'] = public_ip_info
                
                # 서브넷 정보
                if frontend.subnet:
                    frontend_detail['subnet_id'] = frontend.subnet.id
                
                frontend_ip_configs.append(frontend_detail)
        
        # Backend Address Pool
        backend_pools = []
        if lb.backend_address_pools:
            for pool in lb.backend_address_pools:
                pool_detail = {
                    'name': pool.name,
                    'id': pool.id,
                    'provisioning_state': str(pool.provisioning_state),
                    'backend_ip_configurations_count': len(pool.backend_ip_configurations) if pool.backend_ip_configurations else 0
                }
                
                # Backend IP 구성 정보
                if pool.backend_ip_configurations:
                    backend_ips = []
                    for backend_ip in pool.backend_ip_configurations[:5]:  # 처음 5개만
                        backend_ips.append({
                            'id': backend_ip.id,
                            'name': backend_ip.id.split('/')[-1] if backend_ip.id else 'Unknown'
                        })
                    pool_detail['backend_ip_configurations'] = backend_ips
                
                backend_pools.append(pool_detail)
        
        # Load Balancing Rules
        load_balancing_rules = []
        if lb.load_balancing_rules:
            for rule in lb.load_balancing_rules:
                rule_detail = {
                    'name': rule.name,
                    'id': rule.id,
                    'protocol': str(rule.protocol),
                    'frontend_port': rule.frontend_port,
                    'backend_port': rule.backend_port,
                    'idle_timeout_in_minutes': rule.idle_timeout_in_minutes,
                    'enable_floating_ip': rule.enable_floating_ip,
                    'enable_tcp_reset': rule.enable_tcp_reset if hasattr(rule, 'enable_tcp_reset') else False,
                    'disable_outbound_snat': rule.disable_outbound_snat if hasattr(rule, 'disable_outbound_snat') else False,
                    'provisioning_state': str(rule.provisioning_state)
                }
                
                # Frontend IP 구성 참조
                if rule.frontend_ip_configuration:
                    rule_detail['frontend_ip_configuration'] = rule.frontend_ip_configuration.id
                
                # Backend Address Pool 참조
                if rule.backend_address_pool:
                    rule_detail['backend_address_pool'] = rule.backend_address_pool.id
                
                # Health Probe 참조
                if rule.probe:
                    rule_detail['probe'] = rule.probe.id
                
                load_balancing_rules.append(rule_detail)
        
        # Health Probes
        probes = []
        if lb.probes:
            for probe in lb.probes:
                probe_detail = {
                    'name': probe.name,
                    'id': probe.id,
                    'protocol': str(probe.protocol),
                    'port': probe.port,
                    'interval_in_seconds': probe.interval_in_seconds,
                    'number_of_probes': probe.number_of_probes,
                    'request_path': probe.request_path if hasattr(probe, 'request_path') else None,
                    'provisioning_state': str(probe.provisioning_state)
                }
                probes.append(probe_detail)
        
        # Inbound NAT Rules
        inbound_nat_rules = []
        if lb.inbound_nat_rules:
            for nat_rule in lb.inbound_nat_rules:
                nat_rule_detail = {
                    'name': nat_rule.name,
                    'id': nat_rule.id,
                    'protocol': str(nat_rule.protocol),
                    'frontend_port': nat_rule.frontend_port,
                    'backend_port': nat_rule.backend_port,
                    'idle_timeout_in_minutes': nat_rule.idle_timeout_in_minutes,
                    'enable_floating_ip': nat_rule.enable_floating_ip,
                    'enable_tcp_reset': nat_rule.enable_tcp_reset if hasattr(nat_rule, 'enable_tcp_reset') else False,
                    'provisioning_state': str(nat_rule.provisioning_state)
                }
                
                # Frontend IP 구성 참조
                if nat_rule.frontend_ip_configuration:
                    nat_rule_detail['frontend_ip_configuration'] = nat_rule.frontend_ip_configuration.id
                
                # Backend IP 구성 참조
                if nat_rule.backend_ip_configuration:
                    nat_rule_detail['backend_ip_configuration'] = nat_rule.backend_ip_configuration.id
                
                inbound_nat_rules.append(nat_rule_detail)
        
        # Outbound Rules (Standard LB에서만 사용 가능)
        outbound_rules = []
        if hasattr(lb, 'outbound_rules') and lb.outbound_rules:
            for outbound_rule in lb.outbound_rules:
                outbound_rule_detail = {
                    'name': outbound_rule.name,
                    'id': outbound_rule.id,
                    'protocol': str(outbound_rule.protocol),
                    'idle_timeout_in_minutes': outbound_rule.idle_timeout_in_minutes,
                    'enable_tcp_reset': outbound_rule.enable_tcp_reset if hasattr(outbound_rule, 'enable_tcp_reset') else False,
                    'provisioning_state': str(outbound_rule.provisioning_state)
                }
                outbound_rules.append(outbound_rule_detail)
        
        # Load Balancer 정보 구성
        lb_data = {
            'subscription_id': subscription_id,
            'resource_group': resource_group_name,
            'load_balancer': {
                'name': lb.name,
                'id': lb.id,
                'location': lb.location,
                'sku_name': str(lb.sku.name) if lb.sku else 'Basic',
                'sku_tier': str(lb.sku.tier) if lb.sku and hasattr(lb.sku, 'tier') else 'Regional',
                'provisioning_state': str(lb.provisioning_state),
                'tags': get_azure_resource_tags(lb),
                'frontend_ip_configurations': frontend_ip_configs,
                'backend_address_pools': backend_pools,
                'load_balancing_rules': load_balancing_rules,
                'probes': probes,
                'inbound_nat_rules': inbound_nat_rules,
                'outbound_rules': outbound_rules,
                'frontend_ip_count': len(frontend_ip_configs),
                'backend_pool_count': len(backend_pools),
                'rule_count': len(load_balancing_rules),
                'probe_count': len(probes),
                'nat_rule_count': len(inbound_nat_rules)
            }
        }
        
        return lb_data
        
    except Exception as e:
        log_error(f"Load Balancer 상세 정보 수집 실패: {lb.name}, Error={e}")
        return None

def get_public_ip_info(network_client, public_ip_id):
    """공용 IP 정보를 가져옵니다."""
    try:
        parts = public_ip_id.split('/')
        if len(parts) < 9:
            return None
        
        resource_group_name = parts[4]
        public_ip_name = parts[8]
        
        public_ip = network_client.public_ip_addresses.get(
            resource_group_name=resource_group_name,
            public_ip_address_name=public_ip_name
        )
        
        return {
            'name': public_ip.name,
            'ip_address': public_ip.ip_address,
            'allocation_method': str(public_ip.public_ip_allocation_method),
            'sku': str(public_ip.sku.name) if public_ip.sku else 'Basic',
            'version': str(public_ip.public_ip_address_version)
        }
        
    except Exception as e:
        log_error(f"공용 IP 정보 조회 실패: {public_ip_id}, Error={e}")
        return None

def format_output(lb_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return format_azure_output(lb_info_list, 'json')
    elif output_format == 'yaml':
        return format_azure_output(lb_info_list, 'yaml')
    elif output_format == 'tree':
        return format_tree_output(lb_info_list)
    else:
        return format_table_output(lb_info_list)

def format_tree_output(lb_info_list):
    """트리 형식으로 출력합니다."""
    if not lb_info_list:
        console.print("[yellow]표시할 Azure Load Balancer가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for lb_info in lb_info_list:
        subscription_id = lb_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = {}
        
        resource_group = lb_info['resource_group']
        if resource_group not in subscriptions[subscription_id]:
            subscriptions[subscription_id][resource_group] = []
        
        subscriptions[subscription_id][resource_group].append(lb_info)
    
    tree = Tree("⚖️ [bold blue]Azure Load Balancers[/bold blue]")
    
    for subscription_id, resource_groups in subscriptions.items():
        sub_tree = tree.add(f"📋 Subscription: {subscription_id}")
        
        for rg_name, load_balancers in resource_groups.items():
            rg_tree = sub_tree.add(f"📁 Resource Group: [magenta]{rg_name}[/magenta]")
            
            for lb_info in load_balancers:
                lb = lb_info['load_balancer']
                lb_tree = rg_tree.add(f"⚖️ [cyan]{lb['name']}[/cyan] ({lb['sku_name']})")
                
                # 기본 정보
                lb_tree.add(f"📍 Location: [green]{lb['location']}[/green]")
                lb_tree.add(f"📊 State: {format_provisioning_state_simple(lb['provisioning_state'])}")
                
                # Frontend IP 구성
                if lb['frontend_ip_configurations']:
                    frontend_tree = lb_tree.add(f"🌐 Frontend IPs ({len(lb['frontend_ip_configurations'])})")
                    for frontend in lb['frontend_ip_configurations']:
                        if frontend.get('public_ip', {}).get('ip_address'):
                            frontend_tree.add(f"🌍 {frontend['name']}: {frontend['public_ip']['ip_address']} (Public)")
                        elif frontend.get('private_ip_address'):
                            frontend_tree.add(f"🔒 {frontend['name']}: {frontend['private_ip_address']} (Private)")
                        else:
                            frontend_tree.add(f"❓ {frontend['name']}: No IP assigned")
                
                # Backend Pools
                if lb['backend_address_pools']:
                    backend_tree = lb_tree.add(f"🎯 Backend Pools ({len(lb['backend_address_pools'])})")
                    for pool in lb['backend_address_pools']:
                        backend_tree.add(f"🎯 {pool['name']} ({pool['backend_ip_configurations_count']} targets)")
                
                # Load Balancing Rules
                if lb['load_balancing_rules']:
                    rules_tree = lb_tree.add(f"📋 LB Rules ({len(lb['load_balancing_rules'])})")
                    for rule in lb['load_balancing_rules'][:3]:  # 처음 3개만 표시
                        rules_tree.add(f"🔄 {rule['name']}: {rule['protocol']} {rule['frontend_port']}→{rule['backend_port']}")
                    if len(lb['load_balancing_rules']) > 3:
                        rules_tree.add(f"... and {len(lb['load_balancing_rules']) - 3} more rules")
                
                # Health Probes
                if lb['probes']:
                    probe_tree = lb_tree.add(f"🏥 Health Probes ({len(lb['probes'])})")
                    for probe in lb['probes']:
                        probe_tree.add(f"🏥 {probe['name']}: {probe['protocol']}:{probe['port']}")
    
    console.print(tree)

def format_table_output(lb_info_list):
    """테이블 형식으로 출력합니다."""
    if not lb_info_list:
        console.print("[yellow]표시할 Azure Load Balancer가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for lb_info in lb_info_list:
        subscription_id = lb_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = []
        subscriptions[subscription_id].append(lb_info)
    
    for subscription_id, subscription_lbs in subscriptions.items():
        console.print(f"\n[bold blue]🔹 Subscription: {subscription_id}[/bold blue]")
        
        # Load Balancer 요약 테이블
        console.print(f"\n[bold]⚖️ Load Balancers ({len(subscription_lbs)} LBs)[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("LB Name", style="cyan")
        summary_table.add_column("Resource Group", style="magenta")
        summary_table.add_column("Location", style="green")
        summary_table.add_column("SKU", style="yellow")
        summary_table.add_column("Frontend IPs", justify="center")
        summary_table.add_column("Backend Pools", justify="center")
        summary_table.add_column("Rules", justify="center")
        summary_table.add_column("Probes", justify="center")
        summary_table.add_column("State", justify="center")
        
        for lb_info in subscription_lbs:
            lb = lb_info['load_balancer']
            
            summary_table.add_row(
                lb.get('name', '-'),
                lb_info.get('resource_group', '-'),
                lb.get('location', '-'),
                lb.get('sku_name', '-'),
                str(lb.get('frontend_ip_count', 0)),
                str(lb.get('backend_pool_count', 0)),
                str(lb.get('rule_count', 0)),
                str(lb.get('probe_count', 0)),
                format_provisioning_state(lb.get('provisioning_state', 'Unknown'))
            )
        
        console.print(summary_table)
        
        # Frontend IP 상세 정보
        for lb_info in subscription_lbs:
            lb = lb_info['load_balancer']
            if lb.get('frontend_ip_configurations'):
                console.print(f"\n[bold]🌐 Frontend IP Configurations for {lb['name']}[/bold]")
                frontend_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
                frontend_table.add_column("Name", style="cyan")
                frontend_table.add_column("Type", style="yellow")
                frontend_table.add_column("IP Address", style="green")
                frontend_table.add_column("Allocation Method", style="blue")
                frontend_table.add_column("Zones", style="magenta")
                frontend_table.add_column("State", justify="center")
                
                for frontend in lb['frontend_ip_configurations']:
                    ip_type = "Public" if frontend.get('public_ip') else "Private"
                    ip_address = frontend.get('public_ip', {}).get('ip_address') or frontend.get('private_ip_address', '-')
                    allocation_method = frontend.get('public_ip', {}).get('allocation_method') or frontend.get('private_ip_allocation_method', '-')
                    zones = ', '.join(frontend.get('zones', [])) if frontend.get('zones') else '-'
                    
                    frontend_table.add_row(
                        frontend.get('name', '-'),
                        ip_type,
                        ip_address,
                        allocation_method,
                        zones,
                        format_provisioning_state(frontend.get('provisioning_state', 'Unknown'))
                    )
                
                console.print(frontend_table)
        
        # Load Balancing Rules 상세 정보
        for lb_info in subscription_lbs:
            lb = lb_info['load_balancer']
            if lb.get('load_balancing_rules'):
                console.print(f"\n[bold]📋 Load Balancing Rules for {lb['name']}[/bold]")
                rules_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
                rules_table.add_column("Rule Name", style="cyan")
                rules_table.add_column("Protocol", style="yellow")
                rules_table.add_column("Frontend Port", justify="center")
                rules_table.add_column("Backend Port", justify="center")
                rules_table.add_column("Idle Timeout", justify="center")
                rules_table.add_column("Floating IP", justify="center")
                rules_table.add_column("TCP Reset", justify="center")
                rules_table.add_column("State", justify="center")
                
                for rule in lb['load_balancing_rules']:
                    rules_table.add_row(
                        rule.get('name', '-'),
                        rule.get('protocol', '-'),
                        str(rule.get('frontend_port', '-')),
                        str(rule.get('backend_port', '-')),
                        f"{rule.get('idle_timeout_in_minutes', 0)}m",
                        '✅' if rule.get('enable_floating_ip', False) else '❌',
                        '✅' if rule.get('enable_tcp_reset', False) else '❌',
                        format_provisioning_state(rule.get('provisioning_state', 'Unknown'))
                    )
                
                console.print(rules_table)
        
        # 위치별 통계
        location_stats = {}
        for lb_info in subscription_lbs:
            location = lb_info['load_balancer'].get('location', 'Unknown')
            if location not in location_stats:
                location_stats[location] = {'lbs': 0, 'total_rules': 0, 'total_probes': 0}
            location_stats[location]['lbs'] += 1
            location_stats[location]['total_rules'] += lb_info['load_balancer'].get('rule_count', 0)
            location_stats[location]['total_probes'] += lb_info['load_balancer'].get('probe_count', 0)
        
        if len(location_stats) > 1:
            console.print(f"\n[bold]📊 Location Statistics[/bold]")
            stats_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            stats_table.add_column("Location", style="green")
            stats_table.add_column("Load Balancers", justify="center")
            stats_table.add_column("Total Rules", justify="center")
            stats_table.add_column("Total Probes", justify="center")
            
            for location, stats in sorted(location_stats.items()):
                stats_table.add_row(
                    location,
                    str(stats['lbs']),
                    str(stats['total_rules']),
                    str(stats['total_probes'])
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
    
    all_lb_info = parallel_azure_operation(
        fetch_lb_info,
        subscriptions,
        args.location,
        args.resource_group,
        args.name
    )
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_lb_info, args.output)
        print(output)
    elif args.output == 'tree':
        format_tree_output(all_lb_info)
    else:
        format_table_output(all_lb_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-s', '--subscription', help='특정 Azure 구독 ID 목록(,) (없으면 모든 구독 사용)')
    parser.add_argument('-l', '--location', help='위치 필터 (부분 일치)')
    parser.add_argument('-g', '--resource-group', help='리소스 그룹 필터 (부분 일치)')
    parser.add_argument('-n', '--name', help='Load Balancer 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml', 'tree'], default='table',
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure Load Balancer 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)