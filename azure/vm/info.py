#!/usr/bin/env python3
import os
import sys
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree

from common.log import log_info, log_error
from common.azure_utils import (
    get_azure_subscriptions,
    get_azure_locations,
    create_azure_client,
    get_resource_groups,
    format_azure_output,
    get_azure_resource_tags,
    parallel_azure_operation
)

load_dotenv()
console = Console()

def fetch_vm_info(subscription_id, location_filter=None, resource_group_filter=None, vm_name_filter=None):
    """Azure VM 정보를 수집합니다."""
    log_info(f"Azure VM 정보 수집 시작: Subscription={subscription_id}")
    
    compute_client = create_azure_client(ComputeManagementClient, subscription_id)
    network_client = create_azure_client(NetworkManagementClient, subscription_id)
    
    if not compute_client or not network_client:
        return []
    
    try:
        vm_info_list = []
        
        # 리소스 그룹별로 VM 조회
        resource_groups = get_resource_groups(subscription_id)
        
        for rg in resource_groups:
            rg_name = rg['name']
            
            # 리소스 그룹 필터 적용
            if resource_group_filter and resource_group_filter.lower() not in rg_name.lower():
                continue
            
            try:
                # VM 목록 조회
                vms = compute_client.virtual_machines.list(resource_group_name=rg_name)
                
                for vm in vms:
                    # VM 이름 필터 적용
                    if vm_name_filter and vm_name_filter.lower() not in vm.name.lower():
                        continue
                    
                    # 위치 필터 적용
                    if location_filter and location_filter.lower() not in vm.location.lower():
                        continue
                    
                    # VM 상세 정보 수집
                    vm_detail = collect_vm_details(compute_client, network_client, rg_name, vm, subscription_id)
                    if vm_detail:
                        vm_info_list.append(vm_detail)
                        
            except Exception as e:
                log_error(f"리소스 그룹 {rg_name}의 VM 조회 실패: {e}")
                continue
        
        return vm_info_list
        
    except Exception as e:
        log_error(f"Azure VM 목록 조회 실패: Subscription={subscription_id}, Error={e}")
        return []

def collect_vm_details(compute_client, network_client, resource_group_name, vm, subscription_id):
    """VM의 상세 정보를 수집합니다."""
    try:
        # VM 인스턴스 뷰 (상태 정보)
        instance_view = compute_client.virtual_machines.instance_view(
            resource_group_name=resource_group_name,
            vm_name=vm.name
        )
        
        # VM 상태 추출
        power_state = 'unknown'
        provisioning_state = 'unknown'
        
        if instance_view.statuses:
            for status in instance_view.statuses:
                if status.code.startswith('PowerState/'):
                    power_state = status.code.replace('PowerState/', '')
                elif status.code.startswith('ProvisioningState/'):
                    provisioning_state = status.code.replace('ProvisioningState/', '')
        
        # 네트워크 인터페이스 정보
        network_info = []
        if vm.network_profile and vm.network_profile.network_interfaces:
            for nic_ref in vm.network_profile.network_interfaces:
                nic_info = get_network_interface_info(network_client, nic_ref.id)
                if nic_info:
                    network_info.append(nic_info)
        
        # 디스크 정보
        disk_info = []
        if vm.storage_profile:
            # OS 디스크
            if vm.storage_profile.os_disk:
                os_disk = vm.storage_profile.os_disk
                disk_info.append({
                    'name': os_disk.name,
                    'type': 'OS',
                    'size_gb': os_disk.disk_size_gb,
                    'storage_type': str(os_disk.managed_disk.storage_account_type) if os_disk.managed_disk else 'Unknown',
                    'caching': str(os_disk.caching) if os_disk.caching else 'None'
                })
            
            # 데이터 디스크
            if vm.storage_profile.data_disks:
                for data_disk in vm.storage_profile.data_disks:
                    disk_info.append({
                        'name': data_disk.name,
                        'type': 'Data',
                        'size_gb': data_disk.disk_size_gb,
                        'lun': data_disk.lun,
                        'storage_type': str(data_disk.managed_disk.storage_account_type) if data_disk.managed_disk else 'Unknown',
                        'caching': str(data_disk.caching) if data_disk.caching else 'None'
                    })
        
        # VM 정보 구성
        vm_data = {
            'subscription_id': subscription_id,
            'resource_group': resource_group_name,
            'vm': {
                'name': vm.name,
                'id': vm.id,
                'location': vm.location,
                'vm_size': vm.hardware_profile.vm_size if vm.hardware_profile else 'Unknown',
                'power_state': power_state,
                'provisioning_state': provisioning_state,
                'os_type': str(vm.storage_profile.os_disk.os_type) if vm.storage_profile and vm.storage_profile.os_disk else 'Unknown',
                'computer_name': vm.os_profile.computer_name if vm.os_profile else vm.name,
                'admin_username': vm.os_profile.admin_username if vm.os_profile else 'Unknown',
                'created_time': vm.time_created.isoformat() if vm.time_created else None,
                'tags': get_azure_resource_tags(vm),
                'availability_zone': vm.zones[0] if vm.zones else None,
                'network_interfaces': network_info,
                'disks': disk_info
            }
        }
        
        # 이미지 정보
        if vm.storage_profile and vm.storage_profile.image_reference:
            image_ref = vm.storage_profile.image_reference
            vm_data['vm']['image'] = {
                'publisher': image_ref.publisher,
                'offer': image_ref.offer,
                'sku': image_ref.sku,
                'version': image_ref.version
            }
        
        return vm_data
        
    except Exception as e:
        log_error(f"VM 상세 정보 수집 실패: {vm.name}, Error={e}")
        return None

def get_network_interface_info(network_client, nic_id):
    """네트워크 인터페이스 정보를 가져옵니다."""
    try:
        # NIC ID에서 리소스 그룹과 NIC 이름 추출
        parts = nic_id.split('/')
        if len(parts) < 9:
            return None
        
        resource_group_name = parts[4]
        nic_name = parts[8]
        
        nic = network_client.network_interfaces.get(
            resource_group_name=resource_group_name,
            network_interface_name=nic_name
        )
        
        # IP 구성 정보
        ip_configurations = []
        if nic.ip_configurations:
            for ip_config in nic.ip_configurations:
                config_info = {
                    'name': ip_config.name,
                    'private_ip': ip_config.private_ip_address,
                    'private_ip_allocation': str(ip_config.private_ip_allocation_method),
                    'primary': ip_config.primary
                }
                
                # 공용 IP 정보
                if ip_config.public_ip_address:
                    public_ip_info = get_public_ip_info(network_client, ip_config.public_ip_address.id)
                    config_info['public_ip'] = public_ip_info
                
                # 서브넷 정보
                if ip_config.subnet:
                    config_info['subnet_id'] = ip_config.subnet.id
                
                ip_configurations.append(config_info)
        
        return {
            'name': nic.name,
            'id': nic.id,
            'location': nic.location,
            'mac_address': nic.mac_address,
            'primary': nic.primary,
            'enable_accelerated_networking': nic.enable_accelerated_networking,
            'ip_configurations': ip_configurations,
            'network_security_group': nic.network_security_group.id if nic.network_security_group else None
        }
        
    except Exception as e:
        log_error(f"네트워크 인터페이스 정보 조회 실패: {nic_id}, Error={e}")
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

def format_output(vm_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return format_azure_output(vm_info_list, 'json')
    elif output_format == 'yaml':
        return format_azure_output(vm_info_list, 'yaml')
    elif output_format == 'tree':
        return format_tree_output(vm_info_list)
    else:
        return format_table_output(vm_info_list)

def format_tree_output(vm_info_list):
    """트리 형식으로 출력합니다."""
    if not vm_info_list:
        console.print("[yellow]표시할 Azure VM이 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for vm_info in vm_info_list:
        subscription_id = vm_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = {}
        
        resource_group = vm_info['resource_group']
        if resource_group not in subscriptions[subscription_id]:
            subscriptions[subscription_id][resource_group] = []
        
        subscriptions[subscription_id][resource_group].append(vm_info)
    
    tree = Tree("🔹 [bold blue]Azure Virtual Machines[/bold blue]")
    
    for subscription_id, resource_groups in subscriptions.items():
        sub_tree = tree.add(f"📋 Subscription: {subscription_id}")
        
        for rg_name, vms in resource_groups.items():
            rg_tree = sub_tree.add(f"📁 Resource Group: [magenta]{rg_name}[/magenta]")
            
            for vm_info in vms:
                vm = vm_info['vm']
                vm_tree = rg_tree.add(f"💻 [cyan]{vm['name']}[/cyan] ({vm['vm_size']})")
                
                # 기본 정보
                vm_tree.add(f"📍 Location: [green]{vm['location']}[/green]")
                vm_tree.add(f"⚡ Power State: {format_power_state_simple(vm['power_state'])}")
                vm_tree.add(f"🖥️ OS Type: {vm['os_type']}")
                
                # 네트워크 정보
                if vm['network_interfaces']:
                    net_tree = vm_tree.add("🌐 Network Interfaces")
                    for nic in vm['network_interfaces']:
                        nic_tree = net_tree.add(f"🔌 {nic['name']}")
                        for ip_config in nic['ip_configurations']:
                            if ip_config['private_ip']:
                                nic_tree.add(f"🔒 Private IP: {ip_config['private_ip']}")
                            if ip_config.get('public_ip', {}).get('ip_address'):
                                nic_tree.add(f"🌍 Public IP: {ip_config['public_ip']['ip_address']}")
                
                # 디스크 정보
                if vm['disks']:
                    disk_tree = vm_tree.add("💾 Disks")
                    for disk in vm['disks']:
                        disk_tree.add(f"📀 {disk['name']} ({disk['type']}, {disk['size_gb']}GB, {disk['storage_type']})")
    
    console.print(tree)

def format_table_output(vm_info_list):
    """테이블 형식으로 출력합니다."""
    if not vm_info_list:
        console.print("[yellow]표시할 Azure VM이 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for vm_info in vm_info_list:
        subscription_id = vm_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = []
        subscriptions[subscription_id].append(vm_info)
    
    for subscription_id, subscription_vms in subscriptions.items():
        console.print(f"\n[bold blue]🔹 Subscription: {subscription_id}[/bold blue]")
        
        # VM 요약 테이블
        console.print(f"\n[bold]💻 Virtual Machines ({len(subscription_vms)} VMs)[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("VM Name", style="cyan")
        summary_table.add_column("Resource Group", style="magenta")
        summary_table.add_column("Location", style="green")
        summary_table.add_column("Size", style="yellow")
        summary_table.add_column("Power State", justify="center")
        summary_table.add_column("OS Type", justify="center")
        summary_table.add_column("Private IP", style="blue")
        summary_table.add_column("Public IP", style="red")
        
        for vm_info in subscription_vms:
            vm = vm_info['vm']
            
            # 네트워크 정보 추출
            private_ips = []
            public_ips = []
            
            for nic in vm.get('network_interfaces', []):
                for ip_config in nic.get('ip_configurations', []):
                    if ip_config.get('private_ip'):
                        private_ips.append(ip_config['private_ip'])
                    if ip_config.get('public_ip', {}).get('ip_address'):
                        public_ips.append(ip_config['public_ip']['ip_address'])
            
            summary_table.add_row(
                vm.get('name', '-'),
                vm_info.get('resource_group', '-'),
                vm.get('location', '-'),
                vm.get('vm_size', '-'),
                format_power_state(vm.get('power_state', 'unknown')),
                vm.get('os_type', '-'),
                ', '.join(private_ips) if private_ips else '-',
                ', '.join(public_ips) if public_ips else '-'
            )
        
        console.print(summary_table)
        
        # 위치별 통계
        location_stats = {}
        for vm_info in subscription_vms:
            location = vm_info['vm'].get('location', 'Unknown')
            if location not in location_stats:
                location_stats[location] = {'total': 0, 'running': 0, 'stopped': 0}
            location_stats[location]['total'] += 1
            
            power_state = vm_info['vm'].get('power_state', '').lower()
            if 'running' in power_state:
                location_stats[location]['running'] += 1
            elif 'stopped' in power_state or 'deallocated' in power_state:
                location_stats[location]['stopped'] += 1
        
        if len(location_stats) > 1:
            console.print(f"\n[bold]📊 Location Statistics[/bold]")
            stats_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            stats_table.add_column("Location", style="green")
            stats_table.add_column("Total", justify="center")
            stats_table.add_column("Running", justify="center", style="green")
            stats_table.add_column("Stopped", justify="center", style="red")
            
            for location, stats in sorted(location_stats.items()):
                stats_table.add_row(
                    location,
                    str(stats['total']),
                    str(stats['running']),
                    str(stats['stopped'])
                )
            
            console.print(stats_table)

def format_power_state(power_state):
    """VM 전원 상태에 따라 색상을 적용합니다."""
    state_lower = power_state.lower()
    if 'running' in state_lower:
        return f"[bold green]{power_state}[/bold green]"
    elif 'stopped' in state_lower or 'deallocated' in state_lower:
        return f"[bold red]{power_state}[/bold red]"
    elif 'starting' in state_lower:
        return f"[bold yellow]{power_state}[/bold yellow]"
    else:
        return power_state

def format_power_state_simple(power_state):
    """트리용 간단한 전원 상태 포맷"""
    state_lower = power_state.lower()
    if 'running' in state_lower:
        return f"[green]{power_state}[/green]"
    elif 'stopped' in state_lower or 'deallocated' in state_lower:
        return f"[red]{power_state}[/red]"
    else:
        return power_state

def main(args):
    """메인 함수"""
    subscriptions = args.subscription.split(",") if args.subscription else get_azure_subscriptions()
    
    if not subscriptions:
        log_error("Azure 구독을 찾을 수 없습니다. AZURE_SUBSCRIPTIONS 환경변수를 설정하거나 Azure CLI로 로그인하세요.")
        return
    
    all_vm_info = parallel_azure_operation(
        fetch_vm_info,
        subscriptions,
        args.location,
        args.resource_group,
        args.name
    )
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_vm_info, args.output)
        print(output)
    elif args.output == 'tree':
        format_tree_output(all_vm_info)
    else:
        format_table_output(all_vm_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-s', '--subscription', help='특정 Azure 구독 ID 목록(,) (없으면 모든 구독 사용)')
    parser.add_argument('-l', '--location', help='위치 필터 (부분 일치)')
    parser.add_argument('-g', '--resource-group', help='리소스 그룹 필터 (부분 일치)')
    parser.add_argument('-n', '--name', help='VM 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml', 'tree'], default='table',
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure VM 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)