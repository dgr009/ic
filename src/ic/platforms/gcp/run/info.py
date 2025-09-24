#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, List, Optional, Any
from google.cloud.run_v2 import ServicesClient
from google.cloud.run_v2.types import ListServicesRequest, GetServiceRequest
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


def fetch_run_services_via_mcp(mcp_connector, project_id: str, region_filter: str = None) -> List[Dict]:
    """
    MCP 서버를 통해 GCP Cloud Run 서비스를 가져옵니다.
    
    Args:
        mcp_connector: MCP GCP 커넥터
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        Cloud Run 서비스 정보 리스트
    """
    try:
        params = {
            'project_id': project_id,
            'region_filter': region_filter
        }
        
        response = mcp_connector.execute_gcp_query('run', 'list_services', params)
        if response.success:
            return response.data.get('services', [])
        else:
            log_error(f"MCP run services query failed: {response.error}")
            return []
            
    except Exception as e:
        log_error(f"MCP run services fetch failed: {e}")
        return []


def fetch_run_services_direct(project_id: str, region_filter: str = None) -> List[Dict]:
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
        
        # 일반적인 Cloud Run 지원 지역 목록
        regions = [
            'us-central1', 'us-east1', 'us-east4', 'us-west1', 'us-west2', 'us-west3', 'us-west4',
            'europe-west1', 'europe-west2', 'europe-west3', 'europe-west4', 'europe-west6',
            'europe-central2', 'europe-north1',
            'asia-east1', 'asia-east2', 'asia-northeast1', 'asia-northeast2', 'asia-northeast3',
            'asia-south1', 'asia-southeast1', 'asia-southeast2',
            'australia-southeast1',
            'northamerica-northeast1', 'southamerica-east1'
        ]
        
        if region_filter:
            regions = [region_filter]
        
        for region in regions:
            try:
                # 해당 지역의 서비스 가져오기
                parent = f"projects/{project_id}/locations/{region}"
                request = ListServicesRequest(parent=parent)
                
                response = run_client.list_services(request=request)
                
                for service in response:
                    service_data = collect_service_details(
                        run_client, project_id, region, service
                    )
                    if service_data:
                        all_services.append(service_data)
                        
            except gcp_exceptions.Forbidden:
                # 지역에 대한 접근 권한이 없는 경우 무시
                continue
            except gcp_exceptions.NotFound:
                # 지역에 서비스가 없는 경우 무시
                continue
            except Exception as e:
                log_error(f"지역 {region}에서 Cloud Run 서비스 조회 실패: {project_id}, Error={e}")
                continue
        
        log_info(f"프로젝트 {project_id}에서 {len(all_services)}개 Cloud Run 서비스 발견")
        return all_services
        
    except gcp_exceptions.PermissionDenied:
        log_error(f"프로젝트 {project_id}에 대한 Cloud Run 권한이 없습니다")
        return []
    except Exception as e:
        log_error(f"Cloud Run 서비스 조회 실패: {project_id}, Error={e}")
        return []


def fetch_run_services(project_id: str, region_filter: str = None) -> List[Dict]:
    """
    GCP Cloud Run 서비스를 가져옵니다 (MCP 우선, 직접 API 폴백).
    
    Args:
        project_id: GCP 프로젝트 ID
        region_filter: 지역 필터 (선택사항)
    
    Returns:
        Cloud Run 서비스 정보 리스트
    """
    # MCP 서비스 사용 시도
    if MCP_AVAILABLE:
        try:
            mcp_service = MCPGCPService('run')
            return mcp_service.execute_with_fallback(
                'list_services',
                {'project_id': project_id, 'region_filter': region_filter},
                lambda project_id, region_filter: fetch_run_services_direct(project_id, region_filter)
            )
        except Exception as e:
            log_error(f"MCP service failed, using direct API: {e}")
    
    # 직접 API 사용
    return fetch_run_services_direct(project_id, region_filter)


def collect_service_details(run_client: ServicesClient,
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
        if service.template:
            template = service.template
            service_data['template'] = {
                'revision': template.revision,
                'labels': dict(template.labels) if template.labels else {},
                'annotations': dict(template.annotations) if template.annotations else {},
                'scaling': {},
                'vpc_access': {},
                'timeout': template.timeout.seconds if template.timeout else 0,
                'service_account': template.service_account,
                'containers': [],
                'volumes': [],
                'execution_environment': template.execution_environment.name if hasattr(template.execution_environment, 'name') else str(template.execution_environment),
                'encryption_key': template.encryption_key,
                'max_request_timeout': template.max_request_timeout.seconds if template.max_request_timeout else 0,
                'session_affinity': template.session_affinity
            }
            
            # 스케일링 설정
            if template.scaling:
                service_data['template']['scaling'] = {
                    'min_instance_count': template.scaling.min_instance_count,
                    'max_instance_count': template.scaling.max_instance_count
                }
            
            # VPC 액세스 설정
            if template.vpc_access:
                service_data['template']['vpc_access'] = {
                    'connector': template.vpc_access.connector,
                    'egress': template.vpc_access.egress.name if hasattr(template.vpc_access.egress, 'name') else str(template.vpc_access.egress),
                    'network_interfaces': []
                }
                
                if template.vpc_access.network_interfaces:
                    for ni in template.vpc_access.network_interfaces:
                        ni_info = {
                            'network': ni.network,
                            'subnetwork': ni.subnetwork,
                            'tags': list(ni.tags) if ni.tags else []
                        }
                        service_data['template']['vpc_access']['network_interfaces'].append(ni_info)
            
            # 컨테이너 정보
            if template.containers:
                for container in template.containers:
                    container_info = {
                        'name': container.name,
                        'image': container.image,
                        'command': list(container.command) if container.command else [],
                        'args': list(container.args) if container.args else [],
                        'env': [],
                        'resources': {},
                        'ports': [],
                        'volume_mounts': [],
                        'working_dir': container.working_dir,
                        'liveness_probe': {},
                        'startup_probe': {},
                        'depends_on': list(container.depends_on) if container.depends_on else []
                    }
                    
                    # 환경 변수
                    if container.env:
                        for env_var in container.env:
                            env_info = {
                                'name': env_var.name,
                                'value': env_var.value,
                                'value_source': {}
                            }
                            if env_var.value_source:
                                env_info['value_source'] = {
                                    'secret_key_ref': env_var.value_source.secret_key_ref,
                                    'config_map_key_ref': env_var.value_source.config_map_key_ref
                                }
                            container_info['env'].append(env_info)
                    
                    # 리소스 설정
                    if container.resources:
                        service_data['template']['containers'][0]['resources'] = {
                            'limits': dict(container.resources.limits) if container.resources.limits else {},
                            'cpu_idle': container.resources.cpu_idle,
                            'startup_cpu_boost': container.resources.startup_cpu_boost
                        }
                    
                    # 포트 설정
                    if container.ports:
                        for port in container.ports:
                            port_info = {
                                'name': port.name,
                                'container_port': port.container_port
                            }
                            container_info['ports'].append(port_info)
                    
                    # 볼륨 마운트
                    if container.volume_mounts:
                        for vm in container.volume_mounts:
                            vm_info = {
                                'name': vm.name,
                                'mount_path': vm.mount_path
                            }
                            container_info['volume_mounts'].append(vm_info)
                    
                    service_data['template']['containers'].append(container_info)
            
            # 볼륨 정보
            if template.volumes:
                for volume in template.volumes:
                    volume_info = {
                        'name': volume.name,
                        'secret': {},
                        'cloud_sql_instance': {},
                        'empty_dir': {},
                        'nfs': {},
                        'gcs': {}
                    }
                    
                    if volume.secret:
                        volume_info['secret'] = {
                            'secret': volume.secret.secret,
                            'items': [],
                            'default_mode': volume.secret.default_mode
                        }
                        if volume.secret.items:
                            for item in volume.secret.items:
                                item_info = {
                                    'path': item.path,
                                    'version': item.version,
                                    'mode': item.mode
                                }
                                volume_info['secret']['items'].append(item_info)
                    
                    if volume.cloud_sql_instance:
                        volume_info['cloud_sql_instance'] = {
                            'instances': list(volume.cloud_sql_instance.instances) if volume.cloud_sql_instance.instances else []
                        }
                    
                    service_data['template']['volumes'].append(volume_info)
        
        # 트래픽 설정
        if service.traffic:
            for traffic in service.traffic:
                traffic_info = {
                    'type': traffic.type_.name if hasattr(traffic.type_, 'name') else str(traffic.type_),
                    'revision': traffic.revision,
                    'percent': traffic.percent,
                    'tag': traffic.tag
                }
                service_data['traffic'].append(traffic_info)
        
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
        if service.conditions:
            for condition in service.conditions:
                condition_info = {
                    'type': condition.type_,
                    'state': condition.state.name if hasattr(condition.state, 'name') else str(condition.state),
                    'message': condition.message,
                    'last_transition_time': condition.last_transition_time,
                    'severity': condition.severity.name if hasattr(condition.severity, 'name') else str(condition.severity),
                    'reason': condition.reason.name if hasattr(condition.reason, 'name') else str(condition.reason)
                }
                service_data['conditions'].append(condition_info)
        
        # 편의를 위한 추가 필드
        service_data['ready'] = any(
            condition.get('type') == 'Ready' and condition.get('state') == 'CONDITION_SUCCEEDED'
            for condition in service_data['conditions']
        )
        
        # 컨테이너 이미지 (첫 번째 컨테이너)
        if service_data['template'].get('containers'):
            service_data['image'] = service_data['template']['containers'][0].get('image', 'N/A')
        else:
            service_data['image'] = 'N/A'
        
        # CPU/메모리 리소스 (첫 번째 컨테이너)
        if (service_data['template'].get('containers') and 
            service_data['template']['containers'][0].get('resources', {}).get('limits')):
            limits = service_data['template']['containers'][0]['resources']['limits']
            service_data['cpu'] = limits.get('cpu', 'N/A')
            service_data['memory'] = limits.get('memory', 'N/A')
        else:
            service_data['cpu'] = 'N/A'
            service_data['memory'] = 'N/A'
        
        # 스케일링 정보
        scaling = service_data['template'].get('scaling', {})
        service_data['min_instances'] = scaling.get('min_instance_count', 0)
        service_data['max_instances'] = scaling.get('max_instance_count', 100)
        
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


def main(args):
    """
    메인 함수 - GCP Cloud Run 서비스 정보를 조회하고 출력합니다.
    
    Args:
        args: CLI 인자 객체
    """
    try:
        log_info("GCP Cloud Run 서비스 조회 시작")
        
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
        
        # 병렬로 서비스 수집
        all_services = resource_collector.parallel_collect(
            projects, 
            fetch_run_services,
            getattr(args, 'region', None)
        )
        
        if not all_services:
            console.print("[yellow]조회된 Cloud Run 서비스가 없습니다.[/yellow]")
            return
        
        # 필터 적용
        filters = {}
        if hasattr(args, 'service') and args.service:
            filters['name'] = args.service
        if hasattr(args, 'project') and args.project:
            filters['project'] = args.project
        if hasattr(args, 'region') and args.region:
            filters['region'] = args.region
        
        filtered_services = resource_collector.apply_filters(all_services, filters)
        
        # 출력 형식 결정
        output_format = getattr(args, 'output', 'table')
        
        # 결과 출력
        if output_format in ['json', 'yaml']:
            output_text = format_output(filtered_services, output_format)
            console.print(output_text)
        else:
            format_output(filtered_services, output_format)
        
        log_info(f"총 {len(filtered_services)}개 서비스 조회 완료")
        
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
        '-s', '--service', 
        help='서비스 이름으로 필터링 (부분 일치)'
    )
    parser.add_argument(
        '-r', '--region', 
        help='지역으로 필터링 (예: us-central1)'
    )
    parser.add_argument(
        '-o', '--output', 
        choices=['table', 'tree', 'json', 'yaml'],
        default='table',
        help='출력 형식 선택 (기본값: table)'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCP Cloud Run 서비스 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)