#!/usr/bin/env python3
import os
import sys
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from azure.mgmt.containerinstance import ContainerInstanceManagementClient
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

def fetch_aci_info(subscription_id, location_filter=None, resource_group_filter=None, container_group_name_filter=None):
    """Azure Container Instances 정보를 수집합니다."""
    log_info(f"Azure Container Instances 정보 수집 시작: Subscription={subscription_id}")
    
    aci_client = create_azure_client(ContainerInstanceManagementClient, subscription_id)
    if not aci_client:
        return []
    
    try:
        aci_info_list = []
        
        # 리소스 그룹별로 Container Group 조회
        resource_groups = get_resource_groups(subscription_id)
        
        for rg in resource_groups:
            rg_name = rg['name']
            
            # 리소스 그룹 필터 적용
            if resource_group_filter and resource_group_filter.lower() not in rg_name.lower():
                continue
            
            try:
                # Container Group 목록 조회
                container_groups = aci_client.container_groups.list_by_resource_group(resource_group_name=rg_name)
                
                for container_group in container_groups:
                    # Container Group 이름 필터 적용
                    if container_group_name_filter and container_group_name_filter.lower() not in container_group.name.lower():
                        continue
                    
                    # 위치 필터 적용
                    if location_filter and location_filter.lower() not in container_group.location.lower():
                        continue
                    
                    # Container Group 상세 정보 수집
                    aci_detail = collect_aci_details(aci_client, rg_name, container_group, subscription_id)
                    if aci_detail:
                        aci_info_list.append(aci_detail)
                        
            except Exception as e:
                log_error(f"리소스 그룹 {rg_name}의 Container Group 조회 실패: {e}")
                continue
        
        return aci_info_list
        
    except Exception as e:
        log_error(f"Azure Container Instances 목록 조회 실패: Subscription={subscription_id}, Error={e}")
        return []

def collect_aci_details(aci_client, resource_group_name, container_group, subscription_id):
    """Container Group의 상세 정보를 수집합니다."""
    try:
        # 컨테이너 정보
        containers_info = []
        if container_group.containers:
            for container in container_group.containers:
                container_detail = {
                    'name': container.name,
                    'image': container.image,
                    'cpu': container.resources.requests.cpu if container.resources and container.resources.requests else 0,
                    'memory_gb': container.resources.requests.memory_in_gb if container.resources and container.resources.requests else 0,
                    'restart_policy': str(container_group.restart_policy) if container_group.restart_policy else 'Always'
                }
                
                # 환경 변수
                if container.environment_variables:
                    env_vars = []
                    for env_var in container.environment_variables:
                        env_vars.append({
                            'name': env_var.name,
                            'value': env_var.value if not env_var.secure_value else '[SECURE]'
                        })
                    container_detail['environment_variables'] = env_vars
                
                # 포트 정보
                if container.ports:
                    ports = []
                    for port in container.ports:
                        ports.append({
                            'port': port.port,
                            'protocol': str(port.protocol) if port.protocol else 'TCP'
                        })
                    container_detail['ports'] = ports
                
                # 볼륨 마운트
                if container.volume_mounts:
                    volume_mounts = []
                    for mount in container.volume_mounts:
                        volume_mounts.append({
                            'name': mount.name,
                            'mount_path': mount.mount_path,
                            'read_only': mount.read_only if hasattr(mount, 'read_only') else False
                        })
                    container_detail['volume_mounts'] = volume_mounts
                
                # 명령어
                if container.command:
                    container_detail['command'] = list(container.command)
                
                containers_info.append(container_detail)
        
        # IP 주소 정보
        ip_address_info = {}
        if container_group.ip_address:
            ip_address_info = {
                'type': str(container_group.ip_address.type),
                'ip': container_group.ip_address.ip,
                'dns_name_label': container_group.ip_address.dns_name_label,
                'fqdn': container_group.ip_address.fqdn
            }
            
            # 포트 정보
            if container_group.ip_address.ports:
                ports = []
                for port in container_group.ip_address.ports:
                    ports.append({
                        'port': port.port,
                        'protocol': str(port.protocol) if port.protocol else 'TCP'
                    })
                ip_address_info['ports'] = ports
        
        # 볼륨 정보
        volumes_info = []
        if container_group.volumes:
            for volume in container_group.volumes:
                volume_detail = {
                    'name': volume.name
                }
                
                # Azure File Share
                if volume.azure_file:
                    volume_detail['type'] = 'AzureFile'
                    volume_detail['share_name'] = volume.azure_file.share_name
                    volume_detail['storage_account_name'] = volume.azure_file.storage_account_name
                    volume_detail['read_only'] = volume.azure_file.read_only if hasattr(volume.azure_file, 'read_only') else False
                
                # Empty Directory
                elif volume.empty_dir:
                    volume_detail['type'] = 'EmptyDir'
                
                # Secret
                elif volume.secret:
                    volume_detail['type'] = 'Secret'
                    volume_detail['secret_keys'] = list(volume.secret.keys()) if volume.secret else []
                
                # Git Repo
                elif hasattr(volume, 'git_repo') and volume.git_repo:
                    volume_detail['type'] = 'GitRepo'
                    volume_detail['repository'] = volume.git_repo.repository
                    volume_detail['revision'] = volume.git_repo.revision if hasattr(volume.git_repo, 'revision') else 'HEAD'
                
                volumes_info.append(volume_detail)
        
        # 이미지 레지스트리 자격 증명
        image_registry_credentials = []
        if container_group.image_registry_credentials:
            for credential in container_group.image_registry_credentials:
                image_registry_credentials.append({
                    'server': credential.server,
                    'username': credential.username
                    # 패스워드는 보안상 표시하지 않음
                })
        
        # 네트워크 프로필
        network_profile = {}
        if hasattr(container_group, 'network_profile') and container_group.network_profile:
            network_profile = {
                'id': container_group.network_profile.id
            }
        
        # 인스턴스 뷰 (현재 상태)
        instance_view = {}
        if container_group.instance_view:
            instance_view = {
                'state': container_group.instance_view.state,
                'events': []
            }
            
            if container_group.instance_view.events:
                for event in container_group.instance_view.events:
                    instance_view['events'].append({
                        'count': event.count,
                        'first_timestamp': event.first_timestamp.isoformat() if event.first_timestamp else None,
                        'last_timestamp': event.last_timestamp.isoformat() if event.last_timestamp else None,
                        'name': event.name,
                        'message': event.message,
                        'type': event.type
                    })
        
        # Container Group 정보 구성
        aci_data = {
            'subscription_id': subscription_id,
            'resource_group': resource_group_name,
            'container_group': {
                'name': container_group.name,
                'id': container_group.id,
                'location': container_group.location,
                'provisioning_state': str(container_group.provisioning_state),
                'os_type': str(container_group.os_type),
                'restart_policy': str(container_group.restart_policy) if container_group.restart_policy else 'Always',
                'sku': str(container_group.sku) if hasattr(container_group, 'sku') and container_group.sku else 'Standard',
                'tags': get_azure_resource_tags(container_group),
                'containers': containers_info,
                'ip_address': ip_address_info,
                'volumes': volumes_info,
                'image_registry_credentials': image_registry_credentials,
                'network_profile': network_profile,
                'instance_view': instance_view,
                'container_count': len(containers_info),
                'volume_count': len(volumes_info),
                'total_cpu': sum(c.get('cpu', 0) for c in containers_info),
                'total_memory_gb': sum(c.get('memory_gb', 0) for c in containers_info)
            }
        }
        
        return aci_data
        
    except Exception as e:
        log_error(f"Container Group 상세 정보 수집 실패: {container_group.name}, Error={e}")
        return None

def format_output(aci_info_list, output_format):
    """출력 형식에 따라 데이터를 포맷합니다."""
    if output_format == 'json':
        return format_azure_output(aci_info_list, 'json')
    elif output_format == 'yaml':
        return format_azure_output(aci_info_list, 'yaml')
    elif output_format == 'tree':
        return format_tree_output(aci_info_list)
    else:
        return format_table_output(aci_info_list)

def format_tree_output(aci_info_list):
    """트리 형식으로 출력합니다."""
    if not aci_info_list:
        console.print("[yellow]표시할 Azure Container Instances가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for aci_info in aci_info_list:
        subscription_id = aci_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = {}
        
        resource_group = aci_info['resource_group']
        if resource_group not in subscriptions[subscription_id]:
            subscriptions[subscription_id][resource_group] = []
        
        subscriptions[subscription_id][resource_group].append(aci_info)
    
    tree = Tree("📦 [bold blue]Azure Container Instances[/bold blue]")
    
    for subscription_id, resource_groups in subscriptions.items():
        sub_tree = tree.add(f"📋 Subscription: {subscription_id}")
        
        for rg_name, container_groups in resource_groups.items():
            rg_tree = sub_tree.add(f"📁 Resource Group: [magenta]{rg_name}[/magenta]")
            
            for aci_info in container_groups:
                cg = aci_info['container_group']
                cg_tree = rg_tree.add(f"📦 [cyan]{cg['name']}[/cyan] ({cg['os_type']})")
                
                # 기본 정보
                cg_tree.add(f"📍 Location: [green]{cg['location']}[/green]")
                cg_tree.add(f"📊 State: {format_provisioning_state_simple(cg['provisioning_state'])}")
                cg_tree.add(f"🔄 Restart Policy: {cg['restart_policy']}")
                
                # 리소스 정보
                if cg['total_cpu'] > 0 or cg['total_memory_gb'] > 0:
                    cg_tree.add(f"💻 Resources: {cg['total_cpu']} CPU, {cg['total_memory_gb']}GB Memory")
                
                # IP 주소 정보
                if cg['ip_address'].get('ip'):
                    ip_tree = cg_tree.add("🌐 Network")
                    ip_tree.add(f"🌍 IP: {cg['ip_address']['ip']} ({cg['ip_address']['type']})")
                    if cg['ip_address'].get('fqdn'):
                        ip_tree.add(f"🌐 FQDN: {cg['ip_address']['fqdn']}")
                
                # 컨테이너 정보
                if cg['containers']:
                    containers_tree = cg_tree.add(f"📦 Containers ({len(cg['containers'])})")
                    for container in cg['containers']:
                        container_tree = containers_tree.add(f"🐳 {container['name']}")
                        container_tree.add(f"🖼️ Image: {container['image']}")
                        container_tree.add(f"💻 Resources: {container['cpu']} CPU, {container['memory_gb']}GB Memory")
                        
                        if container.get('ports'):
                            ports_str = ', '.join([f"{p['port']}/{p['protocol']}" for p in container['ports']])
                            container_tree.add(f"🔌 Ports: {ports_str}")
                
                # 볼륨 정보
                if cg['volumes']:
                    volumes_tree = cg_tree.add(f"💾 Volumes ({len(cg['volumes'])})")
                    for volume in cg['volumes']:
                        volumes_tree.add(f"💾 {volume['name']} ({volume.get('type', 'Unknown')})")
    
    console.print(tree)

def format_table_output(aci_info_list):
    """테이블 형식으로 출력합니다."""
    if not aci_info_list:
        console.print("[yellow]표시할 Azure Container Instances가 없습니다.[/yellow]")
        return
    
    # 구독별로 그룹화
    subscriptions = {}
    for aci_info in aci_info_list:
        subscription_id = aci_info['subscription_id']
        if subscription_id not in subscriptions:
            subscriptions[subscription_id] = []
        subscriptions[subscription_id].append(aci_info)
    
    for subscription_id, subscription_acis in subscriptions.items():
        console.print(f"\n[bold blue]🔹 Subscription: {subscription_id}[/bold blue]")
        
        # Container Group 요약 테이블
        console.print(f"\n[bold]📦 Container Groups ({len(subscription_acis)} groups)[/bold]")
        summary_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
        summary_table.add_column("Group Name", style="cyan")
        summary_table.add_column("Resource Group", style="magenta")
        summary_table.add_column("Location", style="green")
        summary_table.add_column("OS Type", style="yellow")
        summary_table.add_column("Containers", justify="center")
        summary_table.add_column("Total CPU", justify="center")
        summary_table.add_column("Total Memory", justify="center")
        summary_table.add_column("IP Address", style="blue")
        summary_table.add_column("State", justify="center")
        
        for aci_info in subscription_acis:
            cg = aci_info['container_group']
            
            ip_address = cg['ip_address'].get('ip', '-') if cg['ip_address'] else '-'
            
            summary_table.add_row(
                cg.get('name', '-'),
                aci_info.get('resource_group', '-'),
                cg.get('location', '-'),
                cg.get('os_type', '-'),
                str(cg.get('container_count', 0)),
                str(cg.get('total_cpu', 0)),
                f"{cg.get('total_memory_gb', 0)}GB",
                ip_address,
                format_provisioning_state(cg.get('provisioning_state', 'Unknown'))
            )
        
        console.print(summary_table)
        
        # 컨테이너 상세 정보
        for aci_info in subscription_acis:
            cg = aci_info['container_group']
            if cg.get('containers'):
                console.print(f"\n[bold]🐳 Containers for {cg['name']}[/bold]")
                containers_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
                containers_table.add_column("Container Name", style="cyan")
                containers_table.add_column("Image", style="yellow")
                containers_table.add_column("CPU", justify="center")
                containers_table.add_column("Memory", justify="center")
                containers_table.add_column("Ports", style="blue")
                containers_table.add_column("Environment Variables", justify="center")
                containers_table.add_column("Volume Mounts", justify="center")
                
                for container in cg['containers']:
                    # 포트 정보 요약
                    ports_str = '-'
                    if container.get('ports'):
                        ports_str = ', '.join([f"{p['port']}/{p['protocol']}" for p in container['ports']])
                    
                    # 환경 변수 수
                    env_count = len(container.get('environment_variables', []))
                    
                    # 볼륨 마운트 수
                    mount_count = len(container.get('volume_mounts', []))
                    
                    containers_table.add_row(
                        container.get('name', '-'),
                        container.get('image', '-'),
                        str(container.get('cpu', 0)),
                        f"{container.get('memory_gb', 0)}GB",
                        ports_str,
                        str(env_count) if env_count > 0 else '-',
                        str(mount_count) if mount_count > 0 else '-'
                    )
                
                console.print(containers_table)
        
        # 위치별 통계
        location_stats = {}
        for aci_info in subscription_acis:
            location = aci_info['container_group'].get('location', 'Unknown')
            if location not in location_stats:
                location_stats[location] = {'groups': 0, 'containers': 0, 'total_cpu': 0, 'total_memory': 0}
            location_stats[location]['groups'] += 1
            location_stats[location]['containers'] += aci_info['container_group'].get('container_count', 0)
            location_stats[location]['total_cpu'] += aci_info['container_group'].get('total_cpu', 0)
            location_stats[location]['total_memory'] += aci_info['container_group'].get('total_memory_gb', 0)
        
        if len(location_stats) > 1:
            console.print(f"\n[bold]📊 Location Statistics[/bold]")
            stats_table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
            stats_table.add_column("Location", style="green")
            stats_table.add_column("Container Groups", justify="center")
            stats_table.add_column("Total Containers", justify="center")
            stats_table.add_column("Total CPU", justify="center")
            stats_table.add_column("Total Memory (GB)", justify="center")
            
            for location, stats in sorted(location_stats.items()):
                stats_table.add_row(
                    location,
                    str(stats['groups']),
                    str(stats['containers']),
                    str(stats['total_cpu']),
                    str(stats['total_memory'])
                )
            
            console.print(stats_table)

def format_provisioning_state(state):
    """프로비저닝 상태에 따라 색상을 적용합니다."""
    state_lower = state.lower()
    if 'succeeded' in state_lower:
        return f"[bold green]{state}[/bold green]"
    elif 'failed' in state_lower:
        return f"[bold red]{state}[/bold red]"
    elif 'creating' in state_lower or 'pending' in state_lower:
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
    
    all_aci_info = parallel_azure_operation(
        fetch_aci_info,
        subscriptions,
        args.location,
        args.resource_group,
        args.name
    )
    
    # 출력 형식에 따라 결과 출력
    if args.output in ['json', 'yaml']:
        output = format_output(all_aci_info, args.output)
        print(output)
    elif args.output == 'tree':
        format_tree_output(all_aci_info)
    else:
        format_table_output(all_aci_info)

def add_arguments(parser):
    """명령행 인수를 추가합니다."""
    parser.add_argument('-s', '--subscription', help='특정 Azure 구독 ID 목록(,) (없으면 모든 구독 사용)')
    parser.add_argument('-l', '--location', help='위치 필터 (부분 일치)')
    parser.add_argument('-g', '--resource-group', help='리소스 그룹 필터 (부분 일치)')
    parser.add_argument('-n', '--name', help='Container Group 이름 필터 (부분 일치)')
    parser.add_argument('--output', choices=['table', 'json', 'yaml', 'tree'], default='table',
                       help='출력 형식 (기본값: table)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure Container Instances 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)