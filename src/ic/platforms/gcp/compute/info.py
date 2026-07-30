#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
from google.cloud.compute_v1 import InstancesClient, ZonesClient
from google.cloud.compute_v1.types import ListInstancesRequest, ListZonesRequest, GetInstanceRequest
from google.api_core import exceptions as gcp_exceptions
from rich.console import Console
from rich.table import Table
from rich import box
from rich.rule import Rule
from rich.tree import Tree

from common.gcp_utils import (
        GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    create_gcp_client, format_gcp_output, get_gcp_resource_labels
    )
from common.log import log_info, log_error, log_exception

# Import MCP integration
try:
    from mcp.gcp_connector import MCPGCPService
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

console = Console()


def fetch_compute_instances_via_mcp(mcp_connector, project_id: str, zone_filter: str = None) -> List[Dict]:
    """
    MCP 서버를 통해 GCP Compute Engine 인스턴스를 가져옵니다.
    
    Args:
        mcp_connector: MCP GCP 커넥터
        project_id: GCP 프로젝트 ID
        zone_filter: 존 필터 (선택사항)
    
    Returns:
        인스턴스 정보 리스트
    """
    try:
        params = {
            'project_id': project_id,
            'zone_filter': zone_filter
        }
        
        response = mcp_connector.execute_gcp_query('compute', 'list_instances', params)
        if response.success:
            return response.data.get('instances', [])
        else:
            log_error(f"MCP compute instances query failed: {response.error}")
            return []
            
    except Exception as e:
        log_error(f"MCP compute instances fetch failed: {e}")
        return []


def fetch_compute_instances_direct(project_id: str, zone_filter: str = None) -> List[Dict]:
    """
    직접 API를 통해 GCP Compute Engine 인스턴스를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        zone_filter: 존 필터 (선택사항)
    
    Returns:
        인스턴스 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        instances_client = InstancesClient(credentials=credentials)
        zones_client = ZonesClient(credentials=credentials)
        
        # 프로젝트의 모든 존 가져오기
        zones_request = ListZonesRequest(project=project_id)
        zones = zones_client.list(request=zones_request)
        
        all_instances = []
        
        for zone in zones:
            # 존 필터 적용
            if zone_filter and zone_filter not in zone.name:
                continue
            
            try:
                # 해당 존의 인스턴스 가져오기
                request = ListInstancesRequest(
                    project=project_id,
                    zone=zone.name
                )
                
                instances = instances_client.list(request=request)
                
                for instance in instances:
                    instance_data = collect_instance_details(
                        instances_client, project_id, zone.name, instance
                    )
                    if instance_data:
                        all_instances.append(instance_data)
                        
            except gcp_exceptions.Forbidden:
                log_error(f"존 {zone.name}에 대한 접근 권한이 없습니다: {project_id}")
                continue
            except Exception as e:
                log_error(f"존 {zone.name}에서 인스턴스 조회 실패: {project_id}, Error={e}")
                continue
        
        log_info(f"프로젝트 {project_id}에서 {len(all_instances)}개 인스턴스 발견")
        return all_instances
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Compute Engine 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"Compute Engine 인스턴스 조회 실패: {project_id}, Error={e}")
        return []


def fetch_compute_instances(project_id: str, zone_filter: str = None) -> List[Dict]:
    """
    GCP Compute Engine 인스턴스를 가져옵니다 (MCP 우선, 직접 API 폴백).
    
    Args:
        project_id: GCP 프로젝트 ID
        zone_filter: 존 필터 (선택사항)
    
    Returns:
        인스턴스 정보 리스트
    """
    # MCP 서비스 사용 시도
    if MCP_AVAILABLE:
        try:
            mcp_service = MCPGCPService('compute')
            return mcp_service.execute_with_fallback(
                'list_instances',
                {'project_id': project_id, 'zone_filter': zone_filter},
                lambda project_id, zone_filter: fetch_compute_instances_direct(project_id, zone_filter)
            )
        except Exception as e:
            log_error(f"MCP service failed, using direct API: {e}")
    
    # 직접 API 사용
    return fetch_compute_instances_direct(project_id, zone_filter)


def collect_instance_details(instances_client: InstancesClient, 
                           project_id: str, zone: str, instance) -> Optional[Dict]:
    """
    인스턴스의 상세 정보를 수집합니다.
    
    Args:
        instances_client: Compute Engine 인스턴스 클라이언트
        project_id: GCP 프로젝트 ID
        zone: 존 이름
        instance: 인스턴스 객체
    
    Returns:
        인스턴스 상세 정보 딕셔너리
    """
    try:
        # 기본 인스턴스 정보
        instance_data = {
            'project_id': project_id,
            'name': instance.name,
            'zone': zone,
            'machine_type': instance.machine_type.split('/')[-1] if instance.machine_type else 'N/A',
            'status': instance.status,
            'creation_timestamp': instance.creation_timestamp,
            'description': instance.description or '',
            'labels': get_gcp_resource_labels(instance),
            'metadata': {},
            'disks': [],
            'network_interfaces': [],
            'service_accounts': [],
            'tags': []
        }
        
        # 메타데이터 수집
        if hasattr(instance, 'metadata') and instance.metadata:
            for item in instance.metadata.items:
                instance_data['metadata'][item.key] = item.value
        
        # 디스크 정보 수집
        if hasattr(instance, 'disks') and instance.disks:
            for disk in instance.disks:
                disk_info = {
                    'device_name': disk.device_name,
                    'boot': disk.boot,
                    'auto_delete': disk.auto_delete,
                    'mode': disk.mode,
                    'type': disk.type_,
                    'interface': disk.interface
                }
                if disk.source:
                    disk_info['source'] = disk.source.split('/')[-1]
                instance_data['disks'].append(disk_info)
        
        # 네트워크 인터페이스 정보 수집
        if hasattr(instance, 'network_interfaces') and instance.network_interfaces:
            for ni in instance.network_interfaces:
                ni_info = {
                    'name': ni.name,
                    'network': ni.network.split('/')[-1] if ni.network else 'N/A',
                    'subnetwork': ni.subnetwork.split('/')[-1] if ni.subnetwork else 'N/A',
                    'internal_ip': ni.network_i_p,
                    'external_ip': None
                }
                
                # 외부 IP 정보
                if hasattr(ni, 'access_configs') and ni.access_configs:
                    for access_config in ni.access_configs:
                        if access_config.nat_i_p:
                            ni_info['external_ip'] = access_config.nat_i_p
                            break
                
                instance_data['network_interfaces'].append(ni_info)
        
        # 서비스 계정 정보 수집
        if hasattr(instance, 'service_accounts') and instance.service_accounts:
            for sa in instance.service_accounts:
                sa_info = {
                    'email': sa.email,
                    'scopes': list(sa.scopes) if sa.scopes else []
                }
                instance_data['service_accounts'].append(sa_info)
        
        # 태그 정보 수집
        if hasattr(instance, 'tags') and instance.tags and instance.tags.items:
            instance_data['tags'] = list(instance.tags.items)
        
        # 편의를 위한 추가 필드
        instance_data['internal_ip'] = (
            instance_data['network_interfaces'][0]['internal_ip'] 
            if instance_data['network_interfaces'] else 'N/A'
        )
        instance_data['external_ip'] = (
            instance_data['network_interfaces'][0]['external_ip'] 
            if instance_data['network_interfaces'] and 
               instance_data['network_interfaces'][0]['external_ip'] else None
        )
        
        return instance_data
        
    except Exception as e:
        log_error(f"인스턴스 상세 정보 수집 실패: {instance.name}, Error={e}")
        return None


def get_instance_metadata(project_id: str, zone: str, instance_name: str) -> Optional[Dict]:
    """
    특정 인스턴스의 메타데이터를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        zone: 존 이름
        instance_name: 인스턴스 이름
    
    Returns:
        인스턴스 메타데이터 딕셔너리
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            return None
        
        instances_client = InstancesClient(credentials=credentials)
        
        request = GetInstanceRequest(
            project=project_id,
            zone=zone,
            instance=instance_name
        )
        
        instance = instances_client.get(request=request)
        return collect_instance_details(instances_client, project_id, zone, instance)
        
    except Exception as e:
        log_error(f"인스턴스 메타데이터 조회 실패: {instance_name}, Error={e}")
        return None


def load_mock_data():
    """Mocks/gcp/compute/mock_data.json 에서 데이터를 로드합니다."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    mock_file = os.path.join(dir_path, 'mock_data.json')

    try:
        with open(mock_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[bold red]에러: Mock 데이터 파일을 찾을 수 없습니다: {mock_file}[/bold red]")
        return []
    except json.JSONDecodeError:
        console.print(f"[bold red]에러: Mock 데이터 파일의 형식이 올바르지 않습니다: {mock_file}[/bold red]")
        return []

def format_table_output(instances: List[Dict]) -> None:
    """
    GCP 인스턴스 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        instances: 인스턴스 정보 리스트
    """
    if not instances:
        console.print("[yellow]표시할 GCP Compute Engine 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 존, 이름 순으로 정렬
    instances.sort(key=lambda x: (x.get("project_id", ""), x.get("zone", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Zone", style="bold cyan")
    table.add_column("Instance Name", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Machine Type", style="dim")
    table.add_column("Internal IP", style="blue")
    table.add_column("External IP", style="green")
    table.add_column("Disks", justify="center", style="dim")
    table.add_column("Labels", style="dim")

    last_project = None
    last_zone = None
    
    for i, instance in enumerate(instances):
        project_changed = instance.get("project_id") != last_project
        zone_changed = instance.get("zone") != last_zone

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", end_section=True)

        # 상태에 따른 색상 적용
        status = instance.get('status', 'N/A')
        if status == "RUNNING":
            status_colored = f"[green]{status}[/green]"
        elif status == "TERMINATED":
            status_colored = f"[red]{status}[/red]"
        elif status == "STOPPING":
            status_colored = f"[yellow]{status}[/yellow]"
        else:
            status_colored = f"[dim]{status}[/dim]"
        
        # 디스크 개수
        disk_count = len(instance.get('disks', []))
        disk_info = f"{disk_count}" if disk_count > 0 else "-"
        
        # 라벨 정보 (최대 2개만 표시)
        labels = instance.get('labels', {})
        if labels:
            label_items = list(labels.items())[:2]
            label_text = ", ".join([f"{k}={v}" for k, v in label_items])
            if len(labels) > 2:
                label_text += f" (+{len(labels)-2})"
        else:
            label_text = "-"
        
        display_values = [
            instance.get("project_id", "") if project_changed else "",
            instance.get("zone", "") if project_changed or zone_changed else "",
            instance.get("name", "N/A"),
            status_colored,
            instance.get("machine_type", "N/A"),
            instance.get("internal_ip", "-"),
            instance.get("external_ip", "-") if instance.get("external_ip") else "-",
            disk_info,
            label_text
        ]
        
        table.add_row(*display_values)

        last_project = instance.get("project_id")
        last_zone = instance.get("zone")
    
    console.print(table)


def format_tree_output(instances: List[Dict]) -> None:
    """
    GCP 인스턴스 목록을 트리 형식으로 출력합니다 (프로젝트/존 계층).
    
    Args:
        instances: 인스턴스 정보 리스트
    """
    if not instances:
        console.print("[yellow]표시할 GCP Compute Engine 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for instance in instances:
        project_id = instance.get("project_id", "unknown")
        zone = instance.get("zone", "unknown")
        
        if project_id not in projects:
            projects[project_id] = {}
        if zone not in projects[project_id]:
            projects[project_id][zone] = []
        
        projects[project_id][zone].append(instance)

    # 트리 구조 생성
    tree = Tree("🌐 [bold blue]GCP Compute Engine Instances[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta]")
        
        for zone in sorted(projects[project_id].keys()):
            zone_instances = projects[project_id][zone]
            zone_node = project_node.add(
                f"🌍 [bold cyan]{zone}[/bold cyan] ({len(zone_instances)} instances)"
            )
            
            for instance in sorted(zone_instances, key=lambda x: x.get("name", "")):
                # 상태 아이콘
                status = instance.get('status', 'N/A')
                if status == "RUNNING":
                    status_icon = "🟢"
                elif status == "TERMINATED":
                    status_icon = "🔴"
                elif status == "STOPPING":
                    status_icon = "🟡"
                else:
                    status_icon = "⚪"
                
                # 인스턴스 정보
                instance_name = instance.get("name", "N/A")
                machine_type = instance.get("machine_type", "N/A")
                internal_ip = instance.get("internal_ip", "N/A")
                external_ip = instance.get("external_ip", "None")
                
                instance_info = (
                    f"{status_icon} [bold white]{instance_name}[/bold white] "
                    f"({machine_type}) - "
                    f"Internal: [blue]{internal_ip}[/blue]"
                )
                
                if external_ip and external_ip != "None":
                    instance_info += f", External: [green]{external_ip}[/green]"
                
                instance_node = zone_node.add(instance_info)
                
                # 추가 세부 정보
                if instance.get('disks'):
                    disk_count = len(instance['disks'])
                    instance_node.add(f"💾 Disks: {disk_count}")
                
                if instance.get('labels'):
                    labels_text = ", ".join([f"{k}={v}" for k, v in instance['labels'].items()])
                    instance_node.add(f"🏷️  Labels: {labels_text}")
                
                if instance.get('tags'):
                    tags_text = ", ".join(instance['tags'])
                    instance_node.add(f"🔖 Tags: {tags_text}")

    console.print(tree)


def format_output(instances: List[Dict], output_format: str = 'table') -> str:
    """
    인스턴스 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        instances: 인스턴스 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(instances)
        return ""
    elif output_format == 'tree':
        format_tree_output(instances)
        return ""
    elif output_format == 'json':
        return format_gcp_output(instances, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(instances, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(instances)
        return ""


def print_instance_table(instances):
    """GCP 인스턴스 목록을 계층적 테이블로 출력합니다. (하위 호환성을 위한 래퍼)"""
    format_table_output(instances)

def main(args):
    """
    메인 함수 - GCP Compute Engine 인스턴스 정보를 조회하고 출력합니다.
    
    Args:
        args: CLI 인자 객체
    """
    try:
        log_info("GCP Compute Engine 인스턴스 조회 시작")
        
        # GCP 인증 및 프로젝트 관리자 초기화
        auth_manager = GCPAuthManager()
        if not auth_manager.validate_credentials():
            console.print("[bold red]GCP 인증에 실패했습니다. 인증 정보를 확인해주세요.[/bold red]")
            return
        
        project_manager = GCPProjectManager(auth_manager)
        resource_collector = GCPResourceCollector(auth_manager)
        
        # 프로젝트 목록 가져오기
        if args.project:
            # 특정 프로젝트 지정된 경우
            projects = [args.project]
        else:
            # 모든 접근 가능한 프로젝트 사용
            projects = project_manager.get_projects()
        
        if not projects:
            console.print("[yellow]접근 가능한 GCP 프로젝트가 없습니다.[/yellow]")
            return
        
        log_info(f"조회할 프로젝트: {len(projects)}개")
        
        # 병렬로 인스턴스 수집
        all_instances = resource_collector.parallel_collect(
            projects, 
            fetch_compute_instances,
            args.zone if hasattr(args, 'zone') else None
        )
        
        if not all_instances:
            console.print("[yellow]조회된 Compute Engine 인스턴스가 없습니다.[/yellow]")
            return
        
        # 필터 적용
        filters = {}
        if hasattr(args, 'name') and args.name:
            filters['name'] = args.name
        if hasattr(args, 'project') and args.project:
            filters['project'] = args.project
        if hasattr(args, 'zone') and args.zone:
            filters['zone'] = args.zone
        
        filtered_instances = resource_collector.apply_filters(all_instances, filters)
        
        # 출력 형식 결정
        output_format = getattr(args, 'output', 'table')
        
        # 결과 출력
        if output_format in ['json', 'yaml']:
            output_text = format_output(filtered_instances, output_format)
            console.print(output_text)
        else:
            format_output(filtered_instances, output_format)
        
        log_info(f"총 {len(filtered_instances)}개 인스턴스 조회 완료")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]사용자에 의해 중단되었습니다.[/yellow]")
    except Exception as e:
        log_exception(e)
        console.print(f"[bold red]오류 발생: {e}[/bold red]")


def add_arguments(parser):
    """
    CLI 인자를 추가합니다.
    
    Args:
        parser: argparse.ArgumentParser 객체
    """
    parser.add_argument(
        '-p', '--project', 
        help='GCP 프로젝트 ID로 필터링 (예: my-project-123)'
    )
    parser.add_argument(
        '-n', '--name', 
        help='인스턴스 이름으로 필터링 (부분 일치)'
    )
    parser.add_argument(
        '-z', '--zone', 
        help='존으로 필터링 (예: us-central1-a)'
    )
    parser.add_argument(
        '-o', '--output', 
        choices=['table', 'tree', 'json', 'yaml'],
        default='table',
        help='출력 형식 선택 (기본값: table)'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Compute Engine 인스턴스 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
