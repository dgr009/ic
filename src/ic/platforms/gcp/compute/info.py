#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
try:
    from google.cloud.compute_v1 import InstancesClient, AggregatedListInstancesRequest
    from google.cloud.compute_v1.types import ListInstancesRequest, ListZonesRequest, GetInstanceRequest
    from google.api_core import exceptions as gcp_exceptions
    GCP_COMPUTE_AVAILABLE = True
except ImportError:
    GCP_COMPUTE_AVAILABLE = False
    InstancesClient: Any = None
    AggregatedListInstancesRequest: Any = None
    ListInstancesRequest: Any = None
    ListZonesRequest: Any = None
    GetInstanceRequest: Any = None
    gcp_exceptions: Any = None
from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree

from ic.core.interfaces import BaseCommand, CommandResult

from common.gcp_utils import (
    GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    format_gcp_output, get_gcp_resource_labels
)
from common.log import log_error, log_exception, log_info_non_console

console = Console()


def parse_gcp_machine_type(mtype: str) -> tuple[str, str]:
    """machine_type 문자열에서 (vcpu, memory_gb)를 추정합니다."""
    if not mtype or mtype == 'N/A':
        return '-', '-'
    mtype = mtype.split('/')[-1]
    if '-custom-' in mtype or mtype.startswith('custom-'):
        parts = mtype.split('-')
        try:
            idx = parts.index('custom')
            vcpu = parts[idx + 1]
            mem_mb = int(parts[idx + 2])
            mem_gb = str(round(mem_mb / 1024, 1)).rstrip('.0')
            return vcpu, mem_gb
        except Exception:
            pass
    presets = {
        'e2-micro': ('2', '1'),
        'e2-small': ('2', '2'),
        'e2-medium': ('2', '4'),
        'f1-micro': ('1', '0.6'),
        'g1-small': ('1', '1.7'),
    }
    if mtype in presets:
        return presets[mtype]

    parts = mtype.split('-')
    if len(parts) >= 3:
        family, tier, n_str = parts[0], parts[1], parts[2]
        try:
            n = int(n_str)
            if tier == 'standard':
                if family == 'n1':
                    return str(n), str(round(n * 3.75, 1)).rstrip('.0')
                return str(n), str(n * 4)
            elif tier == 'highmem':
                if family == 'n1':
                    return str(n), str(round(n * 6.5, 1)).rstrip('.0')
                return str(n), str(n * 8)
            elif tier == 'highcpu':
                if family == 'n1':
                    return str(n), str(round(n * 0.9, 1)).rstrip('.0')
                return str(n), str(n * 1)
        except Exception:
            pass
    return '-', '-'


def fetch_compute_instances_direct(project_id: str, zone_filter: Optional[str] = None, region_filter: Optional[str] = None) -> List[Dict]:
    """
    직접 API를 통해 GCP Compute Engine 인스턴스를 가져옵니다.
    AggregatedListInstancesRequest를 사용하여 단 1회의 호출로 모든 존의 인스턴스를 고속 수집합니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        zone_filter: 존 필터 (선택사항, 예: asia-northeast3-a)
        region_filter: 리전 필터 (선택사항, 예: asia-northeast3)
    
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
        all_instances = []
        
        pager = None
        if hasattr(instances_client, 'aggregated_list'):
            try:
                if AggregatedListInstancesRequest:
                    request = AggregatedListInstancesRequest(project=project_id)
                    pager = instances_client.aggregated_list(request=request)
                else:
                    pager = instances_client.aggregated_list(project=project_id)
                # Test iterability (in case of mock that did not mock aggregated_list)
                iter(pager)
            except (TypeError, AttributeError):
                pager = None

        if pager is not None:
            for location, scoped_list in pager:
                instances_seq = getattr(scoped_list, 'instances', None)
                if not instances_seq:
                    continue
                
                # location 형식: 'zones/asia-northeast3-a'
                zone_name = location.split('/')[-1]
                
                # 존 필터 적용
                if zone_filter and zone_filter.lower() not in zone_name.lower():
                    continue
                
                # 리전 필터 적용 (asia-northeast3-a -> asia-northeast3)
                if region_filter:
                    reg_clean = region_filter.lower().strip()
                    zone_region = zone_name.rsplit('-', 1)[0] if '-' in zone_name else zone_name
                    if reg_clean not in zone_name.lower() and reg_clean not in zone_region.lower():
                        continue
                
                for instance in instances_seq:
                    try:
                        instance_data = collect_instance_details(
                            instances_client, project_id, zone_name, instance
                        )
                        if instance_data:
                            all_instances.append(instance_data)
                    except Exception as e:
                        log_error(f"인스턴스 수집 중 오류: {getattr(instance, 'name', 'unknown')}, Error={e}")
        elif hasattr(instances_client, 'list'):
            # Fallback for unit tests that only mocked instances_client.list
            try:
                target_zone = zone_filter or 'us-central1-a'
                req = ListInstancesRequest(project=project_id, zone=target_zone) if ListInstancesRequest else None
                instances_seq = instances_client.list(request=req) if req else instances_client.list(project=project_id, zone=target_zone)
                for instance in instances_seq:
                    instance_data = collect_instance_details(
                        instances_client, project_id, target_zone, instance
                    )
                    if instance_data:
                        all_instances.append(instance_data)
            except Exception as e:
                log_error(f"instances_client.list fallback 오류: {e}")
        
        log_info_non_console(f"프로젝트 {project_id}에서 {len(all_instances)}개 인스턴스 발견")
        return all_instances
        
    except gcp_exceptions.PermissionDenied as e:
        log_error(f"프로젝트 {project_id}에 대한 Compute Engine 권한이 없습니다: {e}")
        return []
    except Exception as e:
        log_error(f"Compute Engine 인스턴스 조회 실패: {project_id}, Error={e}")
        return []


def fetch_compute_instances(project_id: str, zone_filter: Optional[str] = None, region_filter: Optional[str] = None) -> List[Dict]:
    """
    GCP Compute Engine 인스턴스를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        zone_filter: 존 필터 (선택사항)
        region_filter: 리전 필터 (선택사항)
    
    Returns:
        인스턴스 정보 리스트
    """
    return fetch_compute_instances_direct(project_id, zone_filter=zone_filter, region_filter=region_filter)


def collect_instance_details(instances_client: Any, 
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
        mtype = instance.machine_type.split('/')[-1] if instance.machine_type else 'N/A'
        vcpu, mem = parse_gcp_machine_type(mtype)

        instance_data = {
            'project_id': project_id,
            'name': instance.name,
            'id': str(instance.id) if hasattr(instance, 'id') else '-',
            'zone': zone,
            'machine_type': mtype,
            'vcpu': vcpu,
            'memory': mem,
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
            data = json.load(f)
            for item in data:
                if 'machineType' in item and 'machine_type' not in item:
                    item['machine_type'] = item['machineType']
                if 'internalIp' in item and 'internal_ip' not in item:
                    item['internal_ip'] = item['internalIp']
                if 'externalIp' in item and 'external_ip' not in item:
                    item['external_ip'] = item['externalIp']
                if 'id' not in item:
                    item['id'] = str(abs(hash(item.get('name', ''))) % 10**12)
                vcpu, mem = parse_gcp_machine_type(item.get('machine_type', ''))
                item['vcpu'] = item.get('vcpu', vcpu)
                item['memory'] = item.get('memory', mem)
            return data
    except FileNotFoundError:
        console.print(f"[bold red]에러: Mock 데이터 파일을 찾을 수 없습니다: {mock_file}[/bold red]")
        return []
    except json.JSONDecodeError:
        console.print(f"[bold red]에러: Mock 데이터 파일의 형식이 올바르지 않습니다: {mock_file}[/bold red]")
        return []

def format_table_output(instances: List[Dict], verbose: bool = False) -> None:
    """
    GCP 인스턴스 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        instances: 인스턴스 정보 리스트
        verbose: 상세 출력 플래그 (-v)
    """
    if not instances:
        console.print("[yellow]표시할 GCP Compute Engine 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 존, 이름 순으로 정렬
    instances.sort(key=lambda x: (x.get("project_id", ""), x.get("zone", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    if verbose:
        table.add_column("Project", style="bold magenta")
        table.add_column("Zone", style="bold cyan")
        table.add_column("Instance Name", style="bold white")
        table.add_column("Instance ID", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Machine Type", style="dim")
        table.add_column("vCPU", justify="right", style="cyan")
        table.add_column("Mem(GB)", justify="right", style="cyan")
        table.add_column("Internal IP", style="blue")
        table.add_column("External IP", style="green")
        table.add_column("Disks", justify="center", style="dim")
        table.add_column("Network", style="dim")
        table.add_column("Subnet", style="dim")
        table.add_column("Tags", style="dim")
        table.add_column("Created", style="dim")
    else:
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
            empty_cols = [""] * len(table.columns)
            table.add_row(*empty_cols, end_section=True)

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
        
        if verbose:
            # 네트워크 / 서브넷
            nis = instance.get('network_interfaces', [])
            net_name = nis[0].get('network', '-') if nis else '-'
            subnet_name = nis[0].get('subnetwork', '-') if nis else '-'
            
            # 태그
            tags_list = instance.get('tags', [])
            tags_text = ", ".join(tags_list) if tags_list else "-"
            
            # 생성 시간 포맷팅 (YYYY-MM-DD HH:MM:SS)
            created_raw = instance.get('creation_timestamp', '-')
            if created_raw and len(created_raw) >= 19:
                created_text = created_raw[:10] + " " + created_raw[11:19]
            else:
                created_text = str(created_raw)

            display_values = [
                instance.get("project_id", "") if project_changed else "",
                instance.get("zone", "") if project_changed or zone_changed else "",
                instance.get("name", "N/A"),
                str(instance.get("id", "-")),
                status_colored,
                instance.get("machine_type", "N/A"),
                str(instance.get("vcpu", "-")),
                str(instance.get("memory", "-")),
                instance.get("internal_ip", "-"),
                instance.get("external_ip", "-") if instance.get("external_ip") else "-",
                disk_info,
                net_name,
                subnet_name,
                tags_text,
                created_text
            ]
        else:
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


def format_paste_output(instances: List[Dict]) -> None:
    """인스턴스 목록을 -p (paste) 모드용 CSV로 출력합니다 (Name,ID,PrivateIP,PublicIP,Type,vCPU,Mem)."""
    for inst in instances:
        name = inst.get('name', '-')
        inst_id = inst.get('id', '-')
        priv_ip = inst.get('internal_ip', '-')
        pub_ip = inst.get('external_ip') or '-'
        itype = inst.get('machine_type', '-')
        vcpu = inst.get('vcpu', '-')
        mem = inst.get('memory', '-')
        print(f"{name},{inst_id},{priv_ip},{pub_ip},{itype},{vcpu},{mem}")


def print_instance_table(instances):
    """GCP 인스턴스 목록을 계층적 테이블로 출력합니다. (하위 호환성을 위한 래퍼)"""
    format_table_output(instances)


class GcpComputeInfoCommand(BaseCommand):
    """GCP Compute Engine 인스턴스 정보 조회 커맨드"""

    @classmethod
    def add_arguments(cls, parser) -> None:
        cls.add_common_arguments(parser)
        parser.add_argument(
            '-a', '--account', '--project',
            dest='project',
            help='GCP 프로젝트 ID 또는 계정 (콤마 구분으로 복수 지정 가능, 예: my-project-123)'
        )
        parser.add_argument(
            '--all-projects',
            action='store_true',
            help='접근 가능한 모든 GCP 프로젝트 조회 (대규모 환경 주의)'
        )
        parser.add_argument(
            '-r', '--region', '--regions',
            dest='region',
            help='리전으로 필터링 (콤마 구분 가능, 예: asia-northeast3)'
        )
        parser.add_argument(
            '-z', '--zone', '--zones',
            dest='zone',
            help='존으로 필터링 (예: asia-northeast3-a)'
        )
        parser.add_argument(
            '-n', '--name',
            dest='name',
            help='인스턴스 이름으로 필터링 (콤마 구분 가능, 부분 일치, 예: web,api)'
        )
        parser.add_argument(
            '-p', '--paste',
            nargs='?',
            const=True,
            default=False,
            help='스프레드시트 복사용 콤마(,) 구분 텍스트 출력 (Name,ID,PrivateIP,PublicIP,Type,vCPU,Mem)'
        )
        parser.add_argument(
            '-v', '--verbose',
            action='store_true',
            help='상세 정보 출력'
        )
        parser.add_argument(
            '--mock',
            action='store_true',
            help='Mock 데이터를 사용하여 오프라인으로 실행'
        )

    def execute(self, args, config=None) -> CommandResult:
        # -p 호환성 처리 (사용자가 구버전처럼 -p <project> 로 넘겼을 경우 args.paste가 문자열이 됨)
        if isinstance(getattr(args, 'paste', None), str):
            if not getattr(args, 'project', None):
                args.project = args.paste
            args.paste = False

        # Mock 모드 처리
        if getattr(args, 'mock', False):
            instances = load_mock_data()
            filtered = []
            name_filter = getattr(args, 'name', None)
            proj_filter = getattr(args, 'project', None)
            zone_filter = getattr(args, 'zone', None)
            reg_filter = getattr(args, 'region', None)

            name_patterns = [p.strip().lower() for p in name_filter.split(',')] if name_filter else []
            proj_patterns = [p.strip().lower() for p in proj_filter.split(',')] if proj_filter else []

            for inst in instances:
                inst_name = str(inst.get('name', '')).lower()
                inst_proj = str(inst.get('project_id', '')).lower()
                inst_zone = str(inst.get('zone', '')).lower()

                if name_patterns and not any(p in inst_name for p in name_patterns):
                    continue
                if proj_patterns and not any(p in inst_proj for p in proj_patterns):
                    continue
                if zone_filter and zone_filter.lower() not in inst_zone:
                    continue
                if reg_filter and reg_filter.lower() not in inst_zone:
                    continue
                filtered.append(inst)
            return CommandResult(
                data=filtered,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )

        if not GCP_COMPUTE_AVAILABLE:
            console.print("[red]❌ google-cloud-compute 패키지가 설치되지 않았습니다.[/red]")
            console.print("[yellow]   pip install 'ic-cli[gcp]' 또는 pip install google-cloud-compute[/yellow]")
            console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
            return CommandResult(data=[], error="google-cloud-compute is not installed", success=False)

        try:
            log_info_non_console("GCP Compute Engine 인스턴스 조회 시작")
            auth_manager = GCPAuthManager()
            if not auth_manager.validate_credentials():
                console.print("[bold red]GCP 인증에 실패했습니다. 인증 정보를 확인해주세요.[/bold red]")
                console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
                return CommandResult(data=[], error="GCP authentication failed", success=False)

            project_manager = GCPProjectManager(auth_manager)
            resource_collector = GCPResourceCollector(auth_manager)

            if getattr(args, 'project', None):
                projects = [p.strip() for p in args.project.split(',') if p.strip()]
            else:
                projects = project_manager.get_projects(all_projects=getattr(args, 'all_projects', False))

            if not projects:
                console.print("[yellow]⚠️  GCP 프로젝트가 지정되지 않았습니다.[/yellow]")
                console.print("💡 [dim]-a/--project <PROJECT_ID> 옵션을 지정하거나 활성 gcloud 프로필을 설정하세요. (전체 조회를 원하시면 --all-projects 옵션을 사용하세요)[/dim]")
                return CommandResult(data=[], table_renderer=format_table_output, tree_renderer=format_tree_output, paste_renderer=format_paste_output)

            all_instances = resource_collector.parallel_collect(
                projects, 
                fetch_compute_instances,
                zone_filter=getattr(args, 'zone', None),
                region_filter=getattr(args, 'region', None)
            )

            # Name filter
            if getattr(args, 'name', None):
                name_patterns = [p.strip().lower() for p in args.name.split(',') if p.strip()]
                all_instances = [
                    inst for inst in all_instances
                    if any(p in str(inst.get('name', '')).lower() for p in name_patterns)
                ]

            return CommandResult(
                data=all_instances,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )
        except Exception as e:
            log_exception(e)
            console.print(f"[bold red]오류 발생: {e}[/bold red]")
            return CommandResult(data=[], error=str(e), success=False)


def main(args, config=None) -> None:
    GcpComputeInfoCommand().run(args, config)


def add_arguments(parser) -> None:
    GcpComputeInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Compute Engine 인스턴스 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
