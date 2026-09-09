#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
try:
    from google.cloud.run_v2 import ServicesClient
    from google.cloud.run_v2.types import ListServicesRequest, GetServiceRequest
    from google.api_core import exceptions as gcp_exceptions
    GCP_RUN_AVAILABLE = True
except ImportError:
    GCP_RUN_AVAILABLE = False
    ServicesClient: Any = None
    ListServicesRequest: Any = None
    GetServiceRequest: Any = None
    gcp_exceptions: Any = None
from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree

from ic.core.interfaces import BaseCommand, CommandResult
from common.gcp_utils import (
    GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    format_gcp_output
)
from common.log import log_error, log_exception, log_info_non_console

console = Console()


def fetch_run_services_direct(project_id: str, region_filter: Optional[str] = None) -> List[Dict]:
    """
    직접 API를 통해 GCP Cloud Run 서비스를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        Cloud Run 서비스 정보 리스트
    """
    try:
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        if not credentials:
            log_error(f"GCP 인증 실패: {project_id}")
            return []
        
        run_client = ServicesClient(credentials=credentials)
        all_services = []
        
        target_location = region_filter if region_filter else '-'
        try:
            parent = f"projects/{project_id}/locations/{target_location}"
            request = ListServicesRequest(parent=parent)
            response = run_client.list_services(request=request)
            
            for service in response:
                # service.name format: projects/{proj}/locations/{loc}/services/{svc}
                parts = service.name.split('/')
                svc_region = parts[3] if len(parts) > 3 else target_location
                service_data = collect_service_details(
                    run_client, project_id, svc_region, service
                )
                if service_data:
                    all_services.append(service_data)
        except Exception as e:
            log_error(f"Cloud Run 서비스 조회 실패: {project_id}, Error={e}")
        
        log_info_non_console(f"프로젝트 {project_id}에서 {len(all_services)}개 Cloud Run 서비스 발견")
        return all_services
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Cloud Run 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"Cloud Run 서비스 조회 실패: {project_id}, Error={e}")
        return []


def fetch_run_services(project_id: str, region_filter: Optional[str] = None) -> List[Dict]:
    """
    GCP Cloud Run 서비스를 가져옵니다.
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        Cloud Run 서비스 정보 리스트
    """
    return fetch_run_services_direct(project_id, region_filter)


def collect_service_details(run_client: Any,
                          project_id: str, region: str, service) -> Optional[Dict]:
    """
    Cloud Run 서비스의 상세 정보를 수집합니다.
    
    Args:
        run_client: Cloud Run 클라이언트
        project_id: GCP 프로젝트 ID
        region: 지역
        service: 서비스 객체
    
    Returns:
        서비스 상세 정보 딕셔너리
    """
    try:
        # 기본 서비스 정보
        service_data = {
            'project_id': project_id,
            'name': service.name.split('/')[-1],  # projects/PROJECT/locations/REGION/services/NAME -> NAME
            'full_name': service.name,
            'region': region,
            'description': service.description or '',
            'uid': service.uid,
            'generation': service.generation,
            'labels': dict(service.labels) if service.labels else {},
            'annotations': dict(service.annotations) if service.annotations else {},
            'create_time': service.create_time,
            'update_time': service.update_time,
            'delete_time': service.delete_time,
            'expire_time': service.expire_time,
            'creator': service.creator,
            'last_modifier': service.last_modifier,
            'client': service.client,
            'client_version': service.client_version,
            'ingress': service.ingress.name if hasattr(service.ingress, 'name') else str(service.ingress),
            'launch_stage': service.launch_stage.name if hasattr(service.launch_stage, 'name') else str(service.launch_stage),
            'binary_authorization': {},
            'template': {},
            'traffic': [],
            'observed_generation': service.observed_generation,
            'terminal_condition': {},
            'conditions': [],
            'latest_ready_revision': service.latest_ready_revision,
            'latest_created_revision': service.latest_created_revision,
            'uri': service.uri,
            'custom_audiences': list(service.custom_audiences) if service.custom_audiences else [],
            'default_uri_disabled': service.default_uri_disabled
        }
        
        # Binary Authorization 설정
        if service.binary_authorization:
            service_data['binary_authorization'] = {
                'use_default': service.binary_authorization.use_default,
                'policy': service.binary_authorization.policy,
                'breakglass_justification': service.binary_authorization.breakglass_justification
            }
        
        # 템플릿 정보
        template_data: Dict[str, Any] = {}
        containers_list: List[Dict[str, Any]] = []
        volumes_list: List[Dict[str, Any]] = []
        scaling_data: Dict[str, Any] = {}
        vpc_access_data: Dict[str, Any] = {}

        if service.template:
            template = service.template
            if template.scaling:
                scaling_data = {
                    'min_instance_count': template.scaling.min_instance_count,
                    'max_instance_count': template.scaling.max_instance_count
                }
            
            if template.vpc_access:
                vpc_network_interfaces: List[Dict[str, Any]] = []
                if template.vpc_access.network_interfaces:
                    for ni in template.vpc_access.network_interfaces:
                        vpc_network_interfaces.append({
                            'network': ni.network,
                            'subnetwork': ni.subnetwork,
                            'tags': list(ni.tags) if ni.tags else []
                        })
                vpc_access_data = {
                    'connector': template.vpc_access.connector,
                    'egress': template.vpc_access.egress.name if hasattr(template.vpc_access.egress, 'name') else str(template.vpc_access.egress),
                    'network_interfaces': vpc_network_interfaces
                }
            
            if template.containers:
                for container in template.containers:
                    c_env: List[Dict[str, Any]] = []
                    if container.env:
                        for env_var in container.env:
                            env_entry: Dict[str, Any] = {
                                'name': env_var.name,
                                'value': env_var.value,
                                'value_source': {}
                            }
                            if env_var.value_source:
                                env_entry['value_source'] = {
                                    'secret_key_ref': env_var.value_source.secret_key_ref,
                                    'config_map_key_ref': env_var.value_source.config_map_key_ref
                                }
                            c_env.append(env_entry)
                    
                    c_resources: Dict[str, Any] = {}
                    if container.resources:
                        c_resources = {
                            'limits': dict(container.resources.limits) if container.resources.limits else {},
                            'cpu_idle': container.resources.cpu_idle,
                            'startup_cpu_boost': container.resources.startup_cpu_boost
                        }
                    
                    c_ports: List[Dict[str, Any]] = []
                    if container.ports:
                        for port in container.ports:
                            c_ports.append({
                                'name': port.name,
                                'container_port': port.container_port
                            })
                    
                    c_mounts: List[Dict[str, Any]] = []
                    if container.volume_mounts:
                        for vm in container.volume_mounts:
                            c_mounts.append({
                                'name': vm.name,
                                'mount_path': vm.mount_path
                            })
                    
                    containers_list.append({
                        'name': container.name,
                        'image': container.image,
                        'command': list(container.command) if container.command else [],
                        'args': list(container.args) if container.args else [],
                        'env': c_env,
                        'resources': c_resources,
                        'ports': c_ports,
                        'volume_mounts': c_mounts,
                        'working_dir': container.working_dir,
                        'liveness_probe': {},
                        'startup_probe': {},
                        'depends_on': list(container.depends_on) if container.depends_on else []
                    })
            
            if template.volumes:
                for volume in template.volumes:
                    vol_info: Dict[str, Any] = {
                        'name': volume.name,
                        'secret': {},
                        'cloud_sql_instance': {},
                        'empty_dir': {},
                        'nfs': {},
                        'gcs': {}
                    }
                    if volume.secret:
                        items_list: List[Dict[str, Any]] = []
                        if volume.secret.items:
                            for item in volume.secret.items:
                                items_list.append({
                                    'path': item.path,
                                    'version': item.version,
                                    'mode': item.mode
                                })
                        vol_info['secret'] = {
                            'secret': volume.secret.secret,
                            'items': items_list,
                            'default_mode': volume.secret.default_mode
                        }
                    if volume.cloud_sql_instance:
                        vol_info['cloud_sql_instance'] = {
                            'instances': list(volume.cloud_sql_instance.instances) if volume.cloud_sql_instance.instances else []
                        }
                    volumes_list.append(vol_info)
            
            template_data = {
                'revision': template.revision,
                'labels': dict(template.labels) if template.labels else {},
                'annotations': dict(template.annotations) if template.annotations else {},
                'scaling': scaling_data,
                'vpc_access': vpc_access_data,
                'timeout': template.timeout.seconds if template.timeout else 0,
                'service_account': template.service_account,
                'containers': containers_list,
                'volumes': volumes_list,
                'execution_environment': template.execution_environment.name if hasattr(template.execution_environment, 'name') else str(template.execution_environment),
                'encryption_key': template.encryption_key,
                'max_request_timeout': template.max_request_timeout.seconds if template.max_request_timeout else 0,
                'session_affinity': template.session_affinity
            }
        
        # 트래픽 설정
        traffic_list: List[Dict[str, Any]] = []
        if service.traffic:
            for traffic in service.traffic:
                traffic_list.append({
                    'type': traffic.type_.name if hasattr(traffic.type_, 'name') else str(traffic.type_),
                    'revision': traffic.revision,
                    'percent': traffic.percent,
                    'tag': traffic.tag
                })
        
        # 터미널 조건
        if service.terminal_condition:
            condition = service.terminal_condition
            service_data['terminal_condition'] = {
                'type': condition.type_,
                'state': condition.state.name if hasattr(condition.state, 'name') else str(condition.state),
                'message': condition.message,
                'last_transition_time': condition.last_transition_time,
                'severity': condition.severity.name if hasattr(condition.severity, 'name') else str(condition.severity),
                'reason': condition.reason.name if hasattr(condition.reason, 'name') else str(condition.reason),
                'revision_reason': condition.revision_reason.name if hasattr(condition.revision_reason, 'name') else str(condition.revision_reason),
                'execution_reason': condition.execution_reason.name if hasattr(condition.execution_reason, 'name') else str(condition.execution_reason)
            }
        
        # 조건들
        conditions_list: List[Dict[str, Any]] = []
        if service.conditions:
            for condition in service.conditions:
                conditions_list.append({
                    'type': condition.type_,
                    'state': condition.state.name if hasattr(condition.state, 'name') else str(condition.state),
                    'message': condition.message,
                    'last_transition_time': condition.last_transition_time,
                    'severity': condition.severity.name if hasattr(condition.severity, 'name') else str(condition.severity),
                    'reason': condition.reason.name if hasattr(condition.reason, 'name') else str(condition.reason)
                })
        
        service_data['template'] = template_data
        service_data['traffic'] = traffic_list
        service_data['conditions'] = conditions_list

        # 편의를 위한 추가 필드
        service_data['ready'] = any(
            c.get('type') == 'Ready' and c.get('state') == 'CONDITION_SUCCEEDED'
            for c in conditions_list
        )
        
        # 컨테이너 이미지 및 리소스 (첫 번째 컨테이너)
        if containers_list:
            first_c = containers_list[0]
            service_data['image'] = first_c.get('image', 'N/A')
            limits = first_c.get('resources', {}).get('limits', {})
            service_data['cpu'] = limits.get('cpu', 'N/A')
            service_data['memory'] = limits.get('memory', 'N/A')
        else:
            service_data['image'] = 'N/A'
            service_data['cpu'] = 'N/A'
            service_data['memory'] = 'N/A'
        
        # 스케일링 정보
        service_data['min_instances'] = scaling_data.get('min_instance_count', 0)
        service_data['max_instances'] = scaling_data.get('max_instance_count', 100)
        
        return service_data
        
    except Exception as e:
        log_error(f"Cloud Run 서비스 상세 정보 수집 실패: {service.name}, Error={e}")
        return None


def load_mock_data():
    """mock_data.json에서 데이터를 로드합니다."""
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


def format_table_output(services: List[Dict]) -> None:
    """
    GCP Cloud Run 서비스 목록을 Rich 테이블 형식으로 출력합니다.
    
    Args:
        services: 서비스 정보 리스트
    """
    if not services:
        console.print("[yellow]표시할 GCP Cloud Run 정보가 없습니다.[/yellow]")
        return

    # 프로젝트, 지역, 이름 순으로 정렬
    services.sort(key=lambda x: (x.get("project_id", ""), x.get("region", ""), x.get("name", "")))

    table = Table(box=box.HORIZONTALS, expand=False, show_header=True, header_style="bold")
    
    table.add_column("Project", style="bold magenta")
    table.add_column("Region", style="bold cyan")
    table.add_column("Service Name", style="bold white")
    table.add_column("Ready", justify="center")
    table.add_column("URL", style="blue")
    table.add_column("CPU", justify="right", style="dim")
    table.add_column("Memory", justify="right", style="dim")
    table.add_column("Min/Max", justify="center", style="green")
    table.add_column("Image", style="dim")

    last_project = None
    last_region = None
    
    for i, service in enumerate(services):
        project_changed = service.get("project_id") != last_project
        region_changed = service.get("region") != last_region

        # 프로젝트가 바뀔 때 구분선 추가
        if i > 0 and project_changed:
            table.add_row("", "", "", "", "", "", "", "", "", end_section=True)

        # Ready 상태
        ready = service.get('ready', False)
        ready_status = "✓" if ready else "✗"
        ready_colored = f"[green]{ready_status}[/green]" if ready else f"[red]{ready_status}[/red]"
        
        # URL 단축
        url = service.get('uri', 'N/A')
        if url != 'N/A' and len(url) > 40:
            url = url[:37] + "..."
        
        # 이미지 단축
        image = service.get('image', 'N/A')
        if image != 'N/A' and len(image) > 30:
            image = image.split('/')[-1]  # 마지막 부분만 표시
            if len(image) > 30:
                image = image[:27] + "..."
        
        # 스케일링 정보
        min_instances = service.get('min_instances', 0)
        max_instances = service.get('max_instances', 100)
        scaling_info = f"{min_instances}/{max_instances}"
        
        display_values = [
            service.get("project_id", "") if project_changed else "",
            service.get("region", "") if project_changed or region_changed else "",
            service.get("name", "N/A"),
            ready_colored,
            url,
            service.get("cpu", "N/A"),
            service.get("memory", "N/A"),
            scaling_info,
            image
        ]
        
        table.add_row(*display_values)

        last_project = service.get("project_id")
        last_region = service.get("region")
    
    console.print(table)


def format_tree_output(services: List[Dict]) -> None:
    """
    GCP Cloud Run 서비스 목록을 트리 형식으로 출력합니다 (프로젝트/지역 계층).
    
    Args:
        services: 서비스 정보 리스트
    """
    if not services:
        console.print("[yellow]표시할 GCP Cloud Run 정보가 없습니다.[/yellow]")
        return

    # 프로젝트별로 그룹화
    projects = {}
    for service in services:
        project_id = service.get("project_id", "unknown")
        region = service.get("region", "unknown")
        
        if project_id not in projects:
            projects[project_id] = {}
        if region not in projects[project_id]:
            projects[project_id][region] = []
        
        projects[project_id][region].append(service)

    # 트리 구조 생성
    tree = Tree("🏃 [bold blue]GCP Cloud Run Services[/bold blue]")
    
    for project_id in sorted(projects.keys()):
        project_node = tree.add(f"📁 [bold magenta]{project_id}[/bold magenta]")
        
        for region in sorted(projects[project_id].keys()):
            region_services = projects[project_id][region]
            region_node = project_node.add(
                f"🌍 [bold cyan]{region}[/bold cyan] ({len(region_services)} services)"
            )
            
            for service in sorted(region_services, key=lambda x: x.get("name", "")):
                # 상태 아이콘
                ready = service.get('ready', False)
                status_icon = "🟢" if ready else "🔴"
                
                # 서비스 정보
                service_name = service.get("name", "N/A")
                cpu = service.get("cpu", "N/A")
                memory = service.get("memory", "N/A")
                min_instances = service.get("min_instances", 0)
                max_instances = service.get("max_instances", 100)
                
                service_info = (
                    f"{status_icon} [bold white]{service_name}[/bold white] - "
                    f"CPU: [blue]{cpu}[/blue], Memory: [green]{memory}[/green], "
                    f"Scale: {min_instances}-{max_instances}"
                )
                
                service_node = region_node.add(service_info)
                
                # 추가 세부 정보
                if service.get('uri'):
                    service_node.add(f"🔗 URL: {service['uri']}")
                
                if service.get('image'):
                    service_node.add(f"📦 Image: {service['image']}")
                
                # 트래픽 분산 정보
                traffic = service.get('traffic', [])
                if traffic:
                    for t in traffic:
                        revision = t.get('revision', 'N/A')
                        percent = t.get('percent', 0)
                        tag = t.get('tag', '')
                        traffic_info = f"🚦 Traffic: {percent}% -> {revision}"
                        if tag:
                            traffic_info += f" (tag: {tag})"
                        service_node.add(traffic_info)
                
                # 환경 변수 수
                containers = service.get('template', {}).get('containers', [])
                if containers and containers[0].get('env'):
                    env_count = len(containers[0]['env'])
                    service_node.add(f"🔧 Environment Variables: {env_count}")
                
                # 라벨
                labels = service.get('labels', {})
                if labels:
                    labels_text = ", ".join([f"{k}={v}" for k, v in labels.items()])
                    service_node.add(f"🏷️  Labels: {labels_text}")
                
                # VPC 커넥터
                vpc_access = service.get('template', {}).get('vpc_access', {})
                if vpc_access.get('connector'):
                    service_node.add(f"🔗 VPC Connector: {vpc_access['connector']}")

    console.print(tree)


def format_output(services: List[Dict], output_format: str = 'table') -> str:
    """
    서비스 데이터를 지정된 형식으로 포맷합니다.
    
    Args:
        services: 서비스 정보 리스트
        output_format: 출력 형식 ('table', 'tree', 'json', 'yaml')
    
    Returns:
        포맷된 출력 문자열 (table/tree의 경우 직접 출력하고 빈 문자열 반환)
    """
    if output_format == 'table':
        format_table_output(services)
        return ""
    elif output_format == 'tree':
        format_tree_output(services)
        return ""
    elif output_format == 'json':
        return format_gcp_output(services, 'json')
    elif output_format == 'yaml':
        return format_gcp_output(services, 'yaml')
    else:
        # 기본값은 테이블
        format_table_output(services)
        return ""


def format_paste_output(services: List[Dict]) -> None:
    """Cloud Run 서비스 목록을 -p (paste) 모드용 CSV로 출력합니다."""
    for s in services:
        row = [
            s.get('project_id', '-'),
            s.get('region', '-'),
            s.get('name', '-'),
            s.get('url', '-'),
            s.get('last_modifier', '-'),
            s.get('status', '-'),
        ]
        print(",".join(str(c) for c in row))


class GcpRunInfoCommand(BaseCommand):
    """GCP Cloud Run 서비스 정보 조회 커맨드"""

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
            '-n', '--name', '--service-name',
            dest='name',
            help='서비스 이름으로 필터링 (콤마 구분 가능, 부분 일치)'
        )
        parser.add_argument(
            '-r', '--region', '--regions',
            dest='region',
            help='지역으로 필터링 (콤마 구분 가능, 예: us-central1)'
        )
        parser.add_argument(
            '-p', '--paste',
            nargs='?',
            const=True,
            default=False,
            help='스프레드시트 복사용 콤마(,) 구분 텍스트 출력'
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
        if getattr(args, 'mock', False):
            services = load_mock_data()
            filtered = []
            name_filter = getattr(args, 'name', None)
            proj_filter = getattr(args, 'project', None)
            reg_filter = getattr(args, 'region', None)

            name_patterns = [p.strip().lower() for p in name_filter.split(',')] if name_filter else []
            proj_patterns = [p.strip().lower() for p in proj_filter.split(',')] if proj_filter else []

            for s in services:
                s_name = str(s.get('name', '')).lower()
                s_proj = str(s.get('project_id', '')).lower()
                s_reg = str(s.get('region', '')).lower()

                if name_patterns and not any(p in s_name for p in name_patterns):
                    continue
                if proj_patterns and not any(p in s_proj for p in proj_patterns):
                    continue
                if reg_filter and reg_filter.lower() not in s_reg:
                    continue
                filtered.append(s)
            return CommandResult(
                data=filtered,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )

        if not GCP_RUN_AVAILABLE:
            console.print("[red]❌ google-cloud-run 패키지가 설치되지 않았습니다.[/red]")
            console.print("[yellow]   pip install 'ic-cli[gcp]' 또는 pip install google-cloud-run[/yellow]")
            console.print("[yellow]   Mock 데이터로 테스트하려면 --mock 옵션을 사용하세요.[/yellow]")
            return CommandResult(data=[], error="google-cloud-run is not installed", success=False)

        try:
            log_info_non_console("GCP Cloud Run 서비스 조회 시작")
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

            all_services = resource_collector.parallel_collect(
                projects, 
                fetch_run_services,
                getattr(args, 'region', None)
            )

            filters = {}
            if getattr(args, 'name', None):
                filters['name'] = args.name
            if getattr(args, 'project', None):
                filters['project'] = args.project
            if getattr(args, 'region', None):
                filters['region'] = args.region

            filtered_services = resource_collector.apply_filters(all_services, filters)
            return CommandResult(
                data=filtered_services,
                table_renderer=format_table_output,
                tree_renderer=format_tree_output,
                paste_renderer=format_paste_output,
            )
        except Exception as e:
            log_exception(e)
            console.print(f"[bold red]오류 발생: {e}[/bold red]")
            return CommandResult(data=[], error=str(e), success=False)


def main(args, config=None) -> None:
    GcpRunInfoCommand().run(args, config)


def add_arguments(parser) -> None:
    GcpRunInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Cloud Run 서비스 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)